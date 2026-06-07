# Resources — Yield-Rate Gather Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a needed item is the primary drop of >1 resource, gather the source minimizing expected gathers (`rate/avg_quantity`, tie-break nearest node), proven non-dominated/monotone/total/reaching in Lean and differentially cross-checked.

**Architecture:** Plumb resource drop rates into `GameData`; a pure `gather_selection.py` core (the differential target); a mirrored core-only `GatherSelection.lean` with the four property-class theorems; an oracle + differential + mutation; localized wiring in `GatherMaterialsGoal.relevant_actions`; close the `resources` matrix row.

**Tech Stack:** Python 3.13 (`uv`, pytest 100% cov, mypy strict, ruff), Lean 4 (`formal/`, exact ℚ), Hypothesis (differential).

**Spec:** `docs/superpowers/specs/2026-06-06-resources-gather-yield-design.md`

---

## File structure

| File | Responsibility | New? |
|---|---|---|
| `src/artifactsmmo_cli/ai/game_data.py` | `_resource_drops_full` + `resource_drop_table` accessor + populate | modify |
| `src/artifactsmmo_cli/ai/gather_selection.py` | pure `GatherCandidate` + `select_gather_source` | create |
| `src/artifactsmmo_cli/ai/goals/gathering.py` | yield-aware narrowing in `relevant_actions` | modify |
| `formal/Formal/GatherSelection.lean` | model + 5 theorems | create |
| `formal/Formal/{Manifest,Contracts,Audit}.lean` | register theorems + tag | modify |
| `formal/Oracle.lean` | `"gather_selection"` dispatch | modify |
| `formal/diff/test_gather_selection_diff.py` | differential | create |
| `formal/gate.sh` | add the diff test to part (d) | modify |
| `formal/diff/mutate.py` | add the core to the mutation set (if it enumerates targets) | modify (if needed) |
| `docs/behavioral_completeness/{MATRIX,PROOF_CONCEPT_INDEX,BACKLOG}.md` | close the resources row | modify (regenerate) |
| tests under `tests/test_ai/` | unit tests | create |

---

## Task 1: GameData drop-table plumbing

**Files:** Modify `src/artifactsmmo_cli/ai/game_data.py`; Test `tests/test_ai/test_resource_drop_table.py`

- [ ] **Step 1: failing test**

```python
# tests/test_ai/test_resource_drop_table.py
"""GameData retains the full resource drop table (item, rate, min_q, max_q)."""
from artifactsmmo_cli.ai.game_data import GameData


def test_resource_drop_table_returns_rows():
    gd = GameData()
    gd._resource_drops_full = {"copper_rocks": [("copper_ore", 1, 1, 1), ("topaz", 600, 1, 1)]}
    assert gd.resource_drop_table("copper_rocks") == [("copper_ore", 1, 1, 1), ("topaz", 600, 1, 1)]


def test_resource_drop_table_unknown_is_empty():
    assert GameData().resource_drop_table("nope") == []
```

- [ ] **Step 2: run, confirm fail** — `uv run pytest tests/test_ai/test_resource_drop_table.py -v --no-cov` (no attr/method).

- [ ] **Step 3: implement** — in `GameData`, add the field next to `_resource_drops` (~line 69):

```python
    _resource_drops_full: dict[str, list[tuple[str, int, int, int]]] = field(default_factory=dict)
    """resource_code -> [(item_code, rate, min_quantity, max_quantity), ...]; full
    drop table (the primary `_resource_drops` keeps only the lowest-rate item)."""
```

Add the accessor near `resource_drop_item` (~line 184):

```python
    def resource_drop_table(self, code: str) -> list[tuple[str, int, int, int]]:
        """Full (item, rate, min_q, max_q) drop rows for a resource; [] if unknown."""
        return self._resource_drops_full.get(code, [])
```

Populate in `_load_resources` (inside the `if res.drops:` block, alongside the primary):

