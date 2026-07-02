# Learned Per-Monster Potion Economy — Design (Phase 1)

Date: 2026-07-02
Status: approved (brainstorm), pending spec review

## Problem

Potion provisioning today (`marginal_potion_qty_pure`, `ProvisionMarginalFightGoal`)
sizes the equipped heal stack from a **win-rate heuristic**: below a win-rate
threshold, bring potions scaling toward `max_stack` as win-rate falls. It never
learns how many potions a monster *actually* costs. As monsters get harder, the
right number of on-hand potions rises, and that number is directly observable
after each fight. We should **learn per-monster heal demand from real fights** and
size provisioning (and crafting) from it, seeded by the combat model until samples
exist.

Corollary (Phase 2, out of scope here): the same substrate should learn how
*non-heal* utility effects (resist/boost/…) affect combat, driving the bot to
craft more than just heal potions. Phase 1 builds the data model to generalize;
it only wires the heal effect.

## Decisions (from brainstorm)

1. **Phasing:** heal-first, but the recorded data + accessors are keyed to
   generalize to `(monster, effect)`. No non-heal logic in Phase 1 (no dead code).
2. **Learned quantity:** per-monster **HP-healed-per-fight** (`potions_expended ×
   restore`), i.e. effect-magnitude needed per fight. Potion-tier-agnostic:
   provisioning converts back via `ceil(hp_need / this_potion.restore)`. Phase 2
   adds sibling per-effect magnitudes.
3. **Cold-start seed:** `expected_damage_per_fight` from the existing `predict_win`
   model (`_expected_hit(monster→player) × rounds_to_kill`). No new tuning
   constant; self-consistent with the winnability verdict. Learned average
   overrides once samples exist.
4. **Provisioning:** the HP-need quantity **replaces** the win-rate quantity.
   Beatability (`is_winnable`/`predict_win`) still gates *whether* to fight;
   `hp_need` sets *how many potions*.
5. **Craft economy:** the `CraftPotions` baseline gains a term so a harder active
   target monster drives crafting more potions (not just char level).

## Observability (why this is feasible)

Equipped utility consumables auto-consume during combat; the fight API response
returns the updated character, and `WorldState.from_character_schema` already
captures `utility1_slot_quantity` / `utility2_slot_quantity`
(`world_state.py:282-283`). So on a `Fight(monster)` cycle:

```
potions_expended = (prev.utility1_qty + prev.utility2_qty)
                 - (new.utility1_qty  + new.utility2_qty)     # >= 0 on a win
hp_healed        = sum over consumed codes of qty_consumed × item.restore
```

Per-code restore is needed for the HP normalization, so we record the consumed
**codes+quantities**, not just a scalar count. Monster is parsed from the
`Fight(x)` action repr (as `success_rate` keying already does).

## Components

