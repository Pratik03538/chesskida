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

from gm_book import GMBook

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
GM_BOOK_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "Ultimate_GM_Bullet.bin"
)
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
BOT_SOURCE_SELECT_TIMEOUT = 0.020
BOT_SOURCE_SELECT_POLL = 0.001
BOT_SOURCE_SELECT_CHANGE_MIN = 0.0012
BOT_SOURCE_SELECT_MAX_EXTRA_CHANGES = 0
BOT_SOURCE_SELECT_DOMINANCE_RATIO = 0.80
BOT_SOURCE_SELECT_STABLE_SAMPLES = 1

PROMOTION_WAIT = 0.050
PROMOTION_RETRIES = 3
PROMOTION_CONFIRM_TIMEOUT = 0.35
PROMOTION_CONFIRM_FRAMES = 2
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

BOT_VERIFY_TIMEOUT = 0.250
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

# Natural bot move timing.
# The tiny per-move base delay is retained unchanged.
BOT_NATURAL_DELAY_MIN = 0.15
BOT_NATURAL_DELAY_MAX = 0.45
BOT_STRATEGIC_DELAY_MIN = 0.62
BOT_STRATEGIC_DELAY_MAX = 1.30
BOT_MATE_DELAY_MIN = 1.00
BOT_MATE_DELAY_MAX = 2.00

# Thinking simulator:
# No fixed move-number targets. Every move gets a randomized eligibility
# check, but a pause is considered only when the current position looks
# thinking-worthy. A randomized cooldown and remaining per-game budget then
# decide whether a pause is actually taken.
BOT_EVERY_MOVE_DELAY_MIN = 0.000
BOT_EVERY_MOVE_DELAY_MAX = 0.010
BOT_THINKING_ENABLED_DEFAULT = True
BOT_THINKING_START_AFTER_MOVE = 10
# Irregular pause cadence:
# sometimes another pause may be considered after 5-8 moves, while quieter
# positions can naturally wait 9-12+ moves. This is only a minimum refractory
# window; there is no fixed "pause every N moves" schedule.
BOT_PAUSE_MOVE_COOLDOWN_MIN = 5
BOT_PAUSE_MOVE_COOLDOWN_MAX = 12
BOT_PAUSE_ELIGIBILITY_SCALE = 0.55
BOT_POST_50_MOVE = 50
BOT_MATE_PAUSE_MIN_MATE = 1
BOT_MATE_PAUSE_MAX_MATE = 5
BOT_THINK_PAUSE_MIN = 2.0
BOT_THINK_PAUSE_MAX = 5.0
BOT_MATE_PAUSE_MIN = 2.0
BOT_MATE_PAUSE_MAX = 5.0
BOT_THINK_BUDGET_MIN = 10.0
BOT_THINK_BUDGET_MAX = 15.0
BOT_THINK_COOLDOWN_MIN = 5.0
BOT_THINK_COOLDOWN_MAX = 10.0
BOT_THINK_ELIGIBILITY_MIN = 0.18
BOT_THINK_ELIGIBILITY_MAX = 0.65
BOT_THINK_REASONABLE_CP = 60
BOT_THINK_UNCERTAINTY_CP = 75
BOT_THINK_SHARP_EVAL_CP = 80
BOT_THINK_STRATEGIC_LEGAL_MOVES = 24
BOT_OPENING_FAST_VERIFY_MOVES = 10
BOT_STRONG_FAVOR_CP = 250
BOT_DELAY_REPEAT_GAP = 0.045

# Small random gap between SOURCE and DESTINATION clicks.
# This is the physical move gesture interval, not a thinking delay.
BOT_SOURCE_TO_TARGET_DELAY_MIN = 0.004
BOT_SOURCE_TO_TARGET_DELAY_MAX = 0.012

# When the normal safe pool contains too few lower-ranked choices, allow a
# small extra evaluation band ONLY for rank-diversity selection. This does not
# change forced-best, mate, promotion, capture, or physical-safety branches.
HUMAN_SELECTION_DIVERSITY_EXTRA_DROP = 0.08

# Retained as counters for match-state reset/log compatibility.
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
# ============================================================
# MATCH / RESULT-SCREEN CONTROLS
# ADD-ONLY: isolated from chess move/engine logic.
# ============================================================
MATCH_RESULT_CHANGE_THRESHOLD = 0.55
MATCH_RESULT_CONFIRM_FRAMES = 2
MATCH_ACTION_VERIFY_TIMEOUT = 1.20
MATCH_ACTION_SETTLE_DELAY = 0.08
MATCH_BUTTON_MIN_CHANGE = 0.010
MATCH_AUTO_DELAY_MIN = 0.0
MATCH_AUTO_DELAY_MAX = 0.0
MATCH_BUTTON_RETRIES = 10
MATCHMAKING_SCAN_INTERVAL = 0.10

# The actual result-screen action row from the supplied phone screenshot:
#   left  -> Rematch
#   right -> New <time-control>
# These are normalized coordinates, so they remain valid when scrcpy scales
# the phone image to a different client size.
MATCH_REMATCH_CENTER_X = 0.2640
MATCH_NEW_CENTER_X = 0.7360
MATCH_ACTION_CENTER_Y = 0.3970
MATCH_ACTION_BOX_HALF_W = 0.2050
MATCH_ACTION_BOX_HALF_H = 0.0335
MATCH_ACTION_DARK_FRACTION_MIN = 0.72
MATCH_ACTION_LOCAL_CONFIRM_MIN = 0.020


def match_ui_mouse_callback(event, x, y, flags, param):
    if event != cv2.EVENT_LBUTTONUP or param is None:
        return

    def inside(rect):
        if rect is None:
            return False
        x1, y1, x2, y2 = rect
        return x1 <= x <= x2 and y1 <= y <= y2

    if inside(param.get("thinking_toggle_rect")):
        param["thinking_enabled"] = not param.get(
            "thinking_enabled",
            BOT_THINKING_ENABLED_DEFAULT
        )
        print(
            "[PAUSE UI] PAUSE = "
            f"{'ON' if param['thinking_enabled'] else 'OFF'}"
        )
        return

    if inside(param.get("new_match_toggle_rect")):
        param["new_match_enabled"] = (
            not param.get("new_match_enabled", False)
        )
        if param["new_match_enabled"]:
            param["rematch_enabled"] = False

        print(
            "[MATCH UI] NEW MATCH AUTO = "
            f"{'ON' if param['new_match_enabled'] else 'OFF'}"
            + (
                " | REMATCH AUTO = OFF"
                if param["new_match_enabled"]
                else ""
            )
        )
        return

    if inside(param.get("rematch_toggle_rect")):
        param["rematch_enabled"] = (
            not param.get("rematch_enabled", False)
        )
        if param["rematch_enabled"]:
            param["new_match_enabled"] = False

        print(
            "[MATCH UI] REMATCH AUTO = "
            f"{'ON' if param['rematch_enabled'] else 'OFF'}"
            + (
                " | NEW MATCH AUTO = OFF"
                if param["rematch_enabled"]
                else ""
            )
        )
        return


def match_screen_change_score(before_frame, after_frame):
    if before_frame is None or after_frame is None:
        return 0.0

    a = cv2.resize(
        cv2.cvtColor(before_frame, cv2.COLOR_BGR2GRAY),
        (64, 64),
        interpolation=cv2.INTER_AREA
    )
    b = cv2.resize(
        cv2.cvtColor(after_frame, cv2.COLOR_BGR2GRAY),
        (64, 64),
        interpolation=cv2.INTER_AREA
    )

    diff = cv2.absdiff(a, b) / 255.0

    return float(
        max(
            np.mean(diff >= 0.18),
            np.mean(diff) * 2.0
        )
    )


def _match_rect_edge_score(edge_map, x, y, w, h):
    """Score how strongly a rectangle looks like a UI button."""
    height, width = edge_map.shape[:2]

    x1 = max(0, int(x))
    y1 = max(0, int(y))
    x2 = min(width, int(x + w))
    y2 = min(height, int(y + h))

    if x2 - x1 < 10 or y2 - y1 < 10:
        return 0.0

    thickness = max(
        2,
        min(
            8,
            int(min(w, h) * 0.18)
        )
    )

    top = edge_map[
        y1:min(y2, y1 + thickness),
        x1:x2
    ]
    bottom = edge_map[
        max(y1, y2 - thickness):y2,
        x1:x2
    ]
    left = edge_map[
        y1:y2,
        x1:min(x2, x1 + thickness)
    ]
    right = edge_map[
        y1:y2,
        max(x1, x2 - thickness):x2
    ]

    if (
        top.size == 0
        or bottom.size == 0
        or left.size == 0
        or right.size == 0
    ):
        return 0.0

    return float(
        (
            np.mean(top > 0)
            + np.mean(bottom > 0)
            + np.mean(left > 0)
            + np.mean(right > 0)
        ) / 4.0
    )


def match_button_candidates(frame):
    """
    Detect the actual RESULT-SCREEN action row.

    On the current chess UI the Rematch/New controls are two large, equal
    dark rounded rectangles in one horizontal row. The button fill is only
    slightly brighter than the surrounding result background, so an
    intensity-based mask is more reliable than generic edge contours.

    IMPORTANT:
    A candidate is accepted only when it looks like the real two-button
    action row. There is intentionally NO arbitrary screen-coordinate
    fallback.
    """
    if frame is None:
        return []

    height, width = frame.shape[:2]

    if height < 120 or width < 240:
        return []

    gray = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2GRAY
    )

    # The action row occupies the middle/lower result panel. This narrow
    # region is deliberately chosen from the actual result-screen layout so
    # player cards/text above cannot become click targets.
    roi_top = int(height * 0.32)
    roi_bottom = int(height * 0.49)

    roi = gray[
        roi_top:roi_bottom,
        :
    ]

    best = None

    # The button surface is a dark gray that is slightly brighter than the
    # surrounding nearly-black result background. Use several thresholds so
    # anti-aliasing/device rendering does not break detection.
    for low, high in (
        (38, 85),
        (40, 90),
        (42, 100),
        (44, 110),
    ):
        mask = cv2.inRange(
            roi,
            low,
            high
        )

        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(
                cv2.MORPH_RECT,
                (21, 21)
            )
        )

        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(
                cv2.MORPH_RECT,
                (5, 5)
            )
        )

        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            bx, by, bw, bh = cv2.boundingRect(
                contour
            )
            by += roi_top

            if bw < int(width * 0.70):
                continue
            if bw > int(width * 0.99):
                continue

            if bh < int(height * 0.035):
                continue
            if bh > int(height * 0.11):
                continue

            center_y = by + bh * 0.5

            if (
                center_y < height * 0.35
                or center_y > height * 0.46
            ):
                continue

            aspect = bw / max(
                1.0,
                float(bh)
            )

            if aspect < 6.0:
                continue

            # Prefer a nearly full-width paired action row.
            coverage = bw / float(max(1, width))

            candidate_score = (
                coverage * 4.0
                - abs(
                    center_y / float(height) - 0.395
                ) * 2.0
                + min(
                    1.0,
                    aspect / 12.0
                )
            )

            if (
                best is None
                or candidate_score > best[0]
            ):
                best = (
                    candidate_score,
                    bx,
                    by,
                    bw,
                    bh
                )

    if best is None:
        return []

    _, bx, by, bw, bh = best

    # The UI leaves a small central gap between the two buttons. Split the
    # detected action-row surface around that gap instead of guessing a
    # desktop coordinate.
    gap = max(
        8,
        int(width * 0.018)
    )

    half_w = int(
        (bw - gap) / 2
    )

    if half_w < int(width * 0.28):
        return []

    left_x = int(bx)
    right_x = int(
        bx + half_w + gap
    )

    # Keep both halves inside the detected row.
    right_end = right_x + half_w
    detected_end = bx + bw

    if right_end > detected_end:
        half_w = detected_end - right_x

    if half_w < int(width * 0.25):
        return []

    center_y = by + bh * 0.5

    left = (
        int(left_x + half_w * 0.5),
        int(round(center_y)),
        int(half_w),
        int(bh)
    )

    right = (
        int(right_x + half_w * 0.5),
        int(round(center_y)),
        int(half_w),
        int(bh)
    )

    print(
        "[MATCH] Result action row located | "
        f"REMATCH=({left[0]},{left[1]}) "
        f"NEW=({right[0]},{right[1]}) "
        f"row=({bx},{by},{bw},{bh})"
    )

    return [
        (
            left[0],
            left[1],
            left[2],
            left[3],
            1.0
        ),
        (
            right[0],
            right[1],
            right[2],
            right[3],
            1.0
        )
    ]

def result_action_buttons_present(frame):
    """
    Validate the actual Result page from the known Rematch/New button row.

    Do NOT require generic contour candidates here. The supplied result-page
    screenshot shows the buttons at a stable normalized position, and generic
    contour detection was rejecting the real page. A large screen change is
    never enough by itself: both button footprints must independently look like
    the dark rounded action controls.
    """
    if frame is None:
        return False

    height, width = frame.shape[:2]

    if height < 120 or width < 240:
        return False

    left_score = _match_action_visual_score(
        frame,
        MATCH_REMATCH_CENTER_X,
        MATCH_ACTION_CENTER_Y
    )

    right_score = _match_action_visual_score(
        frame,
        MATCH_NEW_CENTER_X,
        MATCH_ACTION_CENTER_Y
    )

    # Both real controls are dark gray panels occupying most of their
    # footprints. Also require the two scores to be reasonably similar;
    # this helps reject a notification/overlay that happens to cover only
    # one side of the screen.
    pair_similarity = min(
        left_score,
        right_score
    ) / max(
        0.001,
        max(left_score, right_score)
    )

    valid = (
        left_score >= MATCH_ACTION_DARK_FRACTION_MIN
        and right_score >= MATCH_ACTION_DARK_FRACTION_MIN
        and pair_similarity >= 0.72
    )

    if valid:
        print(
            "[MATCH] Result buttons PRESENT | "
            f"Rematch={left_score:.3f} "
            f"New={right_score:.3f} "
            f"pair={pair_similarity:.3f}"
        )

    return valid



def _match_action_visual_score(
    frame,
    center_x_norm,
    center_y_norm
):
    """
    Score one known result-button footprint.
    """
    if frame is None:
        return 0.0

    height, width = frame.shape[:2]

    cx = center_x_norm * width
    cy = center_y_norm * height

    half_w = MATCH_ACTION_BOX_HALF_W * width
    half_h = MATCH_ACTION_BOX_HALF_H * height

    x1 = max(0, int(cx - half_w))
    y1 = max(0, int(cy - half_h))
    x2 = min(width, int(cx + half_w))
    y2 = min(height, int(cy + half_h))

    if x2 <= x1 or y2 <= y1:
        return 0.0

    crop = frame[y1:y2, :]
    local = frame[y1:y2, x1:x2]

    gray_local = cv2.cvtColor(
        local,
        cv2.COLOR_BGR2GRAY
    )

    # Actual button panel is approximately 49-65 gray in the supplied
    # screenshot, while the surrounding result background is about 36-40.
    dark_fraction = float(
        np.mean(
            (gray_local >= 35)
            & (gray_local <= 95)
        )
    )

    # Estimate immediate outside-background from strips just above/below the
    # button. This is more robust than a single absolute color threshold.
    strip_h = max(
        4,
        int(half_h * 0.30)
    )

    top_y1 = max(
        0,
        y1 - strip_h
    )
    top_y2 = y1

    bottom_y1 = y2
    bottom_y2 = min(
        height,
        y2 + strip_h
    )

    outside_parts = []

    if top_y2 > top_y1:
        outside_parts.append(
            cv2.cvtColor(
                frame[top_y1:top_y2, x1:x2],
                cv2.COLOR_BGR2GRAY
            )
        )

    if bottom_y2 > bottom_y1:
        outside_parts.append(
            cv2.cvtColor(
                frame[bottom_y1:bottom_y2, x1:x2],
                cv2.COLOR_BGR2GRAY
            )
        )

    if outside_parts:
        outside_mean = float(
            np.mean(
                np.concatenate(
                    [
                        part.reshape(-1)
                        for part in outside_parts
                    ]
                )
            )
        )
    else:
        outside_mean = 0.0

    inside_mean = float(
        np.mean(
            gray_local
        )
    )

    contrast = max(
        0.0,
        inside_mean - outside_mean
    )

    # On the supplied result screenshot the button panel is visibly brighter
    # than the surrounding dark result background. Normalize contrast into
    # [0,1] and combine with fill coverage.
    contrast_score = min(
        1.0,
        contrast / 12.0
    )

    return float(
        0.75 * dark_fraction
        + 0.25 * contrast_score
    )



