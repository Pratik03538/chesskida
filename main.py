# FAST-MAIN BASELINE: copied from main; only performance timings/search/capture sizing tuned.
import cv2
import numpy as np
import mss
import ctypes
import os
import time
import random
import math
import chess
import chess.engine

if os.name == "nt":
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    try:
        ctypes.windll.shcore.SetProcessDpiAware()
    except Exception:
        pass
else:
    wintypes = None
    user32 = None

PIECES_DIR = "pieces_png"
SCRCPY_WINDOW_TITLE = "CHESS_MOBILE"
FALLBACK_TITLE_KEYWORD = "scrcpy"
STOCKFISH_PATH = r"stockfish.exe"
INITIAL_FEN = chess.STARTING_FEN
STOCKFISH_DEPTH = 12
STOCKFISH_TIME = 0.040
ANALYSIS_TIME = 0.010
ANALYSIS_DEPTH = 8
MATCH_THRESHOLD = 0.30
EMPTY_STD_THRESHOLD = 4.5

# Fast bot interaction timing.
BOT_START_DELAY = 0.0
CLICK_DELAY = 0.001
CLICK_SETTLE_DELAY = 0.0
CLICK_CURSOR_SETTLE_MIN = 0.0
CLICK_CURSOR_SETTLE_MAX = 0.0
CLICK_HOLD_MIN = 0.0
CLICK_HOLD_MAX = 0.0

# Before the destination click, verify that the SOURCE square itself was
# actually selected. This prevents a bad source click (for example selecting
# a queen when Stockfish asked for a bishop) from turning into a legal but
# wrong move such as Qxg5 instead of Bxg5.
BOT_SOURCE_SELECT_TIMEOUT = 0.060
BOT_SOURCE_SELECT_POLL = 0.001
BOT_SOURCE_SELECT_CHANGE_MIN = 0.0012
BOT_SOURCE_SELECT_MAX_EXTRA_CHANGES = 0
BOT_SOURCE_SELECT_DOMINANCE_RATIO = 0.80
BOT_SOURCE_SELECT_STABLE_SAMPLES = 1

PROMOTION_WAIT = 0.050
PROMOTION_RETRIES = 5
SCAN_INTERVAL = 0.006
ORIENTATION_TIMEOUT = 1.2
HUMAN_MOVE_TIMEOUT = 0.35
HUMAN_CONFIRM_SAMPLES = 1
HUMAN_SETTLE_TIMEOUT = 0.004
HUMAN_FALLBACK_CHANGE_THRESHOLD = 0.0012
HUMAN_FALLBACK_TOP_SQUARES = 4
HUMAN_FALLBACK_SCAN_INTERVAL = 0.010

# After the normal human detector has had about two seconds of waiting,
# run a full-board ultra recovery scan. This repeats every two seconds
# until a real board change is detected and verified.
HUMAN_ULTRA_RESCAN_INTERVAL = 2.0
HUMAN_ULTRA_CHANGE_THRESHOLD = 0.0008
HUMAN_ULTRA_TOP_SQUARES = 16
HUMAN_ULTRA_TOP_MOVES = 8
HUMAN_ULTRA_MOTION_MIN = 0.0010
HUMAN_ULTRA_MOVE_MARGIN = 0.50
HUMAN_ULTRA_SCAN_COOLDOWN = 0.010

# Extra recovery layer: reconstruct a missed human move by comparing the
# current full-board observation against the last internally committed board.
# This layer runs only from the ultra recovery path, so normal move detection
# remains unchanged.
HUMAN_ULTRA_DELTA_CONF_MAX = 0.55
HUMAN_ULTRA_DELTA_MAX_EXTRA = 3
HUMAN_ULTRA_DELTA_MAX_MISSING = 1
HUMAN_ULTRA_DELTA_MIN_EXACT = 2
HUMAN_ULTRA_DELTA_MARGIN = 2.0
HUMAN_ULTRA_DELTA_CONFIRM_DELAY = 0.025
HUMAN_ULTRA_DELTA_MOTION_FLOOR = 0.00030

# Extra 2-second whole-board catch-up layer. It is used only as a recovery
# path; the normal fast/motion/template detectors remain unchanged.
TURN_RESCAN_INTERVAL = 2.0
TURN_RESCAN_CONFIRM_DELAY = 0.025
TURN_RESCAN_MAX_MISMATCH = 0
TURN_RESCAN_TOP_CANDIDATES = 6

BOT_VERIFY_TIMEOUT = 0.120
BOT_CONFIRM_SAMPLES = 1
BOT_CLICK_RETRIES = 1
BOT_RECOVERY_POLL = 0.0005

# A bot move is considered physically completed only when the expected
# source/target transition is visible with a meaningful pixel change.
BOT_SOURCE_CHANGE_MIN = 0.0060
BOT_TARGET_CHANGE_MIN = 0.0060
BOT_TRANSITION_TOTAL_MIN = 0.0200
BOT_CONFIRM_GAP = 0.0

# Bot post-move piece matching can be slightly less strict than the
# general board scan because the Android/scrcpy frame may contain a
# transient anti-aliased edge after a tap.
BOT_POST_MATCH_THRESHOLD = 0.40
# Full-board verification first trusts the expected python-chess piece
# on occupied squares, then falls back to the normal scan result.
# This prevents a single rook/bishop template confusion (for example
# a8:r -> b) from blocking an otherwise correct physical position.
FULL_BOARD_EXPECTED_MATCH_THRESHOLD = 0.40
# Empty destination safety check only. This prevents a loose template match
# (such as the false K=0.125 seen on an empty e4) from blocking a legal move.
EMPTY_DEST_MATCH_THRESHOLD = 0.10

# Keep pickup/drop points tightly around the square center. The previous
# 40%-area circle allowed too much lateral movement on small/mobile pieces,
# which caused occasional misses and unnecessary retries.
# Both source and destination use the same center-biased safe zone.
CLICK_CIRCLE_AREA = 0.08
CLICK_CIRCLE_RADIUS_FRACTION = math.sqrt(CLICK_CIRCLE_AREA / math.pi)

# After a random 5-8 Stockfish moves, add one random human-like pause.
RANDOM_BUFFER_MOVE_MIN = 5
RANDOM_BUFFER_MOVE_MAX = 8
RANDOM_BUFFER_OPTIONS = (0.0,)
PROMOTION_FALLBACK = True

# FAST PHYSICAL VALIDATION:
# The previous verifier performed a complete 64-square template classification
# after every click (often ~200-390ms). We now use one cheap 128x128 board
# difference map for ALL 64 squares and exact template classification only on
# the squares that are supposed to change. This keeps the same safety invariant:
# the pre-verified board must change only where the move allows, and the
# changed squares must contain the exact expected pieces.
FAST_VERIFY_SIZE = 96
FAST_UNCHANGED_MAX_DIFF = 0.055
FAST_UNEXPECTED_STRONG_DIFF = 0.085
FAST_REQUIRED_CHANGED_DIFF = 0.0010
FAST_MAX_UNEXPECTED_CHANGED_SQUARES = 0
FAST_DEEP_VERIFY_EVERY = 8

# Ultra-fast human move rescan. This uses the same 128x128 vectorized
# board-motion map as bot verification and checks only the most plausible
# legal moves instead of running a complete 64-square template scan first.
HUMAN_FAST_RESCAN_THRESHOLD = 0.00045
HUMAN_FAST_RESCAN_TOP_SQUARES = 12
HUMAN_FAST_RESCAN_TOP_MOVES = 6
HUMAN_FAST_RESCAN_POLL = 0.0007
HUMAN_FAST_RESCAN_CONFIRM_TIMEOUT = 0.050


# Template position guards.
TEMPLATE_CENTER_TOLERANCE = 0.22
PAWN_CENTER_TOLERANCE = 0.15
ROOK_CENTER_TOLERANCE = 0.18
CHANGE_THRESHOLD = 0.0025
SOURCE_CHANGE_THRESHOLD = 0.0025
TARGET_CHANGE_THRESHOLD = 0.0025
SQUARE_DIFF_SIZE = 16

VERBOSE_LOGS = False
SHOW_TERMINAL_FEN = False
SHOW_TERMINAL_BOARD = False

# ============================================================
# STOCKFISH #1-#8 TRAINING PREFERENCE
# ============================================================
TRAINING_MULTI_PV = 8
FORCE_BEST_MIN_CP = 200
FORCE_BEST_IMPROVEMENT_FRACTION = 0.65

# Human-like advantage shaping. Once the bot is clearly winning,
# keep the winning level for a short run, then grow the advantage only
# when Stockfish actually finds a stronger position. Growth is progressive,
# while the current advantage is protected from large unnecessary drops.
HUMAN_ADVANTAGE_START_CP = 400
HUMAN_ADVANTAGE_MAINTAIN_BAND_CP = 30
HUMAN_ADVANTAGE_PROTECT_BAND_CP = 30
HUMAN_ADVANTAGE_HOLD_MIN_MOVES = 1
HUMAN_ADVANTAGE_HOLD_MAX_MOVES = 3
HUMAN_ADVANTAGE_GROWTH_STEP_MIN_CP = 20
HUMAN_ADVANTAGE_GROWTH_STEP_MAX_CP = 45
HUMAN_ADVANTAGE_GROWTH_TRIGGER_CP = 15

# Once a forced mate is already very close, do not humanize it away.
MATE_FORCE_FAST_MAX = 4

# Human-like mate handling is active in the existing M5-M15 window.
# There is no fixed +5 cap anymore. Instead, when the engine finds a faster
# mate (for example M10 -> M9 -> M8), the bot sustains the current mate level
# for a few actual moves and then improves by only one mate step at a time.
# This keeps the winning plan stable instead of chasing every immediate mate
# improvement.
MATE_GRACE_MIN = 5
MATE_GRACE_MAX = 15
MATE_SUSTAIN_MIN_MOVES = 2
MATE_SUSTAIN_MAX_MOVES = 3
MATE_SLOWER_LINE_CHANCE = 0.35

_mate_progress_target_mate = None
_mate_progress_hold_moves = 0
_mate_progress_hold_limit = 2

_advantage_progress_target_cp = None
_advantage_progress_hold_moves = 0
_advantage_progress_hold_limit = 2
_advantage_progress_side = None

MIN_POSITIVE_CP = 5

# ============================================================
# ADAPTIVE OPPONENT-STRENGTH / 80-95% TARGET CONTROLLER
# ============================================================
OPPONENT_ACCURACY_WINDOW = 12
OPPONENT_MIN_SAMPLES = 5
ADAPTIVE_MIN_TARGET = 80.0
ADAPTIVE_MAX_TARGET = 95.0
ADAPTIVE_SAFETY_MARGIN = 1.0
ADAPTIVE_STRONG_THRESHOLD = 90.0
ADAPTIVE_VERY_STRONG_THRESHOLD = 94.0

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
SW_RESTORE = 9

PIECE_MAP = {
    "white_king.png": "K",
    "white_queen.png": "Q",
    "white_rook.png": "R",
    "white_bishop.png": "B",
    "white_knight.png": "N",
    "white_pawn.png": "P",
    "black_king.png": "k",
    "black_queen.png": "q",
    "black_rook.png": "r",
    "black_bishop.png": "b",
    "black_knight.png": "n",
    "black_pawn.png": "p",
}

RAW_TEMPLATES = {}
cached_sq_size = (0, 0)
cached_templates = {}

# ============================================================
# PERFORMANCE CACHES
# ============================================================

# Board geometry is stable while the grid is locked.
_SQUARE_GEOMETRY_CACHE = {}

# For every frame/square, cache the 16x16 grayscale representation
# used by square_change_score(). This avoids repeated resize + grayscale
# conversion for the same frame and square.
_FRAME_SQUARE_CACHE = {}
_FRAME_SQUARE_CACHE_MAX = 4

# Repeated board_hypothesis_score() calls use the same grid and confidence
# arrays. Cache the converted square dictionary.
_GRID_CONF_CACHE = {}
_GRID_CONF_CACHE_MAX = 8


def clear_runtime_caches():
    """Clear transient image/geometry caches."""
    _SQUARE_GEOMETRY_CACHE.clear()
    _FRAME_SQUARE_CACHE.clear()
    _GRID_CONF_CACHE.clear()


PROGRESS_INTERVAL = 0.35
_progress_times = {}
_progress_last_text = {}


def progress(stage, detail="", key=None, interval=PROGRESS_INTERVAL, force=False):
    if not VERBOSE_LOGS and stage not in {"STATE", "PROMOTION"}:
        return

    if key is None:
        key = stage

    now = time.perf_counter()
    last = _progress_times.get(key, 0.0)
    text = f"[{stage}] {detail}" if detail else f"[{stage}]"

    if (
        force
        or text != _progress_last_text.get(key)
        or now - last >= interval
    ):
        _progress_times[key] = now
        _progress_last_text[key] = text
        print(
            f"[{time.strftime('%H:%M:%S')}] {text}",
            flush=True
        )


def load_assets():
    if not os.path.exists(PIECES_DIR):
        print(f"[ERROR] '{PIECES_DIR}' folder not found.")
        return False

    loaded_count = 0

    for fname, symbol in PIECE_MAP.items():
        path = os.path.join(PIECES_DIR, fname)

        if not os.path.exists(path):
            print(f"[WARN] Missing: {fname}")
            continue

        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)

        if img is None:
            print(f"[WARN] Could not read: {fname}")
            continue

        if len(img.shape) != 3 or img.shape[2] != 4:
            print(f"[WARN] {fname} must be BGRA PNG with transparency.")
            continue

        alpha = img[:, :, 3]
        coords = cv2.findNonZero(alpha)

        if coords is None:
            continue

        x, y, w, h = cv2.boundingRect(coords)
        RAW_TEMPLATES[symbol] = img[y:y + h, x:x + w]
        loaded_count += 1

    print(f"[INFO] Loaded {loaded_count}/12 piece templates.")
    return loaded_count == 12


def get_scaled_templates(sq_w, sq_h):
    global cached_sq_size, cached_templates

    key = (int(sq_w), int(sq_h))

    if key == cached_sq_size and cached_templates:
        return cached_templates

    scaled = {}
    scales = (0.60, 0.70, 0.80, 0.90)

    for symbol, img in RAW_TEMPLATES.items():
        h, w = img.shape[:2]

        if h <= 0 or w <= 0:
            continue

        scaled[symbol] = []
        aspect = w / float(h)

        for scale in scales:
            target_h = max(5, int(sq_h * scale))
            target_w = max(5, int(target_h * aspect))

            resized = cv2.resize(
                img,
                (target_w, target_h),
                interpolation=cv2.INTER_AREA
            )

            gray = cv2.cvtColor(
                resized[:, :, :3],
                cv2.COLOR_BGR2GRAY
            )

            _, mask = cv2.threshold(
                resized[:, :, 3],
                80,
                255,
                cv2.THRESH_BINARY
            )

            scaled[symbol].append({
                "gray": gray,
                "mask": mask,
                "size": (target_w, target_h)
            })

    cached_sq_size = key
    cached_templates = scaled
    return scaled


def find_scrcpy_window():
    if not user32:
        return None

    found = []

    def enum_proc(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True

        length = user32.GetWindowTextLengthW(hwnd)

        if length <= 0:
            return True

        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.lower()

        if (
            SCRCPY_WINDOW_TITLE.lower() in title
            or FALLBACK_TITLE_KEYWORD.lower() in title
        ):
            found.append(hwnd)

        return True

    callback = ctypes.WINFUNCTYPE(
        ctypes.c_int,
        wintypes.HWND,
        wintypes.LPARAM
    )(enum_proc)

    user32.EnumWindows(callback, 0)

    return found[0] if found else None


def get_scrcpy_screen_origin(hwnd):
    if not hwnd or not user32:
        return None

    rect = wintypes.RECT()

    if not user32.GetClientRect(
        hwnd,
        ctypes.byref(rect)
    ):
        return None

    point = wintypes.POINT(0, 0)

    if not user32.ClientToScreen(
        hwnd,
        ctypes.byref(point)
    ):
        return None

    return int(point.x), int(point.y)


def focus_scrcpy(hwnd):
    if not user32:
        return False

    candidates = []
    if hwnd and user32.IsWindow(hwnd):
        candidates.append(hwnd)
    else:
        fresh = find_scrcpy_window()
        if fresh:
            candidates.append(fresh)

    for candidate in candidates:
        if not candidate or not user32.IsWindow(candidate):
            continue

        try:
            # Do not pay the old 10ms+ sleep cost on every move.
            if user32.GetForegroundWindow() == candidate:
                return True
            user32.ShowWindow(candidate, SW_RESTORE)
            user32.BringWindowToTop(candidate)
            user32.SetForegroundWindow(candidate)
            return True
        except Exception:
            continue

    return False


def left_click_screen(x, y):
    # Direct Win32 dispatch. No artificial cursor/hold sleeps.
    user32.SetCursorPos(int(x), int(y))
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    return True


def capture_screen(sct, hwnd=None):
    if hwnd and user32 and user32.IsWindow(hwnd):
        rect = wintypes.RECT()

        user32.GetClientRect(
            hwnd,
            ctypes.byref(rect)
        )

        point = wintypes.POINT(
            rect.left,
            rect.top
        )

        user32.ClientToScreen(
            hwnd,
            ctypes.byref(point)
        )

        width = rect.right - rect.left
        height = rect.bottom - rect.top

        if width <= 0 or height <= 0:
            return None

        raw = np.asarray(
            sct.grab({
                "left": point.x,
                "top": point.y,
                "width": width,
                "height": height
            })
        )

    else:
        raw = np.asarray(
            sct.grab(
                sct.monitors[1]
            )
        )

    return raw[:, :, :3].copy()


def classify_square(
    img_crop,
    current_templates,
    expected_symbol=None,
    match_threshold=MATCH_THRESHOLD
):
    if img_crop is None or img_crop.size == 0:
        return None, 999.0

    ch, cw = img_crop.shape[:2]

    # SPEED OPTIMIZATION:
    # scan_board() can now pass an already grayscale crop so the same
    # cv2.cvtColor() is not executed 64 times per full scan.
    if img_crop.ndim == 2:
        gray = img_crop
    else:
        gray = cv2.cvtColor(
            img_crop,
            cv2.COLOR_BGR2GRAY
        )

    if expected_symbol is None:
        margin_y = int(ch * 0.20)
        margin_x = int(cw * 0.20)

        if (
            ch > margin_y * 2
            and cw > margin_x * 2
        ):
            core = gray[
                margin_y:ch - margin_y,
                margin_x:cw - margin_x
            ]

            if float(np.std(core)) < EMPTY_STD_THRESHOLD:
                return None, 999.0

    symbols = (
        (expected_symbol,)
        if expected_symbol
        else current_templates.keys()
    )

    best_symbol = None
    best_score = float("inf")

    for symbol in symbols:
        variants = current_templates.get(symbol)

        if not variants:
            continue

        if symbol.lower() == "p":
            center_tolerance = PAWN_CENTER_TOLERANCE
        elif symbol.lower() == "r":
            center_tolerance = ROOK_CENTER_TOLERANCE
        else:
            center_tolerance = TEMPLATE_CENTER_TOLERANCE

        for tmpl in variants:
            tmpl_gray = tmpl["gray"]
            tmpl_mask = tmpl["mask"]
            th, tw = tmpl["size"]

            if th >= ch or tw >= cw:
                continue

            try:
                result = cv2.matchTemplate(
                    gray,
                    tmpl_gray,
                    cv2.TM_SQDIFF_NORMED,
                    mask=tmpl_mask
                )

                min_val, _, min_loc, _ = cv2.minMaxLoc(
                    result
                )

                match_cx = (
                    float(min_loc[0])
                    + (tw * 0.5)
                )

                match_cy = (
                    float(min_loc[1])
                    + (th * 0.5)
                )

                dx = (
                    abs(match_cx - cw * 0.5)
                    / max(1.0, float(cw))
                )

                dy = (
                    abs(match_cy - ch * 0.5)
                    / max(1.0, float(ch))
                )

                center_error = max(
                    dx,
                    dy
                )

                if center_error > center_tolerance:
                    continue

                if min_val < best_score:
                    best_score = float(min_val)
                    best_symbol = symbol

            except Exception:
                pass

    if (
        best_symbol is not None
        and best_score < match_threshold
    ):
        return best_symbol, best_score

    return None, best_score


def square_geometry(
    board_coords,
    square,
    black_perspective
):
    """
    Same geometry calculation as before, but cached.

    board_coords and perspective are part of the cache key so changing
    the grid or orientation cannot reuse stale coordinates.
    """
    x, y, w, h = board_coords

    key = (
        int(x),
        int(y),
        int(w),
        int(h),
        int(square),
        bool(black_perspective)
    )

    cached = _SQUARE_GEOMETRY_CACHE.get(key)

    if cached is not None:
        return cached

    sq_w = w / 8.0
    sq_h = h / 8.0

    file_ = chess.square_file(square)
    rank_ = chess.square_rank(square)

    if black_perspective:
        col = 7 - file_
        row = rank_
    else:
        col = file_
        row = 7 - rank_

    x1 = int(
        x + col * sq_w
    )

    y1 = int(
        y + row * sq_h
    )

    x2 = int(
        x + (col + 1) * sq_w
    )

    y2 = int(
        y + (row + 1) * sq_h
    )

    result = (
        x1,
        y1,
        x2,
        y2
    )

    if len(_SQUARE_GEOMETRY_CACHE) > 2048:
        _SQUARE_GEOMETRY_CACHE.clear()

    _SQUARE_GEOMETRY_CACHE[key] = result

    return result


def get_square_crop(
    frame,
    board_coords,
    square,
    black_perspective
):
    if frame is None:
        return None

    x1, y1, x2, y2 = square_geometry(
        board_coords,
        square,
        black_perspective
    )

    crop = frame[
        y1:y2,
        x1:x2
    ]

    # Read-only view is sufficient for all current callers.
    # Avoiding .copy() reduces per-square allocation.
    return crop if crop.size else None


def _get_cached_square_gray(
    frame,
    board_coords,
    square,
    black_perspective
):
    """
    Cache the exact small grayscale patch used by square_change_score().

    This is one of the largest safe speed improvements because the same
    square transition is otherwise recalculated many times while testing
    legal moves.
    """
    frame_id = id(frame)

    entry = _FRAME_SQUARE_CACHE.get(frame_id)

    if entry is None or entry["frame"] is not frame:
        entry = {
            "frame": frame,
            "patches": {}
        }

        _FRAME_SQUARE_CACHE[frame_id] = entry

        while len(_FRAME_SQUARE_CACHE) > _FRAME_SQUARE_CACHE_MAX:
            oldest_key = next(
                iter(_FRAME_SQUARE_CACHE)
            )
            _FRAME_SQUARE_CACHE.pop(
                oldest_key,
                None
            )

    patch_key = (
        tuple(int(v) for v in board_coords),
        int(square),
        bool(black_perspective)
    )

    cached = entry["patches"].get(
        patch_key
    )

    if cached is not None:
        return cached

    crop = get_square_crop(
        frame,
        board_coords,
        square,
        black_perspective
    )

    if crop is None:
        return None

    small = cv2.resize(
        crop,
        (
            SQUARE_DIFF_SIZE,
            SQUARE_DIFF_SIZE
        ),
        interpolation=cv2.INTER_AREA
    )

    gray = cv2.cvtColor(
        small,
        cv2.COLOR_BGR2GRAY
    )

    entry["patches"][patch_key] = gray

    return gray


def square_change_score(
    before_frame,
    after_frame,
    board_coords,
    square,
    black_perspective
):
    if (
        before_frame is None
        or after_frame is None
    ):
        return 0.0

    before_gray = _get_cached_square_gray(
        before_frame,
        board_coords,
        square,
        black_perspective
    )

    after_gray = _get_cached_square_gray(
        after_frame,
        board_coords,
        square,
        black_perspective
    )

    if (
        before_gray is None
        or after_gray is None
    ):
        return 0.0

    diff = cv2.absdiff(
        before_gray,
        after_gray
    )

    return float(
        np.mean(diff) / 255.0
    )


def scan_board(frame, board_coords):
    start = time.perf_counter()

    x, y, w, h = board_coords

    sq_w = w / 8.0
    sq_h = h / 8.0

    templates = get_scaled_templates(
        sq_w,
        sq_h
    )

    # SPEED OPTIMIZATION:
    # Convert the complete screenshot to grayscale once.
    # Individual square matching now reuses this grayscale image.
    gray_frame = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2GRAY
    )
    board_grid = []
    confidence_grid = []

    for row in range(8):
        row_data = []
        row_conf = []

        for col in range(8):
            x1 = int(
                x + col * sq_w
            )
            y1 = int(
                y + row * sq_h
            )
            x2 = int(
                x + (col + 1) * sq_w
            )
            y2 = int(
                y + (row + 1) * sq_h
            )

            # Use the precomputed grayscale frame.
            crop_gray = gray_frame[
                y1:y2,
                x1:x2
            ]

            symbol, score = classify_square(
                crop_gray,
                templates
            )

            row_data.append(symbol)
            row_conf.append(score)

        board_grid.append(row_data)
        confidence_grid.append(row_conf)

    elapsed = (
        time.perf_counter() - start
    ) * 1000.0

    return (
        board_grid,
        confidence_grid,
        elapsed
    )


