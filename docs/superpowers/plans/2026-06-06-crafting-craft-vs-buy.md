# Crafting — Craft-vs-Buy Decision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For a needed item an NPC sells, buy it instead of crafting when buying is strictly fewer cooldowns AND affordable above a gold reserve — proven non-dominated/monotone/total/reserve-safe, differentially cross-checked, with the proven least-cost planner doing the per-item pick.

**Architecture:** Pure `craft_vs_buy.cheaper_acquisition` core (the differential target); mirrored `CraftVsBuy.lean` over Int/Nat; oracle + differential + mutation; an impure `acquisition_method` adapter; wiring injects the EXISTING `NpcBuyAction` into `GatherMaterials.relevant_actions` for BUY items; close the crafting matrix row. No data plumbing — `GameData` already has `_npc_locations`/`npc_location`/`npc_sells_item`/`npcs_selling_item` and `NpcBuyAction` already exists.

**Tech Stack:** Python 3.13 (`uv`, pytest 100% cov, mypy strict, ruff), Lean 4 (`formal/`, core Int/Nat), Hypothesis (differential).

**Spec:** `docs/superpowers/specs/2026-06-06-crafting-craft-vs-buy-design.md`

---

## File structure

| File | Responsibility | New? |
|---|---|---|
| `src/artifactsmmo_cli/ai/craft_vs_buy.py` | pure `Method` + `cheaper_acquisition`; impure `acquisition_method` adapter | create |
| `src/artifactsmmo_cli/ai/goals/gathering.py` | inject `NpcBuyAction` for BUY items in `relevant_actions` | modify |
| `formal/Formal/CraftVsBuy.lean` | model + theorems | create |
| `formal/Formal/{Manifest,Contracts,Audit}.lean` | register + tag | modify |
| `formal/Oracle.lean` | `"craft_vs_buy"` dispatch | modify |
| `formal/diff/test_craft_vs_buy_diff.py` | differential | create |
| `formal/gate.sh`, `formal/diff/mutate.py` | add diff + mutation target | modify |
| `docs/behavioral_completeness/{MATRIX,PROOF_CONCEPT_INDEX,BACKLOG}.md` | close crafting row | modify |
| tests under `tests/test_ai/` | unit tests | create |

---

## Task 1: pure decision core

**Files:** Create `src/artifactsmmo_cli/ai/craft_vs_buy.py`; Test `tests/test_ai/test_craft_vs_buy.py`

- [ ] **Step 1: failing test**

```python
# tests/test_ai/test_craft_vs_buy.py
"""cheaper_acquisition: BUY iff affordable (gold - price >= reserve) AND buy < craft."""
from artifactsmmo_cli.ai.craft_vs_buy import Method, cheaper_acquisition


def test_buys_when_affordable_and_strictly_cheaper():
    # craft 80 cd, buy 5 cd, price 100, gold 1000, reserve 200 -> affordable, cheaper -> BUY
    assert cheaper_acquisition(80, 5, 100, 1000, 200) == Method.BUY


def test_crafts_when_unaffordable_even_if_cheaper():
    # gold 250, price 100, reserve 200 -> gold-price=150 < 200 -> not affordable -> CRAFT
    assert cheaper_acquisition(80, 5, 100, 250, 200) == Method.CRAFT


def test_crafts_when_not_strictly_cheaper():
    # buy 80 == craft 80 -> not strictly cheaper -> CRAFT
    assert cheaper_acquisition(80, 80, 100, 1000, 200) == Method.CRAFT


def test_affordability_boundary_equal_is_affordable():
    # gold-price == reserve (800-600=200) -> affordable (>=) -> BUY when cheaper
    assert cheaper_acquisition(80, 5, 600, 800, 200) == Method.BUY


def test_affordability_boundary_one_short_is_not():
    assert cheaper_acquisition(80, 5, 601, 800, 200) == Method.CRAFT
```

- [ ] **Step 2: run, confirm fail** — `uv run pytest tests/test_ai/test_craft_vs_buy.py -v --no-cov`.

- [ ] **Step 3: implement** (`src/artifactsmmo_cli/ai/craft_vs_buy.py`)

