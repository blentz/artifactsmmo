# Design: Per-Goal Inventory Profiles (soft targets, not hard caps)

Date: 2026-06-07
Status: Drafting — pending user confirmation, then implementation
Trigger: live bot livelock + user direction.

## The observed bug (live trace, Robby cyc 20–38)

The bot livelocked: `GatherMaterials(fishing_net)` withdrew `ash_wood×10`
repeatedly while `DepositInventory→DepositAll` dumped it every ~6 cycles — zero
progress for 18+ cycles, stuck-detector silent (actions "succeed", so it doesn't
read as no-progress/oscillation).

Root cause (user-confirmed): inventory **upper bounds are space-blind hard
limits**:
1. `DepositInventoryGoal._RAMP_START = 0.5` — deposit pressure begins at 50%
   inventory used and outranks `GatherMaterials`, so the bot cannot accumulate
   materials past half-full even with 60+ free slots.
2. `inventory_caps.useful_quantity_cap = max_recipe_demand × BATCH_BUFFER(5)` —
   per-item hard caps whose sum is far below `inventory_max`; `DiscardOverstock`
   dumps anything over the per-item cap regardless of free space.
3. The bank keep-set (`bank_selection._keep_codes`) protects `task_code` +
   `crafting_target` recipe inputs, but NOT the **active gather goal's** target
   materials — so `ash_wood` for `fishing_net` (not the `crafting_target`) is
   banked, undoing the withdraw.

Net: the player can never use its full inventory, and an active gather goal whose
materials aren't in the keep-set thrashes withdraw↔deposit forever.

## Design direction (from the user)

> "Per-goal inventory profiles that are targets we try to maintain, but not hard
> limits."

Replace hard, space-blind caps with **soft per-goal target profiles**: the active
goal declares the inventory it *wants to maintain* (the materials + quantities it
needs); inventory management steers *toward* that profile but never dumps profile
items, and deposit/discard fire only under **genuine space pressure** (near-full),
not at a fixed fraction or a per-item recipe cap.

## Proposed architecture

### 1. The profile — what a goal wants to hold

A pure value object `InventoryProfile = dict[item_code -> target_qty]` (the
materials the active goal/objective-step wants on hand). Produced by a pure
function from the active goal + game data, e.g. for `GatherMaterials(item, needed)`
the profile is `needed` (the recipe-closure raw materials × required quantities);
for `PursueTask` the task item + its recipe inputs; for gear/tool steps the step's
recipe closure. This is the SOFT TARGET, not a limit.

### 2. Deposit/discard become space-driven + profile-preserving

- `DepositInventoryGoal`: raise `_RAMP_START` to a high watermark (e.g. ~0.85–0.9)
  so deposit pressure only appears when the bag is genuinely filling — the player
  can use most of its inventory. AND deposit must NEVER bank a profile item (the
  active goal's targets join the keep-set). It deposits only non-profile bankables.
- `DiscardOverstock` / `overstocked_items`: an item is overstock only when it
  exceeds its profile target AND the bag is under real space pressure — i.e.
  overstock is `held − max(profile_target, useful_floor)` and is only acted on when
  `used_fraction` is high. Below the high watermark with free slots, nothing is
  overstock (no premature dumping).

So the hard `useful_quantity_cap` stops being a dump trigger; it becomes (at most)
a tiebreak for *which* overstock to shed once the bag is actually full. The profile
target is the floor we protect.

### 3. Keep-set includes the active profile

`bank_selection._keep_codes` (and the deposit relevant-actions filter) must union
in the active goal's profile item codes, so DepositAll/DiscardOverstock can never
bank/delete a material the current goal is actively accumulating. This directly
kills the fishing_net/ash_wood livelock.

## Proof obligations (keep the gate honest)

`InventoryChainSafe` / `inventory_caps` are proof-backed; the change must preserve
safety, not hollow it:
- **Safety (unchanged invariant):** the bot still deposits/discards BEFORE
  inventory overflows — a Gather that would exceed `inventory_max` is still
  preceded by space-making. Prove the high-watermark deposit still fires in time
  (deposit value > 0 whenever a further gather would overflow), so raising
  `_RAMP_START` does NOT reintroduce a gather-fails-on-full bug.
- **Profile-protection (new):** prove deposit/discard never remove a profile item
  below its target (the keep-set ⊇ profile, mirroring the proven task keep-set
  protection). A pure `overstock(held, profile_target, used_fraction, watermark)`
  core with dominance/safety theorems, differential-tested.
- **Termination/no-livelock (the real win):** with the profile in the keep-set,
  withdraw→deposit can no longer oscillate on an active-goal material — prove the
  accumulation is monotone (profile items are never banked, so held is
  non-decreasing toward the target until the craft consumes them).

## Non-goals

- The goal-SELECTION question (why `fishing_net` vs the `copper_bar` gear step) —
  fishing_net is a legitimate `target_tools` acquisition; that is a separate
  concern. This spec fixes the inventory livelock, not goal ranking.
- Per-goal profiles for guard/discretionary goals beyond what they need.

## Testing / validation

- TDD the pure `overstock`/profile cores at 100%; differential + mutation.
- Regression: existing deposit/discard/bank tests stay green (update any that
  encoded the old 0.5 ramp / per-item-cap-dump behavior — honestly, the old
  behavior was the bug).
- Scenario test reproducing the trace: a `GatherMaterials(fishing_net)` state with
  `ash_wood` in the profile + free slots → `ash_wood` is NOT deposited, held
  accumulates to the target, no withdraw↔deposit oscillation.
- Re-run the live bot and confirm the livelock is gone (gather accumulates +
  crafts fishing_net, then resumes the gear chain).
