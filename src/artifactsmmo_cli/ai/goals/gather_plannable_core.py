"""Pure core of `GatherMaterialsGoal.is_plannable`'s skill-gate fast-fail.

Extracted so the formal differential test (`formal/diff/test_skill_gate_fastfail_diff.py`)
can exercise the exact decision logic against the kernel-proved Lean model
`Formal.SkillGateFastFail.isPlannable` (`formal/Formal/SkillGateFastFail.lean`),
whose `fastfail_sound` theorem proves: when this returns False, no plan can ever
raise the owned count to `needed`, so pruning the goal discards nothing reachable.
"""


def gather_plannable_pure(target_in_needed: bool, has_craft_gate: bool,
                          cur_level: int, craft_level: int,
                          owned: int, needed: int) -> bool:
    """True ⇒ the GatherMaterials goal is worth planning; False ⇒ fast-fail.

    Mirrors `Formal.SkillGateFastFail.isPlannable`:
    `!targetInNeeded || !hasGate || craftLevel ≤ curLevel || needed ≤ owned`.

    - `target_in_needed` False (materials-only goal, e.g. gathering raw `feather`):
      always plannable — gathering inputs never needs the gated final craft.
    - no craft gate, or the crafting skill already meets the recipe level:
      the craft is applicable, so the goal can be planned normally.
    - otherwise the craft is blocked: only plannable if enough is already owned.
    """
    if not target_in_needed:
        return True
    if not has_craft_gate or cur_level >= craft_level:
        return True
    return owned >= needed