def grid_to_dict(
    grid,
    black_perspective=False
):
    pieces = {}

    if grid is None:
        return pieces

    for row in range(8):
        for col in range(8):
            symbol = grid[row][col]

            if symbol is None:
                continue

            if black_perspective:
                file_ = 7 - col
                rank_ = row
            else:
                file_ = col
                rank_ = 7 - row

            pieces[
                chess.square(
                    file_,
                    rank_
                )
            ] = symbol

    return pieces


def square_screen_center(
    square,
    board_coords,
    black_perspective,
    scrcpy_hwnd,
    screen_origin=None
):
    """
    Return a random point inside the centered 40%-area circle.

    The circle is centered in the chess square and its area is exactly
    40% of the square area. Points are sampled uniformly by area, so
    pickup and drop are random but remain strictly inside the circle.

    screen_origin is optional so click_move() can calculate the window
    origin once instead of calling GetClientRect/ClientToScreen twice.
    """
    if screen_origin is None:
        screen_origin = get_scrcpy_screen_origin(
            scrcpy_hwnd
        )

    if screen_origin is None:
        raise RuntimeError(
            "Could not determine scrcpy screen origin."
        )

    origin_x, origin_y = screen_origin

    x, y, w, h = board_coords

    sq_w = w / 8.0
    sq_h = h / 8.0

    file_ = chess.square_file(square)
    rank_ = chess.square_rank(square)

    if black_perspective:
        col = 7 - file_
        row = rank_
    else:
        col = file_
        row = 7 - rank_

    # Every pickup/drop point is sampled uniformly by area inside the
    # centered circle. The circle area is exactly 40% of the square area,
    # so points stay around the centre but are genuinely random instead of
    # repeatedly hitting one fixed centre point. A fresh point is generated
    # on every click attempt, including retries.
    angle = random.uniform(0.0, 2.0 * math.pi)
    radius = (
        CLICK_CIRCLE_RADIUS_FRACTION
        * (random.uniform(0.0, 1.0) ** 2.20)
    )

    rx = 0.5 + radius * math.cos(angle)
    ry = 0.5 + radius * math.sin(angle)

    px = (
        origin_x
        + x
        + (col + rx) * sq_w
    )

    py = (
        origin_y
        + y
        + (row + ry) * sq_h
    )

    return int(px), int(py)


def promotion_symbol(
    move,
    color
):
    if move.promotion is None:
        return None

    return chess.Piece(
        move.promotion,
        color
    ).symbol()


def promotion_candidate_squares(move):
    rank = chess.square_rank(
        move.to_square
    )

    file_ = chess.square_file(
        move.to_square
    )

    result = []

    if rank == 7:
        for step in range(4):
            candidate_rank = rank - step

            if candidate_rank >= 0:
                result.append(
                    chess.square(
                        file_,
                        candidate_rank
                    )
                )

    elif rank == 0:
        for step in range(4):
            candidate_rank = rank + step

            if candidate_rank <= 7:
                result.append(
                    chess.square(
                        file_,
                        candidate_rank
                    )
                )

    else:
        for direction in (-1, 1):
            for step in range(4):
                candidate_rank = (
                    rank
                    + direction * step
                )

                if 0 <= candidate_rank <= 7:
                    result.append(
                        chess.square(
                            file_,
                            candidate_rank
                        )
                    )

    return list(
        dict.fromkeys(result)
    )


def find_promotion_choice(
    sct,
    hwnd,
    move,
    promotion_color,
    board_coords,
    black_perspective,
    allow_fallback=True
):
    expected = promotion_symbol(
        move,
        promotion_color
    )

    if expected is None:
        return None

    frame = capture_screen(
        sct,
        hwnd
    )

    if frame is None:
        return None

    templates = get_scaled_templates(
        board_coords[2] / 8.0,
        board_coords[3] / 8.0
    )

    candidates = promotion_candidate_squares(
        move
    )

    scored = []

    for square in candidates:
        crop = get_square_crop(
            frame,
            board_coords,
            square,
            black_perspective
        )

        if crop is None:
            continue

        detected, score = classify_square(
            crop,
            templates,
            expected_symbol=expected
        )

        if detected == expected:
            scored.append(
                (
                    float(score),
                    square
                )
            )

    if scored:
        scored.sort(
            key=lambda item: item[0]
        )

        return scored[0][1]

    if allow_fallback and PROMOTION_FALLBACK:
        ordered = {
            chess.QUEEN: 0,
            chess.ROOK: 1,
            chess.BISHOP: 2,
            chess.KNIGHT: 3,
        }

        index = ordered.get(
            move.promotion
        )

        if (
            index is not None
            and index < len(candidates)
        ):
            fallback_square = candidates[index]

            print(
                f"[PROMOTION] fallback selected {expected}"
            )

            return fallback_square

    return None


def select_promotion_piece(
    sct,
    hwnd,
    move,
    promotion_color,
    board_coords,
    black_perspective,
    allow_fallback=True
):
    if move.promotion is None:
        return True

    expected = promotion_symbol(
        move,
        promotion_color
    )

    if expected is None:
        return False

    piece_name = chess.piece_name(
        move.promotion
    ).upper()

    progress(
        "PROMOTION",
        (
            f"Stockfish requested {piece_name} "
            f"({expected}); waiting for promotion menu"
        ),
        key="promotion_stage",
        force=True
    )

    for attempt in range(
        1,
        PROMOTION_RETRIES + 1
    ):
        time.sleep(
            PROMOTION_WAIT
        )

        square = find_promotion_choice(
            sct,
            hwnd,
            move,
            promotion_color,
            board_coords,
            black_perspective,
            allow_fallback=allow_fallback
        )

        if square is None:
            progress(
                "PROMOTION",
                (
                    f"menu choice {expected} not detected; "
                    f"attempt {attempt}/{PROMOTION_RETRIES}"
                ),
                key="promotion_loop",
                interval=0.20,
                force=True
            )

            continue

        px, py = square_screen_center(
            square,
            board_coords,
            black_perspective,
            hwnd
        )

        print(
            f"[PROMOTION] selecting {piece_name}"
        )

        if not focus_scrcpy(hwnd):
            continue

        left_click_screen(
            px,
            py
        )

        # Confirm that the exact promotion piece requested by Stockfish is
        # already on the destination square before accepting the promotion.
        promotion_ok = False
        promotion_reason = "promotion state not yet confirmed"
        promotion_deadline = time.perf_counter() + 0.10

        while time.perf_counter() < promotion_deadline:
            check_frame = capture_screen(
                sct,
                hwnd
            )

            if check_frame is None:
                time.sleep(
                    SCAN_INTERVAL
                )
                continue

            # Confirm directly on the destination square that the exact
            # promotion piece requested by Stockfish is now visible.
            target_crop = get_square_crop(
                check_frame,
                board_coords,
                move.to_square,
                black_perspective
            )

            templates = get_scaled_templates(
                board_coords[2] / 8.0,
                board_coords[3] / 8.0
            )

            detected_piece, detected_score = classify_square(
                target_crop,
                templates,
                expected_symbol=expected,
                match_threshold=BOT_POST_MATCH_THRESHOLD
            )

            source_crop = get_square_crop(
                check_frame,
                board_coords,
                move.from_square,
                black_perspective
            )

            source_piece, _ = classify_square(
                source_crop,
                templates
            )

            if (
                detected_piece == expected
                and source_piece is None
            ):
                promotion_ok = True
                promotion_reason = (
                    f"source=empty destination={expected} "
                    f"({detected_score:.3f})"
                )
                break

            time.sleep(
                SCAN_INTERVAL
            )

        if promotion_ok:
            time.sleep(
                CLICK_SETTLE_DELAY
            )

            progress(
                "PROMOTION",
                f"selected {piece_name}; {promotion_reason}",
                key="promotion_stage",
                force=True
            )

            return True

        progress(
            "PROMOTION",
            (
                f"{piece_name} click not confirmed; "
                f"attempt {attempt}/{PROMOTION_RETRIES}"
            ),
            key="promotion_loop",
            force=True
        )

    progress(
        "PROMOTION",
        (
            f"FAILED to select {piece_name}; "
            "game position not advanced"
        ),
        key="promotion_stage",
        force=True
    )

    return False


def _verify_source_click_selected(
    sct,
    hwnd,
    move,
    before_frame,
    board_coords,
    black_perspective
):
    """Confirm the intended SOURCE square was actually selected.

    A fast motion map is used first. The intended source must be the only
    changed board square, and it must remain the dominant changed square for
    two consecutive frames. This is deliberately strict: when Stockfish asks
    for Bxg5, a click that lands on the queen must never be allowed to reach
    the destination click and become Qxg5.
    """
    if sct is None or before_frame is None:
        return True, "source-click visual check unavailable"

    try:
        source_piece = move.from_square
    except Exception:
        return False, "invalid source square"

    start = time.perf_counter()
    deadline = start + BOT_SOURCE_SELECT_TIMEOUT
    stable_samples = 0
    last_reason = "source selection transition not detected"

    while time.perf_counter() < deadline:
        frame = capture_screen(sct, hwnd)
        if frame is None:
            time.sleep(BOT_SOURCE_SELECT_POLL)
            continue

        changes = fast_square_motion_scores(
            before_frame,
            frame,
            board_coords,
            black_perspective
        )
        if changes is None:
            last_reason = "source selection motion map unavailable"
            time.sleep(BOT_SOURCE_SELECT_POLL)
            continue

        source_change = changes.get(source_piece, 0.0)

        other_changes = sorted(
            (
                (change, square)
                for square, change in changes.items()
                if square != source_piece
                and change >= BOT_SOURCE_SELECT_CHANGE_MIN
            ),
            reverse=True,
            key=lambda item: item[0]
        )

        dominant_other = other_changes[0][0] if other_changes else 0.0
        source_is_dominant = (
            source_change >= BOT_SOURCE_SELECT_CHANGE_MIN
            and dominant_other <= source_change * BOT_SOURCE_SELECT_DOMINANCE_RATIO
        )

        if (
            source_is_dominant
            and len(other_changes) <= BOT_SOURCE_SELECT_MAX_EXTRA_CHANGES
        ):
            stable_samples += 1
            if stable_samples >= BOT_SOURCE_SELECT_STABLE_SAMPLES:
                last_reason = (
                    f"source selected {chess.square_name(source_piece)} "
                    f"change={source_change:.4f}; stable={stable_samples}"
                )
                return True, last_reason

            last_reason = (
                f"source selection seen; waiting stable sample "
                f"{stable_samples}/{BOT_SOURCE_SELECT_STABLE_SAMPLES}; "
                f"change={source_change:.4f}"
            )
        else:
            stable_samples = 0
            if other_changes:
                preview = ", ".join(
                    f"{chess.square_name(sq)}:{change:.4f}"
                    for change, sq in other_changes[:3]
                )
                last_reason = (
                    f"wrong/extra square changed; source="
                    f"{source_change:.4f}; {preview}"
                )
            else:
                last_reason = (
                    f"source change too weak: "
                    f"{source_change:.4f}"
                )

        time.sleep(BOT_SOURCE_SELECT_POLL)

    return False, last_reason


def click_move(
    move,
    board_coords,
    black_perspective,
    scrcpy_hwnd,
    sct=None,
    promotion_color=None
):
    if not focus_scrcpy(
        scrcpy_hwnd
    ):
        print(
            "[BOT ERROR] Could not focus scrcpy window."
        )

        return False

    # SPEED OPTIMIZATION:
    # Only resolve the scrcpy screen origin once for source + target.
    screen_origin = get_scrcpy_screen_origin(
        scrcpy_hwnd
    )

    if screen_origin is None:
        print(
            "[BOT ERROR] Could not determine scrcpy screen origin."
        )
        return False

    # Re-sample both pickup and drop points for every click attempt. Every
    # point remains inside the centered 40%-area circle of its own square.
    sx, sy = square_screen_center(
        move.from_square,
        board_coords,
        black_perspective,
        scrcpy_hwnd,
        screen_origin=screen_origin
    )

    tx, ty = square_screen_center(
        move.to_square,
        board_coords,
        black_perspective,
        scrcpy_hwnd,
        screen_origin=screen_origin
    )

    print(
        f"[BOT CLICK] {move.uci()} "
        f"source=({sx},{sy}) target=({tx},{ty})"
    )

    # Keep the mouse cursor completely away from the chess board between
    # moves. This prevents it from remaining on the previous source/target.
    user32.SetCursorPos(0, 0)
    time.sleep(0.010)

    # Select the locked source with a real press/hold/release sequence.
    # The slightly longer hold makes source registration more reliable
    # through scrcpy than the previous zero-duration dispatch.
    user32.SetCursorPos(
        int(sx),
        int(sy)
    )
    time.sleep(0.020)
    user32.mouse_event(
        MOUSEEVENTF_LEFTDOWN,
        0,
        0,
        0,
        0
    )
    time.sleep(0.035)
    user32.mouse_event(
        MOUSEEVENTF_LEFTUP,
        0,
        0,
        0,
        0
    )

    time.sleep(0.025)

    # Drop only on the locked destination, again using a real
    # press/hold/release sequence.
    user32.SetCursorPos(
        int(tx),
        int(ty)
    )
    time.sleep(0.020)
    user32.mouse_event(
        MOUSEEVENTF_LEFTDOWN,
        0,
        0,
        0,
        0
    )
    time.sleep(0.030)
    user32.mouse_event(
        MOUSEEVENTF_LEFTUP,
        0,
        0,
        0,
        0
    )

    # Immediately park the cursor outside the board. It must not sit on
    # the old move while the system is waiting for the verified result.
    user32.SetCursorPos(0, 0)
    time.sleep(0.010)

    if move.promotion is not None:
        if promotion_color is None:
            promotion_color = chess.WHITE

        if sct is None:
            print(
                "[PROMOTION ERROR] "
                "Screen capture context unavailable."
            )

            return False

        promotion_ok = select_promotion_piece(
            sct,
            scrcpy_hwnd,
            move,
            promotion_color,
            board_coords,
            black_perspective
        )

        # After promotion is also completed, keep the cursor off the board.
        user32.SetCursorPos(0, 0)
        return promotion_ok

    return True

def expected_changed_squares(
    board,
    move
):
    squares = {
        move.from_square,
        move.to_square
    }

    if board.is_castling(move):
        if board.is_kingside_castling(move):
            rook_from = (
                chess.H1
                if board.turn == chess.WHITE
                else chess.H8
            )

            rook_to = (
                chess.F1
                if board.turn == chess.WHITE
                else chess.F8
            )

        else:
            rook_from = (
                chess.A1
                if board.turn == chess.WHITE
                else chess.A8
            )

            rook_to = (
                chess.D1
                if board.turn == chess.WHITE
                else chess.D8
            )

        squares.update({
            rook_from,
            rook_to
        })

    if board.is_en_passant(move):
        captured = (
            move.to_square - 8
            if board.turn == chess.WHITE
            else move.to_square + 8
        )

        squares.add(
            captured
        )

    return squares


def expected_board_after_move(
    board,
    move
):
    after = board.copy(
        stack=False
    )

    after.push(move)

    return after


def expected_symbol_after(
    board,
    move,
    square
):
    after = expected_board_after_move(
        board,
        move
    )

    piece = after.piece_at(
        square
    )

    return (
        piece.symbol()
        if piece
        else None
    )


def grid_conf_dict(
    grid,
    confidence_grid,
    black_perspective=False
):
    if grid is None:
        return {}

    # SPEED OPTIMIZATION:
    # The same grid/confidence objects are evaluated against many legal
    # moves. Build this mapping once per grid.
    key = (
        id(grid),
        id(confidence_grid),
        bool(black_perspective)
    )

    cached = _GRID_CONF_CACHE.get(
        key
    )

    if cached is not None:
        cached_grid = cached[0]
        cached_conf = cached[1]

        if (
            cached_grid is grid
            and cached_conf is confidence_grid
        ):
            return cached[2]

    values = {}

    for row in range(8):
        for col in range(8):
            symbol = grid[row][col]

            confidence = 999.0

            if confidence_grid is not None:
                confidence = confidence_grid[row][col]

            if black_perspective:
                file_ = 7 - col
                rank_ = row
            else:
                file_ = col
                rank_ = 7 - row

            square = chess.square(
                file_,
                rank_
            )

            values[square] = (
                symbol,
                confidence
            )

    _GRID_CONF_CACHE[key] = (
        grid,
        confidence_grid,        values
    )

    while len(_GRID_CONF_CACHE) > _GRID_CONF_CACHE_MAX:
        oldest_key = next(
            iter(_GRID_CONF_CACHE)
        )

        _GRID_CONF_CACHE.pop(
            oldest_key,
            None
        )

    return values


def board_hypothesis_score(
    board,
    move,
    grid,
    confidence_grid,
    black_perspective
):
    expected_board = expected_board_after_move(
        board,
        move
    )

    observed = grid_conf_dict(
        grid,
        confidence_grid,
        black_perspective
    )

    score = 0.0
    maximum = 0.0
    exact = 0
    type_match = 0
    empty_match = 0
    mismatch = 0

    for square in chess.SQUARES:
        expected_piece = expected_board.piece_at(
            square
        )

        expected_symbol = (
            expected_piece.symbol()
            if expected_piece
            else None
        )

        observed_symbol, observed_conf = observed.get(
            square,
            (None, 999.0)
        )

        if expected_symbol is None:
            maximum += 1.0

            if observed_symbol is None:
                score += 1.0
                empty_match += 1
            else:
                score -= 1.6
                mismatch += 1

            continue

        maximum += 3.2

        if observed_symbol is None:
            score -= 2.0
            mismatch += 1

        elif observed_symbol == expected_symbol:
            quality = max(
                0.0,
                MATCH_THRESHOLD - observed_conf
            )

            score += (
                3.2
                + min(
                    0.35,
                    quality
                )
            )

            exact += 1

        elif (
            observed_symbol.lower()
            == expected_symbol.lower()
        ):
            score += 2.15
            type_match += 1

        else:
            score -= 1.8
            mismatch += 1

    normalized = (
        score / maximum
        if maximum > 0
        else 0.0
    )

    return {
        "score": score,
        "normalized": normalized,
        "exact": exact,
        "type_match": type_match,
        "empty": empty_match,
        "mismatch": mismatch
    }


def move_transition_strength(
    before_frame,
    after_frame,
    board,
    move,
    board_coords,
    black_perspective
):
    affected = expected_changed_squares(
        board,
        move
    )

    total = 0.0
    minimum = 0.0
    values = {}

    for square in affected:
        value = square_change_score(
            before_frame,
            after_frame,
            board_coords,
            square,
            black_perspective
        )

        values[square] = value
        total += value

    if affected:
        minimum = min(
            values.values()
        )

    return (
        total,
        minimum,
        values
    )


def rank_changed_squares(
    before_frame,
    after_frame,
    board_coords,
    black_perspective
):
    changes = []

    for square in chess.SQUARES:
        score = square_change_score(
            before_frame,
            after_frame,
            board_coords,
            square,
            black_perspective
        )

        if score >= CHANGE_THRESHOLD:
            changes.append(
                (
                    score,
                    square
                )
            )

    changes.sort(
        reverse=True,
        key=lambda item: item[0]
    )

    return changes


def move_visual_score(
    before_frame,
    after_frame,
    board,
    move,
    board_coords,
    black_perspective,
    templates
):
    changed = expected_changed_squares(
        board,
        move
    )

    observed = {
        square: square_change_score(
            before_frame,
            after_frame,
            board_coords,
            square,
            black_perspective
        )
        for square in changed
    }

    target_change = observed.get(
        move.to_square,
        0.0
    )

    source_change = observed.get(
        move.from_square,
        0.0
    )

    if target_change < TARGET_CHANGE_THRESHOLD:
        return None

    if (
        not board.is_castling(move)
        and not board.is_en_passant(move)
    ):
        if source_change < SOURCE_CHANGE_THRESHOLD:
            return None

    expected_target = expected_symbol_after(
        board,
        move,
        move.to_square
    )

    target_match = 0.0

    if expected_target is not None:
        target_crop = get_square_crop(
            after_frame,
            board_coords,
            move.to_square,
            black_perspective
        )

        detected_symbol, score = classify_square(
            target_crop,
            templates
        )

        if detected_symbol is None:
            return None

        if (
            detected_symbol.lower()
            != expected_target.lower()
        ):
            return None

        target_match = max(
            0.0,
            MATCH_THRESHOLD - score
        )

    if board.is_castling(move):
        rook_square = (
            chess.F1
            if (
                board.turn == chess.WHITE
                and board.is_kingside_castling(move)
            )
            else chess.D1
            if board.turn == chess.WHITE
            else chess.F8
            if board.is_kingside_castling(move)
            else chess.D8
        )

        rook_change = observed.get(
            rook_square,
            0.0
        )

        if rook_change < CHANGE_THRESHOLD:
            return None

        king_expected = (
            "K"
            if board.turn == chess.WHITE
            else "k"
        )

        rook_expected = (
            "R"
            if board.turn == chess.WHITE
            else "r"
        )

        king_crop = get_square_crop(
            after_frame,
            board_coords,
            move.to_square,
            black_perspective
        )

        rook_crop = get_square_crop(
            after_frame,
            board_coords,
            rook_square,
            black_perspective
        )

        king_symbol, king_score = classify_square(
            king_crop,
            templates
        )

        rook_symbol, rook_score = classify_square(
            rook_crop,
            templates
        )

        if not king_symbol or not rook_symbol:
            return None

        if (
            king_symbol.lower()
            != king_expected.lower()
        ):
            return None

        if (
            rook_symbol.lower()
            != rook_expected.lower()
        ):
            return None

        return (
            target_change
            + rook_change
            + target_match
        )

    if board.is_en_passant(move):
        captured_square = (
            move.to_square - 8
            if board.turn == chess.WHITE
            else move.to_square + 8
        )

        captured_change = observed.get(
            captured_square,
            0.0
        )

        if captured_change < CHANGE_THRESHOLD:
            return None

        return (
            target_change
            + captured_change
            + target_match
        )

    return (
        target_change
        + max(
            source_change,
            0.0
        )
        + target_match
    )


def human_piece_type(
    board,
    move
):
    piece = board.piece_at(
        move.from_square
    )

    return (
        piece.piece_type
        if piece is not None
        else None
    )


