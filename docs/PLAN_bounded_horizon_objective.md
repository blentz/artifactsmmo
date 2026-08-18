# EPIC SCOPE: A bounded horizon for the unified objective

Status: scope only, 2026-08-17. No code, no task list yet. The measurements below
are live and reproducible; the design question at the end is open.

Supersedes `docs/PLAN_iron_gear_acquisition_tasks.md`, which is a symptom fix on a
decision path that does not run. The evidence in
`docs/PLAN_iron_gear_acquisition.md` stands and feeds this.

---

## 1. What S-014 says, and why the fallback exists

`docs/spec_unified_objective/SPEC.md`:

> **S-003 · The objective is cycles to character level 50.**
>
> **S-014 · Unreachability is carried by the level field alone.** A candidate's
> objective is unreachable exactly when its outcome's highest reachable level is
> below 50. […] when it holds, the outcome's cycles-to-50 figure carries no
> meaning and is not compared.
>
> **S-006** […] Among unreachable candidates, one that reaches a strictly higher
> character level than another ranks strictly better; among those reaching the
> same highest level, a strictly smaller **acquisition cost** ranks strictly
> better.

S-006 is not a hedge someone added defensively. It is forced: once S-014 declares
cycles-to-50 void in that band, ranking on it would compare two numbers the spec
just voided, so acquisition cost is the only cycle-denominated figure left. Given
S-003 and S-014, S-006 is the correct clause.

The fault is upstream of it, in S-003's choice of a **fixed, distant target**. And
the spec records the consequence in its own voice, in the S-009 withdrawal note —
as an argument for why a guard was unnecessary:

> **UNREACHABLE band: same reachable level, so S-006's second key (acquisition
> cost) already prefers the trunk's zero over any positive cost.**

That is stated as a safety property. It is in fact the entire behaviour.

## 2. The measurement: both arms of the trade-off are inert, and each hides the other

Over 10,716 live decision cycles (5 characters, 2026-08-16/17 traces):

```
cycles where ANY candidate had a finite J            :      0 / 10716
cycles where every candidate shared reachable_level  :   8769 / 10716   (82%)
S-006 argmin winner:  xp_trunk 8769    weapon_slot 1895    artifact 27
```

`objective_j` has never executed. Where key 1 ties, everything falls to key 2,
`acquire_cost`, where the trunk sits at 0 by construction and wins 8,769/8,769.
The 1,895 weapon wins are `greater_wooden_staff` — the 18% of cycles where
`reachable_level` differed, because under a frozen loadout a weapon is the only
thing that visibly moves the ceiling. `branch_objective`'s docstring predicted
exactly this and said so.

A representative row: `ring_of_the_adept` costs **3 actions** and loses to the
trunk's **0**. So the iron-gear wall at 1,000,001 is not why iron gear is never
built. At its honest price of ~424 it loses the same way.

**This is the reason the work feels like epicycles.** There are two arms:

| arm | state |
|---|---|
| cost — `acquire_cost` | six routes, state-aware, formally proved, memoised, four epics deep |
| benefit — `cycles_to_fifty` | void for the entire early and mid game |

Each arm's inertness makes the other arm's defects unobservable. Any fix to the
pricer ships green and changes no decision; any fix to the horizon is swamped by a
10^6 sentinel. Every refinement therefore looks like it should have worked and
didn't, which is precisely the shape that invites another correction on top.

## 3. The bounded horizon already exists — one layer up

`ai/tiers/progression_tree_core.py`:

```python
TRUNK_CAP = 50
BAND = 10

def milestone_pure(level: int) -> int:
    """Next trunk milestone: min(50, (level // 10 + 1) * 10)."""
    return min(TRUNK_CAP, (level // BAND + 1) * BAND)
```

`progression_tree.py:529` builds `trunk = ReachCharLevel(level=milestone_pure(state.level))`.
That is why the traces show `ReachCharLevel(level=20)` for a level-16 character.
It is proved in Lean — `Formal.ProgressionTree` carries `milestone_gt_level`,
`milestone_le_cap`, `milestone_band_aligned`, `milestone_advances`, all
axiom-clean.

