# Requirement-Model Unification (EPIC)

**Date:** 2026-07-19
**Status:** DESIGNED — not scheduled, not built
**Scope decision:** **A — represent only** (approved 2026-07-19). See §3.
**Blocks:** `2026-07-19-synergy-weighting-design.md` Phase 1 (§5 of that spec)

---

## 1. Why this epic exists

Six functions answer "what does obtaining X require", and **no test anywhere asserts that
any two of them agree**. They disagree on namespace, on quantities, on whether skills count,
on whether monster drops are representable, and on cycle handling. One of them returns
different answers for the same input depending on `dict` iteration order.

The synergy-weighting design needs one demand-weighted requirement set. Adding a seventh
walk would make the problem worse. This epic unifies the existing ones.

It is **independently justified** — it does not depend on synergy ever being built:

- **D4 is a live determinism bug** (§2.4). `_item_skill_gap` is order-dependent on diamond
  recipes.
- **Three separate workarounds** exist for one representational hole (§2.2).
- **The parity oracle is missing infrastructure.** `audit/obtain_parity_completeness.py`'s
  own docstring names itself the intended future oracle; nothing yet compares walks to each
  other.

---

## 2. The defects being removed

Established by reading the code, with file:line. Two disagreements are **legitimate** and
survive as explicit parameters (§4.2); the four below are drift.

### 2.1 D1 — Namespace split

`recipe_closure` (`ai/recipe_closure.py:195`) returns **resource-node** codes
(`copper_rocks`); every other walk speaks **item** codes (`copper_ore`).
`ai/craft_plan_gen.py:80-87` documents keeping a hand-rolled DFS rather than *"forcing a
mismatched reuse."*

### 2.2 D2 — Drop-leaf blindness, three workarounds

`recipe_closure`'s two-set return cannot represent a monster-drop leaf.
`audit/craft_completeness.py:151-153` states it: `feather` is *"neither a resource code nor
craftable, so `recipe_closure`'s two-set return is blind to it."*

Three independent patches for the one hole: `objective_needs`' extra `all_ingredients` ply
(`ai/tiers/objective_needs.py:86-91`), `craft_completeness._closure_item_set`, and
`craft_plan_gen._closure_items` (`:74`).

### 2.3 D3 — Four crafting-skill-gate derivations

All over the same `recipe_closure` result, none sharing code, disagreeing on output type:

| Site | Output shape |
|---|---|
| `ai/tiers/skill_gates.py:87` `gating_skills` | `{skill: SkillGate(required_level, source)}` |
| `ai/tiers/objective_needs.py:106-123` | skill **names** only (`frozenset[str]`) |
| `ai/task_feasibility.py:44` `_item_skill_gap` | single **worst** `(skill, req, cur)` |
| `ai/goals/progression.py:261-268` | `(skill, level)` pairs |

### 2.4 D4 — Three cycle policies, one nondeterministic

Inside `ai/recipe_closure.py` alone:

| Helper | Revisit policy |
|---|---|
| `_raw_units` (`:90-91`) | per-path copy, returns **cost 1** |
| `_closure_demand` (`:120-121`) | per-path copy, returns **nothing** |
| `_closure_visited` | **threaded** shared map |

Separately, `_item_skill_gap` (`ai/task_feasibility.py:44`) uses a **shared mutable `seen`**
with no path semantics, making its result depend on `dict` iteration order whenever a
diamond appears. That is a live determinism bug and violates the project's
no-incidental-ordering rule independently of this epic.

---

## 3. Scope: represent, do not enforce

**Approved scope is A.** The unified model **represents** gathering-skill gates; no consumer
changes behavior. Every behavioral diff observed during migration is therefore a
**regression signal**, not an intended change.

This is the whole value of characterization-first ordering (§6). Bundling deliberate
behavior changes into the refactor destroys the signal exactly when it is most needed.

Two live defects are consequently **left in place and filed separately** (§8). They are real
and should be fixed — afterward, against a trusted parity oracle, where a census movement is
informative rather than ambiguous.

