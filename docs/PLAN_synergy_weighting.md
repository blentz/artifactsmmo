# PLAN — Synergy Weighting Epic (execution tracker)

**Design spec:** `docs/superpowers/specs/2026-07-19-synergy-weighting-design.md` (717 lines, approved, on main).
**This doc:** the executable, cross-session wave breakdown. The spec is the *why*; this is the *what-next*.

`weight = gain × falloff(focus) × synergy` — magnitude × staleness × **purity**.
Synergy = demand-weighted fraction of a candidate's own work (`A`) that overlaps the other live roots (`B`), leave-one-out, floored at `S_MIN = 1/3` and bounded strictly inside `falloff`'s 9:1 so aging always dominates alignment.

---

## Status ledger

| Phase | What | State |
|---|---|---|
| **0** | Pure bug fixes (taskmaster keying / task-pool retention / accept_task plumbing) | ✅ **DONE** `0836ed4d` (0.1+0.2) + field laid 2026-07-22 (0.3 projection deferred to Phase 4 **by design** — factory emits only the monsters master today) |
| **1** | Requirement-model unification (its own epic) | ✅ **DONE** — closed last session (`2bfd47f9..5d7b19b9`). `RequirementGraph` + projections live; `demand_set → DemandSet` is the quantified form synergy consumes |
| **2** | Synergy core (`synergy_core.py` + `Synergy.lean`) — pure, full triple gate | ⬜ **NEXT** |
| **3** | Tree call site (`_scaled_weights`, `_NO_SYNERGY`, B-assembly, fast-path trap) | ⬜ |
| **4** | Taskmaster choice (argmax expected synergy, reroll-aware top-quantile) | ⬜ — blocked on R1 live probe |
| **5** | Within-band `DISCRETIONARY_ORDER` sort | ⏸ **DEFERRED** — build only on live-trace evidence (spec §Phase-5 misgiving) |

---

## Wave 2 — Synergy core  ⟵ START HERE

Pure, integer/`Fraction` only, **ships extracted** (all three legs: extraction + differential + mutation), structural twin of `falloff`. Zero integration risk — nothing consumes it yet.

```python
# src/artifactsmmo_cli/ai/tiers/synergy_core.py
S_MIN: Fraction = Fraction(1, 3)

def synergy_pure(shared: int, total: int) -> Fraction:
    if total <= 0:
        return Fraction(1)          # §3.4 degenerate: needs nothing == maximally aligned
    assert shared <= total, ...     # ASSERT not clamp — shared>total means assembly layer is wrong
    return S_MIN + (Fraction(1) - S_MIN) * Fraction(shared, total)
```

**Steps (TDD — each test must fail before, pass after):**
1. `test_synergy_core_bounds` — `S_MIN ≤ synergy ≤ 1` over swept `(shared, total)` grid.
2. `test_synergy_total_zero` — `synergy(s, 0) == 1` ∀ s.
3. `test_synergy_asserts_shared_gt_total` — raises, does not clamp.
4. `test_synergy_range_inside_falloff` — `S_MAX/S_MIN < FOCUS_1/FOCUS_FLOOR` as arithmetic over the *real* constants (retuning either trips it). **The §3.5 load-bearing invariant.**
5. ✅ Write `synergy_pure` + `S_MIN` (`src/artifactsmmo_cli/ai/tiers/synergy_core.py`).
6. ✅ `formal/Formal/Synergy.lean` — 5 theorems, twins of `falloff_le_one/ge_floor/floor_pos`:
   `synergy_le_one`, `synergy_ge_floor`, `synergy_floor_pos`, `synergy_monotone`, `synergy_total_zero`
   (+ self-contained Rat helpers; imports nothing, matching ProgressionTree convention). `lake build` green.
7. ✅ Mutation group `SYNERGY_CORE_MUTATIONS` in `formal/diff/mutate.py` (5 mutants, each killed by a named
   test), `run_group(... test_synergy_core.py ...)`, anchors unique (595 total). All 5 killed.

