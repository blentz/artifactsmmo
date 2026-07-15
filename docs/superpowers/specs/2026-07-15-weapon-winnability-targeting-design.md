# Weapon Winnability Targeting — Design

**Status:** approved for planning
**Date:** 2026-07-15
**Related:** `project_winnableacrossband_grounding` ("weapon-only proxy fails past L17"), `project_roadmap5_discovery` ("predict_win has NO ability-coverage guard"), `project_utility_gear_value`, `project_combat_veto_threshold`.

---

## 1. The defect (traced live on Robby, level 13)

`equip_value` ranks a weapon by a flat sum of its stats, including `sum(attack.values())`. It is **blind to damage-type-vs-monster effectiveness.** Measured:

| weapon | equip_value | attack | monsters beatable (`predict_win`, in band) |
|---|---|---|---|
| copper_axe (EQUIPPED) | 10 | earth 5 | **7** |
| fire_staff (recycled) | 43 | fire 16 | 6 |
| **fire_bow (STRATEGIC TARGET)** | **105** | fire 17 | **6** |

The local monsters resist fire / are weak to earth. So:

- **The gear target is a combat DOWNGRADE.** `CharacterObjective.from_game_data` (`tiers/objective.py:296`) ranks weapons by `equip_value` → `target_gear[weapon_slot] = fire_bow` (105). The bot commits its whole strategy to `ObtainItem(fire_bow, weapon_slot)`, grinding weaponcrafting 6→10 and churning/recycling copper_axe + fire_staff rungs — to craft a weapon that beats FEWER monsters than the copper_axe already equipped.
- **The keep authority protects the wrong weapon.** `_combat_weapon` (`inventory_keep.py:243`) → `best_fighting_weapon` → `kit_selection._pick_weapon` (`kit_selection.py:47`) crowns the "highest-attack" weapon = `sum(attack.values())`. fire_staff (16) beats copper_axe (5), so fire_staff gets `COMBAT_WEAPON` keep protection while the combat loadout correctly keeps copper_axe.
- **Result the user saw:** Robby recycled a (surplus) fire_staff and never equipped one, wielding a copper_axe, while pouring effort into fire_bow. Two subsystems disagree: gear-targeting + keep use `equip_value` (loves fire weapons); actual combat uses `predict_win` (prefers the earth axe).

Not caused by the recycle/obtain-model epic — that is pre-existing `equip_value` blindness. The epic only removed the friction, so the bot pursues the bad target efficiently and visibly.

## 2. Root cause

The **fighting-weapon choice** — both "which weapon to grind toward" and "which weapon to protect" — is made by a **damage-type-blind scalar** (`equip_value` / raw `sum(attack)`), when it should be made by **actual winnability** (`predict_win` across the monster band). `predict_win` is the authority the real combat loadout already uses; the target and keep rankers never consulted it.

## 3. Design

### 3.1 New non-Lean core — `ai/weapon_winnability.py`

`predict_win` is a runtime combat simulation (reads `state.hp`, the monster table, the full loadout). It **cannot** live inside the Lean-mirrored, pure `equip_value` / `kit_selection` cores. The winnability ranker therefore sits BESIDE them:

```python
def weapon_winnability(code, state, game_data) -> int:
    """Count of in-band monsters `predict_win` beats with `code` forced into
    the weapon slot (rest of the loadout best on-hand)."""

def best_winnable_weapon(candidates, state, game_data) -> str | None:
    """The candidate weapon maximizing weapon_winnability. Ties broken by
    damage margin, then equip_value, then code (deterministic)."""
```

**"In band"** = the monster set `predict_win` already scopes to the character's level band (the same population `combat_capable` / target selection use — reuse it, do not invent a new band). Forcing `code` equipped: `dataclasses.replace(state, equipment={**state.equipment, "weapon_slot": code})`, mirroring the diagnostic probe. **Verify `predict_win` respects the forced weapon** (it picks "best on-hand loadout for it" — confirm it does not silently re-optimize away from the forced code, or the count is meaningless); if it re-optimizes, the ranker must compute damage with `code` pinned rather than call `predict_win` blind.

### 3.2 Consumer 1 — COMBAT_WEAPON keep (Lean MODEL REFACTOR, not a reduction)

**Correction (found during planning): this is not a "reduction, no new proof burden."** `BankSelection.lean` does not take the fighting weapon as an abstract input — it **computes** it by folding the abstract `attack : Nat → Int` (`bestFightingWeapon`, an argmax mirroring `_pick_weapon`), and `criticalCodes` (the whole deposit-protection proof) depends on it. The differential (`test_bank_selection_diff.py`) pins Python's raw-attack `best_fighting_weapon` against that Lean fold over random attack tables. `predict_win` is a combat sim that **cannot** be expressed as `attack : Nat → Int`, so simply repointing Python to winnability makes the differential diverge and cannot be "retired."

