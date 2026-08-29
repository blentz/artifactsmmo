# The blocked target: the request the fleet never made

`[SHIPPED 2026-08-29]`

## 1. The finding

The fleet's coordination layer is complete and was entirely idle. Measured
against `learning.db` — 105,159 cycles, five characters, the durable record:

| | |
|---|---|
| `SupplyBank` actions ever executed | **0** |
| `supply_claims` rows | **0** |
| demand rows on the live board | 4, every one quantity 1 and `self_servable` |
| `LevelSkill` share of all fleet cycles | **41%** (43,507) |
| grind cycles spent on a skill a sibling was also climbing | **28,050 — 64%** |

All five characters independently climbed gearcrafting, weaponcrafting and
jewelrycrafting. Nobody ever held the `jeweler` role.

**The plumbing was never the problem.** Leases, the skill ledger, the demand
board, four claim kinds, `SupplyBankGoal` — all present, all working, all
starved. Verified live: 5 role leases held, 40 fresh skill rows, TTLs healthy.

## 2. Why it was starved

Demand is published from the chosen root (`_own_unmet_demand` reads
`_last_decide_crafting_target`, set only when the chosen step is an
`ObtainItem`). A character blocked by a crafting-skill gate resolves to
`ReachSkillLevel`, which names no item — so it published **nothing**:

```
l12_deep_chain_grind: goal=ReachSkill(jewelrycrafting->3)  published={}
l10_weapon_upgrade:   goal=ReachSkill(jewelrycrafting->2)  published={}
```

`SUPPLY_BANK` fires on `unmet >= SUPPLY_DEMAND_MIN (10) OR asymmetric`. Every
live row was quantity 1 (fails the first) and `self_servable` (fails the
second). Nothing fired.

**The requester went silent exactly when it needed help.** The one thing a
sibling can do — clear a skill gate you cannot — is the one thing that was never
asked for. That is also the whole explanation for the 64% duplicate grinding:
nobody asks, so everybody builds.

## 3. The change

`IsThisTargetBlocked` records the target its skill gate rejected on the walk
(`RootWalk.blocked_target`), threaded to `RootResolution` →
`StrategyDecision.blocked_target` → the player — the same path `aged` already
takes, and for the same stated reason: the node that reads the gate is the one
producer, and a re-derivation in the player would be a second classifier.

`_own_unmet_demand` publishes the closure of **both** roots — what the character
is working toward, and what it is blocked out of. Two different facts, both real
demand; `closure_demand` accumulates the max across roots into one dict, which is
its documented usage.

`serves_item` then marks the blocked code NOT self-servable — the asker's own
gate is what blocked it — which is exactly what makes the request **asymmetric**,
and what `SUPPLY_BANK`'s second arm fires on at quantity 1.

**One producer, restored on the way past.** `_decide_band` and `plan_from_state`
each carried their own copy of the crafting-target derivation.
`plan_from_state`'s docstring says it "mirrors run()'s per-cycle decide+select" —
and a mirror is what it was: the copies drifted the instant `blocked_target` was
added to one of them, so the diagnostic `plan` command would have published
different demand from the live loop. Both now call
`_record_decision_targets`. Found by a probe that read the wrong path.

## 4. The end-to-end scenario

`tests/test_ai/test_supply_link_scenario.py` drives both halves through
production code on the committed bundle, one assertion per link so a break
reports where it broke:

1. the ask exists (`blocked_target == life_amulet`, derived through the real
   walk, never hand-set);
2. it reaches the board as **asymmetric**;
3. a sibling reads the asymmetry and elects a role owning that skill;
4. and picks **that item**, not one of its materials;
5. the rung fires at quantity 1, which the bulk gate alone refuses;
6. `map_means` returns a `SupplyBankGoal` for it.

Plus the negative: a sibling at the asker's own level is **not** recruited —
`serves_item` is the one level gate, and advertising help nobody can give is the
same stall by a longer route.

**Mutation-checked rather than trusted.** Both tests passed on the first run,
which is when this repo's record says to be suspicious. Suppressing the one
assignment (`walk.blocked_target = ...`) fails the scenario at link 1 and link 3;
restoring it passes. A test that cannot fail is the failure mode this file exists
to avoid.

## 5. What is still unproven

This proves the fleet now **asks**, and that a capable sibling is **selected to
answer**. It does not prove delivery: `SupplyBankGoal` → craft → deposit → the
asker withdraws is beyond where this test stops, and has never executed live.
The next honest measurement is the live one — `SupplyBank` rows > 0 and
`supply_claims` non-empty in `learning.db` after a fleet restart, which is a
query, not an opinion.

The asker also keeps grinding meanwhile. That is deliberate: this increment is
purely additive, and making the asker *stop* climbing a gate a sibling covers
(teaching `classify_target` the fleet) should wait until supply is observed to
deliver. Stopping the grind before delivery works converts a slow climb into a
stall.
