"""Convert an asciicast v3 recording to v2, for tools that only read v2 (e.g.
`agg` 1.5.0, the asciicast->gif renderer).

The two formats differ in exactly two ways that matter here:
  * header: v3 nests terminal size/theme under `term` (`term.cols`,
    `term.rows`, `term.theme`); v2 has flat `width`/`height`/`theme`.
  * events: v3 timestamps are RELATIVE intervals (time since the prev event);
    v2 timestamps are ABSOLUTE (seconds since start). So we accumulate.

The `"x"` (exit) event that v3 appends has no v2 equivalent and is dropped.

Usage:
    uv run python scripts/cast_v3_to_v2.py in_v3.cast out_v2.cast
    ~/.local/bin/agg out_v2.cast out.gif        # then render the gif
"""

import argparse
import json
from typing import cast


def convert(src: str, dst: str) -> tuple[int, int, int]:
    """Write `src` (asciicast v3) to `dst` as v2. Returns (cols, rows, events)."""
    header: dict[str, object] | None = None
    events: list[list[object]] = []
    with open(src, encoding="utf-8") as fh:
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
        raise ValueError(f"{src}: no header line -- not an asciicast file")
    if header.get("version") != 3:
        raise ValueError(f"{src}: version {header.get('version')}, expected asciicast v3")

    term = cast("dict[str, object]", header.get("term", {}))
    out_header: dict[str, object] = {"version": 2, "width": term.get("cols"), "height": term.get("rows")}
    if "timestamp" in header:
        out_header["timestamp"] = header["timestamp"]
    if term.get("theme"):
        out_header["theme"] = term["theme"]
    if header.get("env"):
        out_header["env"] = header["env"]

    written = 0
    with open(dst, "w", encoding="utf-8") as out:
        out.write(json.dumps(out_header) + "\n")
        t = 0.0
        for interval, code, data in events:
            if code == "x":  # v3 exit marker; no v2 equivalent
                continue
            t += cast(float, interval)
            out.write(json.dumps([round(t, 6), code, data]) + "\n")
            written += 1
    return cast(int, out_header["width"]), cast(int, out_header["height"]), written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", help="asciicast v3 file")
    parser.add_argument("output", help="asciicast v2 file to write")
    args = parser.parse_args()
    cols, rows, n = convert(args.input, args.output)
    print(f"wrote {args.output}: {cols}x{rows}, {n} events")


if __name__ == "__main__":
    main()
