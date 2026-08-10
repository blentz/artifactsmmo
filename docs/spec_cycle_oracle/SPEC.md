# Specification — the cycle oracle

**Observation alphabet:** see `OBSERVATION.md`
**Toolchain:** Python 3.13 + mypy strict + Lean 4 mechanical extraction + Hypothesis differential + mutation gate + pytest @100%
**Agent class:** Claude Opus 5 (spec-forge adversaries and judges)

**Artifact under test:** ONE pure function — the **cycle oracle**. Given a
character state, a target character level, a body of learned observations, and the
game's static catalogue, it returns *how far up the level ladder the character can
climb* and *how many executed planner actions that costs*.

**Explicitly NOT under test.** The following are BACKGROUND. They are named here so
that no clause is written about them, and **no source file, module or implementation
of any of them may be consulted while reading this spec.** This document is the
entire subject matter; what any implementation happens to do is not evidence about
what this spec should say.

- **The progression choice core** that ranks candidates using this oracle's output.
  It is separately specified (`docs/spec_unified_objective/SPEC.md`) and consumes
  these results as inputs. How it bands, orders or tie-breaks them is its concern.
- **The acquisition-cost pricer** that says what a candidate costs to obtain. It is
  a sibling producer; this oracle never calls it and is never told its answer.
- **The learning store's collection machinery** — how observations are recorded,
  windowed, or aged. This oracle *reads* observations; it does not produce them.
- **The beatability predicate itself.** Whether a given character state can defeat a
  given monster is computed elsewhere and shared with the executor. Clauses below
  constrain *when and with what arguments* the oracle consults it, never *how it
  decides*.
- The planner, the goal layer, the arbiter, and every consumer of the projection.
- Which skill to grind, and every non-combat progression concern.

---

## Domain facts

Published rules of the game being modelled, taken from
`https://docs.artifactsmmo.com/concepts/stats_and_fights/`. These are **inputs to
the specification, not clauses** — the oracle does not get to choose them.

- The maximum character level is **50**.
- XP awarded for a kill is
  `Round(((monster_level / player_level) × 20 + monster_hp × 0.04) × level_penalty × monster_multiplier × wisdom_bonus)`.
- The level penalty is a step function of the gap between character and monster: at
  or below the monster's level, **100%**; five or more levels above it, **70%**; ten
  or more levels above it, **0%** — the kill awards nothing.
- Each level gained grants the character **+5 maximum HP** and **+2 inventory
  slots**.
- A fight lasts at most **100 turns**; a character that has not won by then loses.
- Equipment carries conditions that must hold for it to be worn, including minimum
  character level.

---

### S-001 · The oracle is a pure total function

Given identical arguments the oracle returns identical results, on every call, with
no dependence on call order, elapsed time, or any state not passed as an argument.
It performs no I/O and mutates none of its arguments. It returns for every input
admitted by S-002 — it does not raise, loop forever, or return a sentinel meaning
"could not compute".

### S-002 · Input domain

The oracle receives a **character state**, a **target level**, a body of **learned
observations**, and the **static catalogue** of monsters and their attributes.

The character state carries at least: the character's current level, its current
progress toward the next level, the amount of progress a level requires, its
current and maximum hit points, its combat attributes, and what it is carrying and
wearing.

The target level is a character level in the game's legal range.

### S-003 · Output shape

The oracle returns, for the state and target it was given:

- the **rungs crossed** — an ordered sequence, one entry per level the walk
  actually advanced through, each naming the monster chosen for that rung and the
  cost attributed to it; and
- a **total cost**, the sum of those rungs' costs.

The highest level the walk reached is recoverable from the rungs alone. No second,
independently-computed encoding of reachability is produced, so there is nothing
that could disagree with the first.

### S-004 · The unit is executed planner actions

Every cost this oracle reports is denominated in **executed planner actions**, and
the unit of that denomination is **one Fight action**. An action whose duration is
that of a Fight contributes one; an action that occupies the character for `k`
times as long contributes `k`. The reported cost is therefore a count in
fight-equivalents, never a duration, and no cost may be **reported** in seconds or
compared against a quantity that is.

Actions are taken to be uniform, and therefore to contribute exactly one, unless
the game publishes a rule making a particular action's duration vary with its
arguments. Where it does, that action is converted by its published duration
divided by a Fight's, and the conversion constant is declared once (S-021).

This clause is load-bearing rather than pedantic, in both directions, and each
direction has been paid for. Reporting a duration under the name of a count made
every consumer wrong by roughly the mean cooldown. Refusing the conversion where
the game itself makes an action non-uniform is the same error mirrored: it prices
a hundred-second action and a three-second action identically, and it did so on
the one axis by which defensive equipment can pay.

### S-005 · The cost of a rung counts the whole combat loop

The cost attributed to a rung is the total fight-equivalent contribution (S-004) of
every action the character must execute to cross it, not only the attacking ones.
Recovery the character is forced into by the damage it takes counts; so does
anything else the loop requires.

The loop is **chained, not per-kill**. The character fights while its hit points
remain AT OR ABOVE the recovery guard's threshold and recovers once when they fall
below it — hit points sitting exactly on the threshold do not force a recovery, and
S-021 explains why that boundary carries the whole cost's monotonicity — so
recovery is executed once per chain of fights rather than once per fight. The
number of fights in a chain is determined by the guard's threshold and the damage
per fight, and the chain includes the fight that carries the character across the
threshold — the guard is consulted before a fight, so that fight is already
committed.

A rung requires a whole number of executions of each action, but a rung's kill
count is not generally a whole multiple of a chain. The clause therefore constrains
the **total**, not each summand: the rung's cost is the sum over its kills of the
per-kill contribution, where recovery's per-kill contribution is one chain's
recovery cost divided by the fights in that chain. No summand is rounded. What crosses a
rung boundary is NOT a residue that the next rung redeems: S-019 meets each rung's
requirement exactly, in fractional actions, so no residue is ever formed. The total
is therefore what the character executes to within the boundary approximation
S-019 states and bounds, and no individual charge is an integer.

A monster that forces recovery after every kill is more expensive per kill than one
that can be fought consecutively, and the reported cost must distinguish them; so
must two monsters that both force recovery after every kill but leave the character
at different depths, **except where the published duration charges those depths the
same**. Recovery is billed in whole seconds (S-021), so two depths inside one second
of each other genuinely cost the same and the oracle must not invent a difference
the server does not charge — at a two-hundred-point bar, adjacent whole damages
price identically across most of the chain-of-one range. What this paragraph forbids
is a cost that stops responding to damage ALTOGETHER, which is what a fixed
per-recovery charge would do; it does not require strict separation at a resolution
finer than the game bills.

