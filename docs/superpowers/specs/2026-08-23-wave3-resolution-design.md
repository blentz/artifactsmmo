# Wave 3 — graph resolution replaces the ranking

Date: 2026-08-23
Status: DESIGN, not authorised for implementation
Author task: `.superpowers/sdd/PLAN_goal_decision_graph_waves_3_6/task-3.1-brief.md`
Parent spec: `docs/superpowers/specs/2026-08-22-goal-decision-graph-design.md`
Worktree read: `/home/blentz/git/artifactsmmo/.worktrees/waves-3-6` at `1bffc75e`

---

## 0. Headline conclusions

1. **Wave 3 is three plans, not one.** The resolution cutover (3a), the deletion
   of the ranking machinery (3b), and the commitment/memo question (3c) have
   different risk profiles, different gates, and different failure modes. 3c
   should be a *gated investigation* in the shape of task 5.3, not a deletion
   task — the spec puts `_committed_repr` and the doomed memo on the deletion
   list and both are arbiter machinery with live Lean bindings, not ranking
   machinery.

2. **The spec's replacement measure `(tier, character level, skill level,
   materials outstanding)` does not survive contact with the Lean — but not
   because it is wrong. It answers a different question.** §4 of the parent spec
   claims this tuple "replaces today's three-measure F/D/E descent in the Lean
   liveness development". It does not and cannot: that tuple is a measure over
   the *resolution walk* (state frozen, one cycle), while F/D/E and `FMeasure`
   are measures over the *cycle trajectory* (state moving, many cycles). As a
   walk measure it is nearly free and mostly redundant with `MAX_RESOLVE_DEPTH`.
   As a trajectory measure two of its four components are unsound — §4.3 gives
   the counter-instances.

3. **No Lean theorem breaks in wave 3.** Two of the fifteen `ExtMeasure`
   components are functions of the meta-decision (`skillXpDeficitProjected`
   through `targetSkillLevel`, and `objectiveStepFlag` through
   `objectiveStepFires`); the other thirteen are functions of state alone. Both
   ranking-dependent slots are *deliberately excluded* from `FMeasure`, the
   16-slot measure that carries today's unconditional-descent capstone
   `ai_reaches_fifty_unconditional`. The Lean work in wave 3 is **deletion and
   manifest hygiene, not restatement** — plus two genuinely new obligations
   (§4.5) that nothing discharges today.

4. **`J` is deletable, but deleting "J" is not deleting `branch_ranking`.** `j`
   is `null` on every root because every candidate lands in the *unreachable*
   band, where `sort_key` never reads `objective_j`. The rest of
   `branch_objective` — `branch_from_ranking` (the live GEAR-vs-XP pivot) and
   `justifying_identities` (the live eligibility filter) — runs on the
   `(band, TARGET_LEVEL - reachable_level, acquire_cost)` key and **decides every
   cycle**. Deleting it is a real behaviour change, not a dead-code removal. This
   is the task-5.3 pattern repeating: the value is dead, the machinery around it
   is live.

5. **Wave 2 shipped `gear_targets_with_blockers` with zero production
   consumers.** `grep -rn gear_targets_with_blockers src/` returns exactly one
   hit — the definition. The "MaxGearForLevel replaces near_term_gear's
   attainability filter with a blocker subgoal" half of wave 2 step 4 produced
   the data source and never wired it. Wave 3a must consume it or the
   weaponcrafting fix stays half-installed.

---

## 1. Consumer inventory

### 1.1 `StrategyDecision` — every field, every consumer

Definition: `src/artifactsmmo_cli/ai/tiers/strategy.py:277-348`.

| field | type | production readers | notes |
|---|---|---|---|
| `interrupt` | `str \| None` | 1 (`to_trace`) | always `None` from `decide_tree` (`progression_tree.py:770`); trace-shape compatibility only, per its own comment |
| `chosen_root` | `MetaGoal \| None` | 4: `strategy_driver.select:938`, `plan_tree.build_plan_tree:139/143`, `player.py:743/764/2701`, `to_trace` | **the contract surface** |
| `chosen_step` | `MetaGoal \| None` | 4: `strategy_driver.select:937`, `plan_tree._expand:68`, `player.py:763`, `to_trace` | **the contract surface** |
| `desired_state` | `dict` | 1 (`to_trace`) | always `{}` from `decide_tree`; its own comment says "no consumer reads desired_state off the decision post-flip" |
| `ranking` | `list[RootScore]` | 4 (see §1.2) | display + one snapshot field |
| `fallback_steps` | `list[MetaGoal]` | 3: `select:939`, `_resolve_step_goal:1094/1103`, `_build_candidates:1319`, plus `player.py:766` (crafting_target scan) | **load-bearing, not display** |
| `fallback_roots` | `list[MetaGoal]` | 3: same sites, index-paired with `fallback_steps` | **load-bearing** |
| `aged_pick` | `bool` | 1: `player._bump_focus:581/588` → `_charge_focus` → d'Hondt seat bump | dies with the arbiter |
| `promoted_from` | `MetaGoal \| None` | 1: `player.py:742/756-761` (`_last_servability_diag`) | diagnostic only, by its own docstring |
| `j_ranking` | `list[ProgressionCandidate]` | 2: `to_trace:342`, `progression_tree:753/756` (feeds `_j_by_identity`/`_reach_by_identity`) | dies with J |

Test-side readers of `.ranking`: 5 files —
`tests/test_ai/test_branch_objective.py`, `tests/test_ai/test_progression_tree.py`,
`tests/test_ai/test_tiers_strategy.py`, `tests/test_ai/test_role_alignment.py`,
`tests/test_ai/scenarios/test_band_liveness.py`.

### 1.2 `RootScore` — every field, every consumer

Definition: `src/artifactsmmo_cli/ai/tiers/strategy.py:231-274`.

| field | production readers | where |
|---|---|---|
| `root_repr` | 4 | `plan_tree.py:146` (chosen-row lookup), `plan_tree.py:161-166` (stub label), `player.py:2705` → `RootScoreView`, `commands/plan.py:80` |
| `category` | 4 | `plan_tree.py:152` (detail string), `plan_tree.py:165`, `player.py:2705`, `commands/plan.py:80` |
| `contribution` | **0 readers** | written twice (`progression_tree.py:272`, `:754`), serialised once by `asdict` in `to_dict:271`. Nothing in `src/` or `tests/` reads `.contribution` off a `RootScore`. |
| `cost` | **0 readers** | written as the literal `0` at both write sites. Nothing reads it. |
| `score` | 3 | `plan_tree.rank_detail:49` (third case only), `player.py:2706` → `RootScoreView.score` → `tui/widgets/log_pane.py:96,99`, `commands/plan.py:81` |
| `step_repr` | 2 | `player.py:2706` → `RootScoreView`, `commands/plan.py:82` |
| `instrumental` | **0 readers in `src/`** | one test pins it always-`False` (`test_tiers_strategy.py:206`) |
| `j` | 1 | `plan_tree.rank_detail:45` |
| `reachable_level` | 1 | `plan_tree.rank_detail:47` |

`rank_detail` (`ai/plan_tree.py:26-49`) is the single funnel for `j` /
`reachable_level` / `score`, and `commands/plan.py:79` imports it explicitly so
"the CLI and the TUI plan pane never disagree about a cycle". Keeping that one
funnel is what makes the display migration a two-line change.

### 1.3 The TUI path

`player.py:2704-2708` projects each `RootScore` into a `RootScoreView`
(`ai/cycle_snapshot.py:8-14`: `root_repr`, `category`, `score`, `step_repr` —
no `j`, no `reachable_level`, no `contribution`, no `cost`). The only reader is
`tui/widgets/log_pane.py:89-101`, which prints `category` and `score:.2f` for the
chosen root plus two alternates. The plan **pane** reads `plan_tree`, not
`strategy_ranking`; the log **pane** reads `strategy_ranking`. Both are display.

### 1.4 Read this before proposing any display deletion

`RootScoreView.score` is a `float` on a Pydantic model with no default. Dropping
`RootScore.score` without dropping `RootScoreView.score` is a runtime error at
`player.py:2706`; dropping both changes `CycleSnapshot`'s schema, which
`tests/test_ai/test_tracer.py` and `tests/test_tui/test_log_pane.py` pin.

---

## 2. What `decide_tree` actually produces

`decide_tree` (`progression_tree.py:503-779`) does eight things:

1. `trunk = ReachCharLevel(milestone_pure(state.level))` — the XP root.
2. `candidates = objective_candidates(...)` — structural gear
   (`_structural_candidates`, off `objective.near_term_gear`) ++ utility potions
   (`_utility_candidates`).
3. **The pivot.** With a store: `branch_ranking` → `branch_from_ranking`.
   Without: `branch_pick_pure(band_adequate, gear_target_exists)`.
4. **The eligibility filter.** `justifying_identities(j_ranking)` restricts the
   gear arm to candidates that beat the trunk under the objective's sort key.
5. **Five multipliers.** `focus` (falloff), `synergy`, `achievability`, `role`,
   and the d'Hondt `seats` interleave, composed in
   `progression_tree_core.focus_aging_pick` / `focus_aging_order`.
6. **`aged_pick`** — a clause-for-clause mirror of `focus_aging_pick`'s
   fast-path guard, consumed by the player's seat ledger.
7. **Servability promotion** — `_servable_promotion` walks the fallback pairs to
   the first `step_servable` pair. Its docstring names the livelock it prevents
   (feather_coat, 2026-06-20).
8. **Display assembly** — `trunk_row` ++ `_gear_ranking_rows(ordered ++ demoted)`.

Wave 3 replaces (2)–(6) and (8). It must **preserve** (1) as one possible walk
outcome, and it must **preserve or re-derive** (7).

### 2.1 The fallback chain is not display

This is the piece the parent spec does not address. `§3.2` says the walk yields
one `Goal` and "A\* stops early because the graph already answered the
meta-questions". But `objective_step_goal` can still return `None` — the
`ReachCharLevel` arm returns `None` when `ctx.combat_monster is None` and again
on the long-haul items-task defer (`strategy_driver.py:631,668`) — and
`_resolve_step_goal` exists precisely to walk past that. Three separate live
traces are cited in the code for why:

- `strategy_driver.py:1074-1078` — 2026-06-06 09:59, bootstrap step `None`,
  gear roots at score 1.0 never tried, 50+ cycles of PursueTask.
- `strategy_driver.py:1079-1088` — 2026-06-06 12:28, fallback ordering
  (UpgradeEquipment before GatherMaterials) needed to break a sticky commit.
- `progression_tree.py:571-584` — 2026-07-27, trunk at fallback index 0
  swallowed the whole gear branch; the fix was to move it *last*, not to remove
  the list.

A wave-3 walk that returns a bare root with no ordered alternatives regresses all
three. §5.2 specifies how the walk re-derives them.

---

## 3. The Lean obligation

### 3.1 `ExtMeasure`: which components are functions of the ranking

`formal/Formal/Liveness/CumulativeProgress.lean:179-218`. All fifteen slots are
projections of `Formal.Liveness.Measure.State`. The question is which *State
fields* are outputs of the meta-decision rather than of the world.

| # | slot | State field(s) | ranking-dependent? |
|---|---|---|---|
| 1 | `levelDeficit` | `level` | no |
| 2 | `xpDeficit` | `xp`, `level` | no |
| 3 | `taskCycles` | `taskTotal`, `taskProgress` | no |
| 4 | `skillXpDeficitProjected` | `targetSkillLevel`, `trackedSkillLevel` | **YES** — `targetSkillLevel` is documented (`Measure.lean:67-70`) as "the target skill LEVEL for that skill (the level a recipe/gate requires)". Today it is whatever the grind selector picked; after wave 3 it is `current + 1` from `CanICraftCurrentTier`. |
| 5 | `bankPressure` | `inventoryUsed`, `inventoryMax` | no |
| 6 | `hpDeficit` | `hp`, `maxHp` | no |
| 7 | `bankInaccessibleFlag` | `bankAccessible` | no (ctx flag over world state) |
| 8 | `overstockFlag` | `hasOverstockItems` | no |
| 9 | `selectBankDepositsFlag` | `selectBankDepositsNonempty` | no |
| 10 | `sellableFlag` | `sellableInventoryNonempty` | no |
| 11 | `pendingItemsFlag` | `pendingItemsNonempty` | no |
| 12 | `objectiveStepFlag` | `objectiveStepFires` | **YES** — "the StrategyArbiter inserts the StepGoal candidate iff the objective tier yields a plannable step" (`Measure.lean:169-172`). That is `decide_tree` ∘ `objective_step_goal` ∘ `is_plannable`. |
| 13 | `taskCoinsTotal` | `taskCoinsTotal` | no |
| 14 | `gold` | `gold` | no |
| 15 | `craftReliefFlag` | `craftReliefFires` | no |

Plus one non-slot field that appears as a *hypothesis*, not a measure component:
`objectiveStepIsFight` (`Measure.lean:174-190`), used in
`progressMeans_decreases_extMeasure_or_advances_level`'s `hperc`.

**13 of 15 are functions of state alone. 2 are functions of the meta-decision.**

### 3.2 Which theorems break

**None.** The reason is structural, not lucky.

Both ranking-dependent fields are *opaque state-carried Bools/Nats* in the Lean
model — the model does not reproduce the Python that computes them, it carries
production's answer and a differential harness asserts agreement. So changing
*how production computes them* cannot break a kernel proof. It can only break a
differential.

The differentials that pin them:

- `formal/diff/test_objectivestep_arming_diff.py` — pins
  `objective_step_goal`'s `ReachCharLevel` arm against
  `objectiveStepFires`/`objectiveStepIsFight`. **Wave 3 does not touch that
  arm** (it is wave 4/6 territory). Survives.
- `formal/diff/test_objective_step_is_fight_diff.py` — pins
  `objective_step_fight_core.objective_step_is_fight_pure`. Untouched.
- `formal/diff/test_local_progress_diff.py:122`,
  `formal/diff/test_cycle_step_diff.py:191` — supply `target_skill_level` as an
  input, not as a derived quantity. Untouched.

The slot-4 descent lemma is `GatherProgress.gather_decreases_measure`
(`formal/Formal/Liveness/GatherProgress.lean:123`), whose hypothesis is
`hprog : s.targetSkillLevel > s.trackedSkillLevel`. Under the increment rule
`target = current + 1`, that hypothesis is *satisfied by construction* — the
lemma survives, and its non-vacuity improves. What changes is the *informal*
reading of slot 4: it becomes a `{0,1}` flag rather than a multi-level deficit.
Nothing in the kernel relied on the wider range.

The decisive fact: **`FMeasure` — the 16-slot measure that carries today's
unconditional-descent capstone — deliberately excludes both ranking-dependent
components.** `formal/Formal/Liveness/FMeasure.lean:41-45`:

> Deliberately NOT in the tuple: `objectiveStepFires`/`objectiveStepIsFight` (the
> ONLY fields `perceptionRefresh` mutates — so the refresh is FMeasure-invariant
> by construction) and the old measure's
> `taskCycles`/`skillXpDeficitProjected`.

So `ai_reaches_fifty_unconditional`, `ai_reaches_fifty_geared`,
`ai_reaches_fifty_defer_faithful` and
`LifecycleBound7.lifecycle_progress_from_bounds_proven` are all untouched by any
change to how the root is chosen.

### 3.3 What DOES break in `formal/`

Not proofs — *modules*. Wave 3b deletes the Python these Lean files mirror, and
five gate scripts fail the moment a Lean declaration outlives its Python or a
manifest row outlives its declaration:

| Lean module | lines | what it mirrors | fate |
|---|---|---|---|
| `Formal/ProgressionTree.lean` | 726 | `progression_tree_core.py` — `milestone_pure`, `branch_pick_pure`, `gear_target_pick`, `falloff`, `dhondt_step`, `focus_aging_pick` | **split.** `milestone_*` (4 theorems) survives if the trunk keeps `milestone_pure`; the falloff/d'Hondt/focus half (12 theorems) goes |
| `Formal/ProgressionChoice.lean` | 214 | `tiers/progression_choice.py` — the J sort key | delete (9 manifest rows) |
| `Formal/Synergy.lean` | 141 | `tiers/synergy_core.py` | **KEEP** — `synergy_core` has two non-ranking consumers (`tiers/taskmaster_choice.py:26`, `tiers/means_worth.py:16`) |
| `Formal/Achievability.lean` | 164 | `tiers/achievability_core.py` | delete (5 manifest rows) — sole consumer is `progression_tree._achievability_map` |
| `Formal/Liveness/InterleaveNoStarvation.lean` | 404 | the d'Hondt no-starvation liveness proof (`interleaveDue_reaches`) | delete |

Total Lean at risk: ~1,650 lines across five files. Each deletion must be
mirrored in `formal/Formal.lean` (imports),
`formal/Formal/Manifest.lean` (rows), `formal/Formal/Audit.lean` (generated from
Manifest — `gate/check_audit_generated.sh`), the proof-concept index
(`scripts/gen_proof_concept_index.py --check`), `formal/Formal/Contracts.lean`,
`formal/Oracle.lean` where applicable, and `formal/diff/mutate.py`'s run groups.
`gate/check_no_orphan_modules.sh` and `gate/check_proof_citations.sh` catch the
half-done cases.

**`Synergy.lean` staying is the trap in this list.** `grep -rl synergy` returns
32 files; the naive read is "synergy is ranking machinery, delete it". Two
production consumers outside the ranking say otherwise.

### 3.4 The differential harnesses that go with them

- `formal/diff/test_progression_choice_diff.py` — deletes with
  `ProgressionChoice.lean`.
- `formal/diff/mutate.py` groups at lines 1126-1145 (`progression_tree`
  occupancy), 1283-1330 (`progression_choice`), 3586-3660 (`synergy_core`,
  `_synergy_map`, fallback order), 3892-3918 (`achievability_core`),
  3919-4020 (`role_alignment`, `_role_map`, `ctx.role_skills`). Anchors must
  resolve to exactly one site (`mutate.py --check-anchors` runs in
  `gate.sh` phase b''''), so a stale anchor fails the gate in seconds — which is
  the good case.

### 3.5 The two obligations wave 3 ADDS

The parent spec names them in §4 and nothing discharges them today:

**O1 — every `SkillToNextLevel(S, C+1)` has an open rung, or reports an honest
wall.** Today `CanICraftCurrentTier` returns `ReachSkillGoal(S, current+1)`
unconditionally; if no rung is open at level `C`, the goal is unplannable and the
arbiter falls through — silently. Under wave 3 that node is on the *only* path
from a skill-gated gear target to work, so a silent fall-through is a stall. This
is a **census**, not a theorem: sweep every `(skill, level)` reachable in the
scenario set and assert an open, XP-positive rung exists or the node emits a
named wall. Cheap; it is the wave-2 §7 census the plan already scoped.

**O2 — the root graph is acyclic.** `MAX_RESOLVE_DEPTH = 32` raises rather than
truncating (`ai/decision.py:26-32`), which is the right runtime behaviour but is
detection, not proof. The honest discharge is a **test** that enumerates every
`Decision` class in `ai/decisions/` and asserts the static edge relation (the
set of types each `resolve` can return) is a DAG. That is a reflection test over
the module, not a Lean theorem, and it is worth more than a theorem here because
the edges are Python control flow, not a modelled relation.

---

## 4. The replacement measure

### 4.1 What the spec proposes

> Recursion is well-founded on the lexicographic measure
> `(tier, character level, skill level, materials outstanding)`,
> each component bounded above and strictly decreasing along an edge. This
> replaces today's three-measure F/D/E descent in the Lean liveness development
> with a single decreasing tuple.

### 4.2 Verdict: the tuple is fine for the obligation it addresses; the second sentence is false

The tuple is a measure over **edges of the resolution walk**. Along a walk the
`WorldState` is frozen — `resolve_node` takes `state` once and never mutates it.
So a walk measure only has to show the *graph* has no cycle, which is O2 above,
and O2 is better served by the static-edge DAG test than by a numeric measure:
the walk's actual edges are `CanICraftCurrentTier → DoesTheRecipeNeedAMonsterDrop`
and friends, which do not move `tier`, `level` or `skill` at all. A measure whose
components are all constant along most edges proves nothing about those edges.

F/D/E and `FMeasure` are measures over **cycle trajectories** — `cycleStep`,
`cycleStepF`, `applyActionKind`. State moves. The obligation is that the bot
makes progress across cycles, and it is discharged today, hypothesis-free, by
`FMeasure`, which wave 3 does not touch (§3.2). **A walk measure cannot replace a
trajectory measure. They are not the same obligation.**

### 4.3 If someone tries to use the tuple as a trajectory measure anyway

Two of the four components are unsound across cycles. Recording the
counter-instances so this is not re-proposed:

**`skill level` — a single scalar over seven skills.** The gear target can change
slot between cycles (a slot fills, `gear_target_tier` advances, the objective's
`_slot_assignments` picks a different type). When it does, the tracked skill
changes: weaponcrafting 10 → jewelrycrafting 3. With `tier` and `character level`
equal, slot 3's deficit *rises*. That is a measure increase with no dominating
slot above it. The Lean model already collapses skills to `trackedSkillLevel`
"because the headline lemma operates on a single (drop, skill) pair"
(`Measure.lean:60-70`) — a compromise that is sound for a one-pair lemma and
unsound for a whole-trajectory measure.

*Fix, if the component is wanted:* make it the **summed deficit against the gear
target tier's requirement set**,
`Σ_S max(0, required_level(S, target_tier) − skills[S])`. Switching which skill
is climbed cannot raise the sum, because the requirement set is fixed by the
tier; any `LevelSkill` serving the tier lowers it.

**`materials outstanding` — not monotone, and it is the least significant slot.**
It rises on `DepositAll`, on `Discard`, on a target change, and on any craft that
consumes inputs into an intermediate needed at higher multiplicity. As the last
component there is nothing below it to absorb the rise, so the tuple increases.
`FMeasure` handles the analogous problem by putting `bankPressure` at slot 12
with fight/claim rises dominated by slots 1/2/11, and it *discloses* the one case
it cannot dominate (a claim-minted item re-arming `overstockFlag`).
`materials outstanding` at slot 4 of 4 has no such structure.

*Fix, if the component is wanted:* it must sit above at least one slot that every
material-raising action descends. There is no such slot in a 4-tuple. This is why
`FMeasure` has sixteen.

### 4.4 Recommendation

- **Do not restate the Lean liveness measure in wave 3.** `FMeasure` is correct
  and untouched. Say so in the wave-3 commit message and add the citation to
  `docs/LEVEL_FIFTY_RESIDUALS.md` so the next reader does not re-derive the
  question.
- **Do discharge O1 (census) and O2 (DAG test).** Those are the real new
  obligations and they are cheap.
- **If a walk measure is still wanted for documentation**, the honest form is
  `(gear_target_tier − 0, 50 − level, Σ skill deficits vs the tier, |unmet
  materials for the current step|)` with the directions fixed, and it should be
  labelled a *walk* measure in the docstring so nobody cites it as a liveness
  result. `MAX_RESOLVE_DEPTH` plus the DAG test already does its job.

### 4.5 What the parent spec's §4 obligations map to

| spec obligation | discharge |
|---|---|
| "Every `SkillToNextLevel(S, C+1)` has at least one open rung, or the node reports an honest wall" | O1 — census, wave 3a |
| "No `Decision` cycle exists" | O2 — static DAG test over `ai/decisions/`, wave 3a |

---

## 5. The resolution contract

### 5.1 Signatures

Two changes to wave 2's `ai/decision.py`, then one new module.

**Change 1 — `resolve_node` becomes leaf-type-agnostic.** Today it terminates on
`isinstance(current, Goal)`. Wave 3's root graph terminates on a `MetaGoal`,
which is a non-runtime-checkable `Protocol` and cannot be `isinstance`-tested.
Flipping the loop condition fixes both and removes a branch:

```python
# src/artifactsmmo_cli/ai/decision.py  (replaces the current resolve_node body)

