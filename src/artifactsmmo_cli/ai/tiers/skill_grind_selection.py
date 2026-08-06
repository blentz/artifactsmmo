"""Pure core for skill-grind target selection: pick the in-skill item to craft
NOW to gain XP toward a skill gate, considering ONLY items that are same-skill,
in-level, obtainable (every recipe input reachable), AND xp-positive (the craft
is not in the server's zero-xp band).

`skill_grind_selection_pure` is the proved decision core (see
formal/Formal/SkillGrindSelection.lean). The impure wrapper `skill_grind_target`
hoists the `GrindCandidate`s — including the recursive `obtainable` flag and the
`xp_positive` band verdict — from GameData + holdings and delegates here.

Why obtainable matters (live weaponcrafting bug, 2026-06-13): the bot, committed
to weaponcrafting, picked `wooden_staff` (recipe needs `wooden_stick`, which has
no recipe and is not gatherable). The GatherMaterials goal then GOAP-failed
(plan_len 0) and the arbiter fell CROSS-SKILL to a gearcrafting grind. Filtering
to obtainable candidates makes selection pick the reachable `copper_dagger`
(copper_bar <- copper_ore) instead, so the committed skill actually grinds.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GrindCandidate:
    """A craftable item considered for a skill grind. `acquire_steps`,
    `obtainable`, `wanted` and `xp_positive` are HOISTED (computed against
    holdings / recipe-closure reachability / the objective's gear+tool targets /
    the server's level_penalty band by the impure wrapper) so this core stays
    pure/extractable. `wanted` = the crafted item is a current objective
    gear/tool target (`is_target`); a wanted item produces a keeper while
    leveling, a non-wanted one only a throwaway. `xp_positive` =
    `ai/skill_xp_positive` says crafting it still pays skill xp at the current
    level.

    `acquire_steps` = the WHOLE-CHAIN action cost of making one of this item
    from what the character already holds (`min_gathers + min_crafts` over the
    recipe closure, the proved lower bound from `ai/min_plan_length`). It
    replaced a one-level `mats_missing` count on 2026-08-06 — see `_beats`."""
    code: str
    craft_skill: str
    craft_level: int
    acquire_steps: int
    obtainable: bool
    wanted: bool
    xp_positive: bool


def _beats(c: GrindCandidate, best: GrindCandidate | None) -> bool:
    """True when feasible `c` strictly precedes `best` in the selection order
    `(wanted desc, -acquire_steps, craft_level)`: a WANTED item (an objective
    gear/tool target) outranks a throwaway, THEN the cheapest chain to build,
    THEN highest craft level. A None `best` (no incumbent) is always beaten. A
    full tie keeps the incumbent (first-seen in candidate order) — deterministic
    without a string tie-break.

    Wanted-first (2026-06-24): pure cheapest-chain greed made the bot craft a
    value-10 `apprentice_gloves` (feathers already in bag) to level weaponcrafting
    while ignoring `copper_dagger` (value 83, the committed weapon). Crafting a
    wanted item gains the SAME skill XP and yields a keeper, so it dominates.
    `wanted` is a VALUE axis, orthogonal to cost, which is why it survived the
    2026-08-06 rework below.

    COST IS MEASURED IN ACTIONS, NOT RECIPE SLOTS (2026-08-06). This key was
    `mats_missing` — the count of recipe entries not currently held — for its
    whole life, and that is a one-level proxy that systematically misprices deep
    chains. Live R2D2 at weaponcrafting 5: `sticky_sword` scored `mats_missing`
    5 (five `copper_bar`) and `apprentice_gloves` scored 6 (six `feather`), so
    the sword won by one. Their real costs are 51 actions and 7 — the 5 bars
    hide 50 `copper_ore` gathers. The bot picked the sword and spent 129 grind
    cycles gathering ore that paid no xp in EITHER skill, never reaching the
    craft; weaponcrafting sat at level 5 the entire time.

    That was the third recurrence of one flaw. Each earlier one was patched by
    bolting another key onto this ordering rather than fixing the key that was
    lying: `wanted` (2026-06-24) and the `xp_positive` filter (2026-08-05, live
    Robby). Both were real, but neither addressed a cost proxy that cannot see
    past the first level of a recipe. `acquire_steps` is that cost measured
    properly — `min_gathers + min_crafts` over the full closure, discounting
    what is already held — reusing the SAME proved lower bound the planner's
    reachability gate uses (`ai/min_plan_length`, Formal.PlanModel), so there is
    one notion of "how much work is this item" in the codebase instead of two
    that disagree."""
    if best is None:
        return True
    if c.wanted and not best.wanted:
        return True
    if best.wanted and not c.wanted:
        return False
    if c.acquire_steps != best.acquire_steps:
        return c.acquire_steps < best.acquire_steps
    if c.craft_level != best.craft_level:
        return c.craft_level > best.craft_level
    return False


def skill_grind_selection_pure(
    skill: str, current_level: int, candidates: list[GrindCandidate],
) -> str:
    """The in-skill item to craft for `skill` XP at `current_level`, or "" when
    none qualifies (caller falls back to LevelSkill on the SAME skill).

    Considers ONLY candidates that are same-skill (`craft_skill == skill`),
    in-level (`craft_level <= current_level`), `obtainable`, and `xp_positive`.
    Among those, returns the `_beats`-maximal candidate's code. Returns "" iff
    none qualify.

    XP-POSITIVE is a FILTER, not a tie-break (live Robby 2026-08-05, 14h at
    character level 22 with 288 zero-xp `LevelSkill(woodcutting->20)` cycles):
    at woodcutting 15 the in-level rungs were `ash_plank` (craft level 1) and
    `spruce_plank` (10), and because `mats_missing` is the ranking's FIRST key
    the grind picked whichever rung's materials were already stockpiled — the
    grey `ash_plank`, whose craft pays nothing 14 levels down. The bot then
    crafted it forever with `woodcutting` xp pinned at 4229 across 104
    consecutive `ok` cycles. Ordering cannot fix this: a rung that pays ZERO is
    worthless at ANY `mats_missing`, so it must be excluded from the candidate
    set rather than merely ranked below. Cheap materials CORRELATE with obsolete
    tiers, which is what made the greedy key pick the one useless rung."""
    best: GrindCandidate | None = None
    for c in candidates:
        if (c.craft_skill != skill or c.craft_level > current_level
                or not c.obtainable or not c.xp_positive):
            continue
        if _beats(c, best):
            best = c
    return best.code if best is not None else ""