### S-006 · Already at or above target costs nothing

If the character's current level is at or above the target, the oracle reports zero
rungs crossed and zero total cost. This is a genuine answer, not a refusal: there is
nothing left to do.

### S-007 · XP per kill comes from the published formula

Where the oracle must predict the XP a kill awards, it computes it from the game's
published formula over the catalogue's attributes for that monster. It does not
guess, does not use a constant, and does not substitute a value not derived from
game data.

### S-008 · Learned observations supersede prediction

Where the observations contain a measured rate for a monster, the oracle **uses**
that measured rate in place of the predicted one. A measured rate and a predicted
one must be in the same unit before either is used, and the oracle never compares
one against the other across units.

**THE ORIGINAL SAID "MAY", AND THAT WORD WAS THIS CLAUSE'S DEFECT.** W-002 exhibited
two oracles that both satisfied it and never agree — one always consults a
measurement, one never does — ranking the same rung's candidates differently and
sending the bot to different monsters. The author ratified the requirement reading:
evidence beats the model where evidence exists. The permission is replaced here
rather than being overridden from elsewhere, because a clause cannot concede on
another's behalf: for two rounds the mandate lived in a neighbouring clause while
this one still read "may", and an implementation that declined the permission broke
no letter of the text it was actually reading.

What counts as a measurement being present is S-018's, and what value it has once
used is S-017's. This clause decides only that a present one is not declined.

Where no measurement exists, S-007's prediction stands. The absence of a
measurement is not an error and does not stop the walk.

### S-009 · A rung is crossed only by a monster the character can beat

The monster chosen for a rung must be one the character can actually defeat. That
verdict is taken from the shared beatability predicate (background, above), so that
the projection and the executor never disagree about which monsters are available.

Beatability is judged **from full hit points**. The justification is the recovery
guard's threshold, not an assumption that recovery precedes every fight: under the
chained loop of S-005 the character enters most fights already damaged, so
"recovery precedes a fight" is false as stated and must not be relied on.

What is true is that the guard bounds how damaged. The character never begins a
fight with less than the guarded fraction of its hit points, so a full-hit-point
verdict is wrong by at most the unguarded remainder — a bounded optimism, taken
deliberately, in exchange for a verdict that does not depend on where in a chain
the fight falls. A verdict that did so depend would make beatability a function of
the projection's own bookkeeping rather than of the character and the monster, and
the executor, which consults the same predicate, has no such bookkeeping to agree
with.

### S-010 · A rung is crossed only by a monster the character is permitted to fight

Independently of whether it can win, the monster chosen for a rung must be one the
game and the plan admit at that rung. A monster the character would not be allowed
to engage is not a candidate, whatever its rewards.

### S-011 · The monster chosen for a rung is the one that crosses it fastest

Among the monsters admitted by S-009 and S-010 at a rung, the oracle picks the one
with the greatest reward per unit cost, in the unit S-004 fixes and over the whole
loop S-005 describes. It does not pick by headline reward, by monster level, or by
name.

Where two monsters are exactly equal the choice is unconstrained, but it must be
deterministic (S-001) and must not depend on how the monsters happen to be named.

### S-012 · A rung with no admissible monster stops the walk

If at some rung no monster satisfies S-009 and S-010, the walk stops there. The
oracle reports the rungs it did cross, and reports the total cost as **not finite**
— the target was not reached and no number of actions is claimed to reach it.

The rungs already crossed are still reported. How far the walk got is information
the caller needs even when it did not finish.

### S-013 · A rung whose fastest monster earns nothing stops the walk

The published level penalty zeroes the reward for a kill ten or more levels beneath
the character. A rung at which every admissible monster awards nothing is not
crossable by fighting, and the walk stops there under S-012's reporting rule rather
than dividing by a zero rate or reporting an unbounded cost as though it were a
number.

### S-014 · The reported cost is a count, and rounds against the character

Cost is reported as a whole number of actions. Where an intermediate figure is
fractional, it is resolved **upward**: a partial action is still an action the
character has to spend, and an objective that rounded down would systematically
under-price every path it projects.

**THE RESOLUTION HAPPENS AT THE POINT OF REPORT, ONCE, AND ON THE TOTAL.** It is
not a property of the value the oracle carries. The oracle's total is EXACTLY the
sum of its rungs' costs (S-003), each an exact quotient (S-019); the whole-number
resolution is applied to that sum when it is presented, and never to a rung. So
S-003's identity holds on the values the oracle returns — a consumer that re-adds
the rungs gets the total back, not a different number — and a reader who compares
a REPORTED total against the rungs it was reported alongside should expect it to
be no smaller, by less than one action.

Stating this was forced: rounding described as if it were stored makes "the total
is the sum of the rungs" false for every walk whose quotients do not sum to a
whole number, which is nearly all of them, and the two clauses then prescribe
different observable values on the same input.

---

## RESIDUALS

Recorded as undecided. Each is a place this document is deliberately silent, and
none may be treated as settled by any implementation.

- **The per-level XP curve.** S-002 admits "the amount of progress a level
  requires" as a single field of the character state. Whether every level in the
  game requires the same amount, and what the oracle should do if it does not, is
  not decided here. The game's API exposes the current level's requirement and this
  document does not claim it is constant.
- **Non-combat routes up the ladder.** Every clause above describes crossing a rung
  by fighting. Whether a rung could be crossed another way, and whether the oracle
  should consider it, is out of scope for this pass — but it is undecided, not
  decided in the negative.
- **The monster catalogue's completeness.** Whether monsters that exist only
  transiently are in the catalogue the oracle is handed is the catalogue's concern,
  not this oracle's.
- **Deaths.** S-005 counts forced recovery. Whether a projected loss (S-009 admits
  only winnable fights, but the published rules make losses possible) should be
  priced is not decided.

### S-015 · The walk carries a projected character state that grows as it climbs  [witness: W-001]

The oracle carries a projected character state through the walk. On crossing a rung it increments the level AND applies the growth the published rules grant for that level, before the next rung's admissibility, beatability and reward are evaluated.

Equipment conditioned on a minimum character level and satisfied by the newly reached level is available to the projection from that rung onward; the loadout is re-evaluated rather than frozen at the one the oracle was handed.

This clause is about the state the oracle CONSTRUCTS for itself between rungs. It does not enlarge the input domain (S-002) and does not change how the beatability predicate decides.