def human_direct_state_confirmed(
    frame,
    board,
    move,
    board_coords,
    black_perspective,
    templates
):
    """
    Targeted final check for fast PAWN/ROOK moves.
    """
    source_piece = board.piece_at(
        move.from_square
    )

    if source_piece is None:
        return (
            False,
            "source piece missing from internal board"
        )

    source_crop = get_square_crop(
        frame,
        board_coords,
        move.from_square,
        black_perspective
    )

    target_crop = get_square_crop(
        frame,
        board_coords,
        move.to_square,
        black_perspective
    )

    source_detected, source_score = classify_square(
        source_crop,
        templates
    )

    if source_detected is not None:
        return (
            False,
            (
                f"source still shows "
                f"{source_detected} "
                f"({source_score:.3f})"
            )
        )

    expected_target = expected_symbol_after(
        board,
        move,
        move.to_square
    )

    if expected_target is None:
        return (
            False,
            "expected destination piece missing"
        )

    target_detected, target_score = classify_square(
        target_crop,
        templates,
        expected_symbol=expected_target
    )

    if target_detected != expected_target:
        return (
            False,
            (
                f"target "
                f"{target_detected or '-'} != "
                f"{expected_target} "
                f"({target_score:.3f})"
            )
        )

    return (
        True,
        (
            f"source empty; target "
            f"{expected_target} "
            f"({target_score:.3f})"
        )
    )



def fast_human_move_rescan(
    sct,
    hwnd,
    board,
    baseline_frame,
    board_coords,
    black_perspective,
    legal_moves
):
    """Ultra-fast human move detection before the slower legacy scanner.

    The first pass uses a vectorized 128x128 board diff. Only legal moves whose
    source and destination are among the strongest changed squares are tested.
    Exact piece-state verification is then performed only on the top few
    candidates. A second fresh frame must confirm the same candidate before the
    move is returned.
    """
    if baseline_frame is None or not legal_moves:
        return None, None

    start = time.perf_counter()
    last_frame = None
    last_candidates = []

    while (
        time.perf_counter() - start
        < HUMAN_FAST_RESCAN_CONFIRM_TIMEOUT
    ):
        frame = capture_screen(
            sct,
            hwnd
        )

        if frame is None:
            time.sleep(HUMAN_FAST_RESCAN_POLL)
            continue

        last_frame = frame

        changed = fast_square_motion_scores(
            baseline_frame,
            frame,
            board_coords,
            black_perspective
        )

        if changed is None:
            time.sleep(HUMAN_FAST_RESCAN_POLL)
            continue

        ranked = sorted(
            (
                (score, square)
                for square, score in changed.items()
                if score >= HUMAN_FAST_RESCAN_THRESHOLD
            ),
            reverse=True,
            key=lambda item: item[0]
        )

        if len(ranked) < 2:
            time.sleep(HUMAN_FAST_RESCAN_POLL)
            continue

        top_squares = {
            square
            for _, square in ranked[:HUMAN_FAST_RESCAN_TOP_SQUARES]
        }

        candidates = []

        for move in legal_moves:
            if (
                move.from_square not in top_squares
                or move.to_square not in top_squares
            ):
                continue

            source_change = changed.get(
                move.from_square,
                0.0
            )
            target_change = changed.get(
                move.to_square,
                0.0
            )

            if (
                source_change < HUMAN_FAST_RESCAN_THRESHOLD
                or target_change < HUMAN_FAST_RESCAN_THRESHOLD
            ):
                continue

            affected = expected_changed_squares(
                board,
                move
            )

            total_change = sum(
                changed.get(square, 0.0)
                for square in affected
            )

            candidates.append(
                (
                    total_change,
                    move
                )
            )

        if not candidates:
            time.sleep(HUMAN_FAST_RESCAN_POLL)
            continue

        candidates.sort(
            reverse=True,
            key=lambda item: item[0]
        )
        last_candidates = candidates[:HUMAN_FAST_RESCAN_TOP_MOVES]

        # Exact post-state check only on the strongest candidates.
        for _, move in last_candidates:
            ok, _ = fast_expected_post_state_confirmed(
                baseline_frame,
                frame,
                board,
                move,
                board_coords,
                black_perspective
            )

            if not ok:
                continue

            # Confirm the same candidate on one more fresh frame.
            confirm_deadline = (
                time.perf_counter()
                + HUMAN_FAST_RESCAN_CONFIRM_TIMEOUT
            )

            while (
                time.perf_counter() < confirm_deadline
            ):
                confirm_frame = capture_screen(
                    sct,
                    hwnd
                )

                if confirm_frame is None:
                    continue

                confirm_ok, confirm_reason = fast_expected_post_state_confirmed(
                    baseline_frame,
                    confirm_frame,
                    board,
                    move,
                    board_coords,
                    black_perspective
                )

                if confirm_ok:
                    # IMPORTANT: source/destination alone are not enough.
                    # The current scrcpy frame must match the complete chess
                    # position expected after this exact human move. This
                    # prevents a visually-near candidate such as Qh5 from
                    # being committed when the real screen move was Qg4/Qg5.
                    full_ok, full_reason = full_board_state_confirmed(
                        confirm_frame,
                        expected_board_after_move(board, move),
                        board_coords,
                        black_perspective
                    )

                    if full_ok:
                        progress(
                            "HUMAN",
                            (
                                f"FAST verified {move.uci()} | "
                                f"scrcpy full-board PASS 64/64"
                            ),
                            key="human_fast_verify",
                            force=True
                        )
                        return (
                            move,
                            confirm_frame
                        )

                    progress(
                        "HUMAN",
                        (
                            f"FAST rejected {move.uci()} | "
                            f"scrcpy full-board mismatch | {full_reason}"
                        ),
                        key="human_fast_reject",
                        force=True
                    )

                # Once this candidate no longer matches, don't wait the whole
                # confirmation window; another move/candidate may be visible.
                break

        time.sleep(
            HUMAN_FAST_RESCAN_POLL
        )

    return None, None




def periodic_full_board_catchup_scan(
    sct,
    hwnd,
    board,
    board_coords,
    black_perspective,
    pending_bot_move=None,
    first_frame=None,
    legal_moves=None
):
    """Recover an already-settled move from complete 64-square board state.

    This is deliberately a recovery layer, not a replacement for the normal
    temporal detector. The last committed python-chess board remains the
    reference. The screen is scanned twice; legal move hypotheses are tested
    against those observations; and the winning expected board must pass the
    existing strict full-board verifier.

    During a frozen Stockfish move, two positions are tested:
      internal -> pending Stockfish move
      internal -> pending Stockfish move -> one legal human reply

    The function only returns a verified hypothesis. It never mutates ``board``.
    """
    if board is None or board_coords is None:
        return None

    if legal_moves is None:
        legal_moves = list(board.legal_moves)

    if pending_bot_move is None and not legal_moves:
        return None

    frame_a = first_frame
    if frame_a is None:
        frame_a = capture_screen(sct, hwnd)
    if frame_a is None:
        return None

    grid_a, conf_a, scan_a_ms = scan_board(
        frame_a,
        board_coords
    )
    observed_a = grid_conf_dict(
        grid_a,
        conf_a,
        black_perspective
    )

    time.sleep(TURN_RESCAN_CONFIRM_DELAY)

    frame_b = capture_screen(sct, hwnd)
    if frame_b is None:
        return None

    grid_b, conf_b, scan_b_ms = scan_board(
        frame_b,
        board_coords
    )
    observed_b = grid_conf_dict(
        grid_b,
        conf_b,
        black_perspective
    )

    def raw_mismatch(observed, expected_board):
        count = 0
        for square in chess.SQUARES:
            observed_symbol, _ = observed.get(
                square,
                (None, 999.0)
            )
            piece = expected_board.piece_at(square)
            expected_symbol = (
                piece.symbol()
                if piece is not None
                else None
            )
            if observed_symbol != expected_symbol:
                count += 1
        return count

    def robust_mismatch(frame, observed, expected_board):
        mismatches = []
        exact = 0

        templates = get_scaled_templates(
            board_coords[2] / 8.0,
            board_coords[3] / 8.0
        )

        for square in chess.SQUARES:
            observed_symbol, observed_conf = observed.get(
                square,
                (None, 999.0)
            )
            piece = expected_board.piece_at(square)
            expected_symbol = (
                piece.symbol()
                if piece is not None
                else None
            )

            if observed_symbol == expected_symbol:
                exact += 1
                continue

            # Occupied expected squares get the same exact expected-piece
            # fallback used by strict full-board verification. This handles
            # isolated template confusion such as bishop/rook.
            if expected_symbol is not None:
                crop = get_square_crop(
                    frame,
                    board_coords,
                    square,
                    black_perspective
                )
                detected, _ = classify_square(
                    crop,
                    templates,
                    expected_symbol=expected_symbol,
                    match_threshold=FULL_BOARD_EXPECTED_MATCH_THRESHOLD
                )
                if detected == expected_symbol:
                    exact += 1
                    continue

            mismatches.append((
                square,
                expected_symbol,
                observed_symbol,
                observed_conf
            ))

        return len(mismatches), exact, mismatches

    candidates = []

    # Human turn: internal board -> one legal human move. Never use this
    # branch while a frozen/pending Stockfish move is being recovered.
    if pending_bot_move is None and board.turn in (chess.WHITE, chess.BLACK):
        for move in legal_moves:
            expected_after = expected_board_after_move(board, move)
            candidates.append({
                "kind": "HUMAN_ONLY",
                "bot_move": None,
                "human_move": move,
                "expected_board": expected_after,
                "raw_pair": raw_mismatch(observed_a, expected_after)
                    + raw_mismatch(observed_b, expected_after),
            })

    # Stockfish turn with a frozen move: test bot-only and bot+human.
    if pending_bot_move is not None:
        if not isinstance(pending_bot_move, chess.Move):
            try:
                pending_bot_move = chess.Move.from_uci(
                    str(pending_bot_move)
                )
            except Exception:
                pending_bot_move = None

    if pending_bot_move is not None and pending_bot_move in board.legal_moves:
        bot_after = expected_board_after_move(
            board,
            pending_bot_move
        )

        candidates.append({
            "kind": "BOT_ONLY",
            "bot_move": pending_bot_move,
            "human_move": None,
            "expected_board": bot_after,
            "raw_pair": raw_mismatch(observed_a, bot_after)
                + raw_mismatch(observed_b, bot_after),
        })

        for human_move in bot_after.legal_moves:
            final_board = expected_board_after_move(
                bot_after,
                human_move
            )
            candidates.append({
                "kind": "BOT_PLUS_HUMAN",
                "bot_move": pending_bot_move,
                "human_move": human_move,
                "expected_board": final_board,
                "raw_pair": raw_mismatch(observed_a, final_board)
                    + raw_mismatch(observed_b, final_board),
            })

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item["raw_pair"]
    )

    evaluated = []
    for item in candidates[:TURN_RESCAN_TOP_CANDIDATES]:
        ma, ea, da = robust_mismatch(
            frame_a,            observed_a,
            item["expected_board"]
        )
        mb, eb, db = robust_mismatch(
            frame_b,
            observed_b,
            item["expected_board"]
        )

        ranked = dict(item)
        ranked.update({
            "mismatch_a": ma,
            "mismatch_b": mb,
            "exact_a": ea,
            "exact_b": eb,
            "details_a": da,
            "details_b": db,
            "score": ma * 100 + mb * 100 - ea - eb,
        })
        evaluated.append(ranked)

    evaluated.sort(
        key=lambda item: (item["score"], item["raw_pair"])
    )

    best = evaluated[0]
    second_score = (
        evaluated[1]["score"]
        if len(evaluated) > 1
        else 999999
    )
    margin = second_score - best["score"]

    if (
        best["mismatch_a"] > TURN_RESCAN_MAX_MISMATCH
        or best["mismatch_b"] > TURN_RESCAN_MAX_MISMATCH
    ):
        preview = " ".join(
            f"{chess.square_name(sq)}:{exp or '-'}->{obs or '-'}({conf:.3f})"
            for sq, exp, obs, conf in best["details_b"][:6]
        )
        progress(
            "RECOVERY",
            (
                f"2s FULL RESCAN | WAITING | best={best['kind']} "
                f"bot={best['bot_move'].uci() if best['bot_move'] else '-'} "
                f"human={best['human_move'].uci() if best['human_move'] else '-'} "
                f"A={best['mismatch_a']}/64 B={best['mismatch_b']}/64 "
                f"preview={preview or '-'} "
                f"scan={scan_a_ms:.1f}/{scan_b_ms:.1f}ms"
            ),
            key="turn_rescan_wait",
            force=True
        )
        return None

    full_ok, full_reason = full_board_state_confirmed(
        frame_b,
        best["expected_board"],
        board_coords,
        black_perspective
    )

    if not full_ok:
        progress(
            "RECOVERY",
            (
                f"2s FULL RESCAN | candidate rejected | "
                f"bot={best['bot_move'].uci() if best['bot_move'] else '-'} "
                f"human={best['human_move'].uci() if best['human_move'] else '-'} | "
                f"{full_reason}"
            ),
            key="turn_rescan_reject",
            force=True
        )
        return None

    progress(
        "RECOVERY",
        (
            f"2s FULL RESCAN VERIFIED | kind={best['kind']} "
            f"bot={best['bot_move'].uci() if best['bot_move'] else '-'} "
            f"human={best['human_move'].uci() if best['human_move'] else '-'} "
            f"A={best['exact_a']}/64 B={best['exact_b']}/64 "
            f"margin={margin:.0f} scan={scan_a_ms:.1f}/{scan_b_ms:.1f}ms"
        ),
        key="turn_rescan_verify",
        force=True
    )

    return {
        "kind": best["kind"],
        "bot_move": best["bot_move"],
        "human_move": best["human_move"],
        "frame": frame_b,
        "reason": (
            "2-second full-board rescan + two-frame legal-state match + "
            "strict full-board verification"
        ),
    }


def ultra_board_delta_recovery(
    sct,
    hwnd,
    board,
    baseline_frame,
    board_coords,
    black_perspective,
    legal_moves,
    first_frame=None
):
    """Recover a missed human move from the full-board state delta.

    The last committed internal board is treated as the reference position.
    We scan the current board, find which squares differ from that internal
    position, and ask python-chess which legal move best explains those exact
    differences. A second independent frame must support the same move.

    Motion is used as an additional signal, but a settled final position can
    still be accepted when the temporal motion signal is weak: the unchanged
    final board is cross-validated against the internal board and a second
    full scan before the move is declared.
    """
    if baseline_frame is None or not legal_moves:
        return None, None

    frame = first_frame
    if frame is None:
        frame = capture_screen(sct, hwnd)
    if frame is None:
        return None, None

    def scan_observation(scan_frame):
        grid, confidence, scan_ms = scan_board(
            scan_frame,
            board_coords
        )
        observed = grid_conf_dict(
            grid,
            confidence,
            black_perspective
        )
        return observed, confidence, scan_ms

    observed_a, confidence_a, scan_a_ms = scan_observation(frame)

    internal_symbols = {
        square: (
            board.piece_at(square).symbol()
            if board.piece_at(square) is not None
            else None
        )
        for square in chess.SQUARES
    }

    # Differences between the physical board and the last committed internal
    # board. Confidence is retained so a weak template mismatch does not get
    # treated as hard evidence against a candidate move.
    diff_a = {}
    for square in chess.SQUARES:
        observed_symbol, observed_conf = observed_a.get(
            square,
            (None, 999.0)
        )
        expected_symbol = internal_symbols[square]
        if observed_symbol == expected_symbol:
            continue
        if (
            observed_symbol is None
            or expected_symbol is None
            or observed_conf <= HUMAN_ULTRA_DELTA_CONF_MAX
        ):
            diff_a[square] = (
                observed_symbol,
                observed_conf
            )

    if len(diff_a) < HUMAN_ULTRA_DELTA_MIN_EXACT:
        progress(
            "HUMAN",
            (
                f"ULTRA DELTA | internal-vs-screen changed="
                f"{', '.join(chess.square_name(sq) for sq in diff_a) or '-'} "
                "| insufficient changed squares; WAITING"
            ),
            key="human_ultra_delta_wait",
            force=True
        )
        return None, None

    time.sleep(HUMAN_ULTRA_DELTA_CONFIRM_DELAY)
    frame_b = capture_screen(sct, hwnd)
    if frame_b is None:
        return None, None
    observed_b, confidence_b, scan_b_ms = scan_observation(frame_b)

    diff_b = {}
    for square in chess.SQUARES:
        observed_symbol, observed_conf = observed_b.get(
            square,
            (None, 999.0)
        )
        expected_symbol = internal_symbols[square]
        if observed_symbol == expected_symbol:
            continue
        if (
            observed_symbol is None
            or expected_symbol is None
            or observed_conf <= HUMAN_ULTRA_DELTA_CONF_MAX
        ):
            diff_b[square] = (
                observed_symbol,
                observed_conf
            )

    def candidate_metrics(observed, move, diff_squares):
        expected_after = expected_board_after_move(
            board,
            move
        )
        affected = set(expected_changed_squares(board, move))

        exact_affected = 0
        changed_affected = 0
        missing = 0
        extra = 0
        after_mismatch = 0

        for square in chess.SQUARES:
            observed_symbol, observed_conf = observed.get(
                square,
                (None, 999.0)
            )
            expected_symbol = (
                expected_after.piece_at(square).symbol()
                if expected_after.piece_at(square) is not None
                else None
            )

            if observed_symbol == expected_symbol:
                if square in affected:
                    exact_affected += 1
                continue

            # Count a board-state mismatch only when the classifier has some
            # usable confidence. Very weak classifications are treated as
            # uncertain rather than hard evidence against the candidate.
            if (
                observed_symbol is not None
                and observed_conf > HUMAN_ULTRA_DELTA_CONF_MAX
            ):
                continue

            after_mismatch += 1
            if square in affected:
                changed_affected += 1

        for square in affected:
            observed_symbol, observed_conf = observed.get(
                square,
                (None, 999.0)
            )
            expected_symbol = (
                expected_after.piece_at(square).symbol()
                if expected_after.piece_at(square) is not None
                else None
            )

            if observed_symbol != expected_symbol:
                missing += 1

        for square in diff_squares:
            if square not in affected:
                extra += 1

        # Strong reward for explaining the exact source/destination change;
        # missing/extra changed squares are penalized but tolerated slightly
        # because the full-board template classifier can be imperfect.
        score = (
            exact_affected * 28.0
            + changed_affected * 8.0
            - missing * 10.0
            - extra * 7.0
            - after_mismatch * 1.25
        )

        return {
            "score": score,
            "affected": affected,
            "exact_affected": exact_affected,
            "changed_affected": changed_affected,
            "missing": missing,
            "extra": extra,
            "after_mismatch": after_mismatch,
            "expected_after": expected_after,
        }

    # Rank legal moves by how well their expected resulting position explains
    # the observed internal-board delta. This is independent of the engine's
    # predicted reply, so a surprising but legal human move can still be found.
    candidates_a = []

    for move in legal_moves:
        ma = candidate_metrics(observed_a, move, diff_a)
        mb = candidate_metrics(observed_b, move, diff_b)
        combined = ma["score"] + mb["score"]
        candidates_a.append((combined, move, ma, mb))

    candidates_a.sort(
        reverse=True,
        key=lambda item: item[0]
    )

    if not candidates_a:
        return None, None

    best_total, best_move, best_a, best_b = candidates_a[0]
    second_total = (
        candidates_a[1][0]
        if len(candidates_a) > 1
        else -999.0
    )
    margin = best_total - second_total

    # The moved squares must be visible as actual differences from the
    # internal board in both frames, and the expected post-state must explain
    # those differences in both scans.
    required_exact = max(
        HUMAN_ULTRA_DELTA_MIN_EXACT,
        len(best_a["affected"]) - 1
    )

    changed_names = ','.join(
        chess.square_name(square)
        for square in sorted(diff_a)
    )
    changed_names_b = ','.join(
        chess.square_name(square)
        for square in sorted(diff_b)
    )

    motion = fast_square_motion_scores(
        baseline_frame,
        frame_b,
        board_coords,
        black_perspective
    )
    source_motion = (
        motion.get(best_move.from_square, 0.0)
        if motion is not None
        else 0.0
    )
    target_motion = (
        motion.get(best_move.to_square, 0.0)
        if motion is not None
        else 0.0
    )
    motion_total = source_motion + target_motion

    progress(
        "HUMAN",
        (
            f"ULTRA DELTA | internal-change={changed_names} "
            f"confirm-change={changed_names_b} "
            f"candidate={best_move.uci()} "
            f"A={best_a['exact_affected']}/{len(best_a['affected'])} "
            f"B={best_b['exact_affected']}/{len(best_b['affected'])} "
            f"missing={best_a['missing']}/{best_b['missing']} "
            f"extra={best_a['extra']}/{best_b['extra']} "
            f"margin={margin:.2f} "
            f"motion={motion_total:.4f} "
            f"scan={scan_a_ms:.1f}/{scan_b_ms:.1f}ms"
        ),
        key="human_ultra_delta_candidate",
        force=True
    )

    if (
        best_a["exact_affected"] < required_exact
        or best_b["exact_affected"] < required_exact
        or best_a["missing"] > HUMAN_ULTRA_DELTA_MAX_MISSING
        or best_b["missing"] > HUMAN_ULTRA_DELTA_MAX_MISSING
        or best_a["extra"] > HUMAN_ULTRA_DELTA_MAX_EXTRA
        or best_b["extra"] > HUMAN_ULTRA_DELTA_MAX_EXTRA
        or margin < HUMAN_ULTRA_DELTA_MARGIN
    ):
        progress(
            "HUMAN",
            "ULTRA DELTA | candidate not sufficiently explained; continuing WAITING",
            key="human_ultra_delta_wait",
            force=True
        )
        return None, None

    # Static final-state cross-check. This is deliberately independent from
    # the normal motion classifier so an already-settled fast human move can
    # still be recovered.
    full_ok, full_reason = full_board_state_confirmed(
        frame_b,
        best_a["expected_after"],
        board_coords,
        black_perspective
    )

    motion_supported = (
        source_motion >= HUMAN_ULTRA_DELTA_MOTION_FLOOR
        or target_motion >= HUMAN_ULTRA_DELTA_MOTION_FLOOR
    )

    if not full_ok:
        progress(
            "HUMAN",
            (
                f"ULTRA DELTA | state rejected {best_move.uci()} | "
                f"{full_reason}"
            ),
            key="human_ultra_delta_reject",
            force=True
        )
        return None, None

    # The full-board state and two-scan delta already provide strong physical
    # evidence. Motion is a useful extra signal when available, but it is not
    # mandatory for a move that is visibly settled and stable in both scans.
    progress(
        "HUMAN",
        (
            f"ULTRA DELTA VERIFIED {best_move.uci()} | "
            f"internal-board delta + dual scan + full-board "
            f"state PASS | motion={'YES' if motion_supported else 'WEAK'}"
        ),
        key="human_ultra_delta_verify",
        force=True
    )

    return best_move, frame_b


