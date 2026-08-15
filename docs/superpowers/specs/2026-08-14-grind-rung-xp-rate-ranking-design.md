# Rank grind rungs by skill-XP rate, not cheapest chain — design

**Date:** 2026-08-14
**Branch (proposed):** `fix/grind-rank-by-xp-rate`
**Status:** design, pre-implementation

**Follows:** the held-copies fix (`ec613f0d`, `ai/grind_probe_state.py`), which
removed a defect in the same selector and did not stop the symptom.

---

## Problem

A skill grind exists to raise a skill level, and a skill level exists to unlock
a crafting tier. The selector that picks which item to craft ranks candidates by
**cheapest chain to build**. Cheapness is not progress. The cheapest in-level
rung is systematically the lowest-level one, and the lowest-level one pays the
least XP per craft — so the ranking optimises against its own purpose.

Live, 2026-08-14, after the held-copies fix landed:

| Character | Chosen rung | `craft_level` | `acquire_steps` | Rung passed over | `craft_level` | `acquire_steps` |
|---|---|---|---|---|---|---|
| Lor | `apprentice_gloves` | 1 | 13 | `sticky_dagger` | 5 | 59 |
| HAL | `apprentice_gloves` | 1 | 43 | `water_bow` | 5 | 59 |

Both characters pick the rung that pays the least. The held-copies fix moved
`apprentice_gloves` from 0 steps to 13 and 43 respectively — a real repair of a
real defect — and it did not change either selection, because 13 and 43 still
beat 59.

The user's instruction: *"instead of selecting cheapest recipe, we should
maximize skill xp gain."*

---

## The four objectives this decision serves

The user named them:

> *"we need each player to help the other players, be able to efficiently
> skill-grind to unlock better crafting tiers, and be able to efficiently
> upgrade equipment with available inventory plus bank all in order to
> efficiently level-up to 50."*

Mapped onto what this selector can see:

1. **Help siblings** — the crafted rung, or its byproducts, serve another
   character's published demand.
2. **Skill-grind to unlock tiers** — XP per action toward the skill gate.
3. **Upgrade equipment from inventory + bank** — the crafted rung is itself a
   gear or tool target, so the craft produces a keeper rather than a throwaway.
4. **Reach level 50** — the objective all three serve; not separately visible
   here, since a skill grind pays no character XP directly.

Objectives 1 and 3 are **value of the byproduct**. Objective 2 is **rate**.
They share one denominator: actions spent.

---

## Audit: every key in the decision, and its live status

Seven keys. Four filters in `skill_grind_selection_pure`, three ranking keys in
`_beats`.

| # | Key | Role | Serves | Live status |
|---|---|---|---|---|
| F1 | `craft_skill == skill` | filter | 2 | alive |
| F2 | `craft_level <= current_level` | filter | 2 | alive; also hoisted into the producer for cost |
| F3 | `obtainable` | filter | 2 | alive |
| F4 | `xp_positive` | filter | 2 | alive |
| R1 | `wanted` desc | rank | 1, 3 | **DEAD** — see below |
| R2 | `acquire_steps` asc | rank | 2 (as cost) | alive, and effectively the only live key |
| R3 | `craft_level` desc | tie-break | 2 (as XP proxy) | alive only under exact integer cost equality |

### Finding 1 — `wanted` is dead in production

`GrindCandidate` is constructed at exactly one place in `src/`
(`tiers/skill_grind_target.py:268`), and that construction passes the literal
`wanted=False`, with a comment explaining that the standalone path has no
objective context. Every other construction is in `tests/` or `formal/diff/`.

So the key introduced on 2026-06-24 to stop the bot crafting a value-10
`apprentice_gloves` instead of the committed `copper_dagger` — the key the
`_beats` docstring says "survived the 2026-08-06 rework" — has not been able to
fire in production since the producer was written. The live symptom is the
identical item, `apprentice_gloves`, chosen for the identical reason.

Objectives 1 and 3 have **no representation at all** in the live ranking.

### Finding 2 — production ranks on one key

With R1 dead and R3 reachable only when two candidates have *equal integer*
`acquire_steps`, the live ranking is `acquire_steps` ascending and nothing else.
The three-key tower in the docstring describes a decision the code does not
make.

