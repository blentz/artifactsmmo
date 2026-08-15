"""Test whether craft XP is PROPORTIONAL to `craft_level` -- the numerator
`_beats` (`ai/tiers/skill_grind_selection.py`) uses as the CARDINAL term of an
XP-per-action rate.

Server-axiom-signoff discipline, the same one `gather_xp_replay.py` applies to
the grey-XP band: THE ANSWER IS OBSERVED, NOT ASSUMED. The documented formula
(https://docs.artifactsmmo.com/concepts/skills)

    XP = Round((XP_base + (content_level / skill_level) * k) * level_penalty
               * wisdom_bonus)

names `XP_base`, `k` and the per-rung `level_penalty` as free parameters that
are in neither the docs nor the API. At a fixed skill level, XP is monotone
nondecreasing in content level -- enough to justify `craft_level` as an
ORDINAL proxy for a rung's payoff. Using it as the numerator of a RATE
(`craft_level / acquire_steps`) additionally assumes XP is proportional to it,
which is a claim about a CONSTANT ratio at fixed skill level, and that is what
this module tests.

DATA SOURCE: `play-trace-*.jsonl`, `argv[1]` (default `REPO_ROOT`, matching
`gather_xp_replay.py`'s own convention -- traces are gitignored session
artifacts that live wherever `play --trace-file` was run, not inside any one
git checkout).

A RECORD'S `state` IS THE RESULT OF ITS OWN ACTION, NOT THE STATE BEFORE IT.
This is the one fact the whole replay hangs on, and getting it backwards is
exactly the bug a code-review round caught here: ground-truthed against 19691
`Fight` cycles, `state[i] - state[i-1] == fight_xp` holds 19691/19691 (100%),
while `state[i+1] - state[i] == fight_xp` holds only 10777/19691 (55%). So
record `i`'s action (`action`, `outcome`) is credited against the PAIR
`(records[i-1].state, records[i].state)` -- the state one step BACK is the
PRE-action snapshot, and the record's own state is POST. The first version of
this file paired `(records[i].state, records[i+1].state)` for record `i`'s
own action, which silently credited each craft with its NEXT NEIGHBOUR's
result instead of its own. Worked case that a reviewer traced by hand
(`play-trace-HAL-20260804-001113.jsonl`, cycles 178-180, mining 12):
`Craft(copper_bar×2)` at cycle 179 left `mining_xp` UNCHANGED from cycle 178
(1939 -> 1939, the correct, PAYS-ZERO grey-band reading -- copper_bar is
craft_level 1, gap 11); the old pairing instead diffed cycle 179's own reading
against cycle 180's `Gather(iron_rocks)` result (1939 -> 1956, +17) and
credited that 17 to the craft. That one misattribution was the entire
`skill_level=12, craft_level=1` arm of the first committed table.

GREY-BAND ZEROS ARE KEPT, NOT DISCARDED. The first version excluded any
same-cycle result of `xp <= 0` as "attribution lag" -- but with the pairing
fixed, an exact zero at `gap = skill_level - craft_level >= GREY_SKILL_GAP`
(`ai/skill_xp_positive.py`) is not missing data, it is the grey band paying
literally nothing, which is real evidence for THIS question (a craft that
pays 0 regardless of `craft_level` is the sharpest possible violation of
proportionality). Discarding it was also a BIASED filter along the axis under
test: low-`craft_level` items sit deep in-band far more often (high
`skill_level - craft_level` gaps accumulate as a character levels the
matching skill on cheap early recipes), so `xp <= 0` was disproportionately
dropping low-`craft_level` observations -- the corrected table below keeps
every same-cycle, same-skill-level observation, zero or not.

QUANTITY NORMALIZATION HAS TWO SEPARATE FACTORS, NOT ONE. A round of review
caught that an earlier version conflated them under a single "qty" and both
its number and its justification were wrong.

(1) The action string `Craft(item_code×N)` REQUESTS N executions of the
recipe -- but N is what was ASKED for, not necessarily what the server
ACTUALLY ran, and `xp`/`inventory_used` only ever reflect what was actually
executed. Worked case (`play-trace-C3P0-20260803-230040.jsonl`, cycle 28,
mining 11): `Craft(copper_bar×4)` posts +5 xp with `inventory_used` dropping
exactly 9 (-10 ore, +1 bar) -- ONE execution of the 10-ore recipe, not four;
the other three requested repetitions never happened and their "missing" 15
xp is not lurking on a later cycle, it was simply never earned. Dividing by
the REQUESTED N (4) instead of the actual executed count (1) understates the
true per-execution xp (5/4 = 1.25 instead of 5.00) whenever the server
executes fewer reps than asked; it can never overstate it. That is why the
representative statistic per `(item, skill_level)` is the MAX observed value
across cycles, not the mean -- a mean blends truncated and untruncated
readings and biases low, while the max, taken over enough cycles, recovers a
reading where request and execution agreed. (An earlier version of this file
attributed the same MAX choice to a different, disproven mechanism -- "partial
in-window batch posting" -- which this cycle-28 case rules out directly:
nothing about it looks like a partial post of a real 4-execution batch, it
looks exactly like a real 1-execution craft.)

(2) Independently, a recipe's OWN `craft.quantity` (the game-data snapshot's
per-item field) is how many output items ONE execution produces, and it is
not always 1: `small_health_potion`, `earth_boost_potion` and
`fire_boost_potion` all craft at quantity=2. `Craft(small_health_potion×1)`
posts 118 xp with `inventory_used` net -1 (-3 `sunflower` consumed -- that is
the item code; the recipe is `{sunflower: 3}` at quantity 2 -- and +2
potions) -- ONE execution, TWO items, so the per-ITEM rate is 118/2 = 59, not
118. Mixing recipes of different `craft.quantity` on a raw "xp per requested
execution" basis silently compares two different units.

Both factors are folded into a single, correctly-scaled reading:
`xp_per_item = xp / (requested_executions * craft.quantity)`, taking the MAX
across a (item, skill_level) group per factor (1) above. This is confirmed
exact wherever `craft.quantity == 1` and request/execution agree: `iron_bar`
posts 24 xp at ×1 and 120 at ×5 (24/item both times); `copper_bar` posts
5/10/20 at ×1/2/4 (5/item). All figures and ratios reported below are on this
per-item basis.

Output: formal/diff/craft_xp_replay_report.txt + stdout.
Usage: uv run python formal/diff/craft_xp_replay.py [TRACE_DIR] [SNAPSHOT] [LEARNING_DB]
"""

