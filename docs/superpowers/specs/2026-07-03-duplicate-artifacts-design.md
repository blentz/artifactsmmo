# Duplicate artifacts (same code in multiple artifact slots) — design

**Date:** 2026-07-03
**Status:** Design — awaiting user review
**Related:** [[project_dual_ring_carveout]] (the ring precedent this mirrors), [[project_equip_owned_gear]] (equip path that inherits this), [[project_gear_demand_economy]] (the no-surplus proof this touches).

## Problem

The game server allows the **same artifact code in multiple of the 3 artifact
slots** (artifact1/2/3) — the same duplicate-allowed behavior the server has for
rings (2 ring slots). Our code forbids it: `DUPLICATE_SLOT_TYPES = frozenset({"ring"})`
(`equip.py:26`) is the *only* type exempt from the strict one-slot-per-code rule
(server HTTP 485 "already equipped"). So an artifact worn in artifact1 blocks a
2nd copy from artifact2/3 — the bot can never stack duplicate artifacts, leaving
2 of 3 artifact slots permanently unusable for a repeated artifact.

Observed: Robby wears `novice_guide` in artifact1; artifact2/3 sit empty.

### Reality caveat (why this is forward investment)

`novice_guide` (lvl 10) is a **unique, one-time item**: no craft, no trade, no
monster/resource drop, no task reward. Robby can never own a 2nd, so this feature
does nothing for `novice_guide`. Every *duplicable* artifact is lvl 20+ **and**
tradeable (buyable in multiples): `perfect_pearl`(20), `lost_world_map`(20),
`corrupted_skull`(25), `life_crystal`(30), `malefic_crystal`(35), the lvl-40
books, `sandwhisper_codex`(50). The capability activates when a character is high
enough level and buys ≥2 of one such artifact.

## Goal

Treat `artifact` as a duplicate-allowed slot type exactly as `ring` is: the bot
may equip up to `min(3 slots, ownership)` copies of the same artifact, and may
acquire extra copies of a duplicable, *acquirable* artifact to fill empty
artifact slots. Preserve every existing realizability and no-surplus guarantee.

Non-goal: stacking unacquirable artifacts (`novice_guide`) — impossible by game
content, and the existing producibility gating already prevents targeting it.

## Design

### Core: one constant

```python
# equip.py
DUPLICATE_SLOT_TYPES: frozenset[str] = frozenset({"ring", "artifact"})
```

This constant is the single source of truth already consumed by every dup-aware
site, all of which are written generically over the *set* (not hardcoded to
"ring"):

- **Equip cap** — `EquipAction.is_applicable` (`equip.py:66`) skips the
  one-slot-per-code block for dup types; `loadout_picker._dup_allowed` /
  `_forbidden` (`loadout_picker.py:156,166`) cap a dup code at physical
  `ownership(code)`. So N owned copies fill up to N of the 3 artifact slots, and
  1 owned copy leaves the others empty (never over-equips).
- **My merged empty-slot fill** — `empty_slot_rank_fills` → `pick_loadout(Rank)`
  inherits the ownership cap automatically; no change needed there.
- **Acquisition** — `progression.py:_worn_in_other_slot` (352) returns `False`
  for dup types, so a worn artifact does not veto acquiring a sibling copy;
  `_find_craftable_upgrade_target` (388) iterates only *craftable* recipes and
  `_find_inventory_upgrade` only *owned* copies, so `novice_guide` (no craft, 0
  spare) never becomes a target — no unacquirable-stall. Buyable duplicable
  artifacts flow through the same generic dup logic.
- **`OptimizeLoadoutAction.apply`** (`optimize_loadout.py:102`) and
  `objective._DUPLICATE_FILL_TYPES` (`objective.py:24`) already read the constant.

### Gear demand economy (the one non-trivial ripple)

`[[project_gear_demand_economy]]`: per-slot demand is exactly 1, except rings = 2,
which — with monotone recipes + tier dominance — yields no-surplus gear plans
(discharges corner-3). Making artifacts duplicable raises artifact demand to up
to 3 (three slots). The demand model and its no-surplus proof must extend from
"ring ⇒ 2" to "dup-type ⇒ slot-count for that type" (ring→2, artifact→3),
preserving the no-surplus / tier-dominance argument. This is the primary formal
work; the resolution (parameterize the per-slot-demand by the type's slot count,
bounded by an acquisition target) is authored via the Lean workflow.

