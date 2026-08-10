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
remain above the recovery guard's threshold and recovers once when they do not, so
recovery is executed once per chain of fights rather than once per fight. The
number of fights in a chain is determined by the guard's threshold and the damage
per fight, and the chain includes the fight that carries the character across the
threshold — the guard is consulted before a fight, so that fight is already
committed.

A rung requires a whole number of executions of each action, but a rung's kill
count is not generally a whole multiple of a chain. The clause therefore constrains
the **total**, not each summand: the rung's cost is the sum over its kills of the
per-kill contribution, where recovery's per-kill contribution is one chain's
recovery cost divided by the fights in that chain. No summand is rounded, and the
residue at a rung boundary is carried rather than discarded (S-019), so the total
equals what the character executes without any individual charge being an integer.

A monster that forces recovery after every kill is more expensive per kill than one
that can be fought consecutively, and the reported cost must distinguish them; so
must two monsters that both force recovery after every kill but leave the character
at different depths, because their recoveries do not cost the same (S-021).

### S-006 · Already at or above target costs nothing

If the character's current level is at or above the target, the oracle reports zero
rungs crossed and zero total cost. This is a genuine answer, not a refusal: there is
nothing left to do.

### S-007 · XP per kill comes from the published formula

Where the oracle must predict the XP a kill awards, it computes it from the game's
published formula over the catalogue's attributes for that monster. It does not
guess, does not use a constant, and does not substitute a value not derived from
game data.

### S-008 · Learned observations may supersede prediction

Where the observations contain a measured rate for a monster, the oracle may use
that measured rate in place of the predicted one. A measured rate and a predicted
one must be in the same unit before either is used, and the oracle never compares
one against the other across units.

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

Where the observations contain a measured rate for a monster (S-018 fixes what that means), the oracle uses it in place of the predicted one for that monster. This is not discretionary.

Candidates at one rung may therefore be priced from different origins -- a measured monster against a predicted one -- and that is intended. What S-008 requires is that both are expressed in the same unit before they are compared, not that they come from the same source.

This clause fixes only THAT a measurement is used. WHAT VALUE it has at a rung is S-017's, and the two must be read in that order: a measurement is never ignored, and it is never used unrestated. Where S-017 restates a measurement to zero, this clause has still been obeyed — the measurement was used, and using it yielded nothing. An oracle may not reach the opposite outcome by declining to consult the measurement at all.

The case this clause alone decides is the ordinary one: a rung whose published award is positive, for a monster that also carries a measurement. There the prediction and the measurement disagree by some finite factor, and the measurement governs.

### S-017 · A measured rate is restated for the rung it is used at  [witness: W-003]

A measured rate belongs to the character level its samples were taken at. Before it is used at a rung, the oracle restates it for that rung by the ratio of the published per-kill award for the same monster at the two levels.

The ratio is dimensionless, so the restated figure remains in the measured rate's own unit and S-008's same-unit requirement continues to hold.

Where the published award at the level the samples were taken is not positive, the measurement and the published rules disagree, no ratio exists, and the restated rate is zero. Where the published award at the rung is zero, the ordinary arithmetic already yields zero and no separate rule is needed.

BOTH OF THOSE ARE STATEMENTS ABOUT REWARD, NOT ABOUT CANDIDACY. Nothing here removes a monster from the set S-009 and S-010 admit, and this clause adds no third ground for exclusion. A monster whose restated rate is zero remains a candidate that S-011 ranks with a reward of zero, and it is S-013 — the zero-reward stop — that decides what happens when every admissible monster is in that position. Read the other way this clause would silently shrink the candidate set that S-011 quantifies over, which is not the decision it was written to make.

### S-018 · A measurement is present only when positive evidence backs it  [witness: W-004]

The observations contain a measured rate for a monster only when that rate is backed by at least one recorded kill and is itself positive. Anything else -- no entry, an entry with no recorded kill, a zero rate, a negative rate -- is an ABSENT measurement, and S-008's fallback to the published prediction applies.

