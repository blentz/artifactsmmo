# Synergy Weighting Between Short- and Long-Term Targets

**Date:** 2026-07-19
**Status:** DESIGNED — not scheduled, not built
**Supersedes:** the backlog note `docs/PLAN_synergy_weighting.md` added in 4c85df15 (idea
capture only; that file lives on branch `fix/dynamic-rest-cost` and is not on `main`)

---

## 1. Problem

A short-term target is not inherently good or bad. A 20,000-gather currency grind is bad
*in isolation*; it is reasonable when the gathers it demands are gathers the character
needs anyway. The bot currently judges every target on its own intrinsic gain and its own
staleness, and never asks whether the work it creates overlaps the work already planned.

Two observed consequences:

1. **Currency monopolisation.** `GatherMaterials(event_ticket, …)`, derived from an
   NPC-buy-only gear root, demands hundreds of gathers that serve nothing else. Even after
   the fall-off fix (365f6f25, 93c5a083) it competes on equal intrinsic footing with
   targets whose materials feed three other live roots.
2. **Task/grind competition.** The current task is a random skill grind. It contends with
   gear progression as an unrelated band-4 discretionary means, rather than being steered
   toward the skill a live gear target already needs. Task work and skill work are two
   lines of progress where they could be one.

Both are the same missing quantity: *how much of this target's work is work I need anyway?*

---

## 2. Architectural constraints discovered

These are load-bearing and were established by reading the code, not assumed.

### 2.1 Numbers die at the `decide_tree` boundary

There are two selectors with incompatible currencies:

| | Tree (`ai/tiers/progression_tree_core.py`) | Arbiter (`ai/arbiter_select.py`) |
|---|---|---|
| Currency | **cardinal** — `Fraction` gain, `falloff`, d'Hondt apportionment | **ordinal** — `band: int` + list position + `repr_` |
| Pool | gear candidates only | everything (guards, collect, step, task means) |
| Proof | mutation gate + discharged no-starvation liveness | **full triple gate** (extraction + differential + mutation) |

`Candidate` (`arbiter_select.py:44-57`) is `(goal, is_means, repr_, band)`. There is no
weight field. `Goal.value()` has exactly one non-test call site — `priority()`
(`goals/base.py:45`) — which has exactly one non-test call site, `player.py:824`, inside
`if self.verbose:`, interpolated into a log string. Thirty subclasses implement `value()`
and none of those numbers reach a decision.

### 2.2 The bands must stay ordinal

The bands encode **safety**, not a crude scoring proxy: a guard must precede, always.
Replacing the ladder with weighted selection would subordinate safety to arithmetic and
require rebuilding the triple gate around a weighted selector. This design does not do
that and no future phase should.

### 2.3 The unlock: cardinal computation, ordinal consumption

`select_pure` returns the **first** admissible candidate from a *pre-ordered* list.
Ordering within a band is built by `_build_candidates` (`strategy_driver.py:1126`), which
is **not** proven core. Therefore synergy may act as a *sort key* without `select_pure`
ever changing.

### 2.4 `strategic_value`'s `horizon` is a dead end

`strategic_value(stats, weights, efficiency_budget, horizon)`
(`ai/tiers/strategic_value.py:104`) accepts a `horizon=(num,den)` that looks like a natural
home for "long-term". It is not:

- it scales **only** the efficiency block and never combat, and `PURSUIT_WEIGHTS` makes
  combat dominate 1000:1 (`pursuit_value.py:43-54`);
- it has **zero production callers** — only `tests/test_ai/test_tiers_strategic_value.py`.

Wiring synergy through `horizon` would be inert. It is named here so the idea is not
re-proposed.

### 2.5 `means_serves` is already a synergy function

`means_serves(kind, goal, needs, state, game_data) -> bool`
(`ai/tiers/means_worth.py:36`) asks "does this means advance what the committed root
needs?" It is boolean, and wired only to `PURSUE_TASK`/`ACCEPT_TASK`; every other kind
returns `True` unconditionally. This design **generalises** it rather than adding a
parallel mechanism.