---

## 4. Target design

### 4.1 `RequirementGraph`

State-free. Item namespace throughout. Quantities carried. Drop-aware. One cycle policy.

```python
@dataclass(frozen=True)
class RequirementGraph:
    edges:        Mapping[str, Mapping[str, int]]      # item -> direct ingredient -> qty
    leaves:       Mapping[str, frozenset[SourceKind]]  # item -> how it can be obtained
    craft_skill:  Mapping[str, tuple[str, int]]        # item -> (skill, required_level)
    gather_skill: Mapping[str, tuple[str, int]]        # resource -> (skill, required_level)
```

`gather_skill` is populated but **unconsumed** in this epic (§3). It ships because a model
that cannot express a known livelock cause is not a unification — the P3b
`iron_ore ← iron_rocks, mining 10` hole (`7b6b4408`) must be representable even while it
stays unenforced.

### 4.2 The two legitimate axes

Preserved as explicit parameters, because different consumers genuinely need different
answers:

- **Axis 1 — edges vs closure.** `prerequisites` (`ai/tiers/prerequisite_graph.py:69`) is
  deliberately **one-ply**; `ai/tiers/strategy.py` does its own traversal on top. Collapsing
  this breaks `act_step`.
- **Axis 2 — state truncation.** `prerequisites` treats an item as a **leaf** when any ready
  non-craft source exists (withdraw, licensed recycle, live gather, located vendor, winnable
  drop) and never descends its recipe. `recipe_closure`/`objective_needs` descend regardless
  of what is held.

State-awareness becomes a **separate truncation pass over the graph**, not a property baked
into the walk.

### 4.3 Projections

| Projection | Replaces | Axis 1 | Axis 2 |
|---|---|---|---|
| `requirement_edges(g, item)` | `prerequisites` body | edges | truncation pass |
| `requirement_closure(g, roots)` | `recipe_closure` | closure | none |
| `demand_set(g, roots) -> DemandSet` | `closure_demand` + `objective_needs` | closure | none |
| `need_set(demand_set) -> NeedSet` | `objective_needs` return | closure | none |
| `skill_gates(g, roots, skills)` | **all four** of D3 | closure | none |

`NeedSet` (`ai/tiers/objective_needs.py:22`) becomes the unquantified projection of
`DemandSet`, so `objective_needs` and `means_serves` keep working at their call sites.

### 4.4 Placement — the `recipe_cost` precedent

`GameData.recipe_cost` (`ai/game_data.py:1064-1073`) is already a lazily-built derived
structure over the whole recipe table (`ai/recipe_cost_memo.py`), invalidated when
`_crafting_recipes` reloads, and covered by `formal/diff/test_recipe_cost_memo_diff.py`. Its
docstring reads *"Phase A accessor — read only; Phase B will wire planners to consume it."*

`RequirementGraph` takes exactly that slot: a `@cached_property`-style accessor on
`GameData`, same invalidation hook, same read-only discipline. This answers the placement
question by precedent rather than preference.

**`CACHE_VERSION` does not change.** The graph is *derived* from already-cached data, not
fetched. `ai/game_data_cache.py:11` is currently 4; the on-disk bundle shape is untouched.

### 4.5 What does NOT move

**The mechanically-extracted core stays exactly where it is.**
`scripts/extract_lean.py:325-344` pins the function names
`("_closure_visited", "_raw_units", "_closure_demand", "recipe_closure_pure")` and the
downstream `imports=("_closure_demand",)`. These are extracted into
`formal/Formal/Extracted/RecipeClosure.lean`, which `TaskBatch.lean:3` and
`TaskReservation.lean:3` import. The fuel argument `len(recipes)+1` is a proved-sufficient
bound (`docs/PLAN_mechanical_extraction.md:93`, P4c).