An absent measurement is not an error and does not stop the walk. In particular a non-positive stored rate never reaches the zero-reward stop, which is a statement about what the published rules award and not about what has been observed.

### S-019 · Progress carries across rungs  [witness: W-005]

The walk tracks cumulative progress. XP earned by the final kill of a rung beyond that rung's requirement is not discarded: it counts toward the next rung.

Only the FIRST rung starts from the character state's current progress toward the next level. Every later rung starts from the surplus carried out of the one before it.

CARRYING IS ACHIEVED BY NOT ROUNDING, and that is the whole of it. A rung's loop cost is the exact quotient of its remaining requirement by the rate, and is NOT resolved to a whole kill; S-014's upward resolution applies to the total the oracle reports, never to an individual rung. A fractional kill carried at a rung boundary is precisely the surplus this clause preserves, so no separate accumulator exists and no surplus is ever banked as a discrete quantity.

**That quotient is in ACTIONS, not kills.** The rate is XP per executed loop action (S-023), so requirement divided by rate is a count of loop actions directly, and no kill count is formed or needed anywhere in the walk. This clause and S-005 speak of "per kill" only to identify WHICH actions are in the loop; neither requires the oracle to know how many kills a rung takes, and an implementation that recovered a kill count in order to re-multiply the loop length by it would charge the loop twice.

**THE REMAINING REQUIREMENT IS AT LEAST ONE UNIT OF EXPERIENCE.** A rung's requirement is the level's requirement less the progress carried into it, floored at one. The floor matters only at the top of the progress range — a character handed a state whose progress already equals its requirement, or a carry that exactly fills the next level — and there it is what stops a rung being crossed for nothing.

That floor is the reason NO RUNG IS EVER CROSSED WITHOUT FIGHTING. Without it the two sentences above would contradict each other at that boundary: an exact quotient of a zero requirement is zero, while the walk's machinery — S-003's naming of a monster per rung, S-009 and S-010's candidacy, S-013's zero-reward stop — presumes a rung that is actually fought. With it, every rung has positive cost, every rung names a monster, and those clauses apply at every rung without exception. The floor is a deliberate rounding AGAINST the character, consistent with S-014, and it is the only place this clause departs from exact arithmetic.

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

**Its cost is its published duration, converted by S-004.** The game publishes that duration as a function of how much is restored: one second per one percent of the character's missing hit points, rounded up, with a floor of three seconds. The character enters a recovery having lost the damage of every fight in the chain, capped at its whole bar, since a recovery cannot restore more than everything.

The conversion constant of S-004 is **the duration of one Fight action**, because the unit is one Fight. The oracle declares it and does not derive it from a measurement, so that the price of a rung does not move with the character whose history happens to be loaded.

Recovery's contribution to one kill is that converted cost divided by the number of fights in the chain. It is not quantised before the rung total is formed. It is monotone non-decreasing in damage everywhere, and STRICTLY increasing throughout the interior band defined below. Saturation inside that band is the specific defect this clause forbids — an oracle that charged a fixed amount for every recovery would report the same rung cost for every damage above the guard's band, and the only quantity defensive equipment moves is damage.

**The contribution has three regimes, and the clause governs each explicitly.** Write `B` for the guard's band as a fraction of maximum hit points, and `d` for the damage one fight takes as a fraction of maximum hit points.

- **The floor regime**, where the chain's accumulated damage is under three percent of the bar. The published floor of three seconds exceeds the earned duration, so a short chain pays an unearned remainder and chaining more fights is genuinely cheaper. Here, and only here, a longer band lowers the per-kill contribution.
- **The interior**, `d < 1 − B`. Here the chain's accumulated damage neither trips the floor nor reaches a whole bar, the recovery restores exactly what the chain spent, and **the size of the guard's band does not enter the per-kill contribution**: a longer band chains proportionally more fights and ends in a proportionally longer recovery, and the two cancel exactly. The contribution is `d` bars' worth of seconds per fight and is strictly increasing in `d`. This is the regime the oracle is for, and no clause may make the band enter it.
- **The ceiling regime**, `d ≥ 1 − B`. The chain's accumulated damage reaches or exceeds a whole bar, so the cap binds: the recovery restores one bar and costs a hundred seconds however much more was lost. The contribution is therefore FLAT in `d`, and the band does enter — a longer band divides that fixed hundred seconds over more fights.

