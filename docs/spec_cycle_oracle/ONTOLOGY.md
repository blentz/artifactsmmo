# Ontology grid

**Subjects:** 1. Oracle call contract (purity, totality, determinism), 2. Input admission and domain validation (character state, target level, catalogue, observations), 3. At-or-above-target early exit, 4. Rung walk driver and per-rung state advancement (XP carry-over, level-up stat growth), 5. Candidate monster enumeration from the catalogue, 6. Beatability consult (when, and with what character state), 7. Permission / admissibility filter ('the game and the plan admit'), 8. Predicted XP-per-kill from the published formula, 9. Measured-rate lookup and unit reconciliation (observations vs prediction), 10. Whole-loop cost model for one kill (recovery and 'anything else the loop requires'), 11. Fastest-monster selection (argmax on reward per unit cost) and tie-break, 12. Walk-stop decision (no admissible monster / zero reward), 13. Cost arithmetic and upward rounding, 14. Result assembly (rungs sequence, total cost, not-finite encoding)
**Stimuli:** normal, boundary, degenerate, conflicting, absent, stale / expiry (aged inputs, TTL, version drift), retry / duplicate / replay (same call twice, same rung twice), dependency failure (beatability predicate, catalogue, observation store), concurrent stimulus (aliased/shared arguments, two calls at once)
**Stimulus-waivers:** CONCURRENCY is waived only for the four subjects that are pure arithmetic over values already resolved inside the call (8 XP prediction, 11 selection, 13 rounding, 14 assembly) — they touch no shared handle, so "two arrive at once" has no distinct meaning beyond the whole-call cell (subject 1). It is NOT waived for subjects 2, 5, 6, 7, 9, 10, 12: the learned-observation body and the catalogue are handles the caller passes in and the (explicitly background) learning store keeps writing to; S-001 promises only that the ORACLE does not mutate its arguments, never that its arguments hold still, so a concurrent write during a multi-rung walk is a live and unaddressed stimulus. DEPENDENCY FAILURE is waived for subject 3 (the early exit fires before any dependency is consulted) and subject 13 (arithmetic on in-call values). TIME/EXPIRY is NOT waived anywhere: S-001 forbids the oracle from depending on elapsed time, which is a different statement from deciding what the oracle does with an input that is old — a measured rate recorded 400 levels ago, a catalogue from a previous game season, a character state snapshot taken before the character levelled. RETRY is genuinely and fully answered at the whole-call level by S-001, and I have marked it DEFINED per-subject on that basis rather than waived; the one place it is not answered is replay WITHIN a walk (the same rung re-entered after a level-up changed max HP), which surfaces under subject 4.

