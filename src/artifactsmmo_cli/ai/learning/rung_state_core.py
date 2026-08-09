"""Pure core: the character's body at a rung the walk has climbed to.

S-015 (`docs/spec_cycle_oracle/SPEC.md`): *"The oracle carries a projected
character state through the walk. On crossing a rung it increments the level AND
applies the growth the published rules grant for that level, before the next
rung's admissibility, beatability and reward are evaluated."*

WHY. `cheapest_path_to_level` advanced `sim_level` and nothing else, so the
beatability verdict at rung 40 was asked of the character's rung-12 body. That
asks whether TODAY'S character can beat a monster it will not meet until it is
twenty-eight levels stronger, and answers no — which is not pessimism, it is the
wrong question.

The direction of the error matters. This figure feeds how FAR a candidate is
projected to get, so freezing the body makes the oracle UNDER-report reachability:
it can declare a target unreachable that the executor will in fact reach, and a
candidate that is honestly the best route to level 50 then loses its band.

Found by ten of the twenty-two adversaries in the blind Phase 2 round
(`W-001`), which exhibited a walk returning a fifteen-rung plan at cost 469 with
growth applied and NOT FINITE without it.

⚠️ THIS IS NOT THE CAUSE OF THE LIVE LEVEL-17 WALL, and it was measured not to be
before this was built: restoring the HP growth moves neither C3P0's nor R2D2's wall
at all, because their binding constraint is ATTACK, which comes from gear rather
than from levelling. Both facts hold — growth does not rescue those two characters,
and its absence still decides reachability in general. The clause is built because
the contract was wrong, not because it unsticks a particular character.
"""

HP_PER_LEVEL = 5
"""Maximum HP the game grants for each level gained.

From the published rules, `https://docs.artifactsmmo.com/concepts/stats_and_fights/`:
*"Each level up grants: +5 Max HP (`max_hp`), +2 inventory spaces
(`inventory_max_items`)"*.

A documented constant of the game's rules, on the same footing as the coefficients
in `GameData.xp_per_kill`'s formula — not a tuning knob and not a default standing
in for data the API could supply. The API reports a character's CURRENT `max_hp`;
it does not expose the per-level grant, so the published rule is the only source.

The +2 inventory slots half of the same rule is deliberately NOT modelled here:
nothing in the cycle oracle reads inventory capacity, so applying it would be
unobservable. `docs/spec_cycle_oracle/SPEC.md` RESIDUALS records that gap.
"""


def projected_max_hp(base_max_hp: int, base_level: int, rung_level: int) -> int:
    """`base_max_hp` grown by the levels gained between `base_level` and `rung_level`.

    Returns `base_max_hp` unchanged when the rung is at or below the level the state
    was observed at — the walk never goes backwards, and a rung it has not yet
    climbed to grants nothing retroactively. That guard is what keeps this total for
    a caller that asks about the starting rung, where `rung_level == base_level` and
    no growth has happened yet.
    """
    if rung_level <= base_level:
        return base_max_hp
    return base_max_hp + HP_PER_LEVEL * (rung_level - base_level)