Leaf = TypeVar("Leaf")

Node = Union["Decision[Leaf]", Leaf]


class Decision(ABC, Generic[Leaf]):
    """A named predicate over state that selects a child node."""

    name: str

    @abstractmethod
    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision[Leaf] | Leaf | None":
        """The child this decision selects for `state`. None = no child."""


def resolve_node(node: "Decision[Leaf] | Leaf | None",
                 state: WorldState, game_data: GameData,
                 ctx: SelectionContext, history: LearningStore | None,
                 ) -> Leaf | None:
    """Walk `node` down to the leaf it selects, or None.

    Terminates on 'not a Decision' rather than on a positive leaf test, so the
    same walk serves the STEP graph (leaf = Goal, an ABC) and the ROOT graph
    (leaf = MetaGoal, a Protocol that cannot be isinstance-tested). One walk,
    two leaf kinds — not two walks.
    """
    seen: list[str] = []
    current: "Decision[Leaf] | Leaf | None" = node
    for _ in range(MAX_RESOLVE_DEPTH):
        if not isinstance(current, Decision):
            return current
        seen.append(current.name)
        current = current.resolve(state, game_data, ctx, history)
    raise RecursionError(
        f"Decision graph did not terminate in {MAX_RESOLVE_DEPTH} steps; "
        f"walk was {' -> '.join(seen)}")
