import chess
import chess.pgn
import time
import random

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
plt.ion()

from transcribe import listen, transcribe_audio
from src.visualize import BoardViewer
from src.gen_audio import play_gen_audio
from commentary import chat
from describe_move import describe_san

# Game settings
HUMAN_WHITE_NAME = "White"
HUMAN_BLACK_NAME = "Black"

def main():
    board = chess.Board()
    print("Starting a new chess game (Player vs. Player)")
    
    game = chess.pgn.Game()
    node = game
    
    # Fixed POV from the human player's side
    viewer = BoardViewer(perspective="white")
    viewer.update(board, show_last_move=False, text="Game start")
    
    # Make announement at the beginning of the game.
    play_gen_audio("""Welcome to Voice Chess! This is Magnus Carlsen speaking. You guys can start playing your game by saying your moves out loud.""")
    
    # Track whose turn it is
    turns = {True: "White", False: "Black"}
    is_white_turn = True
    
    end_reason = None
    pending_draw_offer = False
    try:
        while not board.is_game_over():
            player = turns[is_white_turn]
                    
            # Player move
            print(f"{turns[is_white_turn]}'s turn...")
            
            move_audio = listen() # listens for the move audio
            move_text = transcribe_audio(move_audio).split()[0] # transcribes move audio into SAN
            print("Transcription: ", move_text)
            
            if move_text == "resign":
                end_reason = f"{turns[is_white_turn]} resigns"
                break
            elif move_text == "draw":
                pending_draw_offer = True
                board.push(chess.Move.null()) 
                viewer.update(board, show_last_move=False, text=f"{player} offers a draw.")
                is_white_turn = not is_white_turn
                continue
            elif move_text == "accept" and pending_draw_offer:
                end_reason = "draw"
                viewer.update(board, show_last_move=False, text=f"Draw offer accepted")
                break
            elif move_text == "decline" and pending_draw_offer:
                pending_draw_offer = False
                board.pop()
                is_white_turn = not is_white_turn
                viewer.update(board, show_last_move=False, text=f"Draw offer declined")
                continue
            
            try: # Tries to execute the move
                move = board.parse_san(move_text)
                board.push_san(move_text)
                node = node.add_main_variation(move)

                print("Move executed")
                
            except ValueError:
                play_gen_audio(f"Did you try to play {describe_san(move_text)}? That isn't a legal move. Please try again.")
                print("Invalid move:", move_text, "— please try again.")
                viewer.update(board, show_last_move=True, text=f"Player move: {move_text} - Invalid!")
                continue
            
            viewer.update(board, show_last_move=True, text=f"{player} move: {move_text}") # visualize board
            
            # Porvide commentary on the game (50% chance)
            if random.random() < 0.5:
                    comment = chat(str(game), max_tokens=2048)
                    print("Commentary: ", comment)
                    play_gen_audio(comment)
                    
            viewer.flip()
            time.sleep(0.5)
            viewer.update(board, show_last_move=True, text=f"{player} move: {move_text}") # visualize board
            
            is_white_turn = not is_white_turn
            
        board_results = {
            "1-0": "White wins! That was a great game.",
            "0-1": "Black wins! Well played guys.",
            "1/2-1/2": "The game ended in a draw. Well played!",
            "White resigns": "White resigned! That was pathetic.",
            "Black resigns": "Black resigned! You should have kept on fighting.",
            "draw": "I'm surprised you accepted the draw. There was so much life left in the game!",
        }
        
        title_results = {
            "1-0": "White wins!",
            "0-1": "Black wins!",
            "1/2-1/2": "Draw!",
            "White resigns": "White resigned!.",
            "Black resigns": "Black resigned!",
            "draw": f"{player} accepted the draw.",
        }
        
        result = board.result() if end_reason is None else end_reason
        if end_reason == "draw":
            show_last_move = False
        else:
            show_last_move = True
        viewer.update(board, show_last_move=show_last_move, text=title_results.get(result, "Game over!"))
        play_gen_audio(board_results.get(result, "Game over!"))
        
    except KeyboardInterrupt:
        print("\nGame interrupted.")
        
    finally:
        try: plt.close('all')
        except Exception: pass
        

if __name__ == "__main__":
    main()