### Finding 3 — the existing tests cannot see this change

I initially estimated that "roughly five" of the 14 tests in
`tests/test_ai/test_skill_grind_selection.py` would flip under a rate ranking.
Working each one through both orderings by hand: **zero flip.** All 14 pass
identically under `acquire_steps` ascending and under `craft_level/acquire_steps`
descending.

The reason is structural. Every cost-versus-level test in the file uses a
`steps=0` candidate (a free rung wins both orderings) or an example where the
cheaper rung is *also* the higher-rate one — including
`test_deep_chain_loses_to_a_shallow_one_with_more_recipe_entries`, the
2026-08-06 regression guard, where 7-step gloves beat a 51-step sword on cost
(7 < 51) and on rate (0.143 > 0.098) alike.

Two consequences, and both are requirements on this work:

- The suite is **vacuous with respect to this key**. A green run proves nothing
  about the change. This is the same failure the branch predecessor shipped —
  a fix whose test stayed green with the defect reinstated.
- `test_craft_level_is_only_a_tie_break_under_cost` will still pass while its
  name and body assert something the code no longer does. A test that passes
  for the wrong reason is worse than one that fails; it must be rewritten in
  the same commit, not left green.

---

## Filter or rank key? The criterion

A key belongs in the **filter** set if and only if no value on any other axis
compensates for it. Otherwise it is a rank term, because excluding a
compensable candidate discards a point on the front.

- F1 — a rung in another skill pays zero XP toward *this* gate. No cost or
  value compensates zero. Filter.
- F2 — an out-of-level rung cannot be crafted at all. Filter. (It is also
  hoisted into the producer purely for cost; `test_out_of_level_candidates_
  cannot_change_the_selection` is the theorem that hoist rests on, and it
  survives this change unchanged, because the filters do not move.)
- F3 — an unobtainable rung cannot be built. Filter.
- F4 — a grey rung pays zero XP. `skill_grind_selection_pure`'s docstring is
  emphatic and it is right: *"a rung that pays ZERO is worthless at ANY
  `mats_missing`, so it must be excluded from the candidate set rather than
  merely ranked below."* A rate ranking does **not** weaken the case, and it
  is worth being precise about why, because the tempting argument is wrong:
  the numerator is `craft_level`, not XP, and a grey rung's `craft_level` is
  positive — greyness is a property of the *gap* to the character's skill
  level. So a grey rung can carry a perfectly good rate and win the ordering
  outright while paying nothing. The filter is the only thing standing between
  that rung and the 288-cycle Robby livelock, and it is also what returns `""`
  when every candidate is grey so the caller falls through to the gather arm.
  Filter, unchanged, and load-bearing under the new key exactly as under the
  old one.

**Four filters is the right number and these are the right four.** No fifth
candidate survives the criterion: sibling demand and gear-wantedness are both
compensable — a rung nobody wants but that pays triple XP is a legitimate
choice — so they are rank terms.

There is a fifth *constraint* in the system, `reserved` (do not consume the
committed objective's materials), and it deliberately is **not** a filter. It
is applied as a preference-with-fallback in `skill_grind_target` because
`LevelSkill.is_applicable` calls the selector with no context and
`level_skill_expand` calls it with context; if the reservation could empty the
candidate set, the two walks would disagree about whether a grind exists at
all. That is the selection-says-yes/emission-says-no split behind the wool
livelock. **This constrains the design below**: any context-dependent term may
change the *rank*, never the *membership*.

---

## Pareto analysis: how many rank keys, and in what shape

The axes that genuinely trade off:

- **A. XP gained per craft** (higher better)
- **B. actions to build one** (lower better)
- **C. byproduct value** — keeper for me (objective 3) or for a sibling
  (objective 1)

A three-key lexicographic tower over these returns an extreme point of the
front, not an interior one. The codebase has already made this argument, in
`ai/skill_grind_cost_core.py`, quoting the user directly:

> *"a single scalar in a single currency is the instrument for SELECTING a
> point on such a front — the same argument that retired `branch_pick_pure`,
> where a lexicographic pivot returned one extreme point and a scalar objective
> found the interior."*

The same file records the currency: **actions**. So A and B collapse into one
scalar — XP per action — and C is expressed in the same currency rather than as
a pivot above it.

### The ranking

Shown with Option A's placement of `wanted` (see the decision point below;
under Option B `wanted` is instead a lexicographic key above the rate, and
`effective_steps` is just `acquire_steps`):