```python
"""Craft-vs-buy acquisition decision. For a needed item an NPC sells, choose BUY
over CRAFT only when buying is strictly fewer cooldowns AND affordable above a gold
reserve. Cooldowns is the optimization metric; gold is a HARD constraint (the
reserve), never converted. The pure `cheaper_acquisition` is the differential
target proved in formal/Formal/CraftVsBuy.lean; `acquisition_method` is the impure
adapter that assembles inputs from GameData and delegates.
"""

from dataclasses import dataclass
from enum import Enum

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.min_gathers import min_gathers
from artifactsmmo_cli.ai.world_state import WorldState

GOLD_RESERVE = 500
"""Gold kept in reserve for essentials (e.g. bank expansion); buying a needed item
may not drop gold below this. Tunable; the proof is parametric in `reserve`."""


class Method(Enum):
    CRAFT = "craft"
    BUY = "buy"


def cheaper_acquisition(
    craft_cooldowns: int, buy_cooldowns: int, total_price: int, gold: int, reserve: int
) -> Method:
    """BUY iff affordable above the reserve AND strictly fewer cooldowns; else CRAFT."""
    affordable = gold - total_price >= reserve
    return Method.BUY if (affordable and buy_cooldowns < craft_cooldowns) else Method.CRAFT
```

- [ ] **Step 4: run, confirm pass** (5 tests).

- [ ] **Step 5: commit**

```bash
git add src/artifactsmmo_cli/ai/craft_vs_buy.py tests/test_ai/test_craft_vs_buy.py
git commit -m "feat(ai): pure craft-vs-buy decision core (cooldown-min + gold reserve)"
```

---

## Task 2: Lean model + proofs

**Files:** Create `formal/Formal/CraftVsBuy.lean`; Modify `formal/Formal/{Manifest,Contracts,Audit}.lean`, `formal/Formal.lean`

Use the `lean4:*` skills. Core-only (no Mathlib — `Int`/`Nat` arithmetic is core; `omega` closes most goals).

- [ ] **Step 1:** model (first line is the tag):

```lean
-- @concept: crafting, npcs @property: dominance, monotonicity, totality, safety
namespace Formal.CraftVsBuy

inductive Method where | craft | buy deriving Repr, DecidableEq

/-- BUY iff affordable (gold - price ≥ reserve, over ℤ) AND buy < craft. Mirrors
the Python `cheaper_acquisition`. -/
def cheaperAcquisition (craftCd buyCd totalPrice gold reserve : Int) : Method :=
  if (gold - totalPrice ≥ reserve) ∧ (buyCd < craftCd) then Method.buy else Method.craft
```

(Inputs `Int` to match the Python `gold - total_price` which can go negative; cooldowns are non-negative but `Int` is fine. Use `decide`/`split`/`omega`.)

- [ ] **Step 2:** prove (register these names):
  - `acquisition_total : ∀ a b p g r, cheaperAcquisition a b p g r = Method.craft ∨ cheaperAcquisition a b p g r = Method.buy` (TOTALITY).
  - `buy_iff_affordable_and_cheaper : cheaperAcquisition a b p g r = Method.buy ↔ (g - p ≥ r ∧ b < a)` (DOMINANCE — the exact firing condition).
  - `craft_when_not_cheaper : ¬ (b < a) → cheaperAcquisition a b p g r = Method.craft` and `craft_when_unaffordable : ¬ (g - p ≥ r) → cheaperAcquisition a b p g r = Method.craft` (dominance corollaries — never buy a dominated/unaffordable method).
  - `buy_stable_under_more_gold : cheaperAcquisition a b p g r = Method.buy → g ≤ g' → cheaperAcquisition a b p g' r = Method.buy` (MONOTONICITY in gold).
  - `buy_stable_under_lower_buy : cheaperAcquisition a b p g r = Method.buy → b' ≤ b → cheaperAcquisition a b' p g r = Method.buy` (MONOTONICITY in buy cost).
  - `buy_preserves_reserve : cheaperAcquisition a b p g r = Method.buy → g - p ≥ r` (SAFETY — post-buy gold ≥ reserve).

- [ ] **Step 3:** `lake build Formal.CraftVsBuy`; axiom-check each (`#print axioms`, only `{propext, Classical.choice, Quot.sound}`, no `sorry`/`native_decide`).

- [ ] **Step 4:** register: `import Formal.CraftVsBuy` in `Formal.lean`; `#check @Formal.CraftVsBuy.<thm>` lines in `Manifest.lean`; exact-statement `example : <stmt> := @<thm>` pins in `Contracts.lean` (+ import); `#print axioms` lines in `Audit.lean`. Regenerate index: `uv run python scripts/gen_proof_concept_index.py && uv run python scripts/gen_proof_concept_index.py --check` → OK. Confirm `cd formal && lake build Formal.CraftVsBuy Formal.Contracts 2>&1 | tail -3`.