def ultra_human_background_rescan(
    sct,
    hwnd,
    board,
    baseline_frame,
    board_coords,
    black_perspective,
    legal_moves
):
    """Full-board recovery pass for a human move missed by fast detection.

    Detector 1: vectorized board motion identifies the squares that really
    changed and keeps only legal moves whose source and destination both moved.

    Detector 2: one complete 64-square scan checks the resulting position
    against each motion candidate. Only a move passing both detectors is then
    sent through the existing physical verification gate.
    """
    if baseline_frame is None or not legal_moves:
        return None, None

    ultra_start = time.perf_counter()
    frame = capture_screen(sct, hwnd)
    if frame is None:
        return None, None

    changed = fast_square_motion_scores(
        baseline_frame,
        frame,
        board_coords,
        black_perspective
    )

    if changed is None:
        return None, None

    changed_ranked = sorted(
        (
            (score, square)
            for square, score in changed.items()
            if score >= HUMAN_ULTRA_CHANGE_THRESHOLD
        ),
        reverse=True,
        key=lambda item: item[0]
    )

    if len(changed_ranked) < 2:
        delta_move, delta_frame = ultra_board_delta_recovery(
            sct,
            hwnd,
            board,
            baseline_frame,
            board_coords,
            black_perspective,
            legal_moves,
            first_frame=frame
        )
        if delta_move is not None and delta_frame is not None:
            detect_human_move._last_detection_source = "ULTRA_DELTA"
            return delta_move, delta_frame

        progress(
            "HUMAN",
            "ULTRA RESCAN | no board motion detected; continuing WAITING",
            key="human_ultra_wait",
            force=True
        )
        return None, None

    top_squares = {
        square
        for _, square in changed_ranked[:HUMAN_ULTRA_TOP_SQUARES]
    }

    motion_candidates = []

    for move in legal_moves:
        source_change = changed.get(move.from_square, 0.0)
        target_change = changed.get(move.to_square, 0.0)

        if (
            move.from_square not in top_squares
            or move.to_square not in top_squares
            or source_change < HUMAN_ULTRA_MOTION_MIN
            or target_change < HUMAN_ULTRA_MOTION_MIN
        ):
            continue

        affected = expected_changed_squares(board, move)
        total_motion = sum(
            changed.get(square, 0.0)
            for square in affected
        )

        motion_candidates.append(
            (total_motion, move, source_change, target_change)
        )

    if not motion_candidates:
        delta_move, delta_frame = ultra_board_delta_recovery(
            sct,
            hwnd,
            board,
            baseline_frame,
            board_coords,
            black_perspective,
            legal_moves,
            first_frame=frame
        )
        if delta_move is not None and delta_frame is not None:
            detect_human_move._last_detection_source = "ULTRA_DELTA"
            return delta_move, delta_frame

        progress(
            "HUMAN",
            "ULTRA RESCAN | board changed, but no legal source->target motion pair",
            key="human_ultra_wait",
            force=True
        )
        return None, None

    motion_candidates.sort(reverse=True, key=lambda item: item[0])
    motion_candidates = motion_candidates[:HUMAN_ULTRA_TOP_MOVES]

    # Detector 2: full-board scan. This is deliberately performed only when
    # real board motion was already found, so a static board does not pay this
    # cost every time the normal waiting loop runs.
    grid, confidence, scan_ms = scan_board(
        frame,
        board_coords
    )

    best_scan = None
    for total_motion, move, source_change, target_change in motion_candidates:
        hypothesis = board_hypothesis_score(
            board,
            move,
            grid,
            confidence,
            black_perspective
        )

        score = (
            hypothesis["normalized"] * 100.0
            + min(18.0, total_motion * 70.0)
            + hypothesis["exact"] * 0.12
            - hypothesis["mismatch"] * 0.025
        )

        item = (
            score,
            move,
            hypothesis,
            total_motion,
            source_change,
            target_change
        )

        if best_scan is None or score > best_scan[0]:
            best_scan = item

    if best_scan is None:
        return None, None

    best_score, best_move, best_hypothesis, total_motion, source_change, target_change = best_scan
    second_scores = []

    for total_motion_i, move_i, source_i, target_i in motion_candidates:
        if move_i == best_move:
            continue
        hypothesis_i = board_hypothesis_score(
            board,
            move_i,
            grid,
            confidence,
            black_perspective
        )
        score_i = (
            hypothesis_i["normalized"] * 100.0
            + min(18.0, total_motion_i * 70.0)
            + hypothesis_i["exact"] * 0.12
            - hypothesis_i["mismatch"] * 0.025
        )
        second_scores.append(score_i)

    second_score = max(second_scores) if second_scores else -999.0
    margin = best_score - second_score

    progress(
        "HUMAN",
        (
            f"ULTRA RESCAN | changed={len(changed_ranked)} "
            f"candidate={best_move.uci()} "
            f"motion={total_motion:.4f} "
            f"src={source_change:.4f} "
            f"dst={target_change:.4f} "
            f"board={best_hypothesis['normalized']:.3f} "
            f"margin={margin:.2f} scan={scan_ms:.1f}ms"
        ),
        key="human_ultra_candidate",
        force=True
    )

    # Final safety detector: exact expected source/destination state and no
    # strong unexpected motion. This prevents a random animation/highlight from
    # being declared as a chess move.
    if (
        source_change < HUMAN_ULTRA_MOTION_MIN
        or target_change < HUMAN_ULTRA_MOTION_MIN
        or best_hypothesis["normalized"] < 0.62
        or margin < HUMAN_ULTRA_MOVE_MARGIN
    ):
        delta_move, delta_frame = ultra_board_delta_recovery(
            sct,
            hwnd,
            board,
            baseline_frame,
            board_coords,
            black_perspective,
            legal_moves,
            first_frame=frame
        )
        if delta_move is not None and delta_frame is not None:
            detect_human_move._last_detection_source = "ULTRA_DELTA"
            return delta_move, delta_frame

        progress(
            "HUMAN",
            "ULTRA RESCAN | candidate not strong enough; continuing WAITING",
            key="human_ultra_wait",
            force=True
        )
        return None, None

    post_ok, post_reason = fast_expected_post_state_confirmed(
        baseline_frame,
        frame,
        board,
        best_move,
        board_coords,
        black_perspective
    )

    full_ok, full_reason = full_board_state_confirmed(
        frame,
        expected_board_after_move(board, best_move),
        board_coords,
        black_perspective
    )

    if not post_ok or not full_ok:
        delta_move, delta_frame = ultra_board_delta_recovery(
            sct,
            hwnd,
            board,
            baseline_frame,
            board_coords,
            black_perspective,
            legal_moves,
            first_frame=frame
        )
        if delta_move is not None and delta_frame is not None:
            detect_human_move._last_detection_source = "ULTRA_DELTA"
            return delta_move, delta_frame

        progress(
            "HUMAN",
            (
                f"ULTRA RESCAN | rejected {best_move.uci()} | "
                f"motion={'PASS' if post_ok else post_reason}; "
                f"full={'PASS' if full_ok else full_reason}"
            ),
            key="human_ultra_reject",
            force=True
        )
        time.sleep(HUMAN_ULTRA_SCAN_COOLDOWN)
        return None, None

    # Re-use the existing physical verification gate one final time. It still
    # returns only after the screen itself confirms the move, and the caller
    # pushes the move only after receiving this verified frame.
    physical_ok, verified_frame, physical_reason = verify_human_move_on_screen(
        sct,
        hwnd,
        expected_board_after_move(board, best_move),
        baseline_frame,
        board_coords,
        black_perspective,
        best_move,
        board.copy(stack=False)
    )

    if not physical_ok:
        delta_move, delta_frame = ultra_board_delta_recovery(
            sct,
            hwnd,
            board,
            baseline_frame,
            board_coords,
            black_perspective,
            legal_moves,
            first_frame=frame
        )
        if delta_move is not None and delta_frame is not None:
            detect_human_move._last_detection_source = "ULTRA_DELTA"
            return delta_move, delta_frame

        progress(
            "HUMAN",
            (
                f"ULTRA RESCAN | physical verification rejected "
                f"{best_move.uci()} | {physical_reason}"
            ),
            key="human_ultra_reject",
            force=True
        )
        return None, None

    progress(
        "HUMAN",
        (
            f"ULTRA VERIFIED {best_move.uci()} | "
            f"motion + full-board + physical verification passed | "
            f"total={time.perf_counter() - ultra_start:.3f}s"
        ),
        key="human_ultra_verify",
        force=True
    )

    return (
        best_move,
        verified_frame if verified_frame is not None else frame
    )

def detect_human_move(
    sct,
    hwnd,
    board,
    baseline_frame,
    board_coords,
    black_perspective
):
    if baseline_frame is None:
        return None, None

    start = time.perf_counter()
    detect_human_move._last_detection_source = None

    # Keep the ultra-rescan schedule across repeated calls to this function.
    # The main loop calls detect_human_move() in short chunks; this state makes
    # the recovery pass happen every ~2 seconds for the same human turn.
    position_key = board.fen()
    state = getattr(detect_human_move, "_ultra_state", None)
    if state is None or state.get("position_key") != position_key:
        state = {
            "position_key": position_key,
            "turn_started": time.perf_counter(),
            "next_ultra": time.perf_counter() + HUMAN_ULTRA_RESCAN_INTERVAL,
        }
        detect_human_move._ultra_state = state

    progress(
        "HUMAN",
        "starting move scanner",
        key="human_stage",
        force=True
    )

    confirmations = {}
    last_candidate = None
    last_scan_time = 0.0
    last_fallback_scan = 0.0

    # SPEED OPTIMIZATION:
    # Legal moves do not change while the same board position is being
    # observed, so calculate them once for this detection session.
    legal_moves = list(
        board.legal_moves
    )

    # After the normal detector has had its chance for the current human turn,
    # run the scheduled ultra recovery pass at the beginning of the next scan
    # chunk. Keeping this check outside the 1.25s local loop guarantees the
    # recovery pass is not starved between repeated detector calls.
    now = time.perf_counter()
    if now >= state["next_ultra"]:
        # EXTRA 2-second complete-board recovery. It is intentionally before
        # the existing motion-based ultra pass so an already-settled move
        # can still be reconstructed from the current board state.
        catchup = periodic_full_board_catchup_scan(
            sct,
            hwnd,
            board,
            board_coords,
            black_perspective,
            pending_bot_move=None,
            first_frame=None,
            legal_moves=legal_moves
        )
        state["next_ultra"] = now + HUMAN_ULTRA_RESCAN_INTERVAL

        if catchup is not None and catchup["kind"] == "HUMAN_ONLY":
            detect_human_move._last_detection_source = "PERIODIC_FULL_RESCAN"
            return catchup["human_move"], catchup["frame"]

        ultra_move, ultra_frame = ultra_human_background_rescan(
            sct,
            hwnd,
            board,
            baseline_frame,
            board_coords,
            black_perspective,
            legal_moves
        )
        if ultra_move is not None and ultra_frame is not None:
            return ultra_move, ultra_frame

    # Fast rescan FIRST. This catches a real human move without waiting for
    # the slower legacy rank/64-square template pipeline.
    fast_move, fast_frame = fast_human_move_rescan(
        sct,
        hwnd,
        board,
        baseline_frame,
        board_coords,
        black_perspective,
        legal_moves
    )

    if (
        fast_move is not None
        and fast_frame is not None
    ):
        return fast_move, fast_frame

    while (
        time.perf_counter() - start
        < HUMAN_MOVE_TIMEOUT
    ):
        now = time.perf_counter()

        frame = capture_screen(
            sct,
            hwnd
        )

        if frame is None:
            time.sleep(
                SCAN_INTERVAL
            )
            continue

        ranked = rank_changed_squares(
            baseline_frame,
            frame,
            board_coords,
            black_perspective
        )

        strong_change = (
            len(ranked) >= 2            and ranked[0][0] >= HUMAN_FALLBACK_CHANGE_THRESHOLD
            and ranked[1][0] >= HUMAN_FALLBACK_CHANGE_THRESHOLD
        )

        fallback_mode = False

        # --------------------------------------------------------
        # NORMAL PATH
        # --------------------------------------------------------
        if strong_change:
            settled = get_settled_frame(
                sct,
                hwnd,
                frame,
                timeout=HUMAN_SETTLE_TIMEOUT
            )

            candidate_frame = (
                settled
                if settled is not None
                else frame
            )

            grid, confidence, scan_ms = scan_board(
                candidate_frame,
                board_coords
            )

            last_scan_time = scan_ms

            candidates = []

            for move in legal_moves:
                (
                    transition_total,
                    transition_min,
                    transition_values
                ) = move_transition_strength(
                    baseline_frame,
                    candidate_frame,
                    board,
                    move,
                    board_coords,
                    black_perspective
                )

                if transition_total < 0.004:
                    continue

                hypothesis = board_hypothesis_score(
                    board,
                    move,
                    grid,
                    confidence,
                    black_perspective
                )

                combined = (
                    hypothesis["normalized"] * 100.0
                    + min(
                        12.0,
                        transition_total * 45.0
                    )
                    + hypothesis["exact"] * 0.08
                    - hypothesis["mismatch"] * 0.03
                )

                candidates.append(
                    (
                        combined,
                        move,
                        hypothesis,
                        transition_values
                    )
                )

        # --------------------------------------------------------
        # TARGETED FALLBACK
        # --------------------------------------------------------
        else:
            now = time.perf_counter()

            if (
                now - last_fallback_scan
                < HUMAN_FALLBACK_SCAN_INTERVAL
            ):
                progress(
                    "HUMAN",
                    (
                        f"scanning... "
                        f"{now - start:.2f}s | "
                        "waiting for stable move"
                    ),
                    key="human_loop"
                )

                time.sleep(
                    SCAN_INTERVAL
                )

                continue

            last_fallback_scan = now

            top_squares = [
                square
                for score, square in ranked[
                    :HUMAN_FALLBACK_TOP_SQUARES
                ]
                if score >= HUMAN_FALLBACK_CHANGE_THRESHOLD
            ]

            if not top_squares:
                progress(
                    "HUMAN",
                    (
                        f"scanning... "
                        f"{now - start:.2f}s | "
                        "no stable move yet"
                    ),
                    key="human_loop"
                )

                time.sleep(
                    SCAN_INTERVAL
                )

                continue

            fallback_moves = []

            for move in legal_moves:
                if (
                    move.from_square not in top_squares
                    and move.to_square not in top_squares
                ):
                    continue

                (
                    transition_total,
                    transition_min,
                    transition_values
                ) = move_transition_strength(
                    baseline_frame,
                    frame,
                    board,
                    move,
                    board_coords,
                    black_perspective
                )

                source_change = transition_values.get(
                    move.from_square,
                    0.0
                )

                target_change = transition_values.get(
                    move.to_square,
                    0.0
                )

                if (
                    source_change
                    < HUMAN_FALLBACK_CHANGE_THRESHOLD
                    or
                    target_change
                    < HUMAN_FALLBACK_CHANGE_THRESHOLD
                ):
                    continue

                fallback_moves.append(
                    (
                        transition_total,
                        move,
                        transition_values
                    )
                )

            if not fallback_moves:
                progress(
                    "HUMAN",
                    (
                        f"scanning... "
                        f"{now - start:.2f}s | "
                        "no targeted recovery candidate"
                    ),
                    key="human_loop"
                )

                time.sleep(
                    SCAN_INTERVAL
                )

                continue

            candidate_frame = frame

            grid, confidence, scan_ms = scan_board(
                candidate_frame,
                board_coords
            )

            last_scan_time = scan_ms

            fallback_mode = True
            candidates = []

            for (
                transition_total,
                move,
                transition_values
            ) in fallback_moves:

                hypothesis = board_hypothesis_score(
                    board,
                    move,
                    grid,
                    confidence,
                    black_perspective
                )

                combined = (
                    hypothesis["normalized"] * 100.0
                    + min(
                        14.0,
                        transition_total * 60.0
                    )
                    + hypothesis["exact"] * 0.10
                    - hypothesis["mismatch"] * 0.025
                )

                candidates.append(
                    (
                        combined,
                        move,
                        hypothesis,
                        transition_values
                    )
                )

        if not candidates:
            time.sleep(
                SCAN_INTERVAL
            )
            continue

        candidates.sort(
            reverse=True,
            key=lambda item: item[0]
        )

        (
            best_score,
            best_move,
            best_hypothesis,
            best_transition
        ) = candidates[0]

        progress(
            "HUMAN",
            (
                f"candidate={best_move.uci()} "
                f"score={best_score:.2f} "
                f"board={best_hypothesis['normalized']:.3f} "
                f"candidates={len(candidates)}"
                + (
                    " fallback"
                    if fallback_mode
                    else ""
                )
            ),
            key="human_candidate",
            interval=0.45
        )

        second_score = (
            candidates[1][0]
            if len(candidates) > 1
            else -999.0
        )

        margin = (
            best_score
            - second_score
        )

        piece_type = human_piece_type(
            board,
            best_move
        )

        is_pawn_or_rook = (
            piece_type
            in (
                chess.PAWN,
                chess.ROOK
            )
        )

        if fallback_mode:
            source_change = best_transition.get(
                best_move.from_square,
                0.0
            )

            target_change = best_transition.get(
                best_move.to_square,
                0.0
            )

            candidate_ok = (
                best_hypothesis["normalized"] >= 0.70
                and margin >= 1.0
                and source_change >= HUMAN_FALLBACK_CHANGE_THRESHOLD
                and target_change >= HUMAN_FALLBACK_CHANGE_THRESHOLD
            )

        else:
            candidate_ok = (
                best_hypothesis["normalized"] >= 0.74
                and margin >= 1.0
                and len(best_transition) >= 2
            )

        if candidate_ok:
            key = best_move.uci()

            if key == last_candidate:
                confirmations[key] = (
                    confirmations.get(key, 0)
                    + 1
                )
            else:
                confirmations = {
                    key: 1
                }

                last_candidate = key

            if (
                confirmations[key]
                >= HUMAN_CONFIRM_SAMPLES
            ):
                final_frame = get_settled_frame(
                    sct,
                    hwnd,
                    candidate_frame,
                    timeout=HUMAN_SETTLE_TIMEOUT
                )

                if final_frame is None:
                    final_frame = candidate_frame

                (
                    final_grid,
                    final_confidence,
                    final_scan_ms
                ) = scan_board(
                    final_frame,
                    board_coords
                )

                final_hypothesis = board_hypothesis_score(
                    board,
                    best_move,
                    final_grid,
                    final_confidence,
                    black_perspective
                )

                if (
                    final_hypothesis["normalized"]
                    >= 0.72
                ):
                    expected_human_board = expected_board_after_move(
                        board,
                        best_move
                    )

                    (
                        physical_ok,
                        verified_frame,
                        physical_reason
                    ) = verify_human_move_on_screen(
                        sct,
                        hwnd,
                        expected_human_board,
                        baseline_frame,
                        board_coords,
                        black_perspective,
                        best_move,
                        board.copy(stack=False)
                    )

                    if physical_ok:
                        progress(
                            "HUMAN",
                            (
                                f"verified {best_move.uci()} | "
                                f"{physical_reason}"
                            ),
                            key="human_stage",
                            force=True
                        )

                        return (
                            best_move,
                            verified_frame
                            if verified_frame is not None
                            else final_frame
                        )

                    progress(
                        "HUMAN",
                        (
                            f"candidate {best_move.uci()} rejected by "
                            f"physical board check: {physical_reason}"
                        ),
                        key="human_physical_reject",
                        force=True
                    )

                if is_pawn_or_rook:
                    templates = get_scaled_templates(
                        board_coords[2] / 8.0,
                        board_coords[3] / 8.0
                    )

                    (
                        transition_total,
                        _,
                        final_transition
                    ) = move_transition_strength(
                        baseline_frame,
                        final_frame,
                        board,
                        best_move,
                        board_coords,
                        black_perspective
                    )

                    final_source_change = (
                        final_transition.get(
                            best_move.from_square,
                            0.0
                        )
                    )

                    final_target_change = (
                        final_transition.get(
                            best_move.to_square,
                            0.0
                        )
                    )

                    (
                        direct_ok,
                        direct_reason
                    ) = human_direct_state_confirmed(
                        final_frame,
                        board,
                        best_move,
                        board_coords,
                        black_perspective,
                        templates
                    )

                    if (
                        direct_ok
                        and transition_total >= 0.0025
                        and final_source_change
                        >= HUMAN_FALLBACK_CHANGE_THRESHOLD
                        and final_target_change
                        >= HUMAN_FALLBACK_CHANGE_THRESHOLD
                        and final_hypothesis["normalized"]
                        >= 0.68
                    ):
                        expected_human_board = expected_board_after_move(
                            board,
                            best_move
                        )

                        (
                            physical_ok,
                            verified_frame,
                            physical_reason
                        ) = verify_human_move_on_screen(
                            sct,
                            hwnd,
                            expected_human_board,
                            baseline_frame,
                            board_coords,
                            black_perspective,
                            best_move,
                            board.copy(stack=False)
                        )

                        if physical_ok:
                            progress(
                                "HUMAN",
                                (
                                    f"verified "
                                    f"{best_move.uci()} "
                                    "via pawn/rook recovery | "
                                    f"{physical_reason}"
                                ),
                                key="human_stage",
                                force=True
                            )

                            return (
                                best_move,
                                verified_frame
                                if verified_frame is not None
                                else final_frame
                            )

                        progress(
                            "HUMAN",
                            (
                                f"pawn/rook candidate {best_move.uci()} "
                                "rejected by physical board check: "
                                f"{physical_reason}"
                            ),
                            key="human_physical_reject",
                            force=True
                        )

                progress(
                    "HUMAN",
                    (
                        f"candidate {best_move.uci()} "
                        "failed final check: "
                        f"{final_hypothesis['normalized']:.3f}"
                    ),
                    key="human_final"
                )

        time.sleep(
            SCAN_INTERVAL
        )

    return None, None


def get_settled_frame(
    sct,
    hwnd,
    first_frame,
    timeout=0.10
):
    start = time.perf_counter()

    progress(
        "SETTLE",
        (
            "waiting for stable frame "
            f"({timeout:.2f}s)"
        ),
        key="settle",
        force=True
    )

    previous = first_frame
    stable_count = 0
    last = first_frame

    while (
        time.perf_counter() - start
        < timeout
    ):
        frame = capture_screen(
            sct,
            hwnd
        )

        if frame is None:
            continue

        change = board_frame_change_score(
            previous,
            frame
        )

        last = frame

        if change < 0.0015:
            stable_count += 1
        else:
            stable_count = 0

        progress(
            "SETTLE",
            (
                f"change={change:.4f} "
                f"stable={stable_count}/2"
            ),
            key="settle_loop",
            interval=0.10
        )

        if stable_count >= 2:
            progress(
                "SETTLE",
                "stable frame acquired",
                key="settle",
                force=True
            )

            return frame

        previous = frame

    progress(
        "SETTLE",
        "timeout; using latest frame",
        key="settle",
        force=True
    )

    return last


def board_frame_change_score(
    before_frame,
    after_frame
):
    if (
        before_frame is None
        or after_frame is None
    ):
        return 1.0

    if (
        before_frame.shape
        != after_frame.shape
    ):
        return 1.0

    small_before = cv2.resize(
        before_frame,
        (96, 96),
        interpolation=cv2.INTER_AREA
    )

    small_after = cv2.resize(
        after_frame,
        (96, 96),
        interpolation=cv2.INTER_AREA
    )

    gray_before = cv2.cvtColor(
        small_before,
        cv2.COLOR_BGR2GRAY
    )

    gray_after = cv2.cvtColor(
        small_after,
        cv2.COLOR_BGR2GRAY
    )

    return float(
        np.mean(
            cv2.absdiff(
                gray_before,
                gray_after
            )
        ) / 255.0
    )


def validate_bot_move_frame(
    before_frame,
    after_frame,
    board,
    move,
    board_coords,
    black_perspective
):
    if (
        before_frame is None
        or after_frame is None
    ):
        return False, "missing frame"

    templates = get_scaled_templates(
        board_coords[2] / 8.0,
        board_coords[3] / 8.0
    )

    score = move_visual_score(
        before_frame,
        after_frame,
        board,
        move,
        board_coords,
        black_perspective,
        templates
    )

    if score is None:
        return (
            False,
            "expected visual transition not confirmed"
        )

    return (
        True,
        f"visual score {score:.3f}"
    )