```

The six existing decisions become `Decision[Goal]`. Their bodies do not change.
`__init_subclass__`'s `name` check is unaffected (it reads
`cls.__dict__['resolve']`, which `Generic` does not touch).

**Change 2 — a root-level `MetaGoal` for a skill climb.** `chosen_root` is a
`MetaGoal`; there is no `MetaGoal` today that names "raise skill S". Without one,
a skill-gated resolution cannot be reported as the chosen root and the plan pane
shows the *gear* root while the bot grinds a skill.

```python
# src/artifactsmmo_cli/ai/tiers/meta_goal.py  (append)

@dataclass(frozen=True)
class ReachSkillLevel:
    """The character reaches `level` in `skill`.

    A root-level sibling of `ReachCharLevel`: the tier ladder's answer when a
    gear target is skill-gated is "raise the skill by one", and `chosen_root`
    must be able to name that. Wave 2 could route to `ReachSkillGoal` (a planner
    Goal) but had no MetaGoal for it, so the pane reported the gear root while
    the bot ground a skill.
    """

    skill: str
    level: int

    def is_satisfied(self, state: WorldState, game_data: GameData) -> bool:
        return state.skills.get(self.skill, 1) >= self.level
```

`prerequisite_graph.prerequisites` gains a third arm returning `[]` (a skill
climb has no MetaGoal prerequisites — `LevelSkill`/`ReachSkillGoal` owns the
sub-plan), and `strategy.root_category` gains `"skill"`.

**Change 3 — the root resolution entry point.**

```python
# src/artifactsmmo_cli/ai/decisions/root.py  (new)


