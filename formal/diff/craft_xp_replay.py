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

THE DATA SOURCE IS THE `Cycle` TABLE, NOT `play-trace-*.jsonl`.
`gather_xp_replay.py` replays the jsonl per-cycle state dumps (each line a
full `{"state": {...}}` snapshot, including `skills`/`skill_xp` dicts) that
`play --trace-file` writes. Those files are gitignored session artifacts and
none happened to exist in this worktree at the time this was written. The
persistent, cross-session record is instead `~/.cache/artifactsmmo/learning.db`
(see `learning_db_path.default_learn_db_path`), the same shared-cache
convention `gather_xp_replay.py` already uses for its game-data snapshot. Its
`cycles` table (`ai/learning/models.py:Cycle`) carries one row per executed
action, and `delta_skill_xp_json` (parsed the way
`ai/learning/projections.py:_parse_skill_xp` does) is the per-skill XP delta
that landed on that cycle.

THE STRUCTURAL FINDING, UP FRONT: `Cycle` has no per-skill LEVEL column --
only `level` (character level, a different axis from a skill's own level) and
the skill-XP DELTA. `skill_level_at_the_time`, the second coordinate the task
asks this replay to bucket by, is consequently not a value that exists
anywhere in this data source; grep `ai/learning/models.py` and there is no
`*_skill_level` field on `CycleBase`. This is verified against the live
`sqlite_master` schema in `main()`, not asserted from memory. The practical
result: every `(craft_level, skill_level)` PAIR this replay could report has
an unknown second coordinate, so the count of distinct pairs is 0 regardless
of how many craft cycles exist.

CRAFT ATTRIBUTION LAG, the second finding: `gather_xp_replay.py`'s own
docstring already flags craft results as lagging their cycle "far more often
than gathers". The same is true here -- of the `CraftAction` cycles whose item
resolves in the game-data catalog, a large share carry `delta_skill_xp_json`
with NO entry for the crafted skill at all (the xp lands on the following
cycle instead), and are excluded from `n_valid` for exactly that reason. What
survives is corroborating, not certain: the observation window is real
same-cycle craft/xp pairs.

QUANTITY NORMALIZATION: `action_repr` is `Craft(item_code×qty)`; a batch craft
pays roughly `qty` times a single unit's xp. Reported "xp" below is always
`delta / qty` (xp per unit crafted) -- comparing raw batch totals across
different batch sizes would confound the very question this file asks with a
quantity effect that has nothing to do with `craft_level` or skill level.

Output: formal/diff/craft_xp_replay_report.txt + stdout.
Usage: uv run python formal/diff/craft_xp_replay.py [DB_PATH] [SNAPSHOT]
"""

import collections
import json
import re
import statistics
import sys
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine, select

from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.learning_db_path import default_learn_db_path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT = REPO_ROOT / "formal" / "diff" / "craft_xp_replay_report.txt"
_CRAFT_RE = re.compile(r"Craft\((\w+)[x×](\d+)\)")


class CraftObservation:
    """One same-cycle craft->xp pairing. Pure data; exempt from
    one-class-per-file (tightly-coupled value object for this replay only)."""

    __slots__ = ("craft_level", "item_code", "qty", "skill_level", "xp_per_unit")

    def __init__(self, item_code: str, craft_level: int, qty: int, xp_per_unit: float) -> None:
        self.item_code = item_code
        self.craft_level = craft_level
        # Not a placeholder default: see the module docstring's "STRUCTURAL
        # FINDING". `Cycle` carries no per-skill level column, so this is the
        # actual, honest value of that coordinate for every observation --
        # not a stand-in for a real level that failed to load.
        self.skill_level: int | None = None
        self.qty = qty
        self.xp_per_unit = xp_per_unit


def _has_skill_level_column(engine: Engine) -> bool:
    """True iff the live `cycles` table schema has ANY per-skill-level column.

    Checked against the running schema rather than assumed from
    `ai/learning/models.py`, so a future migration that adds one is caught
    here rather than by a stale docstring."""
    columns = {c["name"] for c in inspect(engine).get_columns("cycles")}
    skill_level_cols = {c for c in columns if "skill" in c and "level" in c}
    return bool(skill_level_cols)


def _craft_catalog(snapshot: Path) -> dict[str, tuple[str, int]]:
    """`{item_code: (craft_skill, craft_level)}` from a raw game-data cache dump."""
    data = json.loads(snapshot.read_text())
    return {
        i["code"]: (i["craft"]["skill"], i["craft"]["level"])
        for i in data["items"]
        if i.get("craft") and i["craft"].get("skill")
    }


def _parse_skill_xp(raw: str) -> dict[str, int]:
    """Tolerant parse of `Cycle.delta_skill_xp_json`. Mirrors
    `ai/learning/projections.py:_parse_skill_xp`'s tolerance -- a single bad
    row must not crash the replay -- without importing a module-private name."""
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    try:
        return {str(k): int(v) for k, v in parsed.items()}
    except (TypeError, ValueError):
        return {}


def _replay(
    cycles: list[Cycle], crafts: dict[str, tuple[str, int]]
) -> tuple[list[CraftObservation], collections.Counter[str]]:
    observations: list[CraftObservation] = []
    skipped: collections.Counter[str] = collections.Counter()
    for cycle in cycles:
        if cycle.outcome != "ok":
            skipped["outcome_not_ok"] += 1
            continue
        match = _CRAFT_RE.match(cycle.action_repr or "")
        if not match:
            skipped["action_repr_not_craft"] += 1
            continue
        item_code, qty_str = match.group(1), match.group(2)
        entry = crafts.get(item_code)
        if entry is None:
            skipped["item_not_in_catalog"] += 1
            continue
        skill, craft_level = entry
        qty = int(qty_str)
        xp = _parse_skill_xp(cycle.delta_skill_xp_json).get(skill)
        if xp is None:
            skipped["no_same_cycle_xp_for_craft_skill"] += 1
            continue
        if xp <= 0:
            # A same-cycle non-positive delta is a level-up reset (xp resets
            # into the new level -- see `_record_learning_cycle`'s own
            # comment on this), not evidence the craft paid nothing.
            skipped["nonpositive_xp_likely_levelup"] += 1
            continue
        observations.append(CraftObservation(item_code, craft_level, qty, xp / qty))
    return observations, skipped


def _render_by_level(
    observations: list[CraftObservation],
) -> tuple[list[str], dict[int, list[float]]]:
    by_level: dict[int, list[float]] = collections.defaultdict(list)
    for obs in observations:
        by_level[obs.craft_level].append(obs.xp_per_unit)
    lines = [
        "",
        "## BY CRAFT_LEVEL (skill_level column: UNRECORDED -- see module docstring)",
        f"{'craft_level':>11} {'n':>5} {'mean_xp/u':>10} {'min':>8} {'max':>8} "
        f"{'stdev':>8} {'xp/level':>9} {'cv':>6}",
    ]
    for level in sorted(by_level):
        xps = by_level[level]
        mean = statistics.mean(xps)
        sd = statistics.stdev(xps) if len(xps) > 1 else 0.0
        cv = sd / mean if mean else 0.0
        lines.append(
            f"{level:11d} {len(xps):5d} {mean:10.2f} {min(xps):8.2f} {max(xps):8.2f} "
            f"{sd:8.2f} {mean / level:9.3f} {cv:6.3f}"
        )
    return lines, by_level


def _render_by_item(observations: list[CraftObservation]) -> list[str]:
    by_item: dict[tuple[str, int], list[float]] = collections.defaultdict(list)
    for obs in observations:
        by_item[(obs.item_code, obs.craft_level)].append(obs.xp_per_unit)
    lines = [
        "",
        "## BY ITEM (per-unit xp, quantity-normalized)",
        f"{'item_code':22} {'craft_level':>11} {'n':>5} {'mean_xp/u':>10} "
        f"{'min':>8} {'max':>8}",
    ]
    for (item_code, level), xps in sorted(by_item.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        lines.append(
            f"{item_code:22} {level:11d} {len(xps):5d} {statistics.mean(xps):10.2f} "
            f"{min(xps):8.2f} {max(xps):8.2f}"
        )
    return lines


def main() -> int:
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(default_learn_db_path())
    snapshot = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else Path.home() / ".cache/artifactsmmo/gamedata-api.artifactsmmo.com.json"
    )
    if not db_path.exists():
        print(f"no learning db at {db_path}", file=sys.stderr)
        return 2
    if not snapshot.exists():
        print(f"no game-data snapshot at {snapshot}", file=sys.stderr)
        return 2

    engine = create_engine(f"sqlite:///{db_path}")
    has_skill_level_column = _has_skill_level_column(engine)
    with Session(engine) as session:
        cycles = list(session.exec(select(Cycle).where(Cycle.action_class == "CraftAction")))

    crafts = _craft_catalog(snapshot)
    observations, skipped = _replay(cycles, crafts)
    by_level_lines, by_level = _render_by_level(observations)
    by_item_lines = _render_by_item(observations)

    distinct_craft_levels = sorted(by_level)
    # Every observation's skill_level is None (see CraftObservation.__init__'s
    # comment); the honest count of distinct (craft_level, skill_level) PAIRS
    # is therefore 0 whenever the column is absent, no matter how many craft
    # cycles or craft levels were observed.
    distinct_pairs = 0 if not has_skill_level_column else len(
        {(obs.craft_level, obs.skill_level) for obs in observations}
    )

    lines = [
        "# craft-xp proportionality replay",
        f"db={db_path} snapshot={snapshot}",
        f"total CraftAction cycles: {len(cycles)}",
        f"skipped: {dict(skipped)}",
        f"valid same-cycle (craft_level, xp) observations: {len(observations)}",
        f"cycles.skill_level column present: {has_skill_level_column}",
        f"distinct craft_level values observed: {distinct_craft_levels}",
        f"distinct (craft_level, skill_level) pairs: {distinct_pairs}",
    ]
    lines += by_level_lines + by_item_lines
    lines.append("")
    if not has_skill_level_column:
        lines.append(
            "VERDICT: INCONCLUSIVE. The `cycles` table records no per-skill-level "
            "column (verified against the live sqlite schema, not assumed), so "
            "`skill_level_at_the_time` cannot be read for any of the "
            f"{len(observations)} valid craft-xp observations above, across "
            f"{len(distinct_craft_levels)} distinct craft_level values "
            f"{distinct_craft_levels}. 0 (craft_level, skill_level) pairs exist to "
            "compare, so proportionality cannot be tested from this data source. "
            "The BY CRAFT_LEVEL table above pools every skill level a craft was "
            "observed at and is DESCRIPTIVE ONLY, not a test: xp/craft_level "
            f"ranges {min(statistics.mean(v) / k for k, v in by_level.items()):.2f}"
            f"-{max(statistics.mean(v) / k for k, v in by_level.items()):.2f} across "
            "buckets, which is exactly the spread a level_penalty effect this "
            "replay cannot isolate would produce."
        )
    else:
        lines.append(
            f"VERDICT: skill_level column IS present -- {len(distinct_craft_levels)} "
            f"craft_level values, {distinct_pairs} distinct (craft_level, "
            "skill_level) pairs. Re-run and hand-classify supported/refuted; this "
            "branch was not reachable when this replay was written and must not be "
            "trusted blindly."
        )
    report = "\n".join(lines) + "\n"
    REPORT.write_text(report)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