The projected state's OWN attributes are given by a closed formula and by nothing else. At a rung of level `k`, reached from a handed state of level `L0`, the projected maximum hit points are exactly `handed_maximum + G × (k − L0)`, where `G` is the published per-level grant, and likewise for every other published per-level grant. Current hit points equal that projected maximum (S-009 judges from full).

**Gear never enters that formula, in EITHER direction.** A piece the re-evaluated loadout adds does not raise the projected maximum, and — this is the harder half — a piece the re-evaluated loadout DISPLACES does not lower it either. The formula's only inputs are the handed total and the number of levels gained.

That is a real and accepted imprecision, stated rather than hidden: after a rung swaps a worn helm for a better one, the projected maximum still credits the departed helm's contribution, because the handed total was server-authoritative and already contained it. The alternative — re-deriving the total from the rung's loadout — would require decomposing the handed total into a base and its worn contributions, and S-002 admits no such decomposition: the oracle is given totals, never a base. A rule that cannot be evaluated from the inputs is not a rule.

So gear changes which monsters are beatable (through the loadout S-020 hands the predicate) and never changes the pool. Where the two disagree about what is worn, the pool is the one that is stale, deliberately.

### S-016 · WITHDRAWN — S-017 already answers W-002  [witness: W-002]

**Withdrawn after failing Phase 2c's closure check twice.** The id is retained and
never reused; W-002 stays in the ledger.

The check was right both times. W-002's exhibit is a rung whose published award is
zero, and this clause decided nothing there *by its own terms* — it fixed only THAT
a measurement is consulted and deferred the value to S-017, which restates that
measurement to zero and shuts the door. Rewriting it a third time to claim the
closure would have been arguing with a correct verdict.

What survives is S-017 and S-018 together: a measurement is present only on
positive evidence (S-018), and once present it is restated for the rung before use
(S-017). Neither leaves room for an oracle to ignore a measurement it holds, which
was the hole in S-008's "may" that this clause was written for. The hole is closed;
this clause is not what closes it.

Recorded rather than deleted because a withdrawn clause is evidence — the next
reader should be able to see that this question was asked, answered elsewhere, and
that a plausible-looking clause spent two rounds failing to do work another clause
had already done.

The original text follows, struck, for the record:

> Where the observations contain a measured rate for a monster (S-018 fixes what that means), the oracle uses it in place of the predicted one for that monster. This is not discretionary.

> Candidates at one rung may therefore be priced from different origins -- a measured monster against a predicted one -- and that is intended. What S-008 requires is that both are expressed in the same unit before they are compared, not that they come from the same source.
>
> This clause fixes only THAT a measurement is used. WHAT VALUE it has at a rung is S-017's, and the two must be read in that order: a measurement is never ignored, and it is never used unrestated.
>
> The case this clause alone decides is the ordinary one: a rung whose published award is positive, for a monster that also carries a measurement.

**THE STRUCK TEXT ABOVE WAS PARTLY UNSTRUCK BY AN EDITING SLIP, AND READ AS LIVE PROSE INSIDE A WITHDRAWN CLAUSE** — including "This is not discretionary", which flatly contradicts S-008's "may". The whole of it is historical and none of it governs. **The DECISION it carried is not lost: W-002's ratified answer is that evidence beats the model where evidence exists, and S-017 now carries that witness and states the mandate.**

### S-017 · A measured rate is restated for the rung it is used at  [witness: W-003]

A measured rate belongs to the character level its samples were taken at. Before it is used at a rung, the oracle restates it for that rung by the ratio of the published per-kill award for the same monster at the two levels.

The ratio is dimensionless, so the restated figure remains in the measured rate's own unit and S-008's same-unit requirement continues to hold.

**THE SAMPLE LEVEL IS ONE VALUE, AND IT IS THE MEAN OF THE LEVELS THE AGGREGATED CYCLES RECORDED, ROUNDED TO NEAREST WITH TIES GOING DOWN.** An observation aggregated across several character levels is not split into one restatement per level: the recorded levels are averaged, rounded, and the ratio is taken at that single level. A sample spanning levels 20 and 30 is restated as though every kill in it had been taken at 25.

**A TIE IS DECIDED HERE AND NOT LEFT TO A LANGUAGE.** Two cycles at adjacent levels — the commonest aggregation there is — produce a half-integer mean, and because the published award is a step function the two roundings can land on opposite sides of the grey boundary: one yields a positive award at the sample level and a finite restated rate, the other yields a zero award, which this clause routes to a restated rate of zero, which under S-013 can stop the walk. The divergence is therefore a finite total against no rungs crossed at all, and no default may be allowed to choose it — half-to-even, the built-in rounding of the declared toolchain, sends 16.5 down and 17.5 up on parity alone.

**Ties go DOWN**, for the same reason every other judgement in the restatement resolves the way it does: a lower sample level carries a HIGHER published award there, hence a SMALLER restated rate. A rate feeds how far a candidate is projected to get and the objective prefers candidates that get further, so an over-estimate manufactures reach and captures the decision, while an under-estimate only costs gear the character might have earned for free. The rounding is also to be performed without forming a binary fraction, so that no representation error can move a tie.

That is an approximation, and this clause says so rather than implying exactness. The published award is a STEP function of the gap between character and monster, so the mean of the awards at two levels is not in general the award at the mean level, and the two diverge most sharply across the grey boundary — a span half below it and half above it restates as though all of it were near the step, when in truth half of it earned nothing. The approximation is accepted because the alternative is to keep per-level sample partitions, which changes what is RECORDED, and this spec governs only how what is recorded is used.

**A RECORDED LEVEL BELOW ONE IS NOT A LEVEL, AND NEVER REACHES THE MEAN.** Characters begin at level one, so the game cannot issue a smaller one; a recorded zero is the ABSENCE of a reading rather than a reading of zero, and it is dropped exactly as a missing level is. This is not tidiness, and it covers zero and every negative alike. A recorded value below one is the signature of a MISSING reading rather than a wrong one: a level that was never written is what a default or an uninitialised counter looks like, and nothing the bot does produces such a value by observing. Zero is additionally the one value at which the published award is neither positive nor non-positive but UNDEFINED, since the award divides the monster's level by the character's — so both of the degenerate rules below would claim it while prescribing opposite outcomes. A measurement whose every cycle recorded such a value has no sample level at all and is ABSENT by the rule two paragraphs down.

