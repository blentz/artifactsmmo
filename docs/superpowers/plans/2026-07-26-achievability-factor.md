# Achievability Factor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Down-weight gear candidates by effort-to-reach, so `life_ring` (craftable) outranks `lich_race_trophy` (1000 event_tickets) despite a lower raw gain.

**Architecture:** A fourth bounded multiplier in the tree's selection weight — `gain * falloff * synergy * achievability` — built exactly like the existing synergy factor: a pure scalar core in `tiers/`, mirrored by a Lean module, assembled by an impure map in `progression_tree.py`, and multiplied in `_scaled_weights`. Effort is UNMET demand (demand minus holdings) over the enriched requirement multiset, which must first be taught to expand buy-only currencies transitively.

**Tech Stack:** Python 3.13, `Fraction` (no floats in the decision path), Lean 4 / lake, pytest, `uv`.

## Global Constraints

- Prefix every Python command with `uv run` (project rule).
- `A_MIN = Fraction(1, 2)` — the ONLY tuning surface, mirroring `S_MIN`'s discipline.
- Factor hierarchy: `falloff` 9:1 ⊃ `synergy` 3:1 ⊃ `achievability` 2:1. Effort informs, never dictates.
- No floats in the decision path — exact `Fraction` throughout.
- ONE behavioural class per file; pure cores take plain scalars, not `GameData`/`WorldState`.
- Do NOT use `if TYPE_CHECKING`. Do NOT catch `Exception`. Imports at top of file.
- 100% coverage, 0 warnings, 0 skipped. Tests live in `tests/`.
- Never run `formal/gate.sh` concurrently with anything else importing `src` — **the live bot counts**. Check `pgrep -af "artifactsmmo play"` first; if it is running, say so in your report rather than running the full gate.
- Source spec: `docs/superpowers/specs/2026-07-26-achievability-factor-design.md`.

## File Structure

| File | Responsibility |
|---|---|
| `src/artifactsmmo_cli/ai/tiers/achievability_core.py` | CREATE — pure scalar core: `A_MIN`, `achievability_pure(effort, min_effort)` |
| `formal/Formal/Achievability.lean` | CREATE — Lean mirror + bounds/antitone proofs |
| `formal/Formal/Manifest.lean` | MODIFY — traceability rows (Audit.lean regenerates from it) |
| `src/artifactsmmo_cli/ai/requirement_graph_memo.py` | MODIFY — transitive currency expansion |
| `src/artifactsmmo_cli/ai/tiers/progression_tree.py` | MODIFY — `_effort_map`, wire into `decide_tree` |
| `src/artifactsmmo_cli/ai/tiers/progression_tree_core.py` | MODIFY — `_scaled_weights`, flat-window clause |
| `formal/diff/mutate.py` | MODIFY — anchors for `A_MIN` and the new arms |

---

### Task 1: Transitive currency expansion (hard prerequisite)

The multiset enriches a BUY leaf with `price * quantity` in its currency, but only for items IN the closure. `lich_race_medal` is not a closure member, so its own 100-ticket price is never expanded — `lich_race_trophy` scores effort 11 and reads as the CHEAPEST candidate. Measured: without this, the factor makes the ordering WORSE than today.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/requirement_graph_memo.py:134-140`
- Test: `tests/test_ai/test_requirement_graph_memo.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `requirement_multiset_for(code)` now expands buy-only currencies transitively. Task 3 reads its output.

- [ ] **Step 1: Write the failing test**

```python
def test_buy_only_currency_expands_transitively():
    """lich_race_trophy costs 10 lich_race_medal; each medal costs 100
    event_ticket. The multiset must show the 1000 tickets, not stop at 10
    medals — un-expanded, the most expensive candidate reads as the cheapest."""
    gd = _gd_with_chain()          # trophy <- 10 medal <- 100 event_ticket each
    ms = gd.requirement_graph.requirement_multiset_for("trophy")
    assert ms.get("event_ticket") == 1000
    assert "medal" not in ms, "the intermediate currency must be expanded, not listed"


def test_currency_cycle_terminates():
    """A priced in B priced in A must not recurse forever."""
    gd = _gd_with_cycle()          # a <- 1 b, b <- 1 a
    assert gd.requirement_graph.requirement_multiset_for("a") is not None
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_requirement_graph_memo.py -k transitively -x -q --no-cov`
Expected: FAIL — `ms.get("event_ticket")` is None, `medal` present with 10.

- [ ] **Step 3: Implement**

Replace the BUY-leaf arm at `requirement_graph_memo.py:134-140` with a helper that walks the currency chain:

