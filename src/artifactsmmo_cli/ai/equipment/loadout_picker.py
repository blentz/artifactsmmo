"""Pick the best loadout from owned items for a given combat or gather purpose.

LAYERING DIRECTION: ``loadout_picker`` imports ``equipment.scoring`` (via
``gear_value``) for the per-slot scorers.  This module lives ABOVE both
``scoring`` and ``gear_value`` in the dependency graph.  No module in
``equipment.scoring`` or ``ai.gear_value`` may import from here.
"""

from artifactsmmo_cli.ai.actions.equip import DUPLICATE_SLOT_TYPES, ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.catalogue_scope import CatalogueScope
from artifactsmmo_cli.ai.equipment.realizable_loadout import ownership
from artifactsmmo_cli.ai.equipment.scoring import armor_score
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_value import gear_value
from artifactsmmo_cli.ai.gear_value_core import Gather, Rank, purpose_key
from artifactsmmo_cli.ai.world_state import WorldState

_UTILITY_FILL_TYPES: frozenset[str] = frozenset({"artifact"})
"""Item types whose value is purpose-independent flat utility (wisdom/prospecting/
hp). They carry no skill_effects, so the Gather scorer values them at 0 and the
empty-slot gate discards them — this set routes them through the flat-utility
term instead. NOT `utility` (consumable/potion slots handled elsewhere).

UNRELATED to `DUPLICATE_SLOT_TYPES`, which also once named "artifact": this set
is about how an artifact is SCORED, that one about how many slots one code may
occupy (artifacts: exactly one, HTTP 485 — Lor probe 2026-08-22). Three DISTINCT
artifacts still fill all three slots through this set.

The differential mirrors this set at ``formal/diff/test_loadout_picker_diff.py``
(``_UTILITY_FILL_TYPES``) to classify oracle candidates independently; keep the
two in sync — a divergence trips the bit-exact Gather-artifact binding test."""

_NO_MONSTER: dict[str, int] = {}
"""Empty monster attack / resistance / player attack: armor_score's defense term
Σ mon_atk·res collapses to 0 and its offense term Σ p_atk·… collapses to 0 (no
attack to scale the piece's damage %), leaving exactly 200 × the flat utility sum
(bit-identical to the Lean model's 200 * flatUtil)."""


def _ordered_slots() -> list[str]:
    """Deterministic slot iteration order for the one-slot-per-code rule.

    Iteration order MATTERS: when two multi-slot peers (e.g. ring1_slot,
    ring2_slot) compete for the same scarce item code, the slot visited first
    takes it (the code then sits in the projected result and is infeasible for
    every later slot). We sort by (type-group, slot-name) so the order is
    stable across runs and matches the natural left-to-right convention of
    multi-slot types.
    """
    seen: set[str] = set()
    out: list[str] = []
    for slots in ITEM_TYPE_TO_SLOTS.values():
        for slot in slots:
            if slot not in seen:
                seen.add(slot)
                out.append(slot)
    return sorted(out)


_ORDERED_SLOTS: list[str] = _ordered_slots()
"""`_ordered_slots()` evaluated once at import.

It is a pure function of `ITEM_TYPE_TO_SLOTS`, a module-level constant built at
import time by `gear_taxonomy`, so the per-call rebuild could only ever produce
this same list — 34,403 rebuilds and 0.46s in the census profile for one answer.
Read-only: `pick_loadout` iterates it and `_candidates_by_slot` keys a fresh dict
from it; neither mutates, and a mutation would be a cross-call bug rather than a
slow path. `_ordered_slots` itself stays as the single producer of the rule.
"""


