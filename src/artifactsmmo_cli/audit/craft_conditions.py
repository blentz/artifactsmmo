"""The conditions census: under which conditions each recipe plans, and the
loadout each of its fights needs (USER 2026-10-10: "find the loadouts and
conditions required to successfully plan each item and from that process,
identify and fix planner bugs found"; docs/PLAN_drop_fight_loadout.md
increment 2).

Each recipe climbs a LADDER of worlds over its nominal at-skill cell (the tier's
character level, the recipe's own craft level), each rung granting one more
condition over the census character (`craft_completeness.census_state`):

1. `cell` — the census cell as it is;
2. `skills` — every other skill at the character's level (it can brew its own
   potions, craft its own tools);
3. `gold` — `GOLD_GRANT` in the pocket (vendors, crossings);
4. `events` — the events that source its event-only leaves live (skipped when
   it has none);
5. `achievements` — every achievement unlocked: the catalogue built with the
   account's achievement-gated tiles open (`tasks_trader`, behind
   `tasks_farmer`, sells jasper/astralyte/magical_cure/prime_fabric for
   tasks_coin, which production funds through `ReachCurrencyGoal`);
6. `gear` — the catalogue's best suppliable gear for the level, worn
   (`CharacterObjective.catalogue_best_gear`): the gear that wins a fight the
   reachable gear (`census_gear`) loses;
7. `level±k` — every grant kept, the character `LEVEL_STEP` levels apart each
   rung from `craft level − 10` (at least 1) to 50, every other skill with it;
   the recipe's own skill stays at its craft level. LOWER levels count: a drop
   is grey ≥ 11 levels above its monster, so pig_skin (pig, 19) is farmable
   only below 30, piggy_helmet's nominal level;
8. `keys`, then `keys±k` — the sweep holding every crossing's key
   (`CraftCell.keys`): the region bridge does not plan a key's acquisition;
10. `held:<leaves>` — the last resort: the leaves still unreachable at the
   top rung granted in the bag (`CraftCell.held`), naming what no route
   produces (a raid reward, a starter item, an unbeatable boss's drop);
9. `grey`, then `grey±k` — the same sweep with the grey-farm policy licensing
   every grey drop (`CraftCell.grey`): the policy (USER 2026-07-06) refuses a
   grey drop for a recipe a near higher tier makes obsolete, and where the
   dropper is grey at every level the recipe's other fights need, only this
   names what plans it. Raising that skill too would make the recipe obsolete: the
   grey-farm policy (USER 2026-07-06, `grey_farm.py`) rightly refuses to farm a
   grey monster for a recipe a near higher tier replaces, so a level-50
   character with every skill at 50 "cannot" make `cooked_beef`.

The recipe's answer is the first rung whose cell PASSES, with the plan's fights
(`craft_census.fight_needs`). A recipe that passes no rung carries its top
rung's gap: a game limit names what even a level-50 character with every skill,
gold and the events cannot reach; `planner_bug` there is a planner bug."""

from dataclasses import dataclass, replace

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.craft_census import CellResult, run_cell
from artifactsmmo_cli.audit.craft_completeness import (
    CraftCell,
    event_cells,
    nominal_char_level,
    unreachable_leaves,
)

GOLD_GRANT = 1_000_000
"""The `gold` rung's pocket: more than any vendor price or crossing fee."""

TOP_LEVEL = 50
"""The game's level cap: the last level rung's character level."""

LEVEL_STEP = 5
"""Levels between the level rungs."""


@dataclass(frozen=True)
class ConditionsResult:
    """One recipe's ladder: the first rung that plans (None: none did) and that
    rung's cell result (the top rung's when none did)."""

    recipe: str
    rung: str | None
    result: CellResult


