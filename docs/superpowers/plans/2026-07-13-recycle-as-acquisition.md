# Recycle-as-Acquisition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teach the planner that recycling a held item is a way to OBTAIN its materials, so the bot stops re-gathering from raw resources what it already holds in crafted form.

**Architecture:** One new pure core (`recoverable_materials`: material → units recoverable from LICENSED surplus, authority = the existing `inventory_keep.destroyable`) plus two edges — the tier descent (`prerequisite_graph.prerequisites` treats a recoverable material as a LEAF) and the goal's action pool (`GatherMaterialsGoal.relevant_actions` admits the already-licensed `RecycleAction`s and the withdraws that feed them). The map is computed once per cycle in `player` (the seam where `SelectionContext` exists) and threaded down as a plain `dict[str,int]`, defaulting to `{}` so every change lands INERT until Task 6 wires it in.

**Tech Stack:** Python 3.13, `uv`, pytest, Lean 4 (`formal/`), GOAP planner.

**Spec:** `docs/superpowers/specs/2026-07-13-recycle-as-acquisition-design.md` (`dee382ce`)

## Global Constraints

- **Always** prefix Python with `uv run`. `uv` is at `/home/blentz/.local/bin/uv` and is **NOT on PATH** — use the absolute path.
- Run pytest via `env -u FORCE_COLOR` — the shell exports `FORCE_COLOR=3`, which breaks ~10 ANSI tests.
- Two-lane suite: `env -u FORCE_COLOR uv run pytest -n auto tests/ --ignore=tests/scenarios` then serial `env -u FORCE_COLOR uv run pytest tests/scenarios --cov-append`. A naive `-n auto` over everything flakes the wall-clock planner tests.
- `formal/diff/` is **NOT** in the default pytest path — run it explicitly.
- The mutation gate needs a **CLEAN COMMITTED TREE**. Refresh `formal/mutate.py` anchors on **every edited line** of a mutated file, or stale anchors report as `(stale)` SURVIVORS and fail the gate.
- **NO inline imports.** All imports at top of file.
- **NEVER** catch `Exception`.
- **NO** `if TYPE_CHECKING`.
- **ONE behavioral class per file.**
- Success criteria: 0 errors, 0 warnings, 0 skipped, **100% coverage**.
- Use only API data or fail with an error. No defaulting to paper over missing game data.
- Yield fidelity: `recoverable` must use `n * max(1, qty // 2)` (repeated **quantity=1** recycles, matching what the factory emits and what `RecycleAction.apply` does), **not** the batch form `max(1, (qty*n)//2)`.
- The authority for "may I recycle this for parts" is `inventory_keep.destroyable`. **NO new `KeepReason`.**

---

## File Structure

| File | Responsibility |
|---|---|
| `src/artifactsmmo_cli/ai/recoverable_materials.py` | **NEW.** Pure core: material → units recoverable from licensed surplus (bag+bank). |
| `src/artifactsmmo_cli/ai/actions/recycle.py` | `RecycleAction` gains `bag_floor` so a protected bag copy can never be consumed. |
| `src/artifactsmmo_cli/ai/destructive_license.py` | Recycle gains a BANK route + stamps `bag_floor`. NpcSell/Delete unchanged. |
| `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py` | Edge 1: recoverable material → LEAF. |
| `src/artifactsmmo_cli/ai/tiers/strategy.py` | Threads `recoverable` through `actionable_step` / `unmet_closure_size` / `root_cost` / `is_reachable`. |
| `src/artifactsmmo_cli/ai/goals/gathering.py` | Edge 2: admit licensed `RecycleAction`s + withdraws for their SOURCE codes. |
| `src/artifactsmmo_cli/ai/player.py`, `tiers/progression_tree.py`, `level_skill_expand.py`, `strategy_driver.py`, `plan_tree.py` | Plumbing — computes `recoverable` at the ctx seam and threads it. **This is where the epic goes live.** |
| `formal/Formal/PrerequisiteGraph.lean` | `prereqEdges` gains the recoverable flag + `prereqs_recoverable_leaf`; recoverable-yield arithmetic mirrored. |
| `formal/Oracle.lean`, `formal/diff/test_prerequisite_graph_diff.py` | Oracle entry + differential. |
| `src/artifactsmmo_cli/audit/recycle_source_completeness.py` | **NEW.** Behavioral census: LIVENESS / SAFETY / BANKED / PARTIAL. |
| `scripts/gen_recycle_source_completeness.py` | **NEW.** `--check` CI gate. |
| `.github/workflows/census-gate.yml` | Wire the third census. |

**Why a separate census module:** the existing `audit/inventory_completeness.py` grid is `KeepReason × cap × pressure × band` with a *disposal* verdict ("did the planner shed the surplus?"). Recycle-as-source asks an *acquisition* question ("did the planner recycle to OBTAIN a material?"). Different cell shape, different verdict — a separate module keeps both honest. Per the keep epic's lesson, its oracle is the authority, so `recoverable_materials` itself must be pinned by **unit tests written before any consumer depends on it** (Task 1).

---

## Task 1: `recoverable_materials` pure core

**Files:**
- Create: `src/artifactsmmo_cli/ai/recoverable_materials.py`
- Test: `tests/ai/test_recoverable_materials.py`

**Interfaces:**
- Consumes: `inventory_keep.destroyable(code, state, game_data, ctx) -> int` (existing; counts bag+bank).
- Produces: `recoverable_materials(state: WorldState, game_data: GameData, ctx: SelectionContext) -> dict[str, int]`

This task is **INERT** — nothing calls it yet. That is deliberate: the census's oracle will BE this function, so it must be pinned by unit tests before any consumer can make the two wrong together.

**Eligibility gates.** The core must apply the SAME gates `RecycleAction.is_applicable` applies, or the descent will leaf a node the executor refuses to serve and the bot stalls:
1. `game_data.crafting_recipe(code)` is not None
2. `stats.crafting_skill` is truthy
3. `state.skills.get(stats.crafting_skill, 1) >= stats.crafting_level`
4. `game_data.workshop_location(stats.crafting_skill)` is not None

- [ ] **Step 1: Write the failing tests**

Create `tests/ai/test_recoverable_materials.py`. Use the repo's existing GameData/WorldState/SelectionContext fixtures (see `tests/ai/test_recycle_surplus.py` for the established pattern of building a fake `GameData` + `SelectionContext`; mirror its fixture construction rather than inventing a new one).

