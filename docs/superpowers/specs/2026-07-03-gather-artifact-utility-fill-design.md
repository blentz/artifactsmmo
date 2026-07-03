# Gather-purpose artifact utility fill — design (Option B)

**Date:** 2026-07-03
**Status:** Design — awaiting user review
**Scope:** single-locus behavior fix + formal lockstep (differential binding + mutation + unit test)

## Problem

An owned utility artifact sits unequipped while its artifact slots are empty.

Live trace (Robby, level 10):

- Inventory holds 1 `novice_guide` (type `artifact`, level 10; effects hp+25, wisdom+25, prospecting+25 → pure monster-independent utility).
- All three artifact slots are empty (`Artifact 1/2/3 = None`).
- `novice_guide` is a strictly positive, zero-cost fill (level gate `10 < 10` = false → feasible).

Yet it is never equipped when the character is not on a combat plan.

### Root cause

`equipment/loadout_picker.pick_loadout` fills an empty slot only when the best
feasible candidate's benefit is **strictly positive** (loadout_picker.py:170,
`best_score <= 0` → skip). Benefit is purpose-routed by `_benefit`:

```python
def _benefit(stats, purpose):
    value = gear_value(stats, purpose)
    return -value if isinstance(purpose, Gather) else value
```

- **Combat purpose:** artifact → `armor_score`, which already adds
  `hp_bonus + wisdom + prospecting + …` (scoring.py:91). `novice_guide` scores
  75 > 0 → **fills**. This is why the artifact *does* get equipped as a fight
  prelude.
- **Gather purpose:** artifact → `-gather_score` = `-skill_effects.get(skill, 0)`
  = **0** (artifacts carry no `skill_effects`). Empty-slot gate `0 <= 0` →
  **skipped**.
- **Rank purpose:** would credit flat utility (`rank_value`), but no live caller
  picks with Rank — it is only a `gear_value` ranker key
  (equip_value.py, inventory_caps.py), never a picker purpose.