**DEVIATION FROM SPEC — extraction/differential leg dropped (recorded, not silent).**
Spec §Phase-2/§7 asks the core to "ship extracted" (full triple gate). But the SAME §Phase-2 also
mandates it "ASSERTS rather than clamps" (pinned by `test_synergy_asserts_shared_gt_total`), and the
AST extractor (`scripts/extract_lean.py:105,1658`) **structurally rejects `assert`** — a total Lean
function cannot carry a partial contract. The two requirements are mutually exclusive for this function.
Removing the assert is forbidden (spec-mandated contract; catches real assembly-layer over-counts) and
a second impl is forbidden (CLAUDE.md). Resolution: match **`falloff`'s exact precedent** — falloff is
also a `Fraction`-returning curve and ships hand-model + mutation, no extraction/differential. The hand
model PROVES the five bounds; the mutation gate BINDS Python to them. The differential leg's only added
guarantee (Python==Lean byte-equal) is redundant for a proven 1-line affine map. Verification is at
falloff-parity, which the spec itself treats as the baseline for `Fraction` curves.

8. Gate: `lake build` (all), `--check-anchors`, synergy mutation leg, full suite 100% cov — **serialized**.

**Verify:** `synergy_le_one` is the `≤1` bound that keeps synergy inside falloff; `synergy_floor_pos` is the `minWeight_pos` feeder that preserves `interleaveDue_reaches` (no-starvation). Both state and prove cleanly — curve shape correct.

---

## Wave 3 — Tree call site

**Split into two landable sub-waves (spec §3.8: "ship `_NO_SYNERGY` wired and prove the plumbing inert first, before real values available"):**

### Wave 3a — plumbing, provably INERT ✅ SHIPPED @025f04ca
- ✅ `_NO_SYNERGY` sentinel (in `progression_tree_core.py`) + `_scaled_weights`/`focus_aging_pick`/`focus_aging_order` gain a DEFAULTED `synergy` param (third factor, keyed `(slot,code)`). Empty default = byte-identical. `decide_tree`/`player.py` UNTOUCHED — fully inert.
- ✅ FAST-PATH TRAP fix: guard → "nothing stale AND no synergy signal".
- ✅ Lean lockstep: `scaledWeights`/`focusAgingPick` gain defaulted synergy assoc-list (`synergyOf`, default `[]`→1); `focusAgingPick_unaged_eq_argmax` holds.
- ✅ 4 tests + 2 new mutants (fast-path-ignores-synergy trap, drop-synergy-factor) + 2 refreshed anchors. Gate green: lake build, anchors 597, mutation 14/14, suite 100%.
- **Note:** `decide_tree` NOT touched in 3a (cleaner inert proof). 3b wires it.

### Wave 3b — real B-assembly, ACTIVATES synergy (item namespace)
- ✅ `_synergy_map` two-pass leave-one-out B-assembly in `decide_tree` (§3.6, item namespace). Members = sibling candidates + committed root + items-task (monsters-task omitted — enriched namespace is 3c). Committed-root double-count deliberate.
- ✅ Memoized `demand_for(code)` on the graph memo (R3), cleared on graph rebuild.
- ✅ Threaded `committed_root_code` + `enable_synergy` opt-in through `strategy.decide` → `decide_tree`; player wires `enable_synergy=True`. Every non-opt-in caller stays inert (kill switch, §3.8).
- ✅ `decide_tree.aged_pick` recompute widened to include the synergy signal (seat-ledger consistency).
- ✅ Tests: `test_synergy_assembly.py` (currency_root_suppressed, committed_root_double_counts, leave_one_out_not_degenerate, items-task-member, empty→_NO_SYNERGY, **fires-on-real-graph**) + 5 mutants. 149 scenario tests + 324 decide-path tests green with synergy active.
- **DEFERRED to 3c**: `means_serves` generalization, `task_skill_convergence`, level-up (all need enriched char_xp/skill_xp namespace — item-only would regress the task gate).