```python
    def _currency_cost(self, item: str, qty: int,
                       seen: frozenset[str] = frozenset()) -> tuple[str, int] | None:
        """(currency, units) for a buy-only item, following the chain to the
        currency you actually EARN. lich_race_trophy costs 10 lich_race_medal,
        each 100 event_ticket, so the real cost is 1000 tickets — stopping at
        the medal hides three orders of magnitude of work. `seen` breaks
        currency cycles; the depth is bounded by the chain, which is finite
        because each hop must name a different currency."""
        purchases = self._game_data.npc_purchases(item)
        if not purchases or item in seen:
            return None
        _npc, price, currency = min(purchases, key=lambda p: p[1])
        deeper = self._currency_cost(currency, price * qty, seen | {item})
        return deeper if deeper is not None else (currency, price * qty)
```

and call it in place of the inline pricing:

```python
                if SourceKind.BUY in graph.leaves.get(item, frozenset()):
                    priced = self._currency_cost(item, out.get(item, 1))
                    if priced is not None:
                        currency, units = priced
                        out[currency] = out.get(currency, 0) + units
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_ai/test_requirement_graph_memo.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Verify against live game data**

Run:
```bash
uv run python -c "
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config
cm = ClientManager(); cm.initialize(Config.from_token_file())
gd = GameData.load(cm.client)
ms = gd.requirement_graph.requirement_multiset_for('lich_race_trophy')
print({k: v for k, v in ms.items() if v > 5})"
```
Expected: `event_ticket` ≈ 1000 present; `lich_race_medal` absent.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/requirement_graph_memo.py tests/test_ai/test_requirement_graph_memo.py
git commit -m "fix(requirements): expand buy-only currencies transitively

The multiset priced a BUY leaf in its DIRECT currency and stopped. lich_race_trophy
read as 10 lich_race_medal — 11 tokens — hiding that each medal costs 100
event_ticket, so the real cost is 1000 tickets of ordinary combat. Any consumer
ranking by multiset size saw the most expensive item in the catalog as the
cheapest. Synergy consumes the same multiset and was blind to it too."
```

---

### Task 2: The pure achievability core

**Files:**
- Create: `src/artifactsmmo_cli/ai/tiers/achievability_core.py`
- Test: `tests/test_ai/test_achievability_core.py`

**Interfaces:**
- Consumes: nothing (pure scalars).
- Produces: `A_MIN: Fraction`, `achievability_pure(effort: int, min_effort: int) -> Fraction`. Task 4 imports both.

- [ ] **Step 1: Write the failing test**

```python
from fractions import Fraction

from artifactsmmo_cli.ai.tiers.achievability_core import A_MIN, achievability_pure


def test_the_cheapest_candidate_is_unpenalised():
    assert achievability_pure(effort=18, min_effort=18) == Fraction(1)


def test_effort_is_relative_not_absolute():
    """Self-scaling: only the RATIO matters, so no absolute effort constant."""
    assert achievability_pure(9, 4) == achievability_pure(19, 9)


def test_a_far_costlier_candidate_approaches_the_floor():
    a = achievability_pure(effort=1000, min_effort=18)
    assert A_MIN < a < Fraction(3, 5)


def test_never_below_the_floor():
    assert achievability_pure(effort=10**9, min_effort=0) >= A_MIN


def test_never_above_one():
    assert achievability_pure(effort=0, min_effort=99) <= Fraction(1)


def test_antitone_in_effort():
    """More effort scores no higher — the defining property."""
    prev = Fraction(2)
    for effort in range(0, 200, 7):
        cur = achievability_pure(effort, min_effort=5)
        assert cur <= prev
        prev = cur


def test_the_floor_is_strictly_positive():
    """d'Hondt must still award a seat eventually (minWeight_pos)."""
    assert A_MIN > 0


def test_the_range_sits_inside_synergy():
    """Hierarchy: falloff 9:1 > synergy 3:1 > achievability 2:1."""
    from artifactsmmo_cli.ai.tiers.synergy_core import S_MIN
    assert Fraction(1) / A_MIN < Fraction(1) / S_MIN
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_achievability_core.py -q --no-cov`
Expected: FAIL — `ModuleNotFoundError: artifactsmmo_cli.ai.tiers.achievability_core`.

- [ ] **Step 3: Implement**

