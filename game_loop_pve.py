import os
import time
import threading
import queue

import chess
import chess.engine
# If needed on macOS, force a GUI backend BEFORE importing pyplot:
import matplotlib
matplotlib.use("TkAgg")

import matplotlib.pyplot as plt
plt.ion() 

from src.transcribe_move import listen, transcribe_audio
from src.visualize import BoardViewer

# --- Configure Stockfish path & strength ---
STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "./stockfish/stockfish-ex")
ENGINE_TIME_SEC = 0.5         # per-move think time (increase for stronger play)
ENGINE_SKILL = 15             # 0-20 (may be ignored by some builds)
HUMAN_PLAYS_WHITE = True      # set False to play Black


from src.gen_audio import gen_audio_from_api
from functools import partial

HOST = "ssh8.vast.ai"
USERNAME = "root"
PORT = 12812
KEYFILE_NAME = "./team03_private_key"
LOCAL_PORT = 8000
REMOTE_HOST = "127.0.0.1"
REMOTE_PORT =8000
MODE = "base64" # either base64 or url

run_gen_audio = partial(
    gen_audio_from_api,
    temperature=1.0,
    host=HOST,
    port=PORT,
    username=USERNAME,
    key_filename=KEYFILE_NAME,
    local_port=LOCAL_PORT,
    remote_host=REMOTE_HOST,
    remote_port=REMOTE_PORT,
    mode=MODE,
)

def main():
    board = chess.Board()
    print("Starting a new chess game (Player vs. Engine)")
    
    # Fixed POV from the human player's side
    start_pov = "white" if HUMAN_PLAYS_WHITE else "black"
    viewer = BoardViewer(perspective=start_pov)
    viewer.update(board, show_last_move=False)
    
    # Engine
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    engine.configure({"Skill Level": ENGINE_SKILL})
    
    while not board.is_game_over():
        side_to_move_is_human = (board.turn == chess.WHITE) == HUMAN_PLAYS_WHITE
        
        if side_to_move_is_human:
            # Player move
            print("Player's turn...")
            
            move_audio = listen() # listens for the move audio
            move_text = transcribe_audio(move_audio) # transcribes move audio into SAN
            
            try: # Tries to execute the move
                board.push_san(move_text)
                print("Move executed")
                viewer.update(board, show_last_move=True) # visualize board
            except ValueError:
                print("Invalid move:", move_text, "— please try again.")
                continue
            
        else:
            # Engine move
            print("\nEngine is thinking...")
            
            result = engine.play(board, chess.engine.Limit(time=ENGINE_TIME_SEC)) # get engines move
            
            if result.move is None:
                print("Engine failed to find a move.")
                break
            
            san = board.san(result.move) # convert move to SAN for TTS
            print(f"Stockfish plays: {san}")
            
            run_gen_audio(f"I will play {san}") # generate and play audio of the engines move
            
            board.push(result.move) # execute the move
            viewer.update(board, show_last_move=True) # visualize board
            
    print("\nGame over!")
    print("Result:", board.result())

if __name__ == "__main__":
    main()