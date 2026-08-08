"""Wire the unified progression objective `J` into the branch pivot.

Builds one `ProgressionCandidate` per gear root plus one for the XP trunk, ranks
them all on `J` (`tiers/progression_choice.py`, the proved core), and lets the
winner name the branch. This is the seat `branch_pick_pure` held.

WHY THE OLD SEAT HAD TO GO. `branch_pick_pure` is a lexicographic pivot on
`band_adequate = winnable AND NOT has_structural_upgrade`. Against a 50-level
catalogue the second conjunct is never true, so the pivot never flipped: GEAR was
chosen in 2950 of 2950 cycles of a 13h five-character run that gained ZERO
character levels. A lexicographic order returns one extreme point of a Pareto
front. `J` puts both arms in one currency so the trade-off point emerges.

`band_adequate` is deliberately NOT read here. Band adequacy was a PROXY for "gear
has stopped paying", and `J` measures that directly: an adequate band is exactly
the case where no gear candidate's projection improves on the trunk's, so the
trunk's zero acquisition cost wins on its own. Keeping the proxy as an extra gate
would let it veto a gear candidate `J` had just shown to pay for itself — the
original bug, one level up. The legacy pivot survives only for callers that supply
no learning store (see `branch_by_objective`'s contract in `decide_tree`).

STAGED: BRANCH ONLY. `J` decides GEAR-vs-XP; WHICH gear is still
`focus_aging_pick`'s call, with its focus ledger, d'Hondt interleave, synergy,
achievability and role factors intact. So `J` may rank `iron_sword` top while the
aging pick commits to `iron_helm` — that is not a defect, it is the boundary of
this step. Handing root choice to `J` as well means retiring five selection
factors at once, and each of them was calibrated against a live trace.

WHICH BAND ACTUALLY DECIDES, IN PRACTICE. `cheapest_path_to_level` projects the
walk to 50 under a FROZEN loadout — it models no acquisitions along the way — so
below roughly the top band every candidate is UNREACHABLE and the ranking is
settled by S-006 (furthest reachable level, then cheapest to acquire) rather than
by the `J` sum itself. Measured across 14 committed scenarios: every candidate
unreachable in all 14, and the six GEAR verdicts were all WEAPONS, because a
weapon is the only thing that raises the ceiling a frozen loadout can grind to.
That is a sound and useful reading — "buy the cheapest thing that moves the wall,
otherwise grind" — but it is NOT the cost/benefit trade `J` describes, and the
`acquire_cost + cycles_to_fifty` sum only starts deciding once the projection can
see level 50. Treat a claim that "J is trading cost against cycles" as unverified
below that band.

THE CURRENCY IS ACTIONS, AND THAT IS LOAD-BEARING. `acquire_cost` comes from
`min_plan_length` (a lower bound on plan length, proved
`Formal.PlanModel.min_plan_length_le_plan`); `cycles_to_fifty` comes from
`cheapest_path_to_level`, denominated in cycles, one cycle per executed action.
S-004 may add them only because they are the same unit. That projection was
denominated in SECONDS until 2026-08-07 and ran ~80x high — see
`ai/learning/projections.FIGHT_CYCLES_PER_KILL`. Anything mixed in here that is
not an action count (a gold price, a level gap, a wall-clock cooldown) reintroduces
exactly that class of bug, silently.
"""

from dataclasses import replace
from math import ceil

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.projections import cheapest_path_to_level
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.min_plan_length import min_plan_length
from artifactsmmo_cli.ai.tiers.progression_choice import (
    TARGET_LEVEL,
    ProgressionCandidate,
    candidate_band,
    objective_j,
    rank_candidates,
    sort_key,
)
from artifactsmmo_cli.ai.tiers.progression_tree_core import Branch, GearCandidate
from artifactsmmo_cli.ai.world_state import WorldState

TRUNK_IDENTITY = "xp_trunk"
"""Identity of the XP-trunk candidate. `J` has no `kind` field by design (S-009
was withdrawn), so the trunk is recognised by this identity and by nothing else —
it competes on the same scalar as every gear root, at zero acquisition cost."""


def _held(state: WorldState) -> dict[str, int]:
    """Inventory + bank, the holdings `min_plan_length` credits against. Same
    accumulation `ProgressionGoal.is_reachable` performs before its own
    `min_plan_length` call, so a candidate already sitting in the bank costs the
    one Equip action there and here alike."""
    owned = dict(state.inventory)
    for code, qty in (state.bank_items or {}).items():
        owned[code] = owned.get(code, 0) + qty
    return owned


