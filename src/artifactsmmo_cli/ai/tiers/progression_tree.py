"""The progression-tree selector (spec 2026-07-06): trunk -> branch -> target.

Phase 4b: THE decision engine — `StrategyEngine.decide` delegates here.
Consumes the same helpers the flat ranking used, so the cutover swapped the
decision procedure, not the data sources.

Value semantics only — nothing here compares reprs with the Lean model
(that lockstep lives at the pure-core level in progression_tree_core.py).

`strategy` is imported as a MODULE (attribute access at call time) because
the dependency is now circular: strategy.decide delegates to `decide_tree`
while this module consumes strategy's RootScore/StrategyDecision/
actionable_step. Module-style access on both sides keeps either import
order sound (nothing is dereferenced until after both modules finish
executing)."""

from collections.abc import Callable, Mapping
from fractions import Fraction
from types import MappingProxyType

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.requirement_graph_memo import CHAR_XP
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.tiers import strategy
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ObtainItem, ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.progression_tree_core import (
    FOCUS_FLAT,
    _NO_SYNERGY,
    Branch,
    GearCandidate,
    branch_pick_pure,
    focus_aging_order,
    focus_aging_pick,
    milestone_pure,
    potion_type_weight,
)
from artifactsmmo_cli.ai.tiers.pursuit_value import pursuit_value
from artifactsmmo_cli.ai.tiers.synergy_core import synergy_pure
from artifactsmmo_cli.ai.weapon_winnability import marginal_weapon_winnability
from artifactsmmo_cli.ai.world_state import WorldState

_NO_FOCUS: Mapping[tuple[str, str], int] = MappingProxyType({})
"""Immutable empty-focus default (mirrors the `NO_PROFILE_CONTEXT` convention):
avoids a mutable `{}` default (ruff B006). `decide_tree` only reads it
(`.get`), never mutates it — the anti-starvation ledger is owned and mutated
by `GamePlayer` (Task 6)."""

_NO_SEATS: Mapping[str, int] = MappingProxyType({})
"""Immutable empty-seats default (sibling of `_NO_FOCUS`): the d'Hondt seat
accumulator for the focus-aging interleave. `decide_tree` only reads it
(`.get`), never mutates it — the accumulator is owned and bumped by
`GamePlayer._interleave_seats` in lockstep with the focus ledger (Task 12).
Empty seats + unaged focus reproduce the plain `gear_target_pick` argmax, so
every default-arg caller is unaffected."""


def _structural_candidates(state: WorldState, game_data: GameData,
                            objective: CharacterObjective) -> list[GearCandidate]:
    """Semantics item 2 (structural slots): near-term gear whose pursuit_value
    strictly beats the currently-equipped item, weight 1 (no scaling).

    Scored on `pursuit_value` (combat-dominant efficiency budget), NOT the flat
    `equip_value`: cross-slot GAIN ranking (`focus_aging_order`) must let a
    combat weapon outrank a pure-utility artifact instead of chasing the
    prospecting artifact that flat equip_value mistakenly scored highest
    (the cross-slot bug). Both the candidate stats AND the current-equipped
    baseline (`_item_value`, also pursuit_value) are on the SAME ruler, so
    the gain is consistent."""
    candidates = []
    for slot, code in objective.near_term_gear(state).items():
        stats = game_data.item_stats(code)
        if stats is None:
            continue
        # Weapon-slot winnability guard: pursuit_value/equip_value is damage-type
        # BLIND, so it would arm a high-attack weapon that beats FEWER monsters
        # (live: fire_bow, attack fire 17, over the equipped copper_axe, attack
        # earth 5 — the local monsters resist fire, so the bot ground weaponcrafting
        # toward a COMBAT DOWNGRADE). predict_win/pick_loadout is already
        # damage-optimal PER MONSTER, so a weapon is worth grinding toward only if
        # OWNING it unlocks a monster the character cannot beat now. Suppress a
        # zero-marginal weapon target; every other slot keeps pursuit_value ranking.
        if (stats.type_ == "weapon"
                and marginal_weapon_winnability(code, state, game_data) <= 0):
            continue
        current_value = objective._item_value(state.equipment.get(slot))
        gain = Fraction(pursuit_value(stats) - current_value)
        if gain > 0:
            candidates.append(GearCandidate(slot=slot, code=code, gain=gain, level=stats.level))
    return candidates