`RequirementGraph` is therefore built **on top of** the extracted core, not in place of it.
Renaming or resignaturing those four functions would break `formal/gate/check_extraction.sh`
for no benefit this epic needs. This decision shrinks the epic substantially and removes its
single largest risk.

### 4.6 What Wave 2 changed about this design (as built)

**Three deliberate deviations**, each documented at the top of `ai/requirement_graph.py`:

1. **`gather_skill` is keyed by ITEM, not resource.** §4.1's headline says "item namespace
   throughout" while its own field comment says `resource -> ...` — the spec contradicted
   itself. Item-keying is what states the livelock §4.1 cites: `iron_ore → (mining, 10)`,
   confirmed on real data. Where several resources drop one item the EASIEST gate wins.
2. **`leaves` carries only STATE-FREE kinds** (CRAFT/GATHER/DROP/BUY). WITHDRAW and RECYCLE
   are state-dependent, so baking them in would re-create axis 2 inside a model §4.1 declares
   state-free. They belong to the truncation pass.
3. **`need_set` is deferred to Wave 3.** `NeedSet.buy_only` / `.char_xp` are not functions of
   demand alone — they need `WorldState`. It migrates with `objective_needs`, where those
   semantics are in scope, rather than being guessed at here.

**Two missing `GameData` accessors, found by a failing test.** `monster_drop_items()` and
`purchasable_items()` did not exist; `gatherable_drop_items()` had no DROP or BUY counterpart.
Without them a drop-ONLY or vendor-ONLY item never enters the enumeration and the graph
reports it **unobtainable** — D2 left half-fixed in the very structure built to fix it. The
general rule now encoded in the build: *every route that can be an item's ONLY route must
contribute its items to the enumeration.*

**One import cycle broken.** `GameData` → memo → graph → `obtain_sources` → `actions.equip`
→ `actions.base` → `GameData`. `SourceKind` is a pure enum but lived in `obtain_sources`,
which drags the whole action stack, so anything `GameData` imports could not name a source
route. Extracted to `ai/source_kind.py` and re-exported (`X as X`, for mypy strict) so all
seven existing import sites are untouched and exactly one enum exists.

---

## 5. Migration hazards

### 5.1 Mutation groups are string-match based

`mutate.py` anchors mutations to **exact source text including indentation**. Reflowing a
pinned line does not fail — it silently detaches the mutation, which then keeps passing
while testing nothing.

| Anchor | Pins |
|---|---|
| `mutate.py:1164-1175` | the `⌈m/Y⌉` / `batches*qty_per` lines in `closure_demand` |
| `mutate.py:1369` | literal indentation of `stack.extend(prerequisites(...))` in `tiers/strategy.py:127` |
| `mutate.py:1191-1193` | literal `sub = _item_skill_gap(ingredient, state, game_data, seen)` |

**Every wave that touches a pinned line must refresh its `mutate.py` anchor in the same
commit**, and the mutation gate must be re-run — a green mutation run after an unrefreshed
edit is not evidence.

### 5.2 Frozen signatures

`formal/diff/test_strategy_traversal_diff.py:61` and `test_reachability_diff.py:63`
monkeypatch `prerequisites` with a fixed-arity
`fake_prerequisites(node, state, game_data, recoverable=None, exclude_recycle_leaf=False)`.
The signature is frozen by those fakes; changing it breaks the diff tests independently of
behavior.

### 5.3 Risk is inverted from consumer count

The three walks with the most consumers have the **least** proof:

| Walk | Lean | Mutation | Guarded by |
|---|---|---|---|
| `objective_needs` | none | none | unit tests only |
| `obtain_sources` / `obtain_source_map` | none | none | **two censuses only** |
| `gating_skills` | none | none | unit tests only |

`obtain_sources` holds up both `obtain_parity_completeness` and
`recycle_source_completeness` with no Lean backstop. The heavily-proven `recipe_closure`
family is comparatively *safe* to touch, because the gate catches mistakes. Migration order
(§7) follows proof coverage, not call-site count.

---

