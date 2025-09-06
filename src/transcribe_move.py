import collections
import sounddevice as sd
import webrtcvad
import requests
import time
import wave
import tempfile
import os
import numpy as np

SERVER = "http://localhost:8080/transcribe"  # via SSH tunnel
RATE = 16000
CHANNELS = 1
FRAME_DURATION = 30  # ms

PRE_BUFFER_MS = 800        # was 300 — capture more lead-in before VAD fires
POST_BUFFER_MS = 1200
MAX_CHUNK_SEC = 5
MIN_CHUNK_SEC = 0.5
VAD_AGGRESSIVENESS = 0
# Use separate thresholds for start vs end
TRIGGER_THRESHOLD_START = 0.55   # easier to start (VAD-only)
TRIGGER_THRESHOLD_END   = 0.80   # stricter to end (VAD+energy)

FRAME_RMS_MIN  = 400
CHUNK_RMS_MIN  = 300

vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)

def rms16(pcm_bytes: bytes) -> float:
    """Root-mean-square of int16 PCM."""
    if not pcm_bytes:
        return 0.0
    arr = np.frombuffer(pcm_bytes, dtype=np.int16)
    # guard against empty array
    if arr.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(arr.astype(np.float32) ** 2)))

# --------------------------
# Frame generator: yields PCM16 bytes
# --------------------------
def frame_generator():
    frame_len = int(RATE * FRAME_DURATION / 1000)
    with sd.InputStream(
        samplerate=RATE,
        channels=CHANNELS,
        dtype='int16',
        blocksize=frame_len,   # deliver frames at our desired size
        latency='low'
    ) as stream:
        while True:
            data, _ = stream.read(frame_len)
            yield data.tobytes()

# --------------------------
# Send audio to server and get transcription
# --------------------------
def transcribe_audio(audio_bytes):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
        path = tmpfile.name
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(RATE)
            wf.writeframes(audio_bytes)

    try:
        with open(path, "rb") as f:
            resp = requests.post(SERVER, files={"audio": f}, timeout=60)
            try:
                data = resp.json()
                # Preferred format:
                transcription = data.get("transcription")
                if transcription is None:
                    # Fallback if server returns {"text": "..."}
                    transcription = data.get("text", "")
                    if transcription:
                        print("⚠️ Using 'text' key from server JSON")
                    else:
                        print("⚠️ Server response missing transcription/text:", data)
                return transcription
            except Exception as e:
                print("⚠️ Failed to parse server JSON:", e, resp.text)
                return ""
    finally:
        os.remove(path)

# --------------------------
# Listen for one full chess move (VAD + energy + buffers)
# --------------------------
def listen():
    frames = frame_generator()

    pre_n  = max(1, int(PRE_BUFFER_MS  / FRAME_DURATION))
    post_n = max(1, int(POST_BUFFER_MS / FRAME_DURATION))

    pre_buffer_frames  = collections.deque(maxlen=pre_n)
    post_buffer_frames = collections.deque(maxlen=post_n)

    triggered = False
    voiced_frames = []
    chunk_start_time = None

    print("Listening for your chess move...")

    for frame in frames:
        # For END decisions we’ll still use VAD+energy; for START use VAD-only
        vad_flag = vad.is_speech(frame, RATE)
        energy_ok = (rms16(frame) >= FRAME_RMS_MIN)

        if not triggered:
            # --- START detection: VAD-only & lower threshold, to avoid missing initial words ---
            pre_buffer_frames.append(frame)
            voiced_votes = sum(1 for f in pre_buffer_frames if vad.is_speech(f, RATE))
            # require buffer to be "full" so we actually have PRE_BUFFER_MS to prepend
            if (len(pre_buffer_frames) == pre_buffer_frames.maxlen and
                voiced_votes > TRIGGER_THRESHOLD_START * len(pre_buffer_frames)):
                triggered = True
                chunk_start_time = time.time()
                # prepend the whole pre-buffer (captures the word onset)
                voiced_frames.extend(pre_buffer_frames)
                pre_buffer_frames.clear()
                print("Speech detected")
        else:
            # --- collecting speech ---
            voiced_frames.append(frame)
            post_buffer_frames.append(frame)

            # END detection: stricter — require majority of last POST buffer to be non-voiced OR hit max length
            end_unvoiced_votes = sum(
                1 for f in post_buffer_frames if not (vad.is_speech(f, RATE) and rms16(f) >= FRAME_RMS_MIN)
            )
            chunk_len = time.time() - chunk_start_time

            if ((len(post_buffer_frames) == post_buffer_frames.maxlen and
                 end_unvoiced_votes > TRIGGER_THRESHOLD_END * len(post_buffer_frames))
                or chunk_len >= MAX_CHUNK_SEC):
                # include post-buffer
                voiced_frames.extend(post_buffer_frames)

                total_chunk_len = time.time() - chunk_start_time
                chunk_bytes = b"".join(voiced_frames)
                overall_rms = rms16(chunk_bytes)

                if total_chunk_len >= MIN_CHUNK_SEC and overall_rms >= CHUNK_RMS_MIN:
                    print("Speech ended")
                    return chunk_bytes
                else:
                    # reset and keep listening
                    triggered = False
                    voiced_frames = []
                    post_buffer_frames.clear()
                    print("Ignored short/quiet audio chunk")
                    
# --------------------------
# Test loop
# --------------------------
if __name__ == "__main__":
    while True:
        print("\nWaiting for next move...")
        move_audio = listen()
        move_text = transcribe_audio(move_audio)
        print("Transcription:", move_text)