**THE REASON IS CONTAMINATION, NOT THE VALUE'S OWN VERDICT.** A lone negative would already resolve on its own terms — the award at a negative level is negative, hence not positive, hence a restated rate of zero by the rule below. What excluding it prevents is different and worse: averaged in beside genuine readings, an unissuable value does not receive a verdict, it MOVES the verdict about the cycles that are genuine, dragging the mean across the grey boundary and deciding the walk on the strength of a field that was never filled in.

**THE HIGH END IS NOT EXCLUDED, AND THE ASYMMETRY IS DELIBERATE.** A recorded level ABOVE the game's maximum is also one the server cannot issue, and it is nonetheless kept and priced by the ordinary arithmetic. The discriminator is not whether the value is possible — neither end is — but whether it is the shape a MISSING reading takes. Nothing produces an above-maximum level by omission; it is a wrong reading rather than an unwritten one, and a wrong reading is evidence of something, where a blank is evidence of nothing.

Keeping it is also the conservative choice, which settles the tie the other way from what symmetry would suggest. Far above the monster the level lands in the zero band, the award at the sample level is not positive, and the restatement returns zero — withholding reach the observation does not support. Dropping it instead would fall back to the published prediction and RESTORE reach on the strength of data already known to be wrong. Where symmetry and the no-manufactured-reach rule disagree, the rule wins.

Read the exclusion above precisely, therefore: it removes values that are the signature of an absent reading — anything below one — and nothing else.

**THE MEAN IS OVER THE SAME POPULATION THE RATE IS AVERAGED OVER, LESS ONLY THE CYCLES THAT NAMED NO LEVEL.** That single rule settles the whole membership question and every corner of it. A cycle that recorded a level but NO KILLS contributes its level, because it contributed to the rate — the rate is a per-cycle average and an idle cycle drags it down, so the level that idle cycle was spent at is part of where the measurement was taken. A cycle that recorded kills but no level contributes to the rate and not to the mean, since it has nothing to contribute. The two denominators therefore differ by exactly the unlevelled cycles and by nothing else.

Dropping the unlevelled cycles from the RATE as well would change a measurement's value on the basis of a field that says nothing about the monster, which is why the populations are not simply made identical. Weighting the mean by kills is likewise declined: it would make the level a property of where the character FOUGHT rather than of where the rate was measured, and the rate being restated is per cycle, not per kill.

**WHERE NO AGGREGATED CYCLE RECORDED A LEVEL AT ALL, THE MEASUREMENT IS ABSENT — NOT ZERO.** No sample level exists, so no ratio can be formed, and S-008's fallback to the published prediction applies (S-018 states the presence condition). Absent and zero are different outcomes and the difference is load-bearing: a restatement to zero leaves the monster a candidate ranked at no reward, which under S-013 can stop the walk, while an absent measurement leaves the published prediction governing and the walk continuing. A missing level is not evidence that the monster awards nothing; it is evidence that the observation cannot be interpreted, and the published rules are what the oracle has left.

Where the published award at the level the samples were taken is not positive, the measurement and the published rules disagree, no ratio exists, and the restated rate is zero. Where the published award at the rung is zero, the ordinary arithmetic already yields zero and no separate rule is needed.

BOTH OF THOSE ARE STATEMENTS ABOUT REWARD, NOT ABOUT CANDIDACY. Nothing here removes a monster from the set S-009 and S-010 admit, and this clause adds no third ground for exclusion. A monster whose restated rate is zero remains a candidate that S-011 ranks with a reward of zero, and it is S-013 — the zero-reward stop — that decides what happens when every admissible monster is in that position. Read the other way this clause would silently shrink the candidate set that S-011 quantifies over, which is not the decision it was written to make.

### S-018 · A measurement is present only when positive evidence backs it  [witness: W-004]

The observations contain a measured rate for a monster only when that rate is backed by at least one recorded kill, is itself positive, and carries the character level its samples were taken at. Anything else -- no entry, an entry with no recorded kill, a zero rate, a negative rate, **a rate no aggregated cycle attached a level to, and a rate whose every aggregated cycle recorded a level BELOW ONE** -- is an ABSENT measurement, and S-008's fallback to the published prediction applies.

The last of those is S-017's exclusion reaching back into this list, and it is spelled out here so the two clauses classify the same measurement the same way. S-017 drops a below-one level as the signature of a reading that was never written; a measurement with no other kind of level therefore has no sample level, and calling it PRESENT here while S-017 calls it ABSENT would leave the taxonomy disagreeing with itself. Both roads already led to the same observable — the published prediction governs — so nothing changes but the account of why.

The level belongs in this list and not in S-017's arithmetic because it is a condition on the EVIDENCE, not on the value. S-017 needs a sample level to restate a rate at all; a rate that has none is not a rate the oracle knows how to interpret anywhere, so it never reaches restatement. Admitting it as present and then restating it to zero would be a different decision with a different consequence — see S-017 for why zero and absent do not interchange.

An absent measurement is not an error and does not stop the walk. In particular a non-positive STORED rate never reaches the zero-reward stop — it is absent, so the published prediction governs and the stop is decided on that.

**THAT IS A STATEMENT ABOUT ABSENT MEASUREMENTS ONLY, AND MUST NOT BE READ AS ONE ABOUT THE STOP.** An earlier version of this sentence added that the zero-reward stop "is a statement about what the published rules award and not about what has been observed", which claims more than this clause decides and contradicts S-017: a PRESENT measurement restated to zero — because the published award at its sample level was not positive — does reach the stop, and halts the walk at a rung whose published award may be perfectly healthy. That is deliberate. Once a measurement is present it is the oracle's estimate of reward, and a zero estimate is a zero reward however it arose; the alternative is to let an observation incoherent with the published rules be quietly discarded, which restores reach on evidence known to be broken. The stop is a test of REWARD, not of provenance. Which measurements are present is this clause's decision; what happens to a present one is S-017's and S-013's.

### S-019 · Progress carries across rungs  [witness: W-005]

A rung's loop cost is the EXACT QUOTIENT of its remaining requirement by the rate, and is never resolved to a whole kill; S-014's upward resolution applies to the total the oracle reports, never to an individual rung. Because the quotient is exact, each rung's requirement is met exactly and **no surplus is ever formed**. There is no accumulator, and no surplus is banked as a discrete quantity.

Only the FIRST rung starts from the character state's current progress toward the next level. Every later rung starts from the level's requirement entire, and needs no credit from the rung before it, because that rung left nothing over.

