"""PURE cycles to raise a skill to a level — a gate's PRICE, not its height.

Increment 1b of the unified-acquisition epic. `obtain_sources._craft_sources`
returns `[]` when the crafting-skill gate is unmet, so at weaponcrafting 5 an
`iron_sword` (gate 10) reads as having no craft route at all. Measured on
scenario `l12_deep_chain_grind`, with the workshop KNOWN: the gate alone excluded
it. `min_plan_length` meanwhile priced the same sword at 65 while ignoring the
gate entirely. Both are wrong, in opposite directions — one calls a five-level
grind free, the other calls it impossible — and neither can be believed.

    "skill levels gate crafting tiers that unlock better weapons and armor. we
     can't craft iron items until crafting level >= 10. there is a pareto front
     spanning all character stats — there is a reason to level up each stat in
     service of reaching level 50."   — user, 2026-08-08

WHY A SKILL LEVEL GETS NO TERM OF ITS OWN. It is priced as the cost of a
PREREQUISITE, so it pays for exactly the tier it unlocks and nothing else. A
hand-weighted per-stat term would re-encode the Pareto front rather than search
it, and every weight would be a tuning surface nobody can calibrate. A single
scalar in a single currency is the instrument for SELECTING a point on such a
front — the same argument that retired `branch_pick_pure`, where a lexicographic
pivot returned one extreme point and a scalar objective found the interior.

THE UNIT IS CYCLES, WHICH ARE ACTIONS. `skill_xp_per_cycle` is measured per
executed cycle, so dividing an xp deficit by it yields actions directly, with no
seconds anywhere on the path. That is the whole reason this can be added to an
acquisition cost at all (S-004).

THE XP CURVE IS NOT IN THE API. `WorldState.skill_max_xp` reports the requirement
for the CURRENT level only; the server exposes no per-level curve. So levels
beyond the next are assumed to cost the same as the current one — the identical
assumption `cheapest_path_to_level` already makes for character levels, and
recorded there as a known limit. It under-estimates on a rising curve, which is
the SAFE direction for a lower bound whose consumers prune with it.
"""

from math import ceil


def skill_grind_cycles(current_level: int, current_xp: int, max_xp: int,
                       target_level: int, xp_per_cycle: float) -> int:
    """Cycles to raise a skill from `current_level` to `target_level`.

    `max_xp` is the xp the CURRENT level requires, applied to every level in
    between (see the module docstring — the API exposes no curve).

    PRECONDITION: `xp_per_cycle > 0`, and it is guaranteed by its only producer
    rather than re-checked here. `LearningStore.skill_xp_per_cycle` averages
    ONLY strictly-positive per-cycle deltas and returns `None` when there are
    none, so a caller either has a positive rate or has no rate at all — and the
    no-rate case is a different decision (the grind cannot be priced) that
    belongs to the caller, not to this arithmetic. A guard here could never
    fire, and an unreachable guard is exactly the dead code this epic has
    already removed once.

    Returns 0 when the gate is already met, so a caller can add this term
    unconditionally and have it vanish exactly when the skill is not a gate.
    That matters: a caller that had to branch on 'is this gated?' would be a
    second place the gate is decided, and the two could disagree.

    Rounded UP — a fractional cycle is still an action the character spends, and
    the objective is exact integers (S-013)."""
    if current_level >= target_level:
        return 0
    levels_after_this_one = target_level - current_level - 1
    remaining_xp = max(0, max_xp - current_xp) + max_xp * levels_after_this_one
    if remaining_xp <= 0:
        return 0
    return ceil(remaining_xp / xp_per_cycle)