- [ ] **Step 5: commit**

```bash
git add formal/Formal/CraftVsBuy.lean formal/Formal.lean formal/Formal/Manifest.lean formal/Formal/Contracts.lean formal/Formal/Audit.lean docs/behavioral_completeness/PROOF_CONCEPT_INDEX.md
git commit -m "formal: CraftVsBuy — dominance/monotone/total/reserve-safe decision over Int"
```

---

## Task 3: oracle + differential + mutation

**Files:** Modify `formal/Oracle.lean`, `formal/gate.sh`, `formal/diff/mutate.py`; Create `formal/diff/test_craft_vs_buy_diff.py`

- [ ] **Step 1:** add a `"craft_vs_buy"` branch to `Oracle.lean`'s `main` (study the existing simple-arithmetic branches): read `[craftCd, buyCd, totalPrice, gold, reserve]` ints, run `cheaperAcquisition`, emit `{"method": 1}` for buy / `{"method": 0}` for craft. `lake build oracle`.

- [ ] **Step 2:** differential test:

```python
# formal/diff/test_craft_vs_buy_diff.py
"""cheaper_acquisition (Python) must agree with Formal.CraftVsBuy.cheaperAcquisition."""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.craft_vs_buy import Method, cheaper_acquisition
from formal.diff.oracle_client import run_oracle

_i = st.integers(min_value=-5, max_value=200)


@settings(max_examples=400)
@given(craft=st.integers(0, 200), buy=st.integers(0, 200), price=st.integers(0, 500),
       gold=st.integers(0, 2000), reserve=st.integers(0, 1000))
def test_decision_matches_lean(craft, buy, price, gold, reserve):
    py = cheaper_acquisition(craft, buy, price, gold, reserve)
    lean = run_oracle("craft_vs_buy", [[craft, buy, price, gold, reserve]])[0]
    assert lean["method"] == (1 if py is Method.BUY else 0)
```

- [ ] **Step 3:** append the diff test to `formal/gate.sh` part (d); add `src/artifactsmmo_cli/ai/craft_vs_buy.py` to `formal/diff/mutate.py`'s target list (follow how `gather_selection` was added in the prior gap; mutate the `>=`, `<`, `and`, the `-`).

- [ ] **Step 4:** `cd formal && lake build oracle && cd .. && uv run pytest formal/diff/test_craft_vs_buy_diff.py -q --no-cov` → PASS (Lean ≡ Python — if they disagree, a real bug; report it). Run mutation on craft_vs_buy → mutants killed.

- [ ] **Step 5: commit**

```bash
git add formal/Oracle.lean formal/gate.sh formal/diff/test_craft_vs_buy_diff.py formal/diff/mutate.py
git commit -m "formal(diff): craft-vs-buy oracle + differential + mutation coverage"
```

---

## Task 4: adapter + wiring into relevant_actions

**Files:** Modify `src/artifactsmmo_cli/ai/craft_vs_buy.py` (add `acquisition_method`), `src/artifactsmmo_cli/ai/goals/gathering.py`; Test `tests/test_ai/test_craft_vs_buy_wiring.py`

`GameData` ALREADY has: `npcs_selling_item(item) -> [(npc, price)]` (cheapest = min price), `npc_location(npc) -> (x,y)|None`, `npc_sells_item(npc, item) -> price|None`. `NpcBuyAction(npc_code, item_code, npc_location, quantity=...)` already exists (`actions/npc.py`) with `is_applicable`/`cost`/`apply`. Verify its constructor field names before use.

- [ ] **Step 1: failing test**

