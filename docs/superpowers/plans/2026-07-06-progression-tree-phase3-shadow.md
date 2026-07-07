# Progression Tree — Phase 3: Shadow Wiring + Divergence Observability

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the progression tree in shadow — every cycle computes BOTH the legacy ranking decision (enacted) and the tree decision (traced only) — with `plan --tree` side-by-side output, a `stats` divergence section, a TUI `tree:` annotation, and the three Phase-2 hardening flags fixed (real adequacy signal, XP-arm fallback drop, `_ordered` assertion). Spec: `docs/superpowers/specs/2026-07-06-progression-tree-design.md` (Shadow rollout section + Phase-2 SHIPPED addendum flags).

**Architecture:** `decide_tree` gains a `band_adequate: bool` parameter (module stays pure; the caller owns the signal). `GamePlayer` computes the tree decision right after the legacy `decide()` in `plan_from_state`, stashes it, and `_emit_trace` writes it as `record["tree"]` beside the existing `record["strategy"]`. `PlanReport` carries it to the CLI; `stats` aggregates agreement from traces. Legacy stays the enacted decision everywhere — zero behavior change to the live bot.

**Tech Stack:** Python 3.13 (`uv`), pytest, existing trace JSONL pipeline. No Lean changes (cores unchanged; assembly is glue). No new dependencies.

## Global Constraints (spec + repo rules)

- ZERO enacted-behavior change: the arbiter still consumes ONLY the legacy decision. The tree is compute + trace + display.
- Trace records are not cached artifacts — no CACHE_VERSION bump needed; absent field = unobserved, never guessed (existing convention).
- Adequacy signal (user design, Option A): `band_adequate = (a winnable xp-positive band target exists for the CURRENT means) AND (no empty armor slot targeted by near_term_gear)` — both computed from EXISTING helpers (`_pick_winnable_monster`, `StrategyEngine._has_empty_armor_slot`).
- Exact arithmetic; no floats in decision paths (float only at trace/display seams via existing `to_dict`/`to_trace`).
- `uv run` prefix; imports at top; never catch Exception; TDD; 100% coverage; mypy strict.
- Never run gate.sh/mutate.py while the bot runs.
- Do not modify: arbiter, guards/means, planner, legacy ranking internals, Lean.

---

### Task 1: Tree hardening — adequacy input, XP-arm fallbacks, ordering assertion

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/progression_tree.py`
- Test: `tests/test_ai/test_progression_tree.py` (extend)

**Interfaces:**
- Produces (BINDING for Tasks 2-3): `decide_tree(state: WorldState, game_data: GameData, objective: CharacterObjective, band_adequate: bool = False) -> StrategyDecision`.
  - `band_adequate` is the caller-supplied band-adequacy verdict; the Phase-2 interim `band_adequate = candidates == []` is REPLACED by this parameter. `gear_target_exists = candidates != []` stays computed internally.
  - XP-arm fix (Phase-2 final-review finding): when the XP branch fires WITH a non-empty candidate list (now possible: adequate but upgrades exist), the gear candidates go into `fallback_steps`/`fallback_roots` (in pick order, after nothing — the trunk IS the chosen decision), so the arbiter can still fall back to gear when the trunk step yields no goal. The gear arm keeps offering the trunk as its first fallback, as today.
  - Ordering assertion (drift-risk hardening): `_ordered(candidates)[0]` must equal `gear_target_pick(candidates)`; enforce with a plain `assert` + explanatory message (proven core is the authority; the display path may never disagree).

- [ ] **Step 1: Write the failing tests (extend the existing test file)**

```python
class TestAdequacyParameter:
    def test_adequate_with_candidates_goes_xp_with_gear_fallbacks(self):
        """Adequate band + upgrades available: XP is chosen, gear candidates
        survive as arbiter fallbacks (Phase-2 final-review finding — they
        must NOT be silently dropped)."""
        gd = _bundle()
        state = scenario_state(SCENARIOS["l10_weapon_upgrade"])
        d = decide_tree(state, gd, CharacterObjective.from_game_data(gd),
                        band_adequate=True)
        assert isinstance(d.chosen_root, ReachCharLevel)
        assert any(isinstance(r, ObtainItem) for r in d.fallback_roots), (
            "gear candidates must survive as fallbacks under the XP branch")

    def test_not_adequate_defaults_preserve_phase2_pins(self):
        """band_adequate=False (the default) reproduces the Phase-2 behavior
        pins exactly — the parameter is additive."""
        gd = _bundle()
        state = scenario_state(SCENARIOS["l10_weapon_upgrade"])
        d = decide_tree(state, gd, CharacterObjective.from_game_data(gd))
        assert isinstance(d.chosen_root, ObtainItem)
        assert d.chosen_root.slot == "weapon_slot"

    def test_adequate_no_candidates_pure_xp(self):
        """Adequate + zero candidates: pure XP decision, empty gear fallbacks."""
        d = decide_tree(NO_CANDIDATE_STATE, NO_CANDIDATE_GD,
                        NO_CANDIDATE_OBJECTIVE, band_adequate=True)
        assert isinstance(d.chosen_root, ReachCharLevel)
        assert d.chosen_step == d.chosen_root
        assert not any(isinstance(r, ObtainItem) for r in d.fallback_roots)
