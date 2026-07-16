# Skill-Grind Admissible Heuristic — Design

**Status:** approved for planning
**Date:** 2026-07-15
**Related:** `PlannerAdmissibility.lean` (the h≡0 optimality proof), `project_level_skill_action` (LevelSkill is the sole skill-grind mechanism), `project_grind_held_rung_livelock` (BUG C, the sibling grind fix), `feedback_proofs_tell_false_stories` (proofs must model the real algorithm), the one-obtain-model epic (`ai/obtain_sources`).

---

## 1. The defect (BUG B — traced live on Robby, level 13, weaponcrafting 7)

`UpgradeEquipment(fire_bow->weapon_slot)` cannot be planned. A valid **3-step plan
exists** — `LevelSkill(weaponcrafting->10)` → `Craft(fire_bow)` → `Equip(fire_bow)`
— with every material already in hand (spruce_plank×6, red_slimeball×13, verified
live). Yet the search returns `plan_len=0` after **4277 nodes / 10s timeout**, so
the arbiter commits `fire_bow` as `chosen_root` but falls through to
`GrindCharacterXP(cow)`: a wasted multi-thousand-node search **every cycle** plus a
strategic mismatch.

### Root cause

The planner is **Dijkstra** (`planner.py`: `h ≡ 0`, optimality proven in
`PlannerAdmissibility.lean`, parametric over any admissible `h`). It expands nodes
in `g`-cost order. The one necessary action, `LevelSkill(weaponcrafting->10)`,
costs **150** (a real 3-level grind). The 16-action relevant set also holds cheap,
**repeatable, state-changing** actions — `Gather(spruce_tree)` 13, `Rest` 10,
`Withdraw` 5, `DepositAll` 25, crafts 19–27 — all far below 150. Dijkstra must pop
the *entire* sub-150-cost frontier before it ever takes the LevelSkill edge, and
because gather/rest/withdraw change inventory/hp/bank they generate thousands of
**distinct** (non-deduped) states. Hence 4277 nodes and no plan in budget.

This is the textbook uniform-cost-search failure: an **expensive-but-necessary**
action reached only after a large **cheap-but-dead** frontier. It is **general** —
every skill-gated gear target whose materials are in hand hits it.

### Rejected alternatives (recorded)

- **Cost re-tuning** (lower LevelSkill / raise cheap actions): does **not** bound
  the *combinatorial* cheap-state frontier (repeatable gather/rest/withdraw
  generate distinct sub-threshold states at any calibration); shifts the threshold,
  fragile; and distorts optimal-plan quality — `LevelSkill`'s 150 encodes a genuine
  3-level grind, so lowering it makes the bot over-grind. Cost-tuning *redefines*
  what "optimal" means. Not the fix.
- **Relaxed-planning-graph h_max** (general admissible heuristic): the principled
  general answer, but needs a declarative precondition/effect atom model the
  codebase does not have (actions are opaque Python `apply`/`is_applicable`) and is
  expensive per node in a search already I/O-bound under learned costs. Deferred as
  YAGNI until a NON-skill-gate explosion is observed.
- **relevant_actions pruning alone**: the filter is already correctly scoped (16
  actions, `LevelSkill` narrowed to `weaponcrafting->10`); pruning the cheap
  actions harder is fragile and does not address the uninformed search.

## 2. The fix — a goal-provided admissible+consistent skill-grind heuristic

Keep Dijkstra's proven optimality; make it **informed** with a heuristic that is
both admissible (`h ≤ true remaining`) and **consistent** (monotone). Consistency
is required — not merely admissibility — because the planner does **graph search
with a visited set** (`planner.py:153-156`): an admissible-but-inconsistent `h`
can let closed-set pruning discard the cheaper path and return a suboptimal plan.

### 2.1 The seam

Add to `Goal` (base):

```python
def heuristic(self, state: WorldState, game_data: GameData) -> float:
    """Admissible, consistent estimate of remaining plan cost. Default 0.0
    (Dijkstra — trivially admissible & consistent). Overriding goals MUST keep
    h ≤ true remaining and monotone, or the visited-set search loses optimality."""
    return 0.0
```