```
(effective_steps = 0 if wanted else acquire_steps,
 craft_level / effective_steps   desc,     # XP-proxy per action
 craft_level                     desc)     # tie-break
```

Compared by **cross-multiplication, never float division**:

```python
if c.craft_level * best.effective_steps != best.craft_level * c.effective_steps:
    return c.craft_level * best.effective_steps > best.craft_level * c.effective_steps
```

Integer-exact, which the Lean model requires (it works over `Int`; floats in a
proved comparison are their own hazard), and division-by-zero-free: a rung at
zero effective steps makes the opposing product zero and wins on any positive
level, with two such rungs falling through to the `craft_level` tie-break.

Verified against the three live cases:

| Case | Rung A | rate | Rung B | rate | Winner | Old winner |
|---|---|---|---|---|---|---|
| R2D2 2026-08-06 | `apprentice_gloves` 1/7 | 0.143 | `sticky_sword` 5/51 | 0.098 | gloves | gloves |
| Lor 2026-08-14 | `sticky_dagger` 5/59 | 0.085 | `apprentice_gloves` 1/13 | 0.077 | dagger | gloves |
| HAL 2026-08-14 | `water_bow` 5/59 | 0.085 | `apprentice_gloves` 1/43 | 0.023 | bow | gloves |

The first row is the 2026-08-06 regression guard and it is **preserved**: the
new key agrees with the old one there. Rows two and three are the live symptom
and both invert. These figures are from the design-time probe and the
acceptance test must re-measure them, not trust this table.

### `craft_level` is an XP proxy, not XP — named as such

The server's published model is

```
XP = Round((XP_base + (content_level / skill_level) * k)
           * level_penalty * wisdom_bonus)
```

`XP_base` and `k` are not published and are not in the API. At a fixed skill
level, XP is monotone nondecreasing in content level — enough to justify
`craft_level` as an **ordinal** proxy, not as the **cardinal** numerator a ratio
needs, because `level_penalty` varies across rungs by a factor nobody has
measured. `learning/models.SkillXpObservation` records `<skill>_max_xp` per
level (the curve), not XP per craft, so the store does not close the gap either.

The honest position: the numerator is a proxy, the assumption is
`XP ∝ craft_level` at fixed skill level, and it is **unverified**. Two
consequences:

- The spec records it as a named assumption rather than a derivation. This is
  the class of claim that has cost this project the most — a docstring bound
  the code never satisfied, a unit error a structural diff could not catch.
- **In scope, bounded:** a replay task that fits observed craft XP against
  `(content_level, skill_level)` from the committed play-traces, exactly as
  `formal/diff/gather_xp_replay.py` established the grey band from 760 live
  gathers. Cycle rows carry `delta_skill_xp_json`. If the fit supports a better
  numerator, use it; if the traces are too thin, the task's deliverable is the
  measured statement that they are, and the proxy stands with its assumption
  documented and cited. Either outcome is a result; neither is a guess.

### Objectives 1 and 3: reviving `wanted`, and where it enters

Both need the same wiring, which does not exist today: `skill_grind_target`
takes no `SelectionContext`, so nothing can tell it that a rung is a gear
target or a sibling's need.

`SelectionContext` already carries every input required —
`near_term_targets` (usable-now gear ∪ tool targets), `target_gear`,
`target_tools`, and `supply_target` (the committed sibling-supply item, fed
from `CoordinationStore.sibling_demand`). `level_skill_expand` already holds a
`ctx` and already passes `ctx.step_profile` for the reservation. So the wiring
is: thread `ctx` into `skill_grind_target`, and set

```
wanted = code in ctx.near_term_targets or code == supply_target_code
```

Two constraints on that wiring, both load-bearing:

- **Membership must not move.** `LevelSkill.is_applicable` calls the selector
  with no context and asks only `is not None`. `wanted` affects rank only, so
  the two walks continue to agree that a grind exists. Stated explicitly
  because the reservation had to be built this way for the same reason.