@dataclass(frozen=True)
class RootResolution:
    """The walk's answer: the root to pursue, ordered alternatives, and the
    trail that produced it.

    `alternatives` is NOT a ranking. It is the ordered remainder of the ONE
    list-valued node in the graph (`WhichSlotIsFurthestBehind`), plus the trunk
    last. It exists because `objective_step_goal` can still return None for a
    resolved root (`ReachCharLevel` with no combat target, the long-haul
    items-task defer) and because `_servable_promotion` still needs somewhere to
    walk. Deleting it regresses three named live traces — see
    `strategy_driver._resolve_step_goal` and `progression_tree`'s fallback-order
    comment.

    `trail` is the ordered `Decision.name`s the walk visited. It replaces the
    ranking as the plan pane's "why": a named path is a better answer to "why
    this root" than a number was.
    """

    root: MetaGoal | None
    alternatives: tuple[MetaGoal, ...]
    trail: tuple[str, ...]


def resolve_root(state: WorldState, game_data: GameData,
                 objective: CharacterObjective, ctx: SelectionContext,
                 history: LearningStore | None) -> RootResolution:
    """Walk the tier graph from `IsMyGearBehindMyTier` to a root MetaGoal."""
```

### 5.2 How the walk preserves `StrategyDecision`'s shape

`decide_tree` keeps its signature and its return type. Its body becomes:

```python
def decide_tree(state, game_data, objective,
                band_adequate=False, step_servable=None,
                ctx=NO_PROFILE_CONTEXT, history=None,
                ) -> "strategy.StrategyDecision":
    resolution = resolve_root(state, game_data, objective, ctx, history)
    chosen_root = resolution.root
    chosen_step = (strategy.actionable_step(chosen_root, state, game_data, ctx)
                   or chosen_root) if chosen_root is not None else None
    fallback_roots = list(resolution.alternatives)
    fallback_steps = [strategy.actionable_step(alt, state, game_data, ctx) or alt
                      for alt in resolution.alternatives]

    tree_pick_root = chosen_root
    if step_servable is not None and chosen_root is not None and chosen_step is not None:
        chosen_root, chosen_step, fallback_roots, fallback_steps = _servable_promotion(
            chosen_root, chosen_step, fallback_roots, fallback_steps, step_servable)
    promoted_from = tree_pick_root if chosen_root is not tree_pick_root else None

    return strategy.StrategyDecision(
        interrupt=None,
        chosen_root=chosen_root,
        chosen_step=chosen_step,
        desired_state={},
        ranking=_resolution_rows(state, game_data, resolution, ctx),
        fallback_steps=fallback_steps,
        fallback_roots=fallback_roots,
        promoted_from=promoted_from,
    )
