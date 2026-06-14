"""Pure interpolation for the map's player-movement glide animation.

`glide_path` returns the sequence of viewport-center tiles to render while the
player-centered map slides from `start` to `end`: a Bresenham line, sampled
down to at most `max_steps` frames, always ending exactly at `end`, with the
`start` tile excluded. No Textual/IO dependency — fully unit-testable.
"""


def _bresenham(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    """Integer line from start to end inclusive (both endpoints included)."""
    x0, y0 = start
    x1, y1 = end
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    points: list[tuple[int, int]] = []
    x, y = x0, y0
    while True:
        points.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    return points


def _sample(frames: list[tuple[int, int]], max_steps: int) -> list[tuple[int, int]]:
    """Evenly pick `max_steps` frames across `frames`, always keeping the last."""
    if max_steps == 1:
        return [frames[-1]]
    n = len(frames)
    return [frames[round(i * (n - 1) / (max_steps - 1))] for i in range(max_steps)]


def glide_path(
    start: tuple[int, int], end: tuple[int, int], max_steps: int
) -> list[tuple[int, int]]:
    """Center tiles to render gliding start -> end (start excluded, ends at end).

    Empty when start == end. Capped to `max_steps` frames. Raises if max_steps < 1.
    """
    if max_steps < 1:
        raise ValueError(f"max_steps must be >= 1, got {max_steps}")
    if start == end:
        return []
    frames = _bresenham(start, end)[1:]   # drop the start tile
    if len(frames) <= max_steps:
        return frames
    return _sample(frames, max_steps)