**So the goal layer plans to the next ten-level milestone while the objective that
ranks candidates against that goal asks whether they can reach 50.** And
`cheapest_path_to_level(target_level, ...)` is already parameterised — the target
is an argument. `branch_objective._outcome` passes the module constant `TARGET_LEVEL`.

Prior horizon attempts are visible in the tree as unrelated constants in unrelated
modules, none of them the objective's: `inventory_caps.RECIPE_SKILL_HORIZON = 2`,
`progression_reserve._HORIZON`, `prerequisite_graph._CHAR_LEVEL_BOOTSTRAP_HORIZON = 2`,
and `strategic_value`'s `horizon: tuple[int, int]`. Four horizons, four scopes, and
the objective reads none of them.

## 4. But banding alone is NOT enough — measured, not argued

Counterfactual probe on the live fleet: run `branch_ranking` as shipped, then again
with `TARGET_LEVEL` patched to `milestone_pure(state.level)`.

**Lor, level 16, milestone 20 (four levels of headroom):**

```
                                    cost      cycles_to_target      J
xp_trunk                               0                  2517   2517
artifact2_slot:lich_race_medal        96                  2505   2601
boots_slot:iron_boots            1000001                  2288   ...
body_armor_slot:adventurer_vest  1000001                  2474   ...
shield_slot:iron_shield          1000001                  2517   ...
```

The benefit term **discriminates**: `iron_boots` saves 2517 − 2288 = **229
cycles** over the band; `adventurer_vest` saves 43; `lich_race_medal` saves 12;
`iron_shield` saves 0 (pure resistance never changes which monster the walk picks).

**R2D2, level 19, milestone 20 (one level of headroom):**

```
xp_trunk                               0                   212    212
artifact2_slot:lich_race_medal        98                   212    310
shield_slot:iron_shield          1000001                   212   ...
```

Every candidate: **212**. The benefit term is flat and J degenerates to
`argmin(acquire_cost)` — the trunk again.

So the horizon has two degenerate ends, and the shipped constant sits at one of
them:

- **too far (50)** — nothing reaches it, J is void, S-006 falls to cost, trunk wins
- **too near (1 level)** — every candidate ties on benefit, J reduces to cost,
  trunk wins

Both collapse to "doing nothing is cheapest". A ten-level milestone is right in the
middle of the band and wrong at its edges, because a milestone horizon is measured
in **levels** while the quantity being compared is measured in **cycles**, and the
cycle-distance to the next milestone varies from 212 to 2,517 depending only on
where in the band the character happens to stand.

## 5. What the two fixes are worth together

Neither alone changes a decision. Together they produce, for the first time, an
answer with a reason:

- Lor's `iron_boots` **saves 229 cycles** to the milestone.
- Lor's gearcrafting 7→10 unlock alone costs ~496 cycles (spec table).
- So for Lor, right now, iron boots are an **honest loss** — and the system can say
  so and say why, instead of arriving at the same verdict by degenerate accident.

That distinction is the whole point. It also sharpens the fleet-amortisation
question already parked in `PLAN_iron_gear_acquisition.md` increment 4: one
character paying the 496 once and supplying four is a materially different trade,
and only an objective that runs can evaluate it.

## 6. Open design question — the one thing to settle before any task list

**A: milestone horizon with a floor.** Target `max(milestone_pure(level),
level + MIN_LOOKAHEAD)`. Minimal change, reuses a Lean-proved function, keeps the
level-denominated band shape. Cost: `MIN_LOOKAHEAD` is a new tuning constant with
no principled value, and the flat-benefit end is pushed around rather than removed.

**B: fixed cycle budget.** Invert the objective: instead of *"cycles to reach a
fixed level"*, ask *"progress made within N cycles"*. Cost is deducted from the
budget; benefit is levels or XP gained in the remaining `N − acquire_cost`.
Invariant to position within a band, so neither degenerate end exists. `N` is a
single tunable that directly expresses planning depth. Cost: this rewrites S-003,
S-004, S-005, S-006 and S-014 and the proved core `tiers/progression_choice.py` —
a real spec-and-proof epic, not a constant change.