def direct_move_state_confirmed(
    frame,
    board,
    move,
    board_coords,
    black_perspective
):
    """
    Check only the squares that must be different after the move.
    """
    if frame is None:
        return False, "missing frame"

    templates = get_scaled_templates(
        board_coords[2] / 8.0,
        board_coords[3] / 8.0
    )

    def detect_expected(
        square,
        expected_symbol,
        label
    ):
        crop = get_square_crop(
            frame,
            board_coords,
            square,
            black_perspective
        )

        detected, score = classify_square(
            crop,
            templates,
            expected_symbol=expected_symbol,
            match_threshold=BOT_POST_MATCH_THRESHOLD
        )

        if detected is None:
            return (
                False,
                f"{label} not detected"
            )

        if (
            detected.lower()
            != expected_symbol.lower()
        ):
            return (
                False,
                (
                    f"{label} type is "
                    f"{detected}, expected "
                    f"{expected_symbol}"
                )
            )

        return (
            True,
            (
                f"{label}="
                f"{detected},{score:.3f}"
            )
        )

    def require_empty(
        square,
        label
    ):
        crop = get_square_crop(
            frame,
            board_coords,
            square,
            black_perspective
        )

        detected, score = classify_square(
            crop,
            templates
        )

        if detected is not None:
            return (
                False,
                (
                    f"{label} still occupied "
                    f"({detected},{score:.3f})"
                )
            )

        return (
            True,
            f"{label}=empty"
        )

    ok, reason = require_empty(
        move.from_square,
        "source"
    )

    if not ok:
        return False, reason

    expected_target = expected_symbol_after(
        board,
        move,
        move.to_square
    )

    if expected_target is not None:
        ok, reason = detect_expected(
            move.to_square,
            expected_target,
            "destination"
        )

        if not ok:
            return False, reason

    if board.is_castling(move):
        if board.is_kingside_castling(move):
            rook_from = (
                chess.H1
                if board.turn == chess.WHITE
                else chess.H8
            )

            rook_to = (
                chess.F1
                if board.turn == chess.WHITE
                else chess.F8
            )

        else:
            rook_from = (
                chess.A1
                if board.turn == chess.WHITE
                else chess.A8
            )

            rook_to = (
                chess.D1
                if board.turn == chess.WHITE
                else chess.D8
            )

        ok, reason = require_empty(
            rook_from,
            "castling rook source"
        )

        if not ok:
            return False, reason

        expected_rook = (
            "R"
            if board.turn == chess.WHITE
            else "r"
        )

        ok, reason = detect_expected(
            rook_to,
            expected_rook,
            "castling rook destination"
        )

        if not ok:
            return False, reason

    if board.is_en_passant(move):
        captured_square = (
            move.to_square - 8
            if board.turn == chess.WHITE
            else move.to_square + 8
        )

        ok, reason = require_empty(
            captured_square,
            "en-passant captured square"
        )

        if not ok:
            return False, reason

    return (
        True,
        "direct changed-square state confirmed"
    )

def _fast_board_gray(frame, board_coords, size=FAST_VERIFY_SIZE):
    if frame is None:
        return None
    x, y, w, h = board_coords
    x1 = max(0, int(x))
    y1 = max(0, int(y))
    x2 = min(frame.shape[1], int(x + w))
    y2 = min(frame.shape[0], int(y + h))
    if x2 <= x1 or y2 <= y1:
        return None
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)


def fast_board_motion_map(before_frame, after_frame, board_coords):
    before = _fast_board_gray(before_frame, board_coords)
    after = _fast_board_gray(after_frame, board_coords)
    if before is None or after is None:
        return None
    diff = cv2.absdiff(before, after).astype(np.float32) / 255.0
    cell = FAST_VERIFY_SIZE // 8
    scores = {}
    for row in range(8):
        for col in range(8):
            value = float(np.mean(diff[row*cell:(row+1)*cell, col*cell:(col+1)*cell]))
            # Map visual row/col to chess square later in caller.
            scores[(row, col)] = value
    return scores


def fast_square_motion_scores(before_frame, after_frame, board_coords, black_perspective):
    visual_scores = fast_board_motion_map(before_frame, after_frame, board_coords)
    if visual_scores is None:
        return None
    scores = {}
    for square in chess.SQUARES:
        file_ = chess.square_file(square)
        rank_ = chess.square_rank(square)
        if black_perspective:
            col = 7 - file_
            row = rank_
        else:
            col = file_
            row = 7 - rank_
        scores[square] = visual_scores[(row, col)]
    return scores


def fast_expected_post_state_confirmed(
    before_frame,
    after_frame,
    board,
    move,
    board_coords,
    black_perspective
):
    """Fast closed-loop post-move verification without a 64-template scan."""
    if before_frame is None or after_frame is None:
        return False, "missing verification frame"

    observed_changes = fast_square_motion_scores(
        before_frame, after_frame, board_coords, black_perspective
    )
    if observed_changes is None:
        return False, "fast board motion map unavailable"

    affected = set(expected_changed_squares(board, move))
    unexpected = []
    for square, change in observed_changes.items():
        if square in affected:
            continue
        if change >= FAST_UNEXPECTED_STRONG_DIFF:
            unexpected.append((square, change))

    # Any strong change outside the squares that this move is allowed to touch
    # means a wrong click or an unexpected board transition occurred.
    if len(unexpected) > FAST_MAX_UNEXPECTED_CHANGED_SQUARES:
        preview = ', '.join(
            f"{chess.square_name(sq)}:{change:.3f}"
            for sq, change in unexpected[:4]
        )
        return False, f"unexpected board change {preview}"

    templates = get_scaled_templates(
        board_coords[2] / 8.0, board_coords[3] / 8.0
    )

    def expected_piece_at(frame, square, expected_symbol):
        crop = get_square_crop(
            frame, board_coords, square, black_perspective
        )
        if expected_symbol is None:
            detected, score = classify_square(crop, templates)
            return detected is None, detected, score
        detected, score = classify_square(
            crop, templates, expected_symbol=expected_symbol,
            match_threshold=FULL_BOARD_EXPECTED_MATCH_THRESHOLD
        )
        return detected == expected_symbol, detected, score

    source_piece = board.piece_at(move.from_square)

    # For ordinary moves, source disappearance is verified by the physical
    # motion of the source square instead of asking the empty-square classifier
    # to prove that the square is empty. Empty/background squares are the most
    # common source of false negatives because highlights/anti-aliasing can
    # resemble the old piece template.
    source_change = observed_changes.get(move.from_square, 0.0)
    target_change = observed_changes.get(move.to_square, 0.0)

    expected_target = expected_symbol_after(
        board,
        move,
        move.to_square
    )

    if expected_target is not None:
        target_ok, target_detected, target_score = expected_piece_at(
            after_frame,
            move.to_square,
            expected_target
        )
        if not target_ok:
            return False, (
                f"destination mismatch "
                f"({target_detected or '-'}:{target_score:.3f}, "
                f"expected {expected_target})"
            )

        if target_change < FAST_REQUIRED_CHANGED_DIFF:
            return False, (
                f"destination transition too weak: "
                f"{target_change:.4f}"
            )

    if move.from_square != move.to_square:
        if source_piece is None:
            return False, "internal source piece missing"

        source_min_change = max(
            0.0007,
            FAST_REQUIRED_CHANGED_DIFF
        )
        if source_change < source_min_change:
            return False, (
                f"source transition too weak: "
                f"{source_change:.4f}"
            )

    if board.is_castling(move):
        rook_to = (
            chess.F1 if board.turn == chess.WHITE and board.is_kingside_castling(move) else
            chess.D1 if board.turn == chess.WHITE else
            chess.F8 if board.is_kingside_castling(move) else chess.D8
        )
        rook_expected = "R" if board.turn == chess.WHITE else "r"
        rook_ok, rook_detected, rook_score = expected_piece_at(
            after_frame,
            rook_to,
            rook_expected
        )
        if not rook_ok:
            return False, (
                f"castling rook mismatch "
                f"({rook_detected or '-'}:{rook_score:.3f})"
            )

        rook_change = observed_changes.get(rook_to, 0.0)
        if rook_change < FAST_REQUIRED_CHANGED_DIFF:
            return False, (
                f"castling rook transition too weak: "
                f"{rook_change:.4f}"
            )

    if board.is_en_passant(move):
        captured_square = (
            move.to_square - 8
            if board.turn == chess.WHITE
            else move.to_square + 8
        )
        captured_change = observed_changes.get(
            captured_square,
            0.0
        )
        captured_ok, captured_detected, captured_score = expected_piece_at(
            after_frame,
            captured_square,
            None
        )
        if not captured_ok:
            return False, (
                f"en-passant captured square not empty "
                f"({captured_detected or '-'}:{captured_score:.3f})"
            )

        if captured_change < FAST_REQUIRED_CHANGED_DIFF:
            return False, (
                f"en-passant captured square transition too weak: "
                f"{captured_change:.4f}"
            )

    return True, (
        "fast physical post-state confirmed "
        f"src={source_change:.4f} dst={target_change:.4f}"
    )

def fast_preclick_board_confirmed(
    reference_frame,
    frame,
    board,
    move,
    board_coords,
    black_perspective
):
    """Fast check that the board is still the last verified internal position."""
    if reference_frame is None or frame is None:
        return False, "missing pre-click frame"

    changes = fast_square_motion_scores(
        reference_frame, frame, board_coords, black_perspective
    )
    if changes is None:
        return False, "fast board motion map unavailable"

    # Ignore the current source/destination only for the safety preview; on a
    # true pre-click frame they must still contain the internal pieces below.
    unexpected = [
        (sq, value)
        for sq, value in changes.items()
        if value >= FAST_UNEXPECTED_STRONG_DIFF
    ]
    if unexpected:
        preview = ', '.join(
            f"{chess.square_name(sq)}:{value:.3f}"
            for sq, value in unexpected[:4]
        )
        return False, f"physical board changed before click ({preview})"

    templates = get_scaled_templates(
        board_coords[2] / 8.0, board_coords[3] / 8.0
    )
    source_piece = board.piece_at(move.from_square)
    if source_piece is None:
        return False, "internal source piece missing"
    source_crop = get_square_crop(
        frame, board_coords, move.from_square, black_perspective
    )
    source_detected, _ = classify_square(source_crop, templates)
    if source_detected != source_piece.symbol():
        return False, f"source mismatch {source_detected or '-'} != {source_piece.symbol()}"

    if board.piece_at(move.to_square) is None:
        target_crop = get_square_crop(
            frame, board_coords, move.to_square, black_perspective
        )
        target_detected, target_score = classify_square(
            target_crop,
            templates,
            match_threshold=EMPTY_DEST_MATCH_THRESHOLD
        )
        if target_detected is not None:
            return False, (
                f"destination unexpectedly occupied by "
                f"{target_detected} ({target_score:.3f})"
            )

    return True, "physical board still matches internal position"


def screen_still_before_move(
    frame,
    board,
    move,
    board_coords,
    black_perspective
):
    # The caller passes the last verified baseline frame. For compatibility,
    # keep this function as the exact-piece guard; the fast pre-click board
    # reference check is performed against baseline_frame at the call site.
    if frame is None:
        return False

    templates = get_scaled_templates(
        board_coords[2] / 8.0, board_coords[3] / 8.0
    )
    source_piece = board.piece_at(move.from_square)
    if source_piece is None:
        return False

    source_crop = get_square_crop(
        frame, board_coords, move.from_square, black_perspective
    )
    source_detected, _ = classify_square(source_crop, templates)
    if source_detected != source_piece.symbol():
        return False

    if board.piece_at(move.to_square) is None:
        target_crop = get_square_crop(
            frame, board_coords, move.to_square, black_perspective
        )
        target_detected, _ = classify_square(
            target_crop,
            templates,
            match_threshold=EMPTY_DEST_MATCH_THRESHOLD
        )
        if target_detected is not None:
            return False

    return True


def full_board_state_confirmed(

    frame,
    expected_board,
    board_coords,
    black_perspective
):
    """Require the physical screen to match the expected chess position.

    The normal 64-square scan is still performed, but occupied squares are
    additionally checked against the exact piece that python-chess expects.
    This resolves isolated template confusions such as a rook being read as
    a bishop while still rejecting genuine board drift.
    """
    if frame is None:
        return False, "missing frame for full-board validation"

    grid, confidence_grid, scan_ms = scan_board(
        frame,
        board_coords
    )

    observed = grid_conf_dict(
        grid,
        confidence_grid,
        black_perspective
    )

    templates = get_scaled_templates(
        board_coords[2] / 8.0,
        board_coords[3] / 8.0
    )

    mismatches = []

    for square in chess.SQUARES:
        expected_piece = expected_board.piece_at(square)
        expected_symbol = (
            expected_piece.symbol()
            if expected_piece is not None
            else None
        )

        observed_symbol, observed_conf = observed.get(
            square,
            (None, 999.0)
        )

        if observed_symbol == expected_symbol:
            continue

        # For occupied expected squares, re-check ONLY the expected piece
        # template. The generic scan can confuse visually similar templates
        # (e.g. rook/bishop) even though the correct expected piece is present.
        if expected_symbol is not None:
            crop = get_square_crop(
                frame,
                board_coords,
                square,
                black_perspective
            )

            expected_detected, expected_score = classify_square(
                crop,
                templates,
                expected_symbol=expected_symbol,
                match_threshold=FULL_BOARD_EXPECTED_MATCH_THRESHOLD
            )

            if expected_detected == expected_symbol:
                continue

        mismatches.append((
            chess.square_name(square),
            expected_symbol or "-",
            observed_symbol or "-",
            observed_conf
        ))

    if mismatches:
        preview = "; ".join(
            f"{sq}:{exp}->{obs}"
            for sq, exp, obs, _ in mismatches[:6]
        )
        if len(mismatches) > 6:
            preview += f"; +{len(mismatches) - 6} more"
        return False, (
            f"full-board mismatch {len(mismatches)}/64 ({preview})"
        )

    return True, f"full-board match 64/64 scan={scan_ms:.1f}ms"


def verify_human_move_on_screen(
    sct,
    hwnd,
    expected_board,
    frame,
    board_coords,
    black_perspective,
    move,
    before_board
):
    """Fast human post-move physical verification.

    The last verified frame is used as the reference. Every board square is
    checked for unexpected pixel movement in one vectorized 128x128 diff,
    while exact piece templates are checked only on the move's affected
    squares. Internal board is still advanced only after this gate passes.
    """
    start = time.perf_counter()
    deadline = start + max(HUMAN_MOVE_TIMEOUT, 0.55)
    last_frame = frame
    last_reason = "human post-move position not yet visible"

    if move is None:
        return False, frame, "missing human move for fast verification"

    baseline_frame = frame
    while time.perf_counter() < deadline:
        candidate_frame = capture_screen(sct, hwnd)
        if candidate_frame is None:
            time.sleep(BOT_RECOVERY_POLL)
            continue
        last_frame = candidate_frame

        ok, reason = fast_expected_post_state_confirmed(
            baseline_frame,
            candidate_frame,
            before_board,
            move,
            board_coords,
            black_perspective
        )
        if ok:
            # Final authority is the actual scrcpy board image, not only the
            # two affected squares. Require the complete expected position
            # before the internal python-chess board is ever advanced.
            full_ok, full_reason = full_board_state_confirmed(
                candidate_frame,
                expected_board,
                board_coords,
                black_perspective
            )
            if full_ok:
                return True, candidate_frame, (
                    "scrcpy full-board match 64/64; "
                    + reason
                )
            last_reason = full_reason
        else:
            last_reason = reason

        time.sleep(BOT_RECOVERY_POLL)

    return False, last_frame, last_reason


def screen_matches_expected_bot_move(
    frame,
    board,
    move,
    board_coords,
    black_perspective,
    before_frame=None
):
    if frame is None:
        return False, "missing frame"

    if before_frame is None:
        return False, "missing pre-move reference frame"

    fast_ok, fast_reason = fast_expected_post_state_confirmed(
        before_frame,
        frame,
        board,
        move,
        board_coords,
        black_perspective
    )
    if not fast_ok:
        return False, fast_reason

    # Pending/recovery confirmation must use the same strict final authority
    # as the normal bot path. Never commit a move from a loose two-square
    # match, especially when Bxg5 could physically become Qxg5.
    expected_after = expected_board_after_move(
        board,
        move
    )
    full_ok, full_reason = full_board_state_confirmed(
        frame,
        expected_after,
        board_coords,
        black_perspective
    )
    if not full_ok:
        return False, (
            "fast post-state passed but scrcpy full-board rejected: "
            + full_reason
        )

    return True, (
        "scrcpy full-board match 64/64; "
        + fast_reason
    )


def transition_confirmed(

    before_frame,
    after_frame,
    board,
    move,
    board_coords,
    black_perspective
):
    affected = expected_changed_squares(
        board,
        move
    )

    changes = {}

    for square in affected:
        changes[square] = square_change_score(
            before_frame,
            after_frame,
            board_coords,
            square,
            black_perspective
        )

    target_change = changes.get(
        move.to_square,
        0.0
    )

    source_change = changes.get(
        move.from_square,
        0.0
    )

    if target_change < TARGET_CHANGE_THRESHOLD:
        return (
            False,
            "destination did not visually change"
        )

    if board.is_castling(move):
        rook_to = (
            chess.F1
            if (
                board.turn == chess.WHITE
                and board.is_kingside_castling(move)
            )
            else chess.D1
            if board.turn == chess.WHITE
            else chess.F8
            if board.is_kingside_castling(move)
            else chess.D8
        )

        if (
            changes.get(
                rook_to,
                0.0
            )
            < CHANGE_THRESHOLD
        ):
            return (
                False,
                "castling rook transition not detected"
            )

        return (
            True,
            f"transition confirmed {target_change:.3f}"
        )

    if board.is_en_passant(move):
        captured = (
            move.to_square - 8
            if board.turn == chess.WHITE
            else move.to_square + 8
        )

        if (
            changes.get(
                captured,
                0.0
            )
            < CHANGE_THRESHOLD
        ):
            return (
                False,
                "en-passant captured square did not change"
            )

        return (
            True,
            f"transition confirmed {target_change:.3f}"
        )

    if source_change >= SOURCE_CHANGE_THRESHOLD:
        return (
            True,
            (
                f"transition confirmed "
                f"{source_change:.3f}/"
                f"{target_change:.3f}"
            )
        )

    return (
        False,
        "source and destination transition not both detected"
    )


def verify_bot_move(
    sct,
    hwnd,
    board,
    move,
    before_frame,
    board_coords,
    black_perspective
):
    """Fast closed-loop bot verification.

    Uses one cheap whole-board motion map plus exact classification only on
    affected squares. Internal board is not advanced until this succeeds.
    """
    start = time.perf_counter()
    deadline = start + BOT_VERIFY_TIMEOUT
    last_frame = None
    last_reason = "post-move state not yet confirmed"

    while time.perf_counter() < deadline:
        after_frame = capture_screen(sct, hwnd)
        if after_frame is None:
            time.sleep(BOT_RECOVERY_POLL)
            continue

        last_frame = after_frame
        ok, reason = fast_expected_post_state_confirmed(
            before_frame,
            after_frame,
            board,
            move,
            board_coords,
            black_perspective
        )
        if ok:
            # Normal moves use the fast closed-loop screen validation. Because
            # before_frame is a previously verified complete board, the 64-square
            # motion map proves that no unrelated square changed, and exact
            # source/destination classification proves the requested piece moved.
            # Captures/castling/promotion still get the strict full-board check.
            strict_full = (
                board.is_capture(move)
                or board.is_castling(move)
                or move.promotion is not None
            )

            if not strict_full:
                return True, after_frame, reason

            expected_after = expected_board_after_move(
                board,
                move
            )
            full_ok, full_reason = full_board_state_confirmed(
                after_frame,
                expected_after,
                board_coords,
                black_perspective
            )

            if full_ok:
                return True, after_frame, (
                    "scrcpy full-board match 64/64; "
                    + reason
                )

            last_reason = (
                "fast post-state passed but scrcpy full-board rejected: "
                + full_reason
            )
        else:
            last_reason = reason
        time.sleep(BOT_RECOVERY_POLL)

    return False, last_frame, last_reason


def detect_board_orientation(

    grid,
    board
):
    def score(black_perspective):
        detected = grid_to_dict(
            grid,
            black_perspective
        )

        count = 0

        for square in chess.SQUARES:
            expected_piece = board.piece_at(
                square
            )

            expected = (
                expected_piece.symbol()
                if expected_piece
                else None
            )

            if (
                detected.get(square)
                == expected
            ):
                count += 1

        return count

    white_score = score(False)
    black_score = score(True)

    print(
        f"[ORIENTATION] "
        f"White={white_score}/64 "
        f"Black={black_score}/64"
    )

    return (
        black_score
        > white_score
    )


def stable_initial_scan(
    sct,
    hwnd,
    board_coords,
    timeout=ORIENTATION_TIMEOUT
):
    start = time.perf_counter()

    previous = None
    stable = 0
    best_frame = None
    best_grid = None

    while (
        time.perf_counter() - start
        < timeout
    ):
        frame = capture_screen(
            sct,
            hwnd
        )

        if frame is None:
            time.sleep(
                SCAN_INTERVAL
            )

            continue

        grid, _, _ = scan_board(
            frame,
            board_coords
        )

        signature = tuple(
            tuple(row)
            for row in grid
        )

        if signature == previous:
            stable += 1
        else:
            previous = signature
            stable = 1

        best_frame = frame
        best_grid = grid

        if stable >= 2:
            return (
                best_frame,
                best_grid
            )

        time.sleep(
            SCAN_INTERVAL
        )

    return (
        best_frame,
        best_grid
    )


def detect_bottom_stockfish_color(
    black_perspective
):
    return (
        chess.BLACK
        if black_perspective
        else chess.WHITE
    )


def score_to_cp(score):
    if score.is_mate():
        mate = score.mate()

        if mate is None:
            return 0

        return (
            100000
            if mate > 0
            else -100000
        )

    value = score.score(
        mate_score=100000
    )

    return (
        0
        if value is None
        else int(value)
    )


def format_eval(cp):
    if cp >= 100000:
        return "MATE WHITE"

    if cp <= -100000:
        return "MATE BLACK"

    return f"{cp / 100.0:+.2f}"


def favor_text(cp):
    if cp >= 100000:
        return "WHITE MATE"

    if cp <= -100000:
        return "BLACK MATE"

    if abs(cp) <= 8:
        return "EQUAL"

    side = (
        "WHITE"
        if cp > 0
        else "BLACK"
    )

    return (
        f"{side} "
        f"+{abs(cp) / 100.0:.2f}"
    )


def material_value(
    piece_type
):
    return {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
        chess.KING: 0,
    }.get(
        piece_type,
        0
    )


def side_material(
    board,
    color
):
    total = 0

    for square, piece in board.piece_map().items():
        if piece.color == color:
            total += material_value(
                piece.piece_type
            )

    return total


def classify_move_quality(
    before_board,
    after_board,
    move,
    mover_color,
    best_move,
    best_eval_cp,
    after_eval_cp
):
    if move == best_move:
        if (
            before_board.is_castling(move)
            or move.promotion is not None
            or before_board.gives_check(move)
        ):
            return "BEST"

        return "EXCELLENT"

    if best_eval_cp >= 100000:
        if after_eval_cp >= 100000:
            return "BRILLIANT*"

        return "BLUNDER"

    loss = max(
        0,
        best_eval_cp - after_eval_cp
    )

    material_before = side_material(
        before_board,
        mover_color
    )

    material_after = side_material(
        after_board,
        mover_color
    )

    sacrifice = (
        material_after
        < material_before
    )

    if loss <= 10 and sacrifice:
        return "BRILLIANT*"

    if loss <= 10:
        return "EXCELLENT"

    if loss <= 25:
        return "GREAT"
    if loss <= 70:
        return "GOOD"

    if loss <= 150:
        return "INACCURACY"

    if loss <= 300:
        return "MISTAKE"

    return "BLUNDER"


