# Complete Effect Coverage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Model gold-bag consumables (use → +gold), carve gems + christmas_magic, and close the structural silent-drop hole so every item effect is modeled-or-carved.

**Architecture:** New `ItemStats.gold_value` + a `gold` ingest branch; a plain GOAP `UseGoldBagAction` pulled by gold-needing goals; `_ITEM_EFFECT_CARVEOUTS` for gems/christmas_magic; the item-effect coverage guard extended from equippable-only to all item types. One Lean addition: an `ApplyBaseline` contract for the new action.

**Tech Stack:** Python 3.13 (`uv` at `~/.local/bin/uv`), Lean 4 (`formal/`), Hypothesis (differential), `formal/diff/mutate.py`, pytest (`--cov-fail-under=100`).

## Global Constraints

- `uv` at `~/.local/bin/uv`; ALWAYS `uv run`. `git checkout uv.lock` before commit if dirtied.
- No inline imports; no `if TYPE_CHECKING`; no `...` imports; NEVER catch `Exception`. ONE behavioral class per file.
- Use only API data or fail. Tests: 0 errors/warnings/skipped (token-gated live tests excepted), 100% coverage; real fixtures; never mock the unit under test.
- Formal: computable Lean `def` + role theorem + `Contracts.lean` pin + `Manifest.lean` roster + differential + mutation; no `sorry`/`native_decide`/custom axioms; standard axioms only. NEVER run `gate.sh`/`mutate.py` while anything imports `src`; `git diff src` after mutation.
- Branch: `feat/complete-effect-coverage` (off main `b054d369`). Spec: `docs/superpowers/specs/2026-06-29-complete-effect-coverage-design.md`.

**Verbatim facts (audit + anchors):**
- The ONLY item-effect gaps are `gold` (model) + `gems` (carve); `christmas_magic` latent (carve); monster effects 0 gaps.
- `gold` carriers: `bag_of_gold` (+2500), `small_bag_of_gold` (+1000); `gems`: `small_bag_of_gems` (+25), `bag_of_gems` (+50) — all `type=="consumable"`.
- Item-effect guard: `game_data._build_items` else-branch (~line 1351) currently `if item_type in ITEM_TYPE_TO_SLOTS: raise` (equippable-only). Carve constants: `_RUNE_ABILITY_CARVEOUTS` (~107), `threat` (inline pass ~1339). Ingest elif-chain ~1265-1345.
- Gold-credit pattern (action apply): `dataclasses.replace(state, gold=state.gold + v, inventory=<dec>, cooldown_expires=None)` (npc_sell/ge_fill).
- `UseConsumableAction` (`actions/consumable.py:34`) is the action template (is_applicable/apply/cost/execute via `action_use_item` + `SimpleItemSchema`). Factory action set: `actions/factory.py:56-62` (plain actions).
- Gold-bags already keep-protected: `type=="consumable"` → `CONSUMABLE_KEEP=999` (inventory_caps `_non_recipe_keep_floor` ~187) — no extra protection needed.
- `ApplyBaseline.lean`: `npcSellApply` (line 272, gold+inv) / `useConsumableApply` (line 290, hp+inv) are the mirror; `ModeledApply` inductive (line 507), `ModeledApply.run` (570), `all_actions_preserve_baseline` (602) enumerate all 24; per-action theorem = `unfold preservesBaseline <fn>; exact ⟨rfl,rfl,rfl,rfl,rfl,rfl,rfl,rfl⟩`.

---

### Task 1: `gold_value` + ingest + carves + structural guard

**Files:**
- Modify: `src/artifactsmmo_cli/ai/item_catalog.py` (new `gold_value` field), `src/artifactsmmo_cli/ai/game_data.py` (ingest `gold`; `_ITEM_EFFECT_CARVEOUTS`; extend guard)
- Test: `tests/ai/test_game_data_item_effect_guard.py` (extend), `tests/ai/test_effect_coverage_audit.py` (new, live-gated)