**C: one iterative walk — let the projection SPEND cycles on acquisition.**
A and B both keep two arms and combine them at the end: cost from one machine
(`acquisition_cost`'s route walk), benefit from another
(`cheapest_path_to_level`'s rung walk), added or budgeted together. C removes the
seam instead of tuning it.

`cheapest_path_to_level`'s rung loop is *already* the iterative machine this needs.
Per rung it re-equips from inventory ∪ equipped at the rung's level, charges equip
actions when `worn` changes (S-020), projects `max_hp` growth and the rung
loadout's wisdom, picks the best monster by XP rate, and accumulates cycles. The
one thing it cannot do is **acquire** anything mid-walk — it only re-equips what is
already held.

Add that single edge and the arms collapse into one loop:

* **cost** is not a term added at the end — it is cycles spent inside the walk;
* **benefit** is not a separate projection — it is the walk finishing sooner;
* **`J`** is just *the total cycles the walk took*. One number, one machine.

The candidate layer disappears with it. `trunk_candidate` was "the walk that buys
nothing" — a path the walk considers, not a competitor. `gear_candidate` was "the
walk with one item pre-placed in inventory" — the walk now decides that itself.
Gone too: `rank_candidates`, `candidate_band`, `objective_j`, the
FINITE/UNREACHABLE split, S-006's fallback key, and **S-014 itself** — because
`blocked → inf → unreachable` stops existing once the walk can buy the gear that
unblocks it.

**Why C beats A and B on the case that started this.** A and B price each candidate
in isolation, so the gearcrafting 7→10 unlock — a *shared prerequisite of five
pieces* — is charged in full to whichever piece is being priced. Lor's `iron_boots`
is billed the whole ~496 cycles, saves 229, and loses. So is `iron_helm`. So is
each of the other three: five candidates independently rejected for a cost they
would have shared. The walk pays it once, `acquisition_cost_core`'s pay-once `paid`
dict amortises it, the next four pieces are cheap, and the walk sees the
compounding. Neither A nor B can express that.

**Degeneracies, checked.** R2D2 one level from its milestone: no upgrade repays
inside a short walk, so the walk buys nothing and grinds — the same verdict as
today, but reached because nothing repays rather than because doing nothing costs
zero. Level 16 against target 50: no unreachable band, because the walk buys what
unblocks it.

**Recommendation: C — and the spike has now measured all four of its risks.**
`docs/PLAN_objective_spike.md` carries the numbers; every kill criterion cleared.
C is the only option where cost and benefit are the same quantity by construction
rather than by unit-matching, the only one that amortises a shared prerequisite
(**74%** on the live iron set), and the only one that deletes more than it adds.
On COST it is roughly **neutral**, not cheaper: E4's first estimate said 4x
cheaper and was corrected on 2026-08-18 — it priced a per-rung candidate
evaluation at the `acquisition_actions` call (47–68 ms) when it actually costs a
rung's whole monster loop (~235 ms measured). C is therefore worth building for
coherence and for the amortisation, NOT for speed, and it carries a design
obligation: an incremental candidate evaluation, because the naive
re-run-the-rung shape is what makes it cost-neutral. B remains the fallback if
that cannot be found; A remains a stopgap only.

**One ordering constraint is now hard.** Increment 2 (the pricing wall) must land
BEFORE increment 3 (the acquisition edge). The largest shared cost in the model is
the skill unlock, it exists only where a grind rate does, and live that rate is
0.0 for every character and every crafting skill — so every candidate carrying one
is walled today. Building C first yields a walk that can buy nothing worth buying,
and it would read as inert for a reason that has nothing to do with C.

All three subsume the machinery already built rather than competing with it.
`skill_grind_selection`'s xp-rate ranking (1bef7388 — ranked by rate, not cheapest
chain, and that must not regress) and the monster xp-rate selection inside the rung
body are the same quantity the objective needs: one rate model with three readers,
instead of two that disagree.

**C's honest costs.**

* *Greedy is not optimal.* Take-if-payback-fits at each rung is a heuristic. That
  is acceptable — the shipped objective is not coherent, so greedy-with-a-reason is
  strictly better — but it must be stated in the spec, not discovered later.
* *Termination needs a proof.* The walk must not buy forever.
  `Formal.ProgressionTree.milestone_advances` is the precedent for the shape.
* *Performance — and the spike's E1 has already overturned the assumption here.*
  `branch_objective`'s docstring claims ~30ms per walk, ~300ms for a 9-candidate
  decision. Measured live 2026-08-18 inside the same search cache: **479–2,828 ms
  per walk**, and Lor's full 12-candidate ranking takes **33.9 s** — longer than
  the ~30 s cooldown it is meant to fit inside. Cost is per-rung (~283 ms), so
  today's shape is `candidates × rungs × rung_cost`.

  That is a live defect in its own right, and it *helps* C rather than hurting it:
  C restructures the same work to `rungs × (rung_cost + candidates × acq_cost)`,
  paying the expensive per-rung term once instead of once per candidate. Whether C
  is cheaper turns on the `acq_cost` term, which E4 must measure — but the
  pre-spike framing ("C might be too slow") had the baseline wrong by two orders
  of magnitude. `adventurer_vest`'s 10.1M-call blow-up at this seam still makes
  the measurement mandatory.
* *Spec surface is larger than B* — it replaces S-003 through S-014 — but the
  result is smaller: no bands, no void figures, no fallback key, no candidate
  construction.

## 7. Provisional increments (contingent on the spike)

**Increment 0 is the spike, and it is specced separately in
`docs/PLAN_objective_spike.md`.** It answers C's two open questions — does the
ranking change, and what does the walk cost — without touching the decision path,
by building the diagnostics the objective has never had. Everything below is
contingent on its verdict.

1. **Make the target a parameter.** `_outcome` and `progression_choice` take the
   target rather than reading a module constant. Pure refactor, no behaviour change
   while the caller still passes 50 — so it can land and be verified alone, and the
   spike's horizon sweep needs it.
2. **Fix the pricing wall.** The two increments from
   `PLAN_iron_gear_acquisition.md` that survive: route existence at restorable HP,
   and a grind rate that does not decay to zero. Still individually inert, but the
   walk cannot produce a correct answer while a real route prices at 10^6.
3. **Land the acquisition edge in the rung loop** (C), with the spec clauses
   rewritten and the Lean core updated in lockstep. This is where
   `branch_objective`'s candidate layer and `progression_choice`'s banding are
   deleted.
4. **Re-run the spike's experiments** and diff against the baseline it recorded. A
   ranking that did not change means the epic is inert and something above is still
   swamping it.
5. **Only then** revisit the five compensating factors in `focus_aging_pick` —
   focus ledger, d'Hondt interleave, synergy, achievability, role. Hypothesis,
   untested: they exist to compensate for a payoff term that never worked, and a
   working one may retire several. Each was calibrated against a live trace, so
   this is a measurement exercise, not a deletion.

## 8. Residuals

- The 82%-tie and 0-finite figures are trace-scoped (2 days, 5 characters).
  `j_ranking` is not persisted to `learning.db`, so this cannot be checked over the
  full history. Corroborated independently by `branch_objective`'s own docstring
  ("Measured across 14 committed scenarios: every candidate unreachable in all 14").
  Persisting `j_ranking` to the store is worth doing regardless.
- `cheapest_path_to_level` freezes the loadout after applying the candidate's item.
  A shorter horizon makes that approximation less wrong, but does not remove it.
- `iron_shield` saving 0 cycles is correct under a walk that ranks monsters by XP
  rate: resistance changes survivability, not the cheapest-monster choice. Whether
  the benefit term *should* see survivability is a separate question this scope
  does not answer.
- R2D2's flat 212 is the honest answer for a character one level from its
  milestone. Any horizon design must state what it does at a band edge rather than
  inheriting whatever falls out.
