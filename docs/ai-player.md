# How the autonomous player decides

The player runs a sense → plan → act loop using **GOAP** (Goal-Oriented
Action Planning) with forward A* search.

**Single root objective:** find the cheapest path to maximum character level
(50). Every decision is scored against expected character-XP per cycle.
Tasks, gold, and skill-XP are means to that end, not first-class goals.

## Strategic decisions

- **Path projection** (`cheapest_path_to_level`): walks the monster ladder
  using documented per-kill XP and observed cycle costs to estimate
  cycles-remaining to L50. Trace shows `projected_cycles_to_max` and
  `path_next_action` every cycle.
- **Low-yield task cancel**: if a held task pays zero char-XP/cycle (e.g.
  items-tasks that only payout on CompleteTask), and any alternative pays
  positive, fire `TaskCancel` immediately.
- **Blocker registry**: persistent learning of progression gates (e.g. bank
  achievement requires defeating sea_marauder L45). Loaded on every session
  start; survives restarts.
- **Equipment optimizer**: per-fight loadout selection by element matching.
  Robby holding `fishing_net` will swap to `copper_dagger` vs `yellow_slime`
  (water-vs-earth resistance flip) automatically.
- **Overstock cap**: items held beyond their max recipe demand (plus task /
  equip / action-consumable / consumable-keep / task-chain floors) get sold
  or deleted in single batched actions. Healing consumables (`hp_restore>0`)
  and `tasks_coin` are protected at high caps so they aren't deleted under
  inventory pressure; the cap also walks the task-recipe chain so mid-chain
  inputs (e.g. `ash_wood` needed to craft the active `ash_plank` task)
  aren't discarded prematurely.
- **CraftRelief circuit breaker**: when inventory pressure crosses 70% AND
  the active items-task deliverable or an in-flight step's intermediate
  material is craftable from current inventory, a `CRAFT_RELIEF` guard
  preempts the deposit/discard ladder and crafts that intermediate instead —
  converting raw materials into goal progress rather than banking or deleting
  them. It never assembles end-stage gear/tools; final equipment assembly is
  left to the gear goals (so relief can't burn an objective's materials on an
  off-objective equippable).
- **Equippable goal semantics**: meta-objective `ObtainItem` for items with
  an equipment slot requires the item to actually be EQUIPPED, not just
  owned. Crafting a `wooden_shield` without equipping it no longer satisfies
  the root; the arbiter plans the `EquipAction` to close the loop.
- **Bank-stock reuse**: PursueTask / GatherMaterials / LevelSkill /
  CraftRelief all consider `WithdrawItemAction` for their recipe-chain
  inputs, so banked materials get withdrawn instead of re-gathered when a
  goal needs them.
- **Craft-skill bootstrap**: a small `ReachSkillLevel(skill, 2)` root is
  added for `weaponcrafting` / `gearcrafting` / `jewelrycrafting` whenever
  the character is at the level-1 floor, so the planner has a low-effort
  competitor for skill XP and the gear-craft loop can start.
- **HP critical floor**: `RestoreHP` priority jumps to 110 below 25% HP to
  preempt any combat goal.
- **Skill-up driver**: `LevelSkillGoal` interrupts gathering to craft for
  skill XP when a near-future upgrade is gated. Action scope is bounded to
  the skill's recipe closure (gathers + withdraws for items the skill's
  recipes consume) so the planner doesn't blow up exploring unrelated gather
  chains.
- **Survival recovery**: stuck-state detector with escalating recovery
  (state refresh → goal suppression → wildcard mode).

## Formally verified core

The decision logic is proven correct in Lean 4 over all inputs, and a
differential + mutation gate mechanically guarantees the running Python
computes the same function as the proofs — a weakened theorem or a surviving
mutant fails the build. See `formal/` and
[development.md](development.md#formal-verification).