def has_structural_upgrade(state: WorldState, game_data: GameData,
                            objective: CharacterObjective) -> bool:
    """True when a positive-gain STRUCTURAL upgrade is reachable — the
    tier-aware leg of band adequacy (2026-07-07 live-shadow correction: a
    FILLED slot holding under-tier gear must not read as adequate; an empty
    slot is just the gain-from-zero special case). Utility/potion targets
    deliberately excluded: consumable restock must never break adequacy or
    the empty-slot churn loop re-enters through the branch switch."""
    return bool(_structural_candidates(state, game_data, objective))


_UTILITY_SLOT_QTY_ATTR = {
    "utility1_slot": "utility1_slot_quantity",
    "utility2_slot": "utility2_slot_quantity",
}
"""Per-slot quantity field, mirrored from equipped_potion.py's `_QTY_ATTR`
(not imported — that map is keyed the same way but private to its module).
Used by `_utility_candidates` for the PER-SLOT stock check: unlike
`equipped_potion_qty` (which sums both slots for a given code — the churn
guard other consumers rely on and must not change), the tree needs to know
whether THIS slot specifically is already stocked, so a fill in slot 1 never
blocks a candidate for the still-empty slot 2."""


def _utility_candidates(state: WorldState, game_data: GameData,
                         objective: CharacterObjective) -> list[GearCandidate]:
    """Semantics item 2 (utility slots): skip a slot that is ITSELF already
    stocked (`state.utility1_slot_quantity`/`utility2_slot_quantity` > 0 —
    refill churn is the guard's job, not the tree's) — a per-slot check, not
    `equipped_potion_qty`'s any-slot sum, so utility1 being stocked no longer
    blacks out utility2's candidate (GAP-5). Weight by the hp_restore family
    (the only family utility_potion_targets emits today — see
    potion_type_weight's docstring for when boost/resist targets join this
    path). Same `gain > 0` guard _structural_candidates has: a zero-weighted
    family (unmodeled) or a zero-value item must never arm the gear branch or
    appear as a candidate."""
    candidates = []
    for slot, code in objective.utility_potion_targets(state).items():
        if getattr(state, _UTILITY_SLOT_QTY_ATTR[slot]) > 0:
            continue
        stats = game_data.item_stats(code)
        if stats is None:
            continue
        gain = potion_type_weight("hp_restore") * Fraction(equip_value(stats))
        if gain > 0:
            candidates.append(GearCandidate(slot=slot, code=code, gain=gain, level=stats.level))
    return candidates


def _candidate_root(candidate: GearCandidate) -> ObtainItem:
    return ObtainItem(code=candidate.code, quantity=1, slot=candidate.slot)


def _gear_ranking_rows(state: WorldState, game_data: GameData,
                       ordered: list[GearCandidate],
                       ctx: SelectionContext = NO_PROFILE_CONTEXT,
                       ) -> "list[strategy.RootScore]":
    """Semantics item 7: one row per gear candidate, best-first. Contribution
    mirrors score in every row (no separate weighting exists in this display
    path — the trunk row does the same: contribution == score == Fraction(1))."""
    rows = []
    for candidate in ordered:
        root = _candidate_root(candidate)
        step = strategy.actionable_step(root, state, game_data, ctx) or root
        rows.append(strategy.RootScore(
            root_repr=repr(root), category="gear", contribution=candidate.gain,
            cost=0, score=candidate.gain, step_repr=repr(step)))
    return rows


def _candidate_fallbacks(state: WorldState, game_data: GameData,
                         ordered: list[GearCandidate],
                         skip: GearCandidate | None = None,
                         ctx: SelectionContext = NO_PROFILE_CONTEXT,
                         ) -> tuple[list[MetaGoal], list[MetaGoal]]:
    """Root/step pairs for `ordered` (pick order), skipping `skip` (the
    candidate already promoted to chosen_root, when there is one). Shared by
    both branches: the GEAR arm skips its own pick, the XP arm skips nothing
    (the trunk — not a candidate — is the chosen decision there)."""
    roots: list[MetaGoal] = []
    steps: list[MetaGoal] = []
    for candidate in ordered:
        if candidate == skip:
            continue
        root = _candidate_root(candidate)
        step = strategy.actionable_step(root, state, game_data, ctx) or root
        roots.append(root)
        steps.append(step)
    return roots, steps


