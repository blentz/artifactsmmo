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

Every cost this oracle reports is a count of **executed planner actions** — one
action, one unit. It is not a duration. No wall-clock quantity may be multiplied
into or divided out of a reported cost, and no reported cost may be derived from a
cooldown, a latency, or any other measure of elapsed time.

This clause is load-bearing rather than pedantic: the quantity it constrains was
denominated in seconds while named for cycles, and every consumer of it was
therefore wrong by roughly the mean cooldown.

### S-005 · The cost of a rung counts the whole combat loop

The cost attributed to a rung counts every action the character must execute to
cross it, not only the attacking ones. Recovery the character is forced into by the
damage it takes counts; so does anything else the loop requires. A monster that
must be recovered from after every kill is more expensive per kill than one that
can be fought consecutively, and the reported cost must distinguish them.

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

Beatability is judged **from full hit points**, because recovery precedes a fight in
the executed plan and a mid-damage verdict would be more pessimistic than what the
character will really face.

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

### S-016 · A measurement supersedes the prediction, it does not merely may  [witness: W-002]

Where the observations contain a measured rate for a monster (S-0NN fixes what that means), the oracle uses it in place of the predicted one for that monster. This is not discretionary.

Candidates at one rung may therefore be priced from different origins -- a measured monster against a predicted one -- and that is intended. What S-008 requires is that both are expressed in the same unit before they are compared, not that they come from the same source.

### S-017 · A measured rate is restated for the rung it is used at  [witness: W-003]

A measured rate belongs to the character level its samples were taken at. Before it is used at a rung, the oracle restates it for that rung by the ratio of the published per-kill award for the same monster at the two levels.

The ratio is dimensionless, so the restated figure remains in the measured rate's own unit and S-008's same-unit requirement continues to hold.

Where the published award at the level the samples were taken is not positive, the measurement and the published rules disagree, no ratio exists, and the monster contributes nothing at that rung. Where the published award at the rung is zero, the ordinary arithmetic already yields zero and no separate rule is needed.

### S-018 · A measurement is present only when positive evidence backs it  [witness: W-004]

The observations contain a measured rate for a monster only when that rate is backed by at least one recorded kill and is itself positive. Anything else -- no entry, an entry with no recorded kill, a zero rate, a negative rate -- is an ABSENT measurement, and S-008's fallback to the published prediction applies.

An absent measurement is not an error and does not stop the walk. In particular a non-positive stored rate never reaches the zero-reward stop, which is a statement about what the published rules award and not about what has been observed.
