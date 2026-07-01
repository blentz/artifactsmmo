"""Time-lapse an asciicast v3 recording of the TUI: play one animation sweep per
action at real speed, then fast-forward the cooldown wait.

Why this is needed: the map pane loops a ~0.8s tool-swing over the WHOLE API
cooldown (map_pane.py SWING_SWEEP_SECONDS, clamped to cooldown_remaining at
_is_animating line 211). A raw cast therefore replays every action's full,
repetitive wait -- a 25s cooldown is ~31 identical sweeps. Idle-compression
(`asciinema rec --idle-time-limit`) can't help: the swing emits output every
0.15s, so there is no idle to compress.

Why we compress time instead of dropping frames: asciicast "o" events are an
INCREMENTAL byte stream to a terminal emulator -- cursor moves, partial-line
writes and scroll ops, all stateful. Textual paints diffs, not full-screen
redraws, so deleting middle frames leaves the cursor/scroll state diverged and
every later frame misaligns. We therefore keep EVERY byte (terminal state stays
coherent) and only rewrite the RELATIVE intervals: the first KEEP_SECONDS of
each action plays at real speed (one clean sweep); every frame after that, until
the next action, is emitted at BLUR_SECONDS so the redundant loops rush past in
a fraction of a second without vanishing.

How actions are detected (robust to the ticking cooldown countdown, which makes
loops NOT byte-identical): a new action clears the line cache (map_pane.py:147)
and repaints ~every row = a BIG output event; a within-cycle swing frame
repaints only a 3-tile-row band = a SMALL event; the countdown tick is tiny. So
classify by output SIZE. A missed/spurious boundary only nudges pacing -- since
no bytes are dropped, the screen is always coherent.

asciicast v3 note: event timestamps are RELATIVE intervals (time since the prev
event), so re-timing a single event is local -- no global re-basing.

Usage:
    asciinema rec raw.cast -c 'uv run artifactsmmo play <char> --tui'
    uv run python scripts/timelapse_cast.py raw.cast demo.cast
    asciinema play demo.cast
"""

import argparse
import json
from collections.abc import Iterator
from typing import cast

Event = list[object]  # asciicast v3 event: [interval, code, data]

# ---------------------------------------------------------------------------
# Tuning knobs -- these three values are the whole "look". Defaults are a
# reasonable starting point; adjust to taste after eyeballing `asciinema play`.
#
#   KEEP_SECONDS  real-time window played at each action's start. ~= one swing
#                 sweep (SWING_SWEEP_SECONDS is 0.8). Bigger -> more of the
#                 animation shown per action; smaller -> snappier but may clip a
#                 sweep mid-swing.
#   BLUR_SECONDS  interval given to every frame AFTER the window until the next
#                 action -- how fast the redundant loops rush past. Smaller ->
#                 the wait blurs by quicker. A 25s wait (~165 frames) at 0.008
#                 rushes past in ~1.3s. Not zero, so the terminal still keeps up.
#   BOUNDARY_BYTES  an "o" event larger than this starts a new action (a
#                 wholesale repaint), resetting the real-time window. Terminal-
#                 size dependent: a full 80x41 viewport repaint is many KB, a
#                 band repaint far less. Too HIGH -> new actions missed -> whole
#                 cast blurs after the first window. Too LOW -> band frames
#                 misread as new actions -> waits not compressed. No bytes are
#                 ever dropped, so a wrong value only mis-paces, never corrupts.
#                 Tune by inspecting event sizes (see --stats).
# ---------------------------------------------------------------------------
KEEP_SECONDS = 0.9
BLUR_SECONDS = 0.008
BOUNDARY_BYTES = 2000


def is_cycle_boundary(data: str, boundary_bytes: int) -> bool:
    """True when an output event is the start of a new action cycle (a wholesale
    viewport repaint) rather than a within-cycle swing frame or countdown tick.

    Keyed on output SIZE, not content, so the once-a-second cooldown countdown
    (which makes successive loops differ byte-for-byte) does not fool it.
    """
    return len(data) > boundary_bytes


