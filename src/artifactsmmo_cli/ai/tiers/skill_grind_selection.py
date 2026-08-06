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
    """A craftable item considered for a skill grind. `mats_missing`,
    `obtainable`, `wanted` and `xp_positive` are HOISTED (computed against
    holdings / recipe-closure reachability / the objective's gear+tool targets /
    the server's level_penalty band by the impure wrapper) so this core stays
    pure/extractable. `wanted` = the crafted item is a current objective
    gear/tool target (`is_target`); a wanted item produces a keeper while
    leveling, a non-wanted one only a throwaway. `xp_positive` =
    `ai/skill_xp_positive` says crafting it still pays skill xp at the current
    level."""
    code: str
    craft_skill: str
    craft_level: int
    mats_missing: int
    obtainable: bool
    wanted: bool
    xp_positive: bool


def _beats(c: GrindCandidate, best: GrindCandidate | None) -> bool:
    """True when feasible `c` strictly precedes `best` in the selection order
    `(wanted desc, -mats_missing, craft_level)`: a WANTED item (an objective
    gear/tool target) outranks a throwaway, THEN fewest missing materials, THEN
    highest craft level. A None `best` (no incumbent) is always beaten. A full tie
    keeps the incumbent (first-seen in candidate order) — deterministic without a
    string tie-break.

    Wanted-first (2026-06-24): pure fewest-materials greed made the bot craft a
    value-10 `apprentice_gloves` (feathers already in bag) to level weaponcrafting
    while ignoring `copper_dagger` (value 83, the committed weapon). Crafting a
    wanted item gains the SAME skill XP and yields a keeper, so it dominates."""
    if best is None:
        return True
    if c.wanted and not best.wanted:
        return True
    if best.wanted and not c.wanted:
        return False
    if c.mats_missing != best.mats_missing:
        return c.mats_missing < best.mats_missing
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