### §1 Recording (learning substrate)
- **`Cycle` model** (`learning/models.py`): add `consumables_expended_json: str =
  "{}"` — `{item_code: qty}` consumed this cycle. Sparse; non-empty only on fights
  that consumed potions. Generalizes to any utility effect (Phase 2 reads the same
  field, resolves each code's effect).
- **`GamePlayer`** (`player.py`): on the action-execution path, when the action is
  a `FightAction`, compute the equipped-utility delta between `prev_state` and
  `new_state`, resolve to `{code: qty}`, and pass into `_record_learning_cycle` →
  persisted in `consumables_expended_json`. Zero/empty when nothing consumed.
  (`_record_combat_outcome` already fires here — same seam.)

### §2 Demand accessor
- **`LearningStore.hp_healed_per_fight(monster_code, window=WINDOW_ACTION)`** →
  `float | None`: mean `hp_healed` over the last-`window` **winning**
  `Fight(monster_code)` cycles with a consumables record; `None` below
  `WARMUP_MIN_SAMPLES` (mirrors `action_class_cost` / `success_rate` warmup gating).
  `hp_healed` per row = `Σ qty × game_data.item_stats(code).hp_restore` — needs a
  restore lookup, so the accessor takes a `restore_of: Callable[[str], int]` the
  caller supplies from item stats (the store stays GameData-free). (`hp_restore`
  is the `ItemStats` field populated from the potion's `restore` effect.)

### §3 Seed + provision quantity (new proven pure core)
- **`expected_damage_per_fight(state, game_data, monster_code) -> int`**
  (`ai/combat.py` or a sibling): extract `_expected_hit(monster→player) ×
  rounds_to_kill` from `predict_win`'s existing computation. Returns 0 when
  unwinnable/irrelevant (caller won't fight anyway).
- **`potion_provision_qty_pure(hp_need, potion_hp_restore, held_heal_qty,
  utility_slot_filled, max_stack) -> int`** — NEW pure decision core:
  ```
  if utility_slot_filled or held_heal_qty <= 0 or potion_hp_restore <= 0: return 0
  desired = ceil(hp_need / potion_hp_restore)   # (hp_need + r - 1) // r
  return min(desired, held_heal_qty, max_stack)
  ```
  Replaces `marginal_potion_qty_pure` in the provision path.
- **`ProvisionMarginalFightGoal` wiring** (`strategy_driver.py:_marginal_provision_goal`):
  `hp_need = hp_healed_per_fight(monster, ...) or expected_damage_per_fight(...)`;
  `qty = potion_provision_qty_pure(hp_need, best_heal_restore, held, False, UTILITY_SLOT_MAX_STACK)`.

### §4 Craft economy hook
- **`potion_supply` baseline** (`potion_baseline_pure` caller): baseline becomes
  `max(level_scaled_baseline, provision_target_for_active_target_monster)`, clamped
  to `UTILITY_SLOT_MAX_STACK`. The active combat target monster comes from the
  same `ctx.combat_monster` the provision goal uses; its `hp_need` →
  `ceil(hp_need / target_potion.restore)`. Cold (no target / no data) → unchanged
  level baseline (no regression).

## Formal / verification obligations

- `marginal_potion_qty_pure` is a proven core (`formal/Formal/MarginalPotionQty.lean`
  + `formal/diff/test_marginal_potion_qty_diff.py` + mutation anchors). Phase 1
  **supersedes it**: introduce `potion_provision_qty_pure` as a NEW proven core
  (Lean model + differential + mutation, per the formal-development discipline —
  ceil-div + triple-min bound), and **retire** `marginal_potion_qty_pure` and its
  Lean/diff/mutation artifacts in the SAME change (no orphaned proofs; gate part
  (d) globs `formal/diff/`). If any other caller of `marginal_potion_qty_pure`
  exists, migrate it first.
- `expected_damage_per_fight` reuses `predict_win` internals — extract without
  changing `predict_win`'s verdict (the proven `predict_win` core stays intact);
  keep the extraction a thin reader, not a second combat model.
- Snapshot/liveness fixtures unaffected (no game-data shape change).

## L50 capstone threading

This economy sits on the capstone's causal chain: **survivability → fight
success → XP gain → level-up → L50** (`FightReady` → `Leveling` →
`LevelFiftyReachableP`). More on-hand potions widen the set of fights the bot
actually wins, which is the XP source the measure-descent liveness argument
rests on.

**Soundness (Phase 1 does not touch proofs):** the capstone winnability core
(`WinnableGrounded` / `WinnableAcrossBand`) is currently **potion-blind** — it
witnesses winnability from best-obtainable loadout + projected HP only, with no
heal-reserve term. Phase 1 provisioning/crafting therefore strengthens *actual*
runtime survivability **beyond** the conservative proven floor: every fight the
proof calls winnable stays winnable (potions only add HP headroom), and some
fights winnable *only* with potions become reachable at runtime without any
claim in the proof. So Phase 1 is conservative-safe — it cannot weaken the L50
argument. The one hard constraint: the runtime must actually EQUIP what any
winnability assumption relies on — since the proof assumes zero potions, there is
nothing extra to guarantee in Phase 1 (the economy is pure upside).

**Capstone-tightening opportunity (the integration point):** the natural next
formal step this economy unlocks is a **potion-extended effective-HP** term in
`WinnableAcrossBand` — model `effectiveHp = projectedHp + guaranteedHealReserve`,
where `guaranteedHealReserve` is bounded by what the economy *guarantees* on hand
(`potion_provision_qty_pure` output × restore). That would WIDEN the proven
winnable band (fights past the current bare-HP frontier become provably winnable
*given* the economy stocks the stack), tightening `FightReadyReach` /
`WinnableAcrossBand` and thus the L50 liveness. This is a deep proof change
(`WinnableAcrossBand` currently holds 49/49 only under best-loadout + full HP).
**Decision: deferred to Phase 1.5** (tracked capstone-tightening spec). Phase 1
ships the runtime economy with the L50 proof UNCHANGED (conservative-safe); the
`effectiveHp` extension is isolated as its own follow-up so the delicate proof
change does not gate shipping survivability value.

## Testing (TDD, 0/0/0/100%)

- `consumables_expended_json` round-trips; player records `{code: qty}` on a
  fight that consumed potions, `{}` otherwise; non-fight cycles never populate it.
- `hp_healed_per_fight`: `None` below warmup; mean over winning fights; ignores
  losses and no-consumable fights; window-bounded.
- `potion_provision_qty_pure`: ceil-div sizing; the three clamps (held, max_stack,
  slot-filled/zero-restore → 0); differential + mutation (new anchors), old anchors
  removed.
- `expected_damage_per_fight`: matches `_expected_hit × rounds_to_kill` on fixtures;
  0 when unwinnable.
- Provision goal: uses learned demand when present, seed otherwise; quantity =
  `ceil(hp_need/restore)`.
- Craft baseline: rises for a harder target monster, unchanged when cold.

## Out of scope

**Phase 1.5 (capstone-tightening, tracked):** potion-extended `effectiveHp` term
in `WinnableAcrossBand` — model `guaranteedHealReserve` from the economy's
provision guarantee, widen the proven winnable band, tighten `FightReadyReach` /
L50 liveness. Deep proof change, isolated from Phase 1 (see L50 threading §).

**Phase 2 —** Non-heal utility effects: per-effect magnitude accessors over the same
`consumables_expended_json` substrate; attribute win-rate/expenditure deltas to
equipped utilities; craft best-ROI non-heal potions per monster. Also learnable
and named by the user but deferred: damage-dealt attribution (fight-log parse),
multi-effect potion selection.