## 6. The parity oracle — characterization first

> **STATUS: Wave 0 BUILT.** `src/artifactsmmo_cli/audit/requirement_parity.py`,
> `scripts/gen_requirement_parity.py`, `tests/test_audit/test_requirement_parity.py`,
> matrix at `docs/behavioral_completeness/REQUIREMENT_PARITY_MATRIX.md`, wired as the
> fifth `census-gate.yml` step. **321 targets, 0.0s** — the process pool §6 anticipated
> was unnecessary. Measured: D1 282, D2 282, D3 244, axis-2 truncation 2.
>
> **`--check` is a DRIFT gate, not a `== 0` residual** — the one deviation from the four
> existing censuses, and deliberate. This census pins defects on purpose, so a bug count
> would be either permanently red or would launder D1–D4 into "expected", which is the
> exact flattering-gate failure the epic exists to undo. It fails when the committed
> matrix and a fresh run disagree; the reviewer then decides D-fix or regression.

**Wave 0 delivers a test that asserts current behavior, disagreements included.** No
production code changes in this wave.

The oracle enumerates a fixture corpus of targets and records, per target, what each walk
answers — including where they differ. Disagreements are asserted **as-is**, with each
encoded expectation naming the defect it embodies (D1–D4) or marked as a legitimate axis
difference (§4.2).

That makes every later wave binary: a diff is either an intentional D-fix, or a regression.

**Placement: `src/artifactsmmo_cli/audit/` with a thin test in `tests/test_audit/`.** It is
closer in kind to the existing censuses than to a unit test — it enumerates a corpus, it is
slow, and it belongs on the census budget rather than the unit-test one. Precedent:
`tests/test_audit/conftest.py` already provides session-scoped `bundle_game_data` and
`full_census` fixtures because rebuilding bundle `GameData` "costs seconds."

Wire it as a fifth check in `.github/workflows/census-gate.yml` (currently four sequential
`--check` steps, 30-minute job budget) alongside `inventory_bug`, `recycle_source_bug`,
`planner_bug`, `obtain_parity_bug`.

---

## 7. Migration waves

Ordered by proof coverage — safest first, so the oracle is trusted before it is leaned on.

| Wave | Content | Risk | Notes |
|---|---|---|---|
| **0** | Parity oracle (§6). No production change. | — | ✅ **BUILT + green.** Must land and be green before Wave 2 |
| **1** | **Delete dead walks.** `gating_skills` and `raw_material_units` — **zero production call sites** | low | ✅ **DONE @e9cf0924.** `skill_gates.py` deleted WHOLE (all four symbols dead, not just the entry point) + LIV-SKILL-3, which proved a property of code the bot never ran. R1 resolved against both offered options — see §10 |
| **2** | Build `RequirementGraph` + projections on top of the extracted core (§4.5). Nothing consumes it yet | low | ✅ **DONE.** Additive; oracle green. 3 deliberate deviations + 2 missing GameData accessors found — see §4.6 |
| **3** | Migrate `objective_needs` (one production caller, `strategy_driver.py:1304`, no Lean/mutation coupling) | low | First real consumer swap; validates the oracle |
| **4** | Migrate the uniform easy sites: `gather_serves_closure` (5 boolean-filter sites) and `recipe_closure` non-audit callers (5 goal modules + `craft_ladder.py:50`) | low-med | All share one destructure shape; several already discard the resource set |
| **5** | Migrate `closure_demand`'s 11 threaded-accumulator sites | **med-high** | Callers mutate a caller-owned dict; `goals/gathering.py:241` and `maintain_consumables.py:75/:80` accumulate **multiple** calls into one shared dict, so a return-value form changes merge semantics. Refresh `mutate.py:1164-1175` |
| **6** | Migrate `prerequisites` | **high** | Two mutation groups against two different test paths; frozen fake signature (§5.2); feeds both GOAP traversal and the TUI plan tree via `plan_tree.py:48` → `cycle_snapshot`. Refresh `mutate.py:1369` |
| **7** | Migrate `task_requirement` / `_item_skill_gap` — **this is where D4 is discharged** | **high** | Its None/non-None boundary is an *upstream input* to unrelated proofs (`test_ladder_fires_diff.py:1485-1668`, `test_goal_system_value_diff.py:597`, `test_plan_exists_diff.py:304`). Two Lean oracles. Refresh `mutate.py:1191-1193` |
| **8** | Migrate `obtain_sources` consumers | **high** | Census-only coverage, no Lean. Bidirectional set equality; WITHDRAW carveout is deliberate (`obtain_parity_completeness.py:44-66,482`) |
| **9** | Delete superseded walks and their now-duplicate tests | low | Oracle proves nothing was lost |

