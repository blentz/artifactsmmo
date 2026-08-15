"""Corroborate `GREY_SKILL_GAP` — the gather/craft zero-xp band — against live
trace data.

Server-axiom-signoff discipline, the same one `xp_formula_replay.py` applies to
the COMBAT curve. The documented rule
(https://docs.artifactsmmo.com/concepts/skills) says gathering and crafting xp
falls to zero for content "10+ levels below your skill level", but the prose is
ambiguous at the boundary: does a gap of exactly 10 pay? The decision core
`ai/skill_xp_positive` needs an exact integer answer, so this replays every
observed `ok` Gather cycle and reports pays/zero bucketed by

    gap = skill_level(at cycle start) - resource_level

A record's `state` is the RESULT of that record's OWN action, not a
before-snapshot: ground-truthed against 19691 `Fight` cycles,
`state[i] - state[i-1] == fight_xp` holds 19691/19691 (100%), while
`state[i+1] - state[i] == fight_xp` (the pairing this file used before a
code-review round caught it) holds only 10777/19691 (55%). So record i's
action is credited against the PAIR `(records[i-1].state, records[i].state)`
-- one step BACK is the pre-action snapshot, and the record's own state is
post.

WHAT THE OLD "ATTRIBUTION LAG" EXPLANATION ACTUALLY WAS: under the wrong
pairing, a handful of gap >= 11 buckets showed a few apparent payers, and this
docstring used to explain them as xp landing on a "neighbouring" cycle. It
does not: those were exactly the off-by-one above, each one crediting a grey
gather with the NEXT record's real yield (a `spruce_tree` gather's own xp,
misattributed to the `ash_tree` cycle beside it, etc.). Under the corrected
pairing there are no such outliers left to explain -- see the VIOLATIONS and
OUTLIERS lines below, which are computed, not asserted.

Crafting is reported separately and remains structurally ADVISORY (this
script's VIOLATION-raising and exit code stay scoped to GATHER, matching the
plan before this fix): but under the corrected pairing CRAFT is exactly as
clean as GATHER -- zero mixed buckets, matching the independent replay in
`formal/diff/craft_xp_replay.py`, which finds zero below-band payers and zero
above-band non-zero-craft observations across 450 craft cycles. "Craft results
lag" was never a property of crafting; it was the same bug measured on noisier
data (crafts are rarer than gathers, so fewer misattributions were needed to
produce a visible outlier).

What would falsify `GREY_SKILL_GAP = 11`: a gap >= 11 bucket that PREDOMINANTLY
pays, or an in-band bucket that never pays at all. Both are reported as explicit
VIOLATION lines and exit non-zero. Sub-majority payers in an out-of-band bucket
are reported as OUTLIERS with their counts, so the lag rate stays visible
instead of being asserted away.

Output: formal/diff/gather_xp_replay_report.txt + stdout.
Usage: uv run python formal/diff/gather_xp_replay.py [TRACE_DIR] [SNAPSHOT]
"""

import collections
import json
import re
import sys
from pathlib import Path

from artifactsmmo_cli.ai.skill_xp_positive import GREY_SKILL_GAP, skill_xp_positive

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT = REPO_ROOT / "formal" / "diff" / "gather_xp_replay_report.txt"
_CRAFT_RE = re.compile(r"Craft\((\w+)[x×]")


def _catalog(snapshot: Path) -> tuple[dict[str, tuple[str, int]], dict[str, tuple[str, int]]]:
    """`{resource_code: (skill, level)}` and `{item_code: (craft_skill, craft_level)}`
    from a raw game-data cache dump."""
    data = json.loads(snapshot.read_text())
    resources = {r["code"]: (r["skill"], r["level"]) for r in data["resources"]}
    crafts = {
        i["code"]: (i["craft"]["skill"], i["craft"]["level"])
        for i in data["items"]
        if i.get("craft") and i["craft"].get("skill")
    }
    return resources, crafts


def _paid(pre: dict, post: dict, skill: str) -> bool:
    """True when `skill` gained a level or xp between the two cycle snapshots."""
    return (post["skills"].get(skill, 0) > pre["skills"].get(skill, 0)
            or post["skill_xp"].get(skill, 0) > pre["skill_xp"].get(skill, 0))