def _outcome(projected: WorldState, store: LearningStore,
             game_data: GameData) -> tuple[int, int]:
    """`(reachable_level, cycles_to_fifty)` for a state, from one
    `cheapest_path_to_level` walk.

    `PathPlan.segments` holds exactly one segment per level actually crossed, so
    `state.level + len(segments)` is the highest level the walk reached whether or
    not it completed — one formula, no branch on `blocked`, and no second encoding
    of reachability that could disagree with the first (S-014 permits only the
    level field to decide unreachability).

    A blocked walk reports `total_cycles = inf`, which is why the cycles figure is
    read ONLY when the walk completed. For an unreachable candidate `J` never
    consults it (`Formal.ProgressionChoice.unreachable_ignores_cycles` pins that
    the sort key ignores the field in that band), so 0 is a safe filler and NOT a
    claim that reaching 50 is free — the band already says it is out of reach.

    Rounded UP: a fractional cycle is still an action the character has to spend,
    and `J` is an integer objective (S-013 — exact, no floats, no thresholds)."""
    plan = cheapest_path_to_level(TARGET_LEVEL, projected, store, game_data)
    reachable_level = projected.level + len(plan.segments)
    cycles = 0 if plan.blocked else ceil(plan.total_cycles)
    return reachable_level, cycles


def trunk_candidate(state: WorldState, store: LearningStore,
                    game_data: GameData) -> ProgressionCandidate:
    """The XP arm: grind the character to 50 with the gear already worn.

    Acquisition cost is 0 — there is nothing to obtain — which is what makes the
    trunk the baseline every gear candidate must beat by saving more cycles than
    it costs to acquire."""
    reachable_level, cycles = _outcome(state, store, game_data)
    return ProgressionCandidate(
        identity=TRUNK_IDENTITY,
        acquire_cost=0,
        reachable_level=reachable_level,
        cycles_to_fifty=cycles,
        failed=False,
    )


def gear_candidate(c: GearCandidate, state: WorldState, store: LearningStore,
                   game_data: GameData) -> ProgressionCandidate:
    """One gear root: obtain and wear `c.code`, then grind to 50.

    The projected state is the current one HOLDING one `c.code` in inventory, and
    nothing else changed — same level, same xp, same worn equipment. The
    acquisition is priced separately by `acquire_cost`, so folding its cost into
    the projection too would double-count it.

    IT MUST BE INVENTORY, NOT `equipment`, and the distinction is not cosmetic.
    `state.attack`, `state.max_hp` and friends are server-authoritative TOTALS
    that already include whatever is worn, so writing a better item into
    `state.equipment` produces an incoherent state: the slot claims the upgrade
    while the totals still describe the old piece. `project_loadout_stats` then
    correctly declines to apply it — it would be double-counting worn gear — and
    the candidate projects byte-identically to the trunk. Measured on
    `l12_deep_chain_grind`: `iron_sword` written into `weapon_slot` left attack at
    `{'earth': 8}`, the wooden staff's value; the same sword placed in inventory
    moved it to `{'earth': 24}`. Every gear candidate looked worthless, `J` put
    them all in the unreachable band behind the trunk's zero cost, and the pivot
    degenerated to XP in 100% of cycles — the exact mirror of the bug it replaces.

    Inventory is also what the gear branch actually delivers: the plan `J` is
    pricing ends in obtaining the item, and `pick_loadout_cached` picks the best
    loadout from inventory ∪ equipped, so a held upgrade is worn by the projection
    the moment it beats the incumbent. A candidate that does NOT beat what is worn
    changes no monster's verdict and projects the trunk's own outcome — correctly
    reading as worthless rather than as an error.

    Nothing here can mint a FAILED candidate: `min_plan_length` is total (an
    unobtainable chain reports a conservatively LARGE bound, never a failure) and
    a blocked walk is UNREACHABLE, which is a different band. The FAILED band stays
    reachable through the core's own contract, unused by this caller."""
    projected = replace(
        state, inventory={**state.inventory, c.code: state.inventory.get(c.code, 0) + 1})
    acquire_cost = min_plan_length(
        c.code, 1, game_data.crafting_recipes, _held(state),
        game_data.max_gather_yield, equip=True,
    )
    reachable_level, cycles = _outcome(projected, store, game_data)
    return ProgressionCandidate(
        identity=candidate_identity(c),
        acquire_cost=acquire_cost,
        reachable_level=reachable_level,
        cycles_to_fifty=cycles,
        failed=False,
    )


