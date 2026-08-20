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

## The unified route (USER heuristic, 2026-08-20)

> "find the best candidate item that has a) best stats for the job and b) has
> obtainable materials — inclusive of requesting materials from the fleet, and
> inclusive of buyable materials from either NPC or Grand Exchange and c) has the
> lowest skill requirements (prefer things we can build, but grind skill XP only
> until it unlocks the next item or tier)"

ONE selection answers "what do I build next", parameterised by the job. Today the
job is "beat monster M"; nothing in the shape is combat-specific.

| clause | mechanism | state |
|---|---|---|
| (a) best stats for the job | `combat_deficit` margin gain vs M | ✅ built (increment 1) |
| (b) withdraw / recycle / craft / gather / NPC-buy / drop | `obtain_sources` SourceKinds 1-6 | ✅ exists |
| (b) Grand Exchange | `buy_source_venue.choose_buy_venue3` | ⚠️ built + Lean-proved, NOT consulted by `obtain_sources` |
| (b) fleet request | `role_leases`, `supply_claims`, `material_demand`, SUPPLY_BANK | ⚠️ exists as a PRODUCER rung; not a route |
| (c) bounded skill grind | `grey_farm._next_tier_level`, `GREY_FARM_NEXT_TIER_MARGIN` | ⚠️ exists, scoped to grey-farm suppression |

So (b) and (c) are **wiring and generalisation of proved parts**, not new
machinery. That is the point: the fix must be composition, not a seventh
mechanism beside six others.

**Ordering is forced.** `project_objective_spike_verdict`: pricing wall BEFORE
the acquisition edge. A candidate pool fed by a model that still walls real
routes at `10^6` would select correctly over a wrong menu.

## Increments

Each lands with `bash formal/gate.sh` green before the next starts.

* **0-1 — `combat_deficit` core + `combat-deficit` CLI.** ✅ DONE @ee8d401e.
  Read-only; no behaviour change. The oracle everything below is checked against.

* **2 — GE becomes a route in the MODEL, not just in one goal.**
  `obtain_sources._buy_sources` is permanent-NPC-only. `choose_buy_venue3` (NPC /
  GE-fill / GE-post, proved in `formal/Formal/BuySourceVenue.lean`) is already
  consumed by `goals/gathering.py:605` and `ge_bid.py:67` — so the ACTION POOL can
  fill a standing sell order that the ROUTE MODEL says does not exist. That is
  exactly the failure class `obtain_sources`' docstring was written to kill
  ("it taught the action pool about recycling, and the generator — which answers
  first — could not express it"). Keep the anti-surrogate discipline: GE is a
  route only when a standing sell order is FILLABLE (`ge_price is not None`),
  never on a speculative posted price.
  ⚠️ `reference_every_buyer_is_an_event_npc`: do NOT propagate `_buy_sources`'
  blunt `is_event_npc` gate to the GE side — GE is not an NPC and that gate would
  kill the route.

* **3 — SIBLING as SourceKind 8 (the fleet request).**
  This is `PLAN_iron_gear_acquisition.md` increment 4, whose open question its own
  text already settles: *"whether the sibling route belongs in `obtain_sources` as
  a seventh `SourceKind` … Recommend the former; the module docstring argues for
  exactly that."* Today a skill-gated item is unobtainable to a character even
  when a sibling is one craft away. ⚠️ `project_supply_claim_and_batch`: one
  producer per request, and a batch target that holds still — two characters once
  delivered 456 units against an ask of 60.

* **4 — the bounded skill grind (c).**
  Lift `_next_tier_level` out of `grey_farm` into a shared core and use it as the
  grind CAP: raise a skill only to the level that unlocks the next item or tier,
  never speculatively past it. `_gated_craft_option` already prices the unlock via
  `skill_grind_cycles`; this bounds what it is allowed to price.
  ⚠️ `project_learned_rate_level_scoping` — a learned rate that carries no level
  silently voids the grey-mob rule. Keep the cap level-scoped.

* **5 — `combat_deficit` consumes the acquisition model. THE JOIN.**
  `candidates=` (already injectable, built in increment 1 for exactly this) is fed
  the acquirable set; the greedy walk ranks on margin gain (a) and tie-breaks on
  bounded skill distance (c). One selection, three clauses, no new rung.

* **6 — replace the countdown with the fact, and DELETE the bypass.**
  Grind on `m` blocked while `combat_deficit(m)` is non-`None`; remove the
  `GOAL_OSCILLATION` countdown for this class; delete `winnable_cascade` tier-1
  and its Lean no-veto theorem, and the monsters branch of
  `MONSTER_LEVEL_MARGIN`. Net removal.

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
