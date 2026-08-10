# Witness ledger — <project>

Every resolved distinguishing pair, in the order they were ratified.

**This file is the acceptance suite.** Not a log, not a record of what happened — the
source the harness harvests from. Each witness already carries a concrete input, two
candidate outputs, and the answer the spec author chose. That *is* a test:

```gherkin
Given  <distinguishing_input>
When   the system runs
Then   <ratified>            # and NOT <rejected>, which an uncertified impl would do
```

You do not author the acceptance suite. You harvest it. So write these entries as
**executable facts**, not as prose about a discussion. If a reader cannot turn an
entry into a passing test without asking a question, the entry is not done.

Two rules that keep the ledger honest:

- **Ids are permanent.** `W-004` is cited by a clause, by a scenario, and by the grid.
  Never renumber, never reuse.
- **A witness is never deleted.** A witness the author decided is a *don't-care* is
  resolved as `DON'T-CARE` and stays in the ledger — it is a carve-out, and carve-outs
  go on the record. Deleting it would hide a decision that was actually made.

### W-001 · projected-state-levelup-growth-not-applied

| | |
|---|---|
| **cell** | 4. Rung walk driver and per-rung state advancement (XP carry-over, level-up stat growth)/degenerate |
| **Σ dimension** | value semantics |
| **severity** | 5 |

**Distinguishing input**
```
character = {level 5, xp 0, requirement 1000, max_hp 100}; target level 20; observations = {} (empty); catalogue = [wolf: level 6, hp 200, beatable iff full HP >= 100; troll: level 12, hp 3000, beatable iff full HP >= 140]. Both monsters permitted (S-010); no forced recovery, so one kill = one action. The spec fixes WHICH hit points the beatability predicate sees (full, not current) but never says whether the state the oracle hands that predicate at rung N has accrued the published '+5 maximum HP' per level gained since rung 0. Both A and B advance the character's LEVEL between rungs (S-007's formula and S-013's penalty require it); they differ only in whether the level-up stat growth is applied.
```

| | behavior |
|---|---|
| **A** | A (growth applied: max_hp 100 -> 105 -> ... so the troll becomes beatable at rung 13): rungs = [6 wolf 32, 7 wolf 36, 8 wolf 40, 9 wolf 44, 10 wolf 48, 11 wolf 50, 12 wolf 77, 13 wolf 77, 14 troll 8, 15 troll 8, 16 troll 8, 17 troll 8, 18 troll 11, 19 troll 11, 20 troll 11]; total_cost = 469 (target reached). |
| **B** | B (max_hp stays 100, only the level advances; the troll is never beatable): rungs = [6 wolf 32, 7 wolf 36, 8 wolf 40, 9 wolf 44, 10 wolf 48, 11 wolf 50, 12 wolf 77, 13 wolf 77, 14 wolf 84, 15 wolf 84, 16 wolf 91]; total_cost = NOT FINITE (at rung 16 the wolf is 10 levels beneath the character, awards 0, and S-013/S-012 stop the walk). |

**Resolution:** `RATIFIED -> A`
**Because:** The published rules grant +5 maximum HP per level unconditionally, and equipment carries a minimum-character-level condition. A walk that advances only the level field asks whether the character's CURRENT body can beat a monster it will not meet until it is many levels stronger, so it under-reports reachability and can call a target unreachable that the executor will in fact reach. Ten of the round's adversaries found this independently; the exhibited case returned a 15-rung plan at cost 469 with growth applied and NOT FINITE without it. Author chose to re-evaluate the loadout too, because minimum level is an equip condition and freezing gear reintroduces the same error one layer down.
**Became:** `S-015` — The walk carries a projected character state that grows as it climbs

---

### W-002 · s008-may-use-measurement-optional

| | |
|---|---|
| **cell** | 12. Walk-stop decision (no admissible monster / zero reward)/conflicting |
| **Σ dimension** | value semantics |
| **severity** | 5 |