```python
"""PURE achievability core. No GameData/WorldState — plain scalars only,
mirrored by formal/Formal/Achievability.lean.

Achievability is the fourth modulating factor in the tree's selection weight:

    weight = gain * falloff(focus) * synergy * achievability
             │       │               │         │
        magnitude  staleness       purity   effort-to-reach

It answers "how much work is left before I can have this", so a large but
distant upgrade stops starving a smaller one I could build now. Live at L21,
lich_race_trophy (gain 25050, 1000 event_tickets away) outranked life_ring
(gain 21020, craftable from gatherable materials) on magnitude alone.

The impure assembly layer (progression_tree.py) computes the two integers —
`effort`, the candidate's UNMET demand, and `min_effort`, the cheapest
candidate's — and this module maps them to a bounded `Fraction`. Taking two
ints keeps the proven core scalar and its mutation group small, mirroring
`synergy_pure(shared, total)` and `falloff(focus_level)`.
"""

from fractions import Fraction

A_MIN = Fraction(1, 2)
"""Floor of the achievability multiplier (> 0): even an enormously distant
target keeps a strictly-positive weight, so d'Hondt still awards it a seat
eventually (`interleaveDue_reaches`, resting on `minWeight_pos`). The range
1/A_MIN = 2 is deliberately kept strictly inside `synergy`'s 3:1 (S_MIN = 1/3),
which is itself inside `falloff`'s 9:1 — so aging dominates alignment dominates
effort. A maximally distant candidate can therefore only lose to a maximally
close one when the gain gap is under 2x; a genuinely enormous upgrade still
wins. This is the ONLY tuning surface; the shape is an affine map into
[A_MIN, 1], pinned by the tests and Achievability.lean."""


def achievability_pure(effort: int, min_effort: int) -> Fraction:
    """Effort multiplier for a candidate needing `effort` unmet units, where the
    cheapest live candidate needs `min_effort`.

    Affine map of `(min_effort + 1) / (effort + 1)` into `[A_MIN, 1]` — same
    shape as `synergy_pure` and `falloff`. Exact `Fraction`, no float in the
    decision path.

    RELATIVE, not absolute: the factor is scored against the cheapest candidate
    in the same decision, so there is no tuned effort scale to drift — the same
    self-scaling argument the requirement multiset's token weights make.

    The `+1` on both sides is not cosmetic. It keeps a zero-effort candidate
    from dividing by zero, and keeps ONE fully-held candidate from slamming
    every other candidate to the floor: with raw ratios, min_effort = 0 sends
    every other ratio to 0 regardless of whether they need 2 units or 2000.

    `effort < min_effort` cannot happen by construction (min_effort is the
    minimum over a set containing effort); the core ASSERTS rather than clamps,
    so an assembly-layer bug fails loudly instead of being silently corrected."""
    assert effort >= min_effort >= 0, f"effort {effort} below min {min_effort}"
    return A_MIN + (Fraction(1) - A_MIN) * Fraction(min_effort + 1, effort + 1)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_ai/test_achievability_core.py -q --no-cov`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/achievability_core.py tests/test_ai/test_achievability_core.py
git commit -m "feat(gear): pure achievability core (effort-to-reach multiplier)

Fourth modulating factor after magnitude, staleness and purity. Affine map of
(min_effort+1)/(effort+1) into [A_MIN, 1], A_MIN = 1/2 — a 2:1 range, strictly
inside synergy's 3:1 and falloff's 9:1, so effort informs without dictating.
Relative to the cheapest live candidate, so there is no absolute effort scale
to drift."
```

---

### Task 3: Effort as unmet demand

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/progression_tree.py`
- Test: `tests/test_ai/test_progression_tree_core.py`

**Interfaces:**
- Consumes: `requirement_multiset_for` (Task 1, now transitive).
- Produces: `_effort_for(code, state, game_data) -> int`. Task 4 calls it.

- [ ] **Step 1: Write the failing test**

```python
def test_effort_ignores_what_is_already_held():
    """life_ring demands 2000 gold; a character holding 12382 has zero gold
    effort. Total demand ranks by price tag; UNMET demand ranks by difficulty."""
    gd, state = _bundle_and_state(gold=12382)
    effort = _effort_for("life_ring", state, gd)
    assert effort < 2000, "gold the character already holds must not count"


def test_skill_tokens_count_as_the_level_deficit():
    """A recipe needing jewelrycrafting 15 against skill 10 contributes 5 —
    this is what separates a skill-gapped item from a currency-gated one."""
    gd, state = _bundle_and_state(skills={"jewelrycrafting": 10})
    with_gap = _effort_for("life_ring", state, gd)
    gd2, state2 = _bundle_and_state(skills={"jewelrycrafting": 15})
    assert _effort_for("life_ring", state2, gd2) < with_gap


def test_char_xp_tokens_do_not_count_as_effort():
    """char_xp marks drop-routed work for SYNERGY alignment; it is not a unit
    of demand and must not inflate effort."""
    gd, state = _bundle_and_state()
    assert _effort_for("mushmush_jacket", state, gd) < 100
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_progression_tree_core.py -k effort -q --no-cov`
Expected: FAIL — `_effort_for` is not defined.

