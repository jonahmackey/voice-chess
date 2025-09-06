import chess
from local_chess_client import listen, transcribe_audio
from visualize import show_board

def main():
    board = chess.Board()
    
    print("♟️ Starting a new chess game")
    
    # Track whose turn it is
    turns = {True: "White", False: "Black"} 
    is_white_turn = True
    
    while not board.is_game_over():
        player = turns[is_white_turn]
        print(f"\n{player}'s turn. Waiting for next move...")
        
        # Listen for one move (blocks until speech ends)
        move_audio = listen()
        
        # Send to server and get transcription
        move_text = transcribe_audio(move_audio)
        print("Transcribed move:", move_text)
        
        try:
            # Try to execute the move in SAN notation
            board.push_san(move_text)
            print("Move executed")
            is_white_turn = not is_white_turn  # Switch turn only if move was valid
        except ValueError:
            # Invalid move
            print("Invalid move:", move_text)
        
        # Print updated board
        print(board)
        # show_board(board, perspective='white' if is_white_turn else 'black')
    
    print("\nGame over!")
    print("Result:", board.result())
    
if __name__ == "__main__":
    main()