```python
def test_recoverable_sums_two_live_contributors_at_depth(game_data, ctx):
    """TWO disjoint contributors, both live. A single contributor cannot
    distinguish `sum` from `max` — the keep epic was bitten by exactly this."""
    # fishing_net {ash_plank: 6}; copper_axe {copper_bar: 6}
    # bag: 7 fishing_net (keep_owned 1 -> destroyable 6)
    #      17 copper_axe (keep_owned 1 -> destroyable 16)
    state = make_state(inventory={"fishing_net": 7, "copper_axe": 17})
    out = recoverable_materials(state, game_data, ctx)
    assert out["ash_plank"] == 6 * max(1, 6 // 2)    # 18
    assert out["copper_bar"] == 16 * max(1, 6 // 2)  # 48


def test_recoverable_counts_bank_copies(game_data, ctx):
    """destroyable counts bag+bank, so a banked hoard is recoverable —
    DEPOSIT_FULL banks the surplus, so this is the MAIN path, not an edge."""
    state = make_state(inventory={}, bank_items={"fishing_net": 7})
    out = recoverable_materials(state, game_data, ctx)
    assert out["ash_plank"] == 6 * max(1, 6 // 2)


def test_recoverable_unit_yield_not_batch_yield(game_data, ctx):
    """A 1-qty ingredient distinguishes repeated-unit from batch recycling.
    4 unit recycles of {glue: 1} recover 4; the batch formula predicts 2."""
    # sticky_thing {glue: 1}; bag 5, keep_owned 1 -> destroyable 4
    state = make_state(inventory={"sticky_thing": 5})
    out = recoverable_materials(state, game_data, ctx)
    assert out["glue"] == 4 * max(1, 1 // 2)   # 4 * 1 == 4
    assert out["glue"] != max(1, (1 * 4) // 2)  # NOT 2


def test_protected_item_contributes_nothing(game_data, ctx):
    """The last copper_axe is the WORKING_KIT tool: destroyable == 0.
    This is the anti-tool-melting property."""
    state = make_state(inventory={"copper_axe": 1})
    assert recoverable_materials(state, game_data, ctx) == {}


def test_under_skill_item_is_not_recoverable(game_data, ctx):
    """RecycleAction.is_applicable refuses when the char is under the recipe's
    crafting_level, so recoverable must refuse too or the descent stalls."""
    state = make_state(inventory={"fire_staff": 5},
                       skills={"weaponcrafting": 1})  # fire_staff needs 5
    assert recoverable_materials(state, game_data, ctx) == {}


def test_unknown_workshop_is_not_recoverable(game_data_no_workshop, ctx):
    """RecycleAction.is_applicable requires workshop_location."""
    state = make_state(inventory={"fishing_net": 7})
    assert recoverable_materials(state, game_data_no_workshop, ctx) == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/ai/test_recoverable_materials.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.recoverable_materials'`

- [ ] **Step 3: Implement**

Create `src/artifactsmmo_cli/ai/recoverable_materials.py`:

```python
"""Materials recoverable by RECYCLING licensed surplus — the acquisition face
of recycle.

`ai/recycle_surplus.recyclable_surplus` answers a DISPOSAL question (which items
may I shed, and how many BAG copies). This answers an ACQUISITION question (which
MATERIALS can I obtain, and how many units) over bag+bank. The authority is the
same one: `inventory_keep.destroyable`. "May I recycle this for parts" IS "may I
destroy this", and the keep-unification epic already answered it — including the
WORKING_KIT / COMBAT_WEAPON reasons that protect the last copper_axe. No new
KeepReason exists here, by design.

YIELD FIDELITY. `actions/factory` emits quantity=1 RecycleActions, so GOAP
recovers n copies by applying a UNIT recycle n times, each yielding
`max(1, (qty * 1) // 2)` per `RecycleAction.apply`. The total is
`n * max(1, qty // 2)` — NOT the batch expression `max(1, (qty * n) // 2)`, which
differs whenever qty == 1 (4 unit recycles of a 1-qty ingredient recover 4; the
batch form predicts 2). If this term drifts from `RecycleAction.apply`, the tier
descent promises materials the executor cannot deliver and the bot stalls.

ELIGIBILITY MIRRORS THE EXECUTOR. Every gate `RecycleAction.is_applicable`
enforces is enforced here (recipe exists, crafting skill known, character meets
the crafting level, workshop location known). A material declared recoverable
that the executor then refuses to recycle is a LEAF WITH NO PLAN — the livelock
shape of 3166d390.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_keep import destroyable
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState


def recoverable_materials(state: WorldState, game_data: GameData,
                          ctx: SelectionContext) -> dict[str, int]:
    """Map each material code to the units recoverable by recycling LICENSED
    surplus held in the bag OR the bank."""
    out: dict[str, int] = {}
    bank = state.bank_items or {}
    codes = set(state.inventory) | set(bank)
    for code in codes:
        recipe = game_data.crafting_recipe(code)
        if recipe is None:
            continue
        stats = game_data.item_stats(code)
        if stats is None or not stats.crafting_skill:
            continue
        if state.skills.get(stats.crafting_skill, 1) < stats.crafting_level:
            continue  # skill gate: the server rejects the recycle
        if game_data.workshop_location(stats.crafting_skill) is None:
            continue  # no workshop known → RecycleAction.is_applicable is False
        copies = destroyable(code, state, game_data, ctx)
        if copies <= 0:
            continue
        for mat_code, mat_qty in recipe.items():
            out[mat_code] = out.get(mat_code, 0) + copies * max(1, mat_qty // 2)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/ai/test_recoverable_materials.py -v
```
Expected: PASS, all 6.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/recoverable_materials.py tests/ai/test_recoverable_materials.py
git commit -m "feat(recycle): recoverable_materials core — recycle as an ACQUISITION route

Authority is the existing inventory_keep.destroyable (bag+bank); no new
KeepReason. Yield mirrors repeated quantity=1 RecycleActions (n * max(1, qty//2)),
and eligibility mirrors RecycleAction.is_applicable exactly, so the tier descent
can never leaf a node the executor refuses to serve.

Inert: no consumers yet. The census oracle will BE this function, so it is pinned
by unit tests FIRST — an oracle and its consumer written together are wrong
together."
```

---

## Task 2: `RecycleAction.bag_floor` — the anti-tool-melting guard

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/recycle.py:20-52`
- Test: `tests/ai/actions/test_recycle.py`

**Interfaces:**
- Produces: `RecycleAction(code, quantity=1, workshop_location=None, bag_floor=0)`; `is_applicable` now also requires `state.inventory[code] - quantity >= bag_floor`.

**Why.** The world model does not distinguish WHICH copy a Recycle consumes — it just decrements the count. Task 3 admits bank copies as recycle sources; without a bag floor, GOAP could satisfy that by recycling the **working `copper_axe` sitting alone in the bag** instead of withdrawing a bank copy. That is the exact failure the keep epic already paid for once (*"destroyable alone on the bag side EATS THE WORKING TOOL"*). The floor forces GOAP to `Withdraw` first.

`bag_floor` is stamped at LICENCE time (Task 3), where the ctx is complete — the same way `workshop_location` is already baked in. It stays pure at search time.

- [ ] **Step 1: Write the failing tests**

Append to `tests/ai/actions/test_recycle.py`:

```python
def test_recycle_blocked_when_it_would_breach_the_bag_floor(game_data):
    """The working copper_axe alone in the bag, 17 in the bank. bag_floor=1
    means the LAST BAG COPY IS UNREACHABLE — GOAP must withdraw first."""
    state = make_state(inventory={"copper_axe": 1}, bank_items={"copper_axe": 17})
    action = RecycleAction(code="copper_axe", quantity=1,
                           workshop_location=(2, 1), bag_floor=1)
    assert action.is_applicable(state, game_data) is False


def test_recycle_allowed_once_a_bank_copy_is_withdrawn(game_data):
    """After Withdraw, the bag holds 2: recycling one still leaves the floor."""
    state = make_state(inventory={"copper_axe": 2}, bank_items={"copper_axe": 16})
    action = RecycleAction(code="copper_axe", quantity=1,
                           workshop_location=(2, 1), bag_floor=1)
    assert action.is_applicable(state, game_data) is True


def test_recycle_bag_floor_defaults_to_zero(game_data):
    """Default 0 preserves every existing call site's behavior exactly."""
    state = make_state(inventory={"fishing_net": 1})
    action = RecycleAction(code="fishing_net", quantity=1,
                           workshop_location=(2, 1))
    assert action.bag_floor == 0
    assert action.is_applicable(state, game_data) is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/ai/actions/test_recycle.py -v
```
Expected: FAIL — `TypeError: RecycleAction.__init__() got an unexpected keyword argument 'bag_floor'`

- [ ] **Step 3: Implement**

In `src/artifactsmmo_cli/ai/actions/recycle.py`, add the field after `workshop_location`:

```python
    code: str
    quantity: int = 1
    workshop_location: tuple[int, int] | None = field(default=None, repr=False)
    bag_floor: int = field(default=0, repr=False)
    """Bag copies of `code` that must SURVIVE this recycle (`keep_in_bag`).

    The world model does not distinguish WHICH copy a recycle consumes — it just
    decrements the count. Once bank copies are licensed as recycle SOURCES
    (`destructive_license`), a recycle with no floor could satisfy itself by
    eating the working tool sitting alone in the bag instead of withdrawing a
    bank copy. The floor makes the protected bag copies UNREACHABLE, so GOAP is
    forced to Withdraw first. Stamped at licence time, where the ctx is complete
    — exactly as `workshop_location` is baked in. Default 0 = no floor."""
```

Add the guard to `is_applicable`, immediately after the existing bag-count check:

```python
        if state.inventory.get(self.code, 0) < self.quantity:
            return False
        if state.inventory.get(self.code, 0) - self.quantity < self.bag_floor:
            return False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/ai/actions/test_recycle.py -v
```
Expected: PASS.

- [ ] **Step 5: Refresh mutation anchors and commit**

Every edited line of `recycle.py` must have its `formal/mutate.py` anchor refreshed (a stale anchor reports as a `(stale)` SURVIVOR and fails the gate).

```bash
grep -n "recycle" formal/mutate.py
git add src/artifactsmmo_cli/ai/actions/recycle.py tests/ai/actions/test_recycle.py formal/mutate.py
git commit -m "feat(recycle): RecycleAction.bag_floor — protected bag copies are unreachable

The world model does not distinguish WHICH copy a recycle consumes. Licensing
bank copies as recycle sources (next commit) would otherwise let GOAP eat the
working copper_axe sitting alone in the bag instead of withdrawing a bank copy —
the same failure the keep epic already paid for. The floor forces the withdraw.

Stamped at licence time where the ctx is complete, as workshop_location already
is. Defaults to 0, so every existing call site is unchanged."
```

---

## Task 3: `destructive_license` — the recycle BANK route

**Files:**
- Modify: `src/artifactsmmo_cli/ai/destructive_license.py:64-101`
- Test: `tests/ai/test_destructive_license.py`

**Interfaces:**
- Consumes: `RecycleAction.bag_floor` (Task 2); `inventory_keep.{bankable, destroyable, keep_in_bag}`.
- Produces: `license_destructive_actions` now stamps `bag_floor` on surviving `RecycleAction`s and admits bank-only recycle sources.

**Why.** `licensed_quantity` short-circuits to 0 for a code with none in the bag (`:73`), so a bank-only `fishing_net` gets **no `RecycleAction` in the pool at all** and `Withdraw -> Recycle` is unplannable. Since `DEPOSIT_FULL` now banks the surplus, that is the MAIN path.

**The rule.** Recycle — and ONLY recycle — gains a bank route:

```
Recycle(code, q) licensed  iff  destroyable(code) >= q
                            and (bankable(code) >= q or bank_copies(code) >= q)
```

`NpcSell` and `Delete` keep the existing bag-side `min(bankable, destroyable)`. Recycle is the only route that just acquired a second purpose, so it is the only one that gets a second reachability path. Safety is preserved by Task 2's floor: `destroyable` bounds HOW MANY copies may cease to exist; `bag_floor` bounds WHICH copies are reachable.

- [ ] **Step 1: Write the failing tests**

Append to `tests/ai/test_destructive_license.py`:

```python
def test_bank_only_recycle_source_is_licensed(state_bank_only, game_data, ctx):
    """7 fishing_net in the BANK, none in the bag. The old bag short-circuit
    dropped the RecycleAction entirely, making Withdraw->Recycle unplannable."""
    pool = [RecycleAction(code="fishing_net", quantity=1, workshop_location=(2, 1))]
    kept = license_destructive_actions(pool, state_bank_only, game_data, ctx)
    assert [a.code for a in kept] == ["fishing_net"]


def test_licensed_recycle_is_stamped_with_the_bag_floor(state_axe_kit, game_data, ctx):
    """1 working copper_axe in the bag (keep_in_bag=1), 17 in the bank.
    The action survives (a bank copy is destroyable) but carries floor 1, so the
    WORKING copy cannot be consumed — GOAP must withdraw first."""
    pool = [RecycleAction(code="copper_axe", quantity=1, workshop_location=(2, 1))]
    kept = license_destructive_actions(pool, state_axe_kit, game_data, ctx)
    assert len(kept) == 1
    assert kept[0].bag_floor == 1
    assert kept[0].is_applicable(state_axe_kit, game_data) is False


def test_fully_protected_code_gets_no_recycle_at_all(state_last_axe, game_data, ctx):
    """1 copper_axe owned total, and it is the WORKING_KIT tool: destroyable==0.
    No bank copy, no bankable copy -> NO action. The anti-tool-melting property."""
    pool = [RecycleAction(code="copper_axe", quantity=1, workshop_location=(2, 1))]
    assert license_destructive_actions(pool, state_last_axe, game_data, ctx) == []


def test_npc_sell_keeps_the_bag_side_rule(state_bank_only, game_data, ctx):
    """Only RECYCLE gains the bank route. A bank-only code is still unsellable —
    selling has not become an acquisition route."""
    pool = [NpcSellAction(item_code="fishing_net", quantity=1, npc="merchant")]
    assert license_destructive_actions(pool, state_bank_only, game_data, ctx) == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/ai/test_destructive_license.py -v
```
Expected: FAIL — the bank-only recycle is dropped; no `bag_floor` is stamped.

- [ ] **Step 3: Implement**

In `destructive_license.py`, add the recycle-specific rule alongside the existing one and stamp the floor. Import `keep_in_bag` and `dataclasses` at the top (no inline imports):

```python
import dataclasses

from artifactsmmo_cli.ai.inventory_keep import bankable, destroyable, keep_in_bag
```

```python
def licensed_recycle_quantity(code: str, state: WorldState, game_data: GameData,
                              ctx: SelectionContext) -> int:
    """Copies of `code` the authority permits a RECYCLE to take.

    Recycle differs from NpcSell/Delete because it is also an ACQUISITION route
    (`ai/recoverable_materials`): its source may legitimately be a BANK copy,
    reached by a Withdraw the planner stages first. So the bag short-circuit
    `licensed_quantity` applies is wrong here — it would drop the RecycleAction
    for a bank-only hoard and make `Withdraw -> Recycle` unplannable, which is
    the MAIN path now that DEPOSIT_FULL banks surplus.

    `destroyable` (bag+bank) bounds HOW MANY copies may cease to exist. Which
    copies are REACHABLE is bounded separately, by the `bag_floor` stamped onto
    the action below — so the working tool alone in the bag is never eaten."""
    reachable = max(bankable(code, state, game_data, ctx),
                    (state.bank_items or {}).get(code, 0))
    return min(reachable, destroyable(code, state, game_data, ctx))
```

Rewrite `license_destructive_actions` to route recycles through the new rule and stamp the floor:

```python
def license_destructive_actions(actions: list[Action], state: WorldState,
                                game_data: GameData,
                                ctx: SelectionContext) -> list[Action]:
    """`actions` with every UNLICENSED destructive action removed.

    Non-destructive actions pass through untouched. A surviving RecycleAction is
    stamped with `bag_floor = keep_in_bag(code)`: the licence says how many copies
    may die, the floor says which ones the planner may reach."""
    licensed: dict[str, int] = {}
    floors: dict[str, int] = {}
    kept: list[Action] = []
    for action in actions:
        demand = destructive_demand(action)
        if demand is None:
            kept.append(action)
            continue
        code, quantity = demand
        if isinstance(action, RecycleAction):
            if code not in floors:
                floors[code] = keep_in_bag(code, state, game_data, ctx)
            allowed = licensed_recycle_quantity(code, state, game_data, ctx)
            if quantity <= allowed:
                kept.append(dataclasses.replace(action, bag_floor=floors[code]))
            continue
        if code not in licensed:
            licensed[code] = licensed_quantity(code, state, game_data, ctx)
        if quantity <= licensed[code]:
            kept.append(action)
    return kept
```

Update the module docstring's "THE LICENCE IS THE AUTHORITY" paragraph to record that recycle now has TWO reachability routes (bag copy above `keep_in_bag`, or a bank copy via Withdraw) and that `bag_floor` — not the conservative `min` — is what keeps the working tool safe.

- [ ] **Step 4: Run the tests**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/ai/test_destructive_license.py tests/ai/actions/test_recycle.py -v
```
Expected: PASS.

- [ ] **Step 5: Refresh mutation anchors and commit**

```bash
grep -n "destructive_license" formal/mutate.py
git add src/artifactsmmo_cli/ai/destructive_license.py tests/ai/test_destructive_license.py formal/mutate.py
git commit -m "feat(recycle): licence a BANK route for recycle, stamped with a bag floor

licensed_quantity short-circuits to 0 for a code with none in the bag, so a
bank-only fishing_net got NO RecycleAction in the pool and Withdraw -> Recycle was
unplannable — the MAIN path now that DEPOSIT_FULL banks the surplus.

Recycle, and only recycle, gains a second reachability route: it is the only
destructive action that is also an ACQUISITION route. NpcSell/Delete keep the
bag-side min(bankable, destroyable).

Safety is not loosened, it is made precise: destroyable bounds HOW MANY copies may
cease to exist, and the stamped bag_floor bounds WHICH copies are reachable."
```

---

## Task 4: Edge 1 — the tier descent leafs a recoverable material

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py:40-71`
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py:63-110,185-196`
- Test: `tests/ai/tiers/test_prerequisite_graph.py`, `tests/ai/tiers/test_strategy.py`

**Interfaces:**
- Produces:
  - `prerequisites(node, state, game_data, recoverable: Mapping[str, int] = EMPTY) -> list[MetaGoal]`
  - `actionable_step(root, state, game_data, recoverable=EMPTY) -> MetaGoal | None`
  - `unmet_closure_size(root, state, game_data, recoverable=EMPTY) -> int`
  - `root_cost(root, state, game_data, recoverable=EMPTY) -> int`
  - `is_reachable(root, state, game_data, path=frozenset(), recoverable=EMPTY) -> bool`
  - where `EMPTY: Mapping[str, int] = MappingProxyType({})` (a module constant — never a mutable `{}` default).

**Still INERT.** Every caller passes nothing, so `recoverable` is empty and behavior is byte-identical. Task 6 wires the real map in.

`is_reachable` MUST be threaded too: if the descent leafs a node but reachability still descends its recipe, the two disagree about the same node.

- [ ] **Step 1: Write the failing tests**

```python
def test_recoverable_material_is_a_leaf(state, game_data):
    """ash_plank is craftable from 10 ash_wood, but 18 units are recoverable by
    recycling surplus fishing_nets — so it is DIRECTLY actionable, not a recipe
    node. This is the whole epic: stop chopping 50 trees you are already holding."""
    node = ObtainItem("ash_plank", 5)
    assert prerequisites(node, state, game_data) == [ObtainItem("ash_wood", 10)]
    assert prerequisites(node, state, game_data, {"ash_plank": 18}) == []


def test_leaf_rule_is_any_recoverable_not_fully_recoverable(state, game_data):
    """recoverable > 0 leafs the node even when it does not cover the need; GOAP
    mixes recycle + gather to make up the shortfall (user decision)."""
    assert prerequisites(ObtainItem("ash_plank", 5), state, game_data,
                         {"ash_plank": 1}) == []


def test_zero_recoverable_still_descends(state, game_data):
    """An entry of 0 is not a leaf — only a positive count is."""
    assert prerequisites(ObtainItem("ash_plank", 5), state, game_data,
                         {"ash_plank": 0}) == [ObtainItem("ash_wood", 10)]


def test_actionable_step_stops_at_the_recoverable_material(state, game_data):
    """The live bug: actionable_step(fire_staff) returned ObtainItem(ash_wood, 10)
    -> 50 gathers. With ash_plank recoverable it returns ash_plank itself."""
    assert actionable_step(ObtainItem("fire_staff"), state, game_data) \
        == ObtainItem("ash_wood", 10)
    assert actionable_step(ObtainItem("fire_staff"), state, game_data,
                           {"ash_plank": 18}) == ObtainItem("ash_plank", 5)


def test_is_reachable_agrees_with_the_descent(state, game_data):
    """If the descent leafs a node, reachability must not still descend its
    recipe — the two would disagree about the same node."""
    assert is_reachable(ObtainItem("fire_staff"), state, game_data,
                        frozenset(), {"ash_plank": 18}) is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/ai/tiers/test_prerequisite_graph.py tests/ai/tiers/test_strategy.py -v
```
Expected: FAIL — `prerequisites() takes 3 positional arguments but 4 were given`

- [ ] **Step 3: Implement**

In `prerequisite_graph.py`, add at module level (imports at top: `from collections.abc import Mapping`, `from types import MappingProxyType`):

```python
NO_RECOVERABLE: Mapping[str, int] = MappingProxyType({})
"""The empty recoverable map — the default, reproducing the pre-epic descent
byte-for-byte. A MappingProxyType, never a mutable `{}` default."""
```

Change the signature and the `ObtainItem` recipe branch:

```python
def prerequisites(node: MetaGoal, state: WorldState, game_data: GameData,
                  recoverable: Mapping[str, int] = NO_RECOVERABLE) -> list[MetaGoal]:
    """Direct prerequisites of `node`, derived from game data.

    `recoverable` maps a material to the units obtainable by RECYCLING licensed
    surplus (`ai/recoverable_materials`). A material with ANY recoverable units is
    a LEAF — directly actionable — so the descent does NOT fall into its recipe.

    Without this, the descent re-derives from raw resources what the bag already
    holds in crafted form: live 2026-07-13, ObtainItem(ash_plank) descended to
    ObtainItem(ash_wood, 10) and the bot chopped 50 ash_wood at 1/cycle (~56 cycles
    of WOODCUTTING xp while the weaponcrafting grind it was serving stayed frozen)
    — while holding 7 fishing_net, whose recipe IS 6 ash_plank each.

    The leaf rule is `> 0`, not "fully covers the need": GOAP mixes recycle with
    gather/craft to make up any shortfall, finding the true optimum rather than an
    all-or-nothing cliff."""
```

Inside the `ObtainItem` branch, before the recipe descent:

```python
        recipe = game_data.crafting_recipe(node.code)
        if recipe is not None:
            if recoverable.get(node.code, 0) > 0:
                return []  # recoverable by recycling licensed surplus → LEAF
            return [ObtainItem(mat, qty) for mat, qty in recipe.items()]
        return []
```

In `strategy.py`, thread `recoverable` through `actionable_step`, `unmet_closure_size`, `root_cost`, and `is_reachable`, each defaulting to `NO_RECOVERABLE` (import it from `prerequisite_graph`) and forwarding it to every `prerequisites(...)` call. In `actionable_step`, the inner `_step` closure captures `recoverable`; pass it to the `prerequisites` call at `:74`.

- [ ] **Step 4: Run the tests**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/ai/tiers/ -v
```
Expected: PASS, and **every pre-existing tier test still passes untouched** (the default is empty, so the change is inert).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py src/artifactsmmo_cli/ai/tiers/strategy.py tests/ai/tiers/
git commit -m "feat(tiers): a recoverable material is a LEAF, not a recipe node

prerequisites() gains `recoverable` (material -> units obtainable by recycling
licensed surplus). A material with ANY recoverable units is directly actionable, so
the descent stops instead of re-deriving it from raw resources.

Live: ObtainItem(ash_plank) descended to ObtainItem(ash_wood, 10) and the bot
chopped 50 ash_wood at 1/cycle while holding 7 fishing_net, whose recipe IS 6
ash_plank each.

is_reachable is threaded too — a descent that leafs a node while reachability still
descends its recipe would disagree with itself about the same node.

INERT: the default is an empty MappingProxyType, so every existing caller is
byte-identical. Task 6 wires the real map in."
```

---

## Task 5: Edge 2 — the goal admits recycles and the withdraws that feed them

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/gathering.py:165-265`
- Test: `tests/ai/goals/test_gathering.py`

**Interfaces:**
- Consumes: the licensed pool (already filtered by `license_destructive_actions`).
- Produces: `GatherMaterialsGoal.relevant_actions` now admits `RecycleAction(c)` when `recipe(c)` intersects the goal's needed closure, plus `WithdrawItemAction(c)` for those same SOURCE codes.

**Why the withdraw matters.** `withdrawable` is built from the needed closure, and the recycle SOURCE is *upstream* of it — `fishing_net` is not in the `ash_plank` closure. Without this, a bank-only source is admitted as a recycle but the withdraw that feeds it is not, and the chain is unplannable.

**Safety is structural:** the pool arriving here has ALREADY been filtered by `license_destructive_actions` at `StrategyArbiter.select`. Admission cannot leak an unlicensed recycle — it can only fail to admit a licensed one, which is the present bug.

- [ ] **Step 1: Write the failing tests**

```python
def test_gather_goal_admits_a_licensed_recycle_source(state, game_data):
    """GatherMaterials(ash_plank) must see Recycle(fishing_net): its recipe IS
    ash_plank. Today the goal admits 0 RecycleActions and the planner re-filters
    at planner.py:124, so even an injected one is discarded."""
    goal = GatherMaterialsGoal(target_item="ash_plank", needed={"ash_plank": 5})
    pool = [RecycleAction(code="fishing_net", quantity=1, workshop_location=(2, 1))]
    kept = goal.relevant_actions(pool, state, game_data)
    assert [a.code for a in kept if isinstance(a, RecycleAction)] == ["fishing_net"]


def test_gather_goal_admits_the_withdraw_that_feeds_the_recycle(state, game_data):
    """The recycle SOURCE is upstream of the material closure, so the closure-built
    `withdrawable` set misses it. Without this the bank->recycle chain is unplannable."""
    goal = GatherMaterialsGoal(target_item="ash_plank", needed={"ash_plank": 5})
    pool = [WithdrawItemAction(code="fishing_net", quantity=1)]
    kept = goal.relevant_actions(pool, state, game_data)
    assert [a.code for a in kept if isinstance(a, WithdrawItemAction)] == ["fishing_net"]


def test_gather_goal_ignores_an_unrelated_recycle(state, game_data):
    """copper_axe recycles to copper_bar, which is not in the ash_plank closure."""
    goal = GatherMaterialsGoal(target_item="ash_plank", needed={"ash_plank": 5})
    pool = [RecycleAction(code="copper_axe", quantity=1, workshop_location=(2, 1))]
    assert [a for a in goal.relevant_actions(pool, state, game_data)
            if isinstance(a, RecycleAction)] == []


def test_recycle_beats_gathering_on_cost(state, game_data):
    """The payoff: Recycle costs 7.00 and yields 3 ash_plank; GatherAction costs
    25.00 and yields 1 ash_wood, of which 10 make ONE plank."""
    goal = GatherMaterialsGoal(target_item="ash_plank", needed={"ash_plank": 5})
    pool = licensed_pool(state, game_data)   # includes Recycle(fishing_net)
    plan = GOAPPlanner().plan(state, goal, goal.relevant_actions(pool, state, game_data),
                              game_data, budget_seconds=30.0)
    assert any(isinstance(a, RecycleAction) for a in plan)
    assert sum(isinstance(a, GatherAction) for a in plan) < 10
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/ai/goals/test_gathering.py -v
```
Expected: FAIL — no `RecycleAction` survives `relevant_actions`.

- [ ] **Step 3: Implement**

In `gathering.py`, import `RecycleAction` at the top. After the `chain` closure-demand loop (which already computes the full material closure and feeds `withdrawable`), add:

```python
        # Recycle-as-acquisition: a licensed RecycleAction whose recipe yields a
        # closure material is a SOURCE for that material, not merely disposal.
        # Live 2026-07-13: the bot chopped 50 ash_wood at 1/cycle to craft 5
        # ash_plank while holding 7 fishing_net — whose recipe IS 6 ash_plank each.
        # Recycle costs 7.00 and returns 3 planks; a gather costs 25.00 and returns
        # ONE ash_wood, of which TEN make one plank.
        #
        # Safety is structural, not conventional: this pool has ALREADY been filtered
        # by `license_destructive_actions` at StrategyArbiter.select, so the recycles
        # visible here are exactly the ones the keep authority permits (and each
        # carries its `bag_floor`, so the working tool is unreachable). Admission can
        # only fail to admit a licensed recycle — it cannot invent an unlicensed one.
        closure_materials = set(chain) | set(self._needed)
        recycle_sources: set[str] = set()
        for action in actions:
            if not isinstance(action, RecycleAction):
                continue
            source_recipe = game_data.crafting_recipe(action.code) or {}
            if set(source_recipe) & closure_materials:
                recycle_sources.add(action.code)
        # The SOURCE is UPSTREAM of the closure (fishing_net is not in the ash_plank
        # closure), so the closure-built `withdrawable` set misses it. Without this a
        # bank-only source is admitted as a recycle whose feeding withdraw is not, and
        # the Withdraw -> Recycle chain — the MAIN path, since DEPOSIT_FULL banks the
        # surplus — is unplannable.
        withdrawable |= recycle_sources
```

Then include recycle sources in the goal's action filter, alongside the existing gather/craft/withdraw/deposit admission:

```python
            if isinstance(action, RecycleAction) and action.code in recycle_sources:
                relevant.append(action)
                continue
```

(Match the surrounding filter loop's existing structure and variable names.)

- [ ] **Step 4: Run the tests**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/ai/goals/test_gathering.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/gathering.py tests/ai/goals/test_gathering.py
git commit -m "feat(gather): admit licensed recycles as material SOURCES

GatherMaterialsGoal never admitted RecycleAction, and the planner re-filters at
planner.py:124 — so even a licensed recycle injected into the pool was discarded,
and the goal could only ever gather.

Also admits the WITHDRAW that feeds each source: the source is UPSTREAM of the
material closure (fishing_net is not in the ash_plank closure), so the
closure-built withdrawable set missed it and Withdraw -> Recycle was unplannable.

Safety is structural: the pool is already licence-filtered at
StrategyArbiter.select, so admission cannot invent an unlicensed recycle."
```

---

## Task 6: Plumbing — wire the map in (THE ACTIVATION)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (compute at the ctx seam; pass to `decide` and `_execute_level_skill`)
- Modify: `src/artifactsmmo_cli/ai/tiers/progression_tree.py:184` (`decide_tree`) and its three `actionable_step` calls (`:129,150,228`)
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py` (`StrategyEngine.decide` → `decide_tree`)
- Modify: `src/artifactsmmo_cli/ai/level_skill_expand.py:19-61` (`next_grind_goal`)
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py:431` (`_gather_fallback_goal` — already has `ctx`)
- Modify: `src/artifactsmmo_cli/ai/plan_tree.py:45` (display-only — passes the map through for an honest tree)
- Test: `tests/ai/test_level_skill_expand.py`, `tests/ai/test_player.py`

**Interfaces:**
- Consumes: `recoverable_materials(state, game_data, ctx) -> dict[str, int]` (Task 1); the threaded tier signatures (Task 4).
- Produces: `next_grind_goal(skill, state, game_data, recoverable=NO_RECOVERABLE)`; `decide_tree(..., recoverable=NO_RECOVERABLE)`.

**This is the task that makes the epic live.** Everything before it is inert.

Follow `decide_tree`'s established pattern for caller-supplied verdicts (`band_adequate`: *"the player wires the real progression-band verdict in; it defaults to False"*). `recoverable` defaults to `NO_RECOVERABLE` and the player wires the real map in.

- [ ] **Step 1: Write the failing test**

```python
def test_next_grind_goal_targets_the_recoverable_material(state, game_data):
    """THE BUG, end to end. weaponcrafting rung fire_staff needs 5 ash_plank.
    Bag holds 7 fishing_net (recipe: 6 ash_plank each). Without recoverable the
    grind goal is GatherMaterials(ash_wood, 10) -> 50 gathers of WOODCUTTING xp."""
    assert next_grind_goal("weaponcrafting", state, game_data)._needed \
        == {"ash_wood": 10}

    recoverable = {"ash_plank": 18}
    goal = next_grind_goal("weaponcrafting", state, game_data, recoverable)
    assert goal._needed == {"ash_plank": 5}


def test_player_wires_the_real_recoverable_map(player):
    """The map must reach the descent from the ctx seam, or all of the above is
    inert in production (feedback_verify_runtime_activation)."""
    player.plan_once()
    assert player._last_recoverable  # non-empty: Robby holds recyclable surplus
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/ai/test_level_skill_expand.py -v
```
Expected: FAIL — `next_grind_goal() takes 3 positional arguments but 4 were given`

- [ ] **Step 3: Implement**

`level_skill_expand.next_grind_goal` gains `recoverable: Mapping[str, int] = NO_RECOVERABLE` and forwards it to its `actionable_step` call:

```python
        step = actionable_step(ObtainItem(rung), state, game_data, recoverable)
```

`progression_tree.decide_tree` gains `recoverable: Mapping[str, int] = NO_RECOVERABLE` and forwards it to all three `strategy.actionable_step` calls (`:129`, `:150`, `:228`) and to any `root_cost` / `unmet_closure_size` calls it makes. `StrategyEngine.decide` gains the same parameter and forwards to `decide_tree`.

`player`: compute ONCE per cycle where the ctx already exists (`_selection_context`), store it, and pass it to `decide` and to `_execute_level_skill`'s `next_grind_goal`:

```python
        ctx = self._selection_context(combat_monster)
        self._last_recoverable = recoverable_materials(self.state, self.game_data, ctx)
        decision = self._strategy.decide(
            ..., recoverable=self._last_recoverable,
        )
```

`strategy_driver._gather_fallback_goal` already has `ctx` in scope at its call site — compute or accept `recoverable` there and forward it to its `actionable_step(ObtainItem(code=code, quantity=1), state, game_data)` call.

`plan_tree.build_tree` accepts `recoverable: Mapping[str, int] = NO_RECOVERABLE` and forwards it to `prerequisites` so the TUI tree shows the same descent the planner takes.

- [ ] **Step 4: Run the two-lane suite**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest -n auto tests/ --ignore=tests/scenarios
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/scenarios --cov-append
```
Expected: PASS, 100% coverage, 0 skipped.

**Watch specifically for scenario regressions.** The leaf rule is `recoverable > 0`, so GOAP can now inherit a partially-deep subtree — the shape that hit the 1M-node cap in `3166d390`. If `test_slot_scenario_search_is_bounded` or any wall-clock planner test regresses, that is the node-explosion risk materializing: route the leafed goal through `strategy_driver`'s existing `gather_step_target` flat-batch bound (which exists for exactly this) rather than weakening the leaf rule.

- [ ] **Step 5: Commit**

```bash
git add -A src/ tests/
git commit -m "feat(recycle): wire recoverable into the descent — THE ACTIVATION

player computes recoverable_materials once per cycle at the ctx seam and threads
it through decide -> decide_tree -> actionable_step -> prerequisites, plus
next_grind_goal and the gather fallback. plan_tree forwards it so the TUI shows the
descent the planner actually takes.

Everything before this commit was inert. Follows decide_tree's established pattern
for caller-supplied verdicts (band_adequate: 'the player wires the real verdict in')."
```

---

## Task 7: Lean — mirror the leaf rule and the yield

**Files:**
- Modify: `formal/Formal/PrerequisiteGraph.lean:57-102`
- Modify: `formal/Oracle.lean:562-583` (`runPrerequisiteGraph`)
- Modify: `formal/diff/test_prerequisite_graph_diff.py`
- Modify: `formal/mutate.py` (anchors)

**Interfaces:**
- Produces: `prereqEdges (recoverable : Bool) (recipe : Option (List (Nat × Nat))) : List Edge`; `recoverableYield (copies qty : Nat) : Nat`.

**`StrategyTraversal.lean` is UNCHANGED and must stay so.** Its `Graph` is abstract over `prereqs : Nat → List Nat`, so `actStep` and every reachability/soundness theorem are already parametric over the prereq function. Changing what `prerequisites` returns changes the Graph INSTANCE, not the traversal. If you find yourself editing `StrategyTraversal.lean`, stop — you have taken a wrong turn.

- [ ] **Step 1: Extend the Lean core**

```lean
/-- `prereqEdges recoverable recipe`: the direct prerequisite edges of an
UNSATISFIED `ObtainItem code`. A material RECOVERABLE by recycling licensed
surplus is a LEAF — directly actionable — so no recipe descent happens. Otherwise
one `Edge.item` per ingredient when craftable, else a leaf. -/
def prereqEdges (recoverable : Bool) (recipe : Option (List (Nat × Nat))) : List Edge :=
  if recoverable then [] else
    match recipe with
    | some ingredients => ingredients.map (fun p => Edge.item p.1 p.2)
    | none => []

/-- `recoverableYield copies qty`: units of an ingredient recovered by applying
`copies` UNIT recycles, each returning `max 1 (qty / 2)` (`RecycleAction.apply`
with quantity=1, which is what `actions/factory` emits). NOT the batch form
`max 1 (qty * copies / 2)` — they differ at `qty = 1`. -/
def recoverableYield (copies qty : Nat) : Nat :=
  copies * max 1 (qty / 2)

/-- `prereqs_recoverable_leaf`: a recoverable material has NO prerequisites,
whatever its recipe. This is the epic's core claim. -/
theorem prereqs_recoverable_leaf (r : Option (List (Nat × Nat))) :
    prereqEdges true r = ([] : List Edge) := by
  rfl

/-- `recoverable_yield_unit_ge_batch`: repeated UNIT recycles never recover LESS
than the batch expression — pinning that the unit form is the correct (and not
merely different) predictor of what the executor achieves. -/
theorem recoverable_yield_unit_ge_batch (copies qty : Nat) :
    max 1 (qty * copies / 2) ≤ recoverableYield copies qty ∨ copies = 0 := by
  sorry  -- REPLACE: prove it. A `sorry` FAILS gate part a''.
```

Restate the three existing theorems under `recoverable = false` (behavior-preserving):
`prereqs_recipe (ingredients) : prereqEdges false (some ingredients) = ...`,
`prereqs_leaf : prereqEdges false none = []`,
`prereqs_membership (ingredients) (e) : e ∈ prereqEdges false (some ingredients) ↔ ...`.

**No `sorry` may survive** — gate part a″ fails on any. Discharge `recoverable_yield_unit_ge_batch` properly, or replace it with a theorem you can actually prove that still pins the unit-vs-batch distinction (e.g. the concrete witness `recoverableYield 4 1 = 4 ∧ max 1 (1 * 4 / 2) = 2`). Per `feedback_zero_vacuousness`, do not ship a vacuous theorem.

- [ ] **Step 2: Update the Oracle entry**

`runPrerequisiteGraph` (`formal/Oracle.lean:574`) must read a `recoverable : Bool` argument and pass it to `prereqEdges`.

- [ ] **Step 3: Extend the differential**

In `formal/diff/test_prerequisite_graph_diff.py`, randomize a `recoverable` flag per trial alongside the recipe table, pass the corresponding `{code: n}` map into the real Python `prerequisites`, and compare against the oracle over ≥200 random tables. Cover BOTH branches (recoverable true and false).

Run it — `formal/diff/` is **NOT** in the default pytest path:

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest formal/diff/test_prerequisite_graph_diff.py -v
```
Expected: PASS.

- [ ] **Step 4: Regenerate extraction and refresh anchors**

Gate part b‴ (extraction drift) fires whenever a mirrored core changes:

```bash
/home/blentz/.local/bin/uv run python scripts/extract_lean.py
grep -n "prerequisite_graph\|recoverable" formal/mutate.py
```
Refresh the `mutate.py` anchors for every edited line.

- [ ] **Step 5: Commit**

```bash
git add formal/ src/
git commit -m "feat(formal): mirror the recoverable leaf rule and the unit-recycle yield

prereqEdges gains the recoverable flag + prereqs_recoverable_leaf; the three
existing theorems are restated under recoverable=false (behavior-preserving).
recoverableYield pins the repeated-UNIT-recycle arithmetic that must not drift
from RecycleAction.apply.

StrategyTraversal is UNCHANGED: its Graph is abstract over `prereqs`, so actStep
and every reachability theorem are already parametric over the prereq function.
Changing what prerequisites returns changes the Graph INSTANCE, not the traversal."
```

---

## Task 8: The recycle-source behavioral census

**Files:**
- Create: `src/artifactsmmo_cli/audit/recycle_source_completeness.py`
- Create: `scripts/gen_recycle_source_completeness.py`
- Modify: `.github/workflows/census-gate.yml`
- Test: `tests/audit/test_recycle_source_completeness.py`

**Interfaces:**
- Consumes: the real `StrategyArbiter` (per the census contract — a census that does not drive production's own selector proves nothing).
- Produces: `--check` exits non-zero when any cell is `RECYCLE_SOURCE_BUG`.

Model on `audit/inventory_completeness.py` (structure, `classify_gap` discipline) but with an ACQUISITION verdict: *did the plan contain `Recycle(source)`?*

**The four cells:**

| Cell | Setup | Verdict |
|---|---|---|
| **LIVENESS** | goal needs `m`; bag holds surplus `S`, `m ∈ recipe(S)`, `destroyable(S) > 0` | plan MUST contain `Recycle(S)` |
| **SAFETY** | only PROTECTED copies of `S` (`destroyable(S) == 0` — the last `copper_axe`, WORKING_KIT) | plan MUST NOT contain `Recycle(S)`; must gather instead |
| **BANKED** | `S` in bank only, bag empty | plan MUST contain `Withdraw(S)` THEN `Recycle(S)` |
| **PARTIAL** | `recoverable[m] < needed[m]`, at recipe depth ≥ 2 | a mixed recycle+gather plan MUST resolve WITHIN BUDGET |

**Two rules carried over from the keep epic — both were paid for in blood:**

1. **A planner timeout is a BUG, never an explained gap.** `classify_gap` takes `planner_failed` as a REQUIRED argument and returns `RECYCLE_SOURCE_BUG` before any other arm. In the keep census a gap class silently ABSORBED a 49,569-node planner timeout, producing a green grid that was lying. The PARTIAL cell is precisely where the node-explosion risk of the `recoverable > 0` leaf rule would show up — if it can be swallowed, the census is worthless.
2. **The SAFETY cell is the one that matters most.** It is what stops this epic from becoming a tool-melting bug: it proves the last `copper_axe` is never dismantled for parts.

- [ ] **Step 1: Write the failing census test**

```python
def test_liveness_cell_plans_a_recycle(game_data):
    cell = build_cell(kind="liveness", source="fishing_net", material="ash_plank")
    plan = plan_cell(cell, game_data)
    assert any(isinstance(a, RecycleAction) and a.code == "fishing_net" for a in plan)


def test_safety_cell_never_recycles_the_working_tool(game_data):
    """1 copper_axe owned, and it is the WORKING_KIT tool. It must be gathered
    around, never dismantled."""
    cell = build_cell(kind="safety", source="copper_axe", material="copper_bar")
    plan = plan_cell(cell, game_data)
    assert not any(isinstance(a, RecycleAction) and a.code == "copper_axe" for a in plan)


def test_banked_cell_withdraws_then_recycles(game_data):
    cell = build_cell(kind="banked", source="fishing_net", material="ash_plank")
    plan = plan_cell(cell, game_data)
    kinds = [type(a).__name__ for a in plan]
    assert kinds.index("WithdrawItemAction") < kinds.index("RecycleAction")


def test_partial_cell_resolves_within_budget(game_data):
    """The node-explosion guard. recoverable < needed at depth >= 2 forces GOAP to
    mix recycle with a from-scratch gather chain — the 1M-node shape of 3166d390."""
    cell = build_cell(kind="partial", source="fishing_net", material="ash_plank")
    plan, planner_failed = plan_cell_timed(cell, game_data)
    assert planner_failed is False
    assert plan


def test_planner_timeout_is_a_bug_never_an_explained_gap(game_data):
    """A gap class that can swallow a planner bug destroys the census's value."""
    cell = build_cell(kind="partial", source="fishing_net", material="ash_plank")
    assert classify_gap(cell, state, game_data, planner_failed=True) \
        is RecycleSourceGapClass.RECYCLE_SOURCE_BUG
```

- [ ] **Step 2: Run to verify failure**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/audit/test_recycle_source_completeness.py -v
```
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the census + the `--check` script**

Build `audit/recycle_source_completeness.py` with the cell dataclass, the grid, `plan_cell` (driving the REAL `StrategyArbiter`, exactly as `inventory_completeness` does), the verdict, and `classify_gap(cell, state, game_data, planner_failed)` returning `RECYCLE_SOURCE_BUG` as the FALL-THROUGH — never a positive match — and unconditionally when `planner_failed`.

`scripts/gen_recycle_source_completeness.py` mirrors `gen_inventory_completeness.py`: writes the doc, and with `--check` exits non-zero when any cell is `recycle_source_bug`.

- [ ] **Step 4: Run the census to zero**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/audit/test_recycle_source_completeness.py -v
/home/blentz/.local/bin/uv run python scripts/gen_recycle_source_completeness.py --check
```
Expected: PASS; `recycle_source_bug 0`.

- [ ] **Step 5: Wire CI and commit**

Add to `.github/workflows/census-gate.yml`, alongside the other two:

```yaml
      - name: recycle-source census — recycle_source_bug == 0
        run: uv run python scripts/gen_recycle_source_completeness.py --check
```

```bash
git add src/artifactsmmo_cli/audit/recycle_source_completeness.py scripts/gen_recycle_source_completeness.py .github/workflows/census-gate.yml tests/audit/
git commit -m "test(census): recycle-as-source behavioral completeness — LIVENESS/SAFETY/BANKED/PARTIAL

Drives the REAL StrategyArbiter. The SAFETY cell is what keeps this epic from
becoming a tool-melting bug: it proves the last copper_axe is never dismantled for
parts. The PARTIAL cell is where the `recoverable > 0` leaf rule's node-explosion
risk would surface, so a planner TIMEOUT classifies as RECYCLE_SOURCE_BUG
unconditionally and before every other arm — a gap class that can swallow a planner
bug destroys the census's entire value."
```

---

## Task 9: Full gate + runtime verification on Robby

**Files:** none (verification only)

Green tests are NOT done. Per `feedback_verify_runtime_activation`: a planner/cost/goal change must FIRE on the live bot or it is inert.

- [ ] **Step 1: Two-lane suite, clean**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest -n auto tests/ --ignore=tests/scenarios
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/scenarios --cov-append
```
Expected: 0 errors, 0 warnings, 0 skipped, 100% coverage.

- [ ] **Step 2: Differential**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest formal/diff/ -v
```
Expected: PASS.

- [ ] **Step 3: Full formal gate (needs a CLEAN COMMITTED TREE)**

```bash
git status --porcelain      # MUST be empty
cd formal && ./gate.sh
```
Expected: ALL PARTS PASS — kernel build, orphan modules, no-sorry, axiom lint, role manifest, proof-concept index, extraction drift, differential, mutation.

**Serialize this** (`feedback_serialize_gate_runs`): never run `gate.sh` concurrently with anything importing `src`, INCLUDING the live bot.

- [ ] **Step 4: Both censuses**

```bash
/home/blentz/.local/bin/uv run python scripts/gen_inventory_completeness.py --check
/home/blentz/.local/bin/uv run python scripts/gen_craft_completeness.py --check
/home/blentz/.local/bin/uv run python scripts/gen_recycle_source_completeness.py --check
```
Expected: `inventory_bug 0`, `planner_bug 0`, `recycle_source_bug 0`.

- [ ] **Step 5: RUNTIME verification — the acceptance bar**

```bash
/home/blentz/.local/bin/uv run artifactsmmo plan Robby
```

**Done means all three:**
1. The `LevelSkill(weaponcrafting)` grind's first leg is `Recycle(fishing_net)` (or `Withdraw(fishing_net) -> Recycle`), **NOT** `Gather(ash_tree)`.
2. `actionable_step(ObtainItem(fire_staff))` returns `ObtainItem(ash_plank, 5)`, not `ObtainItem(ash_wood, 10)`.
3. Weaponcrafting XP moves off **112** after a few live cycles.

If the plan still shows `Gather(ash_tree)`, the map is not reaching the descent — the change is inert in production and Task 6 is incomplete. Do not report success.

- [ ] **Step 6: Final commit**

```bash
git commit --allow-empty -m "chore(recycle): gate green, censuses at 0, runtime-verified on Robby

LevelSkill(weaponcrafting) now recycles the fishing_net hoard for ash_plank instead
of chopping 50 ash_wood at 1/cycle. The hoard was the fuel."
```

---

## Self-Review

**Spec coverage:**
- §2.1 `recoverable_materials` core → Task 1 (incl. §2.6 eligibility gates, and the unit-vs-batch yield)
- §2.2 Edge 1 (leaf rule) → Task 4
- §2.3 Edge 2 (goal pool) → Task 5
- §2.4(a) bank route → Task 3; §2.4(b) `bag_floor` → Task 2; §2.4(c) source withdraw → Task 5
- §2.5 plumbing → Task 6
- §3 Lean → Task 7
- §4 node-explosion risk → held by Task 6 Step 4 (scenario watch) + Task 8 PARTIAL cell
- §5 census + runtime verification → Tasks 8, 9
- §6 out of scope → no tasks, correctly
- §7 churn accepted → no guard, correctly

**Ordering rationale:** Tasks 1–5 are all INERT (defaults preserve today's behavior exactly). Task 6 is the single activation point, so a regression there is unambiguous. Tasks 2 and 3 land the safety guard BEFORE Task 5 admits recycles into a planning goal — the working tool is never reachable, not even for one commit.

**Type consistency:** `recoverable: Mapping[str, int]` and the `NO_RECOVERABLE` constant are used identically in Tasks 4, 5, 6, 7. `recoverable_materials(state, game_data, ctx) -> dict[str, int]` matches its consumer in Task 6. `RecycleAction.bag_floor: int` is defined in Task 2 and consumed in Tasks 3 and 5.
