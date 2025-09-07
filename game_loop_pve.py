import os
import random

import chess
import chess.engine

# If needed on macOS, force a GUI backend BEFORE importing pyplot:
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
plt.ion() 

from src.transcribe_move import listen, transcribe_audio
from src.visualize import BoardViewer
from src.gen_audio import run_gen_audio
from src.gen_move_description import describe_san_first_person, describe_san

# --- Configure Stockfish path & strength ---
STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "./stockfish/stockfish-ex")
ENGINE_TIME_SEC = 1         # per-move think time (increase for stronger play)
ENGINE_SKILL = 15             # 0-20 (may be ignored by some builds)
HUMAN_PLAYS_WHITE = True      # set False to play Black

def main():
    board = chess.Board()
    print("Starting a new chess game (Player vs. Engine)")
    
    # Fixed POV from the human player's side
    start_pov = "white" if HUMAN_PLAYS_WHITE else "black"
    viewer = BoardViewer(perspective=start_pov)
    viewer.update(board, show_last_move=False, text="Game start")
    
    # Engine
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    engine.configure({"Skill Level": ENGINE_SKILL})
    
    # Make announement at the beginning of the game.
    run_gen_audio("""Welcome to Voice Chess! This is Magnus Carlsen speaking. Do you want to play a game? Begin by saying your moves out loud. I'll let you go first.""")
    
    end_reason = None
    try:
        while not board.is_game_over():
            side_to_move_is_human = (board.turn == chess.WHITE) == HUMAN_PLAYS_WHITE
            
            if side_to_move_is_human:
                # Player move
                print("Player's turn...")
                
                move_audio = listen() # listens for the move audio
                move_text = transcribe_audio(move_audio).split()[0] # transcribes move audio into SAN
                print("Transcription: ", move_text)
                
                if move_text == "resign":
                    end_reason = "resign"
                    break
                elif move_text == "draw":
                    # sample a number between 0 and 1
                    if random.random() < 0.3:
                        end_reason = "draw"
                        viewer.update(board, show_last_move=True, text=f"Accepted")
                        break
                    else:
                        run_gen_audio("I decline your draw offer. Let's continue.")
                        viewer.update(board, show_last_move=True, text=f"Draw offer declined")
                        continue
                
                try: # Tries to execute the move
                    board.push_san(move_text)
                    print("Move executed")
                    viewer.update(board, show_last_move=True, text=f"Player move: {move_text}") # visualize board
                except ValueError:
                    run_gen_audio(f"Did you try to play {describe_san(move_text)}? That isn't a legal move. Please try again.")
                    print("Invalid move:", move_text, "— please try again.")
                    viewer.update(board, show_last_move=True, text=f"Player move: {move_text} - Invalid!")
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
                
                side = "white" if board.turn == chess.WHITE else "black"
                san_description = describe_san_first_person(san, side=side)
                run_gen_audio(san_description) # generate and play audio of the engines move # generate and play audio of the engines move
                
                board.push(result.move) # execute the move
                viewer.update(board, show_last_move=True, text=f"Engine move: {san}") # visualize board
                
        board_results = {
            "1-0": "Congratulations, you win!",
            "0-1": "I win! Better luck next time.",
            "1/2-1/2": "The game ended in a draw. Well played!",
            "resign": "You resigned. I win!",
            "draw": "I'll accept a draw. Good game!",
        }
        
        result = board.result() if end_reason is None else end_reason
        if end_reason == "draw":
            show_last_move = False
        else:
            show_last_move = True
            
        viewer.update(board, show_last_move=show_last_move, text=board_results.get(result, "Game over!"))
        run_gen_audio(board_results.get(result, "Game over!"))
        
    except KeyboardInterrupt:
        print("\nGame interrupted by user.")
        
    finally:
        try: engine.quit()
        except Exception: pass
        try: plt.close('all')
        except Exception: pass
        
    
if __name__ == "__main__":
    main()