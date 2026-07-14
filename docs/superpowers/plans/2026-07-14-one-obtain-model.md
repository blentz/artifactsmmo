# One Obtain-Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the two plan producers ONE shared model of how a material can be obtained, so a route added anywhere is seen by both — retiring the second obtain-model that made seven green commits inert.

**Architecture:** A new pure core `ai/obtain_sources` declares every way an item can be obtained (`GATHER / CRAFT / WITHDRAW / RECYCLE / BUY / DROP`). It is computed ONCE per plan call at the seam where `SelectionContext` exists, and passed into the pure recipe-descent core as a plain finite map — so the core stays pure and Lean-mirrorable. `next_craft_core._next` stops branching on `recipes.get(item) is None` and instead reads the source map. `craft_plan_gen`'s four hand-bolted routes (`_recycle_prefix`, `drop_fights`, the `LevelSkill` early-return, the NPC-buy decline) are DELETED — they become source kinds.

**Tech Stack:** Python 3.13, `uv`, pytest, Lean 4 (`formal/`), GOAP planner.

**Spec:** `docs/superpowers/specs/2026-07-14-one-obtain-model-design.md` (`1ab2bc8a`). It SUPERSEDES the macro spec (`70b4cee0`), whose design was disproved by measurement — do not retry it.

## Global Constraints

- **`uv` is at `/home/blentz/.local/bin/uv` and is NOT on PATH.** Always use the absolute path. Always prefix Python with `uv run`.
- Run pytest via `env -u FORCE_COLOR` — the shell exports `FORCE_COLOR=3`, which breaks ANSI tests.
- **RUN ONLY ONE HEAVY PROCESS AT A TIME.** Never start a background test/gate run and keep working. The wall-clock planner and scenario tests FLAKE under CPU contention, and that already produced one phantom failure in the previous epic. Run a command, WAIT for it, then continue.
- **The pre-commit hook runs the FULL suite (~6 min) and does NOT check coverage** (it passes `--no-cov`), though the repo gates at 100%. Check coverage yourself on every module you touch:
  `env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest <tests> --cov=<module> --cov-report=term-missing --cov-fail-under=0 -q`
- Allow a **12-minute** timeout on any `git commit`. Do NOT kill it.
- Tests live in `tests/test_ai/`. `formal/diff/` is **NOT** in the default pytest path — run it explicitly.
- The mutation config is **`formal/diff/mutate.py`** (NOT `formal/mutate.py`). Refresh the anchor for **every line you edit** — a stale anchor is a `(stale)` SURVIVOR and FAILS the gate.
- **NO inline imports.** **NEVER catch `Exception`.** **NO `if TYPE_CHECKING`.** ONE behavioral class per file.
- `ruff check src/ tests/` reports **177 PRE-EXISTING errors** on `main` in files unrelated to this epic. Do NOT fix them. Keep the files you touch clean.
- Use only API/game data or fail with an error — never default around missing data.
- The full formal gate (`cd formal && ./gate.sh`) needs a **CLEAN COMMITTED TREE**.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/artifactsmmo_cli/ai/obtain_sources.py` | **NEW.** `SourceKind`, `Source`, `obtain_sources()`, `obtain_source_map()`. THE model — the one place a route is declared. |
| `src/artifactsmmo_cli/ai/next_craft_core.py` | `NextAction.kind` widens to `SourceKind`; `_next` reads the source map instead of branching on `recipes.get(item) is None`. |
| `src/artifactsmmo_cli/ai/craft_plan_driver_core.py` | `_apply_state` gains the new kinds' effects; `craft_plan_full` threads the source map. |
| `formal/Formal/CraftPlanDriver.lean` | `Source` inductive; `craftPlan_steps_valid` / `craftPlan_reaches` **re-proved** over the widened model. |
| `src/artifactsmmo_cli/ai/craft_plan_gen.py` | DELETE `_recycle_prefix`, `_best_recycle`, `_staging_withdraw`, `_recovered_units`, `_goal_closure`, `_dropper_fight`/`drop_fights`, the `LevelSkill` early-return, the NPC-buy decline. Becomes a thin NextAction→Action mapper. |
| `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py`, `tiers/strategy.py`, `tiers/progression_tree.py`, `level_skill_expand.py`, `strategy_driver.py`, `plan_tree.py` | Consume `obtain_sources`; **DELETE the `recoverable` parameter thread** (it was a symptom of the missing model). |
| `src/artifactsmmo_cli/ai/goals/gathering.py` | `relevant_actions` admits the actions the sources name. |
| `src/artifactsmmo_cli/audit/obtain_parity_completeness.py` + `scripts/gen_obtain_parity.py` | **NEW.** The parity census — the gate that makes the divergence bug unshippable. |
| `.github/workflows/census-gate.yml` | Wire the fourth census. |

**Ordering rationale:** Tasks 1–3 build and prove the widened model while the old callers still pass a 3-kind map, so they land **behavior-identical**. Task 4 is the activation (the generator starts using the new kinds). Tasks 5–6 collapse the remaining consumers. Task 7 makes divergence impossible to ship again. Task 8 verifies.

---

## Task 1: `obtain_sources` — the one model

**Files:**
- Create: `src/artifactsmmo_cli/ai/obtain_sources.py`
- Test: `tests/test_ai/test_obtain_sources.py`

**Interfaces:**
- Consumes: `inventory_keep.destroyable(code, state, game_data, ctx) -> int`; `game_data.crafting_recipe / item_stats / workshop_location / gatherable_drop_items / npc_purchases / is_event_npc / npc_location`; `ai/combat.is_winnable`.
- Produces:
```python
class SourceKind(Enum):
    WITHDRAW = "withdraw"
    RECYCLE  = "recycle"
    CRAFT    = "craft"
    GATHER   = "gather"
    BUY      = "buy"
    DROP     = "drop"