```python
                if res.drops:
                    self._resource_drops[res.code] = min(res.drops, key=lambda d: d.rate).code
                    self._resource_drops_full[res.code] = [
                        (d.code, d.rate, d.min_quantity, d.max_quantity) for d in res.drops
                    ]
```

- [ ] **Step 4: run, confirm pass.**

- [ ] **Step 5: commit**

```bash
git add src/artifactsmmo_cli/ai/game_data.py tests/test_ai/test_resource_drop_table.py
git commit -m "feat(game_data): retain full resource drop table (item, rate, min/max qty)"
```

---

## Task 2: pure selection core

**Files:** Create `src/artifactsmmo_cli/ai/gather_selection.py`; Test `tests/test_ai/test_gather_selection.py`

- [ ] **Step 1: failing test**

```python
# tests/test_ai/test_gather_selection.py
"""select_gather_source: lex-argmin over (expected_gathers, distance, code)."""
from artifactsmmo_cli.ai.gather_selection import GatherCandidate, select_gather_source


def _c(code, rate, mn, mx, dist):
    return GatherCandidate(resource_code=code, rate=rate, min_quantity=mn, max_quantity=mx, distance=dist)


def test_picks_lower_expected_gathers_over_distance():
    # A: rate1/avg1 = 1 expected gather, far (dist 50). B: rate3/avg1 = 3, near (dist 1).
    # Fewer expected gathers wins despite distance.
    assert select_gather_source("copper_ore", [_c("A", 1, 1, 1, 50), _c("B", 3, 1, 1, 1)]) == "A"


def test_distance_breaks_expected_gathers_tie():
    # Equal expected gathers (both 2): nearer wins.
    assert select_gather_source("x", [_c("FAR", 2, 1, 1, 9), _c("NEAR", 2, 1, 1, 2)]) == "NEAR"


def test_code_breaks_distance_tie_deterministically():
    assert select_gather_source("x", [_c("b", 1, 1, 1, 5), _c("a", 1, 1, 1, 5)]) == "a"


def test_avg_quantity_reduces_expected_gathers():
    # rate 4 but yields 2-4 (avg 3) ⇒ expected 4/3 ≈ 1.33, beats rate 2 yield 1 (expected 2).
    assert select_gather_source("x", [_c("HIGHYIELD", 4, 2, 4, 9), _c("LOWYIELD", 2, 1, 1, 1)]) == "HIGHYIELD"


def test_single_candidate_returned():
    assert select_gather_source("x", [_c("only", 7, 1, 1, 3)]) == "only"


def test_empty_returns_none():
    assert select_gather_source("x", []) is None
```

- [ ] **Step 2: run, confirm fail** — module not found.

- [ ] **Step 3: implement** (`src/artifactsmmo_cli/ai/gather_selection.py`)

```python
"""Yield-rate-optimal gather-source selection. When a needed item is the primary
drop of more than one resource, pick the source minimizing the EXPECTED number of
gathers to acquire one unit — `rate / avg_quantity` — tie-broken by nearest node
then code (a total order ⇒ a unique, deterministic winner). Pure: no I/O. This is
the differential target proved in formal/Formal/GatherSelection.lean over exact ℚ.
"""

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class GatherCandidate:
    resource_code: str
    rate: int          # 1-in-N drop rate (>= 1)
    min_quantity: int  # >= 1
    max_quantity: int  # >= min_quantity
    distance: int      # Manhattan distance to nearest node (>= 0)


def _expected_gathers(c: GatherCandidate) -> Fraction:
    """Expected gathers to acquire one unit: rate / average yield. Exact rational
    (never float) so the proof is about the real ordering, not a surrogate."""
    avg_quantity = Fraction(c.min_quantity + c.max_quantity, 2)
    return Fraction(c.rate) / avg_quantity


def _key(c: GatherCandidate) -> tuple[Fraction, int, str]:
    return (_expected_gathers(c), c.distance, c.resource_code)


def select_gather_source(item: str, candidates: list[GatherCandidate]) -> str | None:
    """Return the resource_code of the lex-argmin candidate, or None if empty.
    `item` is carried for the caller's grouping; the metric does not use it."""
    if not candidates:
        return None
    return min(candidates, key=_key).resource_code
```