def match_action_points(frame, action):
    """
    Return the actual Rematch/New button center.

    Prefer the detected result-action row from the current frame. The
    normalized geometry is used only to identify the requested half of that
    same known row.
    """
    if frame is None:
        return []

    candidates = match_button_candidates(
        frame
    )

    selected = None

    if len(candidates) >= 2:
        ordered = sorted(
            candidates,
            key=lambda item: item[0]
        )

        selected = (
            ordered[0]
            if action == "REMATCH"
            else ordered[1]
            if action == "NEW MATCH"
            else None
        )

    if selected is None:
        if action == "REMATCH":
            center_x = MATCH_REMATCH_CENTER_X
        elif action == "NEW MATCH":
            center_x = MATCH_NEW_CENTER_X
        else:
            return []

        score = _match_action_visual_score(
            frame,
            center_x,
            MATCH_ACTION_CENTER_Y
        )

        if score < MATCH_ACTION_DARK_FRACTION_MIN:
            print(
                "[MATCH] Button validation failed | "
                f"action={action} "
                f"visual_score={score:.3f}"
            )
            return []

        height, width = frame.shape[:2]

        px = int(
            round(
                center_x * width
            )
        )
        py = int(
            round(
                MATCH_ACTION_CENTER_Y * height
            )
        )

        button_w = int(
            MATCH_ACTION_BOX_HALF_W * 2 * width
        )
        button_h = int(
            MATCH_ACTION_BOX_HALF_H * 2 * height
        )

        print(
            "[MATCH] Result button validated by known geometry | "
            f"action={action} "
            f"center=({px},{py}) "
            f"visual_score={score:.3f} "
            f"frame={width}x{height}"
        )

        return [
            (
                px,
                py,
                button_w,
                button_h,
                score
            )
        ]

    px = int(
        selected[0]
    )
    py = int(
        selected[1]
    )
    button_w = int(
        selected[2]
    )
    button_h = int(
        selected[3]
    )
    score = float(
        selected[4]
    )

    print(
        "[MATCH] Actual result button selected | "
        f"action={action} "
        f"center=({px},{py}) "
        f"visual_score={score:.3f}"
    )

    return [
        (
            px,
            py,
            button_w,
            button_h,
            score
        )
    ]

def _button_local_change_score(before_frame, after_frame, center_x, center_y, radius=28):
    if before_frame is None or after_frame is None:
        return 0.0

    height, width = before_frame.shape[:2]

    x1 = max(0, int(center_x) - radius)
    y1 = max(0, int(center_y) - radius)
    x2 = min(width, int(center_x) + radius)
    y2 = min(height, int(center_y) + radius)

    if x2 <= x1 or y2 <= y1:
        return 0.0

    a = cv2.cvtColor(
        before_frame[y1:y2, x1:x2],
        cv2.COLOR_BGR2GRAY
    )
    b = cv2.cvtColor(
        after_frame[y1:y2, x1:x2],
        cv2.COLOR_BGR2GRAY
    )

    a = cv2.resize(a, (32, 32), interpolation=cv2.INTER_AREA)
    b = cv2.resize(b, (32, 32), interpolation=cv2.INTER_AREA)

    return float(
        np.mean(cv2.absdiff(a, b)) / 255.0
    )


def perform_match_action(sct, hwnd, action):
    if action not in ("REMATCH", "NEW MATCH"):
        return False, "invalid match action"

    for attempt in range(1, MATCH_BUTTON_RETRIES + 1):
        frame_before = capture_screen(sct, hwnd)

        if frame_before is None:
            time.sleep(0.05)
            continue

        points = match_action_points(
            frame_before,
            action
        )

        for point in points:
            px = int(point[0])
            py = int(point[1])
            client_x = 0
            client_y = 0
            client_w = frame_before.shape[1]
            client_h = frame_before.shape[0]

            if hwnd and user32 and user32.IsWindow(hwnd):
                rect = wintypes.RECT()

                try:
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

                    client_x = int(point.x)
                    client_y = int(point.y)
                    client_w = int(rect.right - rect.left)
                    client_h = int(rect.bottom - rect.top)

                except Exception:
                    pass

            frame_h, frame_w = frame_before.shape[:2]

            screen_x = int(
                client_x
                + (px / max(1, frame_w)) * client_w
            )
            screen_y = int(
                client_y
                + (py / max(1, frame_h)) * client_h
            )

            print(
                f"[MATCH] {action} click attempt "
                f"{attempt}/{MATCH_BUTTON_RETRIES} at "
                f"({screen_x},{screen_y})"
            )

            if not focus_scrcpy(hwnd):
                continue

            # Re-read the client rectangle AFTER focusing. Windows DPI/scaling
            # and scrcpy window activation can otherwise make the first mapping
            # stale by a few pixels or more.
            if hwnd and user32 and user32.IsWindow(hwnd):
                try:
                    rect = wintypes.RECT()
                    user32.GetClientRect(
                        hwnd,
                        ctypes.byref(rect)
                    )

                    client_origin = wintypes.POINT(
                        rect.left,
                        rect.top
                    )

                    user32.ClientToScreen(
                        hwnd,
                        ctypes.byref(client_origin)
                    )

                    client_x = int(client_origin.x)
                    client_y = int(client_origin.y)
                    client_w = int(
                        rect.right - rect.left
                    )
                    client_h = int(
                        rect.bottom - rect.top
                    )

                    screen_x = int(
                        client_x
                        + (px / max(1, frame_w))
                        * client_w
                    )
                    screen_y = int(
                        client_y
                        + (py / max(1, frame_h))
                        * client_h
                    )

                    print(
                        "[MATCH] Click mapping refreshed | "
                        f"client=({client_x},{client_y},"
                        f"{client_w},{client_h}) "
                        f"screen=({screen_x},{screen_y})"
                    )
                except Exception:
                    pass

            left_click_screen(screen_x, screen_y)

            time.sleep(
                MATCH_ACTION_SETTLE_DELAY
            )

            deadline = (
                time.perf_counter()
                + MATCH_ACTION_VERIFY_TIMEOUT
            )

            while time.perf_counter() < deadline:
                after = capture_screen(sct, hwnd)

                if after is None:
                    time.sleep(0.02)
                    continue

                local_change = _button_local_change_score(
                    frame_before,
                    after,
                    px,
                    py
                )
                screen_change = match_screen_change_score(
                    frame_before,
                    after
                )

                # Never confirm from a global screen change alone. A wrong
                # click elsewhere on the result screen can change many pixels
                # and previously caused false "CLICK CONFIRMED" messages.
                target_confirm = _button_local_change_score(
                    frame_before,
                    after,
                    px,
                    py,
                    radius=max(
                        28,
                        int(
                            min(frame_before.shape[:2])
                            * 0.055
                        )
                    )
                )

                before_target_score = _match_action_visual_score(
                    frame_before,
                    (
                        MATCH_REMATCH_CENTER_X
                        if action == "REMATCH"
                        else MATCH_NEW_CENTER_X
                    ),
                    MATCH_ACTION_CENTER_Y
                )

                after_target_score = _match_action_visual_score(
                    after,
                    (
                        MATCH_REMATCH_CENTER_X
                        if action == "REMATCH"
                        else MATCH_NEW_CENTER_X
                    ),
                    MATCH_ACTION_CENTER_Y
                )

                button_pair_after = result_action_buttons_present(
                    after
                )

                target_disappeared = (
                    before_target_score >= MATCH_ACTION_DARK_FRACTION_MIN
                    and after_target_score
                    < before_target_score - 0.06
                )

                if (
                    target_confirm >= MATCH_ACTION_LOCAL_CONFIRM_MIN
                    or (
                        target_disappeared
                        and not button_pair_after
                    )
                ):
                    print(
                        f"[MATCH] {action} CLICK CONFIRMED | "
                        "target action changed/disappeared | "
                        f"screen_change={screen_change:.3f} "
                        f"target_change={target_confirm:.3f} "
                        f"button_before={before_target_score:.3f} "
                        f"button_after={after_target_score:.3f}"
                    )
                    return True, "target button transition confirmed"

                time.sleep(0.02)

            break

        time.sleep(0.05)

    return (
        False,
        f"{action} transition not confirmed after "
        f"{MATCH_BUTTON_RETRIES} attempts"
    )