### Formal lockstep

- **`RealizableLoadout`** is already parameterized over `dupAllowed : Code → Bool`
  (`capOf`/`forbiddenIn`); the ring theorems (`pickLoadout_dual_ring_fills_when_two_owned`,
  `pickLoadout_single_ring_no_dup_fill`) are concrete *witnesses*, not the
  invariant. The generic safety invariant already covers artifacts. Add artifact
  witness theorems (3 owned ⇒ 3 slots fill; 1 owned ⇒ sibling slots empty) so the
  new behavior has a pinned regression, mirroring the ring witnesses.
- **Oracle / differentials** — the oracle receives production `dupAllowed` (now
  including artifact); update any differential fixture that assumes ring-only dup
  and add an artifact-dup case.
- **Mutation** — a mutant that drops `"artifact"` from `DUPLICATE_SLOT_TYPES`
  (reverting to ring-only) must be KILLED by an owned unit test asserting a 2nd
  artifact fills a sibling slot; likewise the `"ring"` element stays guarded.
- No new axioms / sorry / vacuous theorems. `formal/gate.sh` green (serialized).

## Server rule + safety (accepted risk)

The same-code-artifact-dup rule is **asserted by the user, not yet live-probed**
(rings were confirmed HTTP 200 on 2026-06-14). Decision: ship on the assertion
with a documented probe trigger, not a defensive auto-heal.

- **Probe trigger (record in memory + here):** the first time any character owns
  ≥2 of a tradeable artifact, confirm the 2nd-copy equip returns HTTP 200 (not
  485). If it 485s, artifacts are NOT dup-allowed and `"artifact"` must be
  reverted.
- **Livelock caveat:** if the premise is wrong, a repeated dup-artifact equip
  could retry-loop. The dedicated repeated-action-failure StuckDetector is **NOT
  merged** ([[project_repeated_action_failure_signal]]), so the safety net is
  thinner than "existing detection catches it." This raises the importance of the
  probe trigger. (We are not adding the auto-heal fallback — user choice.)

## Testing (0 errors / 0 warnings / 0 skipped / 100% coverage)

1. `pick_loadout` with 3 owned copies of one dup artifact + 3 empty artifact
   slots ⇒ all 3 slots filled with that code. (Mutation killer for the
   `"artifact"` set member.)
2. 1 owned copy ⇒ exactly one artifact slot filled, siblings empty (ownership
   cap; no over-equip).
3. `EquipAction.is_applicable` allows equipping a 2nd copy of a dup artifact into
   a sibling slot when a copy is already worn (no 485 pre-block), and still
   forbids a non-dup type worn elsewhere.
4. Acquisition: a worn duplicable *acquirable* artifact does not veto a sibling
   copy as a target; an unacquirable worn artifact (`novice_guide`, no craft/own)
   is NOT targeted (no stall).
5. Realizability: total demand for a dup artifact never exceeds
   `min(slot_count, ownership)` — no over-equip, matching the Lean invariant.
6. Ring behavior unchanged (regression).

## Out of scope

- Unacquirable artifacts (`novice_guide`) — cannot be stacked; correctly untouched.
- The lvl 20+ tradeable-artifact *buy* pipeline sizing (how many to buy) beyond
  the per-slot demand extension — if the NPC-buy path needs its own
  quantity-for-dup handling, that surfaces during implementation as a follow-up.

## Files touched

- Modify: `src/artifactsmmo_cli/ai/actions/equip.py` (the constant).
- Modify: gear-demand-economy core (per-slot demand by slot-count) + its
  `formal/Formal/…` proof + differential.
- Modify: `formal/Formal/RealizableLoadout.lean` (artifact witnesses),
  `formal/diff/` fixtures, `formal/diff/mutate.py` (artifact-dup mutant).
- Tests: `tests/ai/…` (the 6 cases above).