def _candidates_by_slot(
    state: WorldState, game_data: GameData,
) -> dict[str, list[ItemStats]]:
    """Items the char owns (inventory + currently-equipped), grouped by the slots
    they fit — every slot's candidate list, built in ONE pass.

    Per slot the answer is unchanged: the same `sorted(pool)` order, the same
    None/level filter, the same `slot in ITEM_TYPE_TO_SLOTS[type_]` membership.
    Only the loop nesting moved. It used to be one FULL pass per slot — the pool
    rebuilt, re-sorted and every code re-resolved through `game_data.item_stats`
    sixteen times for one `pick_loadout`, which made the resolve the single
    hottest line in the bot: 5.4M `item_stats` calls and 8.8 of 24.5 seconds in
    the `combat_deficit` census (profile 2026-09-11), and 86% of live planner
    samples sat inside `pick_loadout` for the same reason (2026-07-06, py-spy).
    The pool does not depend on the slot, so fifteen of those sixteen passes
    were answering a question already answered.
    """
    pool: set[str] = set()
    for code in state.inventory:
        if state.inventory[code] > 0:
            pool.add(code)
    for equipped_code in state.equipment.values():
        if equipped_code:
            pool.add(equipped_code)

    # Every slot gets a list, including the ones nothing owned fits: callers
    # index this by slot and an absent key would read as "no such slot" rather
    # than "no candidate". Total by construction — `_ORDERED_SLOTS` is derived
    # from the same `ITEM_TYPE_TO_SLOTS` values indexed below.
    result: dict[str, list[ItemStats]] = {slot: [] for slot in _ORDERED_SLOTS}
    # Sorted iteration: `pool` is a set, and hash-seed iteration order leaked
    # into the argmax tie below (cross-process nondeterministic picks, e.g.
    # copper_armor vs feather_coat at L5 — C1b finding). Candidate order is
    # now canonical so the pick is reproducible everywhere.
    for code in sorted(pool):
        stats = game_data.item_stats(code)
        if stats is None or state.level < stats.level:
            continue
        for slot in ITEM_TYPE_TO_SLOTS.get(stats.type_, []):
            result[slot].append(stats)
    return result


BENEFIT_MEMO_MAX_ENTRIES = 16384
"""Per-GameData entry bound on the `(purpose, code) -> benefit` memo.

Sized against the work that actually shares entries: one `combat_deficit` walk
holds a handful of live purposes (the chain re-equips, which moves
`Combat.player_attack` and therefore the purpose) over a catalogue of ~10^2
equippable codes, so a few thousand entries covers a walk with room to spare —
the 3-scenario census probe fills 6,239 and evicts nothing. The bound exists for
the LIVE bot, where purposes churn with every monster the planner considers for
the life of the process. Eviction is in INSERTION order, not LRU; see
`_benefit_of`."""

_BenefitKey = tuple[tuple[object, ...], str]

_BENEFIT_MEMO: "CatalogueScope[_BenefitKey, tuple[ItemStats, int]]" = CatalogueScope(
    BENEFIT_MEMO_MAX_ENTRIES)
"""`_benefit` memoized ACROSS calls, scoped per GameData — see
`ai/catalogue_scope`, which owns the whole argument about why a cache may not
name a catalogue by a bare `id()`.

WHY THE KEY IS WHAT IT IS. `_benefit(stats, purpose)` is pure in its two
arguments, so the key has to name both:

* `purpose` enters as `gear_value_core.purpose_key`, which is INJECTIVE on the
  closed purpose set (every field of Combat and of Gather is in the tuple).
* `stats` CANNOT enter by value — `ItemStats` is an unfrozen dataclass holding
  dicts, so it is neither hashable nor cheap to hash — and it must not enter as
  `id(stats)`: an `id()` is unique only among LIVE objects, and this project has
  already shipped a memo that served one catalogue's answer to another that way.
  `stats.code` ALONE is not enough either, because two catalogues (the live
  bundle and any test fixture) both carry `iron_boots` with different stats.

So the entry is keyed `(purpose, code)` WITHIN one catalogue's scope and stores
the `ItemStats` it was computed from; a hit is served only when the caller hands
back that very object (`known[0] is stats`). Holding the object is what makes the
identity test sound where a bare `id()` would not be — the entry keeps the item
alive, so the address cannot be recycled under it — and it also makes the memo
correct across the `gd._item_stats = {...}` rebind that ~30 test fixtures do to a
GameData they have already used: a swapped catalogue hands back a DIFFERENT
`ItemStats` for the same code, which reads as a miss and recomputes.
`tests/test_ai/test_loadout_picker_benefit_memo.py` asserts exactly that
invariant."""