import collections
import json
import re
import sqlite3
import statistics
import sys
from pathlib import Path

from artifactsmmo_cli.ai.skill_xp_positive import GREY_SKILL_GAP
from artifactsmmo_cli.learning_db_path import default_learn_db_path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT = REPO_ROOT / "formal" / "diff" / "craft_xp_replay_report.txt"
_CRAFT_RE = re.compile(r"Craft\((\w+)[x×](\d+)\)")


class CraftObservation:
    """One craft cycle's exact xp yield, correctly attributed to ITS OWN
    action (see module docstring). Pure data; exempt from one-class-per-file
    (tightly-coupled value object for this replay only)."""

    __slots__ = ("craft_level", "item_code", "items_per_execution", "requested_executions", "skill_level", "xp")

    def __init__(
        self,
        item_code: str,
        craft_level: int,
        skill_level: int,
        requested_executions: int,
        items_per_execution: int,
        xp: int,
    ) -> None:
        self.item_code = item_code
        self.craft_level = craft_level
        self.skill_level = skill_level
        # The N in `Craft(item×N)` -- REQUESTED, not necessarily executed.
        # See module docstring factor (1).
        self.requested_executions = requested_executions
        # The recipe's own `craft.quantity` -- items produced per execution.
        # See module docstring factor (2).
        self.items_per_execution = items_per_execution
        self.xp = xp

    @property
    def xp_per_item(self) -> float:
        return self.xp / (self.requested_executions * self.items_per_execution)

    @property
    def gap(self) -> int:
        return self.skill_level - self.craft_level


def _craft_catalog(snapshot: Path) -> dict[str, tuple[str, int, int]]:
    """`{item_code: (craft_skill, craft_level, craft_quantity)}` from a raw
    game-data cache dump. `craft_quantity` is items produced per execution
    (usually 1; some alchemy recipes produce 2 -- see module docstring)."""
    data = json.loads(snapshot.read_text())
    return {
        i["code"]: (i["craft"]["skill"], i["craft"]["level"], i["craft"].get("quantity", 1))
        for i in data["items"]
        if i.get("craft") and i["craft"].get("skill")
    }


