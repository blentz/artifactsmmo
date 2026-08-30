# The blocked target: the request the fleet never made

`[SHIPPED 2026-08-29]`

## 1. The finding

⚠️ **TWO NUMBERS IN THIS TABLE ARE WRONG — see §6 for the correction.** They are
left in place rather than edited away: the reasoning built on them is still
sound, and a finding that quietly loses its false premises teaches nothing.

The fleet's coordination layer is complete and was DORMANT. Measured against
`learning.db` — 105,159 cycles, five characters, the durable record:

| | |
|---|---|
| `SupplyBank` actions ever executed | ~~**0**~~ — WRONG, see §6 |
| `supply_claims` rows | ~~**0**~~ — WRONG, see §6 |
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

---

## 6. `[CORRECTION 2026-08-30]` Two of §1's numbers were measurement errors

The fleet restarted 2026-08-30 09:40 onto this code, and the live check that
followed showed §1 was wrong twice. Both errors were mine and both inflated the
finding.

**"`SupplyBank` actions ever executed: 0" — WRONG.** That query counted
`cycles.action_repr`, and `SupplyBank` is a GOAL, not an action; the actions
under it are `Gather`, `Craft`, `DepositAll`. Counted correctly, on
`cycles.selected_goal`:

```
2026-08-02 .. 08-08 ..... 3,115 cycles
2026-08-18 .. 08-23 .....   758 cycles
2026-08-24 ..............     1 cycle
2026-08-25 .. 08-29 .....     0
2026-08-30 (this code) ..    19
total ever ..............  3,793
```

**"`supply_claims` rows: 0" — WRONG in the same family.** That table is TTL'd
live state (`claimed_at`/`expires_at`), so an empty read means "nothing claimed
at this instant", never "nothing ever claimed". The same caution applies to
`role_leases`, `material_demand`, `skill_ledger` and every other coordination
table: they are a snapshot, and only `cycles` is history.

**What survives, and it is still the finding.** The supply rung is not dead — it
is DORMANT, and it went dormant on 2026-08-24, the day the fleet hit the grey
wall and switched from moving materials to climbing skills (see
`project_grey_wall_escape_is_slow`). From that day the board carried only
quantity-1 self-servable rows, because the characters were all blocked and a
blocked character published nothing. That mechanism — verified offline through
production code, and unaffected by the miscount — is what this change fixes.

The honest headline is therefore *"the rung went quiet exactly when the fleet
started needing it"*, not *"the rung has never run"*.

## 7. `[LIVE 2026-08-30]` It works, and it asks for something nobody can make

Measured on the live fleet 4 hours after the restart:

* **3 asymmetric rows** (`self_servable = 0`) — a class the board had not carried
  since the dormancy: `slime_shield` for HAL and Robby, `birch_wood` for HAL.
* `slime_shield` is **gearcrafting@20**; Robby holds 17 and HAL 13, so both are
  gated out of it. Its recipe closure is published beside it — `king_slimeball
  6` matches the recipe exactly, `cloth 2` is the recipe's 3 netted against one
  held. **That is this change, live: the blocked target and its closure.**
* `SupplyBank` ran 19 cycles and DELIVERED: C3P0 gathered `ash_wood` x10 and
  then `DepositAll` — a complete produce-and-bank leg — with R2D2 and Robby
  gathering beside it.

**But nothing has supplied `slime_shield`, and that is correct.** Today's supply
went to `ash_wood`/`birch_wood` through the BULK arm (34 and 12 unmet, both over
`SUPPLY_DEMAND_MIN`). Nobody can serve the shield: it needs gearcrafting 20 and
the fleet's best gearcrafter is Robby at 17, so `serves_item` refuses every
candidate. The ask is honest and currently unfillable — which is itself the
information the board never had: *the whole fleet wants this and not one of us
can make it.* That is exactly the input a skill-specialization decision needs,
and it did not exist before.

**Also visible, and worth its own look: all five characters hold `logger`.**
Demand splitting is supposed to make the fifth holder of a role unattractive.
The wood demand is genuinely large, so it may be legitimate — but 5 of 5 on one
role is the pile-on shape `role_selection`'s docstring says it defends against.

---

## 8. `[SHIPPED 2026-08-30]` Idle is a RATE, not a run

Investigating why all five characters held `logger` found a structural gap in
`decide_role`, independent of everything above.

**A held role had exactly two exits, and flickering demand closed both.**

| exit | reachable when |
|---|---|
| margin scan (`rival >= own_share x 2`) | **only if own demand > 0** |
| release-on-idle | only after **100 CONSECUTIVE** zero-demand cycles |

`GamePlayer` reset the consecutive counter to 0 on any single positive
observation. So a role whose demand blipped positive even once per hundred
cycles could never be released as idle, while on every zero cycle the margin
scan could not run at all.

The idle branch's own comment names half of it — *"the margin scan below cannot
do it because it is only reached on positive own demand"* — and then answers it
with a release gated on a run that a flickering board never accumulates.

**Measured live 2026-08-30.** Replaying `decide_role` against the live board with
the dwell satisfied: all five characters returned `keep=logger` with reason
`idle 0 cycles`, while `miner` carried **64** against their own logger share of
**2.4** — a 26x rival. The `0` is the tell: a blip had just erased the evidence.

**The change.** `ROLE_IDLE_DWELL_CYCLES` is replaced by `ROLE_IDLE_WINDOW = 100`
and `ROLE_IDLE_FRACTION = 9/10`: release when at least 90% of a FULL window of
observations read zero. `GamePlayer` keeps a bounded `deque` of the last 100
observations instead of a counter, cleared whenever the role changes. A partial
window never releases — three zeros out of three is 100% and no evidence, which
is the single-sample failure the dwell was introduced to end.

The constant is **renamed rather than redefined**: its name said "consecutive"
and its meaning is now "of the last hundred", and a constant that quietly changes
what it counts is the drift this module documents everywhere else.

**What is pinned:** a 95-of-100 idle role with a positive blip now releases to a
rival that is asking; a role answering half the time still holds (the anti-churn
case, unchanged); a partial window never releases; and the 9/10 boundary is
inclusive, tested exactly, in `Fraction`.

**What is NOT established.** That this trap is what pinned the live fleet for its
4-hour session. The dwell alone explains the session that was running when I
looked (12-51 cycles, under the 100-cycle hold), and the earlier session's demand
board is unrecoverable — coordination tables are live state, not history (§6).
The trap is real and demonstrable by construction; whether it or the dwell or
correlated demand froze that particular run is unknown, and saying otherwise
would be inventing a measurement.