def _benefit(stats: ItemStats, purpose: object) -> int:
    """Higher = better candidate for `purpose`, used as argmax key per slot.

    For Combat/Rank purposes: delegates directly to gear_value (weapon_score
    for weapons, armor_score for armor — bit-identical to the old per-slot
    weapon/armor_score branch, preserving the PurposeRouting duality proved
    in Formal/PurposeRouting.lean).

    For Gather purposes: negates gear_value (= gather_score) so that the
    tool with the most-negative skill_effect (fastest cooldown) has the
    highest benefit. Armor candidates have gather_score=0, so their benefit
    is also 0 — the empty-slot gate (best_score <= 0 → skip) and the
    strict-improvement rule (> current_score) together guarantee that armor
    slots keep their current item unchanged for Gather purposes. Exception:
    types in `_UTILITY_FILL_TYPES` (artifacts) route through the flat-utility
    term `armor_score(stats, {})` instead, since they carry no skill_effects
    but do grant purpose-independent utility that pick_loadout should equip.
    """
    if isinstance(purpose, Gather):
        if stats.type_ in _UTILITY_FILL_TYPES:
            # Artifacts grant purpose-independent utility (wisdom/prospecting/hp)
            # and carry no skill_effects, so gear_value(Gather) = 0 and the
            # empty-slot gate discards them. Score by the flat-utility term:
            # armor_score against an empty monster (and an empty player attack)
            # zeroes BOTH the defense and the offense term, leaving 200 *
            # (hp_bonus+wisdom+prospecting+inventory_space+haste+lifesteal+
            # combat_buff) — bit-identical to the Lean model's per-item
            # 200 * flatUtil, and consistent with the Combat path (armor_score
            # includes the same flat sum on the same 200 scale). A Gather
            # purpose has no monster and no fight, so the combat half of the
            # unit is genuinely 0 here rather than merely unpriced.
            return armor_score(stats, _NO_MONSTER, _NO_MONSTER, _NO_MONSTER)
        return -gear_value(stats, purpose)
    return gear_value(stats, purpose)


