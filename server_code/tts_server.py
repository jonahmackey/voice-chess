# higgs_api_server.py
from __future__ import annotations
import io
import os
import sys
import uuid
import base64
from pathlib import Path
from typing import Literal, Optional

import torch
import soundfile as sf
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from loguru import logger

# Import model utilities
sys.path.insert(0, str(Path("/root/voice-chess").resolve()))
from generate_audio import (
    HiggsAudioModelClient,
    prepare_generation_context,
    prepare_chunk_text,
    normalize_chinese_punctuation,
)

# Config
OUTPUT_DIR = Path(os.environ.get("HIGGS_OUT_DIR", "/tmp/higgs_audio_out")).resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_TOKENIZER_PATH = os.getenv("HIGGS_AUDIO_TOKENIZER", "bosonai/higgs-audio-v2-tokenizer")
MODEL_PATH = os.getenv("HIGGS_MODEL_PATH", "bosonai/higgs-audio-v2-generation-3B-base")

# Logging
logger.remove()
logger.add(sys.stderr, level="INFO")

# FastAPI app
app = FastAPI(title="Higgs Audio – Persistent Model API")
app.mount("/audio", StaticFiles(directory=str(OUTPUT_DIR)), name="audio")


# Request/response schemas
class GenerateRequest(BaseModel):
    transcript: str = Field(..., description="Text to turn into speech/audio")
    temperature: float = Field(1.0, ge=0.0, le=2.0)
    top_k: int = Field(50, ge=1)
    top_p: float = Field(0.95, gt=0.0, le=1.0)
    ras_win_len: int = Field(7, description="<=0 disables RAS")
    ras_win_max_num_repeat: int = Field(2, ge=0)
    chunk_method: Optional[Literal["speaker", "word"]] = None
    chunk_max_word_num: int = Field(200, ge=1)
    chunk_max_num_turns: int = Field(1, ge=1)
    generation_chunk_buffer_size: Optional[int] = None
    seed: Optional[int] = None
    scene_prompt: Optional[str] = None
    ref_audio: Optional[str] = None
    ref_audio_in_system_message: bool = False
    return_audio: Literal["base64", "url"] = "base64"
    filename: Optional[str] = None  # only used for URL mode

class GenerateResponse(BaseModel):
    id: str
    audio_base64: Optional[str] = None
    audio_url: Optional[str] = None
    sample_rate: int

class HealthResponse(BaseModel):
    status: str
    device: str
    dtype: str


# Globals (model stays warm)
MODEL_CLIENT: Optional[HiggsAudioModelClient] = None

@app.on_event("startup")
def _startup():
    global MODEL_CLIENT
    device = "cuda:0" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
    logger.info(f"Starting server on device={device}")
    # Build model client ONCE
    MODEL_CLIENT = HiggsAudioModelClient(
        model_path=MODEL_PATH,
        audio_tokenizer=AUDIO_TOKENIZER_PATH,
        device=device,
        device_id=0 if device.startswith("cuda") else None,
        max_new_tokens=2048,
        use_static_kv_cache=(device.startswith("cuda")),
    )
    logger.info("Model warmed and ready.")

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    assert MODEL_CLIENT is not None
    return HealthResponse(
        status="ok",
        device=str(MODEL_CLIENT._device),
        dtype=str(MODEL_CLIENT._model.dtype),
    )

@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest, request: Request) -> GenerateResponse:
    """Generate audio from text using the Higgs Audio V2 generation model."""
    assert MODEL_CLIENT is not None
    # Normalize transcript (match your CLI behavior)
    transcript = normalize_chinese_punctuation(req.transcript).strip()
    if transcript and not any(transcript.endswith(c) for c in [".","!","?",",",";","\"", "'", "</SE_e>", "</SE>"]):
        transcript += "."

    # Prepare messages & audio_ids (voice prompts)
    messages, audio_ids = prepare_generation_context(
        scene_prompt="./scene_prompts/quiet_room.txt",
        ref_audio="magnus",
        ref_audio_in_system_message=req.ref_audio_in_system_message,
        audio_tokenizer=MODEL_CLIENT._audio_tokenizer,
        speaker_tags=[],  # single-speaker default; pass tags if you want
    )

    # Chunking
    chunked_text = prepare_chunk_text(
        transcript,
        chunk_method=req.chunk_method,
        chunk_max_word_num=req.chunk_max_word_num,
        chunk_max_num_turns=req.chunk_max_num_turns,
    )

    # Generate
    concat_wv, sr, _ = MODEL_CLIENT.generate(
        messages=messages,
        audio_ids=audio_ids,
        chunked_text=chunked_text,
        generation_chunk_buffer_size=req.generation_chunk_buffer_size,
        temperature=req.temperature,
        top_k=req.top_k,
        top_p=req.top_p,
        ras_win_len=req.ras_win_len,
        ras_win_max_num_repeat=req.ras_win_max_num_repeat,
        seed=req.seed,
    )

    # Encode to WAV in memory (seekable buffer)
    mem = io.BytesIO()
    sf.write(mem, concat_wv, sr, format="WAV")
    mem.seek(0)

    if req.return_audio == "base64":
        b64 = base64.b64encode(mem.read()).decode("utf-8")
        return GenerateResponse(id=str(uuid.uuid4()), audio_base64=b64, sample_rate=sr)

    # return URL
    audio_id = str(uuid.uuid4())
    out = Path(req.filename).name if req.filename else f"{audio_id}.wav"
    if not out.lower().endswith(".wav"):
        out += ".wav"
    out_path = OUTPUT_DIR / out
    out_path.write_bytes(mem.read())
    url = f"{str(request.base_url).rstrip('/')}/audio/{out_path.name}"
    return GenerateResponse(id=audio_id, audio_url=url, sample_rate=sr)
