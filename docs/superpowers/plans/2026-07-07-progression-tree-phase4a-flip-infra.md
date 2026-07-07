# Progression Tree — Phase 4a: Flip Infrastructure (flag-gated enactment)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the progression tree ENACTABLE behind `--progression-tree` (default OFF — zero behavior change until the live shadow data confirms the flip), with symmetric dual-tracing (whichever engine is enacted, the other stays the traced shadow), the zero-gain utility filter closed, and flag-on goldens asserting tree semantics end-to-end through the arbiter. Spec: `docs/superpowers/specs/2026-07-06-progression-tree-design.md`. Phase 4b (default flip, legacy deletion, proof retirement, TUI descent rendering, xfail promotion) is a SEPARATE later plan, gated on the corrected-shadow live data.

**Architecture:** `GamePlayer` gains `progression_tree: bool = False`; the single flip point sits where `_decide_band`/`plan_from_state` bind `decision` — flag on: `decision = tree`, legacy becomes the traced shadow; flag off: today's behavior byte-identical. `play` and `plan` grow the flag. Trace records gain `"enacted": "tree"|"legacy"` so divergence tooling knows which side acted. Sticky anchor + arbiter consume whichever decision is enacted (interface-identical by Phase-2 design).

**Tech Stack:** Python 3.13 (`uv`), pytest. No Lean changes (cores untouched).

## Global Constraints (spec + repo rules)

- DEFAULT OFF: with the flag absent/false, every enacted decision, trace record shape (minus the new `"enacted"` marker), and test outcome is unchanged. The Phase-1 goldens (which run flag-off) must pass untouched.
- Arbiter/guards/means/planner untouched. Legacy ranking internals untouched (deletion is 4b).
- BOTH engines always computed and traced while this phase is live (symmetric shadow — the flip must not blind the divergence tooling).
- Exact arithmetic; no try/except; imports at top; TDD; 100% coverage; mypy strict.
- Typer OptionInfo sentinel: every new CLI param isinstance-guarded (plan.py:104-110 convention).
- Never run gate.sh/mutate.py while the bot runs.

---

### Task 1: Flip point + symmetric shadow + CLI flags

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (`__init__`; `_decide_band` ~247-278; `plan_from_state` ~486-532; `_emit_trace` `record["tree"]` block; `_notify_observer` tree fields)
- Modify: `src/artifactsmmo_cli/commands/play.py` (flag → GamePlayer)
- Modify: `src/artifactsmmo_cli/commands/plan.py` (flag → GamePlayer, both live and --scenario paths)
- Test: `tests/test_ai/scenarios/test_plan_from_state.py` (extend), `tests/test_ai/test_player_strategy_shadow.py` (extend), `tests/test_ai/test_plan_command.py` (extend)

**Interfaces:**
- Produces:
  - `GamePlayer(..., progression_tree: bool = False)` stored as `self._progression_tree`.
  - Flip semantics at BOTH decide sites (`_decide_band`, `plan_from_state`): compute legacy `decision` and tree shadow exactly as today; then when `self._progression_tree` and the tree shadow is not None: the tree decision becomes the enacted `decision` (flows to arbiter/sticky/report), and `self._last_decision`/`self._last_tree_decision` stash SWAPPED roles is NOT wanted — keep stashes engine-true: `_last_decision` = legacy always, `_last_tree_decision` = tree always; introduce `self._last_enacted_decision` used where "the decision that acted" matters (sticky anchor update at player.py:275 feeds from the ENACTED decision's chosen_root; `_notify_observer`'s `chosen_root` snapshot field = enacted; `PlanReport.decision` = enacted).
  - `PlanReport` unchanged in shape: `decision` = enacted, `tree_decision` = tree shadow (even when tree is enacted — the compact `tree: ==/!=` line then always shows `==`; acceptable, self-documenting). NEW `PlanReport.enacted_engine: str = "legacy"` (`"tree"` when flag on).
  - `_emit_trace`: `record["enacted"] = "tree" if ... else "legacy"`; `record["strategy"]` stays LEGACY always, `record["tree"]` stays TREE always (symmetric shadow — divergence stats keep meaning across the flip).
  - CLI: `play` and `plan` gain `--progression-tree` (bool flag, default False, isinstance-guarded) passed to GamePlayer. `plan --scenario` path: construct `GamePlayer(character=scenario, history=None, progression_tree=tree_enact_flag)`.
- BINDING: flag-off behavior byte-identical (all existing tests pass unmodified); tree-enacted decision flows through the SAME arbiter/sticky path with zero special-casing beyond the decision-object swap.

