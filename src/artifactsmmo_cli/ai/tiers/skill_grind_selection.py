"""Pure core for skill-grind target selection: pick the in-skill item to craft
NOW to gain XP toward a skill gate, considering ONLY items that are same-skill,
in-level, AND obtainable (every recipe input reachable).

`skill_grind_selection_pure` is the proved decision core (see
formal/Formal/SkillGrindSelection.lean). The impure wrapper `skill_grind_target`
hoists the `GrindCandidate`s — including the recursive `obtainable` flag — from
GameData + holdings and delegates here.

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
    """A craftable item considered for a skill grind. `mats_missing` and
    `obtainable` are HOISTED (computed against holdings / recipe-closure
    reachability by the impure wrapper) so this core stays pure/extractable."""
    code: str
    craft_skill: str
    craft_level: int
    mats_missing: int
    obtainable: bool


def _beats(c: GrindCandidate, best: GrindCandidate | None) -> bool:
    """True when feasible `c` strictly precedes `best` in the selection order
    `(-mats_missing, craft_level)`: fewest missing materials first, then highest
    craft level. A None `best` (no incumbent) is always beaten. A full tie keeps
    the incumbent (first-seen in candidate order) — deterministic without a
    string tie-break."""
    if best is None:
        return True
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
    in-level (`craft_level <= current_level`), and `obtainable`. Among those,
    returns the `_beats`-maximal candidate's code. Returns "" iff none qualify."""
    best: GrindCandidate | None = None
    for c in candidates:
        if c.craft_skill != skill or c.craft_level > current_level or not c.obtainable:
            continue
        if _beats(c, best):
            best = c
    return best.code if best is not None else ""