@dataclass(frozen=True)
class Source:
    kind: SourceKind
    code: str        # resource / recipe item / bank item / recycle SOURCE item / npc / monster
    yield_per: int   # units of the TARGET obtained per application

def obtain_sources(item, state, game_data, ctx) -> list[Source]
def obtain_source_map(items, state, game_data, ctx) -> dict[str, list[Source]]
```

**INERT — no consumers yet.** The parity census's oracle will BE this function, so it must be pinned by unit tests before anything depends on it (an oracle and its consumer written together are wrong together).

**THE PRIORITY ORDER IS A DECLARED POLICY, and it is the whole point of the file.** `obtain_sources` returns sources in this order, and the descent takes the first applicable one:

1. `WITHDRAW` — a copy is already in the bank. Consumes nothing new.
2. `RECYCLE` — a LICENSED surplus item's recipe yields it (`destroyable(src) > 0`). Turns dead stock into the material.
3. `CRAFT` — it has a recipe AND the crafting skill gate is met AND a workshop is known.
4. `GATHER` — some resource drops it.
5. `BUY` — a PERMANENT (non-event) NPC vendor sells it and its location is known.
6. `DROP` — a WINNABLE monster drops it.

Rationale (put this in the module docstring): **prefer sources that consume stock already owned over sources that create new work.** This generalises the rule the existing `_next` already hard-codes — it prefers a bank withdraw over descending into a recipe. `RECYCLE` sits with `WITHDRAW` because it also consumes stock already owned.

**ELIGIBILITY GATES — each source kind must be emitted ONLY when the executor can actually serve it.** A source the executor refuses is a leaf with no plan, which is the livelock shape of `3166d390`.
- `RECYCLE`: mirror `ai/recoverable_materials.recoverable_materials` EXACTLY — the source item must have a recipe, a known `crafting_skill`, the character must meet its `crafting_level`, its workshop must be known, **and it must be EQUIPPABLE** (`ITEM_TYPE_TO_SLOTS` — `RecycleAction`s are only ever CONSTRUCTED by `actions/factory.py` for equippables, so a non-equippable source has no action in existence). `yield_per = max(1, mat_qty // 2)` — the repeated **quantity=1** yield, NOT the batch form.
- `CRAFT`: skill gate met AND `workshop_location(skill)` is not None.
- `BUY`: a permanent vendor (`not is_event_npc(npc)` and `npc_location(npc) is not None`).
- `DROP`: `is_winnable` against the dropper.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_obtain_sources.py`. Mirror the fixture style of `tests/test_ai/test_recoverable_materials.py` (build a fake `GameData` + `SelectionContext` the same way) — do NOT invent a new fixture idiom.

```python
def test_priority_prefers_stock_already_owned(game_data, ctx):
    """WITHDRAW and RECYCLE outrank CRAFT/GATHER: they consume stock we already
    hold. This generalises the rule _next already hard-codes (bank before descend)."""
    # ash_plank: craftable (from ash_wood), banked x3, AND recoverable from
    # 7 surplus fishing_net (recipe {ash_plank: 6})
    state = make_state(inventory={"fishing_net": 7}, bank_items={"ash_plank": 3})
    kinds = [s.kind for s in obtain_sources("ash_plank", state, game_data, ctx)]
    assert kinds[0] is SourceKind.WITHDRAW
    assert kinds[1] is SourceKind.RECYCLE
    assert SourceKind.CRAFT in kinds


def test_recycle_source_names_the_SOURCE_item_not_the_target(game_data, ctx):
    """Source.code for a RECYCLE is the item to DESTROY, not the material gained —
    the mapper needs it to pick RecycleAction(fishing_net)."""
    state = make_state(inventory={"fishing_net": 7})
    rec = [s for s in obtain_sources("ash_plank", state, game_data, ctx)
           if s.kind is SourceKind.RECYCLE]
    assert [s.code for s in rec] == ["fishing_net"]
    assert rec[0].yield_per == max(1, 6 // 2)   # 3 — the UNIT-recycle yield, not batch


def test_protected_item_is_not_a_recycle_source(game_data, ctx):
    """The last copper_axe is WORKING_KIT: destroyable == 0. Never a source.
    This is the anti-tool-melting property."""
    state = make_state(inventory={"copper_axe": 1})
    assert not [s for s in obtain_sources("copper_bar", state, game_data, ctx)
                if s.kind is SourceKind.RECYCLE]


def test_non_equippable_is_not_a_recycle_source(game_data, ctx):
    """RecycleActions are only CONSTRUCTED for equippables (factory.py). A
    consumable/resource source has NO action in existence -> leaf with no plan."""
    state = make_state(inventory={"cooked_chicken": 9})   # craftable, NOT equippable
    assert not [s for s in obtain_sources("chicken", state, game_data, ctx)
                if s.kind is SourceKind.RECYCLE]


def test_under_skill_craft_is_not_a_source(game_data, ctx):
    """A craft whose skill gate is unmet cannot be served now."""
    state = make_state(skills={"weaponcrafting": 1})   # fire_staff needs 5
    assert not [s for s in obtain_sources("fire_staff", state, game_data, ctx)
                if s.kind is SourceKind.CRAFT]


def test_event_vendor_is_not_a_buy_source(game_data, ctx):
    """Event NPCs are not permanent; a BUY source must be reliably reachable."""
    state = make_state(gold=10_000)
    assert not [s for s in obtain_sources("event_only_item", state, game_data, ctx)
                if s.kind is SourceKind.BUY]


def test_unwinnable_dropper_is_not_a_drop_source(game_data, ctx):
    state = make_state(level=1)
    assert not [s for s in obtain_sources("boss_scale", state, game_data, ctx)
                if s.kind is SourceKind.DROP]


def test_raw_resource_has_exactly_one_gather_source(game_data, ctx):
    state = make_state()
    srcs = obtain_sources("ash_wood", state, game_data, ctx)
    assert [s.kind for s in srcs] == [SourceKind.GATHER]
    assert srcs[0].code == "ash_tree"


def test_source_map_covers_a_whole_closure(game_data, ctx):
    state = make_state()
    m = obtain_source_map(["ash_plank", "ash_wood"], state, game_data, ctx)
    assert set(m) == {"ash_plank", "ash_wood"}
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/test_obtain_sources.py -q --no-cov
```
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.obtain_sources'`

- [ ] **Step 3: Implement `src/artifactsmmo_cli/ai/obtain_sources.py`**

Module docstring must state: this is THE model of how an item can be obtained; **adding a seventh source is one edit here and every consumer gains it**; the priority order and its rationale; and that every kind's eligibility gate mirrors what the executor can actually serve (a source the executor refuses is a leaf with no plan). `SourceKind` and `Source` are pure data declarations and may share this module (the repo's one-class-per-file rule exempts cohesive enum/dataclass groups).

- [ ] **Step 4: Run the tests + coverage**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/test_obtain_sources.py -q --no-cov
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/test_obtain_sources.py --cov=artifactsmmo_cli.ai.obtain_sources --cov-report=term-missing --cov-fail-under=0 -q
```
Expected: all PASS; 100% on the new module.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/obtain_sources.py tests/test_ai/test_obtain_sources.py
git commit -m "feat(obtain): the ONE model of how an item can be obtained

Six sources (WITHDRAW/RECYCLE/CRAFT/GATHER/BUY/DROP) in one declared priority
order: prefer stock already owned over new work. Today the chain builder knows
THREE (next_craft_core.NextAction.kind) and every other route is hand-bolted into
craft_plan_gen — which is why recycle had to be taught twice and shipped inert.

Inert: no consumers yet. The parity census's oracle will BE this function, so it is
pinned by unit tests FIRST."
```

---

## Task 2: widen the pure recipe descent

**Files:**
- Modify: `src/artifactsmmo_cli/ai/next_craft_core.py` (`NextAction`, `next_craft_target_pure`, `_next`)
- Modify: `src/artifactsmmo_cli/ai/craft_plan_driver_core.py` (`_apply_state`, `craft_plan_full`)
- Test: `tests/test_ai/test_next_craft_core.py`, `tests/test_ai/test_craft_plan_driver_core.py`

**Interfaces:**
- Consumes: `SourceKind`, `Source` (Task 1).
- Produces:
```python
class NextAction(NamedTuple):
    item: str          # the TARGET item this step obtains
    kind: SourceKind
    qty: int
    code: str = ""     # the source's own code (resource / bank item / RECYCLE source / npc / monster).
                       # "" for CRAFT, where the source code IS `item`.

def next_craft_target_pure(sources, owned, bank, target, qty) -> NextAction | None
def craft_plan_full(sources, recipes, owned, bank, target, qty) -> list[NextAction]
```

`sources: Mapping[str, list[Source]]` — the finite map from Task 1's `obtain_source_map`. **Passing a plain finite map (not `SelectionContext`) is what keeps this core pure and Lean-mirrorable.**

**BEHAVIOUR-PRESERVING BY CONSTRUCTION:** when the map contains only `GATHER`/`CRAFT`/`WITHDRAW` sources, the descent must produce **byte-identical** plans to today. Every existing test in these two files must pass UNCHANGED. If you have to edit one, you have changed behaviour — stop and fix the code, not the test.

The `_next` rewrite replaces the hard-coded model:

```python
# BEFORE — the model, hard-coded:
recipe = recipes.get(item)
if recipe is None:
    return NextAction(item, "gather", deficit)
for inp, per in recipe.items():
    required = per * deficit
    if owned.get(inp, 0) < required:
        if bank.get(inp, 0) == 0:
            return _next(recipes, owned, bank, inp, required, fuel - 1)
        return NextAction(inp, "withdraw", min(bank.get(inp, 0), required - owned.get(inp, 0)))
return NextAction(item, "craft", deficit)

# AFTER — the model, read from the map (priority order is baked into the list):
for src in sources.get(item, ()):
    if src.kind is SourceKind.CRAFT:
        continue          # a craft needs its inputs first — handled below
    return _step_for(src, item, deficit, owned, bank)   # WITHDRAW/RECYCLE/GATHER/BUY/DROP
# CRAFT: descend into the first short input, exactly as before
```

Keep the `fuel` totality guard and its rationale comment.

`_apply_state` gains the new kinds' effects — and each must mirror its executor:
- `RECYCLE`: `owned[item] += qty`; **`owned[src.code] -= ceil(qty / src.yield_per)`** (the source items consumed). Mirrors `RecycleAction.apply`.
- `BUY`: `owned[item] += qty`; gold is NOT modelled here (the core has no gold) — the BUY source is only emitted when a permanent vendor exists; affordability is the action's `is_applicable`. Say so in a comment.
- `DROP`: `owned[item] += qty` (the same deliberate abstraction the existing Fight xp projection uses — see `feedback_combat_xp_projection_is_abstract`; do NOT "fix" it).

- [ ] **Step 1: Write the failing tests**

```python
def test_recycle_source_emits_a_recycle_step(sources):
    """8 ash_plank needed, 0 held; 7 fishing_net are a licensed RECYCLE source
    (yield 3 each). The descent must emit a RECYCLE step, not a GATHER of ash_wood.
    THIS IS THE BUG: today the recipe descent cannot express this at all."""
    na = next_craft_target_pure(sources, owned={}, bank={}, target="ash_plank", qty=8)
    assert na.kind is SourceKind.RECYCLE
    assert na.code == "fishing_net"


def test_recycle_consumes_the_source_items(sources):
    """_apply_state must debit the SOURCE item, or the plan double-spends it."""
    owned, bank = _apply_state(sources, RECIPES, {"fishing_net": 7}, {},
                               NextAction("ash_plank", SourceKind.RECYCLE, 6, "fishing_net"))
    assert owned["ash_plank"] == 6
    assert owned["fishing_net"] == 7 - 2      # ceil(6 / yield 3) == 2 nets consumed


def test_three_kind_map_is_byte_identical_to_today(sources_gather_craft_only):
    """The regression guard: with only GATHER/CRAFT/WITHDRAW sources, the widened
    descent must produce EXACTLY the plan the old recipe-driven descent produced."""
    plan = craft_plan_full(sources_gather_craft_only, RECIPES, {}, {}, "copper_bar", 6)
    assert [(s.item, s.kind, s.qty) for s in plan] == [
        ("copper_ore", SourceKind.GATHER, 60),
        ("copper_bar", SourceKind.CRAFT, 6),
    ]


def test_buy_source_emits_a_buy_step(sources_with_vendor):
    na = next_craft_target_pure(sources_with_vendor, {}, {}, "lifesteal_rune", 1)
    assert na.kind is SourceKind.BUY
```

- [ ] **Step 2: Run to verify they fail**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/test_next_craft_core.py tests/test_ai/test_craft_plan_driver_core.py -q --no-cov
```
Expected: FAIL — `TypeError: next_craft_target_pure() got an unexpected keyword argument 'sources'`

- [ ] **Step 3: Implement the widened cores** (per the code sketch above)

- [ ] **Step 4: Run BOTH test files + coverage; every pre-existing test must pass UNCHANGED**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/test_next_craft_core.py tests/test_ai/test_craft_plan_driver_core.py -q --no-cov
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/test_next_craft_core.py tests/test_ai/test_craft_plan_driver_core.py --cov=artifactsmmo_cli.ai.next_craft_core --cov=artifactsmmo_cli.ai.craft_plan_driver_core --cov-report=term-missing --cov-fail-under=0 -q
```

- [ ] **Step 5: Refresh mutation anchors and commit**

```bash
grep -n "next_craft\|craft_plan_driver" formal/diff/mutate.py
git add src/artifactsmmo_cli/ai/next_craft_core.py src/artifactsmmo_cli/ai/craft_plan_driver_core.py tests/test_ai/ formal/diff/mutate.py
git commit -m "feat(obtain): the recipe descent walks the SOURCE MODEL, not the recipe tree

NextAction.kind was Literal['gather','craft','withdraw'] — three sources — so no
route that is not a recipe edge could ever enter the chain, whatever the action pool
held. It now reads obtain_sources' finite map (six kinds), passed in as a plain
Mapping so the core stays pure and Lean-mirrorable.

Behaviour-preserving: with a 3-kind map the descent is byte-identical, and every
pre-existing test passes unchanged."
```

---

## Task 3: Lean — re-prove the driver over the widened model

**Files:**
- Modify: `formal/Formal/CraftPlanDriver.lean`
- Modify: `formal/Oracle.lean` (the craft-plan entry)
- Modify: `formal/diff/test_craft_plan_driver_diff.py` (find the real filename with `ls formal/diff/ | grep -i craft`)
- Modify: `formal/diff/mutate.py`

`CraftPlanDriver.lean` proves `craftPlan_steps_valid` (no fabricated steps), `craftPlan_reaches` (a complete plan reaches the target), `craftPlan_head`, `craftPlan_nil_iff` over the 3-kind model.

**These must be RE-PROVED over the widened source set — not weakened, not restricted back to three kinds.** The existing `withdraw` arm of `nextHelper` is the template: it is already a non-recipe source, so the shape of a `RECYCLE`/`BUY`/`DROP` arm follows it.

```lean
inductive Source where
  | withdraw (code : Nat) | recycle (code yieldPer : Nat) | craft
  | gather (code : Nat)   | buy (code : Nat)              | drop (code : Nat)
deriving DecidableEq, Repr
```

`applyState` gains each kind's effect. The RECYCLE arm must **debit the source item** by `⌈qty / yieldPer⌉` — the theorem `craftPlan_reaches` is what will catch it if you forget, because a plan that double-spends its recycle source does not reach the target.

**ZERO `sorry`** — gate part a″ fails on any. **NO VACUOUS THEOREMS** (`feedback_zero_vacuousness`): every hypothesis must be satisfiable. If a theorem will not go through, state a weaker one that is still load-bearing and SAY SO in your report — do not weaken it silently.

- [ ] **Step 1: Extend the Lean model + re-prove**
- [ ] **Step 2: Update the Oracle entry**
- [ ] **Step 3: Extend the differential — randomise over ALL SIX kinds and assert every kind is exercised** (a differential that only ever sees three kinds agrees vacuously)

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest formal/diff/ -q --no-cov -k craft
```

- [ ] **Step 4: Regenerate extraction (gate part b‴ fires on any mirrored-core change) and refresh anchors**

```bash
/home/blentz/.local/bin/uv run python scripts/extract_lean.py
grep -n "craft_plan\|next_craft" formal/diff/mutate.py
```

- [ ] **Step 5: `cd formal && lake build`, then commit**

```bash
git add formal/ src/
git commit -m "feat(formal): re-prove the craft-plan driver over the six-source model

craftPlan_steps_valid / craftPlan_reaches were proved over the 3-kind recipe model.
Re-proved over the widened source set — not weakened. The RECYCLE arm must debit its
source item; craftPlan_reaches is what catches a plan that double-spends it."
```

---

## Task 4: delete the generator's four bolt-ons (THE ACTIVATION)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/craft_plan_gen.py`
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` (build the source map once, at the seam that has `ctx`, and pass it in)
- Test: `tests/test_ai/test_craft_plan_gen.py` (find the real filename)

**DELETE:**
- `_recycle_prefix`, `_best_recycle`, `_staging_withdraw`, `_recovered_units`, `_goal_closure` — RECYCLE is a `SourceKind` now.
- `_dropper_fight` and the `drop_fights` map — DROP is a `SourceKind`.
- The `LevelSkill` early-`return [lvl]` — a skill-gated craft is simply not a CRAFT source until the gate is met; emit the `LevelSkill` leg through the same NextAction→Action mapping.
- The NPC-buy `return None` decline — BUY is a `SourceKind`.
- The `_finish` / `_with_rearm` **prefix special-casing**. (The recycle epic's final review found a real bug here: a recycle prefix made `mapped[0]` a Recycle, so the loadout re-arm silently skipped and plans opened bare-handed. With recycle as an ordinary step in the chain, there is no prefix and no special case — the bug becomes unrepresentable.)

**KEEP:** the O(closure) descent, the NextAction→concrete-action mapping, the truncate-at-DROP rule (a kill's drop yield is stochastic, so every simulated step after it assumes materials that may not arrive — this is a genuine non-determinism, not a missing model), and the first-leg applicability gate.

**The generator must build its legs from the goal's `relevant_actions` pool**, as it already does. That plus the shared model is what makes DRY structural.

- [ ] **Step 1: Write the failing test — the bug that started all this**

```python
def test_generator_recycles_instead_of_chopping(state_with_nets, game_data, pool, sources):
    """THE BUG. weaponcrafting rung fire_staff needs 5 ash_plank; the bag holds
    7 fishing_net (recipe: 6 ash_plank each). The generator planned Gather(ash_tree)
    — 50 gathers of WOODCUTTING xp — because its recipe descent could not express a
    recycle. It must now emit a Recycle leg from the SHARED model, with no
    _recycle_prefix in existence."""
    plan = generate_next_craft_action(goal, state_with_nets, game_data, pool, sources)
    assert any(isinstance(a, RecycleAction) for a in plan)
    assert not any(isinstance(a, GatherAction) and a.resource_code == "ash_tree" for a in plan)


def test_npc_buy_no_longer_declines_to_a_star(state, game_data, pool, sources):
    """A permanent-vendor leaf used to force `return None`. BUY is a source now."""
    plan = generate_next_craft_action(buy_goal, state, game_data, pool, sources)
    assert plan is not None
```

- [ ] **Step 2: Run to verify failure.** Expected: FAIL (extra `sources` arg / no Recycle leg).
- [ ] **Step 3: Delete the bolt-ons; thread the source map.**
- [ ] **Step 4: Run the generator tests, then the scenarios lane (ONE AT A TIME).**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/test_craft_plan_gen.py -q --no-cov
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/scenarios -q --no-cov
```
Expected: 141 passed. **A search-bound regression here means the generator started declining where it used to fire — report it, do NOT weaken the test.**

- [ ] **Step 5: Commit**

```bash
git add -A src/ tests/
git commit -m "feat(obtain): delete the generator's four bolt-on routes — THE ACTIVATION

_recycle_prefix, drop_fights, the LevelSkill early-return, and the NPC-buy decline
all existed because the recipe descent could not express those routes. It can now.
The _finish/_with_rearm prefix special-case dies with them, and with it the
final-review bug where a recycle prefix silently disarmed the loadout re-arm and
plans opened bare-handed."
```

---

## Task 5: collapse the tier descent onto the model — DELETE the `recoverable` thread

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py`, `tiers/strategy.py`, `tiers/progression_tree.py`, `level_skill_expand.py`, `strategy_driver.py`, `plan_tree.py`, `player.py`
- Delete: `src/artifactsmmo_cli/ai/recoverable_materials.py` and its tests (superseded by the RECYCLE arm of `obtain_sources`)

The recycle epic threaded `recoverable: Mapping[str,int] = NO_RECOVERABLE` through `prerequisites` / `actionable_step` / `unmet_closure_size` / `root_cost` / `is_reachable` / `decide_tree` / `next_grind_goal`. **That thread is a symptom of the missing model** — it is one bespoke map for one route. It is replaced by the source map, and `_producible(code)` becomes `bool(obtain_sources(code, ...))`.

- [ ] **Step 1: Write the failing test**

```python
def test_a_material_with_ANY_source_is_a_leaf(state, game_data, sources):
    """ash_plank is craftable, but recyclable from held nets -> directly actionable."""
    assert prerequisites(ObtainItem("ash_plank", 5), state, game_data, sources) == []


def test_producible_is_exactly_has_a_source(state, game_data, sources):
    assert _producible("ash_plank", state, game_data, sources) is True
    assert _producible("unobtainium", state, game_data, sources) is False
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Replace the `recoverable` parameter with `sources` throughout; delete `recoverable_materials.py`.**

**The mutation gate FORCES the deletion to be real:** once `recoverable_materials` is unreachable from production its anchors report as `(stale)` SURVIVORS and FAIL the gate. You cannot deprecate it; you must delete it (and its mutation entries).

- [ ] **Step 4: Full suite + scenarios (ONE AT A TIME).**
- [ ] **Step 5: Commit** — `git grep -n "recoverable" src/` must return nothing but incidental prose.

---

## Task 6: `relevant_actions` admits what the sources name

**Files:** `src/artifactsmmo_cli/ai/goals/gathering.py`, `tests/test_ai/test_gathering.py`

`GatherMaterialsGoal.relevant_actions` hand-builds its admission per route (gather/craft/withdraw, plus the recycle admission the last epic bolted on). It must instead admit the concrete actions the closure's **sources** name — so the pool and the descent cannot disagree about what is reachable.

Safety is unchanged and structural: the pool arriving here is ALREADY filtered by `license_destructive_actions` at `StrategyArbiter.select`, and each surviving `RecycleAction` carries its `bag_floor`/`owned_floor`. **Do NOT add a second protection rule here** — duplicate authority is forbidden.

- [ ] **Step 1: Failing test** — a licensed `Recycle(fishing_net)` and its feeding `Withdraw` are admitted for an `ash_plank` closure **because the source model names them**, not because of a bespoke rule.
- [ ] **Step 2–4:** implement, run `tests/test_ai/test_gathering.py` + scenarios, check coverage.
- [ ] **Step 5:** Commit.

---

## Task 7: the PARITY CENSUS — make divergence unshippable

**Files:**
- Create: `src/artifactsmmo_cli/audit/obtain_parity_completeness.py`, `scripts/gen_obtain_parity.py`, `tests/test_audit/test_obtain_parity.py`
- Modify: `.github/workflows/census-gate.yml` (a fourth census step)

**This is the gate that makes the seven-inert-commits bug impossible to ship again.** Model it on `src/artifactsmmo_cli/audit/recycle_source_completeness.py` and `inventory_completeness.py` — same structure, same discipline.

For a grid of (material, world-state) cells it asserts the two producers **agree about what is obtainable**:

| Check | Assertion |
|---|---|
| **POOL ⊆ MODEL** | if the GOAP pool can serve material `m` (some action in `relevant_actions` yields it), `obtain_sources(m)` must name a source for it |
| **MODEL ⊆ POOL** | if `obtain_sources(m)` names a source, the pool must contain a concrete action serving it |
| **PLAN PARITY** | for a goal both producers can serve, the descent's plan and A\*'s plan must use the SAME set of source KINDS |

**A disagreement is an `OBTAIN_PARITY_BUG`, never an explained gap.** `classify_gap` takes `planner_failed` as a REQUIRED argument and returns the BUG class for it BEFORE any other arm — per the keep epic, *a gap class that can swallow a planner bug destroys the census's entire value*.

**Prove the census is FALSIFIABLE** before trusting it: delete one source kind from `obtain_sources` and confirm a cell turns RED. Report how you verified it. (In the last epic a new census cell passed *without* the fix it was written to test, because it was built on the wrong item.)

Target: `obtain_parity_bug == 0`.

- [ ] **Steps 1–5:** failing tests → implement → drive to 0 → verify falsifiability → wire CI → commit.

---

## Task 8: full gate + runtime verification

**Files:** none (verification only). **Run each step ONE AT A TIME — nothing else running.**

- [ ] **Step 1: two-lane suite**

```bash
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest -n auto tests/ --ignore=tests/test_ai/scenarios
env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/scenarios --cov-append
```
Expected: 0 errors, 0 warnings, 0 skipped, 100% coverage; scenarios 141/141.

- [ ] **Step 2: differential** — `env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest formal/diff/ -q --no-cov`

- [ ] **Step 3: full formal gate (CLEAN COMMITTED TREE)**

```bash
git status --porcelain      # MUST be empty
cd formal && ./gate.sh
```
Expected: ALL GATE PARTS PASSED, `mutation gate OK`, 0 survivors, 0 stale anchors.

- [ ] **Step 4: ALL FOUR censuses**

```bash
/home/blentz/.local/bin/uv run python scripts/gen_inventory_completeness.py --check
/home/blentz/.local/bin/uv run python scripts/gen_craft_completeness.py --check
/home/blentz/.local/bin/uv run python scripts/gen_recycle_source_completeness.py --check
/home/blentz/.local/bin/uv run python scripts/gen_obtain_parity.py --check
```
Expected: `inventory_bug 0`, `planner_bug 0`, `recycle_source_bug 0`, `obtain_parity_bug 0`.
**The recycle census must be green with `_recycle_prefix` DELETED** — that is the proof recycle now flows from the shared model.

- [ ] **Step 5: no search regression**

Re-measure the two cases the generator serves at `nodes=0` today, from an EMPTY bag and bank: `copper_bar x6` and `copper_ring x2`. Both must still be served by the descent (not fall through to a capped A\* search).

- [ ] **Step 6: RUNTIME — on a state that REACHES the changed path**

```bash
/home/blentz/.local/bin/uv run artifactsmmo plan Robby
```

Per `feedback_two_plan_producers`: **a live check that does not exercise the changed path proves nothing.** The last epic's runtime proof passed only because Robby's bag happened to be slot-full, which made the generator defer to A\*. So verify BOTH:
1. **slot-full bag** — the grind plans a `Recycle(...)` leg, not `Gather(ash_tree)`;
2. **roomy bag** (the generator's fast path) — SAME result.

If the roomy-bag case still plans `Gather(ash_tree)`, the generator is not reading the shared model and the task is INCOMPLETE. Say so plainly.

- [ ] **Step 7: final commit**

---

## Self-Review

**Spec coverage:** §3.1 model → Task 1. §3.2 consumers → Tasks 2 (descent), 5 (tier), 6 (pool). §3.3 deletions → Task 4. §5 Lean → Task 3. §6.1 parity census → Task 7. §6.2–6 verification → Task 8. §6.6 (`recoverable` thread gone) → Task 5. §7 out-of-scope → no tasks, correctly.

**Ordering:** Tasks 1–3 land behaviour-identical (a 3-kind map reproduces today exactly). Task 4 is the single activation point, so a regression there is unambiguous. Task 5's deletion is FORCED real by the mutation gate.

**Type consistency:** `SourceKind` / `Source` / `obtain_sources` / `obtain_source_map` are used identically in Tasks 1, 2, 4, 5, 6, 7. `NextAction(item, kind: SourceKind, qty, code)` is defined in Task 2 and consumed in Tasks 3 and 4. `craft_plan_full(sources, recipes, owned, bank, target, qty)` is fixed in Task 2 and used in Task 4.

**Known risk carried:** Task 3 (re-proving two kernel theorems over six kinds) is the hardest task and the one most likely to come back BLOCKED. If it does, the fallback is NOT to weaken the theorems — it is to narrow the source set that enters the Lean model (e.g. prove over WITHDRAW/RECYCLE/CRAFT/GATHER and treat BUY/DROP as axiomatised leaves with a signed-off assumption), and to say so explicitly.