```python
# tests/test_ai/test_craft_vs_buy_wiring.py
"""GatherMaterials.relevant_actions injects NpcBuyAction for a needed item that is
NPC-sold, affordable above the reserve, and cheaper to buy than craft; leaves
craft-only / unaffordable / pricier items alone."""
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.craft_vs_buy import GOLD_RESERVE, Method, acquisition_method
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from tests.test_ai.fixtures import make_state


def _gd_buyable():
    gd = GameData()
    # copper_bar: craftable (copper_ore x10) OR bought from shop_npc at 5g, near.
    gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
    gd._npc_sell_prices = {"shop": {"copper_bar": 5}}
    gd._npc_locations = {"shop": (1, 0)}
    return gd


def test_acquisition_method_buys_cheap_affordable():
    gd = _gd_buyable()
    state = make_state(gold=GOLD_RESERVE + 1000, inventory={}, x=0, y=0)
    # 1 copper_bar: craft ~10 ore gathers; buy ~2 cooldowns at 5g, affordable -> BUY
    assert acquisition_method("copper_bar", 1, state, gd, GOLD_RESERVE) == Method.BUY


def test_acquisition_method_crafts_when_unaffordable():
    gd = _gd_buyable()
    state = make_state(gold=GOLD_RESERVE - 1, inventory={}, x=0, y=0)
    assert acquisition_method("copper_bar", 1, state, gd, GOLD_RESERVE) == Method.CRAFT


def test_relevant_actions_injects_npcbuy_for_buy_item():
    gd = _gd_buyable()
    state = make_state(gold=GOLD_RESERVE + 1000, inventory={}, x=0, y=0,
                       skills={"mining": 5})
    goal = GatherMaterialsGoal(target_item="copper_bar", needed={"copper_bar": 1})
    relevant = goal.relevant_actions([], state, gd)
    assert any(isinstance(a, NpcBuyAction) and a.item_code == "copper_bar" for a in relevant)
```

(Adapt to the real `NpcBuyAction` field names + `GatherMaterialsGoal` constructor if they differ — read both first.)

- [ ] **Step 2: run, confirm fail.**

- [ ] **Step 3: implement** — add `acquisition_method` to `craft_vs_buy.py`:

```python
def _craft_cooldowns(item: str, needed: int, state: WorldState, game_data: GameData) -> int:
    owned = dict(state.inventory)
    for code, qty in (state.bank_items or {}).items():
        owned[code] = owned.get(code, 0) + qty
    gathers = min_gathers(item, needed, game_data._crafting_recipes, owned)
    # one craft action per distinct craftable node in the recipe tree (>=1 if craftable)
    crafts = 1 if (game_data._crafting_recipes.get(item)) else 0
    return gathers + crafts


def _buy_cooldowns(npc_location: tuple[int, int] | None, state: WorldState, needed: int) -> int:
    if npc_location is None:
        return needed  # unknown location: degrade to a constant-ish term (documented)
    travel = abs(npc_location[0] - state.x) + abs(npc_location[1] - state.y)
    return travel + needed  # one buy action per unit (no per-buy cap modeled)


def acquisition_method(item: str, needed: int, state: WorldState, game_data: GameData,
                       reserve: int) -> Method:
    """Assemble inputs from GameData and delegate to the proved `cheaper_acquisition`.
    Returns CRAFT when no NPC sells the item (fail-open)."""
    sellers = game_data.npcs_selling_item(item)
    if not sellers:
        return Method.CRAFT
    npc_code, unit_price = min(sellers, key=lambda np: np[1])
    total_price = unit_price * needed
    buy_cd = _buy_cooldowns(game_data.npc_location(npc_code), state, needed)
    craft_cd = _craft_cooldowns(item, needed, state, game_data)
    return cheaper_acquisition(craft_cd, buy_cd, total_price, state.gold, reserve)
```

In `GatherMaterialsGoal.relevant_actions` (`gathering.py`), after the existing
narrowing, inject buy alternatives. Add imports at top
(`from artifactsmmo_cli.ai.actions.npc import NpcBuyAction`,
`from artifactsmmo_cli.ai.craft_vs_buy import GOLD_RESERVE, Method, acquisition_method`).
Then, for each recipe-closure item the goal needs (its `_needed` keys + closure
intermediates already used by the existing filter), if `acquisition_method(...) ==
Method.BUY`, append `NpcBuyAction(npc_code=<cheapest seller>, item_code=item,
npc_location=<that npc loc>, quantity=needed)`:

```python
        # Craft-vs-buy: offer an NpcBuy alternative for a needed item that is
        # NPC-sold, affordable above GOLD_RESERVE, and strictly cheaper to buy than
        # craft (proved in formal/Formal/CraftVsBuy.lean). The least-cost planner
        # then picks buy-vs-make. Items with no seller / unaffordable / pricier are
        # left craft-only.
        for item, qty in self._needed.items():
            sellers = game_data.npcs_selling_item(item)
            if not sellers:
                continue
            if acquisition_method(item, qty, state, game_data, GOLD_RESERVE) is not Method.BUY:
                continue
            npc_code, _price = min(sellers, key=lambda np: np[1])
            result.append(NpcBuyAction(npc_code=npc_code, item_code=item,
                                       npc_location=game_data.npc_location(npc_code),
                                       quantity=qty))
```