def branch_ranking(state: WorldState, game_data: GameData,
                   candidates: list[GearCandidate],
                   store: LearningStore) -> list[ProgressionCandidate]:
    """Every gear root plus the trunk, in `J` order.

    The trunk goes LAST into `rank_candidates`, so `sorted`'s stability breaks an
    exact `J` tie toward gear rather than toward the trunk. That is deliberate and
    it is the only place the trunk gets special treatment: a tie means the gear
    pays for itself exactly, and the tie-break that matters is the one that keeps
    the loadout improving instead of freezing it. Ordering is otherwise decided
    wholly by `J` — never by comparing identities as text (S-008).

    Costs one `cheapest_path_to_level` walk per candidate, ~30ms each measured
    inside a search cache (~300ms for a 9-candidate decision, against a ~30s cycle).
    The caller opens that cache; without one this is ~14x slower — see
    `LearningStore.win_count`."""
    return rank_candidates(
        [gear_candidate(c, state, store, game_data) for c in candidates]
        + [trunk_candidate(state, store, game_data)]
    )


_FINITE_BAND = candidate_band(ProgressionCandidate(
    identity="", acquire_cost=0, reachable_level=TARGET_LEVEL,
    cycles_to_fifty=0, failed=False))
"""The finite band's value, DERIVED by asking the core to classify a candidate
that is finite by construction (reaches `TARGET_LEVEL`, has not failed) rather
than by repeating its private `_BAND_FINITE` literal here. A copied literal can
drift from the core silently; this one cannot — if the core's banding changed,
this changes with it."""


def finite_j(c: ProgressionCandidate) -> int | None:
    """`J` where it means something, None elsewhere.

    Outside the finite band `objective_j` adds acquisition cost to a cycles figure
    S-014 declares void, and the sort key never reads it there
    (`Formal.ProgressionChoice.unreachable_ignores_cycles`). Reporting the sum
    anyway would publish a meaningless number under the objective's own name."""
    return objective_j(c) if candidate_band(c) == _FINITE_BAND else None


def justifying_identities(ranking: list[ProgressionCandidate]) -> frozenset[str]:
    """The gear candidates that BEAT the trunk under `J` — i.e. exactly the ones
    whose existence justified choosing the gear branch at all.

    THE RULE: the gear branch may only pursue a candidate that justified choosing
    it. Without this the branch verdict and the root choice answer two different
    questions, and live data showed them disagreeing. R2D2, 2026-08-07: `J` chose
    GEAR because `greater_wooden_staff` raised the reachable level from 18 to 25,
    and the bot then pursued `adventurer_vest` — reach 18, zero ceiling gain, and
    the most expensive candidate on the board. HAL, in the same situation on the
    same cycle, pursued the staff. The branch was being justified by an item the
    bot did not go and get.

    Defined by `J`'s own order rather than by a hand-written "raises the ceiling"
    test, so it stays correct in every band: below the top band a candidate beats
    the trunk only by reaching further (the trunk's zero acquisition cost wins any
    tie on S-006's second key), while in the finite band it beats the trunk by
    saving more cycles than it costs. One rule, no per-band special cases, and it
    follows automatically if the core's ordering ever changes.

    Empty when the trunk is first — the XP branch, where nothing is filtered
    because no gear candidate is being pursued in the first place."""
    trunk_key = next((sort_key(c) for c in ranking if c.identity == TRUNK_IDENTITY), None)
    if trunk_key is None:
        return frozenset()
    return frozenset(c.identity for c in ranking
                     if c.identity != TRUNK_IDENTITY and sort_key(c) < trunk_key)


def candidate_identity(c: GearCandidate) -> str:
    """The `J` identity of a gear candidate — the one place the `(slot, code)`
    naming lives, so `gear_candidate` and any filter built on
    `justifying_identities` cannot drift apart."""
    return f"{c.slot}:{c.code}"


def branch_from_ranking(ranking: list[ProgressionCandidate]) -> Branch:
    """XP iff the trunk won. With no gear candidates the trunk is the only entry
    and XP follows with no special case, reproducing `branch_pick_pure`'s
    "gear yields when it has no reachable target" arm as a consequence rather than
    as a rule."""
    return Branch.XP if ranking[0].identity == TRUNK_IDENTITY else Branch.GEAR