def _sqlite_skill_level_note(db_path: Path) -> str:
    """One-line, live-schema-checked note on whether the OTHER candidate data
    source (the learning store's `cycles` table) carries a per-skill-level
    column. Best-effort: a missing/unreadable db degrades to a plain note
    rather than failing the whole replay, since this is context, not the
    measurement itself. This finding is unaffected by the pairing bug fixed
    elsewhere in this module -- it is a schema fact, not a computed one."""
    if not db_path.exists():
        return f"SQLITE NOTE: no learning db at {db_path}; schema not checked."
    conn = sqlite3.connect(str(db_path))
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(cycles)")}
    finally:
        conn.close()
    skill_level_cols = {c for c in columns if "skill" in c and "level" in c}
    if skill_level_cols:
        return f"SQLITE NOTE: cycles table DOES carry skill-level column(s): {sorted(skill_level_cols)}."
    return (
        f"SQLITE NOTE: {db_path}'s cycles table has NO per-skill-level column "
        "(checked live via PRAGMA table_info) -- only aggregate character "
        "`level` and the skill-xp DELTA. This is why this replay reads "
        "play-trace-*.jsonl instead."
    )


def _replay(
    traces: list[Path], crafts: dict[str, tuple[str, int, int]]
) -> tuple[list[CraftObservation], collections.Counter[str], int]:
    observations: list[CraftObservation] = []
    skipped: collections.Counter[str] = collections.Counter()
    used = 0
    for path in traces:
        try:
            records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        except json.JSONDecodeError:
            continue
        if not records or "skills" not in (records[0].get("state") or {}):
            continue
        used += 1
        # (prev_rec, cur_rec): cur_rec HOLDS the action/outcome being tested,
        # and cur_rec.state is that action's RESULT. prev_rec.state is the
        # snapshot from BEFORE it ran -- see module docstring.
        for prev_rec, cur_rec in zip(records, records[1:], strict=False):
            if cur_rec.get("outcome") != "ok":
                continue
            match = _CRAFT_RE.match(str(cur_rec.get("action")))
            if not match:
                continue
            item_code, qty_str = match.group(1), match.group(2)
            entry = crafts.get(item_code)
            if entry is None:
                skipped["item_not_in_catalog"] += 1
                continue
            skill, craft_level, items_per_execution = entry
            pre, post = prev_rec.get("state") or {}, cur_rec.get("state") or {}
            if "skills" not in pre or "skills" not in post:
                skipped["missing_state"] += 1
                continue
            pre_level, post_level = pre["skills"].get(skill), post["skills"].get(skill)
            if pre_level is None or post_level is None:
                skipped["skill_not_in_state"] += 1
                continue
            if post_level == pre_level + 1:
                # Same-cycle level-up: the true yield spans the old level's
                # remaining xp plus what banked into the new one, and this
                # trace format carries no per-skill max_xp to bridge that
                # exactly (unlike character xp/level, which the trace DOES
                # carry). Excluded as unmeasurable, not as zero or as lag.
                skipped["same_cycle_levelup_unmeasurable"] += 1
                continue
            if post_level != pre_level:
                skipped["skill_level_regressed_or_multijump"] += 1
                continue
            xp = post["skill_xp"].get(skill, 0) - pre["skill_xp"].get(skill, 0)
            if xp < 0:
                skipped["unexpected_negative_same_level"] += 1
                continue
            # xp == 0 is KEPT (see module docstring: the grey band paying
            # nothing is real evidence, not missing data).
            observations.append(
                CraftObservation(
                    item_code, craft_level, pre_level, int(qty_str), items_per_execution, xp
                )
            )
    return observations, skipped, used


def _representative_per_item(
    observations: list[CraftObservation],
) -> dict[tuple[str, int], tuple[float, int, int]]:
    """`{(item_code, skill_level): (max_xp_per_item, n_cycles, craft_level)}`.
    MAX rather than mean per the module docstring's QUANTITY NORMALIZATION
    section, factor (1): a request for N executions that the server only
    partially fulfils can only under-report the true per-execution (hence
    per-item) xp when divided by the REQUESTED N, never over-report it, so
    the max across observed cycles for the same item at the same skill_level
    recovers a reading where request and execution agreed."""
    grouped: dict[tuple[str, int], list[CraftObservation]] = collections.defaultdict(list)
    for obs in observations:
        grouped[(obs.item_code, obs.skill_level)].append(obs)
    return {
        key: (max(o.xp_per_item for o in obs_list), len(obs_list), obs_list[0].craft_level)
        for key, obs_list in grouped.items()
    }