The flatness in the third regime is not the forbidden saturation; it is the published rule being true. A recovery cannot restore more than everything, so two fights that both empty the bar really do cost the same recovery, and an oracle that charged more for the heavier one would be inventing a duration the server does not charge. **What makes it harmless rather than a defect is that it is not a regime the walk ranks gear in:** a character losing a whole bar in one fight is not winning it, and S-009's beatability predicate — not this clause — is what keeps such a monster out of the walk. This clause prices what it is handed; it does not certify that the third regime is reachable.

An earlier version of this clause asserted strict monotonicity and band-independence over the WHOLE range, which is false at the ceiling by the clause's own arithmetic. The correction is to state the boundary, not to weaken the interior.

The maximum hit points this scales against are the projected state's own (S-015): the handed maximum grown by the published per-level grant, and not raised by carried gear.

**This clause and S-005 price the same executions and cannot disagree.** S-005 counts what is executed; this one prices each execution. The earlier reading, in which recovery cost a fixed one action contributed as the fraction of a hit-point pool consumed, disagreed with S-005 about rungs whose kill count did not fill a whole chain — and it disagreed over a band size that, priced in duration, does not affect the answer.

### S-022 · The per-rung choice maximises reward per action, not per rung  [witness: W-008]

The monster chosen for a rung is the one with the greatest reward per executed action, measured over the whole loop S-005 describes. It is not chosen by the integral cost of crossing that particular rung.

The actions in that ratio are the PER-KILL LOOP actions alone (S-020): the fight and the recovery it forces. A rung's once-per-rung setup cost is not in the denominator, and a monster is not penalised in the ranking for needing an equip — that charge is added to the rung total after the choice is made.

This is well-founded only because progress carries (S-019) and because the rate's denominator is proportional to kills. No reward is lost at a rung boundary and no fixed charge distorts the ratio, so the monster that earns fastest per action also reaches the target fastest, and S-011's criterion and this one are the same criterion. S-011's heading names that consequence rather than a second and different rule.

### S-023 · Rates are reconciled in XP per executed action  [witness: W-009]

A measured rate is XP per executed planner action over the whole combat loop -- the same unit S-004 fixes for costs, and the unit an observation of actual play naturally arrives in, since it averages over every action the pursuit spent including recovery.

A prediction from the published formula is per KILL, and is converted into that unit by dividing by the rung's loop action count (S-005) before it is compared with anything.

"Executed action" here means a PER-KILL LOOP action and only those — the fight and the recovery it forces. A rung's once-per-rung setup cost (S-020's equips) is outside this denominator on both sides of the conversion: it is not divided into the prediction, and a measured rate is not understood to have absorbed it. A fixed charge in a rate's denominator would make the rate depend on how many kills the rung happens to need, which is the very thing a rate exists not to depend on.

**The unit governs every use of the rate, not only comparison.** Once a rate is in XP per loop action it stays there: it is the divisor S-019 divides a rung's remaining requirement by, and that quotient is a count of LOOP ACTIONS which is the rung's loop cost outright. No kill count is formed, and the loop length is never applied a second time.

The conversion runs in that direction and never the other. Recovering a per-kill figure from a whole-loop measurement means MULTIPLYING by a loop length the measurement has already absorbed — and then, because the walk costs a rung in actions, multiplying by it again on the way back out. An earlier version of this sentence said "divide", naming the wrong operation and so forbidding nothing: an implementation that multiplied up to a per-kill rate, took the requirement over it to get kills, and charged the loop per kill broke no letter of the clause and over-charged every rung by a whole loop length.

For a prediction the round trip is exact and harmless, because the prediction is genuinely per-kill and dividing it once is how it arrives in the unit at all. For a MEASUREMENT it is not: the measurement never carried a kill count to recover, so the loop length used to recover one is the rung's model rather than the measurement's own, and the result is a number the observation does not support.
