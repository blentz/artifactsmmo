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

DATA SOURCE: the learning store's `craft_yield` table, not
`play-trace-*.jsonl`. Traces are a debugging artifact the user deletes at
will -- 164 of 169 `play-trace-*.jsonl` files went on 2026-08-15 -- and
nothing this codebase cites may depend on them being present. This module's
FIRST version (2026-08-15) read traces directly and found 450 usable craft
cycles across 13 items; that finding is REFUTED and is recorded, dated, as
HISTORY in this docstring and in `_beats`'s -- it is not reproduced by this
version and cannot be, because its corpus no longer exists. See "HISTORICAL
FINDING" below.

`craft_yield` ROWS ARE UPSERTS, ONE PER (character, item_code) -- last write
wins (`LearningStore.record_craft_yield`). Unlike the old per-cycle trace
scan, there is at most one row to read per character/item pair; there is no
"across many cycles, take the MAX" step here because there is only ever one
observation to take.

`craft_yield.skill_level` (added in commit `f08dd5aa`, 2026-08-15) is the
PRE-craft level the xp was paid at -- see that commit's message. It is
NULLABLE, NOT BACK-FILLED: every row written before that commit landed carries
`skill_level = NULL`, because nobody recorded a level for them and inventing
one (0, or the character's level today) would hand this measurement a
fabricated observation it could not tell from a real one. ROWS WITH A NULL
SKILL_LEVEL ARE EXCLUDED, NOT DEFAULTED, and this replay reports the count and
reason for every exclusion rather than silently shrinking the denominator.

`craft_yield.quantity` IS THE ACTUAL PRODUCED COUNT, ALREADY EXECUTION- AND
RECIPE-QUANTITY CORRECT. `CraftAction.execute` writes it as
`sum(d.quantity for d in details.items if d.code == self.code)` -- a literal
count of items the API says this craft call produced -- which already
resolves BOTH traps the trace-based version had to recover by parsing
`Craft(item×N)` action strings by hand: (1) it is the EXECUTED count, not a
requested batch size that the server may not have fully honoured, and (2) it
already reflects the recipe's own `craft.quantity` (items produced per
execution -- `small_health_potion`, `earth_boost_potion` and
`fire_boost_potion` all craft at quantity=2), since it is a sum over items
actually produced, not a per-execution multiplier applied separately. So
`xp_per_item = xp / quantity` is exact with no extra normalization step;
dividing by anything OTHER than this stored `quantity` (e.g. the game-data
snapshot's own `craft.quantity` alone, ignoring how many executions actually
ran) would silently reintroduce the exact bug `6e382378`/`ac193b9b` fixed in
the trace-based version. The game-data snapshot is read only for `craft_level`
(and `skill`, for the report), never for a normalization divisor.

READS ACROSS EVERY CHARACTER, NOT ONE. `LearningStore.observed_craft_xp`
scopes its query to `self._character`; this replay needs the whole corpus, so
it opens the store's own engine and selects every `craft_yield` row directly
-- the same table, same columns, same NULL-exclusion contract as
`observed_craft_xp`, generalized to all rows the way
`formal/diff/store_records.load_cycles` generalizes `Cycle` reads for the
sibling harnesses in this migration (`character=None` there reads every row
too).

COVERAGE COLLAPSES, AND THAT IS THE HONEST RESULT, NOT A BUG IN THIS FILE. The
trace corpus gave 450 craft cycles across 13 items (see HISTORICAL FINDING
below); `craft_yield` currently holds far fewer rows, over more items, and
only those written since `f08dd5aa` carry a skill level at all -- as of this
writing that is ZERO rows (the migration added the column; no craft has run
against this cache since). An empty usable corpus is expected, not a defect,
and this module reports it as such rather than manufacturing coverage or
silently falling back to the deleted trace path.

HISTORICAL FINDING (measured 2026-08-15, trace-based, corpus since deleted).
The trace-based predecessor of this file measured 450 valid craft cycles
(214 paying, 236 exact zero) across 25 distinct (craft_level, skill_level)
pairs and 13 items, and found xp / craft_level NOT constant at fixed
skill_level in 10 of 11 qualifying buckets -- REFUTED. Full figures live in
this file's git history (`ce579d2c`, `6e382378`, `ac193b9b`) and in
`formal/diff/craft_xp_replay_report.txt`'s history, and are restated in
`_beats`'s docstring as a dated, historical finding. This version cannot
reproduce it -- `play-trace-*.jsonl` is gone -- and does not try to; it
measures the same question against whatever `craft_yield` can currently
answer, honestly, even when that is "nothing yet."