def ladder(recipe: str, game_data: GameData) -> list[tuple[str, CraftCell, bool]]:
    """The recipe's rungs, in climbing order (see the module doc): its name,
    its cell, and whether it is played in the achievements-unlocked world."""
    stats = game_data.item_stats(recipe)
    if stats is None or not stats.crafting_skill:
        raise ValueError(f"{recipe} is not a craftable recipe")
    level = stats.crafting_level
    cell = CraftCell(nominal_char_level(level), stats.crafting_skill, level)
    rungs = [("cell", cell, False)]
    cell = replace(cell, skills_at_level=True)
    rungs.append(("skills", cell, False))
    cell = replace(cell, gold=GOLD_GRANT)
    rungs.append(("gold", cell, False))
    events = frozenset().union(*(c.events for c in event_cells(recipe, game_data)))
    if events:
        cell = replace(cell, events=events)
        rungs.append(("events", cell, False))
    rungs.append(("achievements", cell, True))
    cell = replace(cell, geared=True)
    rungs.append(("gear", cell, True))
    nominal = cell.char_level
    levels = range(max(1, stats.crafting_level - 10), TOP_LEVEL + 1, LEVEL_STEP)
    for level in levels:
        if level != nominal:
            rungs.append((f"level{level - nominal:+d}", replace(cell, char_level=level), True))
    keyed = replace(cell, keys=True)
    rungs.append(("keys", keyed, True))
    for level in levels:
        if level != nominal:
            rungs.append((f"keys{level - nominal:+d}", replace(keyed, char_level=level), True))
    grey = replace(keyed, grey=True)
    rungs.append(("grey", grey, True))
    for level in levels:
        if level != nominal:
            rungs.append((f"grey{level - nominal:+d}", replace(grey, char_level=level), True))
    return rungs


def climb(recipe: str, game_data: GameData, achieved: GameData) -> ConditionsResult:
    """Run the ladder until a rung passes; `achieved` is the same catalogue
    with every achievement unlocked."""
    result: CellResult | None = None
    rungs = ladder(recipe, game_data)
    for name, cell, unlocked in rungs:
        result = run_cell(recipe, cell, achieved if unlocked else game_data)
        if result.passed:
            return ConditionsResult(recipe, name, result)
    assert result is not None  # every ladder has rungs
    _name, top, _unlocked = rungs[-1]
    leaves = unreachable_leaves(recipe, top, achieved)
    if leaves:
        granted = run_cell(recipe, replace(top, held=leaves), achieved)
        if granted.passed:
            return ConditionsResult(recipe, "held:" + ",".join(sorted(leaves)), granted)
    return ConditionsResult(recipe, None, result)


def summary_line(results: list[ConditionsResult]) -> str:
    """Recipes per first passing rung, then the top-rung gaps of those that
    pass none."""
    rungs: dict[str, int] = {}
    for r in results:
        if r.rung is not None:
            rungs[r.rung] = rungs.get(r.rung, 0) + 1
    gaps: dict[str, int] = {}
    for r in results:
        if r.rung is None and r.result.gap is not None:
            gaps[r.result.gap] = gaps.get(r.result.gap, 0) + 1
    planned = sum(rungs.values())
    by_rung = ", ".join(f"{name} {n}" for name, n in rungs.items())
    unplanned = ", ".join(f"{gap} {n}" for gap, n in sorted(gaps.items(), key=lambda kv: -kv[1]))
    return (f"{len(results)} recipes; planned {planned} ({by_rung}); "
            f"unplanned {len(results) - planned} ({unplanned})")


def _fights(result: CellResult) -> str:
    return ", ".join(f"{monster}: {need}" for monster, need in result.fights) or "-"


def render_conditions(results: list[ConditionsResult]) -> str:
    """The CONDITIONS doc: the summary, then one row per recipe (skill, craft
    level, the first rung that plans and its character level, the plan's
    fights and what wins each — or the top rung's gap)."""
    lines = [
        "# Craft-Planning Conditions",
        "",
        "> GENERATED — do not hand-edit. Regenerate with "
        "`uv run python scripts/gen_craft_conditions.py`.",
        ">",
        "> Each recipe climbs the ladder of `audit/craft_conditions.py` (cell, every "
        "skill at the character level, gold, its events, then the character level "
        "in steps of 5); the first rung that plans is its condition. A fight's need "
        "is `bare` (the stats win), the potion loadout that wins it, or `loses`.",
        "",
        summary_line(results),
        "",
        "| Recipe | Skill | Craft lvl | Plans at | Char lvl | Fights (what wins) |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        rung = r.rung if r.rung is not None else f"**none: {r.result.gap}**"
        lines.append(f"| {r.recipe} | {r.result.skill} | {r.result.craft_level} | {rung} "
                     f"| {r.result.char_level} | {_fights(r.result)} |")
    return "\n".join(lines) + "\n"