- **The candidate cache stays context-free.** `build_selectable_grind_candidates`
  memoises on `(skill, level, equipment, inventory, bank, skills)`; folding
  context into that key multiplies the cache by objective state and would undo
  a fix that took a 47.0s producer down. `wanted` is applied *after* the cache
  read, by rebuilding the returned list with `dataclasses.replace` — never by
  mutating the cached list in place.

### Decision: where `wanted` enters the comparison

**RESOLVED 2026-08-14 — Option A.** The user approved the recommendation at
spec review. Option B is recorded below as the rejected alternative, not as a
live choice; an implementer who finds Option A unworkable escalates rather than
falling back to B.

**Option A (recommended): marginal-cost credit.** A wanted rung's chain is work
the character owes regardless of the grind, so the grind's *marginal* cost for
it is zero:

```
effective_steps = 0 if wanted else acquire_steps
```

Principled — it is the marginal-cost reading of "wanted", it introduces no
tuned weight, and it puts value in the same currency as cost, which is the
argument `skill_grind_cost_core` already makes. It also removes the extreme
point: a wanted rung wins on rate rather than by pivot, so among several wanted
rungs the highest-level one wins rather than the cheapest.

**Option B (conservative): keep `wanted` as the lexicographic primary key**, as
it is written today and as approved in the earlier design discussion. Smallest
diff, keeps `beats_prefers_wanted`-shaped proofs intact, and preserves the
existing four `wanted` tests verbatim. Its known cost is the extreme-point
pathology this project has already retired once elsewhere: a wanted rung at 500
steps outranks a throwaway at 2.

Both options need identical wiring; they differ only inside `_beats`.
**Recommendation: A.** Whichever is chosen, it is chosen here, in
review, and not by the implementer.

---

## Formal

`formal/Formal/SkillGrindSelection.lean` models `_beats` and the fold.

**Falsified and must be restated:** `beats_prefers_cheaper_chain` (line 271) —
"among candidates of equal `wanted` standing, a STRICTLY CHEAPER chain always
beats a costlier incumbent — regardless of craft level". Under a rate ranking
this is false, deliberately: a costlier chain that pays proportionally more XP
now wins. Its docstring calls itself "THE ROLE THAT WOULD HAVE CAUGHT ALL THREE
RECURRENCES", so it is replaced, not deleted:

- `beats_prefers_higher_rate` — equal `wanted` standing and
  `c.craft_level * b.effective_steps > b.craft_level * c.effective_steps`
  implies `_beats c (some b)`.
- `beats_prefers_cheaper_at_equal_level` — equal `wanted` standing, **equal
  `craft_level`**, strictly fewer steps implies `_beats`. This is the old
  theorem's surviving content: cheapness still wins where it is the only thing
  that differs, and stating it separately keeps the anti-regression guarantee
  the old theorem was carrying.

**Unaffected and must stay green:** `grind_actionable`, `fold_reaches_some`,
`fold_some_feasible`, `step_preserves_some`, `step_feasible_some`. Every one of
these is about the *filters* and the fold's shape, and the filters do not move.
That the liveness proofs survive untouched is itself evidence the filter set is
the right cut.

**Non-vacuity:** every new theorem's witness uses distinct nonzero levels and
distinct nonzero step counts. An all-zeros witness has passed the gate on this
project before while proving nothing.

`formal/diff/test_skill_grind_selection_diff.py` binds the Python core to the
Lean model and must be re-derived case by case, not rebaselined wholesale — and
it must gain at least one case where the two orderings disagree, for the reason
in Finding 3.

Mutation anchors for `_beats` must be refreshed in the same commit as the edit,
and must resolve to exactly one site.

---

## Testing

**Discriminating unit test, and the ablation.** The suite currently cannot see
this change, so the first requirement is a test that can:

```python
def test_a_costlier_chain_wins_when_it_pays_proportionally_more_xp():
    # Live Lor, 2026-08-14: a 13-step level-1 rung (rate 0.077) beat a 59-step
    # level-5 rung (rate 0.085) under cheapest-chain, and the grind sat at
    # weaponcrafting 8 for 757 cycles crafting the level-1 rung.
    cands = [_c("apprentice_gloves", level=1, steps=13),
             _c("sticky_dagger", level=5, steps=59)]
    assert skill_grind_selection_pure("weaponcrafting", 8, cands) == "sticky_dagger"
```