In `GOAPPlanner.plan`, replace the two hardcoded `h = 0.0` (root at
`planner.py:138`, child at `:186`) with `h = goal.heuristic(<state>, game_data)`
— the root uses the start state, each child uses `next_state`. Every goal that does
not override `heuristic` keeps `h=0`: behavior is byte-identical for them.

### 2.2 The heuristic (UpgradeEquipmentGoal, GatherMaterialsGoal)

```
heuristic(state, game_data):
    if self.is_satisfied(state):            return 0.0
    total = 0.0
    for (skill, level) in forced_skill_grinds(target, state, game_data):
        total += LevelSkill(skill=skill, target_level=level).cost(state, game_data)
    return total
```

`forced_skill_grinds` returns a `(skill, level)` only when the grind is
**unavoidable** for the goal — the admissibility guard (§2.3).

`LevelSkill.cost` is deterministic (current skill level + `SkillXpCurve`; **no
learning input**) and monotone in the level gap. Only `LevelSkill` raises a skill
in-search (`CraftAction.apply` deliberately does not — `crafting.py`), so the grind
cost is a stable per-state quantity.

### 2.3 The admissibility guard — a grind is counted only when FORCED

A gated craft is only a landmark (hence a valid heuristic term) when crafting is
the **only** way to satisfy the goal. Count `(skill, level)` iff **all** hold:

1. the goal is **not** satisfied at `state`;
2. the closure craft is gated: `state.skills.get(skill, 1) < level`;
3. the target item is **not already owned** (inventory + bank cover the need) —
   else the plan is just `Equip`/`Withdraw`, no grind;
4. the target has **no non-craft obtain source** — via `ai/obtain_sources`, no
   `WITHDRAW`/`BUY`/`DROP` route the character can take. If a non-craft route
   exists, crafting (hence the grind) is avoidable.

If any of 1–4 fails, the grind contributes 0. **Omitting a genuinely-forced grind
is always safe** (h only shrinks, stays a lower bound); the guard exists solely to
prevent *over*-counting, which is what would break admissibility.

Scope note: this spec counts the **target item's own** crafting-skill grind — the
dominant landmark and the Bug B trigger. Grinds for gated *intermediates* (e.g. a
plank gated behind woodcutting) are **not** counted; omitting them keeps `h`
admissible (a smaller lower bound), just less tight. They are a future tightening,
not correctness debt.

### 2.4 Why admissible + consistent

- **Admissible.** A forced grind lies on every plan to the goal, so
  `true_remaining(s) ≥ LevelSkill.cost(s) ≥ h(s)` (h is the sum of forced-grind
  costs, itself a lower bound on the sum of *all* required work).
- **Consistent.** For the grind edge `s → s'`: `LevelSkill.apply` sets the skill to
  `level`, so `h(s') = 0` and the edge cost equals `LevelSkill.cost(s) = h(s)`,
  giving `h(s) = cost + h(s')` (equality). For any **other** action, the skill is
  unchanged, so `h(s') = h(s)` and `h(s) ≤ cost + h(s')` holds because `cost ≥ 0`.
  Consistency makes closed-set pruning sound → the visited-set search stays optimal.

  **Target stability.** The heuristic's target must be the SAME item the goal's
  `is_satisfied` targets (pinned `committed_target` for the Bug B case; otherwise
  `find_upgrade_target`, which is deterministic per state). Consistency needs the
  target to be stable across a search: it is, because only an `Equip` changes the
  equipped set, and equipping the target *satisfies* the goal (search ends) — no
  non-terminal edge flips the target. `GatherMaterialsGoal`'s `target_item` is
  fixed at construction, so it is stable by definition. Admissibility holds
  per-state regardless; only consistency relies on this stability, and the plan
  must assert it (a search whose target flips mid-way would need the term recomputed
  against the flipped target).

### 2.5 Worked effect (fire_bow @ weaponcrafting 7)