```

(`NO_CANDIDATE_*` stand for the no-candidate synthetic fixture ALREADY used
by `TestSyntheticBranches` to reach the XP arm in Phase 2 — reuse that exact
fixture/state construction under whatever names it has; do not invent a new
one. `_bundle()` stands for the test file's existing bundle-loader helper —
match its real name.)

- [ ] **Step 2: Run to verify the new tests fail** (`TypeError: unexpected keyword argument 'band_adequate'`)

- [ ] **Step 3: Implement** — parameter + XP-arm fallback retention + the `_ordered[0] == pick` assert. Update the module docstring's interim-adequacy note to describe the new contract (caller owns the signal; Task 2 wires the real one).

- [ ] **Step 4: Full suite green, 100% coverage** (the assert's failure arm is exempt from coverage the same way other invariant asserts in the repo are — check how existing `assert` lines are treated; if coverage flags it, restructure as `if ...: raise AssertionError(...)` is NOT wanted — keep plain assert; coverage counts the line as covered when it executes truthy).

- [ ] **Step 5: Commit** — `feat(tree): adequacy parameter + XP-arm gear fallbacks + ordering assert`

---

### Task 2: Shadow wiring in GamePlayer + PlanReport

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (`plan_from_state` ~line 449 region; `_emit_trace` ~line 1128; the run-cycle decide at ~line 241 stashes via the same path)
- Modify: `src/artifactsmmo_cli/ai/plan_report.py` (new field)
- Test: `tests/test_ai/scenarios/test_plan_from_state.py` (extend) + `tests/test_ai/test_player_trace.py`-style existing trace tests (find the file that exercises `_emit_trace` and extend it)

**Interfaces:**
- Consumes: Task 1's `decide_tree(..., band_adequate=...)`.
- Produces:
  - `GamePlayer._tree_band_adequate() -> bool` — `self._pick_winnable_monster() is not None and not self._strategy._has_empty_armor_slot(state, game_data)` (private-method access within the same package is the existing pattern; if `_has_empty_armor_slot` is instance-private on StrategyEngine, call it through `self._strategy`).
  - `GamePlayer._compute_tree_shadow() -> StrategyDecision | None` — returns None when state/game_data/strategy unseeded; else `decide_tree(state, gd, self._objective, band_adequate=self._tree_band_adequate())`. Called in `plan_from_state` immediately after the legacy `decide()`; result stashed on `self._last_tree_decision`.
  - `PlanReport.tree_decision: StrategyDecision | None = None` — populated by `plan_from_state`.
  - `_emit_trace` gains, next to the existing `record["strategy"]` block: `record["tree"] = tree.to_trace()` where `tree = self._last_tree_decision or self._compute_tree_shadow()`; emitted only when non-None (absent = unobserved).
- BINDING: the legacy `decision` variable's flow to the arbiter is UNTOUCHED — the shadow computation must not reorder, replace, or feed into it. The tree shadow must also never raise into the live loop: it composes total functions over already-validated state; no try/except is permitted (repo rule) — totality is the guarantee, and the tests prove it over all scenarios.

- [ ] **Step 1: Failing tests** — (a) scenarios: `plan_from_state()` on `l10_weapon_upgrade` returns a report with `report.tree_decision is not None` and `isinstance(report.tree_decision.chosen_root, ObtainItem)`; legacy `report.decision` unchanged vs the existing assertions (extend the existing offline test). (b) trace: the existing `_emit_trace` test gets a sibling asserting `record["tree"]` present with `chosen_root` repr when strategy+game_data are seeded (mirror how the `record["strategy"]` assertion works in that test file — locate it via `grep -rn "to_trace" tests/`).

- [ ] **Step 2:** Verify failures. **Step 3:** Implement. **Step 4:** Full suite + coverage + mypy. **Step 5:** Commit — `feat(shadow): dual decision — tree computed+traced every cycle, legacy enacted`

---

### Task 3: `plan --tree` side-by-side CLI

**Files:**
- Modify: `src/artifactsmmo_cli/commands/plan.py`
- Test: `tests/test_ai/test_plan_command.py` (extend)

**Interfaces:**
- Consumes: `PlanReport.tree_decision`.
- Produces: `--tree` flag (works with AND without `--scenario`). When set, after the legacy report `_print_report` output, print a `TREE (shadow — not enacted):` block: `chosen_root`, `chosen_step`, then the descent ranking rows in the existing top-8 format. When `report.tree_decision is None`, print `tree: <unavailable — strategy not seeded>`. Default (no flag): print exactly one compact line inside `_print_report` when the report carries a tree decision: `tree: <chosen_root repr>` with agreement marker `==` / `!=` vs legacy `chosen_root` repr — so every plan invocation shows divergence at a glance.

- [ ] **Step 1: Failing tests** — (a) `--scenario l10_weapon_upgrade --tree` output contains `TREE (shadow` and an `ObtainItem` repr; (b) plain `--scenario l1_fresh` (no flag) output contains a `tree: ` line with `==` or `!=`. Remember the Typer OptionInfo sentinel: the new `tree` param must be isinstance-guarded like `scenario`/`bundle` (see plan.py:104-110 comment).
- [ ] **Steps 2-4:** fail → implement → suite green. **Step 5:** Commit — `feat(cli): plan --tree — side-by-side shadow decision`

---

### Task 4: `stats` divergence section

**Files:**
- Modify: `src/artifactsmmo_cli/commands/stats.py` (+ its `TraceStats` aggregator — follow where `_section_goals` gets its data; the aggregation type lives with the command or in a helper module — extend in place, matching existing section style)
- Test: the existing stats-command test file (locate via `grep -rn "stats" tests/ -l | head`), extend.

**Interfaces:**
- Consumes: trace records where BOTH `strategy` and `tree` keys exist (older traces lack `tree` — skip, never guess).
- Produces: `_section_tree_divergence(s: TraceStats) -> Table | None` — None when zero dual records (section omitted, matching `_section_errors` style). Otherwise:
  - total dual cycles; agreement count + % where `strategy.chosen_root == tree.chosen_root` (repr equality — `to_trace` emits reprs);
  - per-tree-branch counts (tree chose gear vs xp — derive: `chosen_root` repr startswith `ObtainItem` = gear, `ReachCharLevel` = xp);
  - top 5 divergent pairs `(legacy_root, tree_root)` by count.
- Aggregation happens in `TraceStats`' existing single-pass record loop — add fields there, no second pass.

- [ ] **Step 1: Failing test** — feed the aggregator synthetic records (2 agreeing, 1 divergent, 1 legacy-only old-format) → totals (3 dual, 2 agree, 66%…), old-format skipped, divergent pair listed. Mirror the fixture style the existing stats tests use.
- [ ] **Steps 2-4:** fail → implement → suite green. **Step 5:** Commit — `feat(stats): tree-shadow divergence section`

---

### Task 5: TUI `tree:` annotation

**Files:**
- Modify: the TUI log-line renderer that prints the per-cycle "why"/goal line (locate: `grep -rn "selected_goal\|why" src/artifactsmmo_cli/tui/ | head` — the log screen's cycle-line formatter; memory says tui/ is OUTSIDE the ruff gate but mypy still applies)
- Test: the TUI log-screen test file (locate near the renderer; TUI tests exist — Phase-1 lesson: conftest pops FORCE_COLOR, don't set NO_COLOR).

**Interfaces:**
- Consumes: the trace/cycle record's `tree` field (the TUI consumes the same records the tracer writes — find how the log screen receives cycle data: live queue or trace tail).
- Produces: when a cycle record carries `tree`, the log line gains a suffix ` tree:{==|!=}` (agreement vs the enacted root, same repr comparison as Task 4). No `tree` key → no suffix (old traces render unchanged).

- [ ] **Step 1: Failing test** on the line formatter (pure string-in/string-out if the formatter is extractable; if it is inline in a widget, extract a pure `_format_cycle_line(record) -> str` helper FIRST — statement-coverage blind spots on inline ternaries are a known repo lesson).
- [ ] **Steps 2-4:** fail → implement → suite green. **Step 5:** Commit — `feat(tui): tree-shadow agreement annotation on cycle log line`

---

### Task 6: Wrap-up

- [ ] **Step 1:** Spec: append "Phase 3 SHIPPED" (commits; adequacy signal now = winnable-band-target ∧ no-empty-armor-slot; hardening flags closed; live-review checklist: run bot, then `artifactsmmo stats --trace-file play-trace-Robby.jsonl` divergence section + `plan Robby --tree`).
- [ ] **Step 2:** IF bot down: `./formal/gate.sh` (remember: a new Lean module would need `uv run python scripts/gen_proof_concept_index.py` — Phase 3 adds none, but the check is free). If live: record debt.
- [ ] **Step 3:** Commit docs; update `project_progression_tree.md` (Phase 3 shipped; NEXT = live shadow review, then Phase 4 flip).
