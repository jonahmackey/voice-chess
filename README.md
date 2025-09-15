# Voice chess

Play chess with your voice. **Voice Chess** uses [python-chess](https://python-chess.readthedocs.io/), [Stockfish](https://stockfishchess.org/), and [Boson AI’s](https://www.boson.ai/) audio models to create a fully voice-driven chess experience — complete with **Magnus Carlsen’s cloned voice** as your opponent.

This project was built by [Jonah Mackey](https://jonahmackey.github.io/) and Yuchong Zhang during the **Boson AI Higgs Audio V2 Hackathon**.  
We had access to both the [Higgs Audio V2 generation model](https://www.boson.ai/blog/higgs-audio-v2) and an their unreleased audio understanding model, hosted on a Boson-provided VM.

## Features
- **Voice input**: Speak your moves naturally — “Hmm... I'd like to move my pawn to e4.”  
- **Player vs Engine (PvE)**: Play against Stockfish, voiced by Magnus Carlsen.  
- **Player vs Player (PvP)**: Two players take turns speaking their moves, while Magnus commentates the game.
- **Voice synthesis**: Game commentary and engine moves spoken aloud in Magnus Carlsen's voice.  
- **Visualization**: Live chessboard visualization with Matplotlib.  
- **Remote model integration**: Local game connects to VM servers for transcription and speech synthesis.

## How It works

### Modes
* Player vs. Engine (`main_pve.py`)
* Player vs. Player (`main_pvp.py`)

### Player Turn
1. Voice is recorded locally as you speak your move (`audio_utils.listen()`). 
2. Audio sent to VM (`transcribe.py`), where the understanding model transcibes the audio to standard algebraic chess notation (SAN).
3. The SAN move is sent back to the local machine and executed with `python-chess`.

### Engine Turn
1. Stockfish selects a move.
2. Move is described in natural language (`move_descriptions.py`).
3. Text is sent to VM (`gen_audio.py`), where the speech synthesis model generates audio in Magnus Carlsen's voice.
4. Audio is sent back to the local machine and played aloud.

### Commentary
- Optional LLM call (`commentary.py`) produces a one-sentence board comment in PvP mode  (e.g., "Nice! Black goes with the Sicilian Defense.")

## Project Structure

```
voice-chess/
├── main_pve.py                 # Entry point: player vs Stockfish (engine speaks as Magnus)
├── main_pvp.py                 # Entry point: player vs player (commentated by Magnus)
│
├── src/                        # Core local client-side modules
│   ├── transcribe.py           # Send recorded audio to remote ASR server
│   ├── audio_utils.py          # Record voice input with VAD
│   ├── gen_audio.py            # Send text to remote TTS server + play audio aloud
│   ├── commentary.py           # Generate one-sentence game commentary using an LLM
│   ├── describe_move.py        # Convert SAN chess moves into natural language descriptions
│   └── visualize.py            # Matplotlib chessboard visualization
│
├── server_code/                # Hackathon-only VM server code (not runnable locally)
│   ├── transcribe_server.py    # Flask API: transcribe audio into SAN chess moves with understanding model.
│   ├── audio_server.py         # FastAPI API: generate audio in Magnus Carlsen's voice with speech synthesis model.
│
├── scene_prompts/              # Prompt templates for generation
│   └── quiet_room.txt          # Example prompt for consistent acoustic environment
│
├── voice_prompts/              # Voice reference data for cloning Magnus’s voice
│   ├── magnus.wav              # 30s Magnus Carlsen audio sample (reference voice)
│   └── magnus.txt              # Transcript of the reference audio
│
├── requirements.txt            # Python dependencies for local client code
└── README.md                   # Project documentation
```

## Installation

### Requirements
- Python 3.10+
- [Stockfish](https://stockfishchess.org/download/) installed and available at `./stockfish/stockfish-ex`.
- A microphone and speakers/headphones

### Setup
```bash
git clone https://github.com/jonahmackey/voice-chess.git
cd voice-chess

# Install dependencies
pip install -r requirements.txt
```

## VM Code (Hackathon Only)

The `vm_code/` directory contains Flask/FastAPI servers deployed on the Boson AI VM:
* `transcribe_server.py` → Routes audio through Higgs ASR.
* `audio_server.py` → Routes text through Higgs Audio V2 for TTS.

These won’t run outside Boson’s infrastructure, but are included for completeness and adaptation.