def match_ui_draw(
    display_frame,
    match_ui,
    board_coords=None
):
    if match_ui is None:
        return

    for key in (
        "thinking_toggle_rect",
        "rematch_toggle_rect",
        "new_match_toggle_rect",
        "move_history_rect",
    ):
        match_ui[key] = None

    height, width = display_frame.shape[:2]

    # Dedicated control panel: always outside the chess board.
    panel_w = min(
        560,
        max(420, width - 16)
    )
    panel_h = 230

    if board_coords is None:
        panel_x = max(
            8,
            width - panel_w - 8
        )
        panel_y = 52
    else:
        bx, by, bw, bh = board_coords
        board_rect = (
            bx,
            by,
            bx + bw,
            by + bh
        )

        candidates = [
            (bx + bw + 12, max(52, by)),
            (bx - panel_w - 12, max(52, by)),
            (max(8, bx), max(8, by - panel_h - 12)),
            (max(8, bx), min(height - panel_h - 8, by + bh + 12)),
        ]

        def valid(rect):
            x1, y1, x2, y2 = rect
            return (
                x1 >= 4
                and y1 >= 4
                and x2 <= width - 4
                and y2 <= height - 4
                and (
                    x2 <= board_rect[0]
                    or x1 >= board_rect[2]
                    or y2 <= board_rect[1]
                    or y1 >= board_rect[3]
                )
            )

        panel_x, panel_y = candidates[0]

        for cx, cy in candidates:
            if valid(
                (cx, cy, cx + panel_w, cy + panel_h)
            ):
                panel_x, panel_y = cx, cy
                break

    panel_x = max(
        4,
        min(width - panel_w - 4, panel_x)
    )
    panel_y = max(
        4,
        min(height - panel_h - 4, panel_y)
    )

    match_ui["controls_rect"] = (
        panel_x,
        panel_y,
        panel_x + panel_w,
        panel_y + panel_h
    )

    # Professional dark-panel palette.
    bg = (24, 29, 41)
    border = (255, 210, 90)
    accent = (255, 220, 110)
    text_main = (245, 248, 255)
    text_muted = (185, 195, 210)
    active = (100, 225, 150)
    inactive = (165, 145, 255)

    overlay = display_frame.copy()

    cv2.rectangle(
        overlay,
        (panel_x, panel_y),
        (panel_x + panel_w, panel_y + panel_h),
        bg,
        -1
    )

    display_frame[:] = cv2.addWeighted(
        overlay,
        0.92,
        display_frame,
        0.08,
        0
    )

    cv2.rectangle(
        display_frame,
        (panel_x, panel_y),
        (panel_x + panel_w, panel_y + panel_h),
        border,
        2
    )

    phase_text = {
        "GAME": "GAME",
        "RESULT": "RESULT SCREEN",
        "AWAIT_RESULT": "WAITING FOR RESULT SCREEN",
        "MATCHMAKING": "WAITING FOR NEW MATCH",
        "IDLE": "READY"
    }.get(
        match_ui.get("phase", "IDLE"),
        match_ui.get("phase", "IDLE")
    )

    cv2.putText(
        display_frame,
        f"MATCH: {phase_text}",
        (panel_x + 14, panel_y + 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        accent,
        1
    )

    pref = match_ui.get(
        "preference",
        {}
    )

    def cp_text(value):
        if value is None:
            return "-"
        try:
            return f"{float(value) / 100.0:+.2f}"
        except Exception:
            return str(value)

    cv2.putText(
        display_frame,
        (
            f"BEST:{pref.get('best','-')} {cp_text(pref.get('best_cp'))}  "
            f"SELECTED:{pref.get('selected','-')} "
            f"{cp_text(pref.get('selected_cp'))}  "
            f"RANK:{pref.get('rank','-')}"
        ),
        (panel_x + 14, panel_y + 46),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.36,
        text_main,
        1
    )

    cv2.putText(
        display_frame,
        f"REASON: {str(pref.get('reason','-'))[:92]}",
        (panel_x + 14, panel_y + 66),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.31,
        text_muted,
        1
    )

    obstruction = float(
        match_ui.get(
            "board_obstruction",
            0.0
        )
    )

    guard_text = (
        f"BOARD VISIBILITY: {(1.0 - obstruction) * 100:.1f}%"
    )

    if match_ui.get("screen_guard"):
        guard_text += " | PAUSED >30% HIDDEN"

    cv2.putText(
        display_frame,
        guard_text,
        (panel_x + 14, panel_y + 86),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.34,
        accent,
        1
    )

    auto_action = "OFF"

    if match_ui.get("rematch_enabled"):
        auto_action = "REMATCH"
    elif match_ui.get("new_match_enabled"):
        auto_action = "NEW MATCH"

    cv2.putText(
        display_frame,
        f"AUTO ACTION: {auto_action}",
        (panel_x + 14, panel_y + 104),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.34,
        text_main,
        1
    )

    thinking_enabled = bool(
        match_ui.get(
            "thinking_enabled",
            BOT_THINKING_ENABLED_DEFAULT
        )
    )

    if _thinking_budget_remaining is None:
        budget_text = (
            f"{BOT_THINK_BUDGET_MIN:.0f}-{BOT_THINK_BUDGET_MAX:.0f}s"
        )
    else:
        budget_text = f"{_thinking_budget_remaining:.1f}s LEFT"

    cv2.putText(
        display_frame,
        (
            f"PAUSE: {'ON' if thinking_enabled else 'OFF'}  |  "
            f"PAUSE RANGE: {BOT_THINK_PAUSE_MIN:.1f}-{BOT_THINK_PAUSE_MAX:.1f}s"
        ),
        (panel_x + 14, panel_y + 124),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.33,
        accent,
        1
    )

    cv2.putText(
        display_frame,
        f"TOTAL PAUSE BUDGET: {budget_text}  |  RANDOM MOVE GAP",
        (panel_x + 14, panel_y + 144),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.30,
        text_muted,
        1
    )

    new_match_label = (
        "NEW MATCH: ON"
        if match_ui.get("new_match_enabled")
        else "NEW MATCH: OFF"
    )

    rematch_label = (
        "REMATCH: ON"
        if match_ui.get("rematch_enabled")
        else "REMATCH: OFF"
    )

    # Thinking toggle sits above the existing match-action controls.
    think_label = (
        "PAUSE: ON"
        if thinking_enabled
        else "PAUSE: OFF"
    )

    think_bx1 = panel_x + 14
    think_bx2 = panel_x + min(
        190,
        panel_w - 14
    )
    think_by1 = panel_y + 152
    think_by2 = panel_y + 180

    match_ui["thinking_toggle_rect"] = (
        think_bx1,
        think_by1,
        think_bx2,
        think_by2
    )

    cv2.rectangle(
        display_frame,
        (think_bx1, think_by1),
        (think_bx2, think_by2),
        (38, 45, 60),
        -1
    )

    cv2.rectangle(
        display_frame,
        (think_bx1, think_by1),
        (think_bx2, think_by2),
        active if thinking_enabled else inactive,
        2
    )

    think_size = cv2.getTextSize(
        think_label,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.34,
        1
    )[0]

    think_tx = think_bx1 + max(
        2,
        (think_bx2 - think_bx1 - think_size[0]) // 2
    )

    think_ty = think_by1 + max(
        think_size[1] + 2,
        ((think_by2 - think_by1) + think_size[1]) // 2
    )

    cv2.putText(
        display_frame,
        think_label,
        (think_tx, think_ty),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.34,
        text_main,
        1
    )

    labels = (
        (new_match_label, "new_match_toggle_rect"),
        (rematch_label, "rematch_toggle_rect")
    )

    gap = 10
    button_h = 32
    usable_w = panel_w - 28
    button_w = max(
        150,
        int((usable_w - gap) / 2)
    )

    by = panel_y + 186

    for index, (label, rect_key) in enumerate(labels):
        bx1 = panel_x + 14 + index * (button_w + gap)
        bx2 = min(
            panel_x + panel_w - 14,
            bx1 + button_w
        )
        by2 = min(
            panel_y + panel_h - 10,
            by + button_h
        )

        match_ui[rect_key] = (
            bx1,
            by,
            bx2,
            by2
        )

        enabled = label.endswith(": ON")

        cv2.rectangle(
            display_frame,
            (bx1, by),
            (bx2, by2),
            (38, 45, 60),
            -1
        )

        cv2.rectangle(
            display_frame,
            (bx1, by),
            (bx2, by2),
            active if enabled else inactive,
            2
        )

        text_size = cv2.getTextSize(
            label,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.34,
            1
        )[0]

        tx = bx1 + max(
            2,
            (bx2 - bx1 - text_size[0]) // 2
        )

        ty = by + max(
            text_size[1] + 2,
            ((by2 - by) + text_size[1]) // 2
        )

        cv2.putText(
            display_frame,
            label,
            (tx, ty),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.34,
            text_main,
            1
        )




_SCREEN_MOVE_HISTORY_CACHE_KEY = None
_SCREEN_MOVE_HISTORY_CACHE_LINES = []


def move_history_lines_for_screen(board, max_plies=24):
    global _SCREEN_MOVE_HISTORY_CACHE_KEY
    global _SCREEN_MOVE_HISTORY_CACHE_LINES

    if board is None:
        return []

    key = tuple(
        move.uci()
        for move in board.move_stack
    )

    if key == _SCREEN_MOVE_HISTORY_CACHE_KEY:
        return _SCREEN_MOVE_HISTORY_CACHE_LINES

    temp = chess.Board(
        INITIAL_FEN
    )

    rows = []

    for index, move in enumerate(board.move_stack):
        try:
            san = temp.san(move)
        except Exception:
            san = move.uci()

        if index % 2 == 0:
            rows.append(
                f"{index // 2 + 1}. {san}"
            )
        else:
            rows[-1] += f" {san}"

        temp.push(move)

    keep_pairs = max(
        1,
        max_plies // 2
    )

    _SCREEN_MOVE_HISTORY_CACHE_KEY = key
    _SCREEN_MOVE_HISTORY_CACHE_LINES = rows[-keep_pairs:]

    return _SCREEN_MOVE_HISTORY_CACHE_LINES


def draw_move_history_panel(
    display_frame,
    board,
    board_coords,
    match_ui=None
):
    if match_ui is not None:
        match_ui["move_history_rect"] = None

    if board is None or board_coords is None:
        return

    lines = move_history_lines_for_screen(
        board
    )

    if not lines:
        return

    height, width = display_frame.shape[:2]
    bx, by, bw, bh = board_coords

    panel_w = min(
        300,
        max(230, width // 4)
    )
    panel_h = min(
        height - 20,
        44 + len(lines) * 19
    )

    board_rect = (
        bx,
        by,
        bx + bw,
        by + bh
    )

    controls_rect = (
        match_ui.get("controls_rect")
        if match_ui is not None
        else None
    )

    candidates = []

    # Prefer the dedicated right-side UI canvas when the match controls are there.
    if (
        controls_rect is not None
        and controls_rect[0] >= bx + bw + 12
    ):
        candidates.extend([
            (
                controls_rect[0],
                controls_rect[3] + 12
            ),
            (
                controls_rect[0],
                max(
                    8,
                    controls_rect[1] - panel_h - 12
                )
            ),
        ])

    candidates.extend([
        (bx - panel_w - 12, max(52, by)),
        (bx + bw + 12, max(52, by)),
        (max(8, bx), max(8, by - panel_h - 12)),
        (max(8, bx), min(height - panel_h - 8, by + bh + 12)),
    ])

    def overlaps(a, b):
        if b is None:
            return False
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        return not (
            ax2 <= bx1
            or ax1 >= bx2
            or ay2 <= by1
            or ay1 >= by2
        )

    panel_x, panel_y = candidates[0]

    for cx, cy in candidates:
        rect = (
            cx,
            cy,
            cx + panel_w,
            cy + panel_h
        )

        if (
            cx >= 4
            and cy >= 4
            and cx + panel_w <= width - 4
            and cy + panel_h <= height - 4
            and not overlaps(rect, board_rect)
            and not overlaps(rect, controls_rect)
        ):
            panel_x, panel_y = cx, cy
            break

    panel_x = max(
        4,
        min(width - panel_w - 4, panel_x)
    )
    panel_y = max(
        4,
        min(height - panel_h - 4, panel_y)
    )

    if match_ui is not None:
        match_ui["move_history_rect"] = (
            panel_x,
            panel_y,
            panel_x + panel_w,
            panel_y + panel_h
        )

    # Separate, clean move-history panel palette.
    bg = (28, 32, 46)
    border = (190, 135, 255)
    header = (215, 165, 255)
    text_main = (245, 248, 255)

    overlay = display_frame.copy()

    cv2.rectangle(
        overlay,
        (panel_x, panel_y),
        (
            min(width - 8, panel_x + panel_w),
            min(height - 8, panel_y + panel_h)
        ),
        bg,
        -1
    )

    display_frame[:] = cv2.addWeighted(
        overlay,
        0.94,
        display_frame,
        0.06,
        0
    )

    cv2.rectangle(
        display_frame,
        (panel_x, panel_y),
        (
            min(width - 8, panel_x + panel_w),
            min(height - 8, panel_y + panel_h)
        ),
        border,
        2
    )

    cv2.putText(
        display_frame,
        "MOVES",
        (panel_x + 12, panel_y + 23),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.47,
        header,
        1
    )

    for row_index, line in enumerate(lines):
        cv2.putText(
            display_frame,
            line,
            (
                panel_x + 12,
                panel_y + 45 + row_index * 19
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.37,
            text_main,
            1
        )





MATCH_BOARD_VISIBILITY_THRESHOLD = 0.30
MATCH_BOARD_OBSTRUCTION_CHANGE = 0.050

# Direct old-game -> new-game recovery without requiring a result screen.
# A fresh board reset changes many squares at once; normal chess moves do not.
MATCH_NEW_GAME_RESET_CHANGED_SQUARES = 8
MATCH_NEW_GAME_RESET_CHANGE_MIN = 0.050

MATCH_NEW_GAME_CHECK_INTERVAL = 0.10
MATCH_NEW_GAME_MIN_EXACT = 58
MATCH_NEW_GAME_MIN_DETECTED_PIECES = 20
MATCH_NEW_GAME_MAX_DETECTED_PIECES = 40
MATCH_NEW_GAME_CONFIRM_DELAY = 0.0


def match_board_obstruction_ratio(
    before_frame,
    current_frame,
    board_coords,
    black_perspective
):
    if (
        before_frame is None
        or current_frame is None
        or board_coords is None
    ):
        return 0.0

    changes = fast_square_motion_scores(
        before_frame,
        current_frame,
        board_coords,
        black_perspective
    )

    if changes is None:
        return 0.0

    return sum(
        1
        for score in changes.values()
        if score >= MATCH_BOARD_OBSTRUCTION_CHANGE
    ) / 64.0


def _new_game_screen_exact_count(
    grid,
    confidence,
    candidate_board,
    black_perspective
):
    observed = grid_conf_dict(
        grid,
        confidence,
        black_perspective
    )

    exact = 0

    for square in chess.SQUARES:
        observed_symbol, _ = observed.get(
            square,
            (None, 999.0)
        )

        piece = candidate_board.piece_at(
            square
        )

        expected_symbol = (
            piece.symbol()
            if piece is not None
            else None
        )

        if observed_symbol == expected_symbol:
            exact += 1

    return exact


def _new_game_expected_fallback_exact_count(
    frame,
    candidate_board,
    board_coords,
    black_perspective
):
    """Re-check mismatched occupied squares using the expected piece.

    Keep the normal 64-square exact score as the base. Only repair occupied
    squares where the generic classifier confused a visually similar piece.
    Empty-square mismatches remain mismatches, so this cannot turn a generic
    UI frame into a valid chess position.
    """
    if frame is None:
        return 0

    grid, confidence, _ = scan_board(
        frame,
        board_coords
    )

    observed = grid_conf_dict(
        grid,
        confidence,
        black_perspective
    )

    templates = get_scaled_templates(
        board_coords[2] / 8.0,
        board_coords[3] / 8.0
    )

    exact = 0

    for square in chess.SQUARES:
        observed_symbol, _ = observed.get(
            square,
            (None, 999.0)
        )

        piece = candidate_board.piece_at(
            square
        )

        expected_symbol = (
            piece.symbol()
            if piece is not None
            else None
        )

        if observed_symbol == expected_symbol:
            exact += 1
            continue

        if expected_symbol is None:
            continue

        crop = get_square_crop(
            frame,
            board_coords,
            square,
            black_perspective
        )

        expected_detected, _ = classify_square(
            crop,
            templates,
            expected_symbol=expected_symbol,
            match_threshold=FULL_BOARD_EXPECTED_MATCH_THRESHOLD
        )

        if expected_detected == expected_symbol:
            exact += 1

    return exact

def _new_game_detected_piece_count(
    grid,
    confidence,
    black_perspective
):
    """Count occupied squares reported by the board scan.

    Matchmaking must reject sparse false matches, but it should not reject a
    real board merely because a few extra UI pixels were classified as a
    piece. The strict START / START+WHITE-MOVE verification below remains the
    actual acceptance gate.
    """
    return sum(
        1
        for row in grid
        for symbol in row
        if symbol is not None
    )


def detect_new_game_state(
    sct,
    hwnd,
    board_coords,
    source_frame=None
):
    if board_coords is None:
        return None

    frame = (
        source_frame
        if source_frame is not None
        else capture_screen(
            sct,
            hwnd
        )
    )

    if frame is None:
        return None

    grid, confidence, scan_ms = scan_board(
        frame,
        board_coords
    )

    if grid is None:
        return None

    detected_piece_count = _new_game_detected_piece_count(
        grid,
        confidence,
        False
    )

    # Do not reject here solely because the generic piece classifier missed
    # some pieces. The definitive gate below is the 64-square position match;
    # a blank/searching screen cannot reach that exactness level.
    start_board = chess.Board(
        INITIAL_FEN
    )

    candidates = [
        (
            0,
            None,
            start_board
        )
    ]

    # The fresh match may already contain White's first move. Preserve the
    # existing project behavior and consider every legal White first move,
    # regardless of which color is assigned to Stockfish.
    for move in start_board.legal_moves:
        candidates.append(
            (
                1,
                move,
                expected_board_after_move(
                    start_board,
                    move
                )
            )
        )

    scored = []

    # IMPORTANT: do not trust detect_board_orientation() here. On a blank or
    # partially rendered screen it can choose the wrong perspective from a
    # handful of false template matches. Score both orientations and let the
    # fully verified candidate decide.
    for perspective in (
        False,
        True
    ):
        for kind, first_move, candidate_board in candidates:
            exact = _new_game_screen_exact_count(
                grid,
                confidence,
                candidate_board,
                perspective
            )

            scored.append(
                (
                    exact,
                    kind,
                    first_move,
                    candidate_board,
                    perspective
                )
            )

    scored.sort(
        reverse=True,
        key=lambda item: (
            item[0],
            item[1]
        )
    )

    exact, kind, first_move, candidate_board, perspective = scored[0]

    # Recover the common rook/bishop (or similar-template) scan confusion on
    # the single strongest candidate instead of rejecting the real board.
    if exact < MATCH_NEW_GAME_MIN_EXACT:
        fallback_exact = _new_game_expected_fallback_exact_count(
            frame,
            candidate_board,
            board_coords,
            perspective
        )

        if fallback_exact > exact:
            exact = fallback_exact

    if exact < MATCH_NEW_GAME_MIN_EXACT:
        full_ok, full_reason = full_board_state_confirmed(
            frame,
            candidate_board,
            board_coords,
            perspective
        )

        if full_ok:
            exact = 64
            progress(
                "MATCH",
                (
                    "new-game candidate recovered by "
                    f"full-board verification | perspective="
                    f"{'BLACK' if perspective else 'WHITE'}"
                ),
                key="new_match_full_board_recovery",
                interval=0.50
            )
        else:
            fallback_exact = _new_game_expected_fallback_exact_count(
                frame,
                candidate_board,
                board_coords,
                perspective
            )

            if fallback_exact > exact:
                exact = fallback_exact

    if exact < MATCH_NEW_GAME_MIN_EXACT:
        progress(
            "MATCH",
            (
                "board candidate rejected | "
                f"pieces={detected_piece_count} "
                f"best_exact={exact}/64 "
                f"perspective={'BLACK' if perspective else 'WHITE'}"
            ),
            key="new_match_candidate_reject",
            interval=0.50
        )
        return None

    stockfish_color_now = detect_bottom_stockfish_color(
        perspective
    )

    human_color_now = (
        chess.BLACK
        if stockfish_color_now == chess.WHITE
        else chess.WHITE
    )

    turn_ok, turn_reason = validate_new_game_turn_state(
        candidate_board,
        stockfish_color_now,
        human_color_now,
        first_move
    )

    if not turn_ok:
        progress(
            "MATCH",
            f"new-game candidate rejected | {turn_reason}",
            key="new_match_turn_reject",
            interval=0.50,
            force=True
        )
        return None

    print(
        "[MATCH] NEW GAME TURN CHECK | "
        f"{turn_reason}"
    )

    first_reason = (
        f"new-game candidate exact={exact}/64 "
        f"pieces={detected_piece_count}/32"
    )

    time.sleep(
        MATCH_NEW_GAME_CONFIRM_DELAY
    )

    confirm_frame = capture_screen(
        sct,
        hwnd
    )

    if confirm_frame is None:
        return None

    confirm_grid, confirm_confidence, _ = scan_board(
        confirm_frame,
        board_coords
    )

    if confirm_grid is None:
        return None

    confirm_piece_count = _new_game_detected_piece_count(
        confirm_grid,
        confirm_confidence,
        perspective
    )

    if confirm_piece_count < MATCH_NEW_GAME_MIN_DETECTED_PIECES:
        return None

    confirm_exact = _new_game_screen_exact_count(
        confirm_grid,
        confirm_confidence,
        candidate_board,
        perspective
    )

    if confirm_exact < MATCH_NEW_GAME_MIN_EXACT:
        confirm_full_ok, confirm_full_reason = full_board_state_confirmed(
            confirm_frame,
            candidate_board,
            board_coords,
            perspective
        )

        if confirm_full_ok:
            confirm_exact = 64
        else:
            confirm_exact_fallback = (
                _new_game_expected_fallback_exact_count(
                    confirm_frame,
                    candidate_board,
                    board_coords,
                    perspective
                )
            )

            if confirm_exact_fallback > confirm_exact:
                confirm_exact = confirm_exact_fallback

    if confirm_exact < MATCH_NEW_GAME_MIN_EXACT:
        progress(
            "MATCH",
            (
                "candidate changed before confirmation | "
                f"first={exact}/64 confirm={confirm_exact}/64 "
                f"pieces={confirm_piece_count}"
            ),
            key="new_match_confirm_reject",
            interval=0.50
        )
        return None

    # Re-check for White's first move after confirmation. This handles the
    # race where the fresh board is detected at START, but White has already
    # moved before the state machine reaches its turn-processing block.
    (
        candidate_board,
        detected_first_move,
        first_move_frame,
        first_move_grid
    ) = refresh_white_first_move_after_new_game(
        sct,
        hwnd,
        candidate_board,
        stockfish_color_now,
        human_color_now,
        board_coords,
        perspective,
        first_move
    )

    if detected_first_move is not None:
        first_move = detected_first_move
        kind = 1

        if first_move_frame is not None:
            confirm_frame = first_move_frame

        if first_move_grid is not None:
            confirm_grid = first_move_grid

        # Re-verify the final synchronized first-move position against the
        # physical frame that will become baseline_frame.
        final_ok, final_reason = full_board_state_confirmed(
            confirm_frame,
            candidate_board,
            board_coords,
            perspective
        )

        if not final_ok:
            progress(
                "MATCH",
                f"WHITE first move lost during final sync | {final_reason}",
                key="new_match_first_move_final_reject",
                interval=0.50,
                force=True
            )
            return None

        confirm_exact = 64

        second_reason = (
            "confirm synchronized WHITE first move position exact=64/64 "
            f"pieces={confirm_piece_count}/32"
        )
    else:
        second_reason = (
            f"confirm exact={confirm_exact}/64 "
            f"pieces={confirm_piece_count}/32"
        )

    turn_ok, turn_reason = validate_new_game_turn_state(
        candidate_board,
        stockfish_color_now,
        human_color_now,
        first_move
    )

    if not turn_ok:
        progress(
            "MATCH",
            f"new-game post-probe rejected | {turn_reason}",
            key="new_match_post_probe_turn_reject",
            interval=0.50,
            force=True
        )
        return None

    return {
        "frame": confirm_frame,
        "grid": confirm_grid,
        "scan_ms": scan_ms,
        "perspective": perspective,
        "stockfish_color": stockfish_color_now,
        "human_color": human_color_now,
        "board": candidate_board,
        "first_move": first_move,
        "kind": (
            "START"
            if kind == 0
            else "WHITE_MOVE"
        ),
        "exact": exact,
        "reason": (
            f"{first_reason}; second={second_reason}"
        )
    }


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
# STOCKFISH MULTI-PV TRAINING
# ============================================================
# The earlier full system used MultiPV=15 after the GM book ends.
# The existing fast selection/recovery logic remains unchanged; only
# the candidate count is restored to the original 15-line search.
TRAINING_MULTI_PV = 15
FORCE_BEST_MIN_CP = 200
FORCE_BEST_IMPROVEMENT_FRACTION = 0.65

# Human-like advantage shaping. Once the bot is clearly winning,
# keep the winning level for a short run, then grow the advantage only
# when Stockfish actually finds a stronger position. Growth is progressive,
# while the current advantage is protected from large unnecessary drops.
HUMAN_ADVANTAGE_START_CP = 400
HUMAN_ADVANTAGE_LIGHT_DROP_CP = 70
HUMAN_ADVANTAGE_NORMAL_DROP_CP = 45
HUMAN_ADVANTAGE_RECOVER_CP = 15
HUMAN_ADVANTAGE_MIN_TARGET_CP = 300
BOT_MAX_RANK2_DROP_CP = 50
BOT_MAX_RANK3_DROP_CP = 35
BOT_MAX_RANK4_DROP_CP = 70
BOT_MAX_RANK5_DROP_CP = 80
BOT_MAX_RANK6_DROP_CP = 90
BOT_MAX_RANK7_DROP_CP = 100
BOT_MAX_RANK8_DROP_CP = 110
HUMAN_ADVANTAGE_MAINTAIN_BAND_CP = 30
HUMAN_ADVANTAGE_PROTECT_BAND_CP = 30
HUMAN_ADVANTAGE_HOLD_MIN_MOVES = 1
HUMAN_ADVANTAGE_HOLD_MAX_MOVES = 3
HUMAN_ADVANTAGE_GROWTH_STEP_MIN_CP = 20
HUMAN_ADVANTAGE_GROWTH_STEP_MAX_CP = 45
HUMAN_ADVANTAGE_GROWTH_TRIGGER_CP = 15

# Winning-position guard:
# Human-like selection is allowed, but once there is a real advantage it must
# not throw away a large part of the advantage or voluntarily hang a major piece.
HUMAN_WINNING_GUARD_START_CP = 60
HUMAN_WINNING_GUARD_MAX_DROP_CP = 45
HUMAN_WINNING_GUARD_RANK_CAP = 5
HUMAN_STRONG_WINNING_CP = 300
HUMAN_STRONG_WINNING_RANK_CAP = 3
HUMAN_WINNING_NON_BEST_CHANCE = 0.45
HUMAN_STRONG_WINNING_NON_BEST_CHANCE = 0.25
FREE_CAPTURE_MIN_VALUE = 3
FREE_CAPTURE_MAX_CP_DROP = 100
# Extra safety for genuinely free captures:
# after taking the piece, do not allow a line that gives up a major/minor
# piece in the next 1-2 opponent moves or enters a forced mate M1-M5.
FREE_CAPTURE_SAFETY_DEPTH = 10
FREE_CAPTURE_SAFETY_MAX_CP_DROP = 250
FREE_CAPTURE_SAFETY_MAX_PLY = 4

# Once a forced mate reaches M5, stop humanizing it away and finish quickly.
MATE_FORCE_FAST_MAX = 5

# Human-like mate handling remains active for M6-M15. M5 and below are
# considered a real finishing opportunity and use the fastest mate.
MATE_GRACE_MIN = 6
MATE_GRACE_MAX = 15
MATE_SUSTAIN_MIN_MOVES = 2
MATE_SUSTAIN_MAX_MOVES = 3
MATE_SLOWER_LINE_CHANCE = 0.35

# During the early/normal game, allow a wider human-like selection band so
# #1/#2 do not dominate simply because all other MultiPV lines are a few
# centipawns lower. The underlying engine search remains MultiPV=15.
HUMAN_SELECTION_EXTRA_DROP_CP = 70
HUMAN_SELECTION_DISTANCE_CP = 80.0
HUMAN_SELECTION_NON_BEST_CHANCE = 0.88

# In normal human-like selection, do not let #1/#2 dominate when #3+
# alternatives are safely available. Forced mate / forced-best / explicit
# punishment paths remain unchanged.
HUMAN_SELECTION_TOP12_MAX_CHANCE = 0.10

# In the mating phase, first take genuinely free material when it is safe.
# Once the opponent has only one non-king piece left, stop cleanup and mate.
MATE_CLEANUP_MAX_REMAINING_PIECES = 1
MATE_CLEANUP_MIN_VALUE = 1

_mate_progress_target_mate = None
_mate_progress_hold_moves = 0
_mate_progress_hold_limit = 2

_advantage_progress_target_cp = None

_advantage_target_cp = None
_advantage_hold_moves = 0
_advantage_hold_limit = 2
_advantage_last_selected_cp = None
_advantage_light_drop_used = False
_advantage_down_streak = 0
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

if os.name == "nt":
    _ULONG_PTR = (
        ctypes.c_ulonglong
        if ctypes.sizeof(ctypes.c_void_p) == 8
        else ctypes.c_ulong
    )

    class _MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", _ULONG_PTR),
        ]

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [
            ("mi", _MOUSEINPUT),
        ]

    class _INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [
            ("type", wintypes.DWORD),
            ("u", _INPUT_UNION),
        ]

    try:
        user32.SendInput.argtypes = [
            wintypes.UINT,
            ctypes.POINTER(_INPUT),
            ctypes.c_int,
        ]
        user32.SendInput.restype = wintypes.UINT
    except Exception:
        pass

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
_last_bot_natural_delay = None
_bot_timing_move_count = 0
_thinking_budget_remaining = None
_thinking_budget_total = None
_thinking_move_cooldown_remaining = 0
_mate_pause_used = False


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


def _sendinput_mouse_flag(flag):
    if not user32 or os.name != "nt" or "_INPUT" not in globals():
        return False

    try:
        inp = _INPUT()
        inp.type = 0
        inp.mi.dx = 0
        inp.mi.dy = 0
        inp.mi.mouseData = 0
        inp.mi.dwFlags = int(flag)
        inp.mi.time = 0
        inp.mi.dwExtraInfo = 0

        sent = user32.SendInput(
            1,
            ctypes.byref(inp),
            ctypes.sizeof(_INPUT)
        )
        return int(sent) == 1
    except Exception:
        return False


def left_click_screen(x, y, hold_seconds=0.020):
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.004)

    if _sendinput_mouse_flag(MOUSEEVENTF_LEFTDOWN):
        time.sleep(max(0.0, float(hold_seconds)))

        if _sendinput_mouse_flag(MOUSEEVENTF_LEFTUP):
            return True

        try:
            user32.mouse_event(
                MOUSEEVENTF_LEFTUP,
                0,
                0,
                0,
                0
            )
        except Exception:
            pass

        return False

    user32.mouse_event(
        MOUSEEVENTF_LEFTDOWN,
        0,
        0,
        0,
        0
    )
    time.sleep(max(0.0, float(hold_seconds)))
    user32.mouse_event(
        MOUSEEVENTF_LEFTUP,
        0,
        0,
        0,
        0
    )
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


def board_to_display_grid(
    board,
    black_perspective=False
):
    """Build the overlay grid directly from the already-verified chess board."""
    grid = [
        [None for _ in range(8)]
        for _ in range(8)
    ]

    for square, piece in board.piece_map().items():
        file_ = chess.square_file(square)
        rank_ = chess.square_rank(square)

        if black_perspective:
            col = 7 - file_
            row = rank_
        else:
            col = file_
            row = 7 - rank_

        grid[row][col] = piece.symbol()

    return grid


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
    allow_fallback=True,
    before_board=None
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

    # Promotion menu order is deterministic: QUEEN, ROOK, BISHOP, KNIGHT.
    # Never choose among all four slots by "best Q-like template" score.
    # A bishop can occasionally produce a numerically better Q-template match
    # than the real queen slot, which can send the click to the wrong piece.
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
        index is None
        or index >= len(candidates)
    ):
        return None

    expected_square = candidates[index]

    expected_crop = get_square_crop(
        frame,
        board_coords,
        expected_square,
        black_perspective
    )

    if expected_crop is not None:
        detected, score = classify_square(
            expected_crop,
            templates,
            expected_symbol=expected
        )

        if detected == expected:
            print(
                f"[PROMOTION] exact slot confirmed "
                f"{expected} score={score:.3f}"
            )
            return expected_square

    # During normal promotion selection we still use the deterministic slot
    # even when template confirmation is weak; the slot itself is known from
    # the promotion direction/menu order. During recovery (allow_fallback=False)
    # we do not click blindly when the expected piece is not visually found.
    if allow_fallback and PROMOTION_FALLBACK:
        print(
            f"[PROMOTION] deterministic slot selected {expected}"
        )
        return expected_square

    return None


