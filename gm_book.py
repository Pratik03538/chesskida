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
    Runtime reader for the Grandmaster/Bullet binary move book.

    The book is intentionally isolated from the live bot logic:
      board position -> book candidates -> weighted historical move
      -> fallback to the existing Stockfish selector when not found.

    The loader accepts the common serialized layouts used by the earlier
    project: mapping-like books, nested "book"/"positions"/"entries" payloads,
    move->weight dictionaries, and list/tuple entry records.
    """

    _MOVE_KEYS = ("move", "uci", "san", "m")
    _WEIGHT_KEYS = (
        "weight",
        "weights",
        "count",
        "counts",
        "frequency",
        "frequencies",
        "games",
        "game_count",
        "score",
        "value",
    )

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        self.data: Any = None
        self.loaded = False
        self.format = "unloaded"

    def load(self) -> bool:
        if not self.path.exists():
            self.loaded = False
            self.format = "missing"
            return False

        raw = self.path.read_bytes()

        objects = [raw]

        for opener, name in (
            (gzip.decompress, "gzip"),
            (bz2.decompress, "bz2"),
            (lzma.decompress, "lzma"),
        ):
            try:
                objects.append((opener(raw), name))
            except Exception:
                pass

        for payload in objects:
            if isinstance(payload, tuple):
                blob, compression = payload
            else:
                blob, compression = payload, "raw"

            try:
                value = pickle.loads(blob)
            except Exception:
                continue

            if value is None:
                continue

            self.data = value
            self.loaded = True
            self.format = f"pickle/{compression}"
            return True

        self.loaded = False
        self.format = "unsupported"
        return False

    @staticmethod
    def _position_keys(board: chess.Board) -> list[Any]:
        keys: list[Any] = []

        # FEN variants.
        for value in (
            board.fen(),
            board.board_fen(),
        ):
            if value not in keys:
                keys.append(value)

        # Polyglot/Zobrist position key, when python-chess exposes it.
        try:
            if chess.polyglot is not None:
                value = chess.polyglot.zobrist_hash(board)
                keys.extend((value, str(value), hex(value)))
        except Exception:
            pass

        # Older project variants sometimes used python-chess' internal
        # transposition key directly.
        try:
            value = board._transposition_key()
            keys.extend((value, str(value)))
        except Exception:
            pass

        return keys

    @staticmethod
    def _unwrap(value: Any) -> Any:
        if isinstance(value, dict):
            for key in (
                "moves",
                "entries",
                "book",
                "positions",
                "data",
                "table",
            ):
                if key in value and isinstance(value[key], (dict, list, tuple)):
                    # Do not unwrap a plain move->weight dictionary.
                    keys = set(str(k).lower() for k in value.keys())
                    if not keys.intersection({"e2e4", "move", "uci", "san"}):
                        return value[key]
        return value

    def _lookup_raw(self, board: chess.Board) -> Any:
        if not isinstance(self.data, dict):
            return None

        for key in self._position_keys(board):
            if key in self.data:
                return self._unwrap(self.data[key])

            text_key = str(key)
            if text_key in self.data:
                return self._unwrap(self.data[text_key])

        # A small set of nested wrapper layouts.
        for wrapper in ("book", "positions", "entries", "data", "table"):
            nested = self.data.get(wrapper)
            if not isinstance(nested, dict):
                continue

            for key in self._position_keys(board):
                if key in nested:
                    return self._unwrap(nested[key])

                text_key = str(key)
                if text_key in nested:
                    return self._unwrap(nested[text_key])

        return None

    @classmethod
    def _extract_weight(cls, value: Any) -> float:
        if isinstance(value, (int, float)):
            return max(0.0, float(value))

        if isinstance(value, dict):
            for key in cls._WEIGHT_KEYS:
                if key in value and isinstance(value[key], (int, float)):
                    return max(0.0, float(value[key]))

        return 1.0

    @classmethod
    def _extract_move(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value

        if isinstance(value, dict):
            for key in cls._MOVE_KEYS:
                if key in value:
                    return value[key]

        if isinstance(value, (tuple, list)) and value:
            return value[0]

        return None

    @classmethod
    def _candidate_items(cls, raw: Any) -> list[tuple[Any, float]]:
        if raw is None:
            return []

        items: list[tuple[Any, float]] = []

        if isinstance(raw, dict):
            # Nested record lists.
            for move, value in raw.items():
                extracted = cls._extract_move(value)
                if extracted is None:
                    extracted = move
                weight = cls._extract_weight(value)
                items.append((extracted, weight))
            return items

        if isinstance(raw, (list, tuple)):
            for item in raw:
                if isinstance(item, dict) and not any(
                    key in item for key in cls._MOVE_KEYS
                ):
                    # A dict may itself be {move: weight}.
                    for move, value in item.items():
                        extracted = cls._extract_move(value) or move
                        items.append((extracted, cls._extract_weight(value)))
                    continue

                move = cls._extract_move(item)
                if move is None:
                    continue

                weight = cls._extract_weight(item)
                if (
                    isinstance(item, (tuple, list))
                    and len(item) >= 2
                    and isinstance(item[1], (int, float))
                ):
                    weight = max(0.0, float(item[1]))

                items.append((move, weight))

        return items

    @staticmethod
    def _resolve_move(board: chess.Board, value: Any) -> chess.Move | None:
        if isinstance(value, chess.Move):
            move = value
            return move if move in board.legal_moves else None

        if value is None:
            return None

        text = str(value).strip()

        # UCI first.
        try:
            move = chess.Move.from_uci(text)
            if move in board.legal_moves:
                return move
        except Exception:
            pass

        # SAN fallback.
        try:
            return board.parse_san(text)
        except Exception:
            return None

    def choose(self, board: chess.Board) -> dict[str, Any] | None:
        if not self.loaded:
            return None

        raw = self._lookup_raw(board)
        if raw is None:
            return None

        raw_items = self._candidate_items(raw)
        if not raw_items:
            return None

        candidates: list[dict[str, Any]] = []

        for value, weight in raw_items:
            move = self._resolve_move(board, value)
            if move is None:
                continue

            candidates.append(
                {
                    "move": move,
                    "weight": max(0.0, float(weight)),
                    "source": value,
                }
            )

        if not candidates:
            return None

        # Merge duplicate moves while preserving the book's total weight.
        merged: dict[str, dict[str, Any]] = {}
        for item in candidates:
            uci = item["move"].uci()
            if uci not in merged:
                merged[uci] = item.copy()
            else:
                merged[uci]["weight"] += item["weight"]

        candidates = list(merged.values())

        # Historical frequency/weight rank is only diagnostic; selection is
        # genuinely weighted, matching the earlier "weighted choice" behavior.
        candidates.sort(
            key=lambda item: (-item["weight"], item["move"].uci())
        )

        weights = [item["weight"] for item in candidates]

        if sum(weights) <= 0.0:
            selected = random.choice(candidates)
        else:
            selected = random.choices(
                candidates,
                weights=weights,
                k=1,
            )[0]

        selected_rank = (
            next(
                index
                for index, item in enumerate(candidates)
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