**THIS IS NOT THE SAME RULE AS CARRYING THE OVERSHOOT, AND AN EARLIER VERSION OF THIS CLAUSE CLAIMED IT WAS.** Not rounding and carrying a surplus coincide only when the rate is the same at both rungs, and it almost never is: the published award carries the character's level in its base term AND in its penalty step, so the rate moves at every rung even for one monster, and S-011 may change the monster outright. The physical climb executes WHOLE actions, so the action that carries the character across a boundary earns its whole award at the DEPARTING rung's rate and spills the excess into the next rung — where this model instead charges that excess at the ARRIVING rung's rate. Valuing a residue in experience and redeeming it later is a different arithmetic from never forming one, and calling them "exactly equivalent" was wrong.

**THE MODEL DECLINES TO MODEL THAT SPILL, AND THE ERROR IS BOUNDED AND DECLARED.** The difference is confined to the excess of ONE action per rung boundary, so it is strictly less than one action per rung, and it can fall either way. Where the next rung's rate is lower — the ordinary case, since a monster greys as the character climbs — the spill was earned more cheaply than this model charges for it, and the model OVER-prices. Where S-011 finds a better monster at the next rung, the model UNDER-prices, bounded by the ratio of the two rates. S-014's single upward resolution of the total is the only correction applied and is not claimed to cover this. Modelling the spill exactly would require the walk to know where within an action each boundary falls, which is precisely the per-rung accumulator this clause exists to do without.

**MEASURED, so that the bound is not left as an argument.** Against a whole-action simulation of the same walk — one where the crossing action earns its whole award at the departing rung's rate and the excess spills forward — two live characters' climbs came out at 3057 actions against 3058 reported over four rungs, and 2670 against 2670 over five. The per-boundary errors partly cancel rather than accumulating, so the observed gap is a single action across a whole climb and not the per-rung bound's worth. The bound stands as the guarantee; this is what it is worth in practice, and it is small enough that closing it would not repay the accumulator.

**That quotient is in ACTIONS, not kills.** The rate is XP per executed loop action (S-023), so requirement divided by rate is a count of loop actions directly, and no kill count is formed or needed anywhere in the walk. This clause and S-005 speak of "per kill" only to identify WHICH actions are in the loop; neither requires the oracle to know how many kills a rung takes, and an implementation that recovered a kill count in order to re-multiply the loop length by it would charge the loop twice.

**THE REMAINING REQUIREMENT IS AT LEAST ONE UNIT OF EXPERIENCE.** A rung's requirement is the level's requirement less the progress carried into it, floored at one. The floor matters only at the top of the progress range, on a character handed a state whose progress already equals its requirement. No carry can reach it: every later rung takes the level's requirement entire, so nothing the walk generates can reduce a requirement to zero.

**WHAT THE FLOOR BUYS IS A POSITIVE COST, AND NOT A WHOLE ACTION.** A rung floored this way is charged one unit of experience' worth of loop — a small fraction of a fight, not a fight. The clause does not pretend otherwise. Positivity is all the walk's machinery needs: S-003's naming of a monster per rung, S-009 and S-010's candidacy, and S-013's zero-reward stop all presume a rung that is fought, and a zero would let a rung be crossed at no cost at all while still claiming a monster. A charge below one action is an under-price, but it is bounded by one action and confined to an input the server cannot produce, which is a smaller price than the alternative of special-casing the rung out of the walk entirely.

**A FLOORED RUNG CARRIES NOTHING OUT.** Where the floor binds, the excess that provoked it is discarded, and the next rung starts from the level's full requirement exactly as every non-first rung does. That is not a second rounding decision; it follows from there being no accumulator. The character's own recorded progress enters the walk ONCE, at the first rung. Every later rung's requirement is the level's requirement entire, and nothing crosses a boundary at all — the exact quotient leaves no surplus to cross. So there is nothing in the walk an excess could be carried in, whatever its size.

The floor binds only on a state the server cannot produce — progress at or beyond the requirement is a level the character has already been granted — so this rule governs a HANDED input rather than anything the walk generates. It is stated because a total function must decide it, and because deciding it the other way silently would let a walk begin pre-advanced on experience no rung was ever charged for, which is the same understatement of cost the floor exists to prevent.

**THE OTHER END OF THE SAME RANGE IS DECIDED THE SAME WAY, AND THE SUBTRACTION IS LITERAL.** Handed progress BELOW zero is equally impossible for the server to produce, and it is not discarded: the first rung's requirement is the level's requirement less that progress, so a progress of minus forty against a requirement of a hundred gives a requirement of a hundred and forty, and the walk is charged for experience the character never lost. The floor plays no part at this end — the subtraction has already produced a value above one — and the ordinary arithmetic is left to run.

The two ends are decided in opposite arithmetic directions and by the SAME principle, which is why this is one decision rather than two. Both resolve AGAINST the character, as S-014 does: an excess at the top is dropped rather than credited, and a deficit at the bottom is charged rather than dropped. The alternative — discarding an out-of-range progress at both ends because the walk cannot interpret it — is coherent but resolves the bottom end in the character's favour, which would let a malformed state under-report a climb, and under-reporting a climb is the one error the objective cannot tolerate: it is what makes a candidate look reachable when it is not.

That floor is the reason NO RUNG IS EVER CROSSED AT ZERO COST. Without it the two sentences above would contradict each other at that boundary: an exact quotient of a zero requirement is zero, while the machinery just listed presumes a rung that is actually fought. With it, every rung has positive cost, every rung names a monster, and those clauses apply at every rung without exception. The floor is a deliberate rounding AGAINST the character, consistent with S-014, and together with the declined boundary spill above it is one of the two places this clause departs from exact arithmetic — both bounded, both stated.

### S-020 · The consult sees carried gear, and the equip is charged  [witness: W-006]

The state handed to the beatability predicate carries the best loadout the character already holds and is permitted to wear at that rung -- inventory and worn together -- not only what is currently worn. Equip conditions are evaluated against the rung's level (S-015), so gear the rung newly unlocks is included.

WHICH loadout is best for a purpose is not decided here. It comes from the same shared loadout selection the executor uses, exactly as the beatability verdict does, and that selection is BACKGROUND: two carried pieces competing for one slot with neither dominating is its problem to settle, and it must settle it deterministically (S-001). This clause fixes only that the selection is offered inventory and worn together, and is evaluated at the rung's level.

**Changing the loadout is executed work, priced by its published duration under S-004, and counted in ITEM MOVEMENTS rather than slots.** Two published rules fix it, and neither may be guessed:

