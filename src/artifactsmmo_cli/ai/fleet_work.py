"""When the coordination tables name fleet work for this character (Phase
5-2c-iv, `tiers.meta_goal.ReachFleetOutcome`). Read by the root walk, which
offers the fleet objective only while one of these holds.
"""

from artifactsmmo_cli.ai.selection_context import SelectionContext

FLEET_SUPPLY = "supply"
"""`ReachFleetOutcome.kind` for a sibling request this role banks."""

FLEET_TURN_IN = "turn_in"
"""`ReachFleetOutcome.kind` for a resolved currency turn-in election."""

# Minimum UNMET sibling demand (units of one material) that justifies pausing
# this character's own objective step to produce for a sibling. Read by
# `_fires(SUPPLY_BANK, …)` off `ctx.supply_target`'s third component — the
# still-unmet quantity `_pick_supply_target` computed, already net of what the
# requester holds and of what the shared bank already stocks.
#
# WHY A THRESHOLD AT ALL. 2026-08-01: SUPPLY_BANK moved OUT of
# DISCRETIONARY_ORDER (below the objective step, where it never won a single
# cycle of the traced four-character run) and INTO COLLECT_REWARD_ORDER, above
# the step. Unconditional promotion was considered and DECLINED: with five
# characters each publishing their root's closure demand every cycle, a
# fires-on-any-demand rung would have them serving each other most cycles and
# levelling slowly. This constant is the whole of what prevents that — it is
# load-bearing, not decoration.
#
# WHY 10, DERIVED NOT INVENTED. Two sources agree:
#   (a) Live traces. Across the 44 `play-trace-*.jsonl` runs on hand, every
#       non-null `supply_target` carried demand exactly 10 (copper_ore x10 twice,
#       ash_wood x10 once). A `>=` test at 10 therefore keeps firing on every
#       real request observed so far — the promotion is not made inert by its
#       own gate.
#   (b) The recipe graph. Running `recipe_closure.closure_demand(root, 1, …)`
#       over all 321 craftable roots in `formal/sim/game_data_snapshot.json` and
#       taking, per root, the LARGEST base-material quantity (the quantity
#       `_pick_supply_target` maximises over) gives this distribution:
#         1:25  2:6  3:1  4:3  5:9  6:8  7:1  |  10:12  12:2  15:11  20:2
#         24:15  28:5  30:6  32:2  35:3  36:12  40:8  42:11  48:13  49:9
#         50:25  54:4  56:1  60:15  66:1  70:15  80:50  100:29  110:1  120:14
#         192:2
#       There is an EMPTY BAND at 8 and 9: no root's peak base demand lands
#       there. So every threshold in 8..10 partitions the roots identically —
#       53 roots (16.5%) below, 268 (83.5%) at or above. The cut is a real gap
#       in the data, not a knife edge, and 10 is the value in that gap that also
#       matches (a) exactly.
#
# WHAT THIS BUYS: a character pauses its own chain only for a request of
# genuinely bulk size — the 24/50/80/120-unit asks that dominate the recipe
# graph and cost the requester hours of self-gathering. 83.5% of roots' peak
# requests still preempt the objective step.
#
# WHAT IT GIVES UP: sub-threshold demand no longer reaches SUPPLY_BANK AT ALL,
# because the rung left DISCRETIONARY_ORDER — there is no low-priority fallback
# slot any more. A sibling wanting <10 units, or wanting the last few units of a
# request already mostly filled, is told (by silence) to gather them itself:
# 1-9 units of one material is a handful of gather actions, cheaper to self-serve
# than to route through the bank. The measured cost of that loss is small — in
# the traced runs SUPPLY_BANK was selected zero times from the discretionary
# band, because the objective step outranked it on every cycle a step existed.
#
# THE SECOND ARM (ctx.asymmetric_demand, Task 4). The rationale above assumes
# the asker CAN self-serve — that a sub-threshold request is a handful of
# gather actions the asker itself could run. That assumption breaks whenever
# the requested code is skill-gated out of the asker's own reach:
# `sibling_demand_asymmetric` (Task 2) already did the work of proving the
# asker cannot make it, at ANY quantity, this side of a level-up. A request
# like that is never a cheaper self-serve alternative — it is simply blocked —
# so it is worth a sibling's cycle even at the observed live size of 1. That
# asymmetry (one role can fill a gap another role structurally cannot) is the
# whole point of holding a role at all, and it is a SEPARATE gate from bulk
# size: `ctx.asymmetric_demand` fires regardless of SUPPLY_DEMAND_MIN, it does
# not raise or lower the bulk threshold above.
#
# 2026-10-09 (Phase 5-2c-iv): SUPPLY_BANK left the collect band; the request
# is now the fleet objective's (`ReachFleetOutcome`), served on its rotation
# turn rather than above the step. The gate is unchanged: it still decides
# whether a request is worth this character's turns at all.
SUPPLY_DEMAND_MIN = 10


def supply_due(ctx: SelectionContext) -> bool:
    """A sibling request this role serves, large enough to be worth turns, or
    one only a role like this one can fill."""
    target = ctx.supply_target
    if target is None:
        return False
    return target[2] >= SUPPLY_DEMAND_MIN or target[0] in ctx.asymmetric_demand


def fleet_work_code(kind: str, ctx: SelectionContext) -> str:
    """The item the named work is about: the requested material, the turn-in
    item, or (a holder with no turn-in in view) the recalled currency."""
    if kind == FLEET_SUPPLY:
        assert ctx.supply_target is not None
        return ctx.supply_target[0]
    if ctx.turn_in is not None:
        return ctx.turn_in.item_code
    assert ctx.recall is not None
    return ctx.recall[0]


def turn_in_due(ctx: SelectionContext) -> bool:
    """A resolved currency turn-in election involves this character — as the
    buyer, or as a holder asked to surrender (`_resolve_turn_in` writes neither
    field for an uninvolved character)."""
    return ctx.turn_in is not None or ctx.recall is not None