```

Every consumer that reads only `chosen_root` / `chosen_step` — which is
`strategy_driver.select`, `plan_tree`, and the crafting-target scan — is
byte-unaffected. `_servable_promotion` survives verbatim; it is a pure function
over four lists and knows nothing about scoring.

`_resolution_rows` produces the display list on the SAME `RootScore` type,
with the trail in `category` and no numeric key:

```python
def _resolution_rows(state, game_data, resolution, ctx) -> "list[strategy.RootScore]":
    """One row per resolved node, chosen first, alternatives after.

    `score` is dropped to the constant Fraction(1) on every row rather than
    removed: `RootScoreView.score` is a required float on a Pydantic model that
    the TUI log pane and two test modules pin, and changing the snapshot schema
    is a separate change from changing the decision. The row's real content is
    `category`, which now carries the resolution trail — a named path, which is
    what a reader wanted from the number and never got.
    """
```

### 5.3 The root graph

Five nodes (an earlier draft of this line said six and drew five; five is correct — wave-3a task 4 built five and invented no sixth). Each is one `Decision[MetaGoal]` in `ai/decisions/root.py`.

```
IsMyGearBehindMyTier                 gear_targets_with_blockers(state, history) non-empty?
  no  -> IsThereACombatTarget
  yes -> WhichSlotIsFurthestBehind

WhichSlotIsFurthestBehind            the largest tier gap among blocked slots
  -> IsThisTargetBlocked(target)     ; siblings become RootResolution.alternatives

IsThisTargetBlocked                  GearTarget.blocker
  None                  -> ObtainItem(code, slot=slot)                 [LEAF]
  "skill:<S>:<L>"       -> ReachSkillLevel(S, state.skills[S] + 1)     [LEAF]
  "material:<m>"        -> ObtainItem(m, qty)                          [LEAF]

IsThereACombatTarget                 ctx.combat_monster is not None
  yes -> ReachCharLevel(tier_of_level(game_data, state.level))         [LEAF]
  no  -> CanIClearMyTier

CanIClearMyTier                      next_uncleared_tier(...) is None?
  yes -> ReachCharLevel(milestone_pure(state.level))                   [LEAF]  (ladder finished; trunk)
  no  -> IsMyGearBehindMyTier is already false here, so this is the honest wall
         -> None                                                        [LEAF]