Waves 5–8 each land as their own commit with their own gate run. Waves 1–4 may batch.

---

## 8. Filed separately — NOT in this epic

Found while designing; real, and deliberately excluded per §3.

**F1 — WITHDRAWN 2026-07-20. Not a defect; the premise was wrong.**

This was recorded as "the parity census asks the POOL side via a skill-enforcing predicate
against a MODEL side that cannot enforce it, so under-skilled gathers diverge — green only
because no fixture hits the case." **Probed empirically; both directions hold.**

The structural observation is true: `_gather_sources(item, game_data)`
(`ai/obtain_sources.py:238`) never receives `state` and is the only source kind with a
state-free eligibility predicate. The conclusion drawn from it was not. The census carries a
deliberate asymmetry that covers exactly this case (`obtain_parity_completeness.py:489-501`):

| Direction | `applicable_only` | Under-skilled gather |
|---|---|---|
| POOL ⊆ MODEL | `True` — only actions that can fire now | `{} ⊆ {GATHER}` ✓ |
| MODEL ⊆ POOL | `False` — inapplicable entries still count | `{GATHER} ⊆ {GATHER}` ✓ |

Measured against a synthetic `deep_rocks` (mining 10) with the character at mining 1:
`MODEL = {GATHER}`, `POOL(applicable_only) = {}`, `POOL(all) = {GATHER}`, both subset checks
`True`.

The state-free predicate is moreover *correct* for the model's purpose. `prerequisite_graph`
leafs on a GATHER source regardless of skill, and since P3b a skill-locked gather genuinely
IS obtainable via LevelSkill → Gather. A source-layer skill gate would wrongly mark it
unreachable — reintroducing the livelock P3b fixed, and it would have to reproduce the
`skill_open` narrowing hazard (`ai/gather_skill_gate.py`) besides.

Left as-is deliberately. Retained here as a record so the "obvious" gate is not re-proposed.

**F2 — FIXED 2026-07-20 (`879a5f59`).** `UpgradeEquipmentGoal` never received the P3b
gather-gate fix: it built `gated_skill_levels` from `crafting_skill`/`crafting_level` alone
while its comment claimed to mirror `GatherMaterialsGoal`. An equippable whose material's
only source was a locked gather was therefore unplannable from that goal — the `GatherAction`
was admitted but the `LevelSkill` that could open it was not, so it sat in the pool
permanently unreachable.

Root cause was that the logic was mirrored *by comment* rather than shared as code. Fixed at
that level: extracted to `ai/gather_skill_gate.py` (`openable_gather_grinds`, `skill_open`,
`level_below_and_grindable`), consumed by both goals. `GatherMaterialsGoal` behaviour is
unchanged — the extracted function is its former body verbatim.

**F3 — FIXED 2026-07-20 (`879a5f59`).** `ai/actions/level_skill.py`'s docstring said the
action "raises a *crafting* skill"; it has opened gathering gates since P3b.

---

## 9. Verification