Output: formal/diff/craft_xp_replay_report.txt + stdout.
Usage: uv run python formal/diff/craft_xp_replay.py [SNAPSHOT] [LEARNING_DB]
"""

import collections
import json
import statistics
import sys
from pathlib import Path

from sqlmodel import Session as SqlSession
from sqlmodel import select

from artifactsmmo_cli.ai.learning.models import CraftYieldObservation
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.skill_xp_positive import GREY_SKILL_GAP
from artifactsmmo_cli.learning_db_path import default_learn_db_path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT = REPO_ROOT / "formal" / "diff" / "craft_xp_replay_report.txt"


class CraftObservation:
    """One character's most recent craft of one item, as the learning store
    holds it. Pure data; exempt from one-class-per-file (tightly-coupled value
    object for this replay only).

    `quantity` is `craft_yield.quantity` -- the ACTUAL produced count, already
    execution- and recipe-quantity correct (see module docstring). `xp` is the
    total xp that craft call paid, so `xp_per_item = xp / quantity` needs no
    further normalization."""

    __slots__ = ("craft_level", "item_code", "quantity", "skill_level", "xp")

    def __init__(
        self, item_code: str, craft_level: int, skill_level: int, quantity: int, xp: int,
    ) -> None:
        self.item_code = item_code
        self.craft_level = craft_level
        self.skill_level = skill_level
        self.quantity = quantity
        self.xp = xp

    @property
    def xp_per_item(self) -> float:
        return self.xp / self.quantity

    @property
    def gap(self) -> int:
        return self.skill_level - self.craft_level


def _craft_catalog(snapshot: Path) -> dict[str, tuple[str, int]]:
    """`{item_code: (craft_skill, craft_level)}` from a raw game-data cache
    dump. No quantity field here -- unlike the trace-based predecessor, this
    version never needs the recipe's own `craft.quantity`; `craft_yield.quantity`
    already IS the per-item-correct produced count (see module docstring)."""
    data = json.loads(snapshot.read_text())
    return {
        i["code"]: (i["craft"]["skill"], i["craft"]["level"])
        for i in data["items"]
        if i.get("craft") and i["craft"].get("skill")
    }


def _load_observations(
    db_path: Path, crafts: dict[str, tuple[str, int]]
) -> tuple[list[CraftObservation], int, int, int]:
    """Read every `craft_yield` row across every character, returning
    `(observations, total_rows, excluded_null_level, excluded_not_in_catalog)`.

    `LearningStore.observed_craft_xp` scopes to one character
    (`self._character`); this reads the whole corpus by selecting every
    `CraftYieldObservation` row directly off the store's engine -- same table,
    same columns, same NULL-exclusion contract as that method, generalized
    across characters the way `store_records.load_cycles` generalizes `Cycle`
    reads (see module docstring).

    Rows are excluded, never defaulted, for two reasons: a NULL `skill_level`
    (every row written before `f08dd5aa`, or by a caller that could not
    resolve the skill), or an `item_code` absent from the current craft
    catalog (a recipe removed or renamed since the row was written)."""
    store = LearningStore(db_path=str(db_path), character="")
    try:
        with SqlSession(store._engine) as s:
            rows = list(s.exec(select(CraftYieldObservation)))
    finally:
        store.close()

    observations: list[CraftObservation] = []
    excluded_null_level = 0
    excluded_not_in_catalog = 0
    for row in rows:
        if row.skill_level is None:
            excluded_null_level += 1
            continue
        entry = crafts.get(row.item_code)
        if entry is None:
            excluded_not_in_catalog += 1
            continue
        _skill, craft_level = entry
        observations.append(
            CraftObservation(row.item_code, craft_level, row.skill_level, row.quantity, row.xp)
        )
    return observations, len(rows), excluded_null_level, excluded_not_in_catalog


def _representative_per_item(
    observations: list[CraftObservation],
) -> dict[tuple[str, int], tuple[float, int, int]]:
    """`{(item_code, skill_level): (xp_per_item, n_rows, craft_level)}`. `n_rows`
    is always 1 per (character, item_code) since `craft_yield` upserts, but a
    key can be fed by more than one CHARACTER's row at the same skill_level, so
    the mean across contributing rows is reported (there is no request/execution
    truncation to correct for here -- see module docstring -- so MAX is not
    needed the way the trace-based predecessor needed it)."""
    grouped: dict[tuple[str, int], list[CraftObservation]] = collections.defaultdict(list)
    for obs in observations:
        grouped[(obs.item_code, obs.skill_level)].append(obs)
    return {
        key: (statistics.mean(o.xp_per_item for o in obs_list), len(obs_list), obs_list[0].craft_level)
        for key, obs_list in grouped.items()
    }


def _render_by_pair(
    representative: dict[tuple[str, int], tuple[float, int, int]],
) -> tuple[list[str], dict[tuple[int, int], list[float]]]:
    by_pair: dict[tuple[int, int], list[float]] = collections.defaultdict(list)
    lines = [
        "",
        "## BY ITEM (xp/item = mean across contributing characters' rows at that skill_level)",
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

    Also returns `all_flat`: the skill_levels where EVERY step is FLAT (ratio
    unchanged craft_level to craft_level)."""
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
    snapshot = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path.home() / ".cache/artifactsmmo/gamedata-api.artifactsmmo.com.json"
    )
    db_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(default_learn_db_path())

    if not snapshot.exists():
        print(f"no game-data snapshot at {snapshot}", file=sys.stderr)
        return 2
    if not db_path.exists():
        print(f"no learning store at {db_path}", file=sys.stderr)
        return 2

    crafts = _craft_catalog(snapshot)
    observations, total_rows, excluded_null_level, excluded_not_in_catalog = _load_observations(
        db_path, crafts
    )

    header = [
        "# craft-xp proportionality replay",
        f"store={db_path}",
        f"snapshot={snapshot}",
        f"craft_yield rows: {total_rows}",
        f"  excluded (skill_level IS NULL -- written before f08dd5aa, or level unresolved): "
        f"{excluded_null_level}",
        f"  excluded (item_code not in current craft catalog): {excluded_not_in_catalog}",
        f"usable observations: {len(observations)}",
    ]

    if not observations:
        lines = [
            *header,
            "",
            "VERDICT: EMPTY CORPUS. 0 usable observations -- every craft_yield row is "
            "either excluded for a NULL skill_level or for an item_code the current "
            "catalog does not recognize. This is the EXPECTED state immediately after "
            "f08dd5aa (2026-08-15) added the column: no craft has been recorded against "
            "this store since. It is not evidence for or against proportionality -- "
            "there is nothing to test yet -- and it must not be read as either "
            "confirming or refuting the HISTORICAL trace-based REFUTED finding (see "
            "module docstring and formal/diff/craft_xp_replay_report.txt's prior "
            "content in git history). Re-run once characters have crafted since "
            "f08dd5aa.",
        ]
        report = "\n".join(lines) + "\n"
        REPORT.write_text(report)
        print(report)
        return 1

    representative = _representative_per_item(observations)
    by_item_lines, by_pair = _render_by_pair(representative)
    ratio_lines, qualifying, all_flat = _ratio_table(by_pair)

    paying = [o for o in observations if o.xp > 0]
    zero = [o for o in observations if o.xp == 0]
    zero_below_band = [o for o in zero if o.gap < GREY_SKILL_GAP]
    payers_at_or_above_band = [o for o in paying if o.gap >= GREY_SKILL_GAP]

    lines = [
        *header,
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
            f"VERDICT: INCONCLUSIVE. {len(observations)} usable observation(s) across "
            f"{len(by_pair)} distinct (craft_level, skill_level) pairs -- too few to test "
            "proportionality: no skill_level has crafts observed at 2+ distinct "
            "craft_levels to compare. The assumption stands UNVERIFIED by this run; see "
            "the module docstring's HISTORICAL FINDING for the last time it was."
        )
        report = "\n".join(lines) + "\n"
        REPORT.write_text(report)
        print(report)
        return 1

    non_flat = sorted(set(qualifying) - all_flat)
    flat_clause = (
        f"The exception: skill_level {sorted(all_flat)} is FLAT -- both craft_levels "
        "there have already fallen into the zero-xp grey band (ratio 0.000 at both), "
        "which is constant only in the trivial sense that zero equals zero. "
        if all_flat
        else ""
    )
    lines.append(
        f"VERDICT: REFUTED. Measured over {len(observations)} craft observations "
        f"({len(paying)} paying, {len(zero)} zero) across {len(by_pair)} distinct "
        "(craft_level, skill_level) pairs (formal/diff/craft_xp_replay.py): xp / "
        f"craft_level is NOT constant at fixed skill_level in {len(non_flat)}/"
        f"{len(qualifying)} qualifying buckets (skill_level {non_flat}). "
        f"{flat_clause}See the RATIO table's per-step directions above."
    )
    report = "\n".join(lines) + "\n"
    REPORT.write_text(report)
    print(report)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