def select_promotion_piece(
    sct,
    hwnd,
    move,
    promotion_color,
    board_coords,
    black_perspective,
    allow_fallback=True,
    before_board=None
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
        # IMPORTANT: a previous promotion click may already have succeeded even
        # when the first confirmation window missed the settled frame. Before
        # clicking again, check whether the exact final position is already on
        # screen. Never treat a click itself as confirmation.
        settled_frame = capture_screen(
            sct,
            hwnd
        )

        if settled_frame is not None:
            target_crop = get_square_crop(
                settled_frame,
                board_coords,
                move.to_square,
                black_perspective
            )
            source_crop = get_square_crop(
                settled_frame,
                board_coords,
                move.from_square,
                black_perspective
            )

            templates = get_scaled_templates(
                board_coords[2] / 8.0,
                board_coords[3] / 8.0
            )

            settled_target, settled_score = classify_square(
                target_crop,
                templates,
                expected_symbol=expected,
                match_threshold=BOT_POST_MATCH_THRESHOLD
            )
            settled_source, _ = classify_square(
                source_crop,
                templates
            )

            settled_exact = (
                settled_target == expected
                and settled_source is None
            )

            settled_full = False
            settled_full_reason = "full-board reference unavailable"

            if settled_exact and before_board is not None:
                settled_full, settled_full_reason = (
                    full_board_state_confirmed(
                        settled_frame,
                        expected_board_after_move(
                            before_board,
                            move
                        ),
                        board_coords,
                        black_perspective
                    )
                )

            if settled_exact and settled_full:
                progress(
                    "PROMOTION",
                    (
                        f"already confirmed on board: "
                        f"{piece_name} ({settled_score:.3f}); "
                        f"{settled_full_reason}"
                    ),
                    key="promotion_stage",
                    force=True
                )
                return True

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

        click_sent = left_click_screen(
            px,
            py
        )

        if not click_sent:
            progress(
                "PROMOTION",
                (
                    f"{piece_name} input dispatch failed; "
                    f"attempt {attempt}/{PROMOTION_RETRIES}"
                ),
                key="promotion_loop",
                force=True
            )
            continue

        # A successful input dispatch is NOT a successful promotion.
        # Confirmation requires the exact promoted piece on the destination,
        # the source square to be empty, and the complete expected board state.
        promotion_ok = False
        promotion_reason = "promotion state not yet confirmed"
        promotion_streak = 0
        promotion_deadline = (
            time.perf_counter()
            + PROMOTION_CONFIRM_TIMEOUT
        )

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

            exact_transition_ok = (
                detected_piece == expected
                and source_piece is None
            )

            full_ok = False
            full_reason = "not yet full-board confirmed"

            if exact_transition_ok and before_board is not None:
                # Final authority: complete physical board must match the
                # expected post-promotion position.
                full_ok, full_reason = full_board_state_confirmed(
                    check_frame,
                    expected_board_after_move(
                        before_board,
                        move
                    ),
                    board_coords,
                    black_perspective
                )

            if (
                exact_transition_ok
                and before_board is not None
                and full_ok
            ):
                promotion_streak += 1
                promotion_reason = (
                    f"source=empty destination={expected} "
                    f"({detected_score:.3f}); {full_reason}"
                )

                if promotion_streak >= PROMOTION_CONFIRM_FRAMES:
                    promotion_ok = True
                    break
            else:
                promotion_streak = 0
                if exact_transition_ok:
                    promotion_reason = (
                        f"piece visible but full-board not confirmed: "
                        f"{full_reason}"
                    )
                else:
                    promotion_reason = (
                        f"destination/source not confirmed "
                        f"({detected_piece or '-'}:{detected_score:.3f})"
                    )

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
    promotion_color=None,
    before_frame=None,
    before_board=None
):
    if not focus_scrcpy(scrcpy_hwnd):
        print(
            "[BOT ERROR] Could not focus scrcpy window."
        )
        return False

    screen_origin = get_scrcpy_screen_origin(
        scrcpy_hwnd
    )
    if screen_origin is None:
        print(
            "[BOT ERROR] Could not determine scrcpy screen origin."
        )
        return False

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

    user32.SetCursorPos(0, 0)

    if not left_click_screen(
        sx,
        sy,
        hold_seconds=0.020
    ):
        print(
            "[BOT CLICK] SOURCE INPUT DISPATCH FAILED | "
            f"{move.uci()}"
        )
        return False

    if (
        sct is not None
        and before_frame is not None
    ):
        source_ok, source_reason = (
            _verify_source_click_selected(
                sct,
                scrcpy_hwnd,
                move,
                before_frame,
                board_coords,
                black_perspective
            )
        )

        if not source_ok:
            print(
                "[BOT CLICK] SOURCE VISUAL NOT CONFIRMED | "
                f"{move.uci()} | {source_reason} | continuing to target"
            )

    source_target_delay = random.uniform(
        BOT_SOURCE_TO_TARGET_DELAY_MIN,
        BOT_SOURCE_TO_TARGET_DELAY_MAX
    )

    print(
        "[BOT GESTURE] "
        f"source->target gap={source_target_delay:.3f}s"
    )

    time.sleep(source_target_delay)

    if not left_click_screen(
        tx,
        ty,
        hold_seconds=0.020
    ):
        print(
            "[BOT CLICK] TARGET INPUT DISPATCH FAILED | "
            f"{move.uci()}"
        )
        return False

    user32.SetCursorPos(0, 0)

    if move.promotion is not None:
        if promotion_color is None:
            promotion_color = chess.WHITE

        if sct is None:
            print(
                "[PROMOTION ERROR] "
                "Screen capture context unavailable."
            )
            return False

        return select_promotion_piece(
            sct,
            scrcpy_hwnd,
            move,
            promotion_color,
            board_coords,
            black_perspective,
            before_board=before_board
        )

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

        # Safety gate: motion at the source is not enough to prove the piece
        # actually left. The source square must now classify as empty.
        source_empty_ok, source_detected, source_score = expected_piece_at(
            after_frame,
            move.from_square,
            None
        )
        if not source_empty_ok:
            return False, (
                f"source still occupied "
                f"({source_detected or '-'}:{source_score:.3f})"
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
        if len(board.move_stack) == 0:
            return True, (
                "initial-position source template miss tolerated "
                f"({source_detected or '-'} != {source_piece.symbol()}); "
                "motion map and destination safety passed"
            )
        return False, (
            f"source mismatch {source_detected or '-'} "
            f"!= {source_piece.symbol()}"
        )

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

    # Recovery must stay on the fast closed-loop path. The fast verifier
    # already checks that only allowed squares moved, the destination contains
    # the exact expected piece, and the source is now empty.
    return True, fast_reason


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
                _bot_timing_move_count > BOT_OPENING_FAST_VERIFY_MOVES
                and (
                    board.is_capture(move)
                    or board.is_castling(move)
                    or move.promotion is not None
                )
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


def refresh_white_first_move_after_new_game(
    sct,
    hwnd,
    board,
    stockfish_color_now,
    human_color_now,
    board_coords,
    perspective,
    first_move=None
):
    """
    After the fresh board is accepted, give White one immediate verification
    pass before deciding to wait.

    Returns:
        (board, first_move, frame, grid)
    so the physical baseline is kept synchronized with the logical board when
    White has already made the first move.
    """
    if (
        human_color_now != chess.WHITE
        or first_move is not None
        or board is None
        or board.move_stack
        or board.turn != chess.WHITE
    ):
        return board, first_move, None, None

    probe_frame = capture_screen(
        sct,
        hwnd
    )

    if probe_frame is None:
        return board, first_move, None, None

    detected_first = detect_existing_white_first_move(
        probe_frame,
        board,
        board_coords,
        perspective
    )

    if detected_first is None:
        return board, first_move, None, None

    expected_board = expected_board_after_move(
        board,
        detected_first
    )

    try:
        ok, reason = full_board_state_confirmed(
            probe_frame,
            expected_board,
            board_coords,
            perspective
        )
    except Exception:
        ok = False
        reason = "first-move full-board verification failed"

    if not ok:
        print(
            "[MATCH] WHITE FIRST-MOVE PROBE REJECTED | "
            f"{detected_first.uci()} | {reason}"
        )
        return board, first_move, None, None

    probe_grid, _, _ = scan_board(
        probe_frame,
        board_coords
    )

    try:
        san = board.san(
            detected_first
        )
    except Exception:
        san = detected_first.uci()

    board = expected_board

    print(
        "[MATCH] WHITE MOVE ALREADY PRESENT | "
        f"{detected_first.uci()} {san} | "
        "fresh-game first-move probe confirmed"
    )

    return (
        board,
        detected_first,
        probe_frame,
        probe_grid
    )



def validate_new_game_turn_state(
    board,
    stockfish_color_now,
    human_color_now,
    first_move=None
):
    """
    Explicitly validate who must move first after every fresh-game reset.

    Chess always starts with White. Therefore:
      - Human = WHITE  -> Human must move first (unless White's first move
                         is already visible, in which case Stockfish moves next).
      - Human = BLACK  -> Stockfish/White must move first.
    """
    if board is None:
        return False, "board is None"

    if stockfish_color_now not in (chess.WHITE, chess.BLACK):
        return False, "invalid Stockfish color"

    if human_color_now not in (chess.WHITE, chess.BLACK):
        return False, "invalid Human color"

    if stockfish_color_now == human_color_now:
        return False, "Stockfish/Human colors are identical"

    # The legal first move in chess is always White's move. The returned
    # candidate board may already contain that move.
    expected_turn = (
        chess.BLACK
        if first_move is not None
        else chess.WHITE
    )

    if board.turn != expected_turn:
        return (
            False,
            (
                "new-game turn mismatch | "
                f"board_turn={'WHITE' if board.turn == chess.WHITE else 'BLACK'} "
                f"expected={'WHITE' if expected_turn == chess.WHITE else 'BLACK'}"
            )
        )

    first_player = (
        "STOCKFISH"
        if board.turn == stockfish_color_now
        else "HUMAN"
        if board.turn == human_color_now
        else "INVALID"
    )

    if first_player == "INVALID":
        return False, "board turn belongs to neither player"

    # Before White has moved, the owner of White determines the first actor.
    if first_move is None:
        expected_first_player = (
            "HUMAN"
            if human_color_now == chess.WHITE
            else "STOCKFISH"
        )

        if first_player != expected_first_player:
            return (
                False,
                (
                    "first-player mismatch | "
                    f"Human={'WHITE' if human_color_now == chess.WHITE else 'BLACK'} "
                    f"Stockfish={'WHITE' if stockfish_color_now == chess.WHITE else 'BLACK'} "
                    f"expected_first={expected_first_player} "
                    f"actual_first={first_player}"
                )
            )

    # After White's first move is already on screen, the turn MUST be Black.
    # Ownership of Black decides who acts next.
    next_player = first_player

    return (
        True,
        (
            f"first={'WHITE' if human_color_now == chess.WHITE else 'STOCKFISH/WHITE'} "
            f"| next={next_player} "
            f"| Human={'WHITE' if human_color_now == chess.WHITE else 'BLACK'} "
            f"| Stockfish={'WHITE' if stockfish_color_now == chess.WHITE else 'BLACK'}"
        )
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


def natural_bot_move_delay(
    board,
    move,
    engine_result=None,
    selection_meta=None,
    moves_since_buffer=0,
    thinking_enabled=BOT_THINKING_ENABLED_DEFAULT,
    previous_eval_white_cp=None
):
    """Return the retained base delay plus irregular human-like pauses.

    Cadence rules:
      * first 10 bot moves: no long pause
      * after a real pause: only 5-8 moves are guaranteed pause-free
      * after that, every move is reevaluated from the current position, so
        another pause can happen around 5-8 moves sometimes, or 10-12 moves
        later in other situations; there is no fixed N-move schedule
      * after move 50: normal pauses stop
      * after move 50, only one final pause is allowed when Stockfish has a
        mate-in-5..mate-in-1 opportunity; the exact mate distance is random
        by position, and the special mate pause is used at most once
      * regular pause time uses the existing 10-15 second game budget
    """
    global _last_bot_natural_delay
    global _bot_timing_move_count
    global _thinking_budget_remaining
    global _thinking_budget_total
    global _thinking_move_cooldown_remaining
    global _mate_pause_used

    if len(board.move_stack) <= 1:
        _bot_timing_move_count = 0
        _thinking_budget_total = random.uniform(
            BOT_THINK_BUDGET_MIN,
            BOT_THINK_BUDGET_MAX
        )
        _thinking_budget_remaining = _thinking_budget_total
        _thinking_move_cooldown_remaining = 0
        _mate_pause_used = False

    _bot_timing_move_count += 1

    # Existing tiny base delay remains unchanged.
    base_delay = random.uniform(
        BOT_EVERY_MOVE_DELAY_MIN,
        BOT_EVERY_MOVE_DELAY_MAX
    )
    delay = base_delay
    _last_bot_natural_delay = base_delay

    # First 10 bot moves: absolutely no long pause.
    if _bot_timing_move_count <= BOT_THINKING_START_AFTER_MOVE:
        return max(0.0, float(delay))

    if not thinking_enabled:
        return max(0.0, float(delay))

    # ============================================================
    # AFTER MOVE 50:
    # No normal thinking pauses anymore. The only allowed long pause
    # is one mate-in-5..mate-in-1 moment for the entire game.
    # ============================================================
    if _bot_timing_move_count > BOT_POST_50_MOVE:
        if _mate_pause_used:
            return max(0.0, float(delay))

        mate_distance = None

        if isinstance(engine_result, list):
            for info in engine_result:
                try:
                    score_obj = info.get("score")
                    if score_obj is None:
                        continue

                    mate_score = score_obj.pov(board.turn).mate()

                    if mate_score is None:
                        continue

                    mate_distance_abs = abs(int(mate_score))

                    if (
                        mate_distance_abs
                        <= BOT_MATE_PAUSE_MAX_MATE
                        and mate_distance_abs
                        >= BOT_MATE_PAUSE_MIN_MATE
                    ):
                        mate_distance = mate_distance_abs
                        break
                except Exception:
                    continue

        if mate_distance is None:
            return max(0.0, float(delay))

        pause_duration = random.uniform(
            BOT_MATE_PAUSE_MIN,
            BOT_MATE_PAUSE_MAX
        )

        _mate_pause_used = True

        # This is the single final mate pause. Keep it separate from the
        # ordinary pause budget because move-50+ is explicitly mate-only.
        delay += pause_duration

        print(
            "[BOT PAUSE] "
            f"duration={pause_duration:.3f}s "
            f"reason=MATE M{mate_distance} "
            f"move={_bot_timing_move_count} "
            "final_mate_pause=yes",
            flush=True
        )

        return max(0.0, float(delay))

    if (
        _thinking_budget_remaining is None
        or _thinking_budget_remaining <= BOT_THINK_PAUSE_MIN
    ):
        return max(0.0, float(delay))

    # Minimum move gap after every real pause.
    # The refractory length itself is randomized from 5-12 moves. This is
    # only a hard minimum; once it expires, the current position must still
    # pass the situation-based stochastic eligibility gate below.
    if _thinking_move_cooldown_remaining > 0:
        _thinking_move_cooldown_remaining -= 1
        return max(0.0, float(delay))

    signal_score = 0.0

    # Multiple reasonable moves / evaluation uncertainty from MultiPV.
    scores = []
    if isinstance(engine_result, list):
        for info in engine_result[:TRAINING_MULTI_PV]:
            try:
                score_obj = info.get("score")
                if score_obj is None:
                    continue

                cp = score_to_cp(
                    score_obj.pov(board.turn)
                )

                if cp is not None:
                    scores.append(int(cp))
            except Exception:
                continue

    if len(scores) >= 2:
        top_cp = scores[0]

        reasonable_count = sum(
            1
            for cp in scores
            if abs(cp - top_cp) <= BOT_THINK_REASONABLE_CP
        )

        if reasonable_count >= 2:
            signal_score += 0.34

        second_gap = abs(scores[1] - top_cp)

        if second_gap <= BOT_THINK_UNCERTAINTY_CP:
            signal_score += 0.24

    # Position immediately after a tactical/forcing change.
    if board.move_stack:
        try:
            previous_board = board.copy(stack=True)
            last_move = previous_board.pop()

            previous_was_tactical = (
                previous_board.is_capture(last_move)
                or previous_board.is_castling(last_move)
                or last_move.promotion is not None
                or previous_board.gives_check(last_move)
            )

            if previous_was_tactical:
                signal_score += 0.22
        except Exception:
            pass

    # Sharp evaluation change relative to the previous completed analysis.
    if (
        previous_eval_white_cp is not None
        and scores
    ):
        try:
            current_eval_white_cp = score_to_cp(
                engine_result[0]["score"].pov(chess.WHITE)
            )

            if (
                current_eval_white_cp is not None
                and abs(
                    int(current_eval_white_cp)
                    - int(previous_eval_white_cp)
                ) >= BOT_THINK_SHARP_EVAL_CP
            ):
                signal_score += 0.22
        except Exception:
            pass

    # Strategic decision point: many legal choices.
    try:
        legal_count = board.legal_moves.count()
    except Exception:
        legal_count = 0

    if legal_count >= BOT_THINK_STRATEGIC_LEGAL_MOVES:
        signal_score += 0.14

    # Strongly forcing current moves are poor pause candidates.
    try:
        forced_move = (
            board.is_check()
            or board.is_capture(move)
            or board.is_castling(move)
            or move.promotion is not None
            or board.gives_check(move)
        )
    except Exception:
        forced_move = False

    if forced_move:
        signal_score *= 0.35

    if signal_score <= 0.0:
        return max(0.0, float(delay))

    # Position-dependent random eligibility.
    #
    # Important: there is NO target like "pause again at move 8/10/12".
    # The 5-8 block above is only a hard minimum. Once it expires, this
    # stochastic position gate is evaluated independently on each move.
    # Weak/quiet positions tend to wait longer; genuinely rich positions
    # can pause soon after the minimum block.
    eligibility = min(
        BOT_THINK_ELIGIBILITY_MAX,
        max(
            BOT_THINK_ELIGIBILITY_MIN,
            (
                BOT_THINK_ELIGIBILITY_MIN
                + signal_score * BOT_PAUSE_ELIGIBILITY_SCALE
            )
        )
    )

    if random.random() >= eligibility:
        return max(0.0, float(delay))

    # Budget safety.
    if _thinking_budget_remaining <= BOT_THINK_PAUSE_MIN:
        return max(0.0, float(delay))

    pause_max = min(
        BOT_THINK_PAUSE_MAX,
        float(_thinking_budget_remaining)
    )

    if pause_max < BOT_THINK_PAUSE_MIN:
        return max(0.0, float(delay))

    pause_duration = random.uniform(
        BOT_THINK_PAUSE_MIN,
        pause_max
    )

    _thinking_budget_remaining = max(
        0.0,
        float(_thinking_budget_remaining) - pause_duration
    )

    # Only the randomized refractory minimum is set here. The next
    # pause is NOT scheduled for a specific move; after this block, the
    # current position must pass a fresh situation-based eligibility test.
    _thinking_move_cooldown_remaining = random.randint(
        BOT_PAUSE_MOVE_COOLDOWN_MIN,
        BOT_PAUSE_MOVE_COOLDOWN_MAX
    )

    delay += pause_duration

    print(
        "[BOT PAUSE] "
        f"duration={pause_duration:.3f}s "
        f"remaining_budget={_thinking_budget_remaining:.3f}s "
        f"next_pause_block={_thinking_move_cooldown_remaining} moves "
        f"eligibility={eligibility:.2f} "
        f"move={_bot_timing_move_count}",
        flush=True
    )

    return max(0.0, float(delay))
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
    max_rank = TRAINING_MULTI_PV - 1

    if (
        opponent_accuracy is None
        or sample_count < OPPONENT_MIN_SAMPLES
    ):
        return {
            "opponent_accuracy": opponent_accuracy,
            "target_accuracy": 88.0,
            "max_rank": max_rank,
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
        max_eval_drop = 0.18
        state = "OPPONENT LIGHT"

    elif score < 80.0:
        max_eval_drop = 0.14
        state = "OPPONENT MEDIUM"

    elif score < 88.0:
        max_eval_drop = 0.10
        state = "OPPONENT STRONG"

    elif score < ADAPTIVE_STRONG_THRESHOLD:
        max_eval_drop = 0.075
        state = "OPPONENT VERY STRONG"

    elif score < ADAPTIVE_VERY_STRONG_THRESHOLD:
        max_eval_drop = 0.050
        state = "OPPONENT ELITE"

    else:
        max_eval_drop = 0.035
        state = "OPPONENT EXTREME"

    return {
        "opponent_accuracy": score,
        "target_accuracy": target,
        "max_rank": max_rank,
        "max_eval_drop": max_eval_drop,
        "state": state,
    }


def find_free_mate_cleanup_capture(board, candidates):
    """Find a safe capture of free opponent material during mate play.

    A capture qualifies when the target contains a non-king opponent piece,
    the capturing piece cannot be legally recaptured on the destination
    square immediately after the capture, and the opponent still has more
    than one non-king piece overall. Prefer higher-value free material; for
    equal values prefer a move that is already present in MultiPV.
    """
    mover = board.turn
    candidate_map = {
        candidate["move"]: candidate
        for candidate in candidates
    }

    opponent_material = sum(
        1
        for piece in board.piece_map().values()
        if (
            piece.color != mover
            and piece.piece_type != chess.KING
        )
    )

    if (
        opponent_material
        <= MATE_CLEANUP_MAX_REMAINING_PIECES
    ):
        return None

    piece_values = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
    }

    captures = []

    for move in board.legal_moves:
        victim = board.piece_at(
            move.to_square
        )

        if victim is None:
            continue

        if victim.color == mover:
            continue

        victim_value = piece_values.get(
            victim.piece_type,
            0
        )

        if victim_value < MATE_CLEANUP_MIN_VALUE:
            continue

        trial = board.copy(
            stack=False
        )

        trial.push(move)

        # "Free" means the capturing piece is not immediately capturable
        # by any legal reply on the destination square.
        immediately_recapturable = any(
            reply.to_square == move.to_square
            for reply in trial.legal_moves
        )

        if immediately_recapturable:
            continue

        candidate = candidate_map.get(
            move
        )

        captures.append(
            {
                "move": move,
                "victim": victim,
                "victim_value": victim_value,
                "candidate": candidate,
                "rank": (
                    candidate["rank"]
                    if candidate is not None
                    else None
                ),
                "cp": (
                    candidate["cp"]
                    if candidate is not None
                    else None
                ),
            }
        )

    if not captures:
        return None

    max_value = max(
        item["victim_value"]
        for item in captures
    )

    best_value_captures = [
        item
        for item in captures
        if item["victim_value"] == max_value
    ]

    candidate_captures = [
        item
        for item in best_value_captures
        if item["candidate"] is not None
    ]

    if candidate_captures:
        selected = max(
            candidate_captures,
            key=lambda item: (
                item["cp"],
                -item["rank"]
            )
        )
    else:
        selected = random.choice(
            best_value_captures
        )

    return selected


def find_priority_queen_promotion(
    board,
    candidates,
    best_cp
):
    """Prefer a safe QUEEN promotion whenever promotion is available.

    Queen promotion is the default conversion choice. Underpromotion is left
    to the engine only when no legal queen promotion exists or the queen move
    is clearly unsafe and a better engine-backed promotion is available.
    """
    candidate_map = {
        candidate["move"]: candidate
        for candidate in candidates
    }

    queen_promotions = [
        move
        for move in board.legal_moves
        if move.promotion == chess.QUEEN
    ]

    if not queen_promotions:
        return None

    choices = []

    for move in queen_promotions:
        candidate = candidate_map.get(move)

        try:
            after = board.copy(stack=False)
            after.push(move)
        except Exception:
            continue

        if after.is_checkmate():
            return {
                "move": move,
                "info": candidate["info"] if candidate else None,
                "rank": candidate["rank"] if candidate else 0,
                "cp": candidate["cp"] if candidate else best_cp,
                "reason_tag": "QUEEN PROMOTION MATE"
            }

        # Never force a queen promotion when the newly promoted queen can be
        # immediately captured and the engine did not consider the move.
        if candidate is None:
            immediate_queen_loss = any(
                reply.to_square == move.to_square
                for reply in after.legal_moves
            )
            if immediate_queen_loss:
                continue

        candidate_cp = (
            int(candidate["cp"])
            if candidate is not None
            else best_cp
        )

        if candidate is not None and candidate_cp < best_cp - FREE_CAPTURE_MAX_CP_DROP:
            continue

        choices.append(
            {
                "move": move,
                "info": candidate["info"] if candidate else None,
                "rank": candidate["rank"] if candidate else 0,
                "cp": candidate_cp,
                "reason_tag": "QUEEN PROMOTION"
            }
        )

    if not choices:
        return None

    choices.sort(
        key=lambda item: (
            item["cp"],
            -item["rank"]
        ),
        reverse=True
    )

    return choices[0]


def free_capture_position_safe(
    board,
    move
):
    """Check that a free capture does not immediately expose our position.

    The capture is accepted only when the resulting position does not give the
    opponent a mate-in-one and does not leave a major/minor own piece hanging
    for a free immediate capture. This protects the rest of our material while
    still allowing genuinely free captures.
    """
    try:
        after = board.copy(stack=False)
        after.push(move)

        # Never choose a free capture that walks into an immediate checkmate.
        for reply in after.legal_moves:
            trial = after.copy(stack=False)
            trial.push(reply)

            if trial.is_checkmate():
                return False

        piece_values = {
            chess.PAWN: 1,
            chess.KNIGHT: 3,
            chess.BISHOP: 3,
            chess.ROOK: 5,
            chess.QUEEN: 9,
            chess.KING: 100,
        }

        # After our free capture, reject any immediate opponent capture that
        # wins one of our major/minor pieces without an immediate recapture.
        for reply in after.legal_moves:
            victim = after.piece_at(reply.to_square)

            if victim is None or victim.color != board.turn:
                continue

            victim_value = piece_values.get(
                victim.piece_type,
                0
            )

            # Pawns are allowed to remain tactically loose; the requested
            # protection is for the rest of our important pieces.
            if victim_value < 3:
                continue

            after_reply = after.copy(stack=False)
            after_reply.push(reply)

            can_recapture = any(
                response.to_square == reply.to_square
                for response in after_reply.legal_moves
            )

            if can_recapture:
                continue

            return False

        return True

    except Exception:
        # Safety-first: if the position cannot be checked reliably, do not
        # promote this move to a "free capture" automatically.
        return False


def free_capture_engine_safe(
    board,
    move,
    engine,
    reference_cp
):
    """Second-stage safety check for a genuinely free capture.

    Uses a shallow engine line after the capture to reject:
    - forced mate against us in M1-M5;
    - a large evaluation collapse;
    - a major/minor own piece being lost in the first ~2 opponent moves
      without an immediate recapture in the principal variation.

    This is only applied to free-capture candidates, not ordinary engine
    captures, so normal move selection stays fast.
    """
    if engine is None:
        return True

    try:
        after = board.copy(stack=False)
        after.push(move)

        info = engine.analyse(
            after,
            chess.engine.Limit(
                depth=FREE_CAPTURE_SAFETY_DEPTH
            )
        )

        score_obj = info.get("score")
        if score_obj is not None:
            our_score = score_obj.pov(board.turn)
            mate = our_score.mate()

            # Never enter a forced mate M1-M5 after grabbing a "free" piece.
            if (
                mate is not None
                and mate < 0
                and abs(int(mate)) <= 5
            ):
                return False

            cp = our_score.score(
                mate_score=100000
            )
            if (
                cp is not None
                and reference_cp is not None
                and cp < int(reference_cp) - FREE_CAPTURE_SAFETY_MAX_CP_DROP
            ):
                return False

        # Tactical material safety over the first 1-2 opponent moves.
        # Look only at the engine PV, keeping this check bounded and fast.
        pv = info.get("pv", [])
        probe = after

        for ply_index, reply in enumerate(
            pv[:FREE_CAPTURE_SAFETY_MAX_PLY]
        ):
            if reply not in probe.legal_moves:
                break

            mover = probe.turn
            victim_square = reply.to_square

            if probe.is_en_passant(reply):
                victim_square = (
                    reply.to_square - 8
                    if mover == chess.WHITE
                    else reply.to_square + 8
                )

            victim = probe.piece_at(victim_square)

            if (
                mover != board.turn
                and victim is not None
                and victim.color == board.turn
                and victim.piece_type in {
                    chess.KNIGHT,
                    chess.BISHOP,
                    chess.ROOK,
                    chess.QUEEN,
                }
            ):
                victim_value = material_value(
                    victim.piece_type
                )

                after_opponent_capture = probe.copy(
                    stack=False
                )
                after_opponent_capture.push(reply)

                recaptured = any(
                    response.to_square == reply.to_square
                    for response in after_opponent_capture.legal_moves
                )

                if not recaptured and victim_value >= 300:
                    return False

            probe.push(reply)

        return True

    except Exception:
        # Safety-first for this optional second-stage check: when the engine
        # cannot evaluate the candidate reliably, do not elevate it as a safe
        # free capture.
        return False


def find_priority_capture(
    board,
    candidates,
    best_cp,
    force_endgame=False,
    engine=None
):
    """Prefer safe captures before human-like wandering.

    A capture can come from MultiPV=15 or, for a genuinely free piece, from
    the complete legal move list. This applies to captures by every piece
    type, including king captures; the king itself is never a legal victim.
    """
    candidate_map = {
        candidate["move"]: candidate
        for candidate in candidates
    }

    own_material = side_material(board, board.turn)
    enemy_material = side_material(board, not board.turn)

    non_king_pieces = sum(
        1
        for piece in board.piece_map().values()
        if piece.piece_type != chess.KING
    )

    winning_material = own_material > enemy_material
    endgame = force_endgame or non_king_pieces <= 10

    choices = []

    for move in board.legal_moves:
        if not board.is_capture(move):
            continue

        victim_square = move.to_square
        if board.is_en_passant(move):
            victim_square = (
                move.to_square - 8
                if board.turn == chess.WHITE
                else move.to_square + 8
            )

        victim = board.piece_at(victim_square)
        if victim is None or victim.color == board.turn:
            continue

        victim_value = material_value(victim.piece_type)
        if victim_value <= 0:
            continue

        mover_piece = board.piece_at(move.from_square)
        mover_value = (
            material_value(mover_piece.piece_type)
            if mover_piece is not None
            else 0
        )

        try:
            after = board.copy(stack=False)
            after.push(move)
        except Exception:
            continue

        if after.is_checkmate():
            return {
                "move": move,
                "info": candidate_map.get(move, {}).get("info")
                    if move in candidate_map
                    else None,
                "rank": (
                    candidate_map[move]["rank"]
                    if move in candidate_map
                    else 0
                ),
                "cp": (
                    candidate_map[move]["cp"]
                    if move in candidate_map
                    else best_cp
                ),
                "victim_value": victim_value,
                "reason_tag": "CHECKMATE CAPTURE"
            }

        immediate_replies = [
            reply
            for reply in after.legal_moves
            if reply.to_square == move.to_square
        ]

        # A truly free capture: no opponent piece can immediately take the
        # capturing piece. The deeper engine safety pass is applied later
        # after candidates are ranked, so normal move selection stays fast.
        free_capture = (
            not immediate_replies
            and free_capture_position_safe(board, move)
        )

        candidate = candidate_map.get(move)
        candidate_cp = (
            int(candidate["cp"])
            if candidate is not None
            else best_cp
        )

        # Candidate captures from MultiPV are trusted inside a reasonable
        # engine-score band. Non-MultiPV captures are used only when they are
        # genuinely free; this prevents forcing poisoned captures.
        if candidate is None:
            if not free_capture:
                continue
        else:
            if candidate_cp < best_cp - FREE_CAPTURE_MAX_CP_DROP:
                continue

            # Do not trade a high-value piece for a lower-value victim simply
            # because it happens to be a capture, unless the engine itself
            # selected it inside the normal safety band.
            if (
                not free_capture
                and victim_value < mover_value
                and winning_material
            ):
                continue

        # In a winning endgame, free captures get an even stronger priority.
        # Otherwise, only take them ahead of the fuzzy shuffle when the
        # position is materially/evaluationally favorable.
        if not free_capture:
            if endgame and winning_material:
                # Equal-or-better trades are acceptable in liquidation mode.
                if victim_value < mover_value:
                    continue
            elif candidate is None:
                continue

        choices.append(
            {
                "move": move,
                "info": (
                    candidate["info"]
                    if candidate is not None
                    else None
                ),
                "rank": (
                    candidate["rank"]
                    if candidate is not None
                    else 99
                ),
                "cp": candidate_cp,
                "victim_value": victim_value,
                "free": free_capture,
                "mover_value": mover_value,
                "reason_tag": (
                    "FREE CAPTURE"
                    if free_capture
                    else "SAFE LIQUIDATION CAPTURE"
                )
            }
        )

    if not choices:
        return None

    # First take the highest-value free target. In endgames, also prefer
    # favorable liquidation captures over wandering moves.
    choices.sort(
        key=lambda item: (
            1 if item["free"] else 0,
            item["victim_value"],
            item["cp"],
            -item["rank"]
        ),
        reverse=True
    )

    # Free pieces remain the highest capture priority, but only after
    # the candidate survives the 1-2 move material / M1-M5 mate safety test.
    free_choices = [
        item
        for item in choices
        if item["free"]
    ]

    if free_choices and engine is not None:
        free_choices.sort(
            key=lambda item: (
                item["victim_value"],
                item["cp"],
                -item["rank"]
            ),
            reverse=True
        )

        for free_choice in free_choices:
            if free_capture_engine_safe(
                board,
                free_choice["move"],
                engine,
                best_cp
            ):
                return free_choice
    elif free_choices:
        return free_choices[0]

    selected = choices[0]

    if (
        selected["free"]
        or endgame
        or winning_material
    ):
        # A free capture that failed the deeper safety check must not be
        # re-selected as a fallback. Prefer the best ordinary capture instead.
        if selected["free"] and engine is not None:
            safe_alternatives = [
                item
                for item in choices
                if not item["free"]
            ]
            if safe_alternatives:
                return max(
                    safe_alternatives,
                    key=lambda item: (
                        item["cp"],
                        -item["rank"]
                    )
                )
            return None
        return selected

    return None


def find_safe_free_capture(
    board,
    candidates,
    best_cp
):
    """Find a genuinely free major/minor piece to capture.

    A capture is "free" here only when the captured piece is worth at least a
    minor piece and the capturing piece cannot be immediately taken back.
    The candidate must still be reasonably close to the current best engine
    score so a poisoned/tactical capture is not forced.
    """
    choices = []

    for candidate in candidates:
        move = candidate["move"]
        victim_square = move.to_square

        if board.is_en_passant(move):
            victim_square = (
                move.to_square - 8
                if board.turn == chess.WHITE
                else move.to_square + 8
            )

        victim = board.piece_at(victim_square)

        if victim is None or victim.color == board.turn:
            continue

        victim_value = material_value(victim.piece_type)
        if victim_value < FREE_CAPTURE_MIN_VALUE * 100:
            continue

        try:
            after = board.copy(stack=False)
            after.push(move)
        except Exception:
            continue

        # No legal reply may capture the moved piece. That is the key
        # distinction between a genuinely free piece and an ordinary exchange.
        immediate_take = any(
            reply.to_square == move.to_square
            for reply in after.legal_moves
        )

        if immediate_take:
            continue

        if not free_capture_position_safe(board, move):
            continue

        candidate_cp = int(candidate.get("cp", best_cp))
        if candidate_cp < best_cp - FREE_CAPTURE_MAX_CP_DROP:
            continue

        choices.append(
            (
                victim_value,
                candidate_cp,
                -int(candidate.get("rank", 99)),
                candidate
            )
        )

    if not choices:
        return None

    choices.sort(reverse=True, key=lambda item: item[:3])
    return choices[0][3]


def candidate_hangs_own_piece(
    board,
    move
):
    """Reject obvious one-move giveaways.

    This is intentionally conservative: a check/mate or a materially winning
    capture can still be a deliberate sacrifice. Otherwise a moved piece that
    can be taken next move without a recapture is rejected when that sequence
    loses material.
    """
    try:
        if board.gives_check(move):
            return False

        before_victim = board.piece_at(move.to_square)
        victim_value = (
            material_value(before_victim.piece_type)
            if before_victim is not None
            and before_victim.color != board.turn
            else 0
        )

        moved_piece = board.piece_at(move.from_square)
        if moved_piece is None:
            return True

        moved_value = material_value(moved_piece.piece_type)

        after = board.copy(stack=False)
        after.push(move)

        if after.is_checkmate():
            return False

        for reply in after.legal_moves:
            if reply.to_square != move.to_square:
                continue

            reply_piece = after.piece_at(reply.from_square)
            if reply_piece is None:
                continue

            after_reply = after.copy(stack=False)
            after_reply.push(reply)

            recaptured = any(
                response.to_square == reply.to_square
                for response in after_reply.legal_moves
            )

            if recaptured:
                continue

            # Net material swing after the opponent takes our moved piece.
            # Negative means the move simply gave material away.
            net = victim_value - moved_value

            if net < 0 and moved_value >= 100:
                return True

        return False

    except Exception:
        # Safety-first fallback: unknown candidates are not rejected here;
        # the existing engine score and physical verification remain in force.
        return False


def choose_stockfish_move(
    board,
    multipv_infos,
    previous_eval_white_cp=None,
    opponent_accuracy=None,
    opponent_sample_count=0,
    opponent_pressure=False,
    engine=None
):
    # Reset the historical fuzzy state at a fresh match/new game.
    # This is retained from the fast-main-match-controls branch so a previous
    # game's advantage/mate progression never leaks into the next game.
    global _advantage_target_cp
    global _advantage_hold_moves
    global _advantage_hold_limit
    global _advantage_last_selected_cp
    global _advantage_light_drop_used
    global _advantage_down_streak
    global _mate_progress_target_mate
    global _mate_progress_hold_moves
    global _mate_progress_hold_limit

    if len(board.move_stack) <= 1:
        _advantage_target_cp = None
        _advantage_hold_moves = 0
        _advantage_hold_limit = random.randint(
            HUMAN_ADVANTAGE_HOLD_MIN_MOVES,
            HUMAN_ADVANTAGE_HOLD_MAX_MOVES
        )
        _advantage_last_selected_cp = None
        _advantage_light_drop_used = False
        _advantage_down_streak = 0
        _mate_progress_target_mate = None
        _mate_progress_hold_moves = 0
        _mate_progress_hold_limit = random.randint(
            MATE_SUSTAIN_MIN_MOVES,
            MATE_SUSTAIN_MAX_MOVES
        )
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
        # During the human-like mating window, clear genuinely free
        # material first. This is intentionally before the M4 force rule:
        # if the opponent blunders a queen/rook/minor/pawn and it is safely
        # capturable, take it before closing the game. When only one
        # non-king piece remains, proceed with the normal mate plan.
        if (
            MATE_GRACE_MIN
            <= best["mate"]
            <= MATE_GRACE_MAX
        ):
            cleanup = find_free_mate_cleanup_capture(
                board,
                candidates
            )

            if cleanup is not None:
                selected = cleanup["candidate"]

                if selected is None:
                    selected = {
                        "move": cleanup["move"],
                        "info": best["info"],
                        "rank": None,
                        "cp": best_cp,
                        "mate": None,
                    }
                else:
                    selected = dict(
                        selected
                    )
                    selected["move"] = cleanup["move"]

                victim_name = chess.piece_name(
                    cleanup["victim"].piece_type
                ).upper()

                rank_text = (
                    f"#{cleanup['rank'] + 1}"
                    if cleanup["rank"] is not None
                    else "FREE"
                )

                return (
                    selected["move"],
                    selected["info"],
                    {
                        "rank": cleanup["rank"],
                        "current_cp": best_cp,
                        "selected_cp": cleanup["cp"],
                        "source": "MATE_CLEANUP",
                        "reason": (
                            f"MATE CLEANUP | "
                            f"FREE {victim_name} "
                            f"TARGET="
                            f"{chess.square_name(selected['move'].to_square)} "
                            f"RANK={rank_text}"
                        )
                    }
                )

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
        # Convert an extra pawn when a queen promotion is genuinely
        # available. Promotion is a stronger conversion priority than
        # wandering/shuffling in a winning position.
        priority_promotion = find_priority_queen_promotion(
            board,
            candidates,
            best_cp
        )

        if priority_promotion is not None:
            return (
                priority_promotion["move"],
                priority_promotion["info"],
                {
                    "rank": priority_promotion["rank"],
                    "current_cp": best_cp,
                    "selected_cp": priority_promotion["cp"],
                    "source": "QUEEN_PROMOTION",
                    "reason": (
                        f"{priority_promotion['reason_tag']} | "
                        f"TARGET={chess.square_name(priority_promotion['move'].to_square)}"
                    )
                }
            )

        # Before normal fuzzy selection, prefer safe captures so "human-like"
        # does not become "wander around while a free piece is hanging".
        priority_capture = find_priority_capture(
            board,
            candidates,
            best_cp,
            engine=engine
        )

        if priority_capture is not None:
            return (
                priority_capture["move"],
                priority_capture["info"],
                {
                    "rank": priority_capture["rank"],
                    "current_cp": best_cp,
                    "selected_cp": priority_capture["cp"],
                    "source": "CAPTURE_PRIORITY",
                    "reason": (
                        f"{priority_capture['reason_tag']} | "
                        f"TARGET={chess.square_name(priority_capture['move'].to_square)} "
                        f"VICTIM={priority_capture['victim_value']/100:.1f} "
                        f"{'FREE' if priority_capture['free'] else 'LIQUIDATION'}"
                    )
                }
            )

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
        # Keep the original safety floor for winning positions, but in
        # normal/early play allow a small extra human-like evaluation band.
        selection_floor_cp = floor_cp

        winning_guard = (
            best_cp >= HUMAN_WINNING_GUARD_START_CP
        )

        if not advantage_mode:
            selection_floor_cp = max(
                5,
                floor_cp - HUMAN_SELECTION_EXTRA_DROP_CP
            )

        # Once ahead, keep human-like variation inside a tight evaluation
        # band. The old 70cp extra drop could turn a winning position into
        # equality for the sake of rank shuffling.
        if winning_guard:
            winning_drop_floor = max(
                5,
                best_cp - HUMAN_WINNING_GUARD_MAX_DROP_CP
            )
            selection_floor_cp = max(
                selection_floor_cp,
                winning_drop_floor
            )

        winning_rank_cap = (
            HUMAN_STRONG_WINNING_RANK_CAP
            if best_cp >= HUMAN_STRONG_WINNING_CP
            else HUMAN_WINNING_GUARD_RANK_CAP
        )

        effective_rank_cap = (
            min(adaptive_max_rank, winning_rank_cap)
            if winning_guard
            else adaptive_max_rank
        )

        safe = [
            c
            for c in candidates
            if (
                c["cp"] >= selection_floor_cp
                and c["cp"] > 0
                and c["rank"] <= effective_rank_cap
                and (
                    not winning_guard
                    or not candidate_hangs_own_piece(
                        board,
                        c["move"]
                    )
                )
            )
        ]

        if not safe:
            safe = [best]

        if not safe:
            safe = [best]

        non_best = [
            c
            for c in safe
            if c["rank"] > 0
        ]

        non_best_chance = (
            HUMAN_STRONG_WINNING_NON_BEST_CHANCE
            if best_cp >= HUMAN_STRONG_WINNING_CP
            else HUMAN_WINNING_NON_BEST_CHANCE
            if winning_guard
            else HUMAN_SELECTION_NON_BEST_CHANCE
        )

        if (
            len(non_best) >= 2
            and random.random() < non_best_chance
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
                # Progress moves must still feel human-like. Do not collapse
                # the pool to only the top few centipawn lines: that makes
                # advantage growth select #1 repeatedly. Keep every safe
                # MultiPV=15 candidate available and let the fuzzy rank/score
                # weighting decide among them.
                growth_pool = [
                    c
                    for c in safe
                    if c["cp"] >= floor_cp
                ]

                if growth_pool:
                    pool = growth_pool
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
            # Keep #1/#2 available, but deliberately make #3+ more likely.
            # Forced-best, mate, promotion, and safety branches above are
            # untouched; this only changes the normal fuzzy shuffle weighting.
            rank_factors = {
                0: 0.50,
                1: 0.62,
                2: 0.88,
                3: 1.05,
                4: 1.14,
                5: 1.16,
                6: 1.15,
                7: 1.12,
                8: 1.09,
                9: 1.06,
                10: 1.03,
                11: 1.00,
                12: 0.98,
                13: 0.96,
                14: 0.94,
            }
        else:
            # Same principle in normal play: #3+ should usually win the fuzzy
            # draw when several safe near-equal candidates exist.
            rank_factors = {
                0: 0.55,
                1: 0.68,
                2: 0.90,
                3: 1.06,
                4: 1.14,
                5: 1.16,
                6: 1.14,
                7: 1.11,
                8: 1.08,
                9: 1.05,
                10: 1.02,
                11: 1.00,
                12: 0.98,
                13: 0.96,
                14: 0.94,
            }

        lower_rank_pool = [
            candidate
            for candidate in pool
            if candidate["rank"] >= 2
        ]

        # If the normal safety/evaluation band leaves fewer than three
        # candidates, do NOT let the fuzzy draw collapse back to #1/#2.
        # Build a slightly wider lower-rank-only pool using the same engine
        # candidates and the same rank cap. The extra band is small and is
        # used only to create human-like choice diversity.
        diversity_floor_cp = max(
            5,
            int(
                best_cp
                * (
                    1.0
                    - min(
                        0.28,
                        max_drop
                        + HUMAN_SELECTION_DIVERSITY_EXTRA_DROP
                    )
                )
            )
        )

        diversity_lower_pool = [
            candidate
            for candidate in candidates
            if (
                candidate["rank"] >= 2
                and candidate["rank"] <= effective_rank_cap
                and candidate["cp"] >= diversity_floor_cp
                and candidate["cp"] > 0
                and (
                    not winning_guard
                    or not candidate_hangs_own_piece(
                        board,
                        candidate["move"]
                    )
                )
            )
        ]

        if (
            diversity_lower_pool
            and (
                len(pool) < 3
                or not lower_rank_pool
            )
        ):
            selection_pool = diversity_lower_pool
        else:
            selection_pool = (
                lower_rank_pool
                if (
                    lower_rank_pool
                    and random.random() > HUMAN_SELECTION_TOP12_MAX_CHANCE
                )
                else pool
            )

        weighted = []

        for candidate in selection_pool:
            distance = abs(
                candidate["cp"]
                - desired_cp
            )

            weight = (
                1.0
                / (
                    1.0
                    + distance / (
                        HUMAN_SELECTION_DISTANCE_CP
                        * (
                            1.35
                            if advantage_mode
                            else 1.0
                        )
                    )
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
        0: 0.85,
        1: 0.90,
        2: 0.98,
        3: 1.04,
        4: 1.08,
        5: 1.10,
        6: 1.08,
        7: 1.06,
        8: 1.04,
        9: 1.02,
        10: 1.00,
        11: 0.98,
        12: 0.96,
        13: 0.94,
        14: 0.92,
    }

    lower_rank_safe = [
        candidate
        for candidate in safe
        if candidate["rank"] >= 2
    ]

    selection_safe = (
        lower_rank_safe
        if (
            lower_rank_safe
            and random.random() > HUMAN_SELECTION_TOP12_MAX_CHANCE
        )
        else safe
    )

    weighted = []

    for candidate in selection_safe:
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


def verify_existing_white_first_move(
    sct,
    hwnd,
    board,
    move,
    frame,
    board_coords,
    black_perspective
):
    expected_board = expected_board_after_move(
        board,
        move
    )

    current_frame = frame
    deadline = time.perf_counter() + 0.18
    last_reason = (
        "first white move state not yet confirmed"
    )

    while time.perf_counter() < deadline:
        if current_frame is not None:
            full_ok, full_reason = (
                full_board_state_confirmed(
                    current_frame,
                    expected_board,
                    board_coords,
                    black_perspective
                )
            )

            if full_ok:
                return (
                    True,
                    current_frame,
                    "direct full-board first-move confirmation"
                )

            last_reason = full_reason

        current_frame = capture_screen(
            sct,
            hwnd
        )

        if current_frame is None:
            time.sleep(BOT_RECOVERY_POLL)
            continue

        time.sleep(BOT_RECOVERY_POLL)

    return (
        False,
        frame,
        last_reason
    )


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

    gm_book = GMBook(GM_BOOK_PATH)

    if gm_book.load():
        print(
            "[BOOK] Ultimate_GM_Bullet.bin loaded: "
            f"{GM_BOOK_PATH} | format={gm_book.format}"
        )
    else:
        print(
            "[BOOK] Ultimate_GM_Bullet.bin not available/unsupported; "
            "using Stockfish human-like selection only."
        )

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
    match_ui = {
        "phase": "IDLE",
        "requested_action": None,
        "rematch_enabled": False,
        "new_match_enabled": True,
        "thinking_enabled": BOT_THINKING_ENABLED_DEFAULT,
        "thinking_toggle_rect": None,
        "rematch_toggle_rect": None,
        "new_match_toggle_rect": None,
        "controls_rect": None,
        "result_text": "WAITING FOR NEW MATCH...",
        "preference": {
            "best": "-",
            "selected": "-",
            "rank": "-",
            "best_cp": None,
            "selected_cp": None,
            "reason": "-",
        },
        "board_obstruction": 0.0,
        "screen_guard": False,
    }

    match_result_streak = 0
    match_auto_after = None
    match_next_scan = time.perf_counter()

    stockfish_moves_since_buffer = 0

    next_buffer_after = random.randint(
        RANDOM_BUFFER_MOVE_MIN,
        RANDOM_BUFFER_MOVE_MAX
    )

    opponent_match_history = []
    next_human_best_uci = None
    opponent_pressure = False

    with mss.mss() as sct:
        cv2.namedWindow(
            "Chess Vision Tracker"
        )

        cv2.setMouseCallback(
            "Chess Vision Tracker",
            match_ui_mouse_callback,
            match_ui
        )
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

                # Keep the live capture untouched for detection/click verification.
                # Add a dedicated right-side presentation area for all UI panels so
                # evaluation data, buttons and move history never cover the board.
                display_frame = frame.copy()

                if cached_board_coords:
                    ui_side_width = 600
                    ui_gap = 12
                    canvas_width = (
                        frame.shape[1]
                        + ui_gap
                        + ui_side_width
                    )

                    ui_canvas = np.zeros(
                        (
                            frame.shape[0],
                            canvas_width,
                            frame.shape[2]
                        ),
                        dtype=frame.dtype
                    )

                    ui_canvas[
                        :,
                        :frame.shape[1]
                    ] = frame

                    display_frame = ui_canvas

                if key == ord("m"):
                    if match_ui.get("phase") == "RESULT":
                        match_ui["requested_action"] = "REMATCH"

                elif key == ord("n"):
                    if match_ui.get("phase") == "RESULT":
                        match_ui["requested_action"] = "NEW MATCH"

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
                    match_ui["phase"] = "IDLE"
                    match_ui["requested_action"] = None
                    match_ui["result_text"] = "WAITING FOR NEW MATCH..."
                    match_ui["preference"] = {
                        "best": "-",
                        "selected": "-",
                        "rank": "-",
                        "best_cp": None,
                        "selected_cp": None,
                        "reason": "-",
                    }
                    match_ui["board_obstruction"] = 0.0
                    match_ui["screen_guard"] = False
                    match_result_streak = 0
                    match_auto_after = None

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
                            # Do not infer a chess orientation/player side from a
                            # non-board screen. The fresh-game detector validates
                            # START / START+WHITE-MOVE first, then supplies the
                            # trusted perspective and colors.
                            cached_board_grid = locked_grid
                            baseline_frame = locked_frame

                            startup_new_game = None
                            visual_black_perspective = False
                            stockfish_color = None
                            human_color = None

                            # Do not assume that locking the grid means a
                            # match exists. A game may start later, so probe
                            # the actual board for START or START+White move.
                            if len(board.move_stack) == 0:
                                startup_new_game = detect_new_game_state(
                                    sct,
                                    scrcpy_hwnd,
                                    cached_board_coords,
                                    source_frame=locked_frame
                                )

                            if startup_new_game is not None:
                                board = startup_new_game["board"]
                                visual_black_perspective = (
                                    startup_new_game["perspective"]
                                )
                                stockfish_color = (
                                    startup_new_game["stockfish_color"]
                                )
                                human_color = (
                                    startup_new_game["human_color"]
                                )
                                cached_board_grid = startup_new_game["grid"]
                                baseline_frame = startup_new_game["frame"]

                                print(
                                    "[MATCH] NEW GAME DETECTED AT STARTUP | "
                                    f"kind={startup_new_game['kind']} "
                                    f"exact={startup_new_game['exact']}/64"
                                )

                            elif len(board.move_stack) == 0:
                                # No match yet. Stay in matchmaking and let the
                                # fast direct new-game probe pick it up later.
                                game_ready = False
                                match_ui["phase"] = "MATCHMAKING"
                                match_ui["requested_action"] = None
                                match_ui["screen_guard"] = False
                                match_ui["result_text"] = (
                                    "WAITING FOR NEW MATCH..."
                                )
                                match_next_scan = time.perf_counter()

                                print(
                                    "[MATCH] No fresh game yet | "
                                    "waiting for START or START+WHITE-MOVE"
                                )

                            if (
                                startup_new_game is not None
                                and startup_new_game.get("first_move") is not None
                            ):
                                print(
                                    "[MATCH] WHITE MOVE ALREADY PRESENT | "
                                    f"{startup_new_game['first_move'].uci()} | synced"
                                )

                            if (
                                startup_new_game is None
                                and len(board.move_stack) != 0
                                and human_color == chess.WHITE
                            ):
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
                                    ) = verify_existing_white_first_move(
                                    sct,
                                    scrcpy_hwnd,
                                    board,
                                    first_move,
                                    locked_frame,
                                    cached_board_coords,
                                    visual_black_perspective
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

                            # Only enter GAME when the startup
                            # probe found a valid fresh game, or the internal
                            # board was already beyond the initial position.
                            if (
                                startup_new_game is not None
                                or len(board.move_stack) != 0
                            ):
                                game_ready = True
                                match_ui["phase"] = "GAME"
                                match_ui["requested_action"] = None
                                match_result_streak = 0
                                match_auto_after = None
                                analysis_state = None
                            else:
                                game_ready = False

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

                            if game_ready:
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

                                print(
                                    "[MATCH] FIRST-TURN DECISION | "
                                    f"{'HUMAN' if board.turn == human_color else 'STOCKFISH'} "
                                    "TO MOVE"
                                )
                            else:
                                print(
                                    "[INFO] Waiting for NEW MATCH..."
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
                        cached_board_coords,
                        timeout=0.25
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
                                ) = verify_existing_white_first_move(
                                    sct,
                                    scrcpy_hwnd,
                                    board,
                                    first_move,
                                    fresh_frame,
                                    cached_board_coords,
                                    visual_black_perspective
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
                        match_ui["phase"] = "GAME"
                        match_ui["requested_action"] = None
                        match_result_streak = 0
                        match_auto_after = None

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

                # ============================================================
                # BOARD VISIBILITY / UNSCHEDULED NEW-GAME RECOVERY
                # ADD-ONLY: existing move detection remains unchanged.
                # ============================================================
                if (
                    grid_locked
                    and cached_board_coords
                    and match_ui.get("phase") != "IDLE"
                ):
                    obstruction = 0.0

                    # In a live game, normal chess movement should remain
                    # allowed. The obstruction ratio is still useful because a
                    # phone notification/call/banner can cover a large part of
                    # the board. Such an overlay pauses move processing only;
                    # it never changes the chess game into RESULT.
                    if (
                        baseline_frame is not None
                        and match_ui.get("phase")
                        in ("GAME", "AWAIT_RESULT", "MATCHMAKING")
                    ):
                        obstruction = match_board_obstruction_ratio(
                            baseline_frame,
                            frame,
                            cached_board_coords,
                            visual_black_perspective
                        )

                    match_ui["board_obstruction"] = obstruction

                    recovery_due = (
                        time.perf_counter()
                        >= match_next_scan
                    )

                    large_hidden = (
                        obstruction
                        >= MATCH_BOARD_VISIBILITY_THRESHOLD
                    )

                    matchmaking_phase = (
                        match_ui.get("phase") == "MATCHMAKING"
                    )

                    # Direct new-match recovery while already in GAME.
                    # This handles: accidental exit -> New game, rematch
                    # started outside the result-screen flow, or the bot being
                    # restarted while the app is already on a fresh game.
                    new_game = None

                    direct_reset_probe = (
                        recovery_due
                        and match_ui.get("phase") == "GAME"
                        and game_ready
                        and not bot_thinking
                        and baseline_frame is not None
                    )

                    if direct_reset_probe:
                        reset_changes = fast_square_motion_scores(
                            baseline_frame,
                            frame,
                            cached_board_coords,
                            visual_black_perspective
                        )

                        if reset_changes is not None:
                            reset_changed_squares = sum(
                                1
                                for value in reset_changes.values()
                                if value >= MATCH_NEW_GAME_RESET_CHANGE_MIN
                            )

                            if (
                                reset_changed_squares
                                >= MATCH_NEW_GAME_RESET_CHANGED_SQUARES
                            ):
                                new_game = detect_new_game_state(
                                    sct,
                                    scrcpy_hwnd,
                                    cached_board_coords,
                                    source_frame=frame
                                )

                                if new_game is not None:
                                    print(
                                        "[MATCH] DIRECT NEW GAME RESET DETECTED | "
                                        f"changed={reset_changed_squares}/64"
                                    )

                    recovery_allowed = (
                        matchmaking_phase
                        or not game_ready
                    )

                    if (
                        new_game is None
                        and recovery_due
                        and recovery_allowed
                        and (
                            matchmaking_phase
                            or large_hidden
                        )
                    ):
                        new_game = detect_new_game_state(
                            sct,
                            scrcpy_hwnd,
                            cached_board_coords,
                            source_frame=frame
                        )

                        if new_game is not None:
                            board = new_game["board"]

                            visual_black_perspective = (
                                new_game["perspective"]
                            )
                            stockfish_color = (
                                new_game["stockfish_color"]
                            )
                            human_color = (
                                new_game["human_color"]
                            )

                            cached_board_grid = new_game["grid"]
                            baseline_frame = new_game["frame"]

                            game_ready = True
                            bot_thinking = False
                            analysis_state = None
                            last_bot_position_key = None
                            pending_bot_moves.clear()
                            pending_recovered_human = None
                            next_human_best_uci = None
                            opponent_pressure = False
                            opponent_match_history.clear()

                            next_main_turn_rescan = (
                                time.perf_counter()
                                + TURN_RESCAN_INTERVAL
                            )

                            stockfish_moves_since_buffer = 0
                            next_buffer_after = random.randint(
                                RANDOM_BUFFER_MOVE_MIN,
                                RANDOM_BUFFER_MOVE_MAX
                            )

                            _advantage_progress_target_cp = None
                            _advantage_progress_hold_moves = 0
                            _advantage_progress_hold_limit = random.randint(
                                HUMAN_ADVANTAGE_HOLD_MIN_MOVES,
                                HUMAN_ADVANTAGE_HOLD_MAX_MOVES
                            )
                            _advantage_progress_side = None

                            match_ui["phase"] = "GAME"
                            match_ui["requested_action"] = None
                            match_ui["screen_guard"] = False
                            match_ui["board_obstruction"] = 0.0
                            match_ui["result_text"] = "WAITING FOR NEW MATCH..."
                            match_ui["preference"] = {
                                "best": "-",
                                "selected": "-",
                                "rank": "-",
                                "best_cp": None,
                                "selected_cp": None,
                                "reason": "new game detected",
                            }

                            match_result_streak = 0
                            match_auto_after = None

                            print(
                                "[MATCH] UNSCHEDULED NEW GAME DETECTED | "
                                f"kind={new_game['kind']} "
                                f"exact={new_game['exact']}/64 "
                                f"Stockfish="
                                f"{'WHITE' if stockfish_color == chess.WHITE else 'BLACK'} "
                                f"| Human="
                                f"{'WHITE' if human_color == chess.WHITE else 'BLACK'}"
                            )

                            print(
                                "[MATCH] BOARD SIDE SETUP | "
                                f"bottom={'BLACK' if stockfish_color == chess.BLACK else 'WHITE'} "
                                f"| Stockfish={'WHITE' if stockfish_color == chess.WHITE else 'BLACK'} "
                                f"| Human={'WHITE' if human_color == chess.WHITE else 'BLACK'} "
                                f"| turn={'WHITE' if board.turn == chess.WHITE else 'BLACK'}"
                            )

                            print(
                                "[MATCH] FIRST-TURN DECISION | "
                                f"{'HUMAN' if board.turn == human_color else 'STOCKFISH'} "
                                "TO MOVE"
                            )

                            if new_game.get("first_move") is not None:
                                first_move = new_game["first_move"]

                                try:
                                    san = board.san(
                                        first_move
                                    )
                                except Exception:
                                    san = first_move.uci()

                                print(
                                    "[MATCH] WHITE MOVE ALREADY PRESENT | "
                                    f"{first_move.uci()} {san} | synced"
                                )

                        elif (
                            large_hidden
                            and match_ui.get("phase") in ("GAME", "MATCHMAKING")
                            and not bot_thinking
                            and not board.is_game_over()
                        ):
                            # Temporary external screen obstruction:
                            # preserve the current board/phase and simply pause
                            # move processing until the board is visible again.
                            if not match_ui.get("screen_guard"):
                                print(
                                    "[SCREEN GUARD] PAUSED | "
                                    f"external overlay/obstruction={obstruction * 100:.1f}% | "
                                    "preserving current game"
                                )

                            match_ui["screen_guard"] = True

                        elif (
                            match_ui.get("screen_guard")
                            and match_ui.get("phase") in ("GAME", "MATCHMAKING")
                            and not large_hidden
                        ):
                            visible_ok, _ = full_board_state_confirmed(
                                frame,
                                board,
                                cached_board_coords,
                                visual_black_perspective
                            )

                            if visible_ok:
                                match_ui["screen_guard"] = False
                                game_ready = True

                                print(
                                    "[SCREEN GUARD] BOARD VISIBLE AGAIN | "
                                    "internal position confirmed | continuing"
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

                if match_ui.get("screen_guard"):
                    status = (
                        "PAUSED - SCREEN HIDDEN >30% | "
                        "WAITING FOR BOARD / NEW MATCH"
                    )

                if (
                    game_ready
                    and grid_locked
                    and stockfish_color is not None
                    and not match_ui.get("screen_guard")
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

                                # Previous completed bot-position evaluation is needed
                                # by the timing simulator for both book and engine moves.
                                selected_previous_eval = (
                                    analysis_state.get(
                                        "eval_cp"
                                    )
                                    if analysis_state is not None
                                    else None
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

                                    match_ui["preference"] = {
                                        "best": (
                                            best_info_move.uci()
                                            if best_info_move is not None
                                            else "-"
                                        ),
                                        "selected": best_move.uci(),
                                        "rank": (
                                            f"#{int(selection_meta.get('rank')) + 1}"
                                            if selection_meta.get("rank") is not None
                                            else "FREE"
                                        ),
                                        "best_cp": selection_meta.get("current_cp"),
                                        "selected_cp": selection_meta.get("selected_cp"),
                                        "reason": str(
                                            selection_meta.get(
                                                "reason",
                                                "pending retry"
                                            )
                                        ),
                                    }

                                    print(
                                        "[STOCKFISH] "
                                        f"Retrying pending move: "
                                        f"{best_san}"
                                    )

                                else:
                                    book_choice = gm_book.choose(board)

                                    if book_choice is not None:
                                        engine_elapsed = 0.0
                                        multipv_result = []
                                        result = None
                                        best_move = book_choice["move"]
                                        selected_info = None
                                        best_info_move = None
                                        best_san = book_choice["san"]
                                        selection_meta = {
                                            "rank": int(book_choice["rank"] - 1),
                                            "reason": (
                                                "GM BOOK | "
                                                f"entries={book_choice['entries']} "
                                                "| weighted choice"
                                            ),
                                            "source": "GM_BOOK",
                                            "book_entries": int(
                                                book_choice["entries"]
                                            ),
                                            "book_weight": float(
                                                book_choice["weight"]
                                            ),
                                        }

                                        print(
                                            "[BOOK] POSITION IN BOOK | "
                                            f"entries={book_choice['entries']} "
                                            f"| SELECTED={book_choice['uci']} "
                                            f"{book_choice['san']} "
                                            "| weighted choice | "
                                            f"BOOK-RANK=#{book_choice['rank']}"
                                        )

                                    else:
                                        print(
                                            "[BOOK] OUT OF BOOK -> "
                                            "switching to human-like engine logic"
                                        )
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
                                            opponent_pressure=opponent_pressure,
                                            engine=engine
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

                                # Book moves already have a valid frozen decision.
                                # Keep the same freeze invariant used by the engine path.
                                if locked_bot_move is None:
                                    locked_bot_move = best_move

                                pending_bot_moves[
                                    position_key
                                ] = {
                                    "uci": best_move.uci(),
                                    "san": best_san,
                                    "result": result,
                                    "best_info_move": best_info_move,
                                    "selection_meta": selection_meta,
                                }

                                if pending_entry is not None:
                                    pass
                                elif selection_meta.get("source") == "GM_BOOK":
                                    print(
                                        "[BOOK] Book move frozen; "
                                        "existing click/verification path retained."
                                    )

                                else:
                                    print(
                                        "[ENGINE] "
                                        f"depth={STOCKFISH_DEPTH} "
                                        f"time={engine_elapsed:.3f}s "
                                        f"MultiPV={len(multipv_result)}"
                                    )

                                    selection_rank = selection_meta.get(
                                        "rank"
                                    )

                                    selection_rank_text = (
                                        f"#{selection_rank + 1}"
                                        if selection_rank is not None
                                        else "FREE"
                                    )

                                    print(
                                        "[TRAINING] "
                                        f"BEST="
                                        f"{best_info_move.uci() if best_info_move else '-'} "
                                        f"SELECTED="
                                        f"{best_move.uci()} "
                                        f"RANK="
                                        f"{selection_rank_text}"
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


                                match_ui["preference"] = {
                                    "best": (
                                        best_info_move.uci()
                                        if best_info_move is not None
                                        else "-"
                                    ),
                                    "selected": (
                                        best_move.uci()
                                        if best_move is not None
                                        else "-"
                                    ),
                                    "rank": (
                                        f"#{int(selection_meta.get('rank')) + 1}"
                                        if selection_meta.get("rank") is not None
                                        else "FREE"
                                    ),
                                    "best_cp": selection_meta.get("current_cp"),
                                    "selected_cp": selection_meta.get("selected_cp"),
                                    "reason": str(
                                        selection_meta.get(
                                            "reason",
                                            "-"
                                        )
                                    ),
                                }

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
                                    pending_frame = capture_screen(
                                        sct,
                                        scrcpy_hwnd
                                    )

                                    pending_post_ok, pending_post_reason = (
                                        screen_matches_expected_bot_move(
                                            pending_frame,
                                            board,
                                            best_move,
                                            cached_board_coords,
                                            visual_black_perspective,
                                            baseline_frame
                                        )
                                    )

                                    if pending_post_ok:
                                        print(
                                            "[RECOVERY] Pending Stockfish move already on screen: "
                                            f"{best_san} | fast post-state confirmation"
                                        )
                                        verified = True
                                        after_frame = pending_frame
                                        reason = pending_post_reason

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
                                        allow_fallback=False,
                                        before_board=board
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
                                        last_bot_position_key = position_key
                                        print(
                                            "[VALIDATION] WAITING | pending Stockfish move "
                                            "not yet physically confirmed; no click and no board.push() | "
                                            f"{pre_reason}"
                                        )
                                        time.sleep(BOT_RECOVERY_POLL)
                                        continue

                                if not verified:
                                    print(
                                        "[VALIDATION] PRE-CLICK PASS | "
                                        "physical board matches internal board 64/64"
                                    )

                                    # Apply natural timing ONLY to the first
                                    # click attempt. Pending retries stay fast.
                                    if pending_entry is None:
                                        natural_delay = natural_bot_move_delay(
                                            board,
                                            best_move,
                                            engine_result=multipv_result,
                                            selection_meta=selection_meta,
                                            moves_since_buffer=stockfish_moves_since_buffer,
                                            thinking_enabled=match_ui.get(
                                                "thinking_enabled",
                                                BOT_THINKING_ENABLED_DEFAULT
                                            ),
                                            previous_eval_white_cp=selected_previous_eval
                                        )
                                        print(
                                            "[BOT TIMING] "
                                            f"{natural_delay:.3f}s | "
                                            f"{best_move.uci()} "
                                            f"{best_san}"
                                        )
                                        time.sleep(natural_delay)

                                    clicked = click_move(
                                        best_move,
                                        cached_board_coords,
                                        visual_black_perspective,
                                        scrcpy_hwnd,
                                        sct=sct,
                                        promotion_color=board.turn,
                                        before_frame=before_frame,
                                        before_board=board
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

                                        # Keep retry path fast: use the direct
                                        # expected-post-state probe below. Full-board
                                        # catchup remains available in the background
                                        # recovery path, never blocking this move retry.

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
                                            promotion_color=board.turn,
                                            before_frame=retry_frame,
                                            before_board=board
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

                                    # Opening speed-up: during the first 10 bot
                                    # moves, the internal board is already physically
                                    # verified, so do not pay for another complete
                                    # 64-square template scan just to refresh the overlay.
                                    # Move verification itself is unchanged.
                                    if len(board.move_stack) <= 20:
                                        cached_board_grid = board_to_display_grid(
                                            board,
                                            visual_black_perspective
                                        )
                                        last_scan_time_ms = 0.0
                                    else:
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

                # ============================================================
                # RESULT SCREEN / MATCHMAKING LIFECYCLE
                # ADD-ONLY: normal chess move detectors remain unchanged.
                # ============================================================
                if (
                    grid_locked
                    and cached_board_coords
                    and baseline_frame is not None
                    and not bot_thinking
                    and match_ui.get("phase")
                    in ("GAME", "AWAIT_RESULT")
                ):
                    if board.is_game_over() and match_ui.get("phase") != "RESULT":
                        game_ready = False
                        match_ui["phase"] = "AWAIT_RESULT"
                        match_ui["result_text"] = (
                            f"GAME OVER | {board.outcome()}"
                        )

                    screen_change = match_screen_change_score(
                        baseline_frame,
                        frame
                    )

                    result_action_ui_visible = False
                    result_signal = False

                    # A changed screen is NOT a result screen. A notification,
                    # phone call, banner, keyboard, app switch, or any other
                    # overlay can create a large global pixel change.
                    #
                    # The only positive result signal is the real pair of
                    # Rematch + New buttons. This is also checked while the
                    # engine says GAME OVER, and during AWAIT_RESULT while the
                    # result page is still appearing.
                    should_check_result_buttons = (
                        match_ui.get("phase") == "AWAIT_RESULT"
                        or screen_change >= MATCH_RESULT_CHANGE_THRESHOLD
                        or board.is_game_over()
                    )

                    if should_check_result_buttons:
                        result_action_ui_visible = (
                            result_action_buttons_present(frame)
                        )

                    result_signal = result_action_ui_visible

                    if (
                        screen_change >= MATCH_RESULT_CHANGE_THRESHOLD
                        and not result_signal
                        and match_ui.get("phase") in ("GAME", "AWAIT_RESULT")
                    ):
                        progress(
                            "MATCH",
                            (
                                "screen changed but Rematch/New buttons are absent | "
                                "preserving current game"
                            ),
                            key="non_result_screen_change",
                            interval=0.75,
                            force=True
                        )

                    if result_signal:
                        match_result_streak += 1
                    else:
                        match_result_streak = 0

                    if match_result_streak >= MATCH_RESULT_CONFIRM_FRAMES:
                        if match_ui.get("phase") != "RESULT":
                            game_ready = False
                            match_ui["phase"] = "RESULT"
                            match_ui["requested_action"] = None
                            match_ui["result_text"] = (
                                f"GAME OVER | {board.outcome()}"
                                if board.is_game_over()
                                else "RESULT SCREEN"
                            )
                            match_result_streak = 0
                            match_auto_after = (
                                time.perf_counter()
                                + random.uniform(
                                    MATCH_AUTO_DELAY_MIN,
                                    MATCH_AUTO_DELAY_MAX
                                )
                            )

                            pending_bot_moves.clear()
                            last_bot_position_key = None
                            pending_recovered_human = None
                            next_human_best_uci = None

                            print(
                                "[MATCH] Result screen detected | "
                                f"screen_change={screen_change:.3f}"
                            )
                            remaining_delay = max(
                                0.0,
                                match_auto_after - time.perf_counter()
                            )

                            if remaining_delay > 0.001:
                                print(
                                    f"[MATCH] Waiting "
                                    f"{remaining_delay:.3f}s "
                                    "before automatic match action"
                                )
                            else:
                                print(
                                    "[MATCH] Automatic match action READY | "
                                    "no artificial delay"
                                )

                if match_ui.get("phase") == "RESULT":
                    requested_action = match_ui.get("requested_action")

                    if requested_action is None:
                        if match_ui.get("rematch_enabled"):
                            requested_action = "REMATCH"
                        elif match_ui.get("new_match_enabled"):
                            requested_action = "NEW MATCH"

                    auto_due = (
                        match_auto_after is None
                        or time.perf_counter() >= match_auto_after
                    )

                    manual_request = (
                        match_ui.get("requested_action")
                        in ("REMATCH", "NEW MATCH")
                    )

                    if (
                        requested_action in ("REMATCH", "NEW MATCH")
                        and (auto_due or manual_request)
                    ):
                        match_ui["requested_action"] = None

                        action_ok, action_reason = perform_match_action(
                            sct,
                            scrcpy_hwnd,
                            requested_action
                        )

                        if action_ok:
                            board = chess.Board(
                                INITIAL_FEN
                            )

                            clear_runtime_caches()

                            cached_board_grid = None
                            baseline_frame = None
                            game_ready = False
                            bot_thinking = False
                            stockfish_color = None
                            human_color = None
                            visual_black_perspective = False
                            analysis_state = None
                            last_bot_position_key = None
                            pending_bot_moves.clear()
                            pending_recovered_human = None
                            next_human_best_uci = None
                            opponent_pressure = False
                            opponent_match_history.clear()

                            next_main_turn_rescan = (
                                time.perf_counter()
                                + TURN_RESCAN_INTERVAL
                            )

                            _advantage_progress_target_cp = None
                            _advantage_progress_hold_moves = 0
                            _advantage_progress_hold_limit = random.randint(
                                HUMAN_ADVANTAGE_HOLD_MIN_MOVES,
                                HUMAN_ADVANTAGE_HOLD_MAX_MOVES
                            )
                            _advantage_progress_side = None

                            stockfish_moves_since_buffer = 0
                            next_buffer_after = random.randint(
                                RANDOM_BUFFER_MOVE_MIN,
                                RANDOM_BUFFER_MOVE_MAX
                            )

                            match_result_streak = 0
                            match_auto_after = None
                            match_next_scan = time.perf_counter()

                            match_ui["phase"] = "MATCHMAKING"
                            match_ui["requested_action"] = None
                            match_ui["result_text"] = "WAITING FOR NEW MATCH..."

                            print(
                                f"[MATCH] {requested_action} click CONFIRMED | "
                                "entering matchmaking"
                            )

                        else:
                            print(
                                f"[MATCH] {requested_action} not confirmed | "
                                f"{action_reason}"
                            )
                            match_auto_after = (
                                time.perf_counter()
                                + 0.75
                            )

                if (
                    match_ui.get("phase") == "MATCHMAKING"
                    and grid_locked
                    and cached_board_coords
                    and time.perf_counter() >= match_next_scan
                ):
                    # Poll the LIVE frame directly. The previous implementation
                    # spent up to 0.25s inside stable_initial_scan() before doing
                    # the real START test, which made a newly appeared starting
                    # board easy to miss. detect_new_game_state() already performs
                    # its own two-frame physical confirmation.
                    match_next_scan = (
                        time.perf_counter()
                        + MATCHMAKING_SCAN_INTERVAL
                    )

                    fresh_game = detect_new_game_state(
                        sct,
                        scrcpy_hwnd,
                        cached_board_coords,
                        source_frame=frame
                    )

                    if fresh_game is None:
                        progress(
                            "MATCH",
                            "waiting for START / START+WHITE-MOVE",
                            key="matchmaking_wait",
                            interval=0.75
                        )
                    else:
                        fresh_key = (
                            f"{int(fresh_game['perspective'])}:"
                            f"{fresh_game['kind']}:"
                            f"{fresh_game['first_move'].uci() if fresh_game.get('first_move') is not None else '-'}"
                        )

                        if fresh_key == new_match_start_key:
                            new_match_start_stable += 1
                        else:
                            new_match_start_key = fresh_key
                            new_match_start_stable = 1

                        print(
                            "[MATCH] Fresh game candidate | "
                            f"key={fresh_key} "
                            f"exact={fresh_game['exact']}/64 "
                            f"stable={new_match_start_stable}/2"
                        )

                        if new_match_start_stable >= 2:
                            board = fresh_game["board"]
                            visual_black_perspective = (
                                fresh_game["perspective"]
                            )
                            stockfish_color = (
                                fresh_game["stockfish_color"]
                            )
                            human_color = (
                                fresh_game["human_color"]
                            )
                            cached_board_grid = fresh_game["grid"]
                            baseline_frame = fresh_game["frame"]

                            game_ready = True
                            bot_thinking = False
                            analysis_state = None
                            last_bot_position_key = None
                            pending_bot_moves.clear()
                            pending_recovered_human = None
                            next_human_best_uci = None
                            opponent_pressure = False
                            opponent_match_history.clear()

                            next_main_turn_rescan = (
                                time.perf_counter()
                                + TURN_RESCAN_INTERVAL
                            )

                            _advantage_progress_target_cp = None
                            _advantage_progress_hold_moves = 0
                            _advantage_progress_hold_limit = random.randint(
                                HUMAN_ADVANTAGE_HOLD_MIN_MOVES,
                                HUMAN_ADVANTAGE_HOLD_MAX_MOVES
                            )
                            _advantage_progress_side = None

                            stockfish_moves_since_buffer = 0
                            next_buffer_after = random.randint(
                                RANDOM_BUFFER_MOVE_MIN,
                                RANDOM_BUFFER_MOVE_MAX
                            )

                            match_ui["phase"] = "GAME"
                            match_ui["requested_action"] = None
                            match_ui["result_text"] = "WAITING FOR NEW MATCH..."
                            match_ui["screen_guard"] = False
                            match_ui["board_obstruction"] = 0.0
                            match_result_streak = 0
                            match_auto_after = None

                            print(
                                "[MATCH] NEW GAME READY | "
                                f"Stockfish="
                                f"{'WHITE' if stockfish_color == chess.WHITE else 'BLACK'} "
                                f"| Human="
                                f"{'WHITE' if human_color == chess.WHITE else 'BLACK'}"
                            )

                            print(
                                "[MATCH] BOARD SIDE SETUP | "
                                f"bottom={'BLACK' if stockfish_color == chess.BLACK else 'WHITE'} "
                                f"| Stockfish={'WHITE' if stockfish_color == chess.WHITE else 'BLACK'} "
                                f"| Human={'WHITE' if human_color == chess.WHITE else 'BLACK'} "
                                f"| turn={'WHITE' if board.turn == chess.WHITE else 'BLACK'}"
                            )

                            print(
                                "[MATCH] FIRST-TURN DECISION | "
                                f"{'HUMAN' if board.turn == human_color else 'STOCKFISH'} "
                                "TO MOVE"
                            )

                            if fresh_game.get("first_move") is not None:
                                first_move = fresh_game["first_move"]

                                print(
                                    "[MATCH] WHITE MOVE ALREADY PRESENT | "
                                    f"{first_move.uci()} | internal board synced"
                                )

                            new_match_start_stable = 0
                            new_match_start_key = None

                if match_ui.get("phase") == "RESULT":
                    status = "RESULT SCREEN | REMATCH / NEW MATCH AUTO CONTROLS"

                elif match_ui.get("phase") == "AWAIT_RESULT":
                    status = "WAITING FOR RESULT SCREEN..."

                elif match_ui.get("phase") == "MATCHMAKING":
                    status = "WAITING FOR NEW MATCH..."

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

                    match_ui_draw(
                        display_frame,
                        match_ui,
                        cached_board_coords
                    )

                    draw_move_history_panel(
                        display_frame,
                        board,
                        cached_board_coords,
                        match_ui
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

                if match_ui.get("phase") not in ("GAME", "AWAIT_RESULT"):
                    match_ui_draw(
                        display_frame,
                        match_ui,
                        cached_board_coords
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