- A slot that is occupied cannot be equipped into; the incoming piece is refused while the outgoing one is still worn. A slot that gains a piece is therefore ONE movement, a slot that loses one is ONE, and a slot that SWAPS is **TWO** — the old piece comes off, the new one goes on. Counting differing slots prices every upgrade after a character's first as though the displaced item evaporated.
- The duration is **three seconds per item moved**, and a batch of `n` costs `3n` however it is grouped into requests. An item movement is therefore about a tenth of a Fight, not a whole one. This is S-004's conversion rule applying to a second non-uniform action, not a special case invented here.

A movement's cost does not depend on which slot it is, which piece it is, or how many other pieces move with it. Where the loadout is unchanged the cost is zero, so gear held across many rungs is paid for once.

Whether a change is POSSIBLE is not priced here and is not this clause's business: a full inventory or a piece whose removal would drop the character's hit points too far are conditions on the change happening at all, and belong to the loadout selection and the executor, both background.

That cost is a SETUP cost of the rung, not part of the loop. A rung therefore has two kinds of cost:

- a **per-kill loop cost** — the fight and the recovery it forces (S-005, S-021), paid once per kill and proportional to the number of kills; and
- a **once-per-rung setup cost** — the equip actions needed to move from the loadout the character arrives with to the rung's loadout, paid once regardless of how many kills the rung takes.

The rung's cost is the sum of the two. The distinction is load-bearing rather than presentational: only the per-kill part may enter a per-action RATE (S-022, S-023), because a fixed charge divided by a rate is not a rate. Folding the equip into the loop would make the selection criterion an integral-over-the-rung figure, which S-022 forbids.

The loadout the character "arrives with" is the one the previous rung left it in, and the first rung's is what it is wearing at the start. Gear held across several rungs is therefore paid for once.

This clause is about which arguments the oracle constructs, never about how the predicate decides.

### S-021 · Recovery costs its published duration, amortised over the chain it ends  [witness: W-007]

A recovery action restores the character fully, so one ends each chain of fights (S-005) and no chain needs two.

**A DAMAGE OF ZERO FORCES NO RECOVERY, AND CONTRIBUTES NOTHING.** The guard never trips, no fight ever crosses it, and there is no chain for a recovery to end — so the first sentence's "one ends each chain" is not engaged, and neither the three-second floor nor any other part of the price applies. The per-kill contribution is zero and the loop is the bare Fight. This is the ONE point at which the floor regime below could have bound, and the sweep reported there ran over positive damages only; zero is decided here instead, by the guard rather than by the arithmetic. Without this sentence the regimes below read as exhaustive and an implementer could charge the floor's three seconds for a monster that costs nothing — which changes the monster a rung names, not merely its price, and does so exactly where armour has driven damage to nothing.

**Its cost is its published duration, converted by S-004.** The game publishes that duration as a function of how much is restored: one second per one percent of the character's missing hit points, rounded up, with a floor of three seconds. The character enters a recovery having lost the damage of every fight in the chain, capped at its whole bar, since a recovery cannot restore more than everything.

The conversion constant of S-004 is **the duration of one Fight action**, because the unit is one Fight. The oracle declares it and does not derive it from a measurement, so that the price of a rung does not move with the character whose history happens to be loaded.

**ITS VALUE IS THIRTY SECONDS, AND STATING THE PROVENANCE WITHOUT THE NUMBER DECIDED NOTHING.** An earlier version of this clause fixed where the constant may not come from and never said what it is — while in the same breath declaring every other constant it needed numerically. That left the one term this clause exists to price scaled by an implementation's choice, which defeats the very purpose the provenance rule was written for: the price of a rung stops moving with the loaded character and starts moving with the implementation instead. The freedom was decision-relevant and not cosmetic, since the constant divides the recovery term and nothing else, so two declarations can rank two monsters differently.

Thirty seconds is a DECLARED figure and this clause says so rather than dressing it as published: a Fight's real cooldown varies with the fight, and no single published number covers it. It is a residual, and the honest one to carry — a learned median would make a rung's price move with whichever history is loaded, which is the laundering this clause's provenance rule forbids. Everything the oracle reports is in units of that declared Fight, and a different declaration would be a different unit rather than a different answer.

**THE PUBLISHED DURATION IS A WHOLE NUMBER OF SECONDS, AND THAT QUANTUM IS PART OF THE RULE.** The percentage is rounded UP to the next second before anything else happens; the operative sentence is the published one, and the regime descriptions below are consequences of it rather than a second, competing formula. Where the projected bar is exactly a hundred the rounding is a no-op and the two are indistinguishable — which is precisely why they must be ordered here, since S-015's per-level grant makes the bar something other than a hundred at almost every rung. An oracle that dropped the rounding would charge 48.571 seconds where the server charges 49.

Recovery's contribution to one kill is that converted cost divided by the number of fights in the chain. It is not quantised a SECOND time before the rung total is formed: the one-second rounding above is the only quantisation, and S-014's upward resolution applies to the reported total and never to a rung (S-019). **THE THRESHOLD IS A FRACTION OF THE BAR, COMPARED AS A RATIO, AND IS NEVER SNAPPED TO THE HIT-POINT LATTICE.** The guard asks whether hit points OVER maximum hit points has fallen below three quarters; it does not compute a whole-hit-point threshold and compare against that. The distinction is invisible only where a quarter of the bar happens to be whole, which S-015's five-point grant makes one rung in four. The natural integer implementation floors the threshold, which widens the band to the bar less that floor; swept over every whole bar from 20 to 2500 and every whole positive damage, the two readings disagree on chain length in 12351 pairs and on the per-kill share in 12186 of them. It is not a rounding curiosity — it moves the price, and can move the monster a rung names. The exact ratio is chosen because it is what the EXECUTOR's guard computes, and the whole purpose of pricing the loop this way is that the projection and the runtime agree about when a recovery happens.

That also bounds the rule below: hit points can land EXACTLY on the threshold only where the quarter is whole, so the exact-division case is real at one rung in four and simply cannot arise at the others. It is stated in full anyway, because a rule that holds only where it is reachable is still the rule.

**THE CHAIN CONTINUES WHEN HIT POINTS LAND EXACTLY ON THE GUARD'S THRESHOLD.** The guard trips only when they fall BELOW it, so a chain whose damage divides the band exactly takes one more fight: its length is the whole number of fights the band absorbs, PLUS the committed fight that crosses it, and never the bare quotient. The distinction is invisible except at exact division and it decides the clause's central property. Read the other way — the chain ending at the threshold — a damage of exactly an eighth of the bar against a quarter-band chains two fights and costs 25 seconds, while the slightly SMALLER damage just under an eighth chains three and costs 38, so a heavier monster would be cheaper per kill and better armour could raise a rung's price. Chain length is a step function of damage, and only this boundary keeps the step from ever running backwards.