def build_analysis(
    engine,
    before_board,
    after_board,
    move,
    best_info=None
):
    mover_color = before_board.turn

    try:
        if best_info is None:
            best_info = engine.analyse(
                before_board,
                chess.engine.Limit(
                    depth=ANALYSIS_DEPTH,
                    time=ANALYSIS_TIME
                )
            )

        best_score_obj = best_info.get(
            "score"
        )

        if best_score_obj is None:
            return None

        best_score_white = (
            best_score_obj.pov(
                chess.WHITE
            )
        )

        best_eval_cp = score_to_cp(
            best_score_white
        )

        best_move = best_info.get(
            "pv",
            [None]
        )[0]

        after_info = engine.analyse(
            after_board,
            chess.engine.Limit(
                depth=ANALYSIS_DEPTH,
                time=ANALYSIS_TIME
            )
        )

        after_score_obj = after_info.get(
            "score"
        )

        if after_score_obj is None:
            return None

        after_score_white = (
            after_score_obj.pov(
                chess.WHITE
            )
        )

        after_eval_cp = score_to_cp(
            after_score_white
        )

        quality = classify_move_quality(
            before_board,
            after_board,
            move,
            mover_color,
            best_move,
            score_to_cp(
                best_score_obj.pov(
                    mover_color
                )
            ),
            score_to_cp(
                after_score_obj.pov(
                    mover_color
                )
            )
        )

        pv = []
        temp = after_board.copy()

        for pv_move in after_info.get(
            "pv",
            []
        )[:6]:
            if pv_move not in temp.legal_moves:
                break

            pv.append(
                temp.san(
                    pv_move
                )
            )

            temp.push(
                pv_move
            )

        return {
            "eval_cp": after_eval_cp,
            "eval_text": format_eval(
                after_eval_cp
            ),
            "favor": favor_text(
                after_eval_cp
            ),
            "quality": quality,
            "last_move": (
                after_board.peek().uci()
                if after_board.move_stack
                else move.uci()
            ),
            "best_move": (
                best_move.uci()
                if best_move is not None
                else "-"
            ),
            "depth": after_info.get(
                "depth",
                ANALYSIS_DEPTH
            ),
            "pv": (
                " ".join(pv)
                if pv
                else "-"
            )
        }

    except Exception as exc:
        print(
            f"[ANALYSIS ERROR] {exc}"
        )

        return None


# ============================================================
# STOCKFISH MOVE SELECTION: #1 - #8
# ============================================================

def safe_drop_fraction(
    current_cp
):
    current_eval = (
        current_cp / 100.0
    )

    if current_eval < 2.0:
        return 0.10

    if current_eval < 3.0:
        return 0.15

    if current_eval < 4.0:
        return 0.20

    if current_eval < 5.0:
        return 0.25

    return 0.30


def opponent_recent_accuracy(
    match_history
):
    if not match_history:
        return None, 0

    recent = match_history[
        -OPPONENT_ACCURACY_WINDOW:
    ]

    n = len(recent)

    weights = list(
        range(1, n + 1)
    )

    total_weight = float(
        sum(weights)
    )

    weighted = sum(
        score * weight
        for score, weight
        in zip(
            recent,
            weights
        )
    )

    return (
        weighted / total_weight,
        n
    )


def adaptive_accuracy_profile(
    opponent_accuracy,
    sample_count
):
    if (
        opponent_accuracy is None
        or sample_count < OPPONENT_MIN_SAMPLES
    ):
        return {
            "opponent_accuracy": opponent_accuracy,
            "target_accuracy": 88.0,
            "max_rank": 3,
            "max_eval_drop": 0.12,
            "state": (
                f"WARMUP "
                f"{sample_count}/"
                f"{OPPONENT_MIN_SAMPLES}"
            ),
        }

    score = float(
        opponent_accuracy
    )

    target = min(
        ADAPTIVE_MAX_TARGET,
        max(
            ADAPTIVE_MIN_TARGET,
            score + ADAPTIVE_SAFETY_MARGIN
        )
    )

    if score < 70.0:
        max_rank = 4
        max_eval_drop = 0.18
        state = "OPPONENT LIGHT"

    elif score < 80.0:
        max_rank = 3
        max_eval_drop = 0.14
        state = "OPPONENT MEDIUM"

    elif score < 88.0:
        max_rank = 2
        max_eval_drop = 0.10
        state = "OPPONENT STRONG"

    elif score < ADAPTIVE_STRONG_THRESHOLD:
        max_rank = 2
        max_eval_drop = 0.075
        state = "OPPONENT VERY STRONG"

    elif score < ADAPTIVE_VERY_STRONG_THRESHOLD:
        max_rank = 1
        max_eval_drop = 0.050
        state = "OPPONENT ELITE"

    else:
        max_rank = 1
        max_eval_drop = 0.035
        state = "OPPONENT EXTREME"

    return {
        "opponent_accuracy": score,
        "target_accuracy": target,
        "max_rank": max_rank,
        "max_eval_drop": max_eval_drop,
        "state": state,
    }


def choose_stockfish_move(
    board,
    multipv_infos,
    previous_eval_white_cp=None,
    opponent_accuracy=None,
    opponent_sample_count=0,
    opponent_pressure=False
):
    if not multipv_infos:
        return (
            None,
            None,
            {
                "rank": 0,
                "current_cp": 0,
                "selected_cp": 0,
                "reason": "no MultiPV candidates"
            }
        )

    mover = board.turn
    candidates = []

    for rank, info in enumerate(
        multipv_infos[
            :TRAINING_MULTI_PV
        ]
    ):
        pv = info.get(
            "pv",
            []
        )

        if not pv:
            continue

        move = pv[0]

        if move not in board.legal_moves:
            continue

        score_obj = info.get(
            "score"
        )

        if score_obj is None:
            continue

        pov_score = score_obj.pov(
            mover
        )

        cp = pov_score.score(
            mate_score=100000
        )

        if cp is None:
            cp = 0

        candidates.append({
            "rank": rank,
            "move": move,
            "info": info,
            "cp": int(cp),
            "mate": pov_score.mate(),
        })

    if not candidates:
        return (
            None,
            None,
            {
                "rank": 0,
                "current_cp": 0,
                "selected_cp": 0,
                "reason": "no legal MultiPV candidates"
            }
        )

    best = candidates[0]
    best_cp = best["cp"]

    profile = adaptive_accuracy_profile(
        opponent_accuracy,
        opponent_sample_count
    )

    adaptive_max_rank = int(
        profile["max_rank"]
    )

    adaptive_max_drop = float(
        profile["max_eval_drop"]
    )

    reference_cp = None

    if previous_eval_white_cp is not None:
        reference_cp = (
            previous_eval_white_cp
            if mover == chess.WHITE
            else -previous_eval_white_cp
        )

    if (
        reference_cp is not None
        and reference_cp >= FORCE_BEST_MIN_CP
        and not (
            best["mate"] is not None
            and best["mate"] > 0
            and best["mate"] <= MATE_GRACE_MAX
        )
    ):
        improvement_fraction = (
            (
                best_cp
                - reference_cp
            )
            / max(
                1,
                abs(reference_cp)
            )
        )

        if (
            improvement_fraction
            >= FORCE_BEST_IMPROVEMENT_FRACTION
        ):
            selected = best

            return (
                selected["move"],
                selected["info"],
                {
                    "rank": selected["rank"],
                    "current_cp": best_cp,
                    "selected_cp": selected["cp"],
                    "reason": (
                        f"FORCED #1 | "
                        f"reference="
                        f"+{reference_cp/100:.2f} "
                        f"best="
                        f"+{best_cp/100:.2f} "
                        f"improvement="
                        f"{improvement_fraction*100:.0f}%"
                    )
                }
            )

    if (
        best["mate"] is not None
        and best["mate"] > 0
    ):
        global _mate_progress_target_mate, _mate_progress_hold_moves, _mate_progress_hold_limit

        # M4 or closer: stop humanizing and take the fastest mate immediately.
        if best["mate"] <= MATE_FORCE_FAST_MAX:
            _mate_progress_target_mate = None
            _mate_progress_hold_moves = 0
            _mate_progress_hold_limit = MATE_SUSTAIN_MIN_MOVES

            selected = best

            return (
                selected["move"],
                selected["info"],
                {
                    "rank": selected["rank"],
                    "current_cp": best_cp,
                    "selected_cp": selected["cp"],
                    "reason": (
                        f"MATE FORCE | "
                        f"M{selected['mate']} "
                        f"RANK=#"
                        f"{selected['rank'] + 1}"
                    )
                }
            )

        # The human-like mate window remains M5-M15. Outside that window,
        # keep the existing direct #1 behavior.
        if not (
            MATE_GRACE_MIN
            <= best["mate"]
            <= MATE_GRACE_MAX
        ):
            _mate_progress_target_mate = None
            _mate_progress_hold_moves = 0
            _mate_progress_hold_limit = MATE_SUSTAIN_MIN_MOVES

            selected = best

            return (
                selected["move"],
                selected["info"],
                {
                    "rank": selected["rank"],
                    "current_cp": best_cp,
                    "selected_cp": selected["cp"],
                    "reason": (
                        f"MATE #1 | "
                        f"M{selected['mate']} "
                        f"RANK=#"
                        f"{selected['rank'] + 1}"
                    )
                }
            )

        # Start/recover the sustained mate target. The target represents the
        # mate level the bot is currently willing to play around. It can move
        # faster only one step at a time; it may move slower when the actual
        # engine mate itself has become slower because the opponent defended.
        if _mate_progress_target_mate is None:
            _mate_progress_target_mate = best["mate"]
            _mate_progress_hold_moves = 0
            _mate_progress_hold_limit = random.randint(
                MATE_SUSTAIN_MIN_MOVES,
                MATE_SUSTAIN_MAX_MOVES
            )
        elif best["mate"] > _mate_progress_target_mate:
            _mate_progress_target_mate = best["mate"]
            _mate_progress_hold_moves = 0
            _mate_progress_hold_limit = random.randint(
                MATE_SUSTAIN_MIN_MOVES,
                MATE_SUSTAIN_MAX_MOVES
            )
        elif best["mate"] < _mate_progress_target_mate:
            # Do not follow M10 -> M9 -> M8 immediately. Hold the current
            # target for a few moves first, then improve it by exactly one.
            _mate_progress_hold_moves += 1

            if (
                _mate_progress_hold_moves
                >= _mate_progress_hold_limit
            ):
                _mate_progress_target_mate = max(
                    MATE_GRACE_MIN,
                    _mate_progress_target_mate - 1
                )
                _mate_progress_hold_moves = 0
                _mate_progress_hold_limit = random.randint(
                    MATE_SUSTAIN_MIN_MOVES,
                    MATE_SUSTAIN_MAX_MOVES
                )

        target_mate = int(
            _mate_progress_target_mate
        )

        # Never jump multiple mate steps in a single decision. The active
        # target is the anchor; one slower line is allowed to preserve a
        # natural sustain feel, but it cannot become an accumulating +5 cap.
        allowed_mate_max = target_mate + 1

        mate_candidates = [
            c
            for c in candidates
            if (
                c["mate"] is not None
                and c["mate"] > 0
                and target_mate
                <= c["mate"]
                <= allowed_mate_max
            )
        ]

        # If the engine's current best mate is already faster than the target
        # but no exact target line exists, allow the current best only when
        # the target has caught up to that one-step improvement. Otherwise
        # keep the slower candidate to sustain the plan.
        if not mate_candidates:
            exact_best = [
                c
                for c in candidates
                if (
                    c["mate"] is not None
                    and c["mate"] == best["mate"]
                )
            ]

            if exact_best:
                selected = max(
                    exact_best,
                    key=lambda c: c["rank"]
                )

                return (
                    selected["move"],
                    selected["info"],
                    {
                        "rank": selected["rank"],
                        "current_cp": best_cp,
                        "selected_cp": selected["cp"],
                        "reason": (
                            f"MATE ADAPT | "
                            f"TARGET=M{target_mate} "
                            f"BEST=M{best['mate']} "
                            f"SELECTED=M{selected['mate']} "
                            f"RANK=#"
                            f"{selected['rank'] + 1}"
                        )
                    }
                )

            selected = best

            return (
                selected["move"],
                selected["info"],
                {
                    "rank": selected["rank"],
                    "current_cp": best_cp,
                    "selected_cp": selected["cp"],
                    "reason": (
                        f"MATE BEST | "
                        f"TARGET=M{target_mate} "
                        f"BEST=M{best['mate']} "
                        f"RANK=#"
                        f"{selected['rank'] + 1}"
                    )
                }
            )

        exact_target = [
            c
            for c in mate_candidates
            if c["mate"] == target_mate
        ]

        slower_target = [
            c
            for c in mate_candidates
            if c["mate"] == allowed_mate_max
        ]

        if exact_target:
            # Same mate distance: keep the earlier rule—take the lowest
            # MultiPV line, e.g. #1 M6/#2 M6/#3 M6 -> #3.
            selected = max(
                exact_target,
                key=lambda c: c["rank"]
            )

            # Occasionally sustain with the one-step slower mate when it is
            # available, but never jump several mate moves at once.
            if (
                slower_target
                and random.random() < MATE_SLOWER_LINE_CHANCE
            ):
                selected = max(
                    slower_target,
                    key=lambda c: c["rank"]
                )
        else:
            selected = max(
                slower_target,
                key=lambda c: c["rank"]
            )

        return (
            selected["move"],
            selected["info"],
            {
                "rank": selected["rank"],
                "current_cp": best_cp,
                "selected_cp": selected["cp"],
                "reason": (
                    f"MATE SUSTAIN | "
                    f"TARGET=M{target_mate} "
                    f"BEST=M{best['mate']} "
                    f"SELECTED=M{selected['mate']} "
                    f"HOLD={_mate_progress_hold_moves}/"
                    f"{_mate_progress_hold_limit} "
                    f"RANK=#"
                    f"{selected['rank'] + 1}"
                )
            }
        )

    if best_cp > MIN_POSITIVE_CP:
        normal_max_drop = safe_drop_fraction(
            best_cp
        )

        max_drop = min(
            normal_max_drop,
            adaptive_max_drop
        )

        floor_cp = max(
            5,
            int(
                best_cp
                * (
                    1.0
                    - max_drop
                )
            )
        )

        global _advantage_progress_target_cp
        global _advantage_progress_hold_moves
        global _advantage_progress_hold_limit
        global _advantage_progress_side

        advantage_mode = False
        advantage_maintain = False
        advantage_growth = False
        advantage_target_cp = None

        if best_cp < HUMAN_ADVANTAGE_START_CP:
            _advantage_progress_target_cp = None
            _advantage_progress_hold_moves = 0
            _advantage_progress_hold_limit = random.randint(
                HUMAN_ADVANTAGE_HOLD_MIN_MOVES,
                HUMAN_ADVANTAGE_HOLD_MAX_MOVES
            )
            _advantage_progress_side = None

        else:
            if _advantage_progress_side != mover:
                _advantage_progress_target_cp = None
                _advantage_progress_hold_moves = 0
                _advantage_progress_hold_limit = random.randint(
                    HUMAN_ADVANTAGE_HOLD_MIN_MOVES,
                    HUMAN_ADVANTAGE_HOLD_MAX_MOVES
                )
                _advantage_progress_side = mover

            if _advantage_progress_target_cp is None:
                _advantage_progress_target_cp = best_cp
                _advantage_progress_hold_moves = 0
                _advantage_progress_hold_limit = random.randint(
                    HUMAN_ADVANTAGE_HOLD_MIN_MOVES,
                    HUMAN_ADVANTAGE_HOLD_MAX_MOVES
                )

            # Do not lower the stored winning target for a small evaluation
            # fluctuation. Only reset it when the engine's best itself has
            # fallen materially below the protected winning level.
            if (
                best_cp
                < _advantage_progress_target_cp
                - HUMAN_ADVANTAGE_PROTECT_BAND_CP
            ):
                _advantage_progress_target_cp = best_cp
                _advantage_progress_hold_moves = 0

            advantage_target_cp = int(
                _advantage_progress_target_cp
            )

            advantage_mode = True

            # Every few actual Stockfish moves, make a progress move. This is
            # independent of whether the evaluation changed on the previous
            # move, so the bot cannot sit on +6.0 for dozens of moves simply
            # because the short engine scores happen to repeat.
            _advantage_progress_hold_moves += 1

            progress_due = (
                _advantage_progress_hold_moves
                >= _advantage_progress_hold_limit
                or
                best_cp
                >= advantage_target_cp
                + HUMAN_ADVANTAGE_GROWTH_TRIGGER_CP
                or
                opponent_pressure
            )

            if progress_due:
                # If the position genuinely improved, advance only a small
                # step toward the new best instead of jumping straight there.
                if best_cp > advantage_target_cp + 10:
                    growth_step = random.randint(
                        HUMAN_ADVANTAGE_GROWTH_STEP_MIN_CP,
                        HUMAN_ADVANTAGE_GROWTH_STEP_MAX_CP
                    )

                    _advantage_progress_target_cp = min(
                        best_cp,
                        advantage_target_cp + growth_step
                    )
                    advantage_target_cp = int(
                        _advantage_progress_target_cp
                    )
                    advantage_growth = True

                else:
                    # Even without a visible CP jump, deliberately use a
                    # stronger move from the current safe top end so the game
                    # keeps developing instead of repeating a passive hold.
                    advantage_growth = True

                _advantage_progress_hold_moves = 0
                _advantage_progress_hold_limit = random.randint(
                    HUMAN_ADVANTAGE_HOLD_MIN_MOVES,
                    HUMAN_ADVANTAGE_HOLD_MAX_MOVES
                )
            else:
                advantage_maintain = True

            # Protect the current winning advantage. +6 should not casually
            # fall toward +4 just because a lower MultiPV move exists.
            floor_cp = max(
                floor_cp,
                int(
                    advantage_target_cp
                    - HUMAN_ADVANTAGE_PROTECT_BAND_CP
                )
            )
        safe = [
            c
            for c in candidates
            if (
                c["cp"] >= floor_cp
                and c["cp"] > 0
                and c["rank"] <= adaptive_max_rank
            )
        ]

        if not safe:
            safe = [best]

        non_best = [
            c
            for c in safe
            if c["rank"] > 0
        ]

        if (
            len(non_best) >= 2
            and random.random() < 0.72
        ):
            pool = non_best
        else:
            pool = safe

        roll = random.random()

        if roll < 0.45:
            target_drop = random.uniform(
                0.00,
                max_drop * 0.35
            )

        elif roll < 0.78:
            target_drop = random.uniform(
                max_drop * 0.35,
                max_drop * 0.70
            )

        elif roll < 0.95:
            target_drop = random.uniform(
                max_drop * 0.70,
                max_drop * 0.90
            )

        else:
            target_drop = random.uniform(
                max_drop * 0.90,
                max_drop
            )

        desired_cp = max(
            floor_cp,
            int(
                best_cp
                * (
                    1.0
                    - target_drop
                )
            )
        )

        if advantage_mode:
            if advantage_maintain:
                desired_cp = min(
                    best_cp,
                    max(
                        floor_cp,
                        int(
                            advantage_target_cp
                            + random.uniform(
                                -HUMAN_ADVANTAGE_MAINTAIN_BAND_CP * 0.20,
                                HUMAN_ADVANTAGE_MAINTAIN_BAND_CP * 0.20
                            )
                        )
                    )
                )
            else:
                desired_cp = min(
                    best_cp,
                    max(
                        floor_cp,
                        int(
                            advantage_target_cp
                        )
                    )
                )

        if advantage_mode:
            if advantage_growth:
                # Progress move: prefer the strongest few safe continuations.
                # This is what keeps a +6 position actively developing even
                # when the short evaluation does not move on every turn.
                progress_pool = [
                    c
                    for c in safe
                    if c["cp"] >= max(
                        floor_cp,
                        advantage_target_cp,
                        best_cp - 25                    )
                ]

                if progress_pool:
                    pool = progress_pool
                else:
                    pool = safe
            else:
                maintain_min = max(
                    floor_cp,
                    int(
                        advantage_target_cp
                        - HUMAN_ADVANTAGE_MAINTAIN_BAND_CP
                    )
                )

                maintain_pool = [
                    c
                    for c in safe
                    if (
                        c["cp"] >= maintain_min
                        and c["cp"] <= best_cp
                    )
                ]

                if maintain_pool:
                    pool = maintain_pool

        if advantage_mode and advantage_growth:
            rank_factors = {
                0: 4.50,
                1: 2.35,
                2: 1.55,
                3: 1.05,
                4: 0.70,
                5: 0.50,
                6: 0.35,
                7: 0.25,
            }
        else:
            rank_factors = {
                0: 0.95,
                1: 1.20,
                2: 1.25,
                3: 1.15,
                4: 1.00,
                5: 0.85,
                6: 0.70,
                7: 0.55,
            }

        weighted = []

        for candidate in pool:
            distance = abs(
                candidate["cp"]
                - desired_cp
            )

            weight = (
                1.0
                / (
                    1.0
                    + distance / 35.0
                )
            )

            weight *= (
                rank_factors.get(
                    candidate["rank"],
                    0.45
                )
            )

            weighted.append(
                (
                    candidate,
                    max(
                        0.01,
                        weight
                    )
                )
            )

        total = sum(
            weight
            for _, weight
            in weighted
        )

        pick = random.uniform(
            0,
            total
        )

        running = 0.0
        selected = weighted[0][0]

        for candidate, weight in weighted:
            running += weight

            if pick <= running:
                selected = candidate
                break

        return (
            selected["move"],
            selected["info"],
            {
                "rank": selected["rank"],
                "current_cp": best_cp,
                "selected_cp": selected["cp"],
                "reason": (
                    (
                        "advantage growth"
                        if advantage_mode and advantage_growth
                        else "advantage maintain"
                        if advantage_mode
                        else "controlled shuffle"
                    )
                    + " | "
                    + f"BEST={best_cp/100:+.2f} "
                    + f"SELECTED={selected['cp']/100:+.2f} "
                    + f"RANK=#{selected['rank'] + 1} "
                    + f"FLOOR={floor_cp/100:+.2f} "
                    + f"MAX_DROP={max_drop*100:.1f}% "
                    + f"OPP="
                    f"{profile['opponent_accuracy'] if profile['opponent_accuracy'] is not None else 0.0:.1f}% "
                    f"TARGET="
                    f"{profile['target_accuracy']:.1f}% "
                    f"RANKCAP=#"
                    f"{adaptive_max_rank + 1}"
                )
            }
        )

    near_equal_floor = (
        best_cp - 20
    )

    safe = [
        c
        for c in candidates
        if (
            c["cp"] >= near_equal_floor
            and c["rank"] <= adaptive_max_rank
        )
    ]

    if not safe:
        safe = [best]

    rank_weights = {
        0: 5.0,
        1: 3.8,
        2: 3.2,
        3: 2.4,
        4: 1.8,
        5: 1.2,
        6: 0.8,
        7: 0.5,
    }

    weighted = []

    for candidate in safe:
        weighted.append(
            (
                candidate,
                rank_weights.get(
                    candidate["rank"],
                    0.3
                )
            )
        )

    total = sum(
        weight
        for _, weight
        in weighted
    )

    pick = random.uniform(
        0,
        total
    )

    running = 0.0
    selected = weighted[0][0]

    for candidate, weight in weighted:
        running += weight

        if pick <= running:
            selected = candidate
            break

    return (
        selected["move"],
        selected["info"],
        {
            "rank": selected["rank"],
            "current_cp": best_cp,
            "selected_cp": selected["cp"],
            "reason": (
                f"near-equal shuffle | "
                f"BEST="
                f"{best_cp/100:+.2f} "
                f"SELECTED="
                f"{selected['cp']/100:+.2f} "
                f"RANK=#"
                f"{selected['rank'] + 1}"
            )
        }
    )


