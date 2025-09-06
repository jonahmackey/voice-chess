import chess
import matplotlib.pyplot as plt
import matplotlib.patches as patches

class BoardViewer:
    def __init__(self, perspective="white"):
        assert perspective in ("white", "black")
        self.perspective = perspective
        self.fig = None
        self.ax = None
        self._init_fig()

    def _init_fig(self):
        # plt.ion() should be called in the main script before importing pyplot
        self.fig, self.ax = plt.subplots(figsize=(8, 8))
        try:
            # Some backends don’t have a manager or set_window_title
            self.fig.canvas.manager.set_window_title("VoiceChess")
        except Exception:
            pass
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.ax.set_aspect("equal")
        # Show once, non-blocking (since interactive mode is on in the entry script)
        try:
            self.fig.show()
        except Exception:
            plt.show(block=False)

    def is_open(self):
        try:
            return plt.fignum_exists(self.fig.number)
        except Exception:
            return False

    # ---------- Mapping helpers ----------
    def _model_to_view(self, file_idx: int, rank_idx: int):
        if self.perspective == "white":
            return file_idx, rank_idx
        else:  # black
            return 7 - file_idx, 7 - rank_idx

    def _view_to_model(self, vx: int, vy: int):
        if self.perspective == "white":
            return vx, vy
        else:
            return 7 - vx, 7 - vy

    def update(self, board: chess.Board, show_last_move: bool = True):
        if not self.is_open():
            self._init_fig()

        ax = self.ax
        ax.clear()
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_aspect("equal")

        light = "#f0d9b5"
        dark = "#b58863"
        highlight = "#f6f669"

        # Last move (model coords)
        last_from = last_to = None
        if show_last_move and board.move_stack:
            m = board.move_stack[-1]
            last_from, last_to = m.from_square, m.to_square

        # Draw squares
        for vy in range(8):
            for vx in range(8):
                mf, mr = self._view_to_model(vx, vy)
                model_sq = chess.square(mf, mr)
                color = highlight if model_sq in (last_from, last_to) \
                        else (light if (vx + vy) % 2 == 0 else dark)
                ax.add_patch(patches.Rectangle((vx, vy), 1, 1, facecolor=color))

        # Draw pieces
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if not piece:
                continue
            mf = chess.square_file(sq)
            mr = chess.square_rank(sq)
            vx, vy = self._model_to_view(mf, mr)
            ax.text(vx + 0.5, vy + 0.5, piece.unicode_symbol(),
                    fontsize=36, ha='center', va='center')

        # Rank labels (left edge of the displayed board)
        for vy in range(8):
            label = str(vy + 1) if self.perspective == "white" else str(8 - vy)
            ax.text(-0.3, vy + 0.5, label, fontsize=14, ha='right', va='center')

        # File labels (bottom edge)
        for vx in range(8):
            label = chr(ord('a') + vx) if self.perspective == "white" else chr(ord('h') - vx)
            ax.text(vx + 0.5, -0.3, label, fontsize=14, ha='center', va='top')

        ax.set_xlim(-0.5, 8)
        ax.set_ylim(-0.5, 8)

        # The crucial trio:
        self.fig.canvas.draw_idle()
        try:
            self.fig.canvas.flush_events()
        except Exception:
            pass
        plt.pause(0.001)  # yields to the GUI loop

    def flip(self):
        self.perspective = "black" if self.perspective == "white" else "white"