- [ ] **Step 1: Failing tests**
  - `plan_from_state` flag-on (seed offline `l10_weapon_upgrade`, `GamePlayer(..., progression_tree=True)`): `report.enacted_engine == "tree"`; `report.decision.chosen_root` is the TREE root (ObtainItem weapon_slot — compare against `report.tree_decision.chosen_root`); `report.tree_decision` still populated.
  - Flag-off (existing offline test extended): `report.enacted_engine == "legacy"` and all existing assertions unchanged.
  - Trace test: flag-on player `_emit_trace` record has `enacted == "tree"`, `strategy` key = legacy repr, `tree` key = tree repr (roles NOT swapped).
  - Sticky seam: flag-on `_decide_band`-level test if the existing shadow test file exercises it; otherwise assert via `_last_enacted_decision` after plan_from_state.
  - CLI: `plan x --scenario l10_weapon_upgrade --progression-tree` output's `chosen_root:` line shows the ObtainItem root and the compact tree line shows `==`.
- [ ] **Step 2:** Verify failures. **Step 3:** Implement (the flip is a ~6-line conditional per decide site + marker plumbing; resist refactors). **Step 4:** Full suite + coverage + mypy. **Step 5:** Commit — `feat(flip): --progression-tree — flag-gated tree enactment with symmetric shadow`

---

### Task 2: Zero-gain utility filter

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/progression_tree.py` (`_utility_candidates`)
- Test: `tests/test_ai/test_progression_tree.py` (extend)

**Interfaces:** none new. `_utility_candidates` gains the same `gain > 0` guard `_structural_candidates` has (weighted gain: `potion_type_weight("hp_restore") * equip_value` must be `> 0`). Closes the Phase-2 addendum's latent flag: a zero-weighted or zero-value consumable family must never set `gear_target_exists` or appear as a candidate.

- [ ] **Step 1: Failing test** — synthetic potion whose family weight is 0 (or monkeypatch-free: an item whose `equip_value` computes 0) yields no utility candidate; existing positive-gain scenarios unchanged. Follow the existing `TestSyntheticBranches` fixture style for a zero-value utility item.
- [ ] **Steps 2-4:** fail → implement → suite green (mind the Phase-2/3 pins — they must not shift: today's live utility targets all have positive weighted gain). **Step 5:** Commit — `fix(tree): zero-gain utility candidates never arm the gear branch`

---

### Task 3: Flag-on goldens — tree semantics through the full arbiter

**Files:**
- Test: `tests/test_ai/scenarios/test_goldens_tree.py` (new)

**Interfaces:**
- Consumes: Task 1's flag; the Phase-1 scenario registry + `plan_from_state`.
- Produces: `TREE_EXPECTATIONS` — the tree-era golden set, asserting `report.selected_goal`/first-action CLASSES with the flag ON, per scenario. These are the assertions that PROMOTE to default goldens at 4b (and the Phase-1 `XFAIL_TODAY` strict xfails get reconciled then — note: some Phase-1 "design" reasons predate the adequacy decision; the tree pins are the current design truth).

Golden derivation rules (BINDING — derive, then verify against actual runs, comment any correction):
- `l3_low_hp` → `RestoreHP` (guards preempt regardless of engine — proves tertiary untouched).
- `l8_overstocked` → `DiscardOverstock` (pressure ladder preempts — same).
- `l10_weapon_upgrade` → gear chain: selected goal class derived from the tree's ObtainItem(weapon) step through the goal mapper (expect `GatherMaterials`/`UpgradeEquipment` class — record actual).
- `l1_fresh`, `l10_copper_adequate`, `l12_taskgated_bag` → run, derive from the tree pins + mapper, assert the discovered class with a derivation comment (these document tree-era behavior the way CURRENT_TODAY pinned legacy).
- Every scenario: plan non-empty OR goal `WAIT`-class — no empty arbitration (liveness).

- [ ] **Step 1:** Write the file with derivation-rule assertions; run; correct with comments where the mapper's class differs from the guess (never paper over a genuinely wrong outcome — a tree-enacted scenario selecting a nonsense goal is a BLOCKER to report, not calibrate away).
- [ ] **Steps 2-3:** suite green. **Step 4:** Commit — `test(scenarios): flag-on tree goldens — the 4b promotion set`

---

### Task 4: Wrap-up

- [ ] **Step 1:** Spec: append "Phase 4a SHIPPED" (flag name, symmetric-shadow semantics, `enacted` trace marker, promotion path to 4b; 4b checklist: default flip → legacy deletion → STRATEGY_MUTATIONS rebind → StickySelect scoring-theorem retirement → Phase-1 xfail promotion + CURRENT_TODAY deletion → TUI descent rendering → per-band L20-50 scenarios → POTION_TYPE_WEIGHTS tuning).
- [ ] **Step 2:** IF bot down: `./formal/gate.sh`. If live: record debt (likely — bot is running; the full suite via pre-commit is the interim evidence).
- [ ] **Step 3:** Commit docs; update `project_progression_tree.md`.