The fix REFACTORS the boundary: `BankSelection.lean` takes the fighting-weapon code as an **abstract input** (`bestWeapon : Option Nat` on the model) instead of computing it by attack-fold. `criticalCodes` protects whatever code is designated — the deposit-protection theorems are **preserved** over the abstract designated weapon (they never cared HOW it was chosen). The differential feeds Python's winnability-chosen `best_fighting_weapon` in as that input. This is an honest boundary move: **Lean proves the PROTECTION mechanism; Python + unit tests + the runtime check prove the SELECTION** (winnability, un-mirrorable). The old `bestFightingWeapon` attack-fold and its theorems/mutation-anchors — which pinned a *wrong* selection — are retired; the protection theorems (`criticalCodes` shields the designated weapon) stay.

Python side: `kit_selection.best_fighting_weapon` / `best_owned_fighting_weapon` rank by `best_winnable_weapon` instead of `_pick_weapon`'s raw `sum(attack)`; the candidate SET (`_held_weapon_candidates`, the `criticalCodes` domain) is UNCHANGED. The tool half of `kit_selection` (`best_gathering_tools` + its theorems) is UNCHANGED.

### 3.3 Consumer 2 — the pursued weapon TARGET (state-aware)

**Seam found:** `progression_tree._structural_candidates` (progression_tree.py:50-57) iterates `objective.near_term_gear(state)` and arms a `GearCandidate` for the weapon slot when `gain = pursuit_value(target) - pursuit_value(equipped) > 0`. `_structural_candidates` is **pure Python — NOT Lean-mirrored** (`StrategicValue.lean` proves only the `pursuit_value` SCALAR; the one `mutate.py` hit is a comment). So the target fix is a **non-Lean guard**: for the WEAPON SLOT ONLY, suppress the candidate unless `predict_win` confirms the target weapon beats MORE in-band monsters than the currently-equipped weapon (i.e. `weapon_winnability(target) > weapon_winnability(equipped)`). When the equipped weapon is already the most winnable (copper_axe), no weapon candidate is armed and the fire_bow grind stops. The `pursuit_value` scalar is UNCHANGED; every other slot keeps `pursuit_value` ranking. This guard is the cheap, high-value half of the fix.

### 3.4 Consumer 3 — static endgame `target_gear[weapon_slot]`

`from_game_data` builds the endgame BiS sheet from `game_data` ALONE — no state — so `predict_win` (which needs state) cannot rank it. It stays on `equip_value` as an aspirational ceiling, but it **must not DRIVE pursuit**: the state-aware winnability pick (3.3) governs what the bot actually chases. Confirm the endgame sheet only supplies a ceiling and is filtered/superseded by the state-aware pick at the band the character is in (it already is at low level — the docstring notes BiS is "unreachable and filtered out"; verify the weapon slot behaves so post-change).

## 4. Scope boundaries

- **Weapon slot only.** Damage-dealing non-weapon gear (attack rings/amulets) keeps `equip_value` — deferred as YAGNI until observed mis-ranked.
- **Utility/tool gear unchanged.** `tool_value` (gathering tools), `pursuit_value` for armor/utility slots, `equip_value` for hp/wisdom/prospecting — all stay. `predict_win` does not apply to non-combat gear.
- **`equip_value` itself is NOT changed.** It remains the pure, Lean-mirrored within-slot scalar and the tie-breaker. The fix adds a ranker beside it and repoints the two weapon consumers; it does not touch the scalar's definition.

## 5. Acceptance

1. Unit tests pin `weapon_winnability` / `best_winnable_weapon`: given Robby's monster band, `copper_axe` (7) outranks `fire_staff` (6) and `fire_bow` (6); a fixture where a fire weapon genuinely beats more monsters ranks it first (proves it is winnability, not an anti-fire rule).
2. Falsifiable: a test that would FAIL if the ranker fell back to raw attack (the copper_axe-vs-fire_bow case IS that test).
3. Full formal gate green (the Lean change is a reduction — the retired weapon theorem's mutants must be removed, not left stale).
4. All four censuses stay clean (`inventory_bug 0`, `planner_bug 0`, `recycle_source_bug 0`, `obtain_parity_bug 0`).
5. **Runtime on Robby (mandatory, `feedback_verify_runtime_activation`):** `chosen_root` for the weapon slot is NO LONGER `fire_bow` (it is the equipped copper_axe or a genuine winnability gain); `_combat_weapon` protects the weapon combat actually prefers (copper_axe), not fire_staff; the weaponcrafting-grind-toward-fire_bow stops.

## 6. Out of scope

- Rewriting `predict_win` or adding ability/element-coverage modeling to it (that is `project_roadmap5_discovery`'s separate open item).
- Non-weapon damage gear (§4).
- The recycle churn itself (intended XP accelerator per `project_banked_tool_ferry`) — it only looked stupid because it was feeding a mis-targeted grind; fixing the target removes the visible waste.