```
root       f = g0(0)   + h(150) = 150
LevelSkill f = g(150)  + h(0)   = 150   <- popped before any detour
gather     f = g(13)   + h(150) = 163
rest       f = g(10)   + h(150) = 160
withdraw   f = g(5)    + h(150) = 155
```
Every cheap detour has `f > 150`; the LevelSkill child ties the root at 150 and is
popped first, so the search takes the grind, then `Craft(fire_bow)`, then `Equip` —
the 3-step plan, found in a handful of nodes.

## 3. DRY

`gated_skill_levels` is computed identically in `progression.py`
(UpgradeEquipmentGoal.relevant_actions) and `gathering.py`
(GatherMaterialsGoal.relevant_actions). Extract a shared
`required_skill_grinds(target, state, game_data) -> set[tuple[str, int]]` used by
**both** `relevant_actions` (admission — unchanged behavior) and `heuristic` (cost).
The forced-grind guard (§2.3) wraps this shared set for the heuristic; the admission
path keeps its existing (broader) predicate so no plan edge is dropped.

## 4. Lean — extend PlannerAdmissibility.lean to the real algorithm

`PlannerAdmissibility.lean` today proves only the abstract "first satisfied popped =
least g" and does **not** model the visited set. With `h≡0` that gap is harmless
(h=0 is consistent). Introducing `h≠0` makes the visited-set soundness *depend* on
consistency, so the proof must be extended or it tells a false story
(`feedback_proofs_tell_false_stories`). Add:

1. `Consistent (h : α → Nat) (cost : α → α → Nat) : Prop` — `∀ s s', h s ≤ cost s s' + h s'`.
2. A model of closed-set pruning (a `visited` set that blocks re-expansion), faithful
   to `planner.py:153-156`.
3. A theorem: a **consistent** `h` makes closed-set pruning preserve optimality — when
   a node is first popped its `g` is already least-cost, so pruning its re-expansions
   discards nothing cheaper.
4. Instantiate for the skill-grind heuristic's abstract shape (a landmark cost that is
   0 at the goal and drops by exactly the edge cost when the landmark action is taken)
   — discharging `Admissible` and `Consistent`.

Retain the existing parametric admissibility theorems; this **extends** the model,
it does not weaken it. Snapshot/fixture regen per `reference_snapshot_regen` if the
model's fixtures change.

## 5. Acceptance

1. Unit (`Goal.heuristic`): default 0.0; UpgradeEquipment/GatherMaterials return the
   forced-grind cost for a craft-gated, unowned, craft-only target; **0** for a
   satisfied goal, an already-owned target, and a target with a non-craft obtain
   source (proves the admissibility guard is real, not an always-positive rule).
2. Unit (planner): with an overriding goal, the child `f_score` uses `g + heuristic`;
   an h=0 goal plans byte-identically to before.
3. **Runtime on Robby (mandatory, `feedback_verify_runtime_activation`):**
   `UpgradeEquipment(fire_bow)` goes from 4277 nodes / timeout / `plan_len=0` to a
   found `[LevelSkill(weaponcrafting->10), Craft(fire_bow), Equip(fire_bow)]` plan in
   << budget; `chosen_root` and the emitted plan agree (no fall-through to cow).
4. Full formal gate green, including the extended `PlannerAdmissibility.lean`
   (visited-set + consistency). No mutation anchor left stale on edited lines.
5. All four censuses clean (`inventory_bug`/`planner_bug`/`recycle_source_bug`/
   `obtain_parity_bug` 0).
6. No regression: the full suite green; a spot-check goal that previously planned
   (e.g. a simple craft with skill in hand) plans the same plan.

## 6. Out of scope

- The general RPG / h_max heuristic (§1, deferred until a non-skill-gate explosion).
- Cost re-tuning (§1, rejected).
- Intermediate-material skill grinds in `h` (§2.3 scope note — admissible to omit).
- BUG B's sibling, the `next_grind_goal` held-rung livelock — already fixed and
  committed (`project_grind_held_rung_livelock`, @9a917ce5).