- [ ] **Step 3: Implement in `progression_tree.py`**

```python
def _effort_for(code: str, state: WorldState, game_data: GameData) -> int:
    """UNMET demand for one unit of `code`: how much work is actually LEFT.

    Total demand ranks by price tag, not difficulty — life_ring demands 2000
    gold, which is no work at all to a character holding 12382. Subtracting
    holdings is what makes this an effort measure rather than a cost sheet.

    Token handling:
      * `skill:<name>` — the recipe's craft LEVEL DEFICIT, not the token count.
        A 5-level gap is real work; being already at level is none. This is the
        distinction the whole factor turns on: a skill-gapped candidate must
        read cheaper than a currency-gated one, not equally blocked.
      * `char_xp` — SKIPPED. It marks drop-routed work for synergy alignment;
        it is not a unit of demand and would inflate every drop-routed
        candidate.
      * everything else — an item quantity, credited against inventory + bank.
    """
    stats = game_data.item_stats(code)
    held = dict(state.inventory or {})
    for item, qty in (state.bank_items or {}).items():
        held[item] = held.get(item, 0) + qty
    held["gold"] = state.gold + (state.bank_gold or 0)

    effort = 0
    for token, qty in game_data.requirement_graph.requirement_multiset_for(code).items():
        if token == CHAR_XP:
            continue
        if token.startswith(SKILL_PREFIX):
            skill = token[len(SKILL_PREFIX):]
            need = (stats.crafting_level or 0) if stats is not None else 0
            effort += max(0, need - state.skills.get(skill, 0))
            continue
        effort += max(0, qty - held.get(token, 0))
    return effort
```

Import `CHAR_XP` and `SKILL_PREFIX` from `artifactsmmo_cli.ai.requirement_graph_memo` at the top of the file.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_ai/test_progression_tree_core.py -k effort -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/progression_tree.py tests/test_ai/test_progression_tree_core.py
git commit -m "feat(gear): effort as UNMET demand over the enriched multiset

Holdings-aware: gold the character already has is not work. Skill tokens count
as the craft-level deficit, which is what makes a skill-gapped candidate read
cheaper than a currency-gated one. char_xp is skipped — it marks drop-routed
work for synergy alignment and is not a unit of demand."
```

---

### Task 4: Wire the factor into the weight (and the flat-window clause)

`focus_aging_pick` short-circuits to the plain argmax while every candidate is fresh AND every synergy factor is 1. Its docstring records that omitting the synergy half of that condition made synergy "silently inert for the first FOCUS_FLAT cycles of every root — exactly the window where it matters most". Achievability inherits that bug unless the clause is extended.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/progression_tree_core.py` (`_scaled_weights`, `focus_aging_pick`, `focus_aging_order`)
- Modify: `src/artifactsmmo_cli/ai/tiers/progression_tree.py` (`_achievability_map`, `decide_tree`)
- Test: `tests/test_ai/test_progression_tree_core.py`

**Interfaces:**
- Consumes: `achievability_pure`, `A_MIN` (Task 2); `_effort_for` (Task 3).
- Produces: `_achievability_map(candidates, state, game_data) -> Mapping[tuple[str, str], Fraction]`; `_scaled_weights(candidates, focus, synergy, achievability)`.

- [ ] **Step 1: Write the failing test**