`OptimizeLoadoutAction` is emitted per-monster (Combat) and per-gathering-skill
(Gather) (factory.py:70,79). So the only path that equips an artifact today is a
Combat re-arm sequenced before a `FightAction`. Whenever the active plan is
gathering / skilling / idle (e.g. Robby's Alchemy-16 grind), no Combat optimizer
runs, the Gather optimizer scores the artifact 0, and the free +75 utility stays
in the bag until the next planned fight.

## Goal

Make an owned utility artifact fill an empty artifact slot during **gather**
plans too, reusing the existing (already-proven) Rank flat-utility benefit —
without perturbing the frozen Combat/Gather scorer bindings.

Non-goal: filling artifacts during pure-craft plans that run neither a fight nor
a gather. That requires a standing equip goal (Option A) and is out of scope.

## Design

### Behavior change (one locus)

In `equipment/loadout_picker._benefit`, route **artifact-type** candidates under
a **Gather** purpose through the flat-utility term (`armor_score` against an
empty monster attack) instead of the (always-zero) negated gather score:

```python
from artifactsmmo_cli.ai.equipment.scoring import armor_score
from artifactsmmo_cli.ai.gear_value_core import Gather

_UTILITY_FILL_TYPES = frozenset({"artifact"})  # pure monster-/skill-independent utility
_NO_MONSTER: dict[str, int] = {}               # empty attack → defense term 0 → pure flat utility

def _benefit(stats, purpose):
    if isinstance(purpose, Gather):
        if stats.type_ in _UTILITY_FILL_TYPES:
            # Artifacts grant purpose-independent utility (wisdom/prospecting/hp)
            # and carry no skill_effects, so the Gather scorer values them at 0
            # and the empty-slot gate discards them. Score by the flat-utility
            # term so a gather re-arm fills empty artifact slots. armor_score with
            # an empty monster attack zeroes the defense term, leaving exactly
            # hp_bonus+wisdom+prospecting+inventory_space+haste+lifesteal+
            # combat_buff — bit-identical to the Lean model's per-item `flatUtil`.
            return armor_score(stats, _NO_MONSTER)
        return -gear_value(stats, purpose)
    return gear_value(stats, purpose)
```

**Why `armor_score(stats, {})` and not `gear_value(stats, Rank)`:** the Lean
picker model carries a per-item `flatUtil` int (Oracle.lean `itemFromBlock`,
`b 12`) equal to `hp_bonus + wisdom + prospecting + inventory_space + haste +
lifesteal + combat_buff` (the diff `_item_block`, test_loadout_picker_diff.py:98).
`armor_score` against an empty monster attack returns exactly that sum (the
defense term `Σ mon_atk·res` collapses to 0). `rank_value` applies different
weighting and folds `combat_raw`, so it would NOT be bit-equal to `flatUtil` and
the differential would diverge. Using the flat term keeps the Gather-artifact
benefit bit-identical to `flatUtil`, and consistent with how Combat already
scores artifacts (`armor_score(monster_attack)` = defense + same flat term).

Properties:

- **Combat unchanged.** The Combat branch (`return gear_value(stats, purpose)`)
  is byte-for-byte the prior behavior — artifacts keep routing through
  `armor_score`. No Combat differential re-binding.
- **Gather weapon/armor unchanged.** Non-artifact candidates keep
  `-gather_score`, so the proven "gather picks the best tool; armor slots stay
  unchanged" behavior holds for every non-artifact slot.
- **Gather artifacts now positive.** `novice_guide` → `rank_value(...) > 0` →
  passes the empty-slot gate → fills.
- **Tie-break upgrade (bonus).** Under Gather, artifacts previously all tied at
  0 (arbitrary `max` winner). They now argmax on real utility, so the picker
  chooses the *best* owned artifact and can strictly upgrade a worn one via the
  existing no-downgrade rule (`best_score > current_score`). Aligns with the
  "no repr/alphabetical tiebreak — use a semantic key" rule.

### Scope guards

- `_UTILITY_FILL_TYPES = {"artifact"}` only. The `utility` slot type holds
  consumables (potions) handled by separate machinery; do **not** route those
  through gear scoring.
- Artifacts carry no `skill_effects`, so there is no gather-tool the artifact
  branch could shadow. If a future artifact ever gained a `skill_effect`, this
  rule would ignore it — acceptable and documented; revisit if the game adds
  skill-boosting artifacts.

### Self-activation (no new goal wiring)

`GatherAction.cost` (gathering.py:130) already adds `GATHER_LOADOUT_PENALTY`
whenever `pick_loadout(Gather)` differs from current equipment, which makes the
planner sequence `OptimizeLoadout(Gather)` before the gather. After the fix the
picker proposes the artifact → loadout differs → re-arm step inserted →
`OptimizeLoadoutAction.apply` equips it. Once equipped the loadout matches, the
penalty clears, and no further re-arm is proposed. Self-limiting; reachable for
every gathering skill including `alchemy`.

## Formal lockstep

The Lean picker model (`Formal.GearValue.pickSlotForPurpose` / `purposeBenefit`)
is already **unified over Combat / Gather / Rank**, and:

- The **Rank** benefit already exists in the model with a proven parametric
  per-slot optimality theorem (`pickSlot_purpose_rank_optimal`) and a `flatUtil`
  field aggregated onto the model `Item`.
- The Rank differential binding is **explicitly deferred** in
  `formal/diff/test_loadout_picker_diff.py` *only because no live caller picks
  with Rank*. This change introduces exactly such a live use (artifacts under
  Gather), which is the anticipated way to close that deferral.
- The structural `RealizableLoadout` proofs (realizability, one-slot-per-code /
  `dupFreeExcept`, no-downgrade, empty-fill suppression) are proven over an
  **opaque `Int` scorer** (RealizableLoadout.lean:322) — they hold for any
  benefit and need **no change**.

The existing Gather differential (`test_gather_pick_matches_lean`) generates
**only `type_="weapon"` items** and asserts the **weapon slot** only. Artifacts
are not exercised there, so the production `_benefit` change keeps that test
green — the model change is separable from the production change.

A pure-utility piece must be distinguishable from armor in the model: armor also
has `skillEffect = 0`, and hp-bonus armor has `flatUtil > 0`. If the gather
benefit returned `flatUtil` whenever `skillEffect = 0`, it would start filling
armor slots too — breaking the proven "armor slots stay unchanged under Gather"
behavior (and `test_gather_purpose_empty_armor_slots_stay_empty`). So the model
needs an explicit per-item **utility-fill** flag, mirroring the production
`type_ in _UTILITY_FILL_TYPES` guard.

Required formal work:

1. **Model + Oracle** (`formal/Formal/GearValue.lean`, `formal/Oracle.lean`):
   thread a per-item `isUtilityFill : Bool` into the loadout-picker path (carried
   as a new per-item int in `runLoadoutPicker`'s candidate/current blocks,
   alongside the existing `skillEffect` int — the current block is
   `13-int item + skillEffect`; extend to `+ isUtilityFill`). Make
   `purposeBenefit (.gather …)` return `it.flatUtil` when the item is
   utility-fill, else the existing `-skillEffect`. Re-establish per-slot
   optimality (`pickSlot_score_optimal_purpose` / the Gather branch) over the new
   benefit — the argmax/no-downgrade proofs are generic over the `Int` benefit,
   so this is a benefit-definition edit, not a new proof kind. Author the proof
   deltas via the compiler-guided Lean workflow (lean4:prove); acceptance is a
   clean `lake build`, not hand-written proof terms in this plan.
2. **Differential** (`formal/diff/test_loadout_picker_diff.py`): add an
   artifact-slot Gather property test — generate artifact-type items (utility
   stats, no skill_effects) in an artifact slot, drive `pick_loadout(Gather)`,
   and assert the chosen artifact's live `armor_score(stats, {})` equals the
   oracle's `flatUtil` benefit (bit-exact). Keep the weapon-slot test unchanged.
3. **Mutation** (`formal/mutate.py` anchors): a mutant that reverts the artifact
   branch to `-gather_score` (0) — or drops the `type_ in _UTILITY_FILL_TYPES`
   guard — must be killed. Per the bag-slot-urgency lesson, the killing test must
   be an **owned unit test** bound to this branch, not only the traversal diff.
   Refresh mutate.py anchors after the `_benefit` edit.
4. **Axiom hygiene / gate:** run `formal/gate.sh` (serialized — never concurrent
   with anything importing `src`, including the bot). No new axioms expected;
   the change is benefit-definition level, not a new proof kind.

## Tests (success criteria: 0 errors / 0 warnings / 0 skipped / 100% coverage)

Add to the existing loadout-picker test module (real fixtures, no monkeypatch of
the unit under test):

1. **Fills empty artifact slot under Gather.** State: empty artifact slots,
   inventory holds a `novice_guide`-shaped artifact (hp/wisdom/prospecting > 0,
   no skill_effects), level ≥ item level, Gather purpose. Assert `pick_loadout`
   places the artifact in an artifact slot. **This is the mutation-killing
   test.**
2. **Combat behavior unchanged.** Same artifact, Combat purpose — assert
   `pick_loadout` still fills (regression guard that the Combat path was not
   perturbed).
3. **Best-artifact argmax under Gather.** Two owned artifacts with different
   utility — assert the higher-`rank_value` one is chosen (tie-break upgrade).
4. **Non-artifact Gather unchanged.** A gather tool + armor under Gather — assert
   weapon slot takes the best tool and armor slots stay unchanged (no
   regression from the new branch).
5. **Utility-type excluded.** A `utility`-type consumable is *not* pulled into a
   gear slot by the Gather artifact branch.

## Residual gap (honest)

Plans that run neither a fight nor a gather (pure crafting) still won't re-arm;
the artifact equips on the next gather or fight. Closing that fully needs a
purpose-independent standing equip goal (Option A) and is deliberately excluded
here.

## Files touched

- `src/artifactsmmo_cli/ai/equipment/loadout_picker.py` — `_benefit` artifact
  branch + `_UTILITY_FILL_TYPES`.
- `formal/Oracle.lean` (+ `Formal/GearValue*` as needed) — Gather-artifact
  `flatUtil` binding.
- `formal/diff/test_loadout_picker_diff.py` — artifact-in-Gather pool + assertion.
- `formal/mutate.py` — anchor refresh; artifact-branch mutant.
- `tests/…` loadout-picker test module — 5 tests above.