**Distinguishing input**
```
character = {level 30, xp_progress 0, xp_required 1000, hp 200, max_hp 200}; target level 31; catalogue = [blue_slime: level 18, hp 60, 2 actions per kill (fight + forced recovery)]; observations = {blue_slime: measured rate 25.0 xp per kill}. blue_slime is beatable and permitted; the published formula gives it 0 xp at player level 30 because the gap is 12 (0% penalty band). The zero-reward stop question and the measurement question are the same question here: 'awards nothing' is exactly what S-008 says a measurement MAY overwrite, and S-013 never says which of the two rates the stop test reads.
```

| | behavior |
|---|---|
| **A** | rungs = [(level 30 -> 31 via blue_slime, cost 80)], total_cost = 80 (walk completed; S-008's permissive 'may' exercised, so the rung's rate is the measured 25 xp/kill, kills = ceil(1000/25) = 40, cost = 40 x 2 actions) |
| **B** | rungs = [], total_cost = not finite (S-008's 'may' declined, so S-007's prediction stands at 0 xp/kill; every admissible monster awards nothing, so S-013 stops the walk at rung 30 and S-012's reporting rule applies) |

**Resolution:** `RATIFIED -> A`
**Because:** S-008's bare permissive left two conformant oracles that never agree: one always consults a measurement, one never does. That is not a tolerable freedom, because the two rank the same rung's candidates differently and so send the bot to different monsters. Author chose the requirement reading: evidence beats the model where evidence exists.
**Became:** `S-016` — A measurement supersedes the prediction, it does not merely may
**Reattributed to `S-017`.** S-016 failed Phase 2c's closure check twice and was WITHDRAWN; its id is retained and never reused. A withdrawn clause that decides nothing by its own terms earns no attribution, so this witness is now carried by S-017, which is what actually restates a measurement for the rung it is used at. One clause may answer two witnesses; S-017 also carries W-003.

---

### W-003 · measurement-validity-across-character-levels

| | |
|---|---|
| **cell** | 9. Measured-rate lookup and unit reconciliation (observations vs prediction)/normal |
| **Σ dimension** | value semantics |
| **severity** | 5 |

**Distinguishing input**
```
char = {level: 9, xp_into_level: 0, xp_to_level: 200}; target level = 12; catalogue = [chicken {level: 1, hp: 60, whole-loop actions per kill = 2}]; observations = {chicken: 6.0 xp per kill}. The measurement is keyed by monster only — the spec never says at which character level it was taken or whether the published level-penalty step still modulates it as the character climbs from 9 to 12 (gap crosses the 70% band and then the 0% band). Predicted value for comparison: 3 xp/kill at level 9, 0 at level 11.
```

| | behavior |
|---|---|
| **A** | A treats a measurement as level-invariant (a measured rate supersedes the prediction outright, penalty included): 6.0/2 = 3 xp per action at every rung, ceil(200/3) = 67 each. Returns rungs=[('9->10', chicken, 67), ('10->11', chicken, 67), ('11->12', chicken, 67)], total_cost=201 — target reached. |
| **B** | B re-applies the published level penalty on top of the measured rate: level 9 gap 8 -> 70% (6.0*0.7/2 = 2.1, ceil(200/2.1) = 96), level 10 same, level 11 gap 10 -> 0% so the rung earns nothing and S-013/S-012 stop the walk. Returns rungs=[('9->10', chicken, 96), ('10->11', chicken, 96)], total_cost=NOT FINITE (inf) — target not reached. |

**Resolution:** `RATIFIED -> C`
**Because:** Neither branch as posed. A measurement is not valid as-is at every rung, and the author did not want it discarded outside its penalty band either -- band edges make the rate jump discontinuously at an arbitrary boundary. Chosen instead: restate the measured rate for the rung by the ratio of the published award at the two character levels, which carries the penalty step and the base-term decay together and is continuous. This is the correction already implemented and live-verified: before it, one character projected reaching level 50 by farming a level-4 monster at a flat rate from rung 12 to rung 49.
**Became:** `S-017` — A measured rate is restated for the rung it is used at

---

### W-004 · what-counts-as-a-present-measurement

| | |
|---|---|
| **cell** | 9. Measured-rate lookup and unit reconciliation (observations vs prediction)/absent |
| **Σ dimension** | value semantics |
| **severity** | 5 |

**Distinguishing input**
```
char = {level 10, xp 0, xp-per-level 100, wisdom 1.0}; target level 11; catalogue = [chicken: level 8, hp 60, loop_actions 2] (beatable and permitted, so S-009/S-010 admit it); observations = [{monster: "chicken", measured_xp_per_action: 0.0, samples: 0, recorded_at_level: 10}] — a store entry EXISTS for chicken but carries no samples behind it. Predicted rate from S-007: Round((8/10*20 + 60*0.04)*1.0) = 18 xp/kill / 2 loop actions = 9.0 xp per action.
```

| | behavior |
|---|---|
| **A** | rungs=[] , total_cost = NOT FINITE (the entry is read as a present measurement of 0.0 xp/action, so no admissible monster awards anything and the walk stops under S-013/S-012) |
| **B** | rungs=[(10->11, chicken, 12)] , total_cost = 12 (an entry with zero samples is 'no measurement', so S-007's prediction of 9.0 xp/action stands and the rung is priced ceil(100/9) = 12) |

**Resolution:** `RATIFIED -> A`
**Because:** A key-presence test lets an artifact of an interrupted engagement -- a row with no completed kill -- manufacture a rate of zero, which then trips the zero-reward stop and reports a perfectly reachable target as not finite. The live store also holds a NEGATIVE rate over 100 samples, which is not evidence of anything. Author chose the positive-evidence test.
**Became:** `S-018` — A measurement is present only when positive evidence backs it

---

### W-005 · rung-progress-surplus-carryover

| | |
|---|---|
| **cell** | 4. Rung walk driver and per-rung state advancement (XP carry-over, level-up stat growth)/normal |
| **Σ dimension** | value semantics |
| **severity** | 4 |

**Distinguishing input**
```
character state = {level 10, max_hp 100, progress 0, progress_required 100}; target level 13; observations = {} ; catalogue = [bandit {level 15, hp 25, always beatable, 0 forced recoveries}]. Predicted XP/kill from the published formula is 31 at level 10, 28 at level 11, 26 at level 12 (the ratio term shifts as the character levels), so every rung needs a fractional number of kills that S-014 resolves upward.
```

| | behavior |
|---|---|
| **A** | rungs = [(rung 10, 'bandit', 4), (rung 11, 'bandit', 4), (rung 12, 'bandit', 4)], total cost = 12. A resets progress to 0 at the top of each rung: ceil(100/31)=4, ceil(100/28)=4, ceil(100/26)=4. |
| **B** | rungs = [(rung 10, 'bandit', 4), (rung 11, 'bandit', 3), (rung 12, 'bandit', 4)], total cost = 11. B carries the overshoot of the last kill into the next rung: rung 10 banks 4*31-100 = 24, so rung 11 needs only 76 (ceil(76/28)=3) and banks 8, so rung 12 needs 92 (ceil(92/26)=4). |

**Resolution:** `RATIFIED -> C` (superseding an earlier `RATIFIED -> B`)
**Because:** The author's decision stands and is unchanged: a projection that restarts every rung from zero over-prices a full climb by roughly one kill per rung, and the game does not discard a kill's XP at a level boundary. **A** is rejected for that reason. But **B** is rejected too, and the ratified answer is neither.

**The ratified behaviour is the exact quotient per rung, with no rung resolved to a whole kill:** `rungs = [(rung 10, 'bandit', 3.2258), (rung 11, 'bandit', 3.5714), (rung 12, 'bandit', 3.8462)], total cost = 11`. B reaches the same TOTAL by a different route and its per-rung figures are illegal — S-019 forbids resolving an individual rung to a whole kill, and S-014's upward resolution applies once, at the point of report, to the total alone. A harness that asserted B's `4/3/4` would be pinning a decision the spec forbids while its total happened to agree.

**"Carrying the overshoot" was the wrong description of the mechanism, and this entry used to give it.** Not-rounding and carrying a surplus coincide only when the rate is the same at both rungs, and here it is 31, 28 and 26 — three different rates, chosen precisely to make the rungs fractional. The exact quotient forms no surplus at all, so nothing is carried; what it declines to model is the crossing action's spill, which S-019 now bounds at under one action per boundary and which measured at one action across a live four-rung climb.

**The claim that this needs an implementation change was also wrong.** The implementation takes the full requirement at the top of every rung and divides exactly, which is what the ratified behaviour above requires. No change was needed and none was made.
**Became:** `S-019` — Progress carries across rungs (the heading is retained for its permanent id; the clause itself now leads with the exact-quotient mechanism, since nothing is carried)

---

### W-006 · beatability-consult-loadout-worn-vs-wearable

| | |
|---|---|
| **cell** | 6. Beatability consult (when, and with what character state)/boundary |
| **Σ dimension** | value semantics |
| **severity** | 4 |

**Distinguishing input**
```
char = {level:10, xp:0, xp_max:150, hp:130, max_hp:130, attack:20, defense:5, worn:[], carried:[iron_shield{defense:+6, min_character_level:10}]}; target_level = 13; observations = {}; catalogue = [wolf{level:1, hp:20, attack:6, defense:0}, ogre{level:12, hp:348, attack:10, defense:8}]. Both implementations advance the state per rung identically (so witness 1's decision is held fixed). Bare, the ogre is unbeatable at every rung up to level 12 (140 full HP); with the carried shield worn it is beatable at level 10. The shield's only condition, minimum character level 10, already holds.
```

| | behavior |
|---|---|
| **A** | A (predicate consulted with the loadout as worn — carried-but-unworn gear ignored): rungs=[(level 10, "wolf", 75)], total_cost = NOT FINITE. Rung 11's wolf awards 0 XP and the ogre is unbeatable, so the walk stops. |
| **B** | B (predicate consulted with the best loadout the character is already carrying and is permitted to wear, the equip counted as one executed action under S-005): rungs=[(level 10, "ogre", 9), (level 11, "ogre", 10), (level 12, "ogre", 5)], total_cost = 24. |

**Resolution:** `RATIFIED -> C`
**Because:** Neither branch as posed. The adversaries recommended consulting only WORN gear, which is the cleaner contract and would be wrong here: the gear branch projects a candidate by placing the item in INVENTORY, so an oracle that ignored carried gear would make every gear candidate project identically to the trunk -- a bug this codebase has already had and documented. Author kept the carried-gear reading and closed the hole the other way: the equip is an executed action and must be paid for. Today it is free, which lets the projection take an upgrade the executor would have to spend a cycle on.
**The DECISION stands; B's arithmetic does not.** Both halves — the predicate sees carried gear, and the equip is paid for — are exactly what S-020 fixes, and that is what this entry ratifies. But B priced the equip at ONE executed action, and the published rules give a different number: a slot that gains a piece is one ITEM MOVEMENT, a slot that swaps is TWO (the server refuses to equip into an occupied slot, `491`), and a movement costs three seconds — about a tenth of a Fight, not a whole one. B's totals also predate S-021's published-duration recovery. So a harness must assert the decision and the equip's price (one movement here, since the shield slot is empty: 3 s = 0.1 Fight), not B's literal 9/10/5.
**Became:** `S-020` — The consult sees carried gear, and the equip is charged

---

### W-007 · recovery-quantum-discrete-vs-amortised

| | |
|---|---|
| **cell** | 10. Whole-loop cost model for one kill (recovery and 'anything else the loop requires')/normal |
| **Σ dimension** | value semantics |
| **severity** | 4 |

**Distinguishing input**
```
char = {level 5, xp 0, xp_needed 300, max_hp 100}; target = 6; observations = {}; catalogue = [ogre {level 7, hp 150, dmg_taken_per_fight 51} -> 34 xp/kill, 9 kills; dire_elk {level 6, hp 100, dmg_taken_per_fight 34} -> 28 xp/kill, 11 kills]. Both beatable-from-full-HP and permitted. Ceiling applied once at the rung total in both implementations, so recovery pricing is the ONLY difference.
```

| | behavior |
|---|---|
| **A** | A amortises recovery continuously (a full-heal rest is 1 action, charged as dmg/max_hp per kill): ogre 1.51 x 9 = 13.59 -> 14; dire_elk 1.34 x 11 = 14.74 -> 15. Result: rungs = [{level 6, monster 'ogre', cost 14}], total_cost = 14. |
| **B** | B charges recovery in whole actions at its real cadence -- one rest every floor(max_hp/dmg) kills: ogre floor(100/51)=1 -> 2.0 x 9 = 18; dire_elk floor(100/34)=2 -> 1.5 x 11 = 16.5 -> 17. Result: rungs = [{level 6, monster 'dire_elk', cost 17}], total_cost = 17. |

**Resolution:** `RATIFIED -> C` (superseding an earlier `RATIFIED -> A`)
**Because:** The question was continuous against stepped, and the answer is still CONTINUOUS, for the reason first given: a continuous charge is monotone in damage, so armour that reduces damage without removing a whole recovery still improves the price, where a step on `floor(max_hp/damage)` hides that until a whole recovery disappears. Armour's only channel into this objective is damage, and a step function closes it for most of its range.

**But neither exhibited output is legal now, and the ratified WINNER has flipped.** A priced a recovery as one action charged at `damage / max_hp`; recovery is priced by its PUBLISHED duration (one second per percent of the bar restored, rounded up, floor three, cap one bar) converted at thirty seconds to the Fight. On this exhibit, with a quarter band both monsters chain a single fight: ogre restores 51% for 51 s, a share of 1.7 Fights, a loop of 2.7 actions per kill and a rate of 12.5926 XP per action; dire_elk restores 34% for 34 s, a share of 1.1333, a loop of 2.1333 and a rate of 13.125. The rung's 300 XP therefore costs **23.8235 actions on ogre and 22.8571 on dire_elk**, so a harness must assert `rungs = [{level 6, monster 'dire_elk', cost 22.8571}], total_cost = 23` — dire_elk, which is A's LOSER and B's winner at a cost neither exhibited.

That the winner moved is the finding, not an embarrassment: A's model saturated, and the published-duration model is what lets a heavier hit cost proportionally more. Recorded here so the entry cannot be read as ratifying `damage / max_hp` itself.

⚠️ **THIS EXHIBIT'S BAR OF 100 IS BLIND TO MOST OF WHAT S-021 NOW DECIDES**, and the id is permanent so the input stays as recorded. At 100 hit points one point is one percent, so the published per-second rounding is a no-op and no two adjacent damages tie; a real bar of 535 has 382 such ties. A quarter of 100 is also whole, so the guard-threshold lattice question cannot arise at any damage. Four rounds of verification found real defects that this input structurally could not have exposed. A harness built from this entry pins the continuous-versus-stepped decision and nothing finer — check the quantum, the lattice and the ties against a bar that is not a multiple of four.
**Became:** `S-021` — Recovery is priced by its published duration and contributed as a continuous share (heading retained for its permanent id; "one action" was A's model and is no longer the rule)

---

### W-008 · argmax-per-kill-rate-vs-rung-crossing-cost

| | |
|---|---|
| **cell** | 11. Fastest-monster selection (argmax on reward per unit cost) and tie-break/conflicting |
| **Σ dimension** | value semantics |
| **severity** | 4 |

**Distinguishing input**
```
character = {level: 10, xp: 0, max_xp: 100 (i.e. 100 XP still needed for L11), full HP, wisdom_bonus 1.0}; target_level = 11; observations = {} (empty); catalogue = [bandit_lizard {level 10, hp 1250, loop_cost 7 actions/kill}, blue_slime {level 10, hp 125, loop_cost 3 actions/kill}]. Both monsters are beatable (S-009) and permitted (S-010). Published formula gives bandit_lizard 70 XP/kill (rate 10.00 XP per action) and blue_slime 25 XP/kill (rate 8.33 XP per action); but because kills are integral, bandit_lizard needs ceil(100/70)=2 kills = 14 actions while blue_slime needs ceil(100/25)=4 kills = 12 actions.
```

| | behavior |
|---|---|
| **A** | rungs = [(level 11, "bandit_lizard", 14)], total_cost = 14   — argmax of reward-per-cost measured PER KILL (70/7 = 10.0 > 25/3 = 8.33) |
| **B** | rungs = [(level 11, "blue_slime", 12)], total_cost = 12   — argmax of reward-per-cost measured OVER THE RUNG (100/12 = 8.33 > 100/14 = 7.14), i.e. the monster that literally 'crosses it fastest' |

**Resolution:** `RATIFIED -> C` (superseding an earlier `RATIFIED -> A`)
**Because:** S-011's heading ('crosses it fastest') and its body ('greatest reward per unit cost') named two different criteria, and they pick different monsters. The author chose the per-kill rate — the monster in **A**, `bandit_lizard`.

**The ratified COST is 10, not A's 14, and this entry is executable so the number matters.** Both exhibited outputs are now illegal. A's 14 is `ceil(100/70) = 2` whole kills at 7 actions each, and S-019 forbids resolving an individual rung to a whole kill: the exact quotient is `100 / (70/7) = 10`. B is priced correctly for its monster but picks the wrong one — once bandit_lizard costs 10 rather than 14, it wins under BOTH of the criteria this witness set against each other (per-kill rate 10.00 vs 8.33; reward over the rung 100/10 vs 100/12). A harness must assert `rungs = [(level 11, "bandit_lizard", 10)], total_cost = 10`.

**Closed by `S-019`, not by S-022.** Phase 2c ruled this twice. S-019's exact unrounded quotient is what makes A illegal, and S-011's pre-existing argmax evaluated on that corrected cost is what makes B illegal; this pair contains no loadout change, so S-022's actual content — excluding the once-per-rung setup from the ranking denominator — is not exercised by it and could not have changed the answer.

**An earlier rationale here was also wrong** and is corrected rather than deleted: it said the choice was coupled to surplus XP carrying into the next rung, so that no reward is wasted at a boundary. No surplus is ever formed (S-019), so nothing carries and the coupling never existed. The two criteria coincide for a different reason — a rung's loop cost is its remaining requirement divided by the rate, with no fixed term and no rounding, so ranking by greatest rate and by least loop cost are the same ordering.
**Became:** `S-022` — The per-rung choice maximises reward per action, not per rung. Retained: its exclusion of the setup cost is a real decision, but it is ASSERTED and unwitnessed, and wants a pair in which a cheaper-per-action monster demands an equip that a dearer one does not.

---

### W-009 · measured-rate-unit-undeclared

| | |
|---|---|
| **cell** | 9. Measured-rate lookup and unit reconciliation (observations vs prediction)/conflicting |
| **Σ dimension** | value semantics |
| **severity** | 5 |

**Distinguishing input**
```
Same catalogue and character as above; target level 6; observations = [(wolf, 12.0)] — a bare number, since the spec never says an observation record carries a unit tag. wolf.loop_actions = 3 (S-005 whole loop).
```

| | behavior |
|---|---|
| **A** | A (reads the measured rate as XP per kill, converts the prediction to per-kill to compare): wolf = 12 xp/kill = 4.0 xp/action, loses to chicken's 6.0 → rungs = [(level 6, 'chicken', 50)], total cost = 50 |
| **B** | B (reads the measured rate as XP per executed action, converts the prediction to per-action to compare): wolf = 12 xp/action = 36 xp/kill, beats chicken → rungs = [(level 6, 'wolf', 27)], total cost = 27 |

**Resolution:** `RATIFIED -> C`
**Because:** S-008 required the two rates to agree on a unit without ever saying which unit, which is the same shape of defect S-004 exists to memorialise -- a quantity denominated in one unit and read as another. Author named the unit rather than adding a per-record unit field: enlarging the input domain for a field nothing currently produces buys robustness against a store change that has not happened, at the cost of a hole in S-002 today.
**What is ratified here is the UNIT, not the exhibit's costs.** A's 50 and B's 27 were computed under the recovery model S-021 has since replaced, so a harness must assert that a measured rate is read as XP per executed loop action — and that a prediction is divided by the loop length once, never multiplied back up — rather than either total.
**Became:** `S-023` — Rates are reconciled in XP per executed action

---