```python
_NO_ACHIEVABILITY: Mapping[tuple[str, str], Fraction] = {}


def test_achievability_scales_the_weight():
    """A distant candidate with the bigger gain loses to a close smaller one."""
    far = GearCandidate(slot="artifact3_slot", code="trophy", gain=Fraction(25050), level=20)
    near = GearCandidate(slot="ring1_slot", code="life_ring", gain=Fraction(21020), level=15)
    ach = {("artifact3_slot", "trophy"): Fraction(509, 1000),
           ("ring1_slot", "life_ring"): Fraction(788, 1000)}
    weights = dict(_scaled_weights([far, near], {}, _NO_SYNERGY, ach))
    assert weights["ring1_slot"] > weights["artifact3_slot"]


def test_empty_achievability_reproduces_the_old_weights():
    """The inert default must be bit-identical to pre-achievability behaviour."""
    c = GearCandidate(slot="ring1_slot", code="life_ring", gain=Fraction(21020), level=15)
    assert (_scaled_weights([c], {}, _NO_SYNERGY, _NO_ACHIEVABILITY)
            == _scaled_weights([c], {}, _NO_SYNERGY))


def test_achievability_breaks_the_flat_window_short_circuit():
    """THE TRAP: while every root is fresh, focus_aging_pick returns the plain
    argmax. Without extending that condition, achievability is inert for the
    first FOCUS_FLAT cycles — exactly the window a fresh gear decision lives in.
    Same bug synergy's docstring records."""
    far = GearCandidate(slot="artifact3_slot", code="trophy", gain=Fraction(25050), level=20)
    near = GearCandidate(slot="ring1_slot", code="life_ring", gain=Fraction(21020), level=15)
    ach = {("artifact3_slot", "trophy"): Fraction(1, 2)}
    pick = focus_aging_pick([far, near], {}, {}, _NO_SYNERGY, ach)
    assert pick.code == "life_ring", "flat-window fast path ignored achievability"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_progression_tree_core.py -k achievability -q --no-cov`
Expected: FAIL — `_scaled_weights()` takes 3 positional arguments.

- [ ] **Step 3: Implement**

In `progression_tree_core.py`, add the parameter to all three functions, defaulting to an empty map so every existing caller stays byte-identical:

```python
_NO_ACHIEVABILITY: Mapping[tuple[str, str], Fraction] = {}
```

`_scaled_weights` gains a fourth factor:

```python
    return [(c.slot, c.gain * falloff(focus.get((c.slot, c.code), 0))
             * synergy.get((c.slot, c.code), Fraction(1))
             * achievability.get((c.slot, c.code), Fraction(1)))
            for c in candidates]
```

`focus_aging_pick`'s short-circuit gains the third clause:

```python
    if (all(focus.get((c.slot, c.code), 0) <= FOCUS_FLAT for c in candidates)
            and all(synergy.get((c.slot, c.code), Fraction(1)) == Fraction(1)
                    for c in candidates)
            and all(achievability.get((c.slot, c.code), Fraction(1)) == Fraction(1)
                    for c in candidates)):
        return gear_target_pick(candidates)
```

`focus_aging_order` forwards the new argument to `focus_aging_pick`.

In `progression_tree.py`, add the assembly map and wire it:

```python
def _achievability_map(candidates: list[GearCandidate], state: WorldState,
                       game_data: GameData) -> Mapping[tuple[str, str], Fraction]:
    """Per-candidate effort multiplier, keyed `(slot, code)` like `focus` and
    `synergy`. Scored RELATIVE to the cheapest candidate in this decision, so
    the factor has no absolute effort scale."""
    if not candidates:
        return {}
    efforts = {(c.slot, c.code): _effort_for(c.code, state, game_data) for c in candidates}
    floor = min(efforts.values())
    return {key: achievability_pure(effort, floor) for key, effort in efforts.items()}
```

and in `decide_tree`, alongside the synergy line:

```python
    achievability = _achievability_map(candidates, state, game_data)
    ordered = focus_aging_order(candidates, focus, seats, synergy, achievability)
    pick = focus_aging_pick(candidates, focus, seats, synergy, achievability) if candidates else None
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_ai/test_progression_tree_core.py tests/test_ai/test_progression_tree.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Run the whole suite — this changes a live decision path**

Run: `unset FORCE_COLOR NO_COLOR && uv run pytest tests/ -q --no-cov -n auto --ignore=tests/test_audit/test_inventory_census.py`
Expected: all pass. Scenario pins asserting a gear `chosen_root` may legitimately move — for each one, judge whether the new order is CORRECT before editing the pin, and record the reasoning in its docstring. Do not edit a pin merely to make it agree.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/progression_tree_core.py src/artifactsmmo_cli/ai/tiers/progression_tree.py tests/test_ai/
git commit -m "feat(gear): weight candidates by achievability

weight = gain * falloff * synergy * achievability. The empty default is
bit-identical to the previous weights, so every unit caller is unaffected.

The flat-window short-circuit gains a third clause: without it achievability
would be inert while every root is fresh — exactly the window a gear decision
lives in, and the same bug synergy's docstring records."
```

---

### Task 5: Lean mirror and proofs

**Files:**
- Create: `formal/Formal/Achievability.lean`
- Modify: `formal/Formal.lean` (import), `formal/Formal/Manifest.lean` (traceability rows)