<!-- ABSENT FROM THE SPEC ENTIRELY — the domain has these and the spec never names them,
     so they have no cell at all, not even a MISSING one. Decide whether they belong:
       - THE PLAN, as an input. S-010 makes admissibility depend on what 'the plan' admits, but S-002's input domain never admits a plan, a goal, or any planner context as an argument. The oracle is therefore specified to consult something it is never given.
       - THE BEATABILITY PREDICATE, as an input. S-009 requires consulting a 'shared' predicate; S-002 does not list it among the arguments and S-001 forbids dependence on 'any state not passed as an argument'. Two of the spec's own clauses cannot both hold as written.
       - MAPS, TILES, TRAVEL AND DISTANCE. Monsters exist somewhere. Moving to them is an executed planner action, which S-004 says is the unit and S-005 says the rung cost must count. The spec never names location, so a monster 40 tiles away and one underfoot price identically.
       - DROPS, LOOT AND GOLD. Every kill yields items. They fill inventory (the domain facts even grant +2 slots per level, implying the author knew), and emptying inventory costs executed planner actions that S-005's 'anything else the loop requires' would sweep in. Never named.
       - INVENTORY CAPACITY AND BANK TRIPS. The +2 slots/level domain fact is stated and then used by no clause. Whether a full inventory interrupts the kill loop is unaddressed.
       - THE RECOVERY MECHANISM. S-005 counts 'recovery the character is forced into' but never names what recovery IS — resting, eating, drinking a potion — nor how many actions it costs, nor that consumables are finite and deplete.
       - CONSUMABLES / POTIONS / FOOD as a depleting resource inside the projected loop.
       - WISDOM, AND EVERY OTHER FORMULA INPUT. The published XP formula takes wisdom_bonus and monster_multiplier. S-002's list of what the character state carries does not include wisdom, and the catalogue is described only as 'monsters and their attributes'. S-007 orders the oracle to use a formula whose operands the input domain does not guarantee.
       - THE XP CURVE FOR FUTURE LEVELS. S-002 admits 'the amount of progress a level requires' as ONE field — a scalar for the current level — while the walk crosses many levels. The residual admits the curve is undecided, but the missing entity is sharper than that: there is no per-level requirement TABLE in the input domain at all, so a non-constant curve is not merely undecided, it is unrepresentable.
       - THE LEVEL-50 CAP as anything a clause acts on. It appears in domain facts and vanishes. A target of 50 from level 49, or a walk that would cross 50, is governed by nothing.
       - COMBAT VARIANCE. Beatability is a boolean but kills-per-level is an expectation. Crits, blocks and the 100-turn limit make actual kill counts a distribution; no clause says the reported cost is a mean, a worst case, or anything.
       - DEATH AND RESPAWN AS A COST. The residual asks whether a projected loss should be priced, but the entity itself — a death event, its action cost, its HP/XP consequence — is never named even to be excluded.
       - EQUIPMENT CHANGES DURING THE WALK. S-002 admits 'what it is carrying and wearing' and the domain facts note equipment gates on character level, so the walk crosses levels that unlock gear. No clause says whether the projection may re-equip, or must freeze the loadout it was handed.
       - THE REASON THE WALK STOPPED. S-012 and S-013 stop for different reasons and report the same shape. S-001 forbids a sentinel meaning 'could not compute'. There is no diagnostic channel, so a caller cannot distinguish 'nothing beatable' from 'everything grey' from 'no monsters in the catalogue'.
       - MONSTER AVAILABILITY OVER TIME — respawn, event/transient monsters, other players competing for spawns. The residual defers catalogue completeness; the entity 'a monster that exists but is not there right now' is never named.
       - THE OBSERVATION RECORD ITSELF. S-008 says observations 'contain a measured rate for a monster' — a rate of what, per what, keyed how, with what sample count or confidence, is never given a shape. It is the one input the spec both leans on and refuses to describe.
       - MULTIPLE CHARACTERS. The oracle is written as if one character exists; a shared bank and a shared observation store across characters are the obvious way this becomes wrong.
-->

## Grid