def _render_by_pair(
    representative: dict[tuple[str, int], tuple[float, int, int]],
) -> tuple[list[str], dict[tuple[int, int], list[float]]]:
    by_pair: dict[tuple[int, int], list[float]] = collections.defaultdict(list)
    lines = [
        "",
        "## BY ITEM (representative xp/item = MAX across cycles at that skill_level; see docstring)",
        f"{'item_code':22} {'skill_lvl':>9} {'craft_lvl':>9} {'gap':>4} {'n':>4} {'xp/item':>8}",
    ]
    for (item_code, skill_level), (rep_xp, n, craft_level) in sorted(
        representative.items(), key=lambda kv: (kv[1][2], kv[0][1], kv[0][0])
    ):
        gap = skill_level - craft_level
        lines.append(
            f"{item_code:22} {skill_level:9d} {craft_level:9d} {gap:4d} {n:4d} {rep_xp:8.2f}"
        )
        by_pair[(skill_level, craft_level)].append(rep_xp)
    lines.append("")
    lines.append("## BY (skill_level, craft_level) -- mean/min/max of the item representatives above")
    lines.append(f"{'skill_lvl':>9} {'craft_lvl':>9} {'n_items':>7} {'mean':>8} {'min':>8} {'max':>8}")
    for skill_level, craft_level in sorted(by_pair):
        xps = by_pair[(skill_level, craft_level)]
        lines.append(
            f"{skill_level:9d} {craft_level:9d} {len(xps):7d} {statistics.mean(xps):8.2f} "
            f"{min(xps):8.2f} {max(xps):8.2f}"
        )
    return lines, by_pair


def _ratio_table(
    by_pair: dict[tuple[int, int], list[float]],
) -> tuple[list[str], dict[int, dict[int, float]], set[int]]:
    """Per skill_level with >=2 distinct craft_levels: mean xp per craft_level
    and the ratio xp/craft_level, plus the SIGN of the change between each
    consecutive pair of observed craft_levels -- computed facts, not a
    judgment about whether they mean the ratio is 'basically constant'.

    THE GROUPING HAS NO SKILL COMPONENT, so a bucket can compare rungs of
    DIFFERENT skills -- five of the eleven qualifying buckets do (skill_level 5,
    7, 8, 9, 11), including all four behind the "ratio rises" reading in
    `skill_grind_selection._beats`. `XP_base` and `k` are per-SKILL parameters
    (see this module's own docstring), so a cross-skill step is weaker evidence
    about `craft_level` than a within-skill one, and `_beats` only ever compares
    rungs within one skill. The REFUTED verdict does not depend on them
    (skill_level 10 is mining against mining and moves 5.000 -> 2.400), but any
    statement about the DIRECTION or SIZE of the mispricing should name which
    buckets it rests on.

    Also returns `all_flat`: the skill_levels where EVERY step is FLAT (ratio
    unchanged craft_level to craft_level), so a caller can state precisely
    which buckets the "not constant" claim covers instead of asserting it of
    all of them -- a bucket where both craft_levels have already fallen into
    the zero-xp grey band is trivially flat at 0.000, and a universal claim
    that ignores it is falsified by its own table."""
    by_skill: dict[int, dict[int, float]] = collections.defaultdict(dict)
    for (skill_level, craft_level), xps in by_pair.items():
        by_skill[skill_level][craft_level] = statistics.mean(xps)
    lines = ["", "## RATIO xp/craft_level, PER SKILL_LEVEL WITH >=2 DISTINCT CRAFT_LEVELS"]
    qualifying = {sl: levels for sl, levels in by_skill.items() if len(levels) >= 2}
    all_flat: set[int] = set()
    if not qualifying:
        lines.append("(none -- no skill_level has crafts observed at 2+ distinct craft_levels)")
    for skill_level in sorted(qualifying):
        levels = qualifying[skill_level]
        ordered_cls = sorted(levels)
        ratios = [levels[cl] / cl for cl in ordered_cls]
        steps = []
        directions = []
        for cl_a, cl_b, r_a, r_b in zip(ordered_cls, ordered_cls[1:], ratios, ratios[1:], strict=False):
            direction = "RISES" if r_b > r_a else ("FALLS" if r_b < r_a else "FLAT")
            directions.append(direction)
            steps.append(f"{cl_a}->{cl_b}:{direction}({r_a:.2f}->{r_b:.2f})")
        if directions and all(d == "FLAT" for d in directions):
            all_flat.add(skill_level)
        lines.append(
            f"skill_level={skill_level}: "
            + ", ".join(f"cl={cl}:xp={levels[cl]:.2f},ratio={r:.3f}" for cl, r in zip(ordered_cls, ratios, strict=False))
            + "  steps: " + "; ".join(steps)
        )
    return lines, qualifying, all_flat