```

Every input is already built and merged:
`objective.gear_targets_with_blockers` (wave 2, currently unconsumed),
`tier_progress.gear_target_tier` / `next_uncleared_tier` (wave 1),
`tier_ladder.tier_of_level` (wave 1), `ctx.combat_monster` fed by
`band_target.band_combat_target` (wave 5, merged and live).
The `"skill:<S>:<L>"` blocker string is produced by
`objective._classify_target` (`tiers/objective.py:436-439`) — wave 3a should
replace the string with a small tagged value rather than parse it back, because
parsing a formatted string to recover a decision is the shape of defect this epic
exists to remove. That is a one-field change to `GearTarget`.

### 5.4 What this does NOT change

- `GOAPPlanner`, A\*, the `Goal` ABC, every `Action` — untouched, per §9 of the
  parent spec.
- `actionable_step` and `prerequisites` — the descent *within* a root is
  unchanged. Wave 3 replaces the argmax *over* roots.
  `formal/Formal/StrategyTraversal.lean` (`actStep`) and
  `formal/diff/test_strategy_traversal_diff.py` are unaffected.
- `objective_step_goal`'s `ReachCharLevel` arm — wave 4/6.
- The eleven interrupt guards — wave 4 names them.

---

## 6. Deletion list

Every row carries a grep'd count. Counts are from this worktree at `1bffc75e`.
"src" excludes the definition site itself where noted.

### 6.1 Safe to delete in wave 3b (zero non-ranking consumers)

| item | src consumers | tests | formal | note |
|---|---|---|---|---|
| `RootScore.cost` | **0 readers** (2 writers, `asdict`) | 0 | 0 | literal `0` at both writes |
| `RootScore.contribution` | **0 readers** (2 writers, `asdict`) | 0 | 0 | |
| `RootScore.instrumental` | **0 readers** | 1 (pins always-False) | 0 | |
| `objective_step_goal(committed_root=…)` | **0 readers** — declared `strategy_driver.py:608`, passed at `:1090`, `:1098`, `:1106`, `:1325`, never read in the body | 0 | 0 | dead parameter, found by grep |
| `StrategyDecision.desired_state` | 1 (`to_trace`) | — | 0 | always `{}`; its own comment says no consumer reads it |
| `StrategyDecision.aged_pick` | 1 (`player._bump_focus`) | 5 files | `mutate.py` ×7 | dies with the seat ledger |
| `StrategyDecision.j_ranking` | 2 | 3 files | 0 | dies with J |
| `tiers/achievability_core.py` | 1 (`progression_tree._achievability_map`) | 1 | `Achievability.lean` (5 manifest rows), `mutate.py` group | |
| `ai/role_alignment.py` | 1 (`progression_tree._role_map`) | 3 | `ProgressionTree.lean` prose, `mutate.py` ×2 groups | `ctx.role_skills` stays — `supply_target` uses the same channel |
| `tiers/horizon_contribution.py` | 1 (`branch_objective`) | 1 | 0 | plus `scripts/measure_means_suppression.py:40` — a script, must be updated or deleted with it |
| `tiers/progression_choice.py` | 3 (`branch_objective`, `progression_tree`, `strategy`) + `commands/objective.py` | 2 | `ProgressionChoice.lean` (9 rows), `Extracted/ProgressionChoice.lean`, `test_progression_choice_diff.py`, `mutate.py` group | `TARGET_LEVEL` is re-exported through `horizon_contribution`; check for a third importer before deleting the constant |
| `tiers/branch_objective.py` | 3 (`progression_tree`, `strategy`, `commands/objective.py`) | 2 | 0 | see §6.3 — **this is the live pivot, not dead code** |
| `progression_tree_core`: `falloff`, `focus_aging_pick`, `focus_aging_order`, `dhondt_step`, `FOCUS_FLAT`, `bump_seats` | 1 (`progression_tree`) | 2 | `ProgressionTree.lean` (12 rows), `InterleaveNoStarvation.lean` (whole file), `mutate.py` groups | `milestone_pure`, `Branch`, `GearCandidate`, `branch_pick_pure`, `potion_type_weight` **stay** — `commands/objective.py:46` imports `milestone_pure` |
| `player._gear_focus` | 14 sites in `player.py`, 1 in `cycle_snapshot.py` | 2 files (49 refs) | 0 | plus `CycleSnapshot.gear_focus`, a schema change |
| `player._interleave_seats` | 11 in `player.py`, 2 in `cycle_snapshot.py` | 2 files (33 refs) | 0 | plus `CycleSnapshot.interleave_seats` |
| `_synergy_map` (the call in `decide_tree` only) | 1 | 2 | `mutate.py` group | **`synergy_core.py` itself STAYS** — see below |

### 6.2 Must NOT be deleted — grep says live

| proposed | why not |
|---|---|
| `tiers/synergy_core.py` | 2 non-ranking production consumers: `tiers/taskmaster_choice.py:26` (`expected_pool_synergy`, `synergy_pure`) and `tiers/means_worth.py:16` (`S_MIN`, `synergy_pure`). `Formal/Synergy.lean` stays with it. |
| `tiers/pursuit_value.py` | 2 non-ranking consumers: `tiers/prerequisite_graph.py:19`, `tiers/objective.py:22`. The "1e9 score scale" the spec wants deleted is `pursuit_value` *as a RootScore field*, not the function. |
| `ai/weapon_winnability.marginal_weapon_winnability` | 1 ranking consumer (`_structural_candidates:121`) but it is the **weapon-slot suppressor**, and wave 5's task 5.3 already investigated the analogous three sites and kept all three. `tier_progress.py:31` cites it as the rest-projection idiom. Wave 3 should keep the *predicate* and re-site it inside `IsThisTargetBlocked` rather than delete it; deleting it re-arms the fire_bow damage-type-blind upgrade the comment at `progression_tree.py:113-121` documents. |
| `objective.near_term_gear` | 3 consumers, only one of which is the ranking: `progression_tree.py:108` (goes), `player.py:3723` (the `ctx` near-term target set for the skill-grind `wanted` preference — stays), `audit/craft_completeness.py:540` (the census — stays). |
| `progression_tree_core.milestone_pure` | `commands/objective.py:46` imports it directly; `Formal.ProgressionTree.milestone_*` is 4 manifest rows. |

### 6.3 `J` — confirmed from the code, and the confirmation is a warning

`finite_j` returns `None` outside the finite band (`branch_objective.py:256-264`),
and every live candidate is in the *unreachable* band, so
`objective_j` never reaches the sort key. That is the "`j: null` on all twelve
roots" measurement.

But `sort_key` (`progression_choice.py:107-113`) has three arms, and the
unreachable arm — `(band, TARGET_LEVEL − reachable_level, acquire_cost)` — is the
one that runs. Two live decisions read its output:

- `branch_from_ranking` (`branch_objective.py:302-307`): "XP iff the trunk won".
  **This is the GEAR-vs-XP pivot for every cycle with a learning store**, which
  is every live cycle.
- `justifying_identities` (`branch_objective.py:266-300`): the eligibility filter
  that restricts the gear arm.

So: **deleting `J` is safe; deleting `branch_objective` is a behaviour change.**
The tier walk replaces the pivot with "is my gear behind my tier", which is a
different question with a different answer. That is intended — it is the whole
point of the wave — but it must be reviewed as a behaviour change with a
scenario-set diff, not merged as a dead-code removal.

Recorded because task 5.3 investigated three "obviously dead" sites and found all
three live, one through a caller the plan author had missed.

### 6.4 Deliberately deferred to a gated investigation (wave 3c)

The parent spec's wave-3 deletion list includes two items that are **not ranking
machinery**:

| item | src refs | tests | formal | verdict |
|---|---|---|---|---|
| `StrategyArbiter._committed_repr` (sticky commitment) | 19 refs across `arbiter_select.py`, `strategy_driver.py`, `player.py` | 2 files | `Formal/ArbiterSelect.lean`, `Formal/Extracted/ArbiterSelect.lean`, `Formal/Extracted/Bridges2.lean`, `formal/diff/test_arbiter_select_diff.py`, `mutate.py` | **investigate, do not delete.** This is the *means-goal* commitment inside `select_pure`, not the tree's focus ledger. It has four proven roles in the manifest. The spec's stability argument ("a derived graph returns the same node every cycle") is about the *root*; `_committed_repr` commits to a *Goal*, including guard and discretionary goals the graph never touches. |
| `DoomedMemo` | 27 refs across `doomed_memo.py`, `planner.py`, `player.py`, `strategy_driver.py`, `goals/progression.py` | 4 files | `Formal/DoomedMemo.lean`, `Formal/Contracts.lean`, `Formal/PlanModel.lean`, `Formal/Manifest.lean`, `Formal/Audit.lean`, `Oracle.lean`, `formal/diff/test_doomed_memo_diff.py`, `mutate.py` | **investigate, do not delete.** It is a *planner-cost* memo (`planner.py:36`: "cannot be planned costs 15s once per re-probe window instead of every cycle") with a `memo_exempt` escape on `Goal`. Removing it is a CPU regression of unknown size, not a stability change. |

Both belong in a task shaped exactly like 5.3: read, measure, report, delete
nothing without evidence.

---

## 7. Wave-3 task breakdown

Verdict: **three plans**. Rationale in §7.4.

### Plan 3a — the cutover (this is the risky one)

Every task leaves `bash formal/gate.sh` green. No module is deleted in 3a; the
ranking machinery becomes *uncalled*, which the mutation gate will then report as
survivors — that is expected and is 3b's input.

**3a.1 — `resolve_node` becomes leaf-type-agnostic.**
`ai/decision.py`: the `Generic[Leaf]` change in §5.1. The six existing decisions
in `ai/decisions/obtain_item.py` gain `Decision[Goal]` in their base clause and
nothing else. Pure typing + one flipped branch condition. Mutation anchor: the
loop condition (`not isinstance(current, Decision)`) must resolve to exactly one
site.

**3a.2 — `ReachSkillLevel` MetaGoal.**
`tiers/meta_goal.py` (append, §5.1), `tiers/prerequisite_graph.prerequisites`
third arm returning `[]`, `tiers/strategy.root_category` → `"skill"`,
`ai/goal_serialization.py` round-trip if the root is serialised (check: it
serialises Goals, not MetaGoals — confirm before adding). No behaviour change:
nothing constructs it yet.

**3a.3 — `GearTarget.blocker` becomes structured.**
`tiers/objective.py:294-300, 415-447`. Replace
`blocker=f"skill:{stats.crafting_skill}:{stats.crafting_level}"` with two typed
optional fields (`blocking_skill: str | None`, `blocking_skill_level: int`) or a
small frozen `Blocker` union. Reason: `IsThisTargetBlocked` must not parse a
formatted string back into a decision. `tests/test_ai/test_max_gear_for_level.py`
(5 assertions on `blocker`) updates with it.

**3a.4 — the root graph.** New `ai/decisions/root.py`, six `Decision[MetaGoal]`
classes + `resolve_root` + `RootResolution` (§5.1, §5.3). Nothing calls it yet.
New test module. **This task must include the O2 DAG test** (§3.5) in the same
commit — a reflection sweep over `ai/decisions/` asserting the static
return-type edge relation is acyclic.

**3a.5 — the O1 census.** `src/artifactsmmo_cli/audit/` gains a sweep: for every
`(skill, level)` reachable across the scenario set, assert
`ReachSkillLevel(S, C+1)` has an open, XP-positive rung or the graph emits a named
wall. Wired into `formal/gate.sh`'s census phase next to the six existing
`--check` scripts. Runtime budget: it is a pure catalogue sweep, so seconds, not
the 99s the craft census costs.

**3a.6 — THE FLIP.** `decide_tree`'s body becomes §5.2. Parameters
`band_adequate`, `focus`, `seats`, `committed_root_code`, `enable_synergy`,
`store` are removed from `decide_tree` and `StrategyEngine.decide`; `history`
replaces `store` (the graph needs `is_winnable`'s learning store, not a
projection store). `player.py:727-737` and `player.py:1040-1047` update. This is
the one reviewable behaviour change and it must be its own commit.

Mutation anchors required in the same commit (`feedback_mutation_anchor_discipline`):
the `IsMyGearBehindMyTier` predicate, the `IsThisTargetBlocked` skill arm, and
the `RootResolution.alternatives` construction — each resolving to exactly one
site.

**3a.7 — display.** `_resolution_rows`, `rank_detail`'s first two arms deleted
(the `j` and `reachable_level` cases), `commands/plan.py:76-82`'s header text.
`RootScore.j` / `.reachable_level` become unused but are *not removed here* —
that is 3b, so the schema change is one commit.

**Live acceptance for 3a**, read from `~/.cache/artifactsmmo/learning.db`:
baseline over the 15,242 cycles since 2026-08-20 is
`avg(planner_nodes) = 774.3`, `max = 113,595`. Post-cutover, both must fall, and
`weaponcrafting` must exceed 10 on at least one character. Capture the baseline
row **before** the flip, not from this document.

### Plan 3b — the deletion

Only after 3a is live and the mutation gate has reported the survivors that
prove the machinery is uncalled. Order matters: Python first, then Lean, then
manifest/audit/index, because `check_proof_citations.sh` fails on a Lean name
cited by deleted Python and `check_no_orphan_modules.sh` fails on a Lean module
whose import went away.

- **3b.1** Python modules from §6.1 (10 files, ~3,770 lines of test with them).
- **3b.2** `CycleSnapshot` schema: `gear_focus`, `interleave_seats`,
  `strategy_ranking`'s `score`. One commit, one schema version bump.
- **3b.3** Lean: `ProgressionChoice.lean`, `Achievability.lean`,
  `InterleaveNoStarvation.lean`, and the falloff/d'Hondt half of
  `ProgressionTree.lean`. **`Synergy.lean` stays** (§6.2).
- **3b.4** `Manifest.lean` rows (9 + 5 + 12), `Audit.lean` regeneration,
  `Contracts.lean`, `Oracle.lean`, `scripts/gen_proof_concept_index.py --check`,
  `formal/diff/mutate.py` run groups and anchors, `Formal.lean` imports,
  `formal/diff/test_progression_choice_diff.py`.
- **3b.5** `scripts/measure_means_suppression.py` — imports
  `horizon_contribution`; update or retire.

### Plan 3c — the gated investigation

Shaped as task 5.3 was: read, measure, report, **delete nothing without
evidence**. Two subjects (§6.4): `_committed_repr` and `DoomedMemo`. Deliverable
is a report with a per-site KEEP/DELETE verdict and, for every DELETE, the
measurement that justifies it. Expected outcome, on the 5.3 precedent: mostly
KEEP.

### 7.4 Why three plans and not one

- **Different gates.** 3a's gate is behavioural (scenario set + live acceptance).
  3b's gate is structural (orphan modules, manifest/audit drift, proof citations,
  anchor resolution). Mixing them means a manifest-drift failure blocks a
  behaviour review and vice versa.
- **Different reversibility.** 3a is one commit's revert. 3b removes ~1,650
  lines of Lean and ~3,770 lines of test; reverting it is a merge conflict.
- **Different evidence.** 3b's evidence is *3a's mutation survivors*. Running
  them as one plan means deleting on the assumption the code is uncalled rather
  than on the report that it is.
- **This epic has already paid twice** for optimistic plans: task 5.1 took five
  fix rounds (three of them the same defect class), and task 5.3's premise was
  wrong on all three of its sites. Both were single tasks inside a plan that
  assumed they were small.

Sizing, for the record: 3a touches 9 production files and adds 2 (~600 new lines,
~250 deleted). 3b deletes 10 Python modules, 4 Lean modules and part of a fifth,
14 test modules, and edits 6 gate-visible manifests. 3c writes no code.

---

## 8. Risks, and what I could not determine

### 8.1 Risks

**R1 — the fallback chain is the highest-risk piece and the spec does not cover
it.** §5.2's `RootResolution.alternatives` is my design, not the spec's. If it is
wrong the failure mode is a stall: `objective_step_goal` returns `None`, there is
nowhere to walk, and the arbiter falls to discretionary. Three named live traces
say this happens. Mitigation: 3a.6's scenario-set diff must assert that every
scenario with a non-`None` chosen root also produces a non-empty
`fallback_roots`, and `_servable_promotion` keeps its existing tests.

**R2 — `WhichSlotIsFurthestBehind` is a new argmax.** The wave exists to delete an
argmax and this design introduces one. It is defensible — it ranks *slots by tier
gap*, an integer with a meaning, not roots by an incomparable score — but it is
an argmax, and the discipline that produced the four multipliers will apply
pressure to add a fifth here. Mitigation: the node must take the largest tier gap
and break ties by slot order from `EQUIPMENT_SLOTS`, with a docstring forbidding a
multiplier. A `feedback_no_alphabetical_tiebreak`-style rule.

**R3 — `objective.gear_targets_with_blockers` has never run in production.** It
has 5 tests and 0 production callers. Its `_classify_target` was already fixed
once in fix-round-1 (2026-08-23) for the same mask-ordering bug this epic exists
to remove. Wiring it is a live-behaviour change to a function nobody has watched.
Mitigation: 3a.4 should run it across the scenario set and record the per-slot
targets *before* 3a.6 wires it, so the flip's diff is against recorded numbers.

**R4 — removing the eligibility filter is a silent widening.**
`justifying_identities` currently restricts the gear arm. The tier walk has no
equivalent: whatever slot is furthest behind is pursued. If the tier model
mis-scores a slot, nothing stops it. The parent spec's §8 flags the analogous
`ClearTier`/`predict_win` risk; this is the same risk on the gear axis.

**R5 — `synergy_core` and `pursuit_value` look deletable and are not.** Both have
non-ranking consumers found only by grepping outside the `tiers/` package
(§6.2). An implementer working from the parent spec's one-line deletion list will
delete them.

**R6 — CPU.** The parent spec predicts a large node-count win from the
gate-closed action set (§3.4). This design does **not** deliver that — closing
`relevant_actions` was wave 2 step 5, and I did not verify whether it landed.
If it did not, 3a's live acceptance criterion "planner nodes drop materially" may
not be met by 3a alone, and that must not be read as a 3a failure.

### 8.2 What I could not determine

**U1 — whether wave 2 step 5 (gate-closed `relevant_actions`) landed.** I read
`ai/decisions/obtain_item.py` and `ai/decision.py` in full and neither closes the
action set; I did not sweep every `Goal.relevant_actions` override. If it did not
land, R6 applies and someone must decide whether it belongs in 3a.

**U2 — whether wave 2 step 6 (`LevelSkill` removal) was attempted.**
`ai/level_skill_expand.py` and `ai/grind_expansion.py` are both still present and
`goals/reach_skill.py` still aims `LevelSkill`. The wave-2 spec made the deletion
conditional on a verification and required recording why if it failed. I did not
find that record in `.superpowers/sdd/PLAN_goal_decision_graph_waves_3_6/progress.md`
(which covers waves 5 and 3.1 only). It may be in the wave-1-2 plan directory.

**U3 — the exact `CycleSnapshot` schema-compatibility contract.** I do not know
whether an older snapshot must deserialise against a newer schema (a persisted
trace replay would need it). `gear_focus`, `interleave_seats` and
`strategy_ranking.score` all have defaults today, so removal may be safe, but
3b.2 should confirm against whatever reads persisted snapshots before changing
the model.

**U4 — whether `resolve_root` needs the learning store at all in 3a.**
`tier_progress.tier_cleared` and `band_target.band_combat_target` both take
`history` and both pass it to `is_winnable`. `gear_targets_with_blockers` takes
`history` for `gear_target_tier`. So yes for the tier arms — but I did not verify
that the `search_cache` the player opens around `decide()`
(`player.py:725-726`) still covers the new call shape, and the objective's
per-candidate `cheapest_path_to_level` walks that cache exists for are exactly
what 3a deletes. The cache may become unnecessary, or may become necessary for a
different reason (`tier_cleared` calls `is_winnable` once per normal monster per
tier, per cycle). Measure before deciding.

**U5 — live `j: null` on twelve roots.** I confirmed the *mechanism* from the
code (§6.3) but did not re-measure the twelve roots; the figure is the parent
spec's, dated 2026-08-22. The mechanism confirmation is the stronger claim and it
is the one this design rests on.