- [ ] **Step 4: run, confirm pass** (6 tests).

- [ ] **Step 5: commit**

```bash
git add src/artifactsmmo_cli/ai/gather_selection.py tests/test_ai/test_gather_selection.py
git commit -m "feat(ai): pure yield-rate gather-source selection (lex-argmin core)"
```

---

## Task 3: Lean model + proofs

**Files:** Create `formal/Formal/GatherSelection.lean`; Modify `formal/Formal/{Manifest,Contracts,Audit}.lean`

Use the `lean4:*` skills to prove. Mirror `gather_selection.py` as a computable Lean `def` over exact `ℚ` (the repo's fractional convention — see `Scalarizer.lean`/`DecideKey.lean` for ℚ usage; core-only, no mathlib unless a needed ℚ lemma forces `Formal/Liveness/`-style import — prefer core).

- [ ] **Step 1:** model:

```lean
-- @concept: resources @property: dominance, monotonicity, totality, reachability
namespace Formal.GatherSelection

structure Candidate where
  code : Nat        -- resource code (Nat surrogate; the diff test maps code<->index)
  rate : Nat        -- >= 1
  minQ : Nat        -- >= 1
  maxQ : Nat        -- >= minQ
  dist : Nat
deriving Repr, DecidableEq

/-- Expected gathers = rate / avg-yield, exact ℚ. avgYield = (minQ+maxQ)/2. -/
def expectedGathers (c : Candidate) : ℚ := (c.rate : ℚ) / (((c.minQ + c.maxQ : Nat) : ℚ) / 2)

/-- Lex key (expectedGathers, dist, code). -/
def key (c : Candidate) : ℚ × Nat × Nat := (expectedGathers c, c.dist, c.code)

/-- Lex-argmin selection; none on empty. (List.foldl picking the lex-min.) -/
def selectGatherSource : List Candidate → Option Candidate
  | [] => none
  | c :: cs => some (cs.foldl (fun best x => if keyLt x best then x else best) c)
-- where keyLt is the strict lex order on (ℚ × Nat × Nat); define it explicitly.
```

(Define `keyLt` as the strict lex order; prove its decidability/irreflexivity/transitivity as needed.)

- [ ] **Step 2:** prove the role theorems:
  - `select_some_iff_nonempty : selectGatherSource cs = none ↔ cs = []` (totality/no-deadlock).
  - `select_deterministic` — trivial by `def` (function), state as `∀ cs, selectGatherSource cs = selectGatherSource cs` is vacuous; instead state **`select_mem`**: `selectGatherSource cs = some c → c ∈ cs` AND **`select_is_lex_min`**: `selectGatherSource cs = some c → ∀ x ∈ cs, ¬ keyLt x c` (this IS the dominance/determinism content — the chosen one is the lex-minimum, so no candidate is strictly better).
  - `select_no_cheaper_at_le_distance` — corollary: `selectGatherSource cs = some c → ∀ x ∈ cs, expectedGathers x < expectedGathers c → x.dist > c.dist ∨ False` (no candidate has strictly fewer expected gathers AND ≤ distance). Derive from `select_is_lex_min`.
  - `expected_gathers_mono_in_rate : c1.minQ = c2.minQ → c1.maxQ = c2.maxQ → c1.rate ≤ c2.rate → expectedGathers c1 ≤ expectedGathers c2` (monotonicity; needs `minQ+maxQ > 0`).
  - `gather_selected_reaches_needed` — model gathering as `owned' = owned + 1` (per `GatherApply`); prove `∀ needed owned, ∃ n, owned + n ≥ needed` (reachability of the needed quantity by repeated +1). State minimally: `reach : ∀ (needed : Nat), owned + (needed - owned) ≥ needed` or an explicit `iterate` lemma.

- [ ] **Step 3:** `lake build Formal.GatherSelection`; axiom-check each theorem (`#print axioms`, only `{propext, Classical.choice, Quot.sound}`, no `sorry`/`native_decide`).

- [ ] **Step 4:** register: `import Formal.GatherSelection` in `Formal.lean`; `#check @Formal.GatherSelection.<thm>` lines in `Manifest.lean`; exact-statement `example : <stmt> := @<thm>` pins in `Contracts.lean`; `#print axioms Formal.GatherSelection.<thm>` lines in `Audit.lean`. Regenerate the proof-concept index: `uv run python scripts/gen_proof_concept_index.py` then `--check` → OK.

- [ ] **Step 5: commit**

```bash
git add formal/Formal/GatherSelection.lean formal/Formal.lean formal/Formal/Manifest.lean formal/Formal/Contracts.lean formal/Formal/Audit.lean docs/behavioral_completeness/PROOF_CONCEPT_INDEX.md
git commit -m "formal: GatherSelection — lex-argmin dominance/monotone/total/reach over ℚ"
```

---

## Task 4: oracle dispatch + differential + mutation

**Files:** Modify `formal/Oracle.lean`, `formal/gate.sh`; Create `formal/diff/test_gather_selection_diff.py`

- [ ] **Step 1:** add a `"gather_selection"` branch to `Oracle.lean`'s `main` dispatch (read N candidates each as `[code, rate, minQ, maxQ, dist]` integers from the args, build `List Candidate`, run `selectGatherSource`, emit the selected `code` (or `-1` for none) as JSON). Follow the existing `"gather_apply"` branch shape (~Oracle.lean:1341). `lake build oracle`.

- [ ] **Step 2:** differential test:

```python
# formal/diff/test_gather_selection_diff.py
"""select_gather_source (Python) must agree with Formal.GatherSelection.selectGatherSource (Lean)."""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.gather_selection import GatherCandidate, select_gather_source
from formal.diff.oracle_client import run_oracle

_cand = st.tuples(
    st.integers(min_value=0, max_value=50),    # code
    st.integers(min_value=1, max_value=50),    # rate
    st.integers(min_value=1, max_value=10),    # minQ
    st.integers(min_value=1, max_value=10),    # maxQ (clamped >= minQ below)
    st.integers(min_value=0, max_value=99),    # dist
)


@settings(max_examples=400)
@given(raw=st.lists(_cand, min_size=0, max_size=8, unique_by=lambda t: t[0]))
def test_selection_matches_lean(raw):
    cands = [GatherCandidate(str(c), r, mn, max(mn, mx), d) for (c, r, mn, mx, d) in raw]
    py = select_gather_source("x", cands)
    lean = run_oracle("gather_selection", [[c, r, mn, max(mn, mx), d] for (c, r, mn, mx, d) in raw])[0]
    expected_code = -1 if py is None else int(py)
    assert lean["selected"] == expected_code
```

(`unique_by` code keeps the surrogate Nat code 1:1 so the lex tie-break on code matches between sides.)

- [ ] **Step 3:** add the diff test to `formal/gate.sh` part (d) (append the path to the `uv run pytest formal/diff/...` list). If `formal/diff/mutate.py` enumerates mutation targets by module, add `src/artifactsmmo_cli/ai/gather_selection.py` so a surviving mutant fails the gate.

- [ ] **Step 4:** run: `cd formal && lake build oracle && cd .. && uv run pytest formal/diff/test_gather_selection_diff.py -q --no-cov` → PASS. Then `uv run python formal/diff/mutate.py` (or the scoped subset) → the gather_selection mutants are killed.

- [ ] **Step 5: commit**

```bash
git add formal/Oracle.lean formal/gate.sh formal/diff/test_gather_selection_diff.py formal/diff/mutate.py
git commit -m "formal(diff): gather-selection oracle + differential + mutation coverage"
```

---

## Task 5: wire into GatherMaterials.relevant_actions

**Files:** Modify `src/artifactsmmo_cli/ai/goals/gathering.py`; Test `tests/test_ai/test_gathering_yield_selection.py`

- [ ] **Step 1: failing test**

```python
# tests/test_ai/test_gathering_yield_selection.py
"""GatherMaterials.relevant_actions narrows a multi-source needed item to the
yield-optimal resource; single-source items are untouched; unknown table fail-open."""
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from tests.test_ai.fixtures import make_state


def _gd_two_sources():
    gd = GameData()
    # copper_ore is the PRIMARY drop of both rich_rocks (rate 1) and poor_rocks (rate 3).
    gd._resource_drops = {"rich_rocks": "copper_ore", "poor_rocks": "copper_ore"}
    gd._resource_drops_full = {
        "rich_rocks": [("copper_ore", 1, 1, 1)],
        "poor_rocks": [("copper_ore", 3, 1, 1)],
    }
    gd._resource_skill = {"rich_rocks": ("mining", 1), "poor_rocks": ("mining", 1)}
    return gd


def test_narrows_to_yield_optimal_source():
    gd = _gd_two_sources()
    state = make_state(skills={"mining": 5})
    goal = GatherMaterialsGoal(target_item="copper_ore", needed={"copper_ore": 10})
    actions = [
        GatherAction(resource_code="rich_rocks", locations=frozenset([(1, 0)])),
        GatherAction(resource_code="poor_rocks", locations=frozenset([(1, 0)])),
    ]
    relevant = goal.relevant_actions(actions, state, gd)
    codes = {a.resource_code for a in relevant if isinstance(a, GatherAction)}
    assert codes == {"rich_rocks"}, f"yield-optimal source only, got {codes}"


def test_single_source_untouched():
    gd = _gd_two_sources()
    state = make_state(skills={"mining": 5})
    goal = GatherMaterialsGoal(target_item="copper_ore", needed={"copper_ore": 10})
    actions = [GatherAction(resource_code="rich_rocks", locations=frozenset([(1, 0)]))]
    relevant = goal.relevant_actions(actions, state, gd)
    assert any(getattr(a, "resource_code", None) == "rich_rocks" for a in relevant)
```

- [ ] **Step 2: run, confirm fail** (both sources currently survive).

- [ ] **Step 3: implement** — in `GatherMaterialsGoal.relevant_actions` (`gathering.py`), after the existing recipe-closure filter produces the `result` list, add a narrowing pass over its `GatherAction`s. Add imports at top: `from artifactsmmo_cli.ai.actions.gathering import _nearest` (or replicate the Manhattan helper if `_nearest` is private — prefer importing it) and `from artifactsmmo_cli.ai.gather_selection import GatherCandidate, select_gather_source`. Then:

```python
        # Yield-aware narrowing: when a needed item is the PRIMARY drop of >1
        # resource present in `result`, keep only the source minimizing expected
        # gathers (proved in formal/Formal/GatherSelection.lean). Single-source
        # items and non-gather actions are untouched; an unknown drop table
        # fail-opens (no narrowing).
        gathers = [a for a in result if isinstance(a, GatherAction)]
        by_item: dict[str, list[GatherAction]] = {}
        for a in gathers:
            drop = game_data.resource_drop_item(a.resource_code)
            if drop is not None:
                by_item.setdefault(drop, []).append(a)
        drop_losers: set[int] = set()
        for item, group in by_item.items():
            if len(group) < 2:
                continue
            candidates: list[GatherCandidate] = []
            valid = True
            for a in group:
                row = next((r for r in game_data.resource_drop_table(a.resource_code) if r[0] == item), None)
                if row is None:
                    valid = False
                    break
                _code, rate, mn, mx = row
                candidates.append(GatherCandidate(
                    resource_code=a.resource_code, rate=rate, min_quantity=mn,
                    max_quantity=mx, distance=_nearest(a.locations, state) if a.locations else 0))
            if not valid:
                continue
            winner = select_gather_source(item, candidates)
            for a in group:
                if a.resource_code != winner:
                    drop_losers.add(id(a))
        if drop_losers:
            result = [a for a in result if id(a) not in drop_losers]
```

(If `relevant_actions` already names its return list something other than `result`, adapt. Verify `_nearest` is importable from `actions.gathering`; it is module-level there.)

- [ ] **Step 4: run, confirm pass**, and run the full gather + arbiter suites for regression: `uv run pytest tests/test_ai/test_gathering_yield_selection.py tests/test_ai/ -k "gather or GatherMaterials or relevant" -q --no-cov`.

- [ ] **Step 5: commit**

```bash
git add src/artifactsmmo_cli/ai/goals/gathering.py tests/test_ai/test_gathering_yield_selection.py
git commit -m "feat(arbiter): GatherMaterials narrows multi-source items to yield-optimal resource"
```

---

## Task 6: close the matrix row + full gate

**Files:** Modify `docs/behavioral_completeness/{MATRIX,BACKLOG}.md`

- [ ] **Step 1:** update the `### resources` section of `MATRIX.md`:
  - Behavior coverage → `GatherMaterialsGoal.relevant_actions yield-narrowing + gather_selection.select_gather_source (goals/gathering.py, gather_selection.py)`.
  - Proof coverage → `GatherSelection [dominance, monotonicity, totality, reachability] + GatherApply [safety] (PROOF_CONCEPT_INDEX)`.
  - Gap + policy → `CLOSED — act: gather the yield-optimal source; four classes proven (synthesis)`.
  Run `uv run pytest tests/test_audit/test_matrix_complete.py -q --no-cov` → still PASS (`lint_matrix == []`).

- [ ] **Step 2:** re-rank `BACKLOG.md` — set resources to done/score 0 (closed), so crafting (27) becomes rank 1. Hand-edit the table or re-run the leverage computation.

- [ ] **Step 3:** full gates:
  - `uv run pytest tests/ -q` → 100% coverage (gather_selection 100%; the relevant_actions narrowing branches covered — add a fail-open unit test if the `valid = False` branch is uncovered), all pass.
  - Formal: `cd formal && bash gate/check_no_orphan_modules.sh && bash gate/check_no_sorry.sh && bash gate/check_axioms.sh && bash gate/check_proof_concept_index.sh && lake build oracle && lake build 2>&1 | tail -2` → all OK; and the new differential test passes.
  - `uv run mypy src/artifactsmmo_cli/ai/gather_selection.py src/artifactsmmo_cli/ai/goals/gathering.py src/artifactsmmo_cli/ai/game_data.py` + `ruff check` → clean.

- [ ] **Step 4: commit**

```bash
git add docs/behavioral_completeness/MATRIX.md docs/behavioral_completeness/BACKLOG.md
git commit -m "docs(audit): close resources row (yield-optimal gather, 4 classes proven)"
```

---

## Self-review notes (author)

- **Spec coverage:** data plumbing→T1; pure core→T2; proofs (4 classes)→T3; differential+mutation→T4; wiring (primary-drop, multi-source only, fail-open)→T5; matrix close→T6.
- **Placeholder scan:** none (test "x"/"nope" are literal item codes, not placeholders).
- **Type consistency:** `GatherCandidate(resource_code, rate, min_quantity, max_quantity, distance)` + `select_gather_source(item, candidates)` identical across T2/T4/T5; Lean `Candidate(code, rate, minQ, maxQ, dist)` + `selectGatherSource`/`expectedGathers`/`key` consistent T3/T4; `resource_drop_table` (T1) used in T5.
- **Execution reads (not placeholders):** the exact name of `relevant_actions`'s return list + whether `_nearest` is importable (T5 verifies); the `Oracle.lean` arg-parsing offset convention for the new branch (T4 mirrors the `gather_apply` branch); whether `mutate.py` auto-discovers targets or needs the path added (T4 conditional); the precise ℚ division lemmas Lean needs for `expected_gathers_mono_in_rate` (T3, via lean4 skills).
