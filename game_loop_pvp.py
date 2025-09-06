import threading
import queue
import time
import chess
import matplotlib
import matplotlib.pyplot as plt

from src.transcribe_move import listen, transcribe_audio
from src.visualize import BoardViewer  # your fixed viewer from above

# ---------- Background ASR worker ----------
class ASRWorker(threading.Thread):
    def __init__(self, out_queue: queue.Queue, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.out_queue = out_queue
        self.stop_event = stop_event

    def run(self):
        while not self.stop_event.is_set():
            try:
                # Blocking audio capture/transcription
                audio = listen()
                text = transcribe_audio(audio)
                # Push only non-empty strings
                if text and text.strip():
                    self.out_queue.put(text.strip())
            except Exception as e:
                # Don’t kill the thread on transient errors; log and continue
                self.out_queue.put(f"__ERROR__:{e}")
                time.sleep(0.1)

def main():
    board = chess.Board()
    viewer = BoardViewer(perspective="white")
    viewer.update(board, show_last_move=False)

    print("♟️ Starting a new chess game (Player vs. Player)")
    turns = {True: "White", False: "Black"}
    is_white_turn = True

    # Queue for ASR → main thread, and a stop flag
    move_q: queue.Queue[str] = queue.Queue()
    stop_ev = threading.Event()
    asr = ASRWorker(move_q, stop_ev)
    asr.start()

    try:
        while not board.is_game_over():
            player = turns[is_white_turn]
            print(f"\n{player}'s turn. Say your move (SAN). Type Ctrl+C to quit.")

            # Non-blocking wait for a move: poll queue while keeping GUI responsive
            move_text = None
            while move_text is None and not board.is_game_over():
                try:
                    # Short timeout so we can refresh GUI and keep the window alive
                    item = move_q.get(timeout=0.1)
                    if item.startswith("__ERROR__:"):
                        print("ASR error:", item.split(":", 1)[1])
                        continue
                    move_text = item
                except queue.Empty:
                    # Service the GUI regularly
                    viewer.update(board, show_last_move=True)
                    plt.pause(0.01)  # let the GUI event loop breathe

            if board.is_game_over():
                break

            print("Transcribed move:", move_text)

            # Optional: allow simple voice commands like "flip"
            if move_text.lower() in {"flip", "flip board", "flipboard"}:
                viewer.flip()
                viewer.update(board, show_last_move=True)
                plt.pause(0.01)
                continue

            # Try to execute the SAN move
            try:
                board.push_san(move_text)
                print("Move executed.")
                is_white_turn = not is_white_turn
                
                viewer.update(board, show_last_move=True)
                viewer.flip()
                viewer.update(board, show_last_move=True)
                plt.pause(0.01)
            except ValueError:
                print("Invalid move:", move_text)
                # Continue loop; we’ll wait for another move
                continue

        print("\nGame over!")
        print("Result:", board.result())

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        # Stop ASR thread cleanly
        stop_ev.set()
        asr.join(timeout=1.0)
        plt.ioff()
        plt.show()

if __name__ == "__main__":
    main()