def _replay(traces: list[Path], resources: dict[str, tuple[str, int]],
            crafts: dict[str, tuple[str, int]]) -> tuple[dict, dict, int]:
    gathers: dict[int, list[int]] = collections.defaultdict(lambda: [0, 0])
    crafted: dict[int, list[int]] = collections.defaultdict(lambda: [0, 0])
    used = 0
    for path in traces:
        try:
            records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        except json.JSONDecodeError:
            continue
        if not records or "skills" not in (records[0].get("state") or {}):
            continue
        used += 1
        # (prev_rec, cur_rec): cur_rec HOLDS the action/outcome under test, and
        # cur_rec["state"] is that action's RESULT; prev_rec["state"] is the
        # snapshot from BEFORE it ran. See module docstring.
        for prev_rec, cur_rec in zip(records, records[1:], strict=False):
            if cur_rec.get("outcome") != "ok":
                continue
            pre, post = prev_rec.get("state") or {}, cur_rec.get("state") or {}
            if "skills" not in pre or "skills" not in post:
                continue
            action = str(cur_rec.get("action"))
            if action.startswith("Gather("):
                entry = resources.get(action[len("Gather("):-1])
                bucket = gathers
            else:
                match = _CRAFT_RE.match(action)
                entry = crafts.get(match.group(1)) if match else None
                bucket = crafted
            if entry is None:
                continue
            skill, level = entry
            gap = pre["skills"].get(skill, 1) - level
            bucket[gap][0 if _paid(pre, post, skill) else 1] += 1
    return gathers, crafted, used


def _render(title: str, buckets: dict[int, list[int]],
            advisory: bool) -> tuple[list[str], list[str], list[str]]:
    lines = [f"\n## {title}", f"{'gap':>4} {'pays':>6} {'zero':>6}  verdict"]
    violations: list[str] = []
    outliers: list[str] = []
    for gap in sorted(buckets):
        pays, zero = buckets[gap]
        # The model's claim for this bucket, from the live constant. A gap-g
        # bucket is probed at the lowest real content level (1).
        predicted = skill_xp_positive(1, 1 + gap)
        verdict = "PAYS" if pays and not zero else ("ZERO" if zero and not pays else "mixed")
        flag = ""
        if predicted and pays == 0 and zero:
            flag = "  <-- VIOLATION: model says pays, bucket never paid"
        elif not predicted and pays > zero:
            flag = f"  <-- VIOLATION: model says zero, bucket predominantly paid ({pays}/{pays + zero})"
        elif not predicted and pays:
            flag = f"  <-- outlier: {pays}/{pays + zero} paying (unexplained -- investigate before assuming lag)"
            outliers.append(f"gap={gap}: {pays}/{pays + zero}")
        if flag.startswith("  <-- VIOLATION") and not advisory:
            violations.append(f"gap={gap} pays={pays} zero={zero}{flag}")
        lines.append(f"{gap:4d} {pays:6d} {zero:6d}  {verdict}{flag}")
    return lines, violations, outliers


def main() -> int:
    trace_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT
    snapshot = (Path(sys.argv[2]) if len(sys.argv) > 2
                else Path.home() / ".cache/artifactsmmo/gamedata-api.artifactsmmo.com.json")
    traces = sorted(trace_dir.glob("play-trace-*.jsonl"))
    if not traces:
        print(f"no play-trace-*.jsonl under {trace_dir}", file=sys.stderr)
        return 2
    resources, crafts = _catalog(snapshot)
    gathers, crafted, used = _replay(traces, resources, crafts)

    lines = [
        "# GREY_SKILL_GAP corroboration report",
        f"traces={used} snapshot={snapshot}",
        f"model: skill_xp_positive(content, skill) = content >= 1 and "
        f"skill < content + {GREY_SKILL_GAP}",
    ]
    gather_lines, violations, outliers = _render(
        f"GATHER (load-bearing: {sum(sum(v) for v in gathers.values())} cycles)",
        gathers, advisory=False)
    craft_lines, _, _ = _render(
        f"CRAFT (ADVISORY — attribution lag: "
        f"{sum(sum(v) for v in crafted.values())} cycles)", crafted, advisory=True)
    lines += gather_lines + craft_lines
    lines.append("")
    lines.append("OUT-OF-BAND OUTLIERS (unexplained if any; see module docstring for why "
                 "'attribution lag' is no longer assumed): " + (
        "; ".join(outliers) if outliers else "none"))
    lines.append("VIOLATIONS: " + (
        "; ".join(violations) if violations
        else f"none — GREY_SKILL_GAP = {GREY_SKILL_GAP} holds on every gather bucket"))
    report = "\n".join(lines) + "\n"
    REPORT.write_text(report)
    print(report)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
