"""Pure animation-mode + frame-index math for the map TUI player sprite.

No Textual, no time, no I/O — just numbers. The MapPane supplies elapsed
seconds (monotonic since snapshot arrival) and the snapshot's cooldown
duration; these functions decide the mode and which sprite frame to show."""

from enum import Enum


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