**Interfaces:**
- Consumes: `achievability_pure`'s shape (Task 2).
- Produces: `Formal.Achievability.achievabilityPure` and its bound proofs.

- [ ] **Step 1: Write the Lean module**

Mirror `Formal/Synergy.lean` exactly — same structure, same theorem set:

```lean
-- formal/Formal/Achievability.lean
-- @concept: gear, planner @property: boundedness, monotonicity
/-
Mirrors `achievability_pure` in `src/artifactsmmo_cli/ai/tiers/achievability_core.py`.

The fourth modulating factor in the tree's selection weight. `aMin` is 1/2 — a
2:1 range, strictly inside `Synergy.sMin`'s 3:1, which is inside `falloff`'s
9:1, so aging dominates alignment dominates effort.
-/
namespace Formal.Achievability

def aMin : Rat := mkRat 1 2

/-- Relative-effort ratio `(minEffort+1)/(effort+1)` as an exact `Rat`. The `+1`
on both sides keeps a zero-effort candidate from dividing by zero and keeps one
fully-held candidate from slamming every other to the floor. -/
def achievabilityRatio (effort minEffort : Nat) : Rat :=
  ((minEffort : Rat) + 1) / ((effort : Rat) + 1)

/-- Effort multiplier: the affine map `aMin + (1 - aMin) * ratio`. Mirrors
Python `achievability_pure` (whose `effort >= minEffort` assert is a
precondition, not a branch). -/
def achievabilityPure (effort minEffort : Nat) : Rat :=
  aMin + (1 - aMin) * achievabilityRatio effort minEffort

theorem denom_pos (effort : Nat) : (0 : Rat) < (effort : Rat) + 1 := by
  have : (0 : Rat) ≤ (effort : Rat) := by positivity
  linarith

theorem ratio_nonneg (effort minEffort : Nat) :
    0 ≤ achievabilityRatio effort minEffort := by
  unfold achievabilityRatio
  have h := denom_pos effort
  have : (0 : Rat) ≤ (minEffort : Rat) + 1 := by positivity
  exact div_nonneg this (le_of_lt h)

theorem ratio_le_one {effort minEffort : Nat} (h : minEffort ≤ effort) :
    achievabilityRatio effort minEffort ≤ 1 := by
  unfold achievabilityRatio
  have hd := denom_pos effort
  have hn : (minEffort : Rat) + 1 ≤ (effort : Rat) + 1 := by
    have : (minEffort : Rat) ≤ (effort : Rat) := by exact_mod_cast h
    linarith
  exact (div_le_one hd).mpr hn

theorem achievability_ge_floor (effort minEffort : Nat) :
    aMin ≤ achievabilityPure effort minEffort := by
  unfold achievabilityPure
  have h := ratio_nonneg effort minEffort
  have : (0 : Rat) ≤ 1 - aMin := by unfold aMin; norm_num
  nlinarith

theorem achievability_le_one {effort minEffort : Nat} (h : minEffort ≤ effort) :
    achievabilityPure effort minEffort ≤ 1 := by
  unfold achievabilityPure
  have h1 := ratio_le_one h
  have : (0 : Rat) ≤ 1 - aMin := by unfold aMin; norm_num
  nlinarith

theorem achievability_floor_pos : (0 : Rat) < aMin := by
  unfold aMin; norm_num

/-- ANTITONE: more effort scores no higher — the defining property. -/
theorem achievability_antitone {e1 e2 minEffort : Nat} (h : e1 ≤ e2) :
    achievabilityPure e2 minEffort ≤ achievabilityPure e1 minEffort := by
  unfold achievabilityPure achievabilityRatio
  have hd1 := denom_pos e1
  have hd2 := denom_pos e2
  have hmono : ((minEffort : Rat) + 1) / ((e2 : Rat) + 1)
             ≤ ((minEffort : Rat) + 1) / ((e1 : Rat) + 1) := by
    apply div_le_div_of_nonneg_left (by positivity) hd1
    have : (e1 : Rat) ≤ (e2 : Rat) := by exact_mod_cast h
    linarith
  have : (0 : Rat) ≤ 1 - aMin := by unfold aMin; norm_num
  nlinarith

end Formal.Achievability
```

- [ ] **Step 2: Add the import**

In `formal/Formal.lean`, add `import Formal.Achievability` in alphabetical position.

- [ ] **Step 3: Build**

Run: `cd formal && lake build`
Expected: `Build completed successfully`, no `sorry`, no errors. If a proof does not close, repair it — do NOT add an axiom and do NOT weaken a statement.