def pick_loadout(
    purpose: object, state: WorldState, game_data: GameData,
) -> dict[str, str | None]:
    """Best {slot: item_code | None} loadout from owned items for `purpose`.

    `purpose` is one of ``Combat(monster_attack, monster_resistance)``,
    ``Gather(skill)``, or ``Rank`` (see ``ai/gear_value_core.py``).  Each slot
    is scored by ``_benefit(candidate, purpose)`` — an argmax that is
    bit-identical to the old per-slot ``weapon_score``/``armor_score`` branch
    for Combat purposes (proven in Formal/PurposeRouting.lean), and extends
    naturally to Gather (weapon slot takes the best tool; armor slots stay
    unchanged due to zero benefit).

    Each slot is optimized in a deterministic order against the PROJECTED
    RESULT, enforcing a per-code OCCUPANCY CAP: an item code C is infeasible for
    slot S once the projected result already holds C at its cap in OTHER slots —
    kept there or newly assigned by an earlier iteration. The cap is 1 for every
    type EXCEPT duplicate-allowed types (RINGS ONLY — artifacts were in that set
    until the 2026-08-22 Lor probe answered a 2nd-copy artifact equip with HTTP
    485; see actions/equip.py), whose cap is physical
    `ownership(C)`. So a non-ring code keeps the strict server ONE-SLOT-PER-CODE
    rule (HTTP 485 "This item is already equipped"), while a spare copper_ring
    MAY fill ring2_slot while ring1_slot wears copper_ring — but only when a 2nd
    copy is owned (live-server probe 2026-06-14: a duplicate ring returns HTTP
    200; without a 2nd copy the cap-1-per-owned-copy rule leaves ring2 empty,
    avoiding the inverse of the 2026-06-10 485 livelock — an unrealizable
    double-equip).
    Iteration order matters — `result` starts as a copy of `state.equipment`,
    so at slot S the "other slots" are earlier slots' final picks plus later
    slots' current items. A code DISPLACED by an earlier swap (no longer in the
    result anywhere) is legal to re-assign: the two-pass execute unequips every
    outgoing slot before any equip.

    The realizability invariant (`equipment/realizable_loadout.is_realizable`)
    follows directly: a code is assigned to a further slot only while the
    projected count is below `ownership(C)`, so total demand never exceeds
    ownership. Mirrors Formal.RealizableLoadout (capOf / pickLoadout_realizable
    + pickLoadout_one_slot_per_code → dupFreeExcept).

    Empty slots are only filled by a candidate whose benefit is strictly
    positive: a zero-benefit equip buys nothing for this purpose and burns
    the code's single legal slot.

    Slots whose feasible argmax does not strictly beat their current item keep
    the current item. Slots with no feasible candidate stay as-is.

    Caller compares with `state.equipment` to find the swap delta.
    """
    result: dict[str, str | None] = dict(state.equipment)
    candidates_by_slot = _candidates_by_slot(state, game_data)

    benefit_memo = _BENEFIT_MEMO.cache_for(game_data)
    # `gear_value` accepts the Rank CLASS as well as a Rank instance (`purpose is
    # Rank or isinstance(purpose, Rank)`), and callers use both. `purpose_key`
    # keys the closed set of purpose VALUES, so normalize the field-less class to
    # its instance before keying — the two denote the same purpose to `_benefit`,
    # and keying them apart would merely halve the hit rate, but letting the class
    # reach `purpose_key` would raise.
    memo_purpose = purpose_key(Rank() if purpose is Rank else purpose)

    def _benefit_of(stats: ItemStats) -> int:
        """`_benefit(stats, purpose)` memoized ACROSS calls, per catalogue.

        The same item is scored repeatedly WITHIN one call — once inside the
        `min` key, again as `best_score`, again as `current_score` when it is the
        equipped piece — and then again by the NEXT call, because the callers
        that dominate the profile (`combat_deficit`'s greedy chain, which probes
        every candidate gear swap against the same monster) vary the INVENTORY
        while holding the purpose fixed. That is why `pick_loadout_cached` cannot
        absorb this: its key includes the inventory, so every probe is an honest
        miss there while the per-item scores underneath are identical.

        620,628 `gear_value` evaluations for 34,403 picks in the census profile;
        a per-call memo cut that to 281,289, and carrying it across calls cuts it
        again. See `_BENEFIT_MEMO` for why the key is `(purpose, code)` inside a
        `CatalogueScope` plus an identity check on the stored `ItemStats`, and
        not `id(stats)` or a bare `stats.code`.
        """
        key: _BenefitKey = (memo_purpose, stats.code)
        known = benefit_memo.get(key)
        if known is not None and known[0] is stats:
            # NO `move_to_end`: the bound evicts in INSERTION order, like
            # `loadout_cache._equippable`'s catalogue-static memo and unlike
            # `pick_loadout_cached`'s state-keyed LRU. An entry here is
            # catalogue-static — `(purpose, code)` answers never go cold while
            # their purpose is live, and a purpose's entries are inserted
            # together, so insertion order already retires whole dead purposes
            # first. The re-link cost was 5 % of the census hot path (measured
            # 2026-09-11, 2.906 -> 2.762 s over the 3-scenario probe).
            return known[1]
        value = _benefit(stats, purpose)
        _BENEFIT_MEMO.remember(benefit_memo, key, (stats, value))
        return value

    def _dup_allowed(code: str) -> bool:
        stats = game_data.item_stats(code)
        return stats is not None and stats.type_ in DUPLICATE_SLOT_TYPES

    def _forbidden(code: str, slot: str) -> bool:
        # ONE SLOT PER CODE, generalized to a per-code occupancy CAP: a code is
        # forbidden for `slot` once the projected result already holds it at its
        # cap in OTHER slots. cap = physical ownership for duplicate-allowed
        # types (rings — server returns HTTP 200 on a 2nd copy, probe
        # 2026-06-14), else 1 (every other code keeps the strict HTTP 485 rule).
        # For non-dup codes cap=1, so `worn_elsewhere >= 1` is exactly the old
        # "present elsewhere" membership test. Mirrors
        # Formal.RealizableLoadout.forbiddenIn (capOf) — the kernel-proved
        # dupFreeExcept / realizability invariant.
        worn_elsewhere = sum(
            1 for s, worn in result.items() if s != slot and worn == code
        )
        cap = (ownership(code, state.inventory, state.equipment)
               if _dup_allowed(code) else 1)
        return worn_elsewhere >= cap

    for slot in _ORDERED_SLOTS:
        candidates = candidates_by_slot[slot]
        current_code = state.equipment.get(slot)

        # ONE SLOT PER CODE (rings: up to ownership): drop every candidate whose
        # code the projected result already places at its cap in other slots.
        feasible: list[ItemStats] = [
            cand for cand in candidates if not _forbidden(cand.code, slot)
        ]
        if not feasible:
            # Nothing equippable here — leave the slot as-is. The current item
            # (if any) is always retainable: it is worn HERE, and the duplicate
            # rule prevents any other slot from having taken its code.
            continue

        # Tie chain (feedback: semantic keys, never bare-alphabetical
        # decisions): benefit for the purpose, then item level (equal-benefit
        # candidates prefer the newer gear generation), then code — a pure
        # disambiguator between semantically identical candidates (smallest
        # code wins), which makes the pick a canonical total order instead of
        # hash-seed roulette.
        best = min(feasible, key=lambda s: (-_benefit_of(s), -s.level, s.code))
        best_score = _benefit_of(best)

        if current_code == best.code:
            continue

        current_stats = game_data.item_stats(current_code) if current_code else None
        if current_stats is None:
            if current_code is None and best_score <= 0:
                # Zero-benefit fill of an empty slot buys nothing for this
                # purpose and burns the code's one legal slot — skip it.
                continue
            result[slot] = best.code
            continue
        current_score = _benefit_of(current_stats)
        if best_score > current_score:
            result[slot] = best.code
    return result