| Subject | Stimulus | Verdict | Clauses | Justification |
|---|---|---|---|---|
| 1. Oracle call contract (purity, totality, determinism) | normal | DEFINED | S-001, S-003 |  |
| 1. Oracle call contract (purity, totality, determinism) | boundary | THIN | S-001, S-002 |  |
| 1. Oracle call contract (purity, totality, determinism) | degenerate | THIN | S-001 |  |
| 1. Oracle call contract (purity, totality, determinism) | conflicting | MISSING |  |  |
| 1. Oracle call contract (purity, totality, determinism) | absent | MISSING |  |  |
| 1. Oracle call contract (purity, totality, determinism) | stale / expiry (aged inputs, TTL, version drift) | DEFINED | S-001 |  |
| 1. Oracle call contract (purity, totality, determinism) | retry / duplicate / replay (same call twice, same rung twice) | DEFINED | S-001 |  |
| 1. Oracle call contract (purity, totality, determinism) | dependency failure (beatability predicate, catalogue, observation store) | DEFINED | S-002 | a dependency outside its own contract is malformed input and outside the admitted domain; reading a failed consult as 'no' would turn a crash into an indistinguishable wall |
| 1. Oracle call contract (purity, totality, determinism) | concurrent stimulus (aliased/shared arguments, two calls at once) | THIN | S-001 |  |
| 2. Input admission and domain validation (character state, target level, catalogue, observations) | normal | DEFINED | S-002 |  |
| 2. Input admission and domain validation (character state, target level, catalogue, observations) | boundary | THIN | S-002, S-006 |  |
| 2. Input admission and domain validation (character state, target level, catalogue, observations) | degenerate | MISSING |  |  |
| 2. Input admission and domain validation (character state, target level, catalogue, observations) | conflicting | MISSING |  |  |
| 2. Input admission and domain validation (character state, target level, catalogue, observations) | absent | MISSING |  |  |
| 2. Input admission and domain validation (character state, target level, catalogue, observations) | stale / expiry (aged inputs, TTL, version drift) | DEFINED | S-001 | purity: no dependence on elapsed time, so the oracle has no freshness notion; age is a property of what the caller hands over |
| 2. Input admission and domain validation (character state, target level, catalogue, observations) | retry / duplicate / replay (same call twice, same rung twice) | DEFINED | S-001 |  |
| 2. Input admission and domain validation (character state, target level, catalogue, observations) | dependency failure (beatability predicate, catalogue, observation store) | DEFINED | S-002 | a dependency outside its own contract is malformed input and outside the admitted domain; reading a failed consult as 'no' would turn a crash into an indistinguishable wall |
| 2. Input admission and domain validation (character state, target level, catalogue, observations) | concurrent stimulus (aliased/shared arguments, two calls at once) | DEFINED | S-001 | purity: no shared state and no argument is mutated, so concurrent calls and aliased arguments cannot interfere |
| 3. At-or-above-target early exit | normal | DEFINED | S-006 |  |
| 3. At-or-above-target early exit | boundary | DEFINED | S-006 |  |
| 3. At-or-above-target early exit | degenerate | THIN | S-006, S-003 |  |
| 3. At-or-above-target early exit | conflicting | MISSING |  |  |
| 3. At-or-above-target early exit | absent | MISSING |  |  |
| 3. At-or-above-target early exit | stale / expiry (aged inputs, TTL, version drift) | DEFINED | S-001 | purity: no dependence on elapsed time, so the oracle has no freshness notion; age is a property of what the caller hands over |
| 3. At-or-above-target early exit | retry / duplicate / replay (same call twice, same rung twice) | DEFINED | S-001, S-006 |  |
| 3. At-or-above-target early exit | dependency failure (beatability predicate, catalogue, observation store) | IGNORE |  | S-006's answer is total in the character state and target alone. The exit fires before any catalogue read, observation lookup or beatability consult, so there is no dependency in scope that could fail. Waived on the record rather than omitted. |
| 3. At-or-above-target early exit | concurrent stimulus (aliased/shared arguments, two calls at once) | DEFINED | S-001 | purity: no shared state and no argument is mutated, so concurrent calls and aliased arguments cannot interfere |
| 4. Rung walk driver and per-rung state advancement (XP carry-over, level-up stat growth) | normal | DEFINED | S-003, S-012, S-019 |  |
| 4. Rung walk driver and per-rung state advancement (XP carry-over, level-up stat growth) | boundary | MISSING |  |  |
| 4. Rung walk driver and per-rung state advancement (XP carry-over, level-up stat growth) | degenerate | DEFINED | S-003, S-015 |  |
| 4. Rung walk driver and per-rung state advancement (XP carry-over, level-up stat growth) | conflicting | MISSING |  |  |
| 4. Rung walk driver and per-rung state advancement (XP carry-over, level-up stat growth) | absent | MISSING |  |  |
| 4. Rung walk driver and per-rung state advancement (XP carry-over, level-up stat growth) | stale / expiry (aged inputs, TTL, version drift) | DEFINED | S-001 | purity: no dependence on elapsed time, so the oracle has no freshness notion; age is a property of what the caller hands over |
| 4. Rung walk driver and per-rung state advancement (XP carry-over, level-up stat growth) | retry / duplicate / replay (same call twice, same rung twice) | DEFINED | S-001 | determinism: the same call returns the same answer, so there is nothing to de-duplicate or reconcile |
| 4. Rung walk driver and per-rung state advancement (XP carry-over, level-up stat growth) | dependency failure (beatability predicate, catalogue, observation store) | DEFINED | S-002 | a dependency outside its own contract is malformed input and outside the admitted domain; reading a failed consult as 'no' would turn a crash into an indistinguishable wall |
| 4. Rung walk driver and per-rung state advancement (XP carry-over, level-up stat growth) | concurrent stimulus (aliased/shared arguments, two calls at once) | DEFINED | S-001 | purity: no shared state and no argument is mutated, so concurrent calls and aliased arguments cannot interfere |
| 5. Candidate monster enumeration from the catalogue | normal | THIN | S-002, S-011 |  |
| 5. Candidate monster enumeration from the catalogue | boundary | THIN | S-011 |  |
| 5. Candidate monster enumeration from the catalogue | degenerate | DEFINED | S-012 |  |
| 5. Candidate monster enumeration from the catalogue | conflicting | MISSING |  |  |
| 5. Candidate monster enumeration from the catalogue | absent | MISSING |  |  |
| 5. Candidate monster enumeration from the catalogue | stale / expiry (aged inputs, TTL, version drift) | THIN | S-002 |  |
| 5. Candidate monster enumeration from the catalogue | retry / duplicate / replay (same call twice, same rung twice) | DEFINED | S-001 |  |
| 5. Candidate monster enumeration from the catalogue | dependency failure (beatability predicate, catalogue, observation store) | DEFINED | S-002 | a dependency outside its own contract is malformed input and outside the admitted domain; reading a failed consult as 'no' would turn a crash into an indistinguishable wall |
| 5. Candidate monster enumeration from the catalogue | concurrent stimulus (aliased/shared arguments, two calls at once) | DEFINED | S-001 | purity: no shared state and no argument is mutated, so concurrent calls and aliased arguments cannot interfere |
| 6. Beatability consult (when, and with what character state) | normal | DEFINED | S-009 |  |
| 6. Beatability consult (when, and with what character state) | boundary | DEFINED | S-009, S-020 |  |
| 6. Beatability consult (when, and with what character state) | degenerate | THIN | S-009 |  |
| 6. Beatability consult (when, and with what character state) | conflicting | MISSING |  |  |
| 6. Beatability consult (when, and with what character state) | absent | MISSING |  |  |
| 6. Beatability consult (when, and with what character state) | stale / expiry (aged inputs, TTL, version drift) | DEFINED | S-001 | purity: no dependence on elapsed time, so the oracle has no freshness notion; age is a property of what the caller hands over |
| 6. Beatability consult (when, and with what character state) | retry / duplicate / replay (same call twice, same rung twice) | THIN | S-001, S-009 |  |
| 6. Beatability consult (when, and with what character state) | dependency failure (beatability predicate, catalogue, observation store) | DEFINED | S-002 | a dependency outside its own contract is malformed input and outside the admitted domain; reading a failed consult as 'no' would turn a crash into an indistinguishable wall |
| 6. Beatability consult (when, and with what character state) | concurrent stimulus (aliased/shared arguments, two calls at once) | DEFINED | S-001 | purity: no shared state and no argument is mutated, so concurrent calls and aliased arguments cannot interfere |
| 7. Permission / admissibility filter ('the game and the plan admit') | normal | THIN | S-010 |  |
| 7. Permission / admissibility filter ('the game and the plan admit') | boundary | THIN | S-010 |  |
| 7. Permission / admissibility filter ('the game and the plan admit') | degenerate | DEFINED | S-012, S-010 |  |
| 7. Permission / admissibility filter ('the game and the plan admit') | conflicting | MISSING |  |  |
| 7. Permission / admissibility filter ('the game and the plan admit') | absent | MISSING |  |  |
| 7. Permission / admissibility filter ('the game and the plan admit') | stale / expiry (aged inputs, TTL, version drift) | DEFINED | S-001 | purity: no dependence on elapsed time, so the oracle has no freshness notion; age is a property of what the caller hands over |
| 7. Permission / admissibility filter ('the game and the plan admit') | retry / duplicate / replay (same call twice, same rung twice) | DEFINED | S-001 |  |
| 7. Permission / admissibility filter ('the game and the plan admit') | dependency failure (beatability predicate, catalogue, observation store) | DEFINED | S-002 | a dependency outside its own contract is malformed input and outside the admitted domain; reading a failed consult as 'no' would turn a crash into an indistinguishable wall |
| 7. Permission / admissibility filter ('the game and the plan admit') | concurrent stimulus (aliased/shared arguments, two calls at once) | DEFINED | S-001 | purity: no shared state and no argument is mutated, so concurrent calls and aliased arguments cannot interfere |
| 8. Predicted XP-per-kill from the published formula | normal | DEFINED | S-007 |  |
| 8. Predicted XP-per-kill from the published formula | boundary | THIN | S-007 |  |
| 8. Predicted XP-per-kill from the published formula | degenerate | MISSING |  |  |
| 8. Predicted XP-per-kill from the published formula | conflicting | MISSING |  |  |
| 8. Predicted XP-per-kill from the published formula | absent | MISSING |  |  |
| 8. Predicted XP-per-kill from the published formula | stale / expiry (aged inputs, TTL, version drift) | DEFINED | S-001 | purity: no dependence on elapsed time, so the oracle has no freshness notion; age is a property of what the caller hands over |
| 8. Predicted XP-per-kill from the published formula | retry / duplicate / replay (same call twice, same rung twice) | DEFINED | S-001, S-007 |  |
| 8. Predicted XP-per-kill from the published formula | dependency failure (beatability predicate, catalogue, observation store) | DEFINED | S-002 | a dependency outside its own contract is malformed input and outside the admitted domain; reading a failed consult as 'no' would turn a crash into an indistinguishable wall |
| 8. Predicted XP-per-kill from the published formula | concurrent stimulus (aliased/shared arguments, two calls at once) | IGNORE |  | Waived per stimulus_waivers: the prediction is arithmetic over scalars already read out of the catalogue and character state within this call. It holds no handle and publishes no state, so 'two arrive at once' collapses into the whole-call cell (subject 1, concurrent), which is recorded THIN there rather than swallowed here. |
| 9. Measured-rate lookup and unit reconciliation (observations vs prediction) | normal | DEFINED | S-008, S-017 |  |
| 9. Measured-rate lookup and unit reconciliation (observations vs prediction) | boundary | MISSING |  |  |
| 9. Measured-rate lookup and unit reconciliation (observations vs prediction) | degenerate | MISSING |  |  |
| 9. Measured-rate lookup and unit reconciliation (observations vs prediction) | conflicting | DEFINED | S-008, S-023 |  |
| 9. Measured-rate lookup and unit reconciliation (observations vs prediction) | absent | DEFINED | S-008, S-007, S-018 |  |
| 9. Measured-rate lookup and unit reconciliation (observations vs prediction) | stale / expiry (aged inputs, TTL, version drift) | DEFINED | S-001 | purity: no dependence on elapsed time, so the oracle has no freshness notion; age is a property of what the caller hands over |
| 9. Measured-rate lookup and unit reconciliation (observations vs prediction) | retry / duplicate / replay (same call twice, same rung twice) | DEFINED | S-001 |  |
| 9. Measured-rate lookup and unit reconciliation (observations vs prediction) | dependency failure (beatability predicate, catalogue, observation store) | DEFINED | S-002 | a dependency outside its own contract is malformed input and outside the admitted domain; reading a failed consult as 'no' would turn a crash into an indistinguishable wall |
| 9. Measured-rate lookup and unit reconciliation (observations vs prediction) | concurrent stimulus (aliased/shared arguments, two calls at once) | DEFINED | S-001 | purity: no shared state and no argument is mutated, so concurrent calls and aliased arguments cannot interfere |
| 10. Whole-loop cost model for one kill (recovery and 'anything else the loop requires') | normal | DEFINED | S-005, S-004, S-021 |  |
| 10. Whole-loop cost model for one kill (recovery and 'anything else the loop requires') | boundary | MISSING |  |  |
| 10. Whole-loop cost model for one kill (recovery and 'anything else the loop requires') | degenerate | THIN | S-005 |  |
| 10. Whole-loop cost model for one kill (recovery and 'anything else the loop requires') | conflicting | MISSING |  |  |
| 10. Whole-loop cost model for one kill (recovery and 'anything else the loop requires') | absent | MISSING |  |  |
| 10. Whole-loop cost model for one kill (recovery and 'anything else the loop requires') | stale / expiry (aged inputs, TTL, version drift) | DEFINED | S-001 | purity: no dependence on elapsed time, so the oracle has no freshness notion; age is a property of what the caller hands over |
| 10. Whole-loop cost model for one kill (recovery and 'anything else the loop requires') | retry / duplicate / replay (same call twice, same rung twice) | DEFINED | S-001 |  |
| 10. Whole-loop cost model for one kill (recovery and 'anything else the loop requires') | dependency failure (beatability predicate, catalogue, observation store) | DEFINED | S-002 | a dependency outside its own contract is malformed input and outside the admitted domain; reading a failed consult as 'no' would turn a crash into an indistinguishable wall |
| 10. Whole-loop cost model for one kill (recovery and 'anything else the loop requires') | concurrent stimulus (aliased/shared arguments, two calls at once) | DEFINED | S-001 | purity: no shared state and no argument is mutated, so concurrent calls and aliased arguments cannot interfere |
| 11. Fastest-monster selection (argmax on reward per unit cost) and tie-break | normal | DEFINED | S-011, S-004, S-005 |  |
| 11. Fastest-monster selection (argmax on reward per unit cost) and tie-break | boundary | THIN | S-011 |  |
| 11. Fastest-monster selection (argmax on reward per unit cost) and tie-break | degenerate | DEFINED | S-011 |  |
| 11. Fastest-monster selection (argmax on reward per unit cost) and tie-break | conflicting | DEFINED | S-011, S-001, S-022 |  |
| 11. Fastest-monster selection (argmax on reward per unit cost) and tie-break | absent | DEFINED | S-012 |  |
| 11. Fastest-monster selection (argmax on reward per unit cost) and tie-break | stale / expiry (aged inputs, TTL, version drift) | DEFINED | S-001 | purity: no dependence on elapsed time, so the oracle has no freshness notion; age is a property of what the caller hands over |
| 11. Fastest-monster selection (argmax on reward per unit cost) and tie-break | retry / duplicate / replay (same call twice, same rung twice) | DEFINED | S-001, S-011 |  |
| 11. Fastest-monster selection (argmax on reward per unit cost) and tie-break | dependency failure (beatability predicate, catalogue, observation store) | DEFINED | S-002 | a dependency outside its own contract is malformed input and outside the admitted domain; reading a failed consult as 'no' would turn a crash into an indistinguishable wall |
| 11. Fastest-monster selection (argmax on reward per unit cost) and tie-break | concurrent stimulus (aliased/shared arguments, two calls at once) | IGNORE |  | Waived per stimulus_waivers: selection is a fold over the candidate list already materialised inside this call. Any concurrency exposure lives in enumeration (subject 5) and the observation lookup (subject 9), where it is recorded MISSING, not here. |
| 12. Walk-stop decision (no admissible monster / zero reward) | normal | DEFINED | S-012, S-013 |  |
| 12. Walk-stop decision (no admissible monster / zero reward) | boundary | THIN | S-013 |  |
| 12. Walk-stop decision (no admissible monster / zero reward) | degenerate | DEFINED | S-012, S-006 |  |
| 12. Walk-stop decision (no admissible monster / zero reward) | conflicting | DEFINED | S-013, S-011, S-012, S-016 |  |
| 12. Walk-stop decision (no admissible monster / zero reward) | absent | MISSING |  |  |
| 12. Walk-stop decision (no admissible monster / zero reward) | stale / expiry (aged inputs, TTL, version drift) | DEFINED | S-001 | purity: no dependence on elapsed time, so the oracle has no freshness notion; age is a property of what the caller hands over |
| 12. Walk-stop decision (no admissible monster / zero reward) | retry / duplicate / replay (same call twice, same rung twice) | DEFINED | S-001 |  |
| 12. Walk-stop decision (no admissible monster / zero reward) | dependency failure (beatability predicate, catalogue, observation store) | DEFINED | S-002 | a dependency outside its own contract is malformed input and outside the admitted domain; reading a failed consult as 'no' would turn a crash into an indistinguishable wall |
| 12. Walk-stop decision (no admissible monster / zero reward) | concurrent stimulus (aliased/shared arguments, two calls at once) | DEFINED | S-001 | purity: no shared state and no argument is mutated, so concurrent calls and aliased arguments cannot interfere |
| 13. Cost arithmetic and upward rounding | normal | DEFINED | S-014, S-004 |  |
| 13. Cost arithmetic and upward rounding | boundary | THIN | S-014 |  |
| 13. Cost arithmetic and upward rounding | degenerate | DEFINED | S-013 |  |
| 13. Cost arithmetic and upward rounding | conflicting | THIN | S-014, S-003 |  |
| 13. Cost arithmetic and upward rounding | absent | MISSING |  |  |
| 13. Cost arithmetic and upward rounding | stale / expiry (aged inputs, TTL, version drift) | DEFINED | S-001 | purity: no dependence on elapsed time, so the oracle has no freshness notion; age is a property of what the caller hands over |
| 13. Cost arithmetic and upward rounding | retry / duplicate / replay (same call twice, same rung twice) | DEFINED | S-001 |  |
| 13. Cost arithmetic and upward rounding | dependency failure (beatability predicate, catalogue, observation store) | IGNORE |  | Waived per stimulus_waivers: rounding consumes only the rate and XP-need already computed in-call. It calls nothing that can be down. The failure modes that reach it (a zero rate, a not-finite rate) are priced as degenerate and conflicting in this row, not as dependency failures. |
| 13. Cost arithmetic and upward rounding | concurrent stimulus (aliased/shared arguments, two calls at once) | IGNORE |  | Waived per stimulus_waivers: pure integer/rational arithmetic on call-local values, no shared handle. |
| 14. Result assembly (rungs sequence, total cost, not-finite encoding) | normal | DEFINED | S-003, S-014 |  |
| 14. Result assembly (rungs sequence, total cost, not-finite encoding) | boundary | THIN | S-012, S-001, S-003 |  |
| 14. Result assembly (rungs sequence, total cost, not-finite encoding) | degenerate | DEFINED | S-006, S-012 |  |
| 14. Result assembly (rungs sequence, total cost, not-finite encoding) | conflicting | THIN | S-003, S-012, S-014 |  |
| 14. Result assembly (rungs sequence, total cost, not-finite encoding) | absent | MISSING |  |  |
| 14. Result assembly (rungs sequence, total cost, not-finite encoding) | stale / expiry (aged inputs, TTL, version drift) | DEFINED | S-001 | purity: no dependence on elapsed time, so the oracle has no freshness notion; age is a property of what the caller hands over |
| 14. Result assembly (rungs sequence, total cost, not-finite encoding) | retry / duplicate / replay (same call twice, same rung twice) | DEFINED | S-001, S-003 |  |
| 14. Result assembly (rungs sequence, total cost, not-finite encoding) | dependency failure (beatability predicate, catalogue, observation store) | DEFINED | S-002 | a dependency outside its own contract is malformed input and outside the admitted domain; reading a failed consult as 'no' would turn a crash into an indistinguishable wall |
| 14. Result assembly (rungs sequence, total cost, not-finite encoding) | concurrent stimulus (aliased/shared arguments, two calls at once) | IGNORE |  | Waived per stimulus_waivers: assembly packages call-local values into the returned structure. Whether the returned structure is itself safe to share is the caller's contract and is covered by the whole-call cell (subject 1, concurrent). |