def _servable_promotion(
    chosen_root: MetaGoal, chosen_step: MetaGoal,
    fallback_roots: list[MetaGoal], fallback_steps: list[MetaGoal],
    step_servable: Callable[[MetaGoal, MetaGoal], bool],
) -> tuple[MetaGoal, MetaGoal, list[MetaGoal], list[MetaGoal]]:
    """Servability demotion (the legacy decide()'s `step_servable` role,
    surviving the flip — dropping it risks the plannability livelocks the
    filter exists to prevent, e.g. feather_coat 2026-06-20): when the chosen
    (root, step) is unservable, walk the fallback pairs IN ORDER to the first
    servable pair and promote it to chosen. Demoted pairs (the original
    chosen, then any skipped fallbacks) stay in the fallback lists after the
    promoted one — original priority order minus the promotion. All
    unservable: keep the original choice (the arbiter's doomed-memo handles
    it, as today)."""
    if step_servable(chosen_root, chosen_step):
        return chosen_root, chosen_step, fallback_roots, fallback_steps
    idx = next(
        (i for i, pair in enumerate(zip(fallback_roots, fallback_steps, strict=True))
         if step_servable(*pair)),
        None)
    if idx is None:
        return chosen_root, chosen_step, fallback_roots, fallback_steps
    promoted_root, promoted_step = fallback_roots[idx], fallback_steps[idx]
    demoted_roots = [chosen_root, *fallback_roots[:idx], *fallback_roots[idx + 1:]]
    demoted_steps = [chosen_step, *fallback_steps[:idx], *fallback_steps[idx + 1:]]
    return promoted_root, promoted_step, demoted_roots, demoted_steps


#: The char-level trunk's requirement, as a demand multiset member: it always
#: demands character progression. A gear candidate whose closure routes through
#: monster drops carries a `char_xp` token too, so it overlaps the trunk and is
#: nudged up — the "L50 slightly favoured" preference, mechanical not tuned.
_TRUNK_DEMAND: Mapping[str, int] = MappingProxyType({CHAR_XP: 1})


def _synergy_map(candidates: list[GearCandidate],
                 committed_root_code: str | None,
                 state: WorldState,
                 game_data: GameData) -> Mapping[tuple[str, str], Fraction]:
    """The per-candidate synergy multiplier (spec 2026-07-19 §3.6/§3.10): the
    demand-weighted fraction of a candidate's own ENRICHED requirement multiset
    that OTHER live roots also demand (leave-one-out), mapped through
    `synergy_pure` into [S_MIN, 1]. Keyed `(slot, code)` like the focus ledger.

    The multiset spans items (quantities) AND synthetic tokens — `skill:<name>`
    (closure items gated by that craft/gather skill) and `char_xp` (DROP leaves)
    — so alignment counts skill and character-level overlap, not just shared
    materials (`RequirementGraphMemo.requirement_multiset_for`).

    Two-pass: build each member's multiset once, SUM into `total`, then score
    each candidate `shared / own` where a token is shared iff some OTHER member
    still demands it after the candidate's own copy is removed
    (`total[i] - own[i] > 0`) — the leave-one-out subtraction. Members are the
    sibling candidates, the char-level trunk (always — `char_xp`), the committed
    root, and the current task: an items/gather task by its full enriched
    requirement, a monsters-task by `char_xp` (it produces char progression, not
    items). The committed root is usually ALSO a sibling candidate, so its demand
    enters `total` twice — deliberate: it biases toward finishing what is started
    (§3.6), and a candidate that IS the committed root overlaps itself through
    that second copy. O(N) walks (memoized on the graph), not O(N^2)."""
    if not candidates:
        return _NO_SYNERGY
    memo = game_data.requirement_graph
    own: dict[tuple[str, str], Mapping[str, int]] = {
        (c.slot, c.code): memo.requirement_multiset_for(c.code) for c in candidates}
    members: list[Mapping[str, int]] = list(own.values())
    members.append(_TRUNK_DEMAND)
    if committed_root_code is not None:
        members.append(memo.requirement_multiset_for(committed_root_code))
    if state.task_code is not None:
        if state.task_type == "monsters":
            members.append(_TRUNK_DEMAND)   # combat task -> char progression
        else:
            members.append(memo.requirement_multiset_for(state.task_code))
    total: dict[str, int] = {}
    for demand in members:
        for item, qty in demand.items():
            total[item] = total.get(item, 0) + qty
    out: dict[tuple[str, str], Fraction] = {}
    for key, demand in own.items():
        own_total = sum(demand.values())
        shared = sum(qty for item, qty in demand.items()
                     if total[item] - qty > 0)
        out[key] = synergy_pure(shared, own_total)
    return out


