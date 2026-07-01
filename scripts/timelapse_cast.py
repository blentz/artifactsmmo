"""Time-lapse an asciicast v3 recording of the TUI: keep one animation sweep per
action, then skip the cooldown wait.

Why this is needed: the map pane loops a ~0.8s tool-swing over the WHOLE API
cooldown (map_pane.py SWING_SWEEP_SECONDS, clamped to cooldown_remaining at
_is_animating line 211). A raw cast therefore replays every action's full,
repetitive wait -- a 25s cooldown is ~31 identical sweeps. Idle-compression
(`asciinema rec --idle-time-limit`) can't help: the swing emits output every
0.15s, so there is no idle to compress. The fix is to DROP the redundant loop
frames, keeping only the first sweep of each action, then hard-cut to the next.

How it works (robust to the ticking cooldown countdown, which makes loops NOT
byte-identical): segment the stream at wholesale viewport repaints. A new action
clears the line cache (map_pane.py:147) and repaints ~every row = a BIG output
event; a within-cycle swing frame repaints only a 3-tile-row band = a SMALL
event; the status-pane countdown tick is tiny. So classify by output SIZE, keep
the first KEEP_SECONDS of each cycle at real speed, drop the rest until the next
big repaint, and give each cut a fixed SKIP_GAP beat.

asciicast v3 note: event timestamps are RELATIVE intervals (time since the prev
event), so dropping a frame or re-timing a cut is local -- no global re-basing.

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
#   KEEP_SECONDS  real-time window kept at each action's start. ~= one swing
#                 sweep (SWING_SWEEP_SECONDS is 0.8). Bigger -> more of the
#                 animation shown per action; smaller -> snappier but may clip a
#                 sweep mid-swing.
#   SKIP_GAP      fixed pause placed where a wait was collapsed -- the beat
#                 between actions. Bigger -> more relaxed; smaller -> faster.
#   BOUNDARY_BYTES  an "o" event larger than this is treated as a wholesale
#                 repaint (a new action). This is terminal-size dependent: a
#                 full 80x41 viewport repaint is many KB, a band repaint far
#                 less. Too HIGH -> boundaries missed -> everything after the
#                 first cycle's window is dropped (output truncates). Too LOW ->
#                 band frames misread as boundaries -> waits not collapsed.
#                 Tune by inspecting event sizes (see --stats).
# ---------------------------------------------------------------------------
KEEP_SECONDS = 0.9
SKIP_GAP = 0.4
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


def timelapse(events: list[Event], keep_seconds: float, skip_gap: float, boundary_bytes: int) -> Iterator[Event]:
    """Rewrite events: keep the first `keep_seconds` of each action cycle at real
    speed, drop the redundant loop frames after it, and give each cut a fixed
    `skip_gap` beat. Non-output events (resize/marker/exit) pass through."""
    t_in_cycle = keep_seconds  # so the pre-first-boundary preamble is kept, not dropped
    for event in events:
        interval, code, data = cast(float, event[0]), event[1], cast(str, event[2])
        if code != "o":
            yield event
            continue
        if is_cycle_boundary(data, boundary_bytes):
            yield [skip_gap, code, data]  # collapse the wait that preceded this action
            t_in_cycle = 0.0
        elif t_in_cycle < keep_seconds:
            yield [interval, code, data]  # live sweep -- keep at real speed
            t_in_cycle += interval
        # else: past the window and not a new action -> a redundant loop frame; drop.


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
                        help=f"seconds kept per action (default {KEEP_SECONDS})")
    parser.add_argument("--gap", type=float, default=SKIP_GAP,
                        help=f"beat between actions (default {SKIP_GAP})")
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
    rewritten = timelapse(events, args.keep, args.gap, args.boundary_bytes)
    write_cast(args.output, header, rewritten)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