**Interfaces:**
- Produces: `ItemStats.gold_value: int = 0`; `game_data` ingests `gold` → `gold_value`; `_ITEM_EFFECT_CARVEOUTS: frozenset[str]`; the guard raises for ANY unmodeled, uncarved item effect.

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/ai/test_game_data_item_effect_guard.py
def test_gold_effect_sets_gold_value():
    gd = GameData()
    gd._build_items([_item("bag_of_gold", "consumable", ["gold"])])  # _item sets value=1
    assert gd.item_stats("bag_of_gold").gold_value == 1   # the _Eff value


def test_gems_and_christmas_magic_are_carved_not_fatal():
    gd = GameData()
    gd._build_items([_item("bag_of_gems", "consumable", ["gems"]),
                     _item("christmas_cane", "weapon", ["christmas_magic", "attack_fire"])])
    assert gd.item_stats("bag_of_gems") is not None
    assert gd.item_stats("christmas_cane") is not None


def test_unknown_effect_on_CONSUMABLE_now_raises():
    # the structural fix: the guard is no longer equippable-only.
    gd = GameData()
    with pytest.raises(GameDataCoverageError) as exc:
        gd._build_items([_item("weird_potion", "consumable", ["totally_new_code"])])
    assert "weird_potion" in str(exc.value) and "totally_new_code" in str(exc.value)
```

> Confirm the `_item` helper's `_Eff.value` (it's `1` in the existing file) — `gold_value` should pick up `effect.value`.

- [ ] **Step 2: Run to verify failure**

Run: `~/.local/bin/uv run pytest tests/ai/test_game_data_item_effect_guard.py -v --no-cov`
Expected: `gold_value` attr missing; gems/christmas raise (not yet carved); consumable-unknown does NOT raise yet (silent-drop).

- [ ] **Step 3: Add `gold_value` to ItemStats**

In `item_catalog.py`, add beside the other non-combat consumable fields (near `teleport_map_id`):
```python
gold_value: int = 0   # +gold granted when a gold-bag consumable is used (effect `gold`)
```

- [ ] **Step 4: Ingest `gold` + add the carve constant + extend the guard (game_data.py)**

Add a `gold` ingest branch in the elif-chain (near `teleport`):
```python
                    elif effect.code == "gold":
                        # Gold-bag consumable (bag_of_gold +2500, small_bag_of_gold
                        # +1000): grants gold when used. Modeled so UseGoldBagAction
                        # can credit it; not a combat/gear stat.
                        stats.gold_value = effect.value
```
Add the carve constant near `_RUNE_ABILITY_CARVEOUTS`:
```python
# Item effect codes intentionally NOT modeled (documented carves), checked before
# the all-items coverage guard so they don't raise:
#   gems            — account meta-currency (skins/subscription/event-spawn); no use
#                     in the autonomous reach-50 loop.
#   christmas_magic — event weapon `christmas_cane` effect; the player's hits BUFF the
#                     enemy (a self-debuff). Never modeled; carved so the cane (if it
#                     ever goes live) doesn't trip the equippable guard.
_ITEM_EFFECT_CARVEOUTS: frozenset[str] = frozenset({"gems", "christmas_magic"})
```
Add a carve branch + extend the guard (drop the equippable-only restriction):
```python
                    elif effect.code in _ITEM_EFFECT_CARVEOUTS:
                        pass   # documented intentional carve — see _ITEM_EFFECT_CARVEOUTS
                    else:
                        item_type = getattr(item.type_, "value", item.type_)
                        raise GameDataCoverageError(
                            f"item {item.code!r} ({item_type}) carries unmapped effect "
                            f"code {effect.code!r}: model it, or add a documented entry to "
                            "_ITEM_EFFECT_CARVEOUTS / _RUNE_ABILITY_CARVEOUTS")