### Wave 3c — enriched namespace (char_xp / skill_xp / drops) ✅ BUILT
**User forks (2026-07-23):** closure-count weighting; generalize means_serves now.
- ✅ `requirement_multiset_for(code)` on the graph memo: item quantities + `skill:<name>` tokens (weight = #closure items gated by that craft/gather skill) + `char_xp` token (weight = #DROP leaves). Closure-count weighted, self-scaling, no tuned constant. Memoized, cleared on rebuild.
- ✅ `_synergy_map` uses the enriched multiset; char-level trunk is ALWAYS a member (`_TRUNK_DEMAND={char_xp:1}`); monsters-task enters as a char_xp member (produces char progression, not items); items/gather task by full enriched requirement.
- ✅ `means_serves` generalized to `synergy_pure(overlap, 4) > S_MIN` over task-output-vs-need — **provably equivalent** to the old OR-of-clauses (`> S_MIN ⟺ overlap > 0`), so non-regressing; `means_worth` tests pass unchanged.
- ✅ Tests: `task_skill_convergence`, `level_up_preference`, monsters-task char_xp, enrichment-fires-on-real-graph, differential recompute. 149 scenario + 302 decide-path + 9 means_worth green.
- ✅ Mutants: monsters-branch-flip, trunk-not-member, char-count-zero, craft-weight, means threshold, char-clause. No Lean/core change (values flow through 3a's widened `_scaled_weights`).

---

### Wave 3 detail (reference)

- `_NO_SYNERGY: Mapping[tuple[str,str], Fraction] = MappingProxyType({})` (mirror `_NO_FOCUS`/`_NO_SEATS`); missing entry reads as `Fraction(1)`.
- `_scaled_weights(candidates, focus, synergy=_NO_SYNERGY)` — multiply the third factor in, keyed `(slot, code)` (same as `_gear_focus`).
- B-assembly **two-pass** in `decide_tree` (§3.6): build N demand sets once → multiset union → leave-one-out by multiset subtraction. Members: trunk `ReachCharLevel` (char_xp) + sibling candidates + committed root + current task. Committed root double-counts **deliberately** (pin with `test_committed_root_double_counts`).
- **⚠️ FAST-PATH TRAP** (`focus_aging_pick:193`): short-circuit guard must become "nothing stale **AND** no synergy signal", else synergy is silently inert for FOCUS_FLAT=10 cycles of every root. `test_fast_path_respects_synergy`.
- `means_serves` → generalize to `synergy(...) > S_MIN` (the boolean special case) — do NOT parallel it.
- Structural: `test_no_synergy_map_is_inert` (byte-identical to pre-Wave-3), `test_synergy_absent_from_repr` (synergy cannot enter `repr_` — the currency-grind identity-churn lesson), `test_leave_one_out_not_degenerate`.
- Lean `ProgressionTree.lean` updates in lockstep with widened signatures only; `falloff`/`dhondt_step`/`interleave_due`/`_gear_pref_key` UNTOUCHED.
- Memo the B-assembly per §R3 (feather_coat CPU precedent).
- Worked-case tests: `test_currency_root_suppressed`, `test_task_skill_convergence`.
- **Runtime activation**: must fire on live `plan <char>` (green tests ≠ runtime-active).

## Wave 4 — Taskmaster choice  ⟵ UNBLOCKED (R1 resolved)

- **R1 RESOLVED 2026-07-23** (live OpenAPI probe): completion + exchange work at ANY tasks_master (only error 598 = "no tasks master on this map"), NOT the issuing one; accept has no type param → task TYPE is positional (which master tile). Live `/maps`: 2 tiles (1,2)+(4,13), matches fixture. **Consequence: no completion travel-cost penalty** — master choice optimizes task-type distribution ONLY; complete/exchange route to nearest tile.
- argmax `E_synergy(M)` over `tasks_for(M.code, char_level)`, reroll-aware top-quantile: `k = max(1, ceil(n·1/3))`, tiebreak `task_code` (semantic; flagged as the one identifier ordering a decision).
- Wire at `AcceptTaskGoal()` construction (`strategy_driver.py:382`); goal carries chosen master → `accept_task.apply` projects `task_type` from `taskmaster_code` (completes 0.3). Factory re-points all 5 task actions per master.
- Synergy NEVER enters `AcceptTaskAction.cost` (admissibility trap).
- `test_phase4_inert_with_one_taskmaster` (provably inert until Phase 0 — which is landed).

## Wave 5 — Within-band ordering  ⏸ DEFERRED
`DISCRETIONARY_ORDER` sorted by synergy. Recorded misgiving: reorders means the worth gate ALREADY admitted. Build only if a live trace shows an aligned means losing to a less-aligned one in the same band.

---

## Standing invariants (do not violate)
- Synergy is **cardinal computation, ordinal consumption** — dies at `decide_tree`; `Candidate` gets no weight field; `select_pure` never opened.
- Synergy NEVER in any action cost / planner heuristic (`f=g+h` admissibility).
- No `repr`/alphabetical tiebreak anywhere in the synergy path (feedback_no_alphabetical_tiebreak).
- Gate runs serialized — never concurrent with anything importing src (feedback_serialize_gate_runs).
- Mutation anchors refreshed in the same commit as the source edit.
- Merge to main directly, fast-forward `git push origin HEAD:main`, gate green BEFORE push (no PR to catch it).
- 0 errors / 0 warnings / 0 skipped / 100% coverage.