def decide_tree(state: WorldState, game_data: GameData,
                objective: CharacterObjective,
                band_adequate: bool = False,
                step_servable: Callable[[MetaGoal, MetaGoal], bool] | None = None,
                ctx: SelectionContext = NO_PROFILE_CONTEXT,
                focus: Mapping[tuple[str, str], int] = _NO_FOCUS,
                seats: Mapping[str, int] = _NO_SEATS,
                committed_root_code: str | None = None,
                enable_synergy: bool = False,
                ) -> "strategy.StrategyDecision":
    """The tree assembly: trunk milestone, gear/xp branch pivot, and the
    chosen root/step — composing the Task-1 pure cores exactly per the
    2026-07-06 BINDING semantics. Phase 4b: this IS the decision engine
    (`StrategyEngine.decide` delegates here).

    `band_adequate` is caller-supplied (the player wires the real
    progression-band verdict in; it defaults to False, reproducing the
    Phase-2 interim stand-in `band_adequate = candidates == []` exactly for
    every band-less caller). `gear_target_exists = candidates != []` stays
    computed internally — it is a structural fact about this decide_tree
    call, not something a caller could second-guess.

    `step_servable` is the per-cycle plannability predicate (None in unit
    tests that don't exercise plannability) — see `_servable_promotion`.

    `ctx` (the caller's per-cycle `SelectionContext`) is caller-supplied the
    same way — the player wires the real per-cycle context in; it defaults to
    `NO_PROFILE_CONTEXT`, reproducing the pre-epic descent for every caller
    that doesn't wire it in. Forwarded to every `actionable_step` call so the
    descent stops at a node with any ready `ai/obtain_sources` route instead
    of falling into its recipe (one-obtain-model epic, Task 5 — subsuming the
    recycle-as-acquisition epic's bespoke `recoverable` map).

    `focus`/`seats` (arbiter anti-starvation epic, Task 4; Task 12 perf) drive
    the pick/order aging: `focus` is the caller's per-(slot, code) commitment
    ledger (how many consecutive cycles that candidate has been the committed
    root — see `focus_aging_pick`'s `falloff`), `seats` is the caller's
    incremental d'Hondt seat accumulator (one seat bumped per aged decision,
    reset in lockstep with `focus`) feeding the single-step interleave
    `dhondt_step`. Both default to the empty-focus / empty-seats case, which
    `focus_aging_pick`/`focus_aging_order` guarantee is bit-identical to the
    plain `gear_target_pick` argmax (the old `_ordered` display order it
    replaces) — every existing caller that doesn't wire the ledger in is
    unaffected."""
    trunk = ReachCharLevel(level=milestone_pure(state.level))

    candidates = _structural_candidates(state, game_data, objective) \
        + _utility_candidates(state, game_data, objective)
    gear_target_exists = candidates != []
    branch = branch_pick_pure(band_adequate, gear_target_exists)

    # Synergy weighting (spec 2026-07-19 §3): the third selection factor after
    # magnitude (gain) and staleness (falloff). Computed once here and shared by
    # every candidate; `enable_synergy` is the caller's opt-in (the player wires
    # it) so every unit caller stays byte-identical on the inert `_NO_SYNERGY`
    # default — the §3.8 kill switch.
    synergy = (_synergy_map(candidates, committed_root_code, state, game_data)
               if enable_synergy else _NO_SYNERGY)

    ordered = focus_aging_order(candidates, focus, seats, synergy)
    pick = focus_aging_pick(candidates, focus, seats, synergy) if candidates else None
    if candidates:
        # Drift-risk hardening: the display order's element 0 must always
        # agree with the aging pick — focus_aging_order is built FROM
        # focus_aging_pick (Task 3), so this is a same-cycle consistency
        # check, not a separate authority.
        assert ordered[0] == pick, (
            "focus_aging_order(...)[0] must equal focus_aging_pick(...) — "
            "focus_aging_order is built from focus_aging_pick; the display "
            "path may never disagree with it"
        )

    # Task 12 (candidate-scoped aged verdict): the gear pick went through the
    # focus-aging INTERLEAVE this decision IFF the gear branch is chosen AND
    # some candidate has aged past the flat window — the negation of
    # `focus_aging_pick`'s fast-path condition, over the SAME candidates. The
    # player gates its d'Hondt seat bump on this (not on a whole-ledger scan),
    # so a stale ledger entry for a root that has LEFT the candidate set (e.g.
    # its slot got filled by equipping owned gear — no level-up, no equippable
    # craft, so no focus reset) can no longer make the player consume a seat on
    # a cycle that actually took the fast path. `all(...)` is over the non-empty
    # candidate list whenever the branch is GEAR (gear_target_exists holds).
    # The synergy clause mirrors `focus_aging_pick`'s widened fast-path guard: a
    # pick steered by synergy (weights differ with nothing stale) IS an aged
    # decision, so the player bumps a seat for it — otherwise the interleave
    # schedule and the seat ledger would disagree.
    aged_pick = branch is Branch.GEAR and not (
        all(focus.get((c.slot, c.code), 0) <= FOCUS_FLAT for c in candidates)
        and all(synergy.get((c.slot, c.code), Fraction(1)) == Fraction(1)
                for c in candidates))

    fallback_roots: list[MetaGoal]
    fallback_steps: list[MetaGoal]

    if branch is Branch.GEAR:
        assert pick is not None  # gear_target_exists guarantees a non-empty list
        chosen_root: MetaGoal = _candidate_root(pick)
        chosen_step: MetaGoal = strategy.actionable_step(
            chosen_root, state, game_data, ctx) or chosen_root
        # Semantics item 6: the other branch (xp trunk) first, then the
        # remaining gear candidates in pick order, each its own root/step.
        extra_roots, extra_steps = _candidate_fallbacks(
            state, game_data, ordered, skip=pick, ctx=ctx)
        fallback_roots = [trunk, *extra_roots]
        fallback_steps = [trunk, *extra_steps]
    else:
        # XP branch: the trunk IS the chosen decision. Any gear candidates
        # (possible now that band_adequate is caller-supplied: adequate band
        # with upgrades still on offer) must not be silently dropped —
        # Phase-2 final-review finding — so they survive as fallbacks, in
        # pick order, so the arbiter can still fall back to gear when the
        # trunk step yields no goal.
        chosen_root = trunk
        chosen_step = trunk
        fallback_roots, fallback_steps = _candidate_fallbacks(
            state, game_data, ordered, ctx=ctx)

    if step_servable is not None:
        chosen_root, chosen_step, fallback_roots, fallback_steps = _servable_promotion(
            chosen_root, chosen_step, fallback_roots, fallback_steps, step_servable)

    trunk_row = strategy.RootScore(
        root_repr=repr(trunk), category="char_level", contribution=Fraction(1),
        cost=0, score=Fraction(1), step_repr=repr(trunk))
    ranking = [trunk_row, *_gear_ranking_rows(state, game_data, ordered, ctx)]

    # interrupt/desired_state are trace-shape compatibility only: RestoreHP
    # preemption lives in the engine-independent arbiter guard ladder, and
    # no consumer reads desired_state off the decision post-flip.
    return strategy.StrategyDecision(
        interrupt=None,
        chosen_root=chosen_root,
        chosen_step=chosen_step,
        desired_state={},
        ranking=ranking,
        fallback_steps=fallback_steps,
        fallback_roots=fallback_roots,
        aged_pick=aged_pick,
    )
