"""Pure animation-mode + frame-index math for the map TUI player sprite.

No Textual, no time, no I/O. The mode/index functions are pure numbers; the
MapPane supplies elapsed seconds (monotonic since snapshot arrival) and the
snapshot's cooldown duration. `swing_overlay` additionally maps a swing frame to
the tool sprites to paint (pure data from `sprites.py`)."""

from enum import Enum

from artifactsmmo_cli.tui.sprites import FIGHT_HEAD, GATHER_HEAD, Sprite, grip_overlay


class Mode(Enum):
    IDLE = "idle"
    GLIDE = "glide"
    GATHER_SWING = "gather_swing"
    FIGHT_SWING = "fight_swing"
    PLANNING = "planning"


_KIND_TO_MODE = {
    "move": Mode.GLIDE,
    "gather": Mode.GATHER_SWING,
    "fight": Mode.FIGHT_SWING,
}


def current_mode(action_kind: str, planning_active: bool,
                 elapsed: float, duration: float) -> Mode:
    """Planning overrides all. Otherwise, while the action's cooldown is still
    running (0 < elapsed < duration), the kind picks the animation; once the
    cooldown has elapsed (or there is none, or it is rest/other) → IDLE."""
    if planning_active:
        return Mode.PLANNING
    if duration <= 0.0 or elapsed >= duration:
        return Mode.IDLE
    return _KIND_TO_MODE.get(action_kind, Mode.IDLE)


def swing_frame_index(elapsed: float, frame_count: int, sweep_seconds: float) -> int:
    """Looping sweep position in [0, frame_count). Each sweep takes
    sweep_seconds and repeats. Degenerate sweep -> frame 0."""
    if frame_count <= 1 or sweep_seconds <= 0.0:
        return 0
    phase = (elapsed % sweep_seconds) / sweep_seconds   # [0,1)
    return min(round(phase * frame_count), frame_count - 1)


def glide_index(elapsed: float, duration: float, frame_count: int,
                arrive_fraction: float = 0.9) -> int:
    """Index into glide frames so the last frame is reached at
    arrive_fraction*duration (arrives just before the next action), clamped."""
    if frame_count <= 1:
        return 0
    window = duration * arrive_fraction
    if window <= 0.0:
        return frame_count - 1
    progress = min(elapsed / window, 1.0)               # [0,1]
    return min(int(round(progress * (frame_count - 1))), frame_count - 1)


_GATHER_OFFSETS: list[tuple[int, int]] = [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1)]
_FIGHT_OFFSETS: list[tuple[int, int]] = [(0, -1), (-1, -1), (-1, 0), (-1, 1), (0, 1)]
SWING_FRAME_COUNT = 5      # arc frames per sweep (len of the offset lists)


def swing_overlay(mode: Mode, frame_index: int) -> dict[tuple[int, int], Sprite]:
    """Overlay map for a swing frame: the head in the arc-neighbor tile plus a
    grip in the player tile (0,0). Empty for non-swing modes. The head offset
    sweeps a half-circle — gather right/CW, fight left/CCW (mirrored)."""
    if mode is Mode.GATHER_SWING:
        offsets, head = _GATHER_OFFSETS, GATHER_HEAD
    elif mode is Mode.FIGHT_SWING:
        offsets, head = _FIGHT_OFFSETS, FIGHT_HEAD
    else:
        return {}
    off = offsets[frame_index % len(offsets)]
    return {(0, 0): grip_overlay(off[0], off[1]), off: head}