### 2.6 Requirement computation is smeared across six walks that disagree

There is no single call returning a target's full requirement set. There are **six**
distinct walks answering "what does obtaining X require", and no test anywhere asserts that
any two of them agree. Section 5 diffs them and specifies the unification.

---

## 3. The measure

### 3.1 Definition

```
A = demand-weighted requirement set of the candidate under evaluation
B = ⋃ requirement sets of live roots  \  A          (leave-one-out)

raw     = Σ_{i ∈ A∩B} demand_A(i)  /  Σ_{i ∈ A} demand_A(i)
synergy = S_MIN + (1 − S_MIN) · raw
```

`raw ∈ [0,1]`, `synergy ∈ [S_MIN, 1]`, all exact `Fraction` — no float in the decision path.

`B`'s members: the trunk `ReachCharLevel`, sibling gear candidates, the committed root,
and the current task's requirements.

### 3.2 Why the denominator is `A`, not `B`

The literal reading of "does A advance B" is coverage-of-B, `|A∩B| / |B|`. That fails here:
`B` spans the live objective closure, so every short-term candidate covers a vanishing
slice and all scores collapse toward zero — a near-constant multiplier, i.e. inert.

Normalising by `A` measures **waste**: "what fraction of the work this target creates is
work I need anyway". That is the problem statement restated. The currency grind is not
penalised for being large — it is penalised because almost none of its gathers serve
anything else.

Accepted consequence: a one-material target that shares that material scores 1.0 despite
being trivial. This is correct. Magnitude already lives in `gain`; synergy is a
dimensionless *purity* ratio. The three factors stay semantically disjoint:

```
weight = gain × falloff(focus) × synergy
         │       │                │
    magnitude  staleness       purity
```

### 3.3 Leave-one-out is mandatory

If `B` is the union of live roots' needs and `A` is itself a live root, then `A ⊆ B` by
construction, `raw = 1` for every candidate, and synergy is a constant — the same silent
no-op as §2.4. `B` must exclude `A`'s own contribution. This is what makes the number mean
*synergy* (overlap with the others) rather than *self-consistency*.

### 3.4 Degenerate cases

| Case | Result | Rationale |
|---|---|---|
| `A` empty (nothing to obtain) | `raw = 1` | A target needing no new work is maximally aligned. Not a division by zero. |
| `B` empty (no other live roots) | `raw = 1` uniformly | Synergy becomes a constant; tree degrades exactly to today's behaviour. |

### 3.5 `S_MIN = 1/3` — the anti-starvation invariant

`synergy` must be **strictly positive and bounded**. d'Hondt awards a seat to any
strictly-positive weight eventually — that is `interleaveDue_reaches`, discharged in
`formal/Formal/Liveness/InterleaveNoStarvation.lean:318`, resting on `minWeight_pos`.
Bounded-positive synergy therefore *preserves* the proof, multiplying the starvation bound
by at most `S_MAX/S_MIN = 3`.

**Invariant (load-bearing): synergy's dynamic range must stay strictly inside `falloff`'s.**
`falloff` spans 9:1 (`FOCUS_FLOOR = Fraction(1,9)`). Synergy spans 3:1. Aging therefore
structurally dominates alignment, which is also the correct semantics: *prefer aligned
work, but never let alignment justify grinding a dead root forever.* A high-synergy stuck
root still decays.

This invariant gets an explicit test, not a comment.

### 3.6 Curve shape reuses a proven one

`synergy = S_MIN + (1 − S_MIN)·raw` is an affine map of a normalised quantity into
`[S_MIN, 1]` — the same shape as `falloff`, which is `FLOOR + (1−FLOOR)·(1−t²)`. The Lean
obligations are structural twins of theorems already discharged in
`formal/Formal/ProgressionTree.lean`: `falloff_le_one:332`, `falloff_ge_floor:345`,
`falloff_floor_pos:378`.