Prove it discriminates: with `_beats` reverted to `acquire_steps` ascending it
must FAIL. Paste both outputs into the report. A test that passes before the
change is not evidence of the change.

**Rewritten, not rebaselined.** `test_craft_level_is_only_a_tie_break_under_cost`
passes under both orderings while asserting the opposite of what the code will
do. Rewrite it to state the new rule, and name it in the commit message — a
silently-retained green test asserting a falsehood is the defect this section
exists to prevent.

**Preserved verbatim.** `test_deep_chain_loses_to_a_shallow_one_with_more_
recipe_entries` (the 2026-08-06 R2D2 guard) and
`test_out_of_level_candidates_cannot_change_the_selection` (the producer's
hoist theorem). Neither may be edited. If either needs editing, the design is
wrong.

**Filter tests unchanged.** All four filter tests, including the two grey-band
livelock tests, must pass without modification.

**`wanted` wiring tests.** That a gear target ranks above an equal-rate
throwaway; that a sibling `supply_target` does the same; that
`LevelSkill.is_applicable` and `level_skill_expand` still agree on *existence*
when the context differs; that the candidate cache returns the same list for
two different contexts (the cache-key constraint, asserted directly).

**Live acceptance — not fixture-only.** Probe real character state before and
after: Lor must select `sticky_dagger` or `fire_staff`, HAL must select
`water_bow`, neither may select `apprentice_gloves`. Earlier in this
investigation a fixture disagreed with live state and nearly produced the wrong
conclusion; a fixture-only acceptance is not acceptance here.

**Gate.** `bash formal/gate.sh` — one command, redirected to a file, never
piped into `tail`. Serialize it: the bot must not be running against `src/`.
The gate has not run since `ec613f0d`.

---

## Non-goals

- **Changing the four filters.** The audit concludes they are correct as a set
  and as a count. This design does not touch them. Whether every liveness
  proof does in fact survive untouched is a prediction, not yet a measurement;
  it is the check on that conclusion, and a proof that needs editing is
  evidence against the audit rather than a Lean chore.
- **A per-stat weighted objective across all skills.** `skill_grind_cost_core`
  argues against it: a hand-weighted per-stat term re-encodes the Pareto front
  instead of searching it, and every weight is a tuning surface nobody can
  calibrate. This design adds no tuned constant.
- **Making `acquire_steps` cheaper to compute.** Unrelated; the producer's
  measured cost was addressed on 2026-08-13.
- **The gather arm.** `LevelSkill.is_applicable`'s second disjunct grinds a
  gather skill by gathering, with no rung. Untouched.

## Residuals

- **`craft_level` as a cardinal XP proxy is unverified** (above). The replay
  task is in scope; if it cannot settle the question, the assumption stands
  documented and cited rather than silently assumed.
- **`craft_yield` is not in the ratio.** A recipe producing Y > 1 items costs
  one craft action and pays one craft's XP, so the numerator is right, but
  `acquire_steps` prices one unit and may over-count for a batching recipe.
  Not addressed here; named so it is not mistaken for handled.
- **Sibling demand enters only through `ctx.supply_target`**, a single
  committed item, not the full `CoordinationStore.sibling_demand` map. That is
  the smallest wiring that serves objective 1 with what already exists; a
  broader demand term would need a new context field and its own evidence.
- **`_cache_key` still omits `state.hp`**, a pre-existing gap recorded in
  `skill_grind_target` on 2026-08-13. Unrelated to this change and not fixed
  by it.
- **This is the fourth attempt at this ranking.** The prior three — `wanted`
  (2026-06-24), the `xp_positive` filter (2026-08-05), `acquire_steps`
  replacing `mats_missing` (2026-08-06) — were each real, and the `_beats`
  docstring's own verdict is that each "was patched by bolting another key onto
  this ordering rather than fixing the key that was lying". Changing the
  primary key is a different move from those. The history is still the reason
  for the preserved regression guard, the proven ablation, and the live
  before/after.
