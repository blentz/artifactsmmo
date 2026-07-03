# Craft Unlock-Boosts to Break Leveling Stalls — Design

Date: 2026-07-02
Status: approved (brainstorm), pending spec review
Parent: Phase 2 (non-heal utility economy). Supersedes the abandoned "Phase 2a
predict_win boosts" (already implemented — see
`project_predict_win_boosts_already_done` memory).

## Problem

`predict_win` already CREDITS equipped utility boost potions
(`boost_dmg/res/hp`): they fold into `ItemStats.dmg_elements`/`resistance`/
`hp_bonus`, `pick_loadout` equips the best OWNED boost into a utility slot, and
`project_loadout_stats` folds it — so merely OWNING a boost flips `is_winnable`
for a monster it unlocks. But nothing ever CRAFTS non-heal boosts: the potion
economy (`potion_supply` / `CraftPotionsGoal`) is heal-only. So when
`_winnable_farm_target()` returns `None` (no in-band monster beatable bare),
leveling STALLS even when a craftable boost would make the next monster winnable
(the documented `combat.py:40` stall).

This feature crafts the boost that unlocks the highest-XP reachable monster when —
and only when — leveling is stalled.

## Decisions (from brainstorm)

1. **Trigger:** only when leveling is stalled (`_winnable_farm_target()` is
   `None`). A boost is never crafted while a monster is already winnable bare.
2. **Value metric:** WIN-FLIP (unlock). `predict_win(state + boost-in-inventory,
   monster)` True ⇒ the boost unlocks that monster (binary; no combat-model
   change). Efficiency (speeding already-winnable fights) is out of scope.
3. **Monster scope:** the char-XP leveling target set (in-band monsters,
   `level - LEVEL_BAND_BELOW` and up) — the same set `combat_target_monsters`
   scans. Highest-XP unlock wins.
4. **Auto-equip:** crafting the boost is sufficient. Owning it (inventory) makes
   `pick_loadout` equip it next cycle, so `is_winnable`/`_winnable_farm_target`
   pick up the unlocked monster automatically — no new equip code.

## Components

### §1 Unlock selector — pure decision core
- **`unlock_boost_target(state: WorldState, game_data: GameData) -> tuple[str, str] | None`**
  → `(boost_code, monster_code)` or `None`.
  - Precondition: only meaningful when nothing is bare-winnable; the caller gates
    on `_winnable_farm_target() is None`, but the function is self-contained
    (returns `None` if some in-band monster is already winnable with no boost, so
    it never over-crafts).
  - Candidate boosts: `code` in `game_data.crafting_recipes` whose `ItemStats` is
    `type == "utility"`, is NOT a heal (`hp_restore == 0` — heals are the Phase-1
    economy), carries a combat boost (`combat_buff > 0` OR non-empty folded
    `dmg_elements`/`resistance` OR `hp_bonus > 0` OR `antipoison > 0`), and is
    craftable-now (`state.skills[stats.crafting_skill] >= stats.crafting_level`).
  - Candidate monsters: in-band (`level >= state.level - LEVEL_BAND_BELOW`).
  - Unlock test: `predict_win(state_with_boost_owned, game_data, monster)` where
    `state_with_boost_owned = replace(state, inventory={**inventory, boost: 1})`.
    (Owning it lets `pick_loadout` equip it — the mechanism verified by repro.)
  - Selection: among pairs where the boost flips an otherwise-unwinnable monster
    to winnable, return the one unlocking the **highest** `xp_per_kill`
    (deterministic tie-break: fewest recipe items, then smallest boost code, then
    smallest monster code). `None` if no candidate unlocks anything.
- New file `src/artifactsmmo_cli/ai/unlock_boost.py` (one function). Pure over
  `state`/`game_data`; delegates the combat verdict to the proven `predict_win`.

### §2 Craft goal — `CraftUnlockBoostGoal`
- New file `src/artifactsmmo_cli/ai/goals/craft_unlock_boost.py`.
- `value`/fires: non-zero when `unlock_boost_target(state, game_data)` is
  non-`None` AND `_winnable_farm_target()` is `None` (stall). Target = the
  selector's `boost_code`.
- `relevant_actions`: REUSE the `CraftPotionsGoal` craft ladder for the target
  boost's recipe (gather/buy/withdraw/craft + equip). Extract the shared ladder
  into a helper if needed so both goals share it (DRY) — do NOT duplicate.
- `is_satisfied`: the boost is owned (in inventory ≥ 1) — once owned, the unlock
  fires via `pick_loadout`, so a single crafted batch is enough to satisfy.
- Priority: HIGH — it is a leveling stall-breaker (peer of the alchemy
  gather-bootstrap), routed through the arbiter's guard/step tier so it preempts
  discretionary work when stalled.

### §3 Arbiter integration
- Wire `CraftUnlockBoostGoal` into the strategy so it is selected when the stall
  trigger holds. It competes as a high-priority means (unblocks the char-leveling
  objective). Follow the existing bootstrap-root/guard pattern; do NOT invent a
  new tier.

### §4 Cost control
- The selector's scan is `monsters × boosts × predict_win`. It runs ONLY when
  `_winnable_farm_target()` is `None` (stall — rare), and is cached on
  `(state.level, equipped-signature, sorted owned-boost codes)` (mirror
  `combat_target_monsters`'s cache key), so it is off the hot path. Bounded:
  ~dozens of monsters × ~14 boosts; each `predict_win` reuses the same loadout
  machinery already run per cycle.

## Testing (TDD, 0/0/0/100%)
- `unlock_boost_target`:
  - Returns `None` when some in-band monster is already bare-winnable (never
    over-crafts).
  - Returns `None` when no craftable boost flips any in-band monster.
  - Returns the `(boost, monster)` unlocking the highest-XP monster when a
    craftable boost flips an otherwise-unwinnable one (real `predict_win` +
    fixture monster/boost stats, mirroring the repro).
  - Skips heal potions, not-craftable-now boosts (skill-gated), non-utility items.
  - Deterministic tie-break (two boosts unlock the same top monster → fewer
    recipe items wins).
- `CraftUnlockBoostGoal`:
  - Fires (value > 0) on a stall with an unlock available; zero otherwise.
  - `relevant_actions` emits the target boost's craft ladder (shares the
    CraftPotions ladder helper).
  - `is_satisfied` once the boost is owned.
- Arbiter: the goal is selected when stalled + unlockable; not selected when a
  monster is already winnable.
- No `predict_win` / Lean change → no differential/mutation/formal work.

## Out of scope
Efficiency boosts on already-winnable fights (needs finer-than-binary combat
metric); skill-grinding toward a not-yet-craftable unlock boost; resist/hp
survivability tuning (same selector mechanism, later); learning boost expenditure
(the Phase-1 `consumables_expended_json` substrate already tracks it if wanted).
