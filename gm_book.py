from __future__ import annotations

import bz2
import gzip
import lzma
import os
import pickle
import random
from pathlib import Path
from typing import Any

import chess

try:
    import chess.polyglot
except Exception:
    chess.polyglot = None


class GMBook:
    """
    Native Polyglot opening-book reader for Ultimate_GM_Bullet.bin.

    The original 231 MB book is a standard Polyglot binary book:
      16-byte record = uint64 zobrist key + uint16 move +
                       uint16 weight + uint32 learn

    This keeps book selection independent from the existing chess/vision
    logic.  The caller can continue using the same weighted-choice result
    and the same physical click/verification path.
    """

    def __init__(self, path: str | os.PathLike[str]):
        self.requested_path = Path(path)
        self.path = self.requested_path
        self.reader = None
        self.loaded = False
        self.format = "unloaded"
        self.entries = 0

    def _candidate_paths(self) -> list[Path]:
        paths = [self.requested_path]

        # Compatibility with the original working project location.
        legacy = (
            Path.home()
            / "PycharmProjects"
            / "bot pro c"
            / "Ultimate_GM_Bullet.bin"
        )
        if legacy not in paths:
            paths.append(legacy)

        return paths

    def load(self) -> bool:
        self.reader = None
        self.loaded = False
        self.format = "unloaded"
        self.entries = 0

        found_path = None
        for candidate in self._candidate_paths():
            if candidate.exists() and candidate.is_file():
                found_path = candidate
                break

        if found_path is None:
            self.format = "missing"
            return False

        try:
            if chess.polyglot is None:
                self.format = "polyglot-module-unavailable"
                return False

            self.path = found_path
            self.reader = chess.polyglot.open_reader(str(found_path))
            self.loaded = True
            self.format = "polyglot"

            # File size is an exact sanity check for the native 16-byte
            # Polyglot record format. Do not scan the whole 231 MB file here.
            try:
                size = self.path.stat().st_size
                if size % 16 == 0:
                    self.entries = size // 16
            except Exception:
                pass

            return True
        except Exception:
            self.reader = None
            self.loaded = False
            self.format = "unsupported"
            return False

    def close(self) -> None:
        if self.reader is not None:
            try:
                self.reader.close()
            except Exception:
                pass
        self.reader = None
        self.loaded = False

    @staticmethod
    def _book_move_to_chess_move(board: chess.Board, entry: Any) -> chess.Move | None:
        move = getattr(entry, "move", None)
        if isinstance(move, chess.Move) and move in board.legal_moves:
            return move

        raw_move = getattr(entry, "raw_move", None)
        if raw_move is None:
            return None

        # Polyglot raw_move uses:
        #   bits 0..5   = destination square
        #   bits 6..11  = source square
        #   bits 12..14 = promotion (1=N, 2=B, 3=R, 4=Q)
        to_square = raw_move & 0x3F
        from_square = (raw_move >> 6) & 0x3F
        promotion_code = (raw_move >> 12) & 0x7

        promotion_map = {
            1: chess.KNIGHT,
            2: chess.BISHOP,
            3: chess.ROOK,
            4: chess.QUEEN,
        }
        promotion = promotion_map.get(promotion_code)

        move = chess.Move(
            from_square=from_square,
            to_square=to_square,
            promotion=promotion,
        )

        return move if move in board.legal_moves else None

    @staticmethod
    def _position_key(board: chess.Board) -> int | None:
        try:
            return chess.polyglot.zobrist_hash(board)
        except Exception:
            return None

    def choose(self, board: chess.Board) -> dict[str, Any] | None:
        if not self.loaded or self.reader is None:
            return None

        key = self._position_key(board)
        if key is None:
            return None

        candidates: list[dict[str, Any]] = []

        try:
            # find_all() is the important part here: Polyglot books commonly
            # contain several records with the same position key.
            for entry in self.reader.find_all(board):
                move = self._book_move_to_chess_move(board, entry)
                if move is None:
                    continue

                candidates.append(
                    {
                        "move": move,
                        "weight": max(0.0, float(getattr(entry, "weight", 0))),
                        "learn": getattr(entry, "learn", 0),
                    }
                )
        except Exception:
            return None

        if not candidates:
            return None

        # Merge duplicate legal moves if the binary contains repeated records.
        merged: dict[str, dict[str, Any]] = {}
        for item in candidates:
            uci = item["move"].uci()
            if uci not in merged:
                merged[uci] = item.copy()
            else:
                merged[uci]["weight"] += item["weight"]

        candidates = list(merged.values())

        # Historical book behavior was frequency/weight based, not
        # "always play Polyglot record #1".
        candidates.sort(
            key=lambda item: (-item["weight"], item["move"].uci())
        )

        weights = [item["weight"] for item in candidates]

        if sum(weights) > 0.0:
            selected = random.choices(
                candidates,
                weights=weights,
                k=1,
            )[0]
        else:
            selected = random.choice(candidates)

        selected_rank = (
            next(
                i for i, item in enumerate(candidates)
                if item["move"] == selected["move"]
            )
            + 1
        )

        return {
            "move": selected["move"],
            "uci": selected["move"].uci(),
            "san": board.san(selected["move"]),
            "weight": selected["weight"],
            "rank": selected_rank,
            "entries": len(candidates),
            "candidates": candidates,
        }
