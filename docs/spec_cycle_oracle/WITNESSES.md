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
