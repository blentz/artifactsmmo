# PLAN — `combat_deficit`: one fact replaces five mechanisms

## Why

Live evidence, 2026-08-20, C3P0 (session `session-20260820-011324-320621`, 272
cycles, `exit_reason='stuck_exit'` — the first in 345 recorded sessions):

* `Fight(pig)` **0 wins / 42 losses**. `combat_loadout_outcome` holds 42 rows of
  `(predicted_win=0, actual_win=0)` — one row per *resolved* fight, computed from
  `prev_state_for_learning` (pre-action, full HP). **The model was right every
  time and the bot fought anyway.**
* Measured offline against live state: `combat_margin(C3P0, pig) = -10`.
  Four reachable upgrades close it — `iron_sword`, `iron_armor`,
  `earth_boost_potion`, `earth_ring` (margin `+1`). Three need `iron_bar`.
* What it actually pursued for 10 hours: `UpgradeEquipment(iron_boots->boots_slot)`
  — with `iron_boots` **already worn**, and boots absent from all 24 margin-improving
  items.

### The deficit chain is four layers deep

```
fight deficit  <-  gear deficit  <-  skill deficit  <-  material deficit
predict_win        iron_sword        weaponcrafting 6->10   iron_bar x6
  = False          earth_ring        jewelrycrafting 8->15  iron_bar x5
```

The bot has a mechanism for every layer (`LevelSkill`, `UpgradeEquipment`,
`GatherMaterials`). **None of them is linked to the fight that was lost.**

### What stands in for the link today: a countdown

`Player._suppressed_goals` is `dict[goal_name, cycles_remaining]`, decremented
per cycle and pruned at zero (`player.py:2128`). `GOAL_OSCILLATION` recovery sets
`GrindCharacterXP(pig) -> 5` (L1), `-> 15` (L2), then **L3 raises `StuckExit`**
(`player.py:2437`).

```
lose pig -> oscillation -> suppress grind N cycles -> gear chain runs
         -> countdown hits 0 -> nothing about the gear changed -> lose pig
         -> escalate -> L3 -> StuckExit          <- killed C3P0 at 07:28 UTC
```

Trace confirms the shape: `gear_review` fires **every** cycle; `goal_rank` holds
exactly ONE goal on 228/272 cycles; `UpgradeEquipment` and `GrindCharacterXP(pig)`
are **never both candidates** (0 of 46 pig cycles); the grind is listed in
`suppressed_goals` on 108 cycles and absent on 164.

**The bot's entire answer to "I lost that fight" is a timer.** It cannot converge,
and the terminal rung of the ladder kills the character instead of fixing the gear.

> NOTE — corrects an earlier claim in this investigation: `REPEATED_ACTION_FAILURE`
> is NOT the operative rule. Measured over all 272 cycles, the most `Fight(pig)`
> failures in any 30-cycle window was **8**, against a threshold of 10 — the
> recovery cycles after each loss dilute it below its own bar. The operative rule
> is `GOAL_OSCILLATION` (it is the only rule that suppresses a goal *by name*).
> Which ladder reached L3 is not recoverable from the trace; stdout was not captured.

## The unification

One derived fact:

```
combat_deficit(monster, state, game_data) -> Deficit | None
  None            when predict_win(state, game_data, monster)
  Deficit(...)    otherwise: the ranked acquisitions that most close combat_margin
```

It is a **fact, not a timer**: it clears itself the moment the gear lands.

| today | after |
|---|---|
| `winnable_cascade` tier 1 "winnable check INTENTIONALLY bypassed" + its Lean no-veto theorem | **deleted** — task monster pursued iff deficit is `None` |
| `task_feasibility.MONSTER_LEVEL_MARGIN = 2` (monsters branch) | **deleted** — a worse duplicate of `predict_win` |
| `map_guard` GEAR_REVIEW -> monster-blind `find_upgrade_target` | asks `combat_deficit` for the item that closes the margin **against that monster** |
| `GOAL_OSCILLATION` countdown on a losing grind | grind blocked **while** deficit is non-`None` |
| `StuckExit` as the terminal answer to an unwinnable fight | unreachable for this class |

Net change is **removal**: one Lean theorem, one constant, one countdown path.

### USER decision, recorded

> "when the deficit exists and no single thing fixes it, that just means we need
> multiple upgrades before we can win that fight. the time it takes is just the
> cost of progress."

So there is **no fallback branch**. The deficit closes incrementally; the character
keeps closing it. It does NOT fall back to grey monsters and does NOT park the task.

## Increments

Each lands with `bash formal/gate.sh` green before the next starts.

* **0 — `combat-deficit` CLI (read-only).** Prints baseline margin, the ranked
  improving items, and the greedy reachable chain — i.e. what the offline sweep
  produced. This is the ORACLE every later increment is checked against, and it
  is how "did this actually change live behaviour" gets answered. Precedent:
  `project_objective_cli_diagnostic`.
* **1 — `combat_deficit` core.** Pure, over `combat_margin`; unit + differential
  tests. Must NOT be another proved-but-uncalled helper
  (`feedback_proof_over_an_uncalled_helper`) — increment 2 is its first caller and
  lands in the same series.
* **2 — GEAR_REVIEW becomes monster-aware.** `find_upgrade_target` takes the
  monster the latch fired on; ranks by marginal winnability, not `_best_by_value`.
  Generalises `marginal_weapon_winnability` from weapons-only/negative-filter
  (its sole caller today is `progression_tree.py:121`, `<= 0` -> exclude) to
  all-slots/driver.
* **3 — suppression by fact.** Grind on `m` blocked while `combat_deficit(m)` is
  non-`None`; remove the oscillation countdown for this class.
* **4 — delete the tier-1 bypass** and its Lean no-veto theorem; task pursuit
  gated on deficit.
* **5 — delete the monsters branch of `MONSTER_LEVEL_MARGIN`.**

## Acceptance

Per `feedback_no_trace_file_dependency`, acceptance rests on
`~/.cache/artifactsmmo/learning.db`, never on `play-trace-*.jsonl`:

1. `select count(*) from combat_loadout_outcome where predicted_win=0` stops
   growing. Today: 63 rows, 42 of them C3P0/pig in one session.
2. No new `sessions.exit_reason='stuck_exit'` attributable to a losing grind.
3. A character whose deficit is non-`None` shows gear/skill goals in
   `selected_goal`, and **no** `Fight(<deficit monster>)` in `action_repr`.
4. Runtime activation proven on live `plan <char>` before "done"
   (`feedback_verify_runtime_activation`) — green tests are not evidence.

## Traps carried in from memory

* `feedback_two_plan_producers` — `craft_plan_gen` is a `nodes=0` fast path
  BEFORE A*; only A* reads `relevant_actions`. A runtime proof must reach the
  changed path.
* `feedback_goal_relevant_actions_missing_edges` — 3rd occurrence of a fired rung
  that never plans. Check Fight / OptimizeLoadout / Rest / synthesized Withdraw.
* `project_fight_loadout_precondition` — a gate on `FightAction.is_applicable`
  ripples into EVERY Fight emitter or stalls it.
* `feedback_zero_vacuousness` — deleting the no-veto theorem must not leave a
  vacuous replacement.
* `project_l50_honest_restatement` — grants hidden in a DEFINITION are invisible
  to `#print axioms`.