```
(The `threat` and `_RUNE_ABILITY_CARVEOUTS` branches stay above this; the raise is now for ALL item types, not just equippable.)

- [ ] **Step 5: Live-audit regression test**

```python
# tests/ai/test_effect_coverage_audit.py  (token-gated like test_gear_taxonomy_live_audit)
# Load live GameData; for every item, assert every effect code is either reflected in the
# built ItemStats (modeled) or in the carve sets — i.e. _build_items raised on NONE of them
# (the load itself succeeding proves coverage). Assert gold_value>0 on bag_of_gold; gems/
# christmas in _ITEM_EFFECT_CARVEOUTS. Mirror the skip-without-TOKEN marker of
# test_gear_taxonomy_live_audit.
```

- [ ] **Step 6: Run + commit**

Run the guard tests + full suite + mypy on the 2 src files. Live load sanity:
`~/.local/bin/uv run python -c "from artifactsmmo_cli.client_manager import ClientManager; from artifactsmmo_cli.ai.game_data import GameData; from artifactsmmo_cli.config import Config; cm=ClientManager(); cm.initialize(Config.from_token_file()); gd=GameData.load(cm.client, force_refresh=True); print('LOAD OK', gd.item_stats('bag_of_gold').gold_value)"` → `LOAD OK 2500`. `git checkout uv.lock`.

```bash
git add src/artifactsmmo_cli/ai/item_catalog.py src/artifactsmmo_cli/ai/game_data.py tests/ai/test_game_data_item_effect_guard.py tests/ai/test_effect_coverage_audit.py
git commit -m "feat(effects): model gold_value, carve gems/christmas_magic, close silent-drop hole"
```

---

### Task 2: `UseGoldBagAction` + factory

**Files:**
- Create: `src/artifactsmmo_cli/ai/actions/use_gold_bag.py`
- Modify: `src/artifactsmmo_cli/ai/actions/factory.py` (add to the action set)
- Test: `tests/ai/actions/test_use_gold_bag.py`

**Interfaces:**
- Consumes: `ItemStats.gold_value` (Task 1).
- Produces: `UseGoldBagAction` (a plain `Action`): `is_applicable` iff a gold-bag (`gold_value>0`) is owned; `apply` credits `gold += gold_value` + decrements the bag; `execute` via `action_use_item`; `cost` a small constant.

- [ ] **Step 1: Write the failing tests**

```python
# tests/ai/actions/test_use_gold_bag.py
def test_applicable_iff_gold_bag_owned(gold_fixture):
    state, game_data = gold_fixture  # bag_of_gold (gold_value 2500) in inventory
    assert UseGoldBagAction(_item_stats=game_data.all_item_stats).is_applicable(state, game_data)
    empty = dataclasses.replace(state, inventory={})
    assert not UseGoldBagAction(_item_stats=game_data.all_item_stats).is_applicable(empty, game_data)


def test_apply_credits_gold_and_decrements_bag(gold_fixture):
    state, game_data = gold_fixture
    out = UseGoldBagAction(_item_stats=game_data.all_item_stats).apply(state, game_data)
    assert out.gold == state.gold + 2500
    assert out.inventory.get("bag_of_gold", 0) == state.inventory["bag_of_gold"] - 1


def test_planner_uses_gold_bag_for_short_bank_expansion(gold_fixture):
    # gold below next_expansion_cost but a bag would cover it -> the GOAP planner
    # chains UseGoldBag before BuyBankExpansion. (Match the existing planner-test harness.)
    ...
```

> Reuse/extend an existing action-test fixture; pick the single highest-gold-value owned bag if several (deterministic tiebreak — document).

- [ ] **Step 2: Run to verify failure** — module missing.

- [ ] **Step 3: Implement `UseGoldBagAction`** (mirror `UseConsumableAction`)

```python
# src/artifactsmmo_cli/ai/actions/use_gold_bag.py
"""UseGoldBagAction: consume a gold-bag consumable to credit its gold."""
import dataclasses
from dataclasses import dataclass, field
from collections.abc import Mapping
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.models.simple_item_schema import SimpleItemSchema
from artifactsmmo_api_client.api.my_characters.action_use_item_my_name_action_use_item_post import sync as action_use_item
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

USE_GOLD_BAG_COST = 2.0