### 3.7 Worked outcomes

**Currency grind.** `A = buy_only{event_ticket: N}`; overlap with `B` ≈ ∅ ⇒ `synergy = 1/3`
⇒ 3× suppression, compounding with `falloff` to 27× once stale.

**Task/grind convergence.** Task requires mining ⇒ `skill_xp{mining} ∈ B` ⇒ gear candidates
whose closure consumes mining score high and sort up. Task and grind become one line.

**Level-up preference.** Trunk's requirement set is `char_xp` ⇒ candidates whose closure
routes through `SourceKind.DROP` (monster kills) inherit alignment with levelling. The
user's "L50 slightly favoured" falls out mechanically rather than as a tuned constant.

---

## 4. Taskmaster selection

### 4.1 The lever is real

Upstream docs (https://docs.artifactsmmo.com/concepts/tasks/): *"The type of task you
receive depends on the Tasks Master you visit."* The choice is binary — `TaskType.ITEMS`
vs `TaskType.MONSTERS`. The player picks the **distribution**; the server rolls the draw.

Also established from the same page: task exchange costs **6 coins**; cancel costs **1
coin**; rewards are gold + task coins with **no XP**; monsters tasks pay more coins than
items at every level band (3/4/5 vs 2/3/4).

### 4.2 The bot currently cannot pull the lever

`ai/game_data.py:1398-1400`:

```python
elif ct == MapContentType.TASKS_MASTER:
    self._taskmaster_location = loc
```

One slot, two tiles, `content.code` discarded. The fixture
`tests/test_ai/scenarios/fixtures/gamedata_bundle.json` has `(1,2) → 'monsters'` and
`(4,13) → 'items'`. Last tile in iteration order wins; the other taskmaster is invisible.

This is the **same defect shape** as the ring2 starvation and the currency fall-off: a
keyed thing collapsed into a single unkeyed slot, making sibling contention structurally
invisible. Third occurrence.

Note the asymmetry: `_build_maps` keys `MONSTER`, `RESOURCE`, `NPC`, and `RAID` by `code`.
`TASKS_MASTER` is the one branch that does not.

It compounds — `AcceptTaskAction.apply` (`ai/actions/accept_task.py:33`) hardcodes
`task_type="monsters"` for the projected state regardless of which master was visited, so
the model asserts one type while the server may return the other, and nothing reconciles.

### 4.3 Expected synergy over a pool

```
pool(M)      = retained tasks with type_ == M.code and level ≤ char_level
E_synergy(M) = mean over the top TOP_QUANTILE of { synergy(requirement_set(t), B) : t ∈ pool(M) }
choose M     = argmax E_synergy(M)
```

**Reroll-aware aggregation.** A bad draw is cheap to discard — cancel costs 1 coin and
`LOW_YIELD_CANCEL` already exists — so a master's value is closer to "how good are its
*good* draws" than to its plain average. `TOP_QUANTILE` is an exact `Fraction` and degrades
to a plain mean at 1.

Rejected alternatives: **plain mean** washes out (both pools contain aligned and useless
tasks, so the means sit close and the lever goes soft); **max** assumes free rerolls and
would over-commit to a master on the strength of a task that may never roll.

### 4.4 Placement, and the cost trap

The argmax happens where `AcceptTaskGoal()` is constructed bare today
(`strategy_driver.py:382-383`), so the goal carries its chosen taskmaster.

**Synergy must never touch `AcceptTaskAction.cost`.** Costs are physical seconds feeding
A*'s `f = g + h`, with admissibility pinned in `formal/Formal/PlannerAdmissibility.lean`.
Smuggling a preference into cost re-introduces exactly the non-admissible heuristic that
`h = 0` exists to prevent (`ai/planner.py:128-141`). Synergy chooses the goal; cost stays
physical.

This placement also self-corrects §4.2's `apply` bug: once the goal names a master,
`task_type` is projected from that master's `code` instead of a literal.

---

## 5. Requirement-model unification (Phase 1, in detail)

Synergy needs one demand-weighted requirement set. Adding a seventh walk to produce it
would make the problem worse. Phase 1 therefore unifies the existing six.

### 5.1 The six walks

| Walk | Ply | State-aware | Namespace | Quantities | Crafting skill | Gathering skill | Monster drops |
|---|---|---|---|---|---|---|---|
| `recipe_closure` (`recipe_closure.py:195`) | closure | no | **resource-node** | no | no | no | **no** |
| `closure_demand` (`:258`) | closure | no | item | **yes** | no | no | no |
| `prerequisites` (`prerequisite_graph.py:69`) | **one ply** | **yes** | item | per-run only | no (deliberate) | no | yes |
| `objective_needs` (`objective_needs.py:69`) | closure +1 ply | yes | item | **no** | yes (names only) | no | yes |
| `_item_skill_gap` (`task_feasibility.py:44`) | closure | yes | item | no | **yes (levels)** | no | no |
| `obtain_sources` (`obtain_sources.py:146`) | **single item** | yes | item | `yield_per`/`capacity` | gate only | no | yes |

### 5.2 Which disagreements are legitimate

Two axes are **real** and must survive unification as explicit parameters, because
different consumers genuinely need different answers:

- **Axis 1 — edges vs closure.** `prerequisites` is deliberately one-ply; `tiers/strategy.py`
  does its own traversal on top. Collapsing this would break `act_step`.
- **Axis 2 — state truncation.** `prerequisites` treats an item as a **leaf** when any ready
  non-craft source exists (bank withdraw, licensed recycle, live gather, located vendor,
  winnable drop) and never descends its recipe. `recipe_closure`/`objective_needs` descend
  regardless of what is in the bag. Both are correct for their callers.

Everything below is **not** legitimate — it is drift, and Phase 1 removes it.

### 5.3 The four defects unification removes

**D1 — Namespace split.** `recipe_closure` returns **resource-node** codes (`copper_rocks`)
for raw leaves; every other walk speaks **item** codes (`copper_ore`). `craft_plan_gen.py:80-87`
documents keeping a hand-rolled DFS rather than "forcing a mismatched reuse."

**D2 — Drop-leaf blindness, with three independent workarounds.** `recipe_closure`'s two-set
return cannot represent a monster-drop leaf. `audit/craft_completeness.py:151-153` states it:
`feather` is *"neither a resource code nor craftable, so `recipe_closure`'s two-set return is
blind to it."* Three separate patches exist for this one hole — `objective_needs`' extra
`all_ingredients` ply (`:86-91`), `craft_completeness._closure_item_set`, and
`craft_plan_gen._closure_items`.

**D3 — Four near-identical crafting-skill-gate derivations**, none sharing code, all running
over the same `recipe_closure` result: `tiers/skill_gates.py:87` `gating_skills`,
`objective_needs.py:106-123` `skill_xp`, `goals/progression.py:253-283`
`UpgradeEquipmentGoal.gated_skill_levels`, and `craft_plan_gen.py:189-201`. They disagree on
output type: skill **names** (`objective_needs`), the single **worst** `(skill, req, cur)`
(`_item_skill_gap`), `{skill: SkillGate}` (`skill_gates`), and `(skill, level)` pairs
(`progression`).

**D4 — Three cycle policies, one of them nondeterministic.** Inside `recipe_closure.py`
alone: `_raw_units` uses a per-path copy returning **cost 1** on revisit (`:90-91`);
`_closure_demand` uses a per-path copy returning **nothing** on revisit (`:120-121`);
`_closure_visited` threads a **shared** map. Separately, `_item_skill_gap` uses a shared
mutable `seen` with no path semantics, making its result **dependent on `dict` iteration
order** whenever a diamond appears in the recipe tree. That is a latent determinism bug and
violates the project's no-incidental-ordering rule independently of this design.

### 5.4 Target shape — one substrate, several projections

One state-free walk; state-awareness applied afterward as a separate pass, not baked in.

```python
@dataclass(frozen=True)
class RequirementGraph:
    """Item-namespace, quantity-carrying, drop-aware. One cycle policy. State-free."""
    edges:      Mapping[str, Mapping[str, int]]   # item -> direct ingredient -> qty
    leaves:     Mapping[str, frozenset[SourceKind]]
    craft_skill:  Mapping[str, tuple[str, int]]   # item -> (skill, required_level)
    gather_skill: Mapping[str, tuple[str, int]]   # resource -> (skill, required_level)
```

Projections, each replacing a current walk rather than joining it:

| Projection | Replaces | Axis 1 | Axis 2 |
|---|---|---|---|
| `requirement_edges(g, item)` | `prerequisites` body | edges | truncation pass |
| `requirement_closure(g, roots)` | `recipe_closure` | closure | none |
| `demand_set(g, roots)` → `DemandSet` | `closure_demand` + `objective_needs` | closure | none |
| `need_set(demand_set)` → `NeedSet` | `objective_needs` return | closure | none |
| `skill_gates(g, roots, skills)` | **all four** of D3 | closure | none |

`DemandSet` is the quantified form synergy consumes; `NeedSet` becomes its unquantified
projection, so `objective_needs` and `means_serves` keep working at their call sites.
Memoised on read-set key (planner-memo lesson: memo key = read set).

### 5.5 Deliberately preserved

**Crafting-skill gates stay out of `prerequisites`' node output.** `prerequisite_graph.py:126-130`
omits them because skill grinding is planner-native via `UpgradeEquipmentGoal` +
`LevelSkill` (epic P3, commit `7b6b4408`). `ReachSkillLevel` **no longer exists as a type** —
it was deleted from `meta_goal.py`, `strategy.py`, `objective_needs.py`, `equipment_profile.py`,
`plan_tree.py`, and the Lean models. Re-emitting a skill node would: return an unactionable
step from `act_step` that `map_means` cannot dispatch (livelock); inflate `unmet_closure_size`,
which is the Tier-1 cost proxy that `_CHAR_LEVEL_BOOTSTRAP_HORIZON` is calibrated against;
and break the `PrerequisiteGraph.lean` / `StrategyTraversal.lean` differential gate.

The `RequirementGraph` therefore **carries** `craft_skill` as data — that is what lets D3's
four derivations collapse — while `requirement_edges` continues to emit no skill node. Data
availability and node emission are separated; only the latter was ever retired.

**Scoped `LevelSkill` admission stays scoped.** `progression.py:256-259` records that an
unconditional `skill_grind` admission fans every emitted `LevelSkill` into every search and
times out under load (the P2 `ff4401ac` regression). The unified `skill_gates` projection
must preserve per-target scoping, not return a global set.

### 5.6 A known hole, made explicit rather than inherited

**Gathering-skill gates appear in no walk.** Not `obtain_sources._gather_sources` (`:238-260`
gates on live tiles only, never `resource_skill_level`), not `objective_needs`, not
`prerequisites`. Only the action factory knows about it. This was the exact livelock
root-caused in `7b6b4408` (`iron_ore ← iron_rocks, mining 10`).

`RequirementGraph.gather_skill` exists so the unified model can *represent* it. Populating it
is cheap (the data is already in `GameData`). **Consumers opt in; no current consumer's
behaviour changes in Phase 1.** Wiring it into planning is explicitly out of scope here — but
a model that silently cannot express a known livelock cause is not a unification, so the
field ships even though this design does not use it.

### 5.7 Order of work — characterization before refactor

No test currently asserts any two walks agree, so there is no safety net and no record of
which disagreements are intentional. Therefore:

1. **Write the parity test first**, characterizing *current* behaviour across all six walks
   for a fixture corpus — including their disagreements, asserted as-is. This is the
   missing oracle, and it has standalone value.
2. Build `RequirementGraph` + projections.
3. Migrate consumers one at a time, parity test green at each step. Any diff is either an
   intentional fix (D1–D4) or a regression — the test forces the distinction.
4. Delete the superseded walks.

The existing censuses are the outer net and must stay green throughout:
`audit/obtain_parity_completeness.py` (whose docstring already names itself the intended
future oracle, carrying one declared asymmetry — the WITHDRAW carveout) and
`audit/craft_completeness.py`.

Lean surfaces that move in lockstep: `RecipeClosure.lean` + `Extracted/RecipeClosure.lean`,
`TaskReservation.lean` (`closureDemand`), `CraftPlanDriver.lean` (`craftPlan`), with
differential harnesses `formal/diff/test_recipe_closure_diff.py` and
`test_recipe_cost_memo_diff.py`.

### 5.8 Honest scoping

**Phase 1 is now larger than the rest of this design combined**, and is properly its own
epic that synergy depends on rather than a step inside it. It touches six modules, four
Lean files, two censuses, and roughly a dozen call sites.

It is also independently justified: D4's order-dependence is a live determinism bug, D2's
three workarounds are ongoing maintenance cost, and the parity test of §5.7 is missing
infrastructure regardless of whether synergy is ever built.

**Recommended sequencing:** land Phase 0, then Phase 1 as a standalone epic gated on the
parity test, then Phases 2–4. If Phase 1 proves larger than appetite allows, the fallback is
to build `DemandSet` as a seventh walk and defer unification — this is **explicitly the
inferior option**, recorded only so the trade-off is a decision rather than a surprise.

---

## 6. Phasing

### Phase 0 — Prerequisites (pure bug fixes, independently shippable)

| # | Change | Location |
|---|---|---|
| 0.1 | `taskmaster_tile` → `taskmaster_tiles: dict[str, tuple[int,int]]` keyed by `content.code` | `game_data.py:1398`, `location_catalog.py:26/135`, `game_data.py:189-194/655/1187` |
| 0.2 | Retain `type_`, `level`, `skill`, `min_quantity`, `max_quantity` in `_build_tasks`; add `tasks_for(type_, max_level)` accessor | `game_data.py:1656` |
| 0.3 | `AcceptTaskAction` carries master code; `apply` projects `task_type` from it | `ai/actions/accept_task.py:33`, `ai/actions/factory.py:59-69` |

0.2 is nearly free — `_fetch_tasks` (`game_data.py:1642`) already pulls the whole pool
unfiltered and `_build_tasks` discards these fields. **`CACHE_VERSION` must be bumped**
(cache key changes with retained fields).

`factory.py:59-69` currently constructs `AcceptTaskAction`, `CompleteTaskAction`,
`TaskExchangeAction`, `TaskCancelAction`, and `TaskTradeAction` against one literal tile.
Each must be re-pointed per §8 residual R1.

### Phase 1 — Requirement-model unification

Specified in full in §5. One `RequirementGraph` substrate with five projections replacing
six divergent walks; parity test written first as a characterization oracle; `DemandSet` is
the quantified projection synergy consumes, `NeedSet` its unquantified form.
`means_serves` reduces to `synergy(...) > S_MIN` — the boolean special case.

Per §5.8 this is properly its own epic that synergy depends on, and is independently
justified by the determinism bug D4 and the missing parity oracle.

### Phase 2 — Synergy core

Pure, integer/`Fraction` only, **shipped extracted** (new cores ship extracted;
`progression_tree_core` currently carries only the mutation leg — see §7).

Theorems: `synergy_le_one`, `synergy_ge_floor`, `synergy_floor_pos`, and monotonicity in
shared demand. Structural twins of §3.6.

### Phase 3 — Tree call site

`_scaled_weights` (`progression_tree_core.py:181`) takes a synergy map;
`focus_aging_pick`/`focus_aging_order` signatures widen. `falloff`, the curve, and
`dhondt_step` are **untouched**. `formal/Formal/ProgressionTree.lean` updates in lockstep.

Explicit test for the §3.5 invariant: the starvation bound is multiplied by at most 3.

### Phase 4 — Taskmaster choice

Implements §4.3/§4.4. Depends on Phase 0 and residual R1 being resolved.

### Phase 5 — Within-band ordering

`DISCRETIONARY_ORDER` (`ai/tiers/means.py:66-78`) sorted by synergy instead of being a
fixed tuple. `select_pure` and its triple gate are never opened.

**Misgiving, recorded at the user's request.** Phases 0–4 may already deliver the entire
worked example: Phase 3 fixes gear ranking, Phase 4 fixes which task distribution is drawn
from, and the task/grind convergence of §3.7 arrives through `B` without any reordering.
Phase 5 then adds a knob to an already-corrected ladder, and its benefit is speculative —
it reorders means that the worth gate has *already* admitted, so the marginal effect is
"which admitted means goes first", not "which means is chosen". It also perturbs an
ordering that several proofs read positionally.

**Recommendation: specify Phase 5, but defer implementation pending live evidence** that
discretionary ordering is actually mis-serving after 0–4 land. Build it only if a trace
shows a genuinely aligned means losing to a less-aligned one within the same band.

---

## 7. Verification strategy

| Concern | Approach |
|---|---|
| Synergy core correctness | Extraction + differential + mutation (full triple gate) |
| Tree integration | `ProgressionTree.lean` lockstep; existing mutation group extended |
| Anti-starvation preserved | Explicit test of the §3.5 range invariant; `interleaveDue_reaches` re-checked |
| Identity churn excluded | Test that synergy **cannot** enter `repr_` — structurally excluded, not merely avoided (the currency-grind lesson: a moving value inside goal identity resets sticky-commit keying) |
| Runtime activation | Must fire on live `plan <char>`; green tests ≠ runtime-active |
| Planner completeness | Census gate stays green |
| CPU | Memo hit-rate asserted; `N` ≈ 10–20 closure walks/cycle |

---

## 8. Residuals — stated, not hidden

**R1 — Which taskmaster can complete/exchange a given task is ASSERTED, not probed.**
The docs say exchange works at "any Task Master"; **completion is unspecified**. This is
the same trap as the duplicate-artifacts server rule (asserted, never probed). Phase 0 must
probe this live and record the result before Phase 4 depends on it. If completion is
master-specific, `CompleteTaskAction` must route to the issuing master and the travel cost
of a mis-chosen master becomes part of §4.3's economics.

**R2 — Weight churn.** `B` moves as live roots change, so synergy moves cycle-to-cycle and
d'Hondt apportionment could thrash. Believed benign: `falloff` already moves every cycle
via focus bumps, the seats ledger is built for moving weights, and synergy is outside goal
identity. This is an assumption to instrument, not a proven property.

**R3 — CPU.** `N` ≈ 10–20 requirement-set computations per cycle plus a union. Memo is
designed in (Phase 1), not deferred, given the feather_coat 99%-CPU precedent.

**R4 — `TOP_QUANTILE` is an unvalidated constant.** Introduced by the reroll-aware
aggregator. No principled derivation exists yet; it will need calibration against live
traces the way `FOCUS_FLOOR = 1/9` was calibrated against the Robby trace.

---

## 9. Explicitly out of scope

- Making `Candidate` carry a weight, or replacing the band ladder with weighted selection (§2.2).
- Any change to `select_pure`.
- Any change to `falloff`, the d'Hondt curve, or `dhondt_step`.
- Reviving `strategic_value`'s `horizon` parameter (§2.4).
- Putting synergy into the planner heuristic or any action cost (§4.4).
- Reward-value optimisation of taskmaster choice (the coin/gold tables of §4.1 are noted
  but not used; this design selects on synergy alone).