(Use the goal's actual needed-items attribute name — verify it is `self._needed`. If
`NpcBuyAction`'s `quantity` field/defaults differ, adapt.)

- [ ] **Step 4: run, confirm pass**, then regression: `uv run pytest tests/test_ai/ -k "gather or Gather or relevant or craft or npc" -q --no-cov` → all pass. Confirm 100% coverage of the new branches (fail-open `not sellers`, non-BUY skip) — add unit tests if any branch is uncovered.

- [ ] **Step 5: commit**

```bash
git add src/artifactsmmo_cli/ai/craft_vs_buy.py src/artifactsmmo_cli/ai/goals/gathering.py tests/test_ai/test_craft_vs_buy_wiring.py
git commit -m "feat(arbiter): inject NpcBuy alternative when buying a needed item is cheaper"
```

---

## Task 5: close the matrix row + full gate

**Files:** Modify `docs/behavioral_completeness/{MATRIX,BACKLOG}.md`

- [ ] **Step 1:** update the `### crafting` MATRIX section (keep all 7 fields + citations; lint requires it):
  - Behavior coverage → append `; craft-vs-buy injects NpcBuyAction into GatherMaterials.relevant_actions when cheaper+affordable (craft_vs_buy.py, goals/gathering.py)`.
  - Proof coverage → append `; CraftVsBuy [dominance, monotonicity, totality, safety] + NpcBuyInventory [safety] (PROOF_CONCEPT_INDEX)`.
  - Gap + policy → `CLOSED — act: buy when strictly fewer cooldowns and affordable above the gold reserve, else craft; classes proven (synthesis)`.
  Run `uv run pytest tests/test_audit/test_matrix_complete.py -q --no-cov` → PASS (`lint_matrix == []`).

- [ ] **Step 2:** re-rank `BACKLOG.md` — crafting CLOSED (score 0 / Closed section), so **tasks** (score 18) becomes rank 1.

- [ ] **Step 3:** full gates:
  - `uv run pytest tests/ -q` → 100% coverage, all pass (craft_vs_buy.py 100%; the wiring branches covered).
  - Formal: `cd formal && bash gate/check_no_orphan_modules.sh && bash gate/check_no_sorry.sh && bash gate/check_axioms.sh && bash gate/check_proof_concept_index.sh && lake build oracle 2>&1 | tail -2 && lake build 2>&1 | tail -2` → all OK; new differential passes.
  - `uv run mypy src/artifactsmmo_cli/ai/craft_vs_buy.py src/artifactsmmo_cli/ai/goals/gathering.py` + `ruff check` → clean.
  Fix any RED before committing.

- [ ] **Step 4: commit**

```bash
git add docs/behavioral_completeness/MATRIX.md docs/behavioral_completeness/BACKLOG.md
git commit -m "docs(audit): close crafting row (craft-vs-buy, classes proven)"
```

---

## Self-review notes (author)

- **Spec coverage:** decision core→T1; proofs (4 classes)→T2; differential+mutation→T3; cost models + adapter + wiring (NpcBuy injection, reserve-gated)→T4; matrix close→T5. No data-plumbing task: `_npc_locations`/`npc_location`/`npc_sells_item`/`npcs_selling_item`/`NpcBuyAction` already exist (verified).
- **Placeholder scan:** none (numeric test literals only).
- **Type consistency:** `cheaper_acquisition(craft_cooldowns, buy_cooldowns, total_price, gold, reserve)` + `Method.{CRAFT,BUY}` identical T1/T3/T4; Lean `cheaperAcquisition(craftCd, buyCd, totalPrice, gold, reserve)` + `Method.{craft,buy}` T2/T3; `acquisition_method(item, needed, state, game_data, reserve)` T4; `GOLD_RESERVE` T1/T4.
- **Execution reads (not placeholders):** the real `NpcBuyAction` constructor field names + `quantity` default (T4 verifies via `actions/npc.py`); `GatherMaterialsGoal`'s needed-items attribute (`self._needed`) and `relevant_actions` return-list name (`result`) — T4 confirms; the `Oracle.lean` simple-branch arg convention (T3 mirrors an existing branch); whether `min_gathers` signature is `(item, qty, recipes, owned)` (confirmed in the resources gap).