def draw_overlay(
    display_frame,
    board_coords,
    grid,
    locked,
    black_perspective,
    scan_ms,
    status,
    stockfish_color,
    human_color,
    analysis_state=None
):
    x, y, w, h = board_coords

    sq_w = w / 8.0
    sq_h = h / 8.0

    grid_color = (
        (0, 255, 0)
        if locked
        else (0, 255, 255)
    )

    cv2.rectangle(
        display_frame,
        (x, y),
        (x + w, y + h),
        grid_color,
        2
    )

    for i in range(1, 8):
        cv2.line(
            display_frame,
            (
                x,
                y + int(i * sq_h)
            ),
            (
                x + w,
                y + int(i * sq_h)
            ),
            grid_color,
            1
        )

        cv2.line(
            display_frame,
            (
                x + int(i * sq_w),
                y
            ),
            (
                x + int(i * sq_w),
                y + h
            ),
            grid_color,
            1
        )

    if grid is not None:
        for row in range(8):
            for col in range(8):
                symbol = grid[row][col]

                if not symbol:
                    continue

                fx1 = int(
                    x + col * sq_w
                )

                fy1 = int(
                    y + row * sq_h
                )

                color = (
                    (0, 255, 255)
                    if symbol.isupper()
                    else (0, 0, 255)
                )

                cv2.putText(
                    display_frame,
                    symbol,
                    (
                        fx1
                        + int(sq_w / 3),
                        fy1
                        + int(sq_h / 1.5)
                    ),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.70,
                    color,
                    2
                )

    cv2.rectangle(
        display_frame,
        (0, 0),
        (
            display_frame.shape[1],
            48
        ),
        (0, 0, 0),
        -1
    )

    cv2.putText(
        display_frame,
        status,
        (8, 18),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (0, 255, 255),
        1
    )

    if analysis_state is not None:
        panel_bottom = max(
            52,
            y - 4
        )

        panel_top = max(
            46,
            panel_bottom - 58
        )

        cv2.rectangle(
            display_frame,
            (0, panel_top),
            (
                display_frame.shape[1],
                panel_bottom
            ),
            (15, 15, 15),
            -1
        )

        eval_text = analysis_state.get(
            "eval_text",
            "--"
        )

        favor = analysis_state.get(
            "favor",
            "--"
        )

        quality = analysis_state.get(
            "quality",
            "--"
        )

        last_move = analysis_state.get(
            "last_move",
            "--"
        )

        best_move = analysis_state.get(
            "best_move",
            "--"
        )

        depth = analysis_state.get(
            "depth",
            "--"
        )

        pv = analysis_state.get(
            "pv",
            "--"
        )

        line1 = (
            f"EVAL {eval_text}   "
            f"FAVOR {favor}"
        )

        line2 = (
            f"LAST {last_move}   "
            f"QUALITY {quality}   "
            f"DEPTH {depth}"
        )

        line3 = (
            f"BEST {best_move}   "
            f"LINE (NOT PLAYED) {pv}"
        )

        cv2.putText(
            display_frame,
            line1,
            (
                8,
                panel_top + 17
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (255, 255, 255),
            1
        )

        cv2.putText(
            display_frame,
            line2,
            (
                8,
                panel_top + 35
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            (0, 255, 255),
            1
        )

        cv2.putText(
            display_frame,
            line3,
            (
                8,
                panel_top + 52
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.34,
            (220, 220, 220),
            1
        )

    bottom_color = (
        "BLACK"
        if stockfish_color == chess.BLACK
        else "WHITE"
    )

    top_color = (
        "BLACK"
        if human_color == chess.BLACK
        else "WHITE"
    )

    cv2.putText(
        display_frame,
        (
            f"TOP:{top_color} HUMAN  "
            f"BOTTOM:{bottom_color} STOCKFISH"
        ),
        (8, 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.40,
        (255, 255, 255),
        1
    )


def format_board_for_screen(
    board,
    black_perspective
):
    lines = []

    if black_perspective:
        ranks = range(0, 8)
        files = range(7, -1, -1)
    else:
        ranks = range(7, -1, -1)
        files = range(0, 8)

    for rank in ranks:
        row = []

        for file_ in files:
            piece = board.piece_at(
                chess.square(
                    file_,
                    rank
                )
            )

            row.append(
                piece.symbol()
                if piece
                else "."
            )

        lines.append(
            " ".join(row)
        )

    return "\n".join(lines)


def format_move_history(
    board
):
    temp = chess.Board(
        INITIAL_FEN
    )

    moves = []
    move_number = 1

    for idx, move in enumerate(
        board.move_stack
    ):
        if temp.turn == chess.WHITE:
            san = temp.san(
                move
            )

            moves.append(
                f"{move_number}. {san}"
            )

        else:
            san = temp.san(
                move
            )

            if moves:
                moves[-1] += (
                    f" {san}"
                )
            else:
                moves.append(
                    f"{move_number}... {san}"
                )

            move_number += 1

        temp.push(
            move
        )

    return (
        " ".join(moves)
        if moves
        else "-"
    )


def print_game_state(
    board,
    stockfish_color,
    human_color,
    black_perspective,
    message="",
    analysis_state=None
):
    os.system(
        "cls"
        if os.name == "nt"
        else "clear"
    )

    print(
        "============================================================"
    )

    print(
        "             LOCAL CHESS - HUMAN vs STOCKFISH"
    )

    print(
        "============================================================"
    )

    print(
        f"Stockfish: "
        f"{'WHITE' if stockfish_color == chess.WHITE else 'BLACK'}"
        f" | Human: "
        f"{'WHITE' if human_color == chess.WHITE else 'BLACK'}"
    )

    if message:
        print(
            f"\n{message}\n"
        )

    turn_text = (
        "WHITE"
        if board.turn == chess.WHITE
        else "BLACK"
    )

    controller = (
        "STOCKFISH"
        if board.turn == stockfish_color
        else "HUMAN"
    )

    print(
        f"Turn: {turn_text} / {controller}"
    )

    if SHOW_TERMINAL_FEN:
        print(
            f"FEN: {board.fen()}"
        )

    if analysis_state is not None:
        print(
            "\n[ANALYSIS]"
        )

        print(
            f"EVAL: "
            f"{analysis_state.get('eval_text', '--')} "
            f"| FAVOR: "
            f"{analysis_state.get('favor', '--')} "
            f"| QUALITY: "
            f"{analysis_state.get('quality', '--')}"
        )

        print(
            f"LAST: "
            f"{analysis_state.get('last_move', '--')} "
            f"| BEST: "
            f"{analysis_state.get('best_move', '--')} "
            f"| DEPTH: "
            f"{analysis_state.get('depth', '--')}"
        )

        print(
            "ENGINE LINE (PREDICTION): "
            f"{analysis_state.get('pv', '--')}"
        )

    print(
        f"\n[MOVES] "
        f"{format_move_history(board)}"
    )

    if SHOW_TERMINAL_BOARD:
        print(
            "\n[VERIFIED BOARD]"
        )

        print(
            format_board_for_screen(
                board,
                black_perspective
            )
        )

    print()


def detect_existing_white_first_move(
    frame,
    board,
    board_coords,
    black_perspective
):
    if (
        frame is None
        or board.turn != chess.WHITE
        or board.move_stack
    ):
        return None

    grid, confidence, _ = scan_board(
        frame,
        board_coords
    )

    candidates = []

    for move in board.legal_moves:
        hypothesis = board_hypothesis_score(
            board,
            move,
            grid,
            confidence,
            black_perspective
        )
        candidates.append((
            hypothesis["normalized"],
            move
        ))

    if not candidates:
        return None

    candidates.sort(
        reverse=True,
        key=lambda item: item[0]
    )

    best_score, best_move = candidates[0]
    second_score = (
        candidates[1][0]
        if len(candidates) > 1
        else -999.0
    )

    if (
        best_score < 0.90
        or best_score - second_score < 0.020
    ):
        return None

    templates = get_scaled_templates(
        board_coords[2] / 8.0,
        board_coords[3] / 8.0
    )

    direct_ok, _ = human_direct_state_confirmed(
        frame,
        board,
        best_move,
        board_coords,
        black_perspective,
        templates
    )

    if not direct_ok:
        return None

    expected_board = expected_board_after_move(
        board,
        best_move
    )

    full_ok, _ = full_board_state_confirmed(
        frame,
        expected_board,
        board_coords,
        black_perspective
    )

    return best_move if full_ok else None


def main():
    global _advantage_progress_target_cp
    global _advantage_progress_hold_moves
    global _advantage_progress_hold_limit
    global _advantage_progress_side
    print(
        "============================================================"
    )

    print(
        "        CHESS VISION - HUMAN vs STOCKFISH"
    )

    print(
        "============================================================"
    )

    print(
        "R = initialize board"
    )

    print(
        "L = lock / unlock grid"
    )

    print(
        "W/A/S/D = move grid"
    )

    print(
        "+/- = resize grid"
    )

    print(
        "F = detect bottom side again"
    )

    print(
        "Q = quit"
    )

    print(
        "First chess move is always WHITE."
    )

    print(
        "The color physically at the BOTTOM is always STOCKFISH."
    )

    print(
        "============================================================"
    )

    if not load_assets():
        return

    if not os.path.exists(
        STOCKFISH_PATH
    ):
        print(
            "[ERROR] Stockfish executable not found: "
            f"{STOCKFISH_PATH}"
        )

        return

    try:
        engine = chess.engine.SimpleEngine.popen_uci(
            STOCKFISH_PATH
        )

        engine.configure({
            "Threads": 2,
            "Hash": 128
        })

    except Exception as e:
        print(
            f"[ERROR] Could not start Stockfish: {e}"
        )

        return

    try:
        board = chess.Board(
            INITIAL_FEN
        )

    except Exception as e:
        print(
            f"[ERROR] Invalid initial FEN: {e}"
        )

        engine.quit()

        return

    scrcpy_hwnd = None
    cached_board_coords = None
    cached_board_grid = None
    baseline_frame = None
    grid_locked = False
    game_ready = False
    bot_thinking = False
    last_scan_time_ms = 0.0
    last_bot_position_key = None
    pending_bot_moves = {}
    pending_recovered_human = None
    next_main_turn_rescan = time.perf_counter() + TURN_RESCAN_INTERVAL
    visual_black_perspective = False
    stockfish_color = None
    human_color = None
    status = "READY - PRESS R"
    analysis_state = None
    last_wait_status = ""
    last_wait_report = 0.0

    stockfish_moves_since_buffer = 0

    next_buffer_after = random.randint(
        RANDOM_BUFFER_MOVE_MIN,
        RANDOM_BUFFER_MOVE_MAX
    )

    opponent_match_history = []
    next_human_best_uci = None
    opponent_pressure = False

    with mss.mss() as sct:
        try:
            while True:
                key = cv2.waitKey(
                    1
                ) & 0xFF

                if key == ord("q"):
                    break

                if (
                    not scrcpy_hwnd
                    or not user32.IsWindow(
                        scrcpy_hwnd
                    )
                ):
                    scrcpy_hwnd = find_scrcpy_window()

                frame = capture_screen(
                    sct,                    scrcpy_hwnd
                )

                if frame is None:
                    time.sleep(
                        0.02
                    )
                    continue

                display_frame = frame.copy()

                if key == ord("r"):
                    height, width = frame.shape[:2]

                    board_size = (
                        min(
                            width,
                            height
                        )
                        - 40
                    )

                    start_x = (
                        width
                        - board_size
                    ) // 2

                    start_y = (
                        height
                        - board_size
                    ) // 2

                    cached_board_coords = [
                        start_x,
                        start_y,
                        board_size,
                        board_size
                    ]

                    clear_runtime_caches()

                    grid_locked = False
                    game_ready = False
                    baseline_frame = None
                    analysis_state = None

                    opponent_match_history.clear()

                    next_human_best_uci = None
                    opponent_pressure = False
                    _advantage_progress_target_cp = None
                    _advantage_progress_hold_moves = 0
                    _advantage_progress_hold_limit = random.randint(
                        HUMAN_ADVANTAGE_HOLD_MIN_MOVES,
                        HUMAN_ADVANTAGE_HOLD_MAX_MOVES
                    )
                    _advantage_progress_side = None

                    status = (
                        "UNLOCKED - "
                        "ADJUST GRID, THEN PRESS L"
                    )

                    print(
                        "\n[INFO] Grid initialized."
                    )

                    print(
                        "[INFO] Adjust W/A/S/D/+/-"
                    )

                    print(
                        "[INFO] Press L when correct."
                    )

                if (
                    cached_board_coords
                    and not grid_locked
                ):
                    step = 2

                    if key == ord("w"):
                        cached_board_coords[1] -= step

                    elif key == ord("s"):
                        cached_board_coords[1] += step

                    elif key == ord("a"):
                        cached_board_coords[0] -= step

                    elif key == ord("d"):
                        cached_board_coords[0] += step

                    elif key in (
                        ord("="),
                        ord("+")
                    ):
                        cached_board_coords[2] += step
                        cached_board_coords[3] += step

                    elif key in (
                        ord("-"),
                        ord("_")
                    ):
                        cached_board_coords[2] -= step
                        cached_board_coords[3] -= step

                if (
                    key == ord("l")
                    and cached_board_coords
                ):
                    grid_locked = not grid_locked

                    if grid_locked:
                        clear_runtime_caches()

                        (
                            locked_frame,
                            locked_grid
                        ) = stable_initial_scan(
                            sct,
                            scrcpy_hwnd,
                            cached_board_coords
                        )

                        if (
                            locked_frame is None
                            or locked_grid is None
                        ):
                            grid_locked = False
                            game_ready = False

                            print(
                                "[ERROR] Could not scan board."
                            )

                        else:
                            visual_black_perspective = (
                                detect_board_orientation(
                                    locked_grid,
                                    board
                                )
                            )

                            stockfish_color = (
                                detect_bottom_stockfish_color(
                                    visual_black_perspective
                                )
                            )

                            human_color = (
                                chess.BLACK
                                if stockfish_color == chess.WHITE
                                else chess.WHITE
                            )

                            cached_board_grid = locked_grid
                            baseline_frame = locked_frame

                            if human_color == chess.WHITE:
                                first_move = detect_existing_white_first_move(
                                    locked_frame,
                                    board,
                                    cached_board_coords,
                                    visual_black_perspective
                                )

                                if first_move is not None:
                                    expected_first_board = expected_board_after_move(
                                        board,
                                        first_move
                                    )

                                    (
                                        first_ok,
                                        first_verified_frame,
                                        first_reason
                                    ) = verify_human_move_on_screen(
                                        sct,
                                        scrcpy_hwnd,
                                        expected_first_board,
                                        locked_frame,
                                        cached_board_coords,
                                        visual_black_perspective,
                                        first_move,
                                        board.copy(stack=False)
                                    )

                                    if first_ok:
                                        san = board.san(first_move)
                                        board.push(first_move)
                                        baseline_frame = (
                                            first_verified_frame
                                            if first_verified_frame is not None
                                            else locked_frame
                                        )
                                        print(
                                            f"[SYNC] White-human first move detected: {first_move.uci()}"
                                        )
                                        print(
                                            f"[SYNC] Board advanced to: {san}"
                                        )
                                        print(
                                            f"[SYNC] Physical board verified: {first_reason}"
                                        )
                                        print(
                                            f"[SYNC] Turn = {'BLACK' if board.turn == chess.BLACK else 'WHITE'} / "
                                            f"{'STOCKFISH' if board.turn == stockfish_color else 'HUMAN'}"
                                        )
                                    else:
                                        print(
                                            f"[SYNC] First move rejected; internal board NOT advanced: {first_move.uci()} | {first_reason}"
                                        )

                            game_ready = True
                            analysis_state = None

                            opponent_match_history.clear()
                            next_human_best_uci = None
                            opponent_pressure = False
                            _advantage_progress_target_cp = None
                            _advantage_progress_hold_moves = 0
                            _advantage_progress_hold_limit = random.randint(
                                HUMAN_ADVANTAGE_HOLD_MIN_MOVES,
                                HUMAN_ADVANTAGE_HOLD_MAX_MOVES
                            )
                            _advantage_progress_side = None
                            last_bot_position_key = None
                            pending_bot_moves.clear()

                            stockfish_moves_since_buffer = 0

                            next_buffer_after = random.randint(
                                RANDOM_BUFFER_MOVE_MIN,
                                RANDOM_BUFFER_MOVE_MAX
                            )

                            print(
                                "[INFO] Bottom side:",
                                (
                                    "BLACK"
                                    if stockfish_color == chess.BLACK
                                    else "WHITE"
                                )
                            )

                            print(
                                "[INFO] Stockfish:",
                                (
                                    "BLACK"
                                    if stockfish_color == chess.BLACK
                                    else "WHITE"
                                )
                            )

                            print(
                                "[INFO] Human:",
                                (
                                    "BLACK"
                                    if human_color == chess.BLACK
                                    else "WHITE"
                                )
                            )

                            print(
                                "[INFO] First move is WHITE."
                            )

                            print(
                                "[INFO] Game READY."
                            )

                    else:
                        game_ready = False
                        baseline_frame = None

                        clear_runtime_caches()

                        print(
                            "[INFO] Grid UNLOCKED."
                        )

                if (
                    key == ord("f")
                    and cached_board_coords
                ):
                    clear_runtime_caches()

                    (
                        fresh_frame,
                        fresh_grid
                    ) = stable_initial_scan(
                        sct,
                        scrcpy_hwnd,
                        cached_board_coords
                    )

                    if (
                        fresh_frame is not None
                        and fresh_grid is not None
                    ):
                        visual_black_perspective = (
                            detect_board_orientation(
                                fresh_grid,
                                board
                            )
                        )

                        stockfish_color = (
                            detect_bottom_stockfish_color(
                                visual_black_perspective
                            )
                        )

                        human_color = (
                            chess.BLACK
                            if stockfish_color == chess.WHITE
                            else chess.WHITE
                        )

                        cached_board_grid = fresh_grid
                        baseline_frame = fresh_frame

                        if human_color == chess.WHITE:
                            first_move = detect_existing_white_first_move(
                                fresh_frame,
                                board,
                                cached_board_coords,
                                visual_black_perspective
                            )

                            if first_move is not None:
                                expected_first_board = expected_board_after_move(
                                    board,
                                    first_move
                                )

                                (
                                    first_ok,
                                    first_verified_frame,
                                    first_reason
                                ) = verify_human_move_on_screen(
                                    sct,
                                    scrcpy_hwnd,
                                    expected_first_board,
                                    fresh_frame,
                                    cached_board_coords,
                                    visual_black_perspective,
                                    first_move,
                                    board.copy(stack=False)
                                )

                                if first_ok:
                                    san = board.san(first_move)
                                    board.push(first_move)
                                    baseline_frame = (
                                        first_verified_frame
                                        if first_verified_frame is not None
                                        else fresh_frame
                                    )
                                    print(
                                        f"[SYNC] White-human first move detected: {first_move.uci()}"
                                    )
                                    print(
                                        f"[SYNC] Board advanced to: {san}"
                                    )
                                    print(
                                        f"[SYNC] Physical board verified: {first_reason}"
                                    )
                                    print(
                                        f"[SYNC] Turn = {'BLACK' if board.turn == chess.BLACK else 'WHITE'} / "
                                        f"{'STOCKFISH' if board.turn == stockfish_color else 'HUMAN'}"
                                    )
                                else:
                                    print(
                                        f"[SYNC] First move rejected; internal board NOT advanced: {first_move.uci()} | {first_reason}"
                                    )

                        opponent_match_history.clear()
                        next_human_best_uci = None
                        last_bot_position_key = None
                        pending_bot_moves.clear()

                        stockfish_moves_since_buffer = 0

                        next_buffer_after = random.randint(
                            RANDOM_BUFFER_MOVE_MIN,
                            RANDOM_BUFFER_MOVE_MAX
                        )

                        game_ready = True

                        print(
                            "[INFO] Bottom side:",
                            (
                                "BLACK"
                                if stockfish_color == chess.BLACK
                                else "WHITE"
                            )
                        )

                        print(
                            "[INFO] Stockfish:",
                            (
                                "BLACK"
                                if stockfish_color == chess.BLACK
                                else "WHITE"
                            )
                        )

                        print(
                            "[INFO] Human:",
                            (
                                "BLACK"
                                if human_color == chess.BLACK
                                else "WHITE"
                            )
                        )

                status = "READY - PRESS R"

                if (
                    grid_locked
                    and cached_board_coords
                ):
                    if (
                        not game_ready
                        or stockfish_color is None
                    ):
                        status = (
                            "DETECT BOTTOM SIDE"
                        )

                    elif bot_thinking:
                        status = (
                            "STOCKFISH THINKING..."
                        )

                    elif (
                        board.turn
                        == stockfish_color
                    ):
                        status = (
                            "STOCKFISH TO MOVE | "
                            f"SCAN "
                            f"{last_scan_time_ms:.1f}ms"
                        )

                    else:
                        status = (
                            "WAITING HUMAN MOVE | "
                            f"SCAN "
                            f"{last_scan_time_ms:.1f}ms"
                        )

                if (
                    game_ready
                    and grid_locked
                    and stockfish_color is not None
                ):
                    if (
                        board.turn == human_color
                        and not bot_thinking
                    ):
                        progress(
                            "WAIT",
                            (
                                f"human "
                                f"{'WHITE' if human_color == chess.WHITE else 'BLACK'} "
                                "to move; scanning screen"
                            ),
                            key="turn_wait",
                            force=True
                        )

                        detection_source = None

                        if pending_recovered_human is not None:
                            move, move_frame = pending_recovered_human
                            pending_recovered_human = None
                            detection_source = "PERIODIC_FULL_RESCAN"
                            detect_human_move._last_detection_source = detection_source
                            print(
                                f"[RECOVERY] Consuming already-verified human move: {move.uci()}"
                            )
                        else:
                            (
                                move,
                                move_frame
                            ) = detect_human_move(
                                sct,
                                scrcpy_hwnd,
                                board,
                                baseline_frame,
                                cached_board_coords,
                                visual_black_perspective
                            )

                        if (
                            move is not None
                            and move_frame is not None
                        ):
                            san = board.san(
                                move
                            )

                            expected_human_uci = (
                                next_human_best_uci
                            )
                            opponent_pressure = False

                            if expected_human_uci:
                                exact_top_match = (
                                    100.0
                                    if move.uci()
                                    == expected_human_uci
                                    else 0.0
                                )

                                opponent_match_history.append(
                                    exact_top_match
                                )

                                (
                                    recent_accuracy,
                                    sample_count
                                ) = opponent_recent_accuracy(
                                    opponent_match_history
                                )

                                profile_now = adaptive_accuracy_profile(
                                    recent_accuracy,
                                    sample_count
                                )

                                opponent_pressure = not bool(exact_top_match)

                                print(
                                    f"[OPPONENT] "
                                    f"move={move.uci()} "
                                    f"expected=#1="
                                    f"{expected_human_uci} "
                                    f"TOP_MATCH="
                                    f"{'YES' if exact_top_match else 'NO'} "
                                    f"RECENT="
                                    f"{recent_accuracy:.1f}% "
                                    f"TARGET="
                                    f"{profile_now['target_accuracy']:.1f}% "
                                    f"{profile_now['state']}"
                                )

                            expected_human_board = expected_board_after_move(
                                board,
                                move
                            )

                            detection_source = getattr(
                                detect_human_move,
                                "_last_detection_source",
                                None
                            )
                            detect_human_move._last_detection_source = None

                            if detection_source in (
                                "ULTRA_DELTA",
                                "PERIODIC_FULL_RESCAN"
                            ):
                                # The ultra delta layer has already cross-validated
                                # the current board against the internal board in two
                                # scans and passed full-board physical verification.
                                # Do not run the old temporal-only verifier again on
                                # the same already-settled frame.
                                final_human_ok = True
                                final_human_frame = move_frame
                                final_human_reason = (
                                    "ultra internal-board delta + dual scan + "
                                    "full-board verification confirmed"
                                )
                            else:
                                (
                                    final_human_ok,
                                    final_human_frame,
                                    final_human_reason
                                ) = verify_human_move_on_screen(
                                    sct,
                                    scrcpy_hwnd,
                                    expected_human_board,
                                    baseline_frame,
                                    cached_board_coords,
                                    visual_black_perspective,
                                    move,
                                    board.copy(stack=False)
                                )

                            if not final_human_ok:
                                print(
                                    f"[HUMAN] Rejected before board.push(): "
                                    f"{move.uci()} | {final_human_reason}"
                                )

                                # This detected move was not physically verified,
                                # so undo only the provisional accuracy sample.
                                if expected_human_uci:
                                    if opponent_match_history:
                                        opponent_match_history.pop()

                                # Keep baseline_frame unchanged. It represents the
                                # last internally committed physical board state.
                                continue

                            move_frame = (
                                final_human_frame
                                if final_human_frame is not None
                                else move_frame
                            )

                            next_human_best_uci = None

                            board.push(
                                move
                            )

                            analysis_state = None

                            settled_frame = get_settled_frame(
                                sct,
                                scrcpy_hwnd,
                                move_frame,
                                timeout=HUMAN_SETTLE_TIMEOUT
                            )

                            baseline_frame = (
                                settled_frame
                                if settled_frame is not None
                                else move_frame
                            )

                            last_bot_position_key = None
                            pending_bot_moves.clear()
                            next_main_turn_rescan = time.perf_counter() + TURN_RESCAN_INTERVAL

                            print(
                                f"[HUMAN] Accepted: {san}"
                            )

                    if (
                        board.turn == stockfish_color
                        and not bot_thinking
                    ):
                        position_key = board.fen()

                        if (
                            position_key
                            != last_bot_position_key
                            or position_key
                            in pending_bot_moves
                        ):
                            bot_thinking = True

                            try:
                                pending_entry = (
                                    pending_bot_moves.get(
                                        position_key
                                    )
                                )

                                # Freeze the Stockfish decision for this board position.
                                # The same move is used for click, verification and retry.
                                locked_bot_move = None

                                if pending_entry is not None:
                                    locked_bot_move = (
                                        chess.Move.from_uci(
                                            pending_entry["uci"]
                                        )
                                    )
                                    best_move = locked_bot_move

                                    result = pending_entry[
                                        "result"
                                    ]

                                    best_info_move = pending_entry.get(
                                        "best_info_move"
                                    )

                                    best_san = pending_entry[
                                        "san"
                                    ]

                                    selection_meta = pending_entry.get(
                                        "selection_meta",
                                        {
                                            "rank": 0,
                                            "reason": "pending retry"
                                        }
                                    )

                                    engine_elapsed = 0.0

                                    print(
                                        "[STOCKFISH] "
                                        f"Retrying pending move: "
                                        f"{best_san}"
                                    )

                                else:
                                    print(
                                        "[STOCKFISH] Thinking..."
                                    )

                                    engine_start = time.perf_counter()

                                    multipv_result = engine.analyse(
                                        board,
                                        chess.engine.Limit(
                                            depth=STOCKFISH_DEPTH,
                                            time=STOCKFISH_TIME
                                        ),
                                        multipv=TRAINING_MULTI_PV
                                    )

                                    engine_elapsed = (
                                        time.perf_counter()
                                        - engine_start
                                    )

                                    if not isinstance(
                                        multipv_result,
                                        list
                                    ):
                                        multipv_result = [
                                            multipv_result
                                        ]

                                    result = multipv_result[0]

                                    selected_previous_eval = (
                                        analysis_state.get(
                                            "eval_cp"
                                        )
                                        if analysis_state is not None
                                        else None
                                    )

                                    (
                                        opponent_accuracy,
                                        opponent_sample_count
                                    ) = opponent_recent_accuracy(
                                        opponent_match_history
                                    )

                                    (
                                        best_move,
                                        selected_info,
                                        selection_meta
                                    ) = choose_stockfish_move(
                                        board,
                                        multipv_result,
                                        previous_eval_white_cp=selected_previous_eval,
                                        opponent_accuracy=opponent_accuracy,
                                        opponent_sample_count=opponent_sample_count,
                                        opponent_pressure=opponent_pressure
                                    )

                                    opponent_pressure = False

                                    if (
                                        best_move is None
                                        or best_move
                                        not in board.legal_moves
                                    ):
                                        raise RuntimeError(
                                            "Stockfish selector did not "
                                            "return a legal move."
                                        )

                                    # Freeze the newly selected Stockfish move immediately.
                                    locked_bot_move = best_move

                                    best_info_move = result.get(
                                        "pv",
                                        [None]
                                    )[0]

                                    best_san = board.san(
                                        best_move
                                    )

                                    pending_bot_moves[
                                        position_key
                                    ] = {
                                        "uci": best_move.uci(),
                                        "san": best_san,
                                        "result": result,
                                        "best_info_move": best_info_move,
                                        "selection_meta": selection_meta,
                                    }

                                    print(
                                        "[ENGINE] "
                                        f"depth={STOCKFISH_DEPTH} "
                                        f"time={engine_elapsed:.3f}s "
                                        f"MultiPV={len(multipv_result)}"
                                    )

                                    print(
                                        "[TRAINING] "
                                        f"BEST="
                                        f"{best_info_move.uci() if best_info_move else '-'} "
                                        f"SELECTED="
                                        f"{best_move.uci()} "
                                        f"RANK="
                                        f"#{selection_meta['rank'] + 1}"
                                    )

                                    print(
                                        "[TRAINING] "
                                        f"{selection_meta['reason']}"
                                    )

                                    (
                                        recent_accuracy,
                                        recent_samples
                                    ) = opponent_recent_accuracy(
                                        opponent_match_history
                                    )

                                    adaptive_profile = adaptive_accuracy_profile(
                                        recent_accuracy,
                                        recent_samples
                                    )

                                    print(
                                        "[ADAPT] "
                                        f"opponent="
                                        f"{recent_accuracy if recent_accuracy is not None else 0.0:.1f}% "
                                        f"target="
                                        f"{adaptive_profile['target_accuracy']:.1f}% "
                                        f"state="
                                        f"{adaptive_profile['state']} "
                                        f"rank_cap="
                                        f"#{adaptive_profile['max_rank'] + 1} "
                                        f"max_drop="
                                        f"{adaptive_profile['max_eval_drop']*100:.1f}%"
                                    )

                                # From this point until physical confirmation, only the
                                # frozen Stockfish decision is used; no fresh engine result
                                # can replace the move being clicked or verified.
                                if locked_bot_move is None:
                                    raise RuntimeError(
                                        "Stockfish move was not frozen."
                                    )
                                best_move = locked_bot_move

                                if best_move not in board.legal_moves:
                                    pending_bot_moves.pop(
                                        position_key,
                                        None
                                    )

                                    last_bot_position_key = None

                                    continue

                                # PENDING-MOVE RECOVERY:
                                # A previous click may already have landed even when
                                # transition verification missed it. Before doing ANY
                                # more click, compare the current physical board against
                                # the pending Stockfish move (and also bot+human in case
                                # the human already replied). This runs immediately on
                                # a pending retry, so a settled move is committed instead
                                # of being reported as a permanently frozen move.
                                verified = False
                                after_frame = None
                                reason = "pending Stockfish move not yet confirmed"

                                pending_recovery = None

                                if pending_entry is not None:
                                    pending_recovery = periodic_full_board_catchup_scan(
                                        sct,
                                        scrcpy_hwnd,
                                        board,
                                        cached_board_coords,
                                        visual_black_perspective,
                                        pending_bot_move=best_move,
                                        first_frame=None,
                                        legal_moves=list(board.legal_moves)
                                    )

                                    if (
                                        pending_recovery is not None
                                        and pending_recovery.get("bot_move") == best_move
                                        and pending_recovery.get("frame") is not None
                                        and pending_recovery.get("kind") in (
                                            "BOT_ONLY",
                                            "BOT_PLUS_HUMAN"
                                        )                                    ):
                                        recovery_frame = pending_recovery["frame"]
                                        recovered_human = pending_recovery.get("human_move")

                                        if recovered_human is not None:
                                            pending_recovered_human = (
                                                recovered_human,
                                                recovery_frame
                                            )
                                            print(
                                                "[RECOVERY] Pending Stockfish move + human reply "
                                                "already on screen: "
                                                f"{best_san} + "
                                                f"{chess.square_name(recovered_human.from_square)}"
                                                f"{chess.square_name(recovered_human.to_square)}"
                                            )
                                        else:
                                            print(
                                                "[RECOVERY] Pending Stockfish move already on screen: "
                                                f"{best_san} | no additional click"
                                            )

                                        verified = True
                                        after_frame = recovery_frame
                                        reason = pending_recovery["reason"]

                                before_frame = capture_screen(
                                    sct,
                                    scrcpy_hwnd
                                )

                                if before_frame is None and not verified:
                                    last_bot_position_key = (
                                        position_key
                                    )

                                    continue

                                # PROMOTION RECOVERY:
                                # The pawn move itself may already have landed and
                                # opened the promotion menu even when click/transition
                                # verification failed. In that state the source square
                                # is empty, so re-clicking source+destination would be
                                # wrong. First look ONLY for the exact promotion piece
                                # requested by Stockfish. No fallback location is used
                                # during this recovery probe, so it cannot click a random
                                # board square when no promotion menu is open.
                                if (
                                    not verified
                                    and best_move.promotion is not None
                                    and pending_entry is not None
                                ):
                                    promotion_recovered = select_promotion_piece(
                                        sct,
                                        scrcpy_hwnd,
                                        best_move,
                                        board.turn,
                                        cached_board_coords,
                                        visual_black_perspective,
                                        allow_fallback=False
                                    )

                                    if promotion_recovered:
                                        promotion_check_frame = capture_screen(
                                            sct,
                                            scrcpy_hwnd
                                        )

                                        if promotion_check_frame is not None:
                                            expected_promotion_board = expected_board_after_move(
                                                board,
                                                best_move
                                            )

                                            promotion_full_ok, promotion_full_reason = full_board_state_confirmed(
                                                promotion_check_frame,
                                                expected_promotion_board,
                                                cached_board_coords,
                                                visual_black_perspective
                                            )

                                            promotion_fast_ok = False
                                            promotion_fast_reason = ""

                                            if not promotion_full_ok:
                                                promotion_fast_ok, promotion_fast_reason = fast_expected_post_state_confirmed(
                                                    baseline_frame,
                                                    promotion_check_frame,
                                                    board,
                                                    best_move,
                                                    cached_board_coords,
                                                    visual_black_perspective
                                                )

                                            if promotion_full_ok or promotion_fast_ok:
                                                verified = True
                                                after_frame = promotion_check_frame
                                                reason = (
                                                    "promotion menu recovery confirmed; "
                                                    + (
                                                        promotion_full_reason
                                                        if promotion_full_ok
                                                        else promotion_fast_reason
                                                    )
                                                )
                                                print(
                                                    "[PROMOTION] PENDING RECOVERY SUCCESS | "
                                                    f"{best_san} -> "
                                                    f"{chess.piece_name(best_move.promotion).upper()}"
                                                )

                                if verified:
                                    pre_ok = True
                                    pre_reason = reason
                                else:
                                    # FAST pre-click path: the current frame is first
                                    # checked against the last verified physical board using
                                    # the cheap all-square motion map + exact source/target
                                    # checks. The expensive 64-square template scan is only
                                    # a fallback if the fast gate cannot prove safety.
                                    pre_reference = (
                                        baseline_frame
                                        if baseline_frame is not None
                                        else before_frame
                                    )
                                    pre_ok, pre_reason = fast_preclick_board_confirmed(
                                        pre_reference,
                                        before_frame,
                                        board,
                                        best_move,
                                        cached_board_coords,
                                        visual_black_perspective
                                    )

                                    if not pre_ok:
                                        full_pre_ok, full_pre_reason = full_board_state_confirmed(
                                            before_frame,
                                            board,
                                            cached_board_coords,
                                            visual_black_perspective
                                        )

                                        if full_pre_ok:
                                            pre_ok = True
                                            pre_reason = (
                                                "full-board pre-click fallback: "
                                                + full_pre_reason
                                            )

                                if not pre_ok:
                                    # Never click while the physical board is not
                                    # known to be the exact internal pre-move board.
                                    # A previous tap may still be settling; first
                                    # check whether the requested move has already
                                    # landed. Only a confirmed post-state can commit
                                    # the move. Otherwise keep waiting without any
                                    # internal board change and without declaring a
                                    # terminal desync.
                                    post_already_ok, post_already_reason = (
                                        screen_matches_expected_bot_move(
                                            before_frame,
                                            board,
                                            best_move,
                                            cached_board_coords,
                                            visual_black_perspective,
                                            baseline_frame
                                        )
                                    )

                                    if post_already_ok:
                                        verified = True
                                        after_frame = before_frame
                                        reason = post_already_reason
                                        print(
                                            "[VALIDATION] POST-STATE ALREADY PRESENT | "
                                            f"{best_move.uci()} | committing only after physical confirmation"
                                        )
                                    else:
                                        # The source mismatch can mean the Stockfish move
                                        # is already settled on screen. Re-check the complete
                                        # board before declaring the pending move blocked.
                                        late_recovery = periodic_full_board_catchup_scan(
                                            sct,
                                            scrcpy_hwnd,
                                            board,
                                            cached_board_coords,
                                            visual_black_perspective,
                                            pending_bot_move=best_move,
                                            first_frame=before_frame,
                                            legal_moves=list(board.legal_moves)
                                        )

                                        if (
                                            late_recovery is not None
                                            and late_recovery.get("bot_move") == best_move
                                            and late_recovery.get("frame") is not None
                                            and late_recovery.get("kind") in (
                                                "BOT_ONLY",
                                                "BOT_PLUS_HUMAN"
                                            )
                                        ):
                                            recovery_frame = late_recovery["frame"]
                                            recovered_human = late_recovery.get("human_move")

                                            if recovered_human is not None:
                                                pending_recovered_human = (
                                                    recovered_human,
                                                    recovery_frame
                                                )

                                            verified = True
                                            after_frame = recovery_frame
                                            reason = late_recovery["reason"]
                                            print(
                                                "[RECOVERY] Pending move recovered from full-board state: "
                                                f"{best_san}"
                                                + (
                                                    " + human reply already present"
                                                    if recovered_human is not None
                                                    else ""
                                                )
                                            )
                                        else:
                                            last_bot_position_key = position_key
                                            print(
                                                "[VALIDATION] WAITING | pending Stockfish move "
                                                "not yet physically confirmed; no click and no board.push() | "
                                                f"{pre_reason}"
                                            )
                                            time.sleep(BOT_RECOVERY_POLL)
                                            continue

                                if (
                                    stockfish_moves_since_buffer
                                    >= next_buffer_after
                                ):
                                    buffer_delay = random.choice(
                                        RANDOM_BUFFER_OPTIONS
                                    )

                                    print(
                                        "[BOT BUFFER] "
                                        f"after "
                                        f"{stockfish_moves_since_buffer} "
                                        f"Stockfish moves -> "
                                        f"{buffer_delay:.1f}s"
                                    )

                                    if buffer_delay > 0.0:
                                        time.sleep(buffer_delay)

                                    stockfish_moves_since_buffer = 0

                                    next_buffer_after = random.randint(
                                        RANDOM_BUFFER_MOVE_MIN,
                                        RANDOM_BUFFER_MOVE_MAX
                                    )

                                if not verified:
                                    print(
                                        "[VALIDATION] PRE-CLICK PASS | "
                                        "physical board matches internal board 64/64"
                                    )

                                    clicked = click_move(
                                        best_move,
                                        cached_board_coords,
                                        visual_black_perspective,
                                        scrcpy_hwnd,
                                        sct=sct,
                                        promotion_color=board.turn
                                    )

                                    if not clicked:
                                        print(
                                            "[BOT] CLICK DISPATCH FAILED | "
                                            f"pending={best_move.uci()} | "
                                            "no board change; will retry normally"
                                        )

                                        last_bot_position_key = (
                                            position_key
                                        )

                                        continue

                                    (
                                        verified,
                                        after_frame,
                                        reason
                                    ) = verify_bot_move(
                                        sct,
                                        scrcpy_hwnd,
                                        board,
                                        best_move,
                                        before_frame,
                                        cached_board_coords,
                                        visual_black_perspective
                                    )

                                    retry_count = 0

                                    while (
                                        not verified
                                        and retry_count
                                        < BOT_CLICK_RETRIES
                                    ):
                                        retry_count += 1

                                        # EXTRA 2-second whole-board catch-up while a
                                        # frozen Stockfish move is being retried. This
                                        # specifically handles: bot move already on
                                        # screen + human reply already on screen.
                                        now_rescan = time.perf_counter()
                                        if now_rescan >= next_main_turn_rescan:
                                            catchup = periodic_full_board_catchup_scan(
                                                sct,
                                                scrcpy_hwnd,
                                                board,
                                                cached_board_coords,
                                                visual_black_perspective,
                                                pending_bot_move=best_move,
                                                first_frame=None,
                                                legal_moves=list(board.legal_moves)
                                            )
                                            next_main_turn_rescan = (
                                                now_rescan + TURN_RESCAN_INTERVAL
                                            )

                                            if (
                                                catchup is not None
                                                and catchup.get("bot_move") == best_move
                                                and catchup.get("frame") is not None
                                                and catchup.get("kind") in (
                                                    "BOT_ONLY",
                                                    "BOT_PLUS_HUMAN"
                                                )
                                            ):
                                                recovery_frame = catchup["frame"]
                                                recovered_human = catchup.get("human_move")

                                                # The normal verified-Stockfish commit below
                                                # will push only the pending bot move. If a
                                                # human reply is already visible too, queue
                                                # that verified move for the human branch so
                                                # it is consumed immediately after the bot
                                                # position is committed.
                                                if recovered_human is not None:
                                                    pending_recovered_human = (
                                                        recovered_human,
                                                        recovery_frame
                                                    )
                                                    print(
                                                        "[RECOVERY] Found bot+human already "
                                                        f"on screen: {best_san} + "
                                                        f"{board.san(recovered_human) if recovered_human in expected_board_after_move(board, best_move).legal_moves else recovered_human.uci()}"
                                                    )

                                                verified = True
                                                after_frame = recovery_frame
                                                reason = catchup["reason"]
                                                break

                                        retry_frame = capture_screen(
                                            sct,
                                            scrcpy_hwnd
                                        )

                                        post_ok, post_reason = (
                                            screen_matches_expected_bot_move(
                                                retry_frame,
                                                board,
                                                best_move,
                                                cached_board_coords,
                                                visual_black_perspective,
                                                before_frame
                                            )
                                        )

                                        if post_ok:
                                            verified = True
                                            after_frame = retry_frame
                                            reason = post_reason
                                            break

                                        pre_retry_ok, pre_retry_reason = fast_preclick_board_confirmed(
                                            before_frame,
                                            retry_frame,
                                            board,
                                            best_move,
                                            cached_board_coords,
                                            visual_black_perspective
                                        )

                                        if not pre_retry_ok:
                                            # Do not click through an intermediate/unknown
                                            # frame. Leave the frozen move pending and let
                                            # the next loop confirm the exact pre-state or
                                            # already-landed post-state.
                                            print(
                                                "[VALIDATION] WAITING RETRY | physical board "
                                                "not yet stable; no additional click | "
                                                f"{pre_retry_reason}"
                                            )
                                            break

                                        print(
                                            "[BOT] "
                                            f"Click retry "
                                            f"{retry_count}/"
                                            f"{BOT_CLICK_RETRIES}"
                                        )

                                        clicked_retry = click_move(
                                            best_move,
                                            cached_board_coords,
                                            visual_black_perspective,
                                            scrcpy_hwnd,
                                            sct=sct,
                                            promotion_color=board.turn
                                        )

                                        if not clicked_retry:
                                            break

                                        (
                                            verified,
                                            after_frame,
                                            reason
                                        ) = verify_bot_move(
                                            sct,
                                            scrcpy_hwnd,
                                            board,
                                            best_move,
                                            retry_frame,
                                            cached_board_coords,
                                            visual_black_perspective
                                        )

                                if (
                                    verified
                                    and after_frame is not None
                                ):
                                    before_board = board.copy()

                                    board.push(
                                        best_move
                                    )

                                    analysis_state = build_analysis(
                                        engine,
                                        before_board,
                                        board,
                                        best_move,
                                        best_info=result
                                    )

                                    if analysis_state:
                                        predicted = analysis_state.get(
                                            "best_move"
                                        )

                                        next_human_best_uci = (
                                            predicted
                                            if predicted
                                            and predicted != "-"
                                            else None
                                        )

                                    else:
                                        next_human_best_uci = None

                                    settled_frame = get_settled_frame(
                                        sct,
                                        scrcpy_hwnd,
                                        after_frame,
                                        timeout=0.10
                                    )

                                    baseline_frame = (
                                        settled_frame
                                        if settled_frame is not None
                                        else after_frame
                                    )

                                    (
                                        cached_board_grid,
                                        _,
                                        last_scan_time_ms
                                    ) = scan_board(
                                        baseline_frame,
                                        cached_board_coords
                                    )

                                    pending_bot_moves.pop(
                                        position_key,
                                        None
                                    )

                                    last_bot_position_key = None
                                    next_main_turn_rescan = time.perf_counter() + TURN_RESCAN_INTERVAL

                                    stockfish_moves_since_buffer += 1

                                    print(
                                        f"[VALIDATION] "
                                        f"PASS | {reason}"
                                    )

                                    print_game_state(
                                        board,
                                        stockfish_color,
                                        human_color,
                                        visual_black_perspective,
                                        f"[STOCKFISH] Confirmed: {best_san}",
                                        analysis_state
                                    )

                                else:
                                    # Verification failure is recoverable. Keep the exact
                                    # Stockfish move pending, but do NOT label it as a
                                    # permanent/frozen state. The next iteration first
                                    # checks whether the move already landed, then clicks
                                    # again only when the true internal pre-state is visible.
                                    last_bot_position_key = position_key
                                    print(
                                        "[VALIDATION] WAITING | "
                                        f"pending={best_move.uci()} "
                                        "| physical post-state not yet confirmed; "
                                        "internal board NOT advanced | "
                                        f"{reason}"
                                    )
                                    time.sleep(BOT_RECOVERY_POLL)

                            except Exception as e:
                                print(
                                    f"[STOCKFISH ERROR] {e}"
                                )

                            finally:
                                bot_thinking = False

                    if board.is_game_over():
                        game_ready = False

                        print_game_state(
                            board,
                            stockfish_color,
                            human_color,
                            visual_black_perspective,
                            f"GAME OVER: {board.outcome()}"
                        )

                if (
                    grid_locked
                    and game_ready
                    and not bot_thinking
                ):
                    current_status = status
                    now = time.perf_counter()

                    if (
                        current_status
                        != last_wait_status
                        or
                        now - last_wait_report
                        >= 1.5
                    ):
                        progress(
                            "STATE",
                            current_status,
                            key="state",
                            force=True
                        )

                        last_wait_status = current_status
                        last_wait_report = now

                if cached_board_coords:
                    draw_overlay(
                        display_frame,
                        cached_board_coords,
                        cached_board_grid,
                        grid_locked,
                        visual_black_perspective,
                        last_scan_time_ms,
                        status,
                        (
                            stockfish_color
                            if stockfish_color is not None
                            else chess.BLACK
                        ),
                        (
                            human_color
                            if human_color is not None
                            else chess.WHITE
                        ),
                        analysis_state
                    )

                else:
                    cv2.rectangle(
                        display_frame,
                        (0, 0),
                        (
                            frame.shape[1],
                            48
                        ),
                        (0, 0, 0),
                        -1
                    )

                    cv2.putText(
                        display_frame,
                        "PRESS R TO INITIALIZE BOARD",
                        (8, 28),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (0, 255, 255),
                        2
                    )

                cv2.imshow(
                    "Chess Vision Tracker",
                    display_frame
                )

        finally:
            cv2.destroyAllWindows()

            try:
                engine.quit()
            except Exception:
                pass


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print(
            "\n[INFO] Stopped by user."
        )

        cv2.destroyAllWindows()