def main() -> int:
    trace_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT
    snapshot = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else Path.home() / ".cache/artifactsmmo/gamedata-api.artifactsmmo.com.json"
    )
    db_path = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(default_learn_db_path())

    traces = sorted(trace_dir.glob("play-trace-*.jsonl"))
    if not traces:
        print(f"no play-trace-*.jsonl under {trace_dir}", file=sys.stderr)
        return 2
    if not snapshot.exists():
        print(f"no game-data snapshot at {snapshot}", file=sys.stderr)
        return 2

    crafts = _craft_catalog(snapshot)
    observations, skipped, used = _replay(traces, crafts)
    paying = [o for o in observations if o.xp > 0]
    zero = [o for o in observations if o.xp == 0]
    zero_below_band = [o for o in zero if o.gap < GREY_SKILL_GAP]
    payers_at_or_above_band = [o for o in paying if o.gap >= GREY_SKILL_GAP]

    representative = _representative_per_item(observations)
    by_item_lines, by_pair = _render_by_pair(representative)
    ratio_lines, qualifying, all_flat = _ratio_table(by_pair)
    sqlite_note = _sqlite_skill_level_note(db_path)

    lines = [
        "# craft-xp proportionality replay",
        f"traces={used}/{len(traces)} under {trace_dir}",
        f"snapshot={snapshot}",
        sqlite_note,
        f"skipped: {dict(skipped)}",
        f"valid craft cycles (exact same-cycle attribution): {len(observations)}",
        f"  paying (xp > 0): {len(paying)}   zero (xp == 0): {len(zero)}",
        f"  zero observations BELOW the grey band (gap < {GREY_SKILL_GAP}, i.e. a real "
        f"anomaly if any exist): {len(zero_below_band)}",
        f"  paying observations AT/ABOVE the grey band (gap >= {GREY_SKILL_GAP}, i.e. a "
        f"real anomaly if any exist): {len(payers_at_or_above_band)}",
        f"distinct (item_code, skill_level) representatives: {len(representative)}",
        f"distinct (skill_level, craft_level) pairs: {len(by_pair)}",
        f"skill_levels with >=2 distinct craft_levels: {sorted(qualifying)}",
    ]
    lines += by_item_lines + ratio_lines
    lines.append("")
    if not qualifying:
        lines.append(
            f"VERDICT: INCONCLUSIVE. The committed play-traces contain {len(observations)} "
            f"valid craft cycles across {len(by_pair)} distinct (craft_level, skill_level) "
            "pairs (formal/diff/craft_xp_replay.py), too few to test proportionality -- no "
            "skill_level has crafts observed at 2+ distinct craft_levels to compare. The "
            "assumption stands UNVERIFIED, not confirmed."
        )
    else:
        non_flat = sorted(set(qualifying) - all_flat)
        flat_clause = (
            f"The exception: skill_level {sorted(all_flat)} is FLAT -- both craft_levels "
            "there have already fallen into the zero-xp grey band (ratio 0.000 at both), "
            "which is constant only in the trivial sense that zero equals zero. "
            if all_flat
            else ""
        )
        lines.append(
            f"VERDICT: REFUTED. Measured over {len(observations)} craft cycles "
            f"({len(paying)} paying, {len(zero)} zero) across {len(by_pair)} distinct "
            "(craft_level, skill_level) pairs (formal/diff/craft_xp_replay.py): xp / "
            f"craft_level is NOT constant at fixed skill_level in {len(non_flat)}/"
            f"{len(qualifying)} qualifying buckets (skill_level {non_flat}). "
            f"{flat_clause}See the RATIO table's per-step directions above. The shape "
            "is not one direction across the whole range (see the report's VERDICT "
            "prose / the committed _beats docstring for the authored "
            "characterization); craft_level orders rungs correctly (monotonicity is "
            "not in question here) but does not price them proportionally."
        )
    report = "\n".join(lines) + "\n"
    REPORT.write_text(report)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