def load_cast(path: str) -> tuple[dict[str, object], list[Event]]:
    """Return (header, events) from an asciicast v3 file."""
    header: dict[str, object] | None = None
    events: list[Event] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            parsed = json.loads(line)
            if header is None:
                header = parsed
                continue
            events.append(parsed)
    if header is None:
        raise ValueError(f"{path}: no header line -- not an asciicast file")
    if header.get("version") != 3:
        raise ValueError(f"{path}: version {header.get('version')}, expected asciicast v3")
    return header, events


def timelapse(events: list[Event], keep_seconds: float, blur_seconds: float, boundary_bytes: int) -> Iterator[Event]:
    """Rewrite intervals so the first `keep_seconds` of each action plays at real
    speed and every frame after it (until the next action) rushes past at
    `blur_seconds`. EVERY event is emitted -- no bytes are dropped, so the
    terminal stays coherent. Non-output events (resize/marker/exit) pass through
    unchanged at real time so a resize never gets swallowed by a blur."""
    t_in_cycle = keep_seconds  # so a pre-first-action preamble plays, not blurs
    for event in events:
        interval, code, data = cast(float, event[0]), event[1], cast(str, event[2])
        if code != "o":
            yield event
            continue
        if is_cycle_boundary(data, boundary_bytes):
            yield [interval, code, data]  # new action -> real speed, reset window
            t_in_cycle = 0.0
        elif t_in_cycle < keep_seconds:
            yield [interval, code, data]  # live sweep -- keep at real speed
            t_in_cycle += interval
        else:
            yield [min(interval, blur_seconds), code, data]  # redundant loop -> rush past, keep bytes
            t_in_cycle += interval


def write_cast(path: str, header: dict[str, object], events: Iterator[Event]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(header))
        fh.write("\n")
        for event in events:
            fh.write(json.dumps(event))
            fh.write("\n")


def print_stats(events: list[Event]) -> None:
    """Histogram of output-event sizes -- use this to pick BOUNDARY_BYTES."""
    sizes = sorted(len(cast(str, e[2])) for e in events if e[1] == "o")
    if not sizes:
        print("no output events")
        return
    n = len(sizes)
    pct = {p: sizes[min(n - 1, p * n // 100)] for p in (50, 75, 90, 95, 99)}
    print(f"output events: {n}")
    print(f"bytes  min={sizes[0]}  p50={pct[50]}  p75={pct[75]}  p90={pct[90]}  "
          f"p95={pct[95]}  p99={pct[99]}  max={sizes[-1]}")
    print("pick BOUNDARY_BYTES between the swing-frame cluster (low) and the repaint cluster (high).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", help="raw asciicast v3 file")
    parser.add_argument("output", nargs="?", help="time-lapsed output file (omit with --stats)")
    parser.add_argument("--keep", type=float, default=KEEP_SECONDS,
                        help=f"real-time seconds played per action (default {KEEP_SECONDS})")
    parser.add_argument("--blur", type=float, default=BLUR_SECONDS,
                        help=f"interval for fast-forwarded loop frames (default {BLUR_SECONDS})")
    parser.add_argument("--boundary-bytes", type=int, default=BOUNDARY_BYTES,
                        help=f"repaint size threshold (default {BOUNDARY_BYTES})")
    parser.add_argument("--stats", action="store_true",
                        help="print output-size histogram and exit (helps pick --boundary-bytes)")
    args = parser.parse_args()

    header, events = load_cast(args.input)
    if args.stats:
        print_stats(events)
        return
    if not args.output:
        parser.error("output path required (or pass --stats)")
    rewritten = timelapse(events, args.keep, args.blur, args.boundary_bytes)
    write_cast(args.output, header, rewritten)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