| Concern | Approach |
|---|---|
| No behavior changed | Parity oracle green at every wave (§6) — this is the epic's primary gate |
| Existing censuses | `census-gate.yml` four checks stay at zero: `inventory_bug`, `recycle_source_bug`, `planner_bug`, `obtain_parity_bug` |
| Extraction intact | `formal/gate/check_extraction.sh` — §4.5 means this should never move |
| Mutation groups still attached | Every wave touching a pinned line refreshes its anchor **in the same commit** and re-runs the mutation gate (§5.1) |
| D4 discharged | `test_requirement_set_order_independent` — same input, shuffled `dict` order, identical output. Must fail before Wave 7 |
| Determinism generally | No `repr`/alphabetical ordering introduced anywhere |
| CPU | `RequirementGraph` build time measured against the `recipe_cost` precedent; census job stays inside its 30-minute budget |

Gate discipline note: this project merges to `main` with no PR, so the gate must be green
**before** the push — there is no review step downstream to catch a red one.

---

## 10. Residuals

**R1 — ✅ RESOLVED in Wave 1 (@e9cf0924), and BOTH offered options were wrong.** They shared a
stale premise: that the walk's proof coverage stood or fell with the function. It does not.
`raw_material_units` was a thin wrapper over `_raw_units`, and **`_raw_units` is
production-live** (`task_batch.craft_batch_size_pure` → `strategy_driver` /
`actions.factory` / `intermediate_batch`). So "delete all three together" would have stripped
proof coverage OFF live code, and "keep it as a proof-only artifact" would have left the
differential verifying a shim one indirection from production — the exact
proofs-over-unreachable-code failure this epic exists to undo.

**Resolution: delete the wrapper, repoint the coverage ONTO the live primitive.** All Lean
retained. The mutation anchor needed no re-anchoring — its text was always inside
`_raw_units`' body; only its *label* named the wrapper (and the cited `mutate.py:1144` was
itself stale, actually `:1173`). Unit + differential tests now call `_raw_units` in the live
call shape. `Oracle.lean`'s emitted JSON key was renamed to `raw_units` for the same reason a
stale citation misleads.

**Generalisable lesson for Waves 2-9:** before deleting a walk, check whether it is a *wrapper*
over an extracted-core primitive. The core primitives (`_raw_units`, `_closure_visited`,
`_closure_demand`, `recipe_closure_pure`) are where the Lean actually bites; a public wrapper
being dead says nothing about whether the thing underneath it is.

**R2 — ✅ MEASURED in Wave 2.** Whole-table build over the committed bundle: **4.8 ms**
(321 edges, 522 leaves, 321 craft gates, 42 item-keyed gather gates). Cached access **4 µs**
with object identity preserved. The `recipe_cost` precedent was right — no lazy-per-root
scheme is needed, and the memo can safely rebuild whenever its input fingerprint moves.

**R3 — Some consumer may legitimately keep its own walk.** §7 assumes all migrate. If one
has a genuine reason not to, that is an acceptable outcome — but it must be *documented at
the call site*, not left as an unexplained survivor.

**R4 — The oracle encodes current behavior, including behavior that is wrong.** D1–D4 are
asserted as-is in Wave 0 and only flipped in the wave that fixes them. A reader of the Wave 0
test must not mistake its expectations for endorsements; each must name the defect it pins.

---

## 11. Explicitly out of scope

- Enforcing gathering-skill gates anywhere (F1) — this epic represents only (§3).
- Extending `UpgradeEquipmentGoal` (F2).
- Renaming or resignaturing the mechanically-extracted core (§4.5).
- Any change to `select_pure`, the band ladder, `falloff`, or `dhondt_step`.
- Synergy itself — this epic delivers `DemandSet`; the synergy design consumes it.
- Reviving `ReachSkillLevel` as a `MetaGoal` variant. It was deleted in `7b6b4408` across
  `meta_goal.py`, `strategy.py`, `objective_needs.py`, `equipment_profile.py`,
  `plan_tree.py`, and the Lean models. `RequirementGraph` carries `craft_skill` as **data**;
  node **emission** stays retired. Data availability and node emission are separate concerns
  and only the latter was ever withdrawn.