The contribution is therefore monotone non-decreasing in damage, and increasing throughout the interior band defined below UP TO THE ONE-SECOND QUANTUM — two damages whose chains round to the same whole second cost the same, and they must, because the server charges them the same. **Damage and the bar are whole numbers of hit points**, which is the domain that claim is made over; swept over every whole bar from 20 to 2500 and every whole POSITIVE damage, the contribution never once decreases. Zero extends the property rather than threatening it: it contributes nothing, and every positive damage contributes more. Saturation inside that band is the specific defect this clause forbids — an oracle that charged a fixed amount for every recovery would report the same rung cost for every damage above the guard's band, and the only quantity defensive equipment moves is damage.

**The contribution has three regimes, and the clause governs each explicitly.** Write `B` for the guard's band as a fraction of maximum hit points, and `d` for the damage one fight takes as a fraction of maximum hit points.

- **The floor regime**, where the chain's accumulated damage is at or below TWO percent of the bar. The boundary is two and not three because the rounding runs first: two and a half percent already rounds up to the three seconds the floor guarantees. **AT THE DECLARED BAND THIS REGIME IS EMPTY, and the clause says so rather than legislating a case that cannot arise.** The chain ends at the guard, so its accumulated damage is at least the band — a quarter of the bar — and never approaches two percent; swept over every whole bar from 20 to 2500 hit points and every whole POSITIVE damage, the smallest accumulated damage observed is 25.01% and the floor binds in no pair at all; a damage of zero is outside the sweep and outside these regimes, decided above by the guard. The regime is retained because the published floor is real and a smaller band would reach it, and because the published rule is stated here in full rather than trimmed to the band currently declared. It is not a live branch of the price.
- **The interior**, where `n · d < 1` — the chain's accumulated damage does not reach a whole bar. The recovery restores exactly what the chain spent, and **the size of the guard's band does not enter the per-kill contribution, to within the one-second quantum**: a longer band chains proportionally more fights and ends in a proportionally longer recovery, and the two cancel — exactly in the underlying percentages, and up to the rounding in the seconds actually charged. The contribution is `d` bars' worth of seconds per fight, rounded up once over the chain. This is the regime the oracle is for, and no clause may make the band enter it by more than that quantum.
- **The ceiling regime**, where `n · d ≥ 1`. The cap binds: the recovery restores one bar and costs a hundred seconds however much more was lost. The contribution is FLAT, and the band does enter — a longer band divides that fixed hundred seconds over more fights.

**THE BOUNDARY IS A CONDITION ON THE CHAIN, NOT A THRESHOLD ON `d`.** An earlier version of this clause drew it at `d ≥ 1 − B` and asserted that the cap binds there. That inference is false in both directions, and the clause's own arithmetic shows it. Where `d` exceeds the band the chain is a single fight, so accumulated damage is `d` and the cap does not bind until `d` reaches a whole bar — a monster taking ninety-nine percent of the bar sits in the declared ceiling regime while its recovery genuinely costs ninety-nine seconds, not a hundred. And where the band is deep, a chain of two can exceed a bar at a `d` the old boundary called interior, so the cap binds inside the region where band-independence was promised. Only `n · d ≥ 1` marks the change, because only that is what the cap is a statement about.

At the guard this model declares — a band of one quarter — the interior condition reduces to `d < 1`: any `d` above the band gives a chain of one, and a chain of one reaches a bar only at a full bar. The general form is stated because the reduction depends on the band, and a clause whose correctness turns on a constant it deliberately refuses to let matter must not be written in terms of that constant.

The flatness at the ceiling is not the forbidden saturation; it is the published rule being true. A recovery cannot restore more than everything, so two fights that both empty the bar really do cost the same recovery, and an oracle that charged more for the heavier one would be inventing a duration the server does not charge. **What makes it harmless rather than a defect is that with the boundary drawn correctly it is not a regime the walk ranks gear in:** reaching it takes a chain that loses a whole bar, and at the declared band that is one fight losing a whole bar, which is not a fight the character wins. S-009's beatability predicate — not this clause — is what keeps such a monster out. That argument does NOT survive the old boundary, and this is the second thing wrong with it: a monster taking ninety-nine percent of the bar is winnable from full, so it is ranked, and flattening its cost would buy defensive gear exactly nothing across the band where it matters most. This clause prices what it is handed; it does not certify that the ceiling is reachable.

An earlier version of this clause asserted strict monotonicity and band-independence over the WHOLE range, which is false at the ceiling by the clause's own arithmetic. The correction there is to state the boundary, not to weaken the interior.

A LATER version made the opposite kind of error, and it is the more instructive one. It described the interior as cancelling EXACTLY and as strictly increasing, having checked those claims only on a bar of exactly a hundred, where one hit point is one percent and the published rounding cannot be seen at all. Both claims are false a rounding's width away from the truth, and every rung above the first has a bar S-015 has grown off that number. **The published rule governs, and the properties are its consequences**; where a stated property and the published duration disagree, the property was stated too strongly and the duration is what the server charges. A clause that describes a rule in two ways has not given an implementer one rule, and the exhibit that motivated this one could not tell them apart.

The maximum hit points this scales against are the projected state's own (S-015): the handed maximum grown by the published per-level grant, and not raised by carried gear.

**THE NUMERATOR IS SETTLED TOO, AND IT IS SETTLED THE OTHER WAY.** The recovery charge is a ratio of two quantities, and an earlier version of this clause fixed the provenance of the denominator and left the numerator's unstated. The DAMAGE is evaluated against the rung's re-evaluated loadout — the same loadout S-020 hands the beatability predicate, inventory and worn together, at the rung's level — and not against the gear the character happens to be wearing when the walk starts.

The asymmetry is deliberate and neither half may be read as a mistake for the other. The maximum hit-point pool is a published per-level grant, so gear must not inflate it in either direction; the damage is a combat outcome, so it must be judged under the loadout the character will actually fight in, or this clause disagrees with the predicate that decided the monster was winnable at all. The same asymmetry is already in force one clause over: the walk asks "can I win?" wearing the best owned gear, and asking "how much will I bleed?" wearing something else is how the two answers drift apart. It is also what makes the sentence above true — the only quantity defensive equipment moves is damage, and it moves it HERE.