- [ ] **Step 4: Add the Manifest rows**

In `formal/Formal/Manifest.lean`, after the `-- Synergy (...)` block, add:

```
-- Achievability (the effort-to-reach multiplier pinned into [aMin, 1]):
#check @Formal.Achievability.ratio_nonneg                    -- the effort ratio is nonneg
#check @Formal.Achievability.ratio_le_one                    -- with minEffort ≤ effort the ratio is ≤ 1
#check @Formal.Achievability.achievability_ge_floor          -- never below aMin (the anti-starvation floor)
#check @Formal.Achievability.achievability_le_one            -- never above 1
#check @Formal.Achievability.achievability_floor_pos         -- the floor is strictly positive (feeds interleaveDue_reaches)
#check @Formal.Achievability.achievability_antitone          -- ANTITONE: more effort scores no higher
```

- [ ] **Step 5: Regenerate the audit list and verify the formal gates**

`Formal/Audit.lean` is GENERATED from `Manifest.lean` — do not hand-edit it.

Run:
```bash
uv run python scripts/gen_audit.py
bash formal/gate/check_audit_generated.sh
bash formal/gate/check_proof_concept_index.sh || uv run python scripts/gen_proof_concept_index.py
bash formal/gate/check_axioms.sh
bash formal/gate/check_no_sorry.sh
bash formal/gate/check_no_orphan_modules.sh
```
Expected: all report OK. The axiom gate must show the new theorems within `{propext, Classical.choice, Quot.sound}`.

- [ ] **Step 6: Commit**

```bash
git add formal/Formal/Achievability.lean formal/Formal.lean formal/Formal/Manifest.lean formal/Formal/Audit.lean docs/behavioral_completeness/PROOF_CONCEPT_INDEX.md
git commit -m "feat(formal): prove the achievability multiplier's bounds

Mirrors achievability_core.py. Pinned into [aMin, 1] with aMin = 1/2 — a 2:1
range strictly inside Synergy's 3:1. The floor is strictly positive, so d'Hondt
still awards a distant candidate a seat eventually (minWeight_pos), and the
multiplier is ANTITONE in effort, which is the property the factor exists for."
```

---

### Task 6: Mutation anchors and the live falsifiability witness

**Files:**
- Modify: `formal/diff/mutate.py`
- Test: `tests/test_ai/test_progression_tree.py`

**Interfaces:**
- Consumes: everything above.
- Produces: no new symbols.

- [ ] **Step 1: Write the falsifiability witness**

The factor must be switchable by holdings. A down-weight that cannot be turned off is not measuring effort:

```python
def test_achievability_reorders_the_live_bundle_and_is_reversible():
    """THE acceptance test. With ordinary holdings the craftable ring outranks
    the currency-gated trophy; give the character the 1000 event_tickets and the
    trophy returns to the top. If the second half fails, the factor is a blanket
    penalty on long chains rather than an effort measure."""
    gd = _bundle()
    poor = _state_with(gd, inventory={})
    rich = _state_with(gd, inventory={"event_ticket": 1000})

    poor_order = [c.code for c in _ordered_candidates(poor, gd)]
    rich_order = [c.code for c in _ordered_candidates(rich, gd)]

    assert poor_order.index("life_ring") < poor_order.index("lich_race_trophy")
    assert rich_order.index("lich_race_trophy") < rich_order.index("life_ring")
```

`_ordered_candidates` must read the ACHIEVABILITY-WEIGHTED order (`focus_aging_order(...)`), NOT `decision.ranking` — `progression_tree.py:152` records that those rows are display-only, so a test reading them would pass while the real order was unchanged.

- [ ] **Step 2: Run to verify it fails without the factor**

Run: `git stash && uv run pytest tests/test_ai/test_progression_tree.py -k reorders -q --no-cov; git stash pop`
Expected: FAIL on the stashed (pre-factor) tree — proving the test detects the change rather than passing regardless.

- [ ] **Step 3: Run it against the implementation**

Run: `uv run pytest tests/test_ai/test_progression_tree.py -k reorders -q --no-cov`
Expected: PASS both halves.

- [ ] **Step 4: Add the mutation anchors**

In `formal/diff/mutate.py`, add a new group near `PASSIVE_CURRENCY_HELPER_MUTATIONS`:

```python
# achievability_core.py — the effort-to-reach multiplier. A_MIN is a live
# decision knob (cf. POTION_LEAD_FIGHTS), so it is anchored, not just tested.
# Unit-killed by tests/test_ai/test_achievability_core.py.
ACHIEVABILITY_CORE_MUTATIONS = [
    # Floor removed: a distant candidate decays to zero weight and d'Hondt never
    # awards it a seat — the anti-starvation property minWeight_pos rests on.
    ("achievability: floor removed",
     "A_MIN = Fraction(1, 2)",
     "A_MIN = Fraction(0, 1)"),
    # Floor raised to 1: the factor becomes constant and cannot reorder anything.
    ("achievability: factor flattened to a no-op",
     "A_MIN = Fraction(1, 2)",
     "A_MIN = Fraction(1, 1)"),
    # Ratio inverted: MORE effort would score HIGHER, inverting the whole point.
    ("achievability: effort ratio inverted",
     "Fraction(min_effort + 1, effort + 1)",
     "Fraction(effort + 1, min_effort + 1)"),
]
```

and register it beside the other groups:

```python
    run_group(ACHIEVABILITY_CORE_SRC, ACHIEVABILITY_CORE_MUTATIONS,
              "tests/test_ai/test_achievability_core.py", survivors)
```

with `ACHIEVABILITY_CORE_SRC = ROOT / "src/artifactsmmo_cli/ai/tiers/achievability_core.py"` beside the other `*_SRC` constants.

Note the first two anchors share the same anchor text; if `--check-anchors` reports AMBIGUOUS, widen each to include a distinguishing neighbouring line rather than deleting one — both mutants are worth killing.

- [ ] **Step 5: Verify the anchors resolve and the mutants die**

Run: `uv run python formal/diff/mutate.py --check-anchors`
Expected: `anchor check OK`, count increased by 3.

Run: `uv run python formal/diff/mutate.py --only achievability`
Expected: every mutant `killed`, `mutation gate OK`. A SURVIVOR means the tests do not actually constrain the knob — strengthen the test, do not delete the mutant.

- [ ] **Step 6: Commit**

```bash
git add formal/diff/mutate.py tests/test_ai/test_progression_tree.py
git commit -m "test(gear): anchor A_MIN and pin the reordering as reversible

The acceptance witness runs both directions: with ordinary holdings the
craftable ring outranks the currency-gated trophy, and with 1000 event_tickets
in inventory the trophy returns to the top. A down-weight that cannot be
switched off by holdings is a blanket penalty on long chains, not an effort
measure. Asserted on the weighted order, never on decision.ranking — those rows
are display-only."
```

---

### Task 7: Full gate

**Files:** none (verification only).

- [ ] **Step 1: Check the bot is not running**

Run: `pgrep -af "artifactsmmo play" || echo "clear"`
If the bot IS running, do not run the gate — report that instead. Gate results measured against a live bot are contended and the project rule forbids it.

- [ ] **Step 2: Run the gate**

Run: `bash formal/gate.sh`
Expected: `ALL GATE PARTS PASSED`, 100.00% coverage, tree clean afterwards.

- [ ] **Step 3: Report**

Report the wall-clock, the differential and suite counts, and the coverage line. If any scenario pin was edited in Task 4, list it with the reasoning for why the new ordering is correct.

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| Where it plugs in (`_scaled_weights`) | Task 4 |
| Factor hierarchy, `A_MIN = 1/2` | Task 2 |
| Effort = unmet demand | Task 3 |
| Skill tokens as level deficit | Task 3 |
| Self-scaling weight function | Task 2 |
| Prerequisite 1 — transitive currency expansion | Task 1 |
| Prerequisite 2 — holdings-aware reduction | Task 3 |
| Flat-window trap | Task 4 |
| Testing 1/1b — reorder, on the weighted order | Task 6 |
| Testing 2 — reversible with holdings | Task 6 |
| Testing 3 — `A_MIN` test + mutation anchor | Tasks 2, 6 |
| Testing 4 — transitive expansion asserted | Task 1 |
| Testing 5 — cycle protection | Task 1 |
| Risk — Lean obligation | Task 5 |

**Placeholder scan:** none — every step names an exact file, command, and expected output.

**Type consistency:** `achievability_pure(effort: int, min_effort: int) -> Fraction` is defined in Task 2 and called with that signature in Tasks 4 and 6. `_effort_for(code, state, game_data) -> int` is defined in Task 3 and called in Task 4. `_achievability_map` returns `Mapping[tuple[str, str], Fraction]`, matching `_scaled_weights`' lookup key. Lean `achievabilityPure (effort minEffort : Nat)` matches the Python argument ORDER.

**Ordering dependency:** Task 1 is a hard prerequisite — measured, the factor makes ordering worse without it. Run the tasks in order.
