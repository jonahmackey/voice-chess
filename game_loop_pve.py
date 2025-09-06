import os
import time
import threading
import queue

import chess
import chess.engine
# If needed on macOS, force a GUI backend BEFORE importing pyplot:
# import matplotlib; matplotlib.use("TkAgg")
import matplotlib.pyplot as plt

from src.transcribe_move import listen, transcribe_audio
from src.visualize import BoardViewer

# --- Configure Stockfish path & strength ---
STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "./stockfish/stockfish-ex")
ENGINE_TIME_SEC = 0.5         # per-move think time (increase for stronger play)
ENGINE_SKILL = 15             # 0-20 (may be ignored by some builds)
HUMAN_PLAYS_WHITE = True      # set False to play Black


# ---------- Background ASR worker ----------
class ASRWorker(threading.Thread):
    def __init__(self, out_queue: queue.Queue, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.out_queue = out_queue
        self.stop_event = stop_event

    def run(self):
        while not self.stop_event.is_set():
            try:
                audio = listen()                   # blocking mic capture
                text = transcribe_audio(audio)     # blocking ASR call
                if text and text.strip():
                    self.out_queue.put(text.strip())
            except Exception as e:
                self.out_queue.put(f"__ERROR__:{e}")
                time.sleep(0.1)


def main():
    board = chess.Board()
    print("♟️ Starting a new chess game (Player vs. Engine)")

    # Fixed POV from the human player's side
    start_pov = "white" if HUMAN_PLAYS_WHITE else "black"
    viewer = BoardViewer(perspective=start_pov)
    viewer.update(board, show_last_move=False)

    # Engine
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    try:
        engine.configure({"Skill Level": ENGINE_SKILL})
    except Exception:
        pass

    # ASR thread + queue
    move_q: queue.Queue[str] = queue.Queue()
    stop_ev = threading.Event()
    asr = ASRWorker(move_q, stop_ev)
    asr.start()

    try:
        while not board.is_game_over():
            side_to_move_is_human = (board.turn == chess.WHITE) == HUMAN_PLAYS_WHITE

            if side_to_move_is_human:
                # --- Human (voice) move ---
                print(f"\nYour turn ({'White' if HUMAN_PLAYS_WHITE else 'Black'}). Say your move in SAN (e.g., e4, Nf3, O-O).")
                move_text = None

                # Poll ASR while keeping GUI responsive
                while move_text is None and not board.is_game_over():
                    try:
                        item = move_q.get(timeout=0.1)
                        if item.startswith("__ERROR__:"):
                            print("ASR error:", item.split(":", 1)[1])
                            continue
                        move_text = item
                    except queue.Empty:
                        viewer.update(board, show_last_move=True)
                        plt.pause(0.01)

                if board.is_game_over():
                    break

                print("Transcribed move:", move_text)

                # Optional simple commands (no flipping anymore)
                if move_text.lower() in {"resign", "i resign"}:
                    print("You resigned.")
                    break

                try:
                    board.push_san(move_text)
                    print("Move executed")
                    viewer.update(board, show_last_move=True)  # fixed POV
                    plt.pause(0.01)
                except ValueError:
                    print("Invalid move:", move_text, "— please try again.")
                    continue

            else:
                # --- Engine move ---
                print("\nEngine is thinking...")
                result = engine.play(board, chess.engine.Limit(time=ENGINE_TIME_SEC))
                if result.move is None:
                    print("Engine failed to find a move.")
                    break
                san = board.san(result.move)
                board.push(result.move)
                print(f"Stockfish plays: {san}")

                viewer.update(board, show_last_move=True)      # fixed POV
                plt.pause(0.01)

        print("\nGame over!")
        print("Result:", board.result())

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        stop_ev.set()
        try:
            asr.join(timeout=1.0)
        except Exception:
            pass
        try:
            engine.quit()
        except Exception:
            pass
        plt.ioff()
        plt.show()


if __name__ == "__main__":
    main()