**This clause and S-005 divide the work: S-005 counts what is executed, this one prices each execution.** The earlier reading, in which recovery cost a fixed one action contributed as the fraction of a hit-point pool consumed, disagreed with S-005 about rungs whose kill count did not fill a whole chain — and it disagreed over a band size that, priced in duration, does not affect the answer.

An earlier version of this paragraph went further and asserted the two "cannot disagree". They can, and did, in two places that are now settled IN S-005 rather than papered over here. Its distinguishing requirement said two monsters leaving the character at different depths must always price differently; the published second is the resolution the server bills at, so depths inside one second of each other cost the same and S-005 now carries that exception. Its stopping condition said the character fights while hit points "remain above" the threshold, which recovers at exactly the threshold where this clause continues the chain; S-005 now says AT OR ABOVE. A clause that declares itself consistent with another is asserting something it cannot check from the inside, and both times it was wrong.

### S-022 · The per-rung choice maximises reward per action, not per rung  [witness: W-008]

**What this clause decides is the DENOMINATOR, and only the denominator.** The monster chosen for a rung is the one with the greatest reward per executed action, and the actions in that ratio are the PER-KILL LOOP actions alone (S-005): the fight and the recovery it forces. A rung's once-per-rung setup cost — the loadout change of S-020 — is **excluded**. A monster is not penalised in the ranking for needing an equip; that charge is added to the rung total after the choice is made.

The exclusion is the whole content. A fixed charge in a ratio's denominator is not a rate: it makes the ranking depend on how many kills the rung happens to need, so the same two monsters could rank differently at two rungs that differ only in how much experience remains. It would also make a monster's rank depend on what the character happens to be wearing when it arrives, which is a property of the previous rung, not of this choice.

**PER-KILL AND PER-RUNG ARE THE SAME CRITERION FOR THE LOOP, and that is a theorem here rather than a rule.** Given a rung whose remaining requirement is a fixed positive quantity, and a loop cost with no fixed term and no rounding (S-019), the rung's LOOP cost is that requirement divided by the rate. Ranking by greatest rate and ranking by least loop cost are therefore the same ordering, exactly, for every catalogue.

**That equivalence is about the loop cost alone and does not extend to a rung's TOTAL.** S-020 makes a rung's cost the loop plus the setup, and the setup is exactly what the exclusion above keeps out of the ranking — so the monster with the least loop cost is not always the one with the least rung total, and where a cheaper-per-action monster demands a loadout change that a dearer one does not, the two genuinely differ. This clause chooses the loop, deliberately: the alternative makes a monster's rank depend on what the character was wearing when it arrived, which is a property of the previous rung. The divergence W-008 exhibited was a different one — per-kill against per-rung within the loop, which relied on integral kills and which S-019 abolishes — and that one is unreachable. S-011's heading names the loop equivalence, not a claim about totals.

**W-008 IS THEREFORE CLOSED BY S-019, NOT BY THIS CLAUSE, AND THE LEDGER SAYS SO.** Both of W-008's candidate outputs are illegal today, and neither is made illegal by anything written here: the exact unrounded quotient of S-019 forbids the integral-kill cost of the first, and once that cost is corrected the second's monster is no longer the cheaper one under either criterion. W-008's pair contains no loadout change at all, so the exclusion this clause exists to state is not exercised by it and could not have changed its answer. Claiming that closure would be claiming work S-019 did.

What follows is that this clause stands or falls on the exclusion alone, and it needs a distinguishing pair of its own to earn its place — one in which a cheaper-per-action monster requires an equip that a dearer one does not, so that ranking on the loop and ranking on the total genuinely select differently. Until such a pair exists in the ledger, the exclusion is asserted rather than witnessed, and this paragraph is here so that no later phase mistakes W-008's closure for evidence of it.

### S-023 · Rates are reconciled in XP per executed action  [witness: W-009]

A measured rate is XP per executed planner action over the whole combat loop -- the same unit S-004 fixes for costs, and the unit an observation of actual play naturally arrives in, since it averages over every action the pursuit spent including recovery.

A prediction from the published formula is per KILL, and is converted into that unit by dividing by the rung's loop action count (S-005) before it is compared with anything.

"Executed action" here means a PER-KILL LOOP action and only those — the fight and the recovery it forces. A rung's once-per-rung setup cost (S-020's equips) is outside this denominator on both sides of the conversion: it is not divided into the prediction, and a measured rate is not understood to have absorbed it. A fixed charge in a rate's denominator would make the rate depend on how many kills the rung happens to need, which is the very thing a rate exists not to depend on.

**The unit governs every use of the rate, not only comparison.** Once a rate is in XP per loop action it stays there: it is the divisor S-019 divides a rung's remaining requirement by, and that quotient is a count of LOOP ACTIONS which is the rung's loop cost outright. No kill count is formed, and the loop length is never applied a second time.

**A MEASURED MONSTER'S LOOP COST THEREFORE DOES NOT VARY WITH PROJECTED DAMAGE, AND THAT IS NOT A CONTRADICTION WITH S-005 OR S-021.** A whole-loop measurement has already absorbed the recovery the character really performed, at the damage it really took; re-applying a modelled recovery on top would charge that recovery twice. Where S-005 requires the reported cost to distinguish two monsters that leave the character at different depths, and where S-021 requires the recovery charge to move strictly with damage, they are governing the PREDICTED path — the one where the oracle must model a loop it has not observed. On the measured path the same distinction is present, but it arrives inside the measurement rather than being computed beside it.

The two paths therefore respond to defensive equipment differently, and the difference is real rather than a modelling gap: better armour improves a predicted monster's cost immediately and a measured monster's cost only as new observations accumulate at the new damage. An oracle that "fixed" this by charging a modelled recovery on top of a measurement would not be making the measured path gear-sensitive; it would be double-counting, and S-017 already fixes the one adjustment a measurement does receive — restatement for the rung's level, and nothing else.

The conversion runs in that direction and never the other. Recovering a per-kill figure from a whole-loop measurement means MULTIPLYING by a loop length the measurement has already absorbed — and then, because the walk costs a rung in actions, multiplying by it again on the way back out. An earlier version of this sentence said "divide", naming the wrong operation and so forbidding nothing: an implementation that multiplied up to a per-kill rate, took the requirement over it to get kills, and charged the loop per kill broke no letter of the clause and over-charged every rung by a whole loop length.

For a prediction the round trip is exact and harmless, because the prediction is genuinely per-kill and dividing it once is how it arrives in the unit at all. For a MEASUREMENT it is not: the measurement never carried a kill count to recover, so the loop length used to recover one is the rung's model rather than the measurement's own, and the result is a number the observation does not support.
