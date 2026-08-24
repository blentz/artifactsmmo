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
`ai/acquisition_cost.acquisition_actions`, a route-aware lower bound over all six
ways an item can be obtained; `cycles_to_fifty` comes from
`cheapest_path_to_level`, denominated in cycles, one cycle per executed action.
S-004 may add them only because they are the same unit. That projection was
denominated in SECONDS until 2026-08-07 and ran ~80x high — see
`ai/learning/projections.FIGHT_CYCLES_PER_KILL`. Anything mixed in here that is
not an action count (a gold price, a level gap, a wall-clock cooldown) reintroduces
exactly that class of bug, silently.

WHAT CHANGED WHEN `min_plan_length` WAS RETIRED FROM THIS SEAT. It modelled three
actions — gather, craft, equip — and treated any item WITHOUT A RECIPE as a raw
gatherable, so a vendor item and a drop farm both priced at 2 while a craft chain
priced correctly. Cost was decided by whether an item had a recipe, never by how
it is obtained. Measured on `l12_deep_chain_grind`: `iron_sword` 65 -> 96 (venue
hops and the weaponcrafting gate now included), `feather` 2 -> 14 (the drop farm
priced), `copper_dagger` 62 -> 70.

An item whose materials have NO route this cycle now prices in the millions
(`acquisition_cost_core.UNOBTAINABLE_PER_UNIT` per missing unit) rather than
cheaply. That is intended: in the unreachable band S-006 ranks by furthest
progress and breaks ties on cost, so a genuinely obtainable candidate now beats
an unobtainable one it used to lose to. It also means a candidate can price
unobtainable one cycle and finitely the next, since every route is STATE-AWARE.
`J` only ever compares candidates within a single cycle, so that is sound here —
but a reader of consecutive traces will see the ranking move for reasons that are
about the world, not about the objective.

The bank is no longer credited as free holdings. `min_plan_length` had no
withdraw action, so its callers passed inventory PLUS bank; here WITHDRAW is a
priced route, and counting the bank as owned as well would credit the same copy
twice.
"""

from dataclasses import replace

from artifactsmmo_cli.ai.acquisition_cost import acquisition_actions
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.tiers.horizon_contribution import horizon_outcome
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


def _outcome(projected: WorldState, store: LearningStore,
             game_data: GameData, target: int = TARGET_LEVEL) -> tuple[int, int]:
    """`(reachable_level, cycles_to_target)` for a state, from one
    `cheapest_path_to_level` walk.

    `target` DEFAULTS TO `TARGET_LEVEL`, and every production caller takes the
    default — this parameter exists so a target sweep can happen without
    monkey-patching a module constant, which is how the measurements in
    `docs/PLAN_bounded_horizon_objective.md` were taken and is not a thing a
    diagnostic should have to do. (Its former caller, the `objective` CLI, was
    retired in wave 3b; the parameter itself stays for the `--target` shape
    documented in that plan's measurements.)

    IT DOES NOT PARAMETERISE THE BANDING, DELIBERATELY. `progression_choice`
    still classifies against its own `TARGET_LEVEL`, and that constant is
    mirrored in `Formal.ProgressionChoice` and pinned pointwise by
    `formal/diff/test_progression_choice_diff.py`, so threading a target through
    the proved core means changing five theorems and the oracle's wire format.
    Under option C of the bounded-horizon scope the whole banding apparatus is
    DELETED rather than parameterised, so paying that proof cost now would be
    paying it to remove it later. A caller passing a non-default target gets an
    honest `(reachable_level, cycles)` pair and must not read the band off it.

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
    and `J` is an integer objective (S-013 — exact, no floats, no thresholds).

    THE CYCLES HALF IS `horizon_contribution.cycles_to_horizon`, not a second copy
    of it. That module needs the same figure for a state with no candidate attached
    (a MEANS has none), and two spellings of "run the walk and round up" would be
    free to drift — which would put the objective and the worth of a course on
    subtly different scales, the exact defect S-016 is about. It answers None for a
    blocked walk; the 0 filler is applied HERE, where the band that ignores it
    lives."""
    reachable_level, reached = horizon_outcome(projected, store, game_data, target)
    return reachable_level, 0 if reached is None else reached


def trunk_candidate(state: WorldState, store: LearningStore,
                    game_data: GameData,
                    target: int = TARGET_LEVEL) -> ProgressionCandidate:
    """The XP arm: grind the character to 50 with the gear already worn.

    Acquisition cost is 0 — there is nothing to obtain — which is what makes the
    trunk the baseline every gear candidate must beat by saving more cycles than
    it costs to acquire."""
    reachable_level, cycles = _outcome(state, store, game_data, target)
    return ProgressionCandidate(
        identity=TRUNK_IDENTITY,
        acquire_cost=0,
        reachable_level=reachable_level,
        cycles_to_fifty=cycles,
        failed=False,
    )


def gear_candidate(c: GearCandidate, state: WorldState, store: LearningStore,
                   game_data: GameData,
                   ctx: SelectionContext = NO_PROFILE_CONTEXT,
                   target: int = TARGET_LEVEL) -> ProgressionCandidate:
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
    # RE-ACTIVATED after the blow-up was fixed. The first activation was reverted
    # hours later: the walk was exponential in recipe FAN-OUT, so `adventurer_vest`
    # (four inputs) ran 10.1M recursive calls in 20s without finishing while
    # `iron_sword` (two) took 10ms, and four of five live characters ran ~2x
    # slower per cycle. `acquisition_cost_core` now memoises a per-item unit cost
    # and ignores capacity (which can only RAISE cost, so omitting it keeps the
    # bound sound), making the walk linear: seven-input recipes price in under
    # 10ms. Two benchmarks over HOLDING SIZE now guard the axis that had no test.
    acquire_cost = acquisition_actions(
        c.code, 1, state, game_data, ctx, equip=True, store=store)
    reachable_level, cycles = _outcome(projected, store, game_data, target)
    return ProgressionCandidate(
        identity=candidate_identity(c),
        acquire_cost=acquire_cost,
        reachable_level=reachable_level,
        cycles_to_fifty=cycles,
        failed=False,
    )


def branch_ranking(state: WorldState, game_data: GameData,
                   candidates: list[GearCandidate],
                   store: LearningStore,
                   ctx: SelectionContext = NO_PROFILE_CONTEXT,
                   target: int = TARGET_LEVEL) -> list[ProgressionCandidate]:
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
        [gear_candidate(c, state, store, game_data, ctx, target) for c in candidates]
        + [trunk_candidate(state, store, game_data, target)]
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


def reached_spread(ranked: list[ProgressionCandidate], target: int) -> int | None:
    """`max(cycles) - min(cycles)` over candidates whose walk actually REACHED
    `target`, or None when fewer than two did.

    How much the benefit term can discriminate at a given horizon. Measured live
    2026-08-18 — Lor L16 to milestone 20 spread 229 cycles, R2D2 L19 to milestone
    20 spread 0 — which is why the horizon has two degenerate ends and not one.
    Relocated from the retired `objective` CLI in wave 3b; its sole remaining
    caller is `tests/test_ai/scenarios/test_band_edge_horizon.py`, which measures
    this spread directly over `branch_ranking`'s output.

    Candidates whose walk stopped short are excluded, not counted as zero: their
    cycles figure is a filler (`_outcome` returns 0 on a blocked walk), and
    folding a filler into a spread would report a discrimination that does not
    exist."""
    reached = [c.cycles_to_fifty for c in ranked
              if not c.failed and c.reachable_level >= target]
    if len(reached) < 2:
        return None
    return max(reached) - min(reached)