@dataclass
class UseGoldBagAction(Action):
    """Consume a gold-bag (effect `gold`) to add its gold to the pocket."""
    tags: ClassVar[frozenset[str]] = frozenset({"currency"})
    _item_stats: Mapping[str, ItemStats] = field(default_factory=dict, repr=False)

    def _best_bag(self, state: WorldState) -> tuple[str, int] | None:
        # highest-gold owned gold-bag; deterministic (gold desc, then code) tiebreak.
        best: tuple[str, int] | None = None
        for code, qty in state.inventory.items():
            if qty <= 0:
                continue
            s = self._item_stats.get(code)
            if s is None or s.gold_value <= 0:
                continue
            if best is None or (s.gold_value, code) > (best[1], best[0]):  # see note
                best = (code, s.gold_value)
        return best

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return self._best_bag(state) is not None

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        bag = self._best_bag(state)
        assert bag is not None
        code, gold_value = bag
        new_inv = dict(state.inventory)
        new_inv[code] -= 1
        if new_inv[code] == 0:
            del new_inv[code]
        return dataclasses.replace(state, gold=state.gold + gold_value,
                                   inventory=new_inv, cooldown_expires=None)

    def cost(self, state, game_data, history: LearningStore | None = None) -> float:
        return USE_GOLD_BAG_COST

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        bag = self._best_bag(state)
        if bag is None:
            raise RuntimeError("UseGoldBag: no gold-bag in inventory at execute time")
        code, _ = bag
        result = action_use_item(client=client, name=state.character,
                                 body=SimpleItemSchema(code=code, quantity=1))
        result = Action._raise_for_error(result, f"UseGoldBag({code})")
        return WorldState.from_character_schema(
            result.data.character, bank_items=state.bank_items, bank_gold=state.bank_gold,
            pending_items=state.pending_items, active_events=state.active_events)

    def __repr__(self) -> str:
        return "UseGoldBag"
```

> Fix the tiebreak: pick max by `(gold_value, code)` — sort key must be unambiguous; the `>` comparison above compares tuples `(gold_value, code)` vs `(best_gold, best_code)`, so write it as comparing the SAME shape. Verify `action_use_item` import path + `SimpleItemSchema` against `actions/consumable.py:execute`.

- [ ] **Step 4: Add to the factory**

In `actions/factory.py` plain-action set (~line 56, beside `UseConsumableAction`):
```python
        UseGoldBagAction(_item_stats=game_data.all_item_stats),
```

- [ ] **Step 5: Run + commit**

Run the new tests + full suite + mypy on the 2 files. `git checkout uv.lock`.

```bash
git add src/artifactsmmo_cli/ai/actions/use_gold_bag.py src/artifactsmmo_cli/ai/actions/factory.py tests/ai/actions/test_use_gold_bag.py
git commit -m "feat(effects): UseGoldBagAction — consume gold-bags for their gold (GOAP-pulled)"
```

---

### Task 3: `ApplyBaseline` Lean contract + differential + mutation + gate

**Files:**
- Modify: `formal/Formal/ApplyBaseline.lean` (def + theorem + `ModeledApply` variant + `run` + `all_actions_preserve_baseline`), `formal/Formal/Contracts.lean`, `formal/Formal/Manifest.lean`, `formal/diff/mutate.py` (a baseline-revert witness), `formal/diff/test_apply_baseline_diff.py` (the new action's apply ≡ model)

**Interfaces:**
- Consumes: `UseGoldBagAction.apply` (Task 2).

- [ ] **Step 1: Lean — model the apply + theorem** (mirror `npcSellApply`/`useConsumableApply`)

```lean
/-- `UseGoldBagAction.apply` model: gold up, inventory down. -/
def useGoldBagApply (s : WorldStateLean) (newGold : Int)
    (newInv : List (String × Nat)) : WorldStateLean :=
  { s with gold := newGold, inventory := newInv, cooldown_expires := none }

theorem useGoldBagApply_preserves_baseline (s : WorldStateLean) (g : Int)
    (i : List (String × Nat)) :
    preservesBaseline s (useGoldBagApply s g i) := by
  unfold preservesBaseline useGoldBagApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩
```
Add the `ModeledApply` variant (Family-3 inventory-consume, beside `useConsumable`):
```lean
  | useGoldBag        (newGold : Int) (newInv : List (String × Nat)) : ModeledApply
```
`ModeledApply.run`: `| useGoldBag g i => useGoldBagApply s g i`
`all_actions_preserve_baseline` match arm: `| useGoldBag g i => exact useGoldBagApply_preserves_baseline s g i`

- [ ] **Step 2: Build + pin + roster**

`cd formal && lake build` (no sorry; standard axioms — the proof is 8×`rfl`). Add `useGoldBagApply_preserves_baseline` to `Manifest.lean` (#check) + `Contracts.lean` (exact-statement pin). If `all_actions_preserve_baseline`'s statement is pinned by COUNT or enumerates variants, update that pin to include `useGoldBag`. `cd formal && lake build` full.

- [ ] **Step 3: Differential + mutation**

In `formal/diff/test_apply_baseline_diff.py`, add `UseGoldBagAction` to the apply-baseline differential (the live `apply` preserves the 8-conjunct baseline + mutates only gold/inventory — mirror how `npc_sell`/`use_consumable` are exercised). In `mutate.py`, add a baseline-revert kill-witness for `useGoldBag` (e.g. a mutant that drops the gold credit or touches a baseline field — must die). Run the apply-baseline differential + the mutation; `git diff src` empty after.

- [ ] **Step 4: Full suite + full gate**

`~/.local/bin/uv run pytest --cov-fail-under=100`. Then, nothing else importing `src`: `cd formal && ./gate.sh` → green end-to-end (build, no-sorry, axiom-lint, manifest, contracts, differential incl. the new apply, mutation incl. the new witness, extraction-drift). `git diff src` empty; `git checkout uv.lock`.

- [ ] **Step 5: Commit**

```bash
git checkout uv.lock 2>/dev/null
git add formal/
git commit -m "feat(effects): ApplyBaseline contract for UseGoldBagAction (25th modeled action)"
```

---

## Final review (after all tasks)

Whole-branch review over `git merge-base main HEAD..HEAD`. Verify:
- Every live item effect is modeled-or-carved; the guard now raises for ALL item types (silent-drop hole closed) — synthetic-unknown-consumable test proves it.
- `gold` → `gold_value`; `UseGoldBagAction` credits exact gold + frees the slot; the planner chains it before a gold-short gold-need; gold-bags keep-protected (unchanged).
- `gems`/`christmas_magic` carved with documented rationale; no behavior for them.
- `gold_value` is NOT a gear/combat stat (no `gear_value`/`predict_win`/taxonomy touch).
- `ApplyBaseline` now enumerates 25 actions; `useGoldBag_preserves_baseline` pinned + differential-bound + mutation-killed; no statement weakened.
- Then `superpowers:finishing-a-development-branch`.

## Self-review notes (plan author)

- **Spec coverage:** gold model+ingest+guard → T1; UseGoldBagAction+factory → T2; ApplyBaseline+diff+mutation+gate → T3. All covered.
- **gold_value is currency** — explicitly NOT routed into gear_value/combat_raw/predict_win (the final review checks this); no gear-core re-prove.
- **The structural guard** is the load-bearing correctness fix (no silent drops ∀ item types); the synthetic-unknown-consumable test is its lock.
- **Naming consistency:** `gold_value`/`UseGoldBagAction`/`_best_bag`/`_ITEM_EFFECT_CARVEOUTS`/`useGoldBagApply`/`useGoldBag_preserves_baseline`/`USE_GOLD_BAG_COST` — used identically across tasks.
- **Honest open seams** (match-the-sibling): the gold/action/planner test fixtures, `action_use_item`/`SimpleItemSchema` import paths, the apply-baseline differential + mutation idioms, the live-test skip marker, the `all_actions_preserve_baseline` pin shape — each says "open the sibling and match."
- **No live-network unit test beyond the gated audit** (the audit mirrors `test_gear_taxonomy_live_audit`'s TOKEN gate).
