# Fleet Food Role Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Food is made only when making it beats resting on fleet XP throughput, and only by the character holding the role that owns it; everyone else withdraws held food or rests.

**Architecture:** Four pricing/routing changes on existing seams. (1) the make price of a consumable credits the actions of skills the DAG demands; (2) `xp_demand` stops counting the fleet food shortfall and is computed before the loadout; (3) the chosen loadout carries `made_food`, the food its recovery eats when every unit is priced at replacement, and the stock target and fleet need read it; (4) `heal_prep_goal` produces only for the role owner (or when no one holds it); (5) role demand is weighted by the work (acquisition actions) per unit.

**Tech Stack:** Python 3.13, `uv`, pytest (+xdist), `formal/diff/mutate.py` mutation gate, `formal/gate.sh`.

**Spec:** `docs/superpowers/specs/2026-10-13-fleet-food-role-design.md`

## Global Constraints

- Prefix every Python command with `uv run`.
- No inline imports; imports at top of file. No `if TYPE_CHECKING`. Never catch `Exception`. No `...` relative imports.
- One behavioral class per file (the new modules here hold functions only).
- Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage (`formal/gate.sh`).
- Held food stays FREE (USER 2026-10-09 "free until used up" is kept); only PRODUCTION is priced.
- Useful XP only: skill XP counts when the skill is in `ctx.skill_demand`.
- Mutation anchors are refreshed in the SAME commit as the edit; run `uv run python formal/diff/mutate.py --check-anchors` before committing. Anchors must resolve to exactly one site.
- Partial test runs use `--no-cov` (the 100% coverage floor applies to the full suite only).
- Commit with the pre-commit hook (never `--no-verify`); it runs `tests/test_ai/` (~6 min).
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Single-character run** (no coordination store): `ctx.role` is None and `ctx.fleet_roles` empty — the character must still be allowed to make food. Pinned in Task 4.
2. **No fisher in the fleet** while food wins at replacement price: anyone may make food (the fleet must not starve). Pinned in Task 4.
3. **A food with no make route** (price None, only held stock): it is never in `made_food`, so its target is withdraw-only. Pinned in Task 3.
4. **An unpriceable demand item** (acquisition walk ≥ `UNOBTAINABLE_PER_UNIT`) must not recruit a role. Pinned in Task 5.
5. **Potions share `make_seconds`**: the useful-XP credit lowers a potion's make price when alchemy is demanded. That is intended (same rule); the potion loadout tests must stay green. Pinned by running `test_best_loadout.py` / `test_potion_supply*.py` in Task 1.

Residual (not fixed here, spec-conformant): when food wins at replacement price and no other role carries demand, several characters may still hold `fisher`; `supply_claims`' one-producer-per-item claim limits duplicate production. Watch it live (Task 6).

---

### Task 1: Credit demanded skills in the make price

**Files:**
- Create: `src/artifactsmmo_cli/ai/skill_credit.py`
- Modify: `src/artifactsmmo_cli/ai/acquisition_cost.py` (`acquisition_actions`, ~line 714)
- Modify: `src/artifactsmmo_cli/ai/consumable_price.py:45-50` (`make_seconds`)
- Test: `tests/test_ai/test_skill_credit.py` (create), `tests/test_ai/test_consumable_price.py`
- Modify: `formal/diff/mutate.py`

**Interfaces:**
- Produces: `skill_credit.route_skill(item: str, route: RouteOption, game_data: GameData) -> str | None`; `skill_credit.credit_demanded_skills(options: Mapping[str, list[RouteOption]], skills: frozenset[str], game_data: GameData) -> dict[str, list[RouteOption]]`; `acquisition_actions(..., *, policy=LEGACY, credit_skills: frozenset[str] = frozenset()) -> int`. `make_seconds` now passes `credit_skills=ctx.skill_demand`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_skill_credit.py`:

```python
"""Actions of a skill the DAG demands are not a cost of what they make
(docs/superpowers/specs/2026-10-13-fleet-food-role-design.md §2; USER
2026-10-13 "useful XP only")."""

import dataclasses
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.acquisition_cost_core import RouteOption
from artifactsmmo_cli.ai.consumable_price import make_seconds
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.obtain_sources import UNBOUNDED_CAPACITY
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.skill_credit import credit_demanded_skills, route_skill

_BUNDLE = (Path(__file__).resolve().parent / "scenarios" / "fixtures" / "gamedata_bundle.json")


def _gd(monkeypatch: pytest.MonkeyPatch) -> GameData:
    gd = GameData()
    gd._item_stats = {"cooked_fish": ItemStats(code="cooked_fish", level=1, type_="consumable",
                                               crafting_skill="cooking", crafting_level=1)}
    monkeypatch.setattr(gd, "resource_skill_level",
                        lambda code: ("fishing", 1) if code == "fish_spot" else None)
    return gd


GATHER = RouteOption(kind="gather", venue="fish_spot", actions_per_application=1, yield_per=1,
                     capacity=UNBOUNDED_CAPACITY)
WITHDRAW = RouteOption(kind="withdraw", venue="bank", actions_per_application=1, yield_per=1,
                       capacity=5)
CRAFT = RouteOption(kind="craft", venue="cooking", actions_per_application=1, yield_per=1,
                    capacity=UNBOUNDED_CAPACITY, inputs={"fish": 1})


def test_a_gather_trains_its_resource_skill_and_a_craft_its_item_skill(monkeypatch):
    gd = _gd(monkeypatch)
    assert route_skill("fish", GATHER, gd) == "fishing"
    assert route_skill("cooked_fish", CRAFT, gd) == "cooking"
    assert route_skill("fish", WITHDRAW, gd) is None
    assert route_skill("fish", dataclasses.replace(GATHER, venue="rock"), gd) is None


def test_only_the_demanded_skills_routes_are_free(monkeypatch):
    gd = _gd(monkeypatch)
    options = {"fish": [GATHER, WITHDRAW], "cooked_fish": [CRAFT]}
    credited = credit_demanded_skills(options, frozenset({"fishing"}), gd)
    assert [r.actions_per_application for r in credited["fish"]] == [0, 1]
    assert [r.actions_per_application for r in credited["cooked_fish"]] == [1]
    assert credit_demanded_skills(options, frozenset(), gd) == options


def test_the_make_price_drops_the_demanded_skills_actions():
    """cooked_gudgeon on the bundle: hop + gather + hop + cook = 4 actions.
    Fishing demanded frees the gather; fishing and cooking free both; the two
    hops always cost."""
    gd = load_bundle_game_data(_BUNDLE)
    state = scenario_state(ScenarioCharacter(name="hero", level=10,
                                             skills={"fishing": 10, "cooking": 10}), gd)

    def price(skills: frozenset[str]):  # type: ignore[no-untyped-def]
        return make_seconds("cooked_gudgeon", state, gd,
                            dataclasses.replace(NO_PROFILE_CONTEXT, skill_demand=skills), None)

    assert price(frozenset()) == 120
    assert price(frozenset({"fishing"})) == 90
    assert price(frozenset({"fishing", "cooking"})) == 60
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_skill_credit.py -q --no-cov -p no:cacheprovider`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.skill_credit'`.

- [ ] **Step 3: Implement**

Create `src/artifactsmmo_cli/ai/skill_credit.py`:

```python
"""`credit_demanded_skills`: the acquisition routes with every action that
trains a demanded skill made free
(docs/superpowers/specs/2026-10-13-fleet-food-role-design.md §2).

USER 2026-10-13, "useful XP only": seconds spent on a skill the goal-action DAG
still demands (`SelectionContext.skill_demand`) are spent levelling it anyway,
so they are not a cost of what they produce. A GATHER route trains its
resource's skill; a CRAFT route trains the item's crafting skill. Every other
route (withdraw, buy, drop, ...) trains none and keeps its price. Travel hops
are charged by the walk, not by a route, and always cost."""

from collections.abc import Mapping
from dataclasses import replace

from artifactsmmo_cli.ai.acquisition_cost_core import RouteOption
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.source_kind import SourceKind


def route_skill(item: str, route: RouteOption, game_data: GameData) -> str | None:
    """The skill one application of `route` (listed under `item`) trains, or None."""
    if route.kind == SourceKind.GATHER.value:
        requirement = game_data.resource_skill_level(route.venue)
        return requirement[0] if requirement is not None else None
    if route.kind == SourceKind.CRAFT.value:
        stats = game_data.item_stats(item)
        return stats.crafting_skill if stats is not None else None
    return None


def credit_demanded_skills(options: Mapping[str, list[RouteOption]], skills: frozenset[str],
                           game_data: GameData) -> dict[str, list[RouteOption]]:
    """`options` with every route that trains a skill in `skills` costing no actions."""
    return {item: [replace(route, actions_per_application=0)
                   if route_skill(item, route, game_data) in skills else route
                   for route in routes]
            for item, routes in options.items()}
```

In `src/artifactsmmo_cli/ai/acquisition_cost.py` add the import `from artifactsmmo_cli.ai.skill_credit import credit_demanded_skills` (alphabetical, after the `selection_context` import) and change `acquisition_actions`:

```python
def acquisition_actions(item: str, qty: int, state: WorldState,
                        game_data: GameData, ctx: SelectionContext,
                        equip: bool,
                        store: LearningStore | None = None,
                        gated_drop: bool = True, *, policy: Policy = LEGACY,
                        credit_skills: frozenset[str] = frozenset()) -> int:
```

Append to its docstring: `credit_skills` — routes training one of these skills cost no actions (`skill_credit`); empty by default, so every existing caller is unchanged. Replace the body's options line with:

```python
    owned: dict[str, int] = _owned_with_gold(state)
    options: Mapping[str, list[RouteOption]] = credit_demanded_skills(
        acquisition_options(item, state, game_data, ctx, store, gated_drop, policy=policy),
        credit_skills, game_data)
```

In `src/artifactsmmo_cli/ai/consumable_price.py`, `make_seconds`:

```python
    actions = acquisition_actions(code, 1, state, game_data, ctx, equip=False, store=store,
                                  credit_skills=ctx.skill_demand)
```

and add to the module doc's MAKE bullet: "Actions of a skill in `ctx.skill_demand` are credited (`skill_credit`, USER 2026-10-13 'useful XP only')."

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_skill_credit.py tests/test_ai/test_consumable_price.py tests/test_ai/test_best_loadout.py tests/test_ai/test_potion_supply.py tests/test_ai/test_potion_supply_integration.py tests/test_ai/test_acquisition_cost.py -q --no-cov -n auto -p no:cacheprovider`
Expected: all PASS. If `test_the_make_price_drops_the_demanded_skills_actions` reports other totals, print the three prices, confirm the hop/gather/cook decomposition by reading `acquisition_options("cooked_gudgeon", ...)`, and correct the expected numbers to what the walk proves — never weaken to `<`.

- [ ] **Step 5: Mutation entries**

In `formal/diff/mutate.py` add `SKILL_CREDIT_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "skill_credit.py"` next to `ACQUISITION_COST_SRC`, add `SKILL_CREDIT_SRC` to `_ALL_SRCS`, and add:

```python
SKILL_CREDIT_MUTATIONS = [
    ("skill credit: a gather trains nothing",
     "        return requirement[0] if requirement is not None else None\n",
     "        return None\n"),
    ("skill credit: a craft trains nothing",
     "        return stats.crafting_skill if stats is not None else None\n",
     "        return None\n"),
    ("skill credit: every route is credited",
     "                   if route_skill(item, route, game_data) in skills else route\n",
     "                   if True else route\n"),
]
SKILL_CREDIT_PRICE_MUTATIONS = [
    ("skill credit: the make price ignores the demanded skills",
     "                                  credit_skills=ctx.skill_demand)\n",
     "                                  credit_skills=frozenset())\n"),
]
```

and in the `run_group` list:

```python
    run_group(SKILL_CREDIT_SRC, SKILL_CREDIT_MUTATIONS,
              "tests/test_ai/test_skill_credit.py", survivors)
    run_group(CONSUMABLE_PRICE_SRC, SKILL_CREDIT_PRICE_MUTATIONS,
              "tests/test_ai/test_skill_credit.py", survivors)
```

Run: `uv run python formal/diff/mutate.py --check-anchors`
Expected: `anchor check OK`.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/skill_credit.py src/artifactsmmo_cli/ai/acquisition_cost.py \
  src/artifactsmmo_cli/ai/consumable_price.py tests/test_ai/test_skill_credit.py formal/diff/mutate.py
git commit -m "feat(price): a demanded skill's actions are not a cost of what they make

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Then run the new mutants (needs a clean tree): `uv run python formal/diff/mutate.py --only skill_credit` — expected: every `skill credit:` mutant `killed`.

---

### Task 2: Food does not justify its own production

**Files:**
- Modify: `src/artifactsmmo_cli/ai/xp_demand.py:31-40` (`demand_roots`)
- Modify: `src/artifactsmmo_cli/ai/player.py:~4115-4131` (`_selection_context`)
- Test: `tests/test_ai/test_xp_demand.py`, `tests/test_ai/test_consumable_floor.py:~105-110`, `tests/test_ai/test_player_coordination.py`
- Modify: `formal/diff/mutate.py` (`CONSUMABLE_DEMAND_MUTATIONS`)

**Interfaces:**
- Consumes: Task 1 (`make_seconds` reads `ctx.skill_demand`, so it must be set before the loadout is chosen).
- Produces: `demand_roots(chosen, state, ctx)` no longer appends `ctx.supply_shortfall`; in `_selection_context`, `ctx.skill_demand` / `ctx.level_demanded` are set BEFORE `fight_ahead_loadout` runs.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ai/test_xp_demand.py`:

```python
def test_the_fleet_food_shortfall_is_not_dag_demand() -> None:
    """Spec §2: the shortfall made fishing 'useful', which made the food cheap,
    which made the shortfall. Fishing is useful only when a gear or skill root
    needs it."""
    ctx = dataclasses.replace(NO_PROFILE_CONTEXT, supply_shortfall=(("cooked_bass", 12),))
    assert demand_roots(None, make_state(), ctx) == []
```

In `tests/test_ai/test_consumable_floor.py` replace the assertion at ~line 109
`assert demand_roots(None, make_state(), ctx) == [ObtainItem("cooked_bass", 12)]`
with `assert demand_roots(None, make_state(), ctx) == []` and update that test's docstring to say the shortfall no longer seeds a DAG root (spec 2026-10-13 §2). Remove the `ObtainItem` import if it becomes unused.

Append to `tests/test_ai/test_player_coordination.py` (same module fixtures as `test_the_shortfall_reaches_the_selection_context`):

```python
def test_the_skill_demand_is_known_when_the_loadout_is_chosen(monkeypatch):
    """Spec §2: the make price credits `ctx.skill_demand`, so the loadout must
    be chosen against a context that already carries it."""
    p = GamePlayer(character="hero", fleet_order=("hero",))
    p.state = make_state()
    p.game_data = _make_planner_gd()
    seen = {}

    def choose(state, gd, ctx, store):  # type: ignore[no-untyped-def]
        seen["skills"] = ctx.skill_demand
        return None

    monkeypatch.setattr("artifactsmmo_cli.ai.player.xp_demand",
                        lambda roots, s, g, c: (frozenset({"fishing"}), False))
    monkeypatch.setattr("artifactsmmo_cli.ai.player.fight_ahead_loadout", choose)
    monkeypatch.setattr("artifactsmmo_cli.ai.player.pool_draw", lambda *a: (False, None))
    ctx = p._selection_context(combat_monster="chicken")
    assert seen["skills"] == frozenset({"fishing"})
    assert ctx.skill_demand == frozenset({"fishing"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_xp_demand.py tests/test_ai/test_consumable_floor.py tests/test_ai/test_player_coordination.py -q --no-cov -n auto -p no:cacheprovider`
Expected: 3 FAIL (shortfall still a root ×2; `seen["skills"] == frozenset()`).

- [ ] **Step 3: Implement**

`xp_demand.py` — `demand_roots` becomes:

```python
def demand_roots(chosen: MetaGoal | None, state: WorldState,
                 ctx: SelectionContext) -> list[MetaGoal]:
    """The chosen root, then one `ObtainItem` per unworn target or near-term
    target, in a stable order. NOT the fleet consumable shortfall (spec
    2026-10-13 §2): food demand made fishing 'useful XP', which credited the
    food's make price, which kept the food demanded."""
    worn = {code for code in state.equipment.values() if code is not None}
    roots: list[MetaGoal] = [] if chosen is None else [chosen]
    roots.extend(ObtainItem(code, 1)
                 for code in sorted(ctx.target_gear | ctx.near_term_targets) if code not in worn)
    return roots
```

`player.py` `_selection_context` — move the `xp_demand` block above the loadout pick. The block that today reads:

```python
        ctx = replace(ctx, loadout=self._party_fight_loadout()
                      or fight_ahead_loadout(self.state, self.game_data, ctx, self.history))
        self._consumable_need = consumable_need(ctx.loadout)
        self._supply_shortfall = supply_shortfall(
            self.state, self._fleet_order, self.character, self._consumable_need,
            self._sibling_needs)
        ctx = replace(ctx, supply_shortfall=self._supply_shortfall)
        skills, level = xp_demand(
            demand_roots(self._last_decision.chosen_root if self._last_decision is not None else None,
                         self.state, ctx),
            self.state, self.game_data, ctx)
        ctx = replace(ctx, skill_demand=skills, level_demanded=level)
```

becomes:

```python
        # Skill demand first (spec 2026-10-13 §2): the loadout's make prices
        # credit the skills it names, and it no longer reads the shortfall.
        skills, level = xp_demand(
            demand_roots(self._last_decision.chosen_root if self._last_decision is not None else None,
                         self.state, ctx),
            self.state, self.game_data, ctx)
        ctx = replace(ctx, skill_demand=skills, level_demanded=level)
        ctx = replace(ctx, loadout=self._party_fight_loadout()
                      or fight_ahead_loadout(self.state, self.game_data, ctx, self.history))
        self._consumable_need = consumable_need(ctx.loadout)
        self._supply_shortfall = supply_shortfall(
            self.state, self._fleet_order, self.character, self._consumable_need,
            self._sibling_needs)
        ctx = replace(ctx, supply_shortfall=self._supply_shortfall)
```

Leave `decisions/root.py:449` and `task_worth.py:58` reading the shortfall: after Task 3 the shortfall only names food the fleet would still make at replacement price, so those readers stay honest.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_xp_demand.py tests/test_ai/test_consumable_floor.py tests/test_ai/test_player_coordination.py tests/test_ai/test_planning_window.py -q --no-cov -n auto -p no:cacheprovider`
Expected: all PASS.

- [ ] **Step 5: Mutation entries**

In `formal/diff/mutate.py` replace `CONSUMABLE_DEMAND_MUTATIONS` (its anchor no longer exists) with the inverse mutant:

```python
CONSUMABLE_DEMAND_MUTATIONS = [
    ("floor demand: the shortfall seeds a DAG root again",
     "                 for code in sorted(ctx.target_gear | ctx.near_term_targets) if code not in worn)\n"
     "    return roots\n",
     "                 for code in sorted(ctx.target_gear | ctx.near_term_targets) if code not in worn)\n"
     "    roots.extend(ObtainItem(code, qty) for code, qty in ctx.supply_shortfall)\n"
     "    return roots\n"),
]
```

and change its `run_group` test path to `"tests/test_ai/test_xp_demand.py"`. Add to `PLAYER_SRC` groups:

```python
SKILL_DEMAND_ORDER_MUTATIONS = [
    ("skill demand: the loadout is chosen without it",
     "        ctx = replace(ctx, skill_demand=skills, level_demanded=level)\n"
     "        ctx = replace(ctx, loadout=self._party_fight_loadout()\n",
     "        ctx = replace(ctx, loadout=self._party_fight_loadout()\n"),
]
```

`run_group(PLAYER_SRC, SKILL_DEMAND_ORDER_MUTATIONS, "tests/test_ai/test_player_coordination.py", survivors)`.

Run: `uv run python formal/diff/mutate.py --check-anchors` → `anchor check OK`.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/xp_demand.py src/artifactsmmo_cli/ai/player.py \
  tests/test_ai/test_xp_demand.py tests/test_ai/test_consumable_floor.py \
  tests/test_ai/test_player_coordination.py formal/diff/mutate.py
git commit -m "fix(demand): the fleet food shortfall no longer makes fishing useful XP

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Then `uv run python formal/diff/mutate.py --only xp_demand,test_player_coordination.py` — expected: both new mutants `killed`.

---

### Task 3: The loadout names the food worth MAKING

**Files:**
- Modify: `src/artifactsmmo_cli/ai/chosen_loadout.py` (`ChosenLoadout`)
- Modify: `src/artifactsmmo_cli/ai/best_loadout.py:50-105` (`BestLoadout`, `best_loadout`, `chosen`)
- Modify: `src/artifactsmmo_cli/ai/consumable_floor.py:34-42` (`consumable_need`)
- Modify: `src/artifactsmmo_cli/ai/party_win.py:140,144`
- Modify every other `ChosenLoadout(` / `BestLoadout(` construction (list: `grep -rln "ChosenLoadout(\|BestLoadout(" src tests formal`)
- Test: `tests/test_ai/test_best_loadout.py`, `tests/test_ai/test_consumable_floor.py`, `tests/test_ai/test_chosen_loadout.py`
- Modify: `formal/diff/mutate.py`

**Interfaces:**
- Produces: `ChosenLoadout(monster, potions, food, made_food)` — new REQUIRED 4th field `made_food: tuple[tuple[str, int], ...]`: the foods (and units per recovery) the recovery eats when every food unit is priced at replacement (held count 0; foods with no replacement dropped). `BestLoadout(loadout, rate, bare, made)` — new 4th field `made: LoopRate`. `consumable_need` reads `made_food` for food (potions unchanged).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ai/test_best_loadout.py` (reuse its existing fixture style; read the file's top ~80 lines for its bundle/state helpers and use the same ones):

```python
def test_made_food_is_the_recovery_with_nothing_held(monkeypatch):
    """Spec §1: held food is eaten free, but the stock is MADE only when food
    still beats Rest at replacement price."""
    rates = iter([
        _rate(used=(), eaten=(("apple", 2),)),   # the pick, apples held free
        _rate(used=(), eaten=()),                 # nothing held: Rest wins
    ])
    monkeypatch.setattr(best_mod, "loop_rate", lambda *a, **k: next(rates))
    monkeypatch.setattr(best_mod, "loadouts", lambda prices, gd: [()])
    monkeypatch.setattr(best_mod, "candidate_potions", lambda *a, **k: {})
    monkeypatch.setattr(best_mod, "food_menu",
                        lambda *a, **k: (best_mod.FoodOffer("apple", 50, Fraction(90), 10),))
    best = best_mod.best_loadout(make_state(), GameData(), NO_PROFILE_CONTEXT, "wolf")
    picked = best_mod.chosen(best, "wolf")
    assert picked.food == (("apple", 2),)
    assert picked.made_food == ()


def test_the_made_recovery_holds_nothing_and_drops_unpriced_food(monkeypatch):
    seen = []

    def fake_loop_rate(state, gd, monster, loadout, food, prices):  # type: ignore[no-untyped-def]
        seen.append(tuple(food))
        return _rate(used=(), eaten=())

    monkeypatch.setattr(best_mod, "loop_rate", fake_loop_rate)
    monkeypatch.setattr(best_mod, "loadouts", lambda prices, gd: [()])
    monkeypatch.setattr(best_mod, "candidate_potions", lambda *a, **k: {})
    menu = (best_mod.FoodOffer("apple", 50, Fraction(90), 10),
            best_mod.FoodOffer("relic_bread", 80, None, 4))
    monkeypatch.setattr(best_mod, "food_menu", lambda *a, **k: menu)
    best_mod.best_loadout(make_state(), GameData(), NO_PROFILE_CONTEXT, "wolf")
    assert seen == [menu, (best_mod.FoodOffer("apple", 50, Fraction(90), 0),)]
```

If `FoodOffer` is not importable as `best_mod.FoodOffer`, import it from `artifactsmmo_cli.ai.loop_rate` at the top of the test module. Make sure `Fraction`, `GameData`, `NO_PROFILE_CONTEXT`, `make_state` are imported at the top of the module (most already are).

Append to `tests/test_ai/test_consumable_floor.py`:

```python
def test_the_need_is_the_food_worth_making_not_the_food_held():
    """Spec §4: the fleet floor asks the producer only for food the fleet would
    still eat at replacement price."""
    loadout = ChosenLoadout("wolf", (("boost", 1),), (("apple", 2),), ())
    assert consumable_need(loadout) == {"boost": REFILL_HORIZON_FIGHTS}
    made = ChosenLoadout("wolf", (), (("apple", 2),), (("apple", 1),))
    assert consumable_need(made) == {"apple": REFILL_HORIZON_FIGHTS}
```

(import `REFILL_HORIZON_FIGHTS` from `artifactsmmo_cli.ai.consumable_floor_core` at the top if absent.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_best_loadout.py tests/test_ai/test_consumable_floor.py -q --no-cov -n auto -p no:cacheprovider`
Expected: FAIL (`ChosenLoadout` takes 4 positional args; `made_food` missing).

- [ ] **Step 3: Implement**

`chosen_loadout.py` — add the field and document it:

```python
@dataclass(frozen=True)
class ChosenLoadout:
    """The chosen loadout against `monster`: each utility potion it wears with
    the units one fight drinks, each food its recovery eats with the units one
    fight's recovery eats (only codes it uses, in the chooser's order), and
    `made_food`, the food that recovery eats when every unit must be MADE
    (held count 0, replacement price): the food worth producing (spec
    2026-10-13 §1). Held food is eaten free; only `made_food` is stocked past
    what is held, or asked of the fleet."""

    monster: str
    potions: tuple[tuple[str, int], ...]
    food: tuple[tuple[str, int], ...]
    made_food: tuple[tuple[str, int], ...]
```

`best_loadout.py`:

```python
@dataclass(frozen=True)
class BestLoadout:
    """The chosen utility potions, their loop (`rate.used`: the potions one
    fight drinks; `rate.eaten`: the foods its recovery eats), the no-potion
    loop, and `made`: the chosen potions' loop over the food menu with nothing
    held (spec 2026-10-13 §1)."""

    loadout: tuple[str, ...]
    rate: LoopRate
    bare: LoopRate
    made: LoopRate


def unheld(food: Sequence[FoodOffer]) -> tuple[FoodOffer, ...]:
    """The menu as if nothing were held: every unit at its replacement price,
    and a food with no replacement off the menu."""
    return tuple(replace(offer, held=0) for offer in food if offer.price is not None)
```

At the end of `best_loadout`:

```python
    codes, rate = scored[index]
    made = loop_rate(state, game_data, monster,
                     [(code, UTILITY_SLOT_MAX_STACK) for code in codes], unheld(food), prices)
    # The chosen potions were payable over the real menu, and food never
    # changes what a fight drinks: the same potions are payable here.
    assert made is not None
    return BestLoadout(codes, rate, scored[0][1], made)
```

`chosen`:

```python
    return ChosenLoadout(monster, tuple((code, n) for code, n in best.rate.used if n > 0),
                         best.rate.eaten, best.made.eaten)
```

Add imports at the top of `best_loadout.py` as needed: `from collections.abc import Sequence`, `from dataclasses import dataclass, replace`, and `FoodOffer` in the existing `from artifactsmmo_cli.ai.loop_rate import ...` line.

`consumable_floor.py` `consumable_need`:

```python
    for code, units in (*loadout.potions, *loadout.made_food):
```

and update its docstring/module NEED bullet: "the food its recovery eats when every unit must be made (`ChosenLoadout.made_food`)".

`party_win.py`: both returns gain a 4th `()` argument:
`return ChosenLoadout(monster, (), (), ())` and
`return ChosenLoadout(monster, tuple((code, n) for code, n in drinks if n > 0), (), ())`.

Every remaining construction site: run `grep -rn "ChosenLoadout(\|BestLoadout(" src tests formal` and add the 4th argument.
- For `ChosenLoadout(m, p, f)` in tests and `formal/diff/*.py`, pass `made_food` EQUAL to `f` (the old meaning: the food eaten is the food made) — e.g. `ChosenLoadout("wolf", (), (("cheese", 1),), (("cheese", 1),))`. The test helper `_eats` in `tests/test_ai/test_grind_heal_prep.py` becomes `ChosenLoadout(monster=monster, potions=(), food=food, made_food=food)`.
- For `BestLoadout(a, b, c)` in tests (`tests/test_ai/fixtures.py:167`, `tests/test_ai/test_best_loadout.py:190,200`), pass the same `LoopRate` as `rate` for `made` (e.g. `BestLoadout(loadout, loop, make_loop(), loop)` after binding `loop = make_loop(**loop)`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai tests/test_audit formal/diff/test_inventory_keep_diff.py formal/diff/test_objectivestep_arming_diff.py -q --no-cov -n auto -p no:cacheprovider`
Expected: all PASS.

- [ ] **Step 5: Mutation entries**

Update the existing anchors in `formal/diff/mutate.py`:
- `BEST_LOADOUT_READER_MUTATIONS` "the chosen loadout drops the food its recovery eats": anchor becomes
  `"    return ChosenLoadout(monster, tuple((code, n) for code, n in best.rate.used if n > 0),\n                         best.rate.eaten, best.made.eaten)"` with replacement
  `"    return ChosenLoadout(monster, tuple((code, n) for code, n in best.rate.used if n > 0),\n                         (), best.made.eaten)"`.
- `PARTY_*` entry at ~line 6011: `ChosenLoadout(monster, (), ())` → `ChosenLoadout(monster, (), (), ())` in both anchor and replacement.

Add to `BEST_LOADOUT_READER_MUTATIONS`:

```python
    ("best_loadout reader: the made food is the held-free food",
     "                         best.rate.eaten, best.made.eaten)",
     "                         best.rate.eaten, best.rate.eaten)"),
    ("best_loadout reader: the made menu keeps the held units",
     "    return tuple(replace(offer, held=0) for offer in food if offer.price is not None)\n",
     "    return tuple(offer for offer in food if offer.price is not None)\n"),
    ("best_loadout reader: an unpriced food is made",
     "    return tuple(replace(offer, held=0) for offer in food if offer.price is not None)\n",
     "    return tuple(replace(offer, held=0) for offer in food)\n"),
```

Add to `CONSUMABLE_FLOOR_MUTATIONS` (and fix the existing "the chosen food is not a need" anchor to `"    for code, units in (*loadout.potions, *loadout.made_food):"`):

```python
    ("floor: the need is the food held, not the food made",
     "    for code, units in (*loadout.potions, *loadout.made_food):",
     "    for code, units in (*loadout.potions, *loadout.food):"),
```

Run: `uv run python formal/diff/mutate.py --check-anchors` → `anchor check OK`.

- [ ] **Step 6: Commit**

```bash
git add -A src/artifactsmmo_cli/ai tests formal/diff
git status --short   # only files this task touched may be staged
git commit -m "feat(loadout): the chosen loadout names the food worth making

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Then `uv run python formal/diff/mutate.py --only best_loadout,consumable_floor,party_win` — expected: no survivors.

---

### Task 4: Only the role owner makes food

**Files:**
- Create: `src/artifactsmmo_cli/ai/food_producer.py`
- Modify: `src/artifactsmmo_cli/ai/selection_context.py` (two fields)
- Modify: `src/artifactsmmo_cli/ai/player.py` (`_update_coordination` sets `self._fleet_roles`; `__init__` initialises it; `_selection_context` threads `role` / `fleet_roles`)
- Modify: `src/artifactsmmo_cli/ai/grind_heal_prep.py:52-72` (`heal_prep_goal`)
- Test: `tests/test_ai/test_food_producer.py` (create), `tests/test_ai/test_grind_heal_prep.py`, `tests/test_ai/test_player_coordination.py`
- Modify: `formal/diff/mutate.py`

**Interfaces:**
- Consumes: Task 3 (`ChosenLoadout.made_food`).
- Produces: `SelectionContext.role: str | None = None`, `SelectionContext.fleet_roles: frozenset[str] = frozenset()` (None/empty = single-character run). `food_producer.food_owner(code: str, game_data: GameData) -> str | None`; `food_producer.may_make_food(code: str, role: str | None, fleet_roles: frozenset[str], game_data: GameData) -> bool`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_food_producer.py`:

```python
"""Only the role that owns a food's craft makes it, unless nobody holds that
role (spec 2026-10-13 §4)."""

from artifactsmmo_cli.ai.food_producer import food_owner, may_make_food
from artifactsmmo_cli.ai.game_data import GameData, ItemStats


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "cooked_trout": ItemStats(code="cooked_trout", level=1, type_="consumable",
                                  hp_restore=100, crafting_skill="cooking", crafting_level=1),
        "apple": ItemStats(code="apple", level=1, type_="consumable", hp_restore=50),
    }
    return gd


def test_cooking_is_the_fisher_s():
    assert food_owner("cooked_trout", _gd()) == "fisher"
    assert food_owner("apple", _gd()) is None


def test_the_fisher_makes_food_and_nobody_else_does_while_one_is_held():
    gd = _gd()
    assert may_make_food("cooked_trout", "fisher", frozenset({"fisher", "miner"}), gd)
    assert not may_make_food("cooked_trout", "miner", frozenset({"fisher", "miner"}), gd)
    assert not may_make_food("cooked_trout", None, frozenset({"fisher"}), gd)


def test_with_no_fisher_in_the_fleet_anyone_makes_food():
    """The fleet must not starve while the role is unheld (Review Focus 2)."""
    assert may_make_food("cooked_trout", "miner", frozenset({"miner"}), _gd())


def test_a_lone_character_makes_its_own_food():
    """Single-character run: no role, no fleet (Review Focus 1)."""
    assert may_make_food("cooked_trout", None, frozenset(), _gd())


def test_a_food_no_role_crafts_is_anyone_s():
    assert may_make_food("apple", "miner", frozenset({"fisher"}), _gd())
```

Append to `tests/test_ai/test_grind_heal_prep.py` class `TestHealPrepGoal`:

```python
    def test_food_not_worth_making_is_only_withdrawn(self):
        """Spec §1: Rest beats the food at replacement price (`made_food`
        empty): the banked units are fetched, nothing is cooked."""
        gd = _gd()
        ctx = replace(NO_PROFILE_CONTEXT, combat_monster="wolf",
                      loadout=ChosenLoadout("wolf", (), (("cheese", 1),), ()))
        state = _state(gd, {"milk": CARRY}, bank={"cheese": 5})
        assert _needed(heal_prep_goal(state, gd, ctx, "wolf")) == {"cheese": 5}
        assert heal_prep_goal(_state(gd, {"milk": CARRY}), gd, ctx, "wolf") is None

    def test_a_non_fisher_only_withdraws_while_a_fisher_is_held(self):
        """Spec §4: the fisher makes the fleet's food; a sibling fetches it."""
        gd = _gd()
        ctx = replace(EATS_CHEESE, role="miner", fleet_roles=frozenset({"fisher", "miner"}))
        state = _state(gd, {"milk": CARRY}, bank={"cheese": 5})
        assert _needed(heal_prep_goal(state, gd, ctx, "wolf")) == {"cheese": 5}
        fisher = replace(ctx, role="fisher")
        assert _needed(heal_prep_goal(state, gd, fisher, "wolf")) == {"cheese": CARRY}
```

Append to `tests/test_ai/test_player_coordination.py`:

```python
def test_the_role_and_the_fleet_s_roles_reach_the_selection_context(monkeypatch):
    p = GamePlayer(character="hero", fleet_order=("hero",))
    p.state = make_state()
    p.game_data = _make_planner_gd()
    p._role = "fisher"
    p._fleet_roles = frozenset({"fisher", "miner"})
    monkeypatch.setattr("artifactsmmo_cli.ai.player.fight_ahead_loadout", lambda *a: None)
    monkeypatch.setattr("artifactsmmo_cli.ai.player.pool_draw", lambda *a: (False, None))
    ctx = p._selection_context(combat_monster="chicken")
    assert ctx.role == "fisher"
    assert ctx.fleet_roles == frozenset({"fisher", "miner"})


def test_a_lone_character_sees_no_fleet_roles():
    assert GamePlayer(character="hero")._fleet_roles == frozenset()
```

Add one more test in `test_player_coordination.py` next to an existing `_update_coordination` test that builds a real coordination store (search the module for `set_coordination_store(` and copy that setup): after a sibling claims `fisher` in the store and `p._update_coordination(state, gd)` runs, `p._fleet_roles` contains `"fisher"`. Assert on the store's `live_leases(now)` keys, not a hand-built set.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_food_producer.py tests/test_ai/test_grind_heal_prep.py tests/test_ai/test_player_coordination.py -q --no-cov -n auto -p no:cacheprovider`
Expected: FAIL (`food_producer` missing; `SelectionContext` has no `role`; `_fleet_roles` missing).

- [ ] **Step 3: Implement**

Create `src/artifactsmmo_cli/ai/food_producer.py`:

```python
"""Who makes the fleet's food (spec 2026-10-13 §4, USER "the fleet needs a
food maker role so that others can focus elsewhere").

A food's OWNER is the catalogue role that owns its crafting skill (`fisher`
owns cooking). The owner makes it; a sibling fetches what is banked or rests.
When no live character holds the owning role, anyone makes it — the fleet must
not starve while the role is unheld — and a food no role crafts (an apple
gathered off a tree) is anyone's."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.role_catalog import ROLE_CATALOG, role_skills


def food_owner(code: str, game_data: GameData) -> str | None:
    """The role owning `code`'s crafting skill, or None when no role crafts it."""
    stats = game_data.item_stats(code)
    skill = stats.crafting_skill if stats is not None else None
    if not skill:
        return None
    return next((role.name for role in ROLE_CATALOG if skill in role_skills(role)), None)


def may_make_food(code: str, role: str | None, fleet_roles: frozenset[str],
                  game_data: GameData) -> bool:
    """Whether a character holding `role` makes `code`, given the roles any
    live character holds (`fleet_roles`, empty on a single-character run)."""
    owner = food_owner(code, game_data)
    return owner is None or role == owner or owner not in fleet_roles
```

`selection_context.py` — add after the `skill_demand` field (keep the field-comment style used there):

```python
    # The role this character holds and every role a live character holds
    # (`CoordinationStore.live_leases`), set by the player each cycle. None /
    # empty on a single-character run. `food_producer.may_make_food` reads
    # them: only the owner of a food's craft makes it (spec 2026-10-13 §4).
    role: str | None = None
    fleet_roles: frozenset[str] = frozenset()
```

`player.py`:
- `__init__`, next to `self._role: str | None = None`: `self._fleet_roles: frozenset[str] = frozenset()`.
- `_update_coordination`, in the `if self._coordination is None:` reset block add `self._fleet_roles = frozenset()`; after `now = datetime.now(tz=timezone.utc)` (first line after that block) add `self._fleet_roles = frozenset(self._coordination.live_leases(now))`. (If a later `decide_role` claim/release in the same call changes `self._role`, the next cycle's read picks it up; one-cycle lag is acceptable.)
- `_selection_context`: in the `SelectionContext(...)` constructor call add `role=self._role,` and `fleet_roles=self._fleet_roles,` next to `sibling_skills=self._sibling_skills,`.

`grind_heal_prep.py` — add `from artifactsmmo_cli.ai.food_producer import may_make_food`, then:

```python
    model = ObtainModel(state, game_data, ctx, datetime.now(UTC))
    loadout = loadout_for(state, game_data, ctx, monster)
    made = dict(loadout.made_food)
    for code, eaten in loadout.food:
        carry = food_carry(eaten)
        bag = state.inventory.get(code, 0)
        held = bag + (state.bank_items or {}).get(code, 0)
        # Spec 2026-10-13 §1/§4: units past the held ones are MADE only when
        # the food beats Rest at replacement price and this character makes
        # the fleet's food; otherwise only what is held is fetched.
        makes = made.get(code, 0) > 0 and may_make_food(code, ctx.role, ctx.fleet_roles, game_data)
        for target in ((carry, min(carry, held)) if makes else (min(carry, held),)):
            if target > bag and model.feasible(code, target, HEAL_PREP_POLICY):
                return GatherMaterialsGoal(target_item=code, needed={code: target}, carry=True)
    return None
```

Update `heal_prep_goal`'s docstring: the full carry is the target only when the food is in `made_food` and `may_make_food`; otherwise the units held.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_food_producer.py tests/test_ai/test_grind_heal_prep.py tests/test_ai/test_player_coordination.py tests/test_ai/test_strategy_driver.py tests/test_ai/test_craft_plan_gen.py -q --no-cov -n auto -p no:cacheprovider`
Expected: all PASS.

- [ ] **Step 5: Mutation entries**

Add `FOOD_PRODUCER_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "food_producer.py"` (and to `_ALL_SRCS`). Replace the `GRIND_HEAL_PREP_POLICY_MUTATIONS` entry anchored on `"        for target in (carry, min(carry, held)):"` with:

```python
    ("grind_heal_prep: an unsuppliable carry leaves the held units in the bank",
     "        for target in ((carry, min(carry, held)) if makes else (min(carry, held),)):",
     "        for target in ((carry,) if makes else (min(carry, held),)):"),
    ("grind_heal_prep: food not worth making is made",
     "        makes = made.get(code, 0) > 0 and may_make_food(code, ctx.role, ctx.fleet_roles, game_data)\n",
     "        makes = may_make_food(code, ctx.role, ctx.fleet_roles, game_data)\n"),
    ("grind_heal_prep: a non-owner makes food",
     "        makes = made.get(code, 0) > 0 and may_make_food(code, ctx.role, ctx.fleet_roles, game_data)\n",
     "        makes = made.get(code, 0) > 0\n"),
```

New group:

```python
FOOD_PRODUCER_MUTATIONS = [
    ("food producer: no food has an owner",
     "    return next((role.name for role in ROLE_CATALOG if skill in role_skills(role)), None)\n",
     "    return None\n"),
    ("food producer: an unheld role still forbids",
     "    return owner is None or role == owner or owner not in fleet_roles\n",
     "    return owner is None or role == owner\n"),
    ("food producer: the owner may not make it",
     "    return owner is None or role == owner or owner not in fleet_roles\n",
     "    return owner is None or owner not in fleet_roles\n"),
]
FLEET_ROLES_PLAYER_MUTATIONS = [
    ("fleet roles: never read",
     "        self._fleet_roles = frozenset(self._coordination.live_leases(now))\n",
     ""),
    ("fleet roles: the context never carries the role",
     "            role=self._role,\n            fleet_roles=self._fleet_roles,\n",
     "            fleet_roles=self._fleet_roles,\n"),
]
```

`run_group(FOOD_PRODUCER_SRC, FOOD_PRODUCER_MUTATIONS, "tests/test_ai/test_food_producer.py", survivors)` and `run_group(PLAYER_SRC, FLEET_ROLES_PLAYER_MUTATIONS, "tests/test_ai/test_player_coordination.py", survivors)`. If `role=self._role,` appears elsewhere in `player.py` with the same indentation (the cycle snapshot at ~line 2774 uses 12 spaces too), make the anchor the two-line pair shown so it resolves uniquely; confirm with `--check-anchors`.

Run: `uv run python formal/diff/mutate.py --check-anchors` → `anchor check OK`.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/food_producer.py src/artifactsmmo_cli/ai/selection_context.py \
  src/artifactsmmo_cli/ai/player.py src/artifactsmmo_cli/ai/grind_heal_prep.py \
  tests/test_ai/test_food_producer.py tests/test_ai/test_grind_heal_prep.py \
  tests/test_ai/test_player_coordination.py formal/diff/mutate.py
git commit -m "feat(roles): only the fisher makes the fleet's food; siblings fetch or rest

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Then `uv run python formal/diff/mutate.py --only food_producer,grind_heal_prep,test_player_coordination.py` — expected: no survivors.

---

### Task 5: Role demand weighs work, not units

**Files:**
- Modify: `src/artifactsmmo_cli/ai/role_selection.py:660-710` (`demand_by_role`)
- Modify: `src/artifactsmmo_cli/ai/player.py:~3712-3730` (`_update_coordination`), add `_work_of_item`
- Test: `tests/test_ai/test_role_selection.py`, `tests/test_ai/test_player_coordination.py`
- Modify: `formal/diff/mutate.py`

**Interfaces:**
- Produces: `demand_by_role(item_demand, skill_of_item, catalog, level_of_item=NO_ITEM_LEVELS, skill_levels=NO_SKILL_LEVELS, work_of_item: Mapping[str, int] | None = None) -> dict[str, int]` — with `work_of_item`, each row counts `quantity × work_of_item[code]` and a code absent from the map is skipped; with None (pure-module unit tests only), each row counts its quantity. `GamePlayer._work_of_item(item_demand: Mapping[str, int], state: WorldState, game_data: GameData) -> dict[str, int]`: acquisition actions per unit (`acquisition_actions(code, 1, state, game_data, NO_PROFILE_CONTEXT, equip=False)`), codes with no route (≥ `UNOBTAINABLE_PER_UNIT`) omitted. Actions stand in for seconds: the walk's unit is one fight-equivalent (`FIGHT_SECONDS`), a uniform factor that does not change any comparison.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ai/test_role_selection.py` (it already imports `demand_by_role` and `ROLE_CATALOG`; add any missing import at the top):

```python
def test_role_demand_is_the_work_it_asks_for():
    """Spec §3: 80 fish at 2 actions each (160) weigh less than one sword at
    300 actions."""
    demand = {"cooked_trout": 80, "iron_sword": 1}
    skill = {"cooked_trout": "cooking", "iron_sword": "weaponcrafting"}
    work = {"cooked_trout": 2, "iron_sword": 300}
    totals = demand_by_role(demand, skill, ROLE_CATALOG, work_of_item=work)
    assert totals["fisher"] == 160 and totals["miner"] == 300


def test_an_item_with_no_priced_work_does_not_recruit():
    """Review Focus 4: an unpriceable item is skipped, not counted as free."""
    totals = demand_by_role({"relic": 5}, {"relic": "gearcrafting"}, ROLE_CATALOG, work_of_item={})
    assert totals["logger"] == 0
```

Append to `tests/test_ai/test_player_coordination.py`:

```python
def test_the_work_of_an_item_is_its_acquisition_walk(monkeypatch):
    p = GamePlayer(character="hero")
    walks = {"cooked_trout": 2, "relic": UNOBTAINABLE_PER_UNIT}
    monkeypatch.setattr("artifactsmmo_cli.ai.player.acquisition_actions",
                        lambda code, qty, state, gd, ctx, equip: walks[code])
    assert p._work_of_item({"cooked_trout": 80, "relic": 1}, make_state(), GameData()) == {
        "cooked_trout": 2}
```

(import `UNOBTAINABLE_PER_UNIT` from `artifactsmmo_cli.ai.acquisition_cost_core` and `GameData` at the top if absent.) Also extend an existing `_update_coordination` role test in this module: patch `GamePlayer._work_of_item` to return a map and assert the `demand_by_role` passed to `decide_role` is the weighted one (patch `artifactsmmo_cli.ai.player.decide_role` to capture its `demand_by_role` kwarg).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_role_selection.py tests/test_ai/test_player_coordination.py -q --no-cov -n auto -p no:cacheprovider`
Expected: FAIL (`unexpected keyword argument 'work_of_item'`; `_work_of_item` missing).

- [ ] **Step 3: Implement**

`role_selection.py` `demand_by_role` — signature gains `work_of_item: Mapping[str, int] | None = None`; the loop's last line becomes:

```python
        weight = 1 if work_of_item is None else work_of_item.get(item_code)
        if weight is None:
            continue
        totals[role_name] += quantity * weight
```

Add to the docstring: "`work_of_item` (spec 2026-10-13 §3) weighs each row by the work one unit asks — acquisition actions per unit — so eighty fish do not out-recruit a sword that is an hour of crafting. A code with no entry has no priced route and recruits no one. None counts units (the pure unit tests' shape; the player always passes the map)."

`player.py` — imports at top (alphabetical in the existing block): `from artifactsmmo_cli.ai.acquisition_cost import acquisition_actions` (if not already imported), `from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT`, `NO_PROFILE_CONTEXT` in the existing `selection_context` import. New method next to `_producing_split`:

```python
    @staticmethod
    def _work_of_item(item_demand: Mapping[str, int], state: WorldState,
                      game_data: GameData) -> dict[str, int]:
        """Acquisition actions for one unit of each code on the board — the work
        a role is asked for (spec 2026-10-13 §3). Priced against the profile-free
        context: a board weight, not a plan. A code with no route is left out and
        so recruits no one."""
        work = {code: acquisition_actions(code, 1, state, game_data, NO_PROFILE_CONTEXT,
                                          equip=False)
                for code in item_demand}
        return {code: actions for code, actions in work.items()
                if actions < UNOBTAINABLE_PER_UNIT}
```

In `_update_coordination`, after `skill_of_item, level_of_item = self._producing_split(item_demand, game_data)`:

```python
        work_of_item = self._work_of_item(item_demand, state, game_data)
```

and pass `work_of_item=work_of_item` to BOTH `demand_by_role(...)` calls there (`by_role` and `asymmetric_roles`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_role_selection.py tests/test_ai/test_player_coordination.py -q --no-cov -n auto -p no:cacheprovider`
Expected: all PASS. The per-cycle cost of `_work_of_item` (one acquisition walk per board code) is checked live in Task 6 Step 3; if it exceeds 1 s per cycle, stop and report — do not add a cache without a design decision.

- [ ] **Step 5: Mutation entries**

Add `ROLE_SELECTION_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "role_selection.py"` if absent (and to `_ALL_SRCS`), then:

```python
ROLE_WORK_MUTATIONS = [
    ("role work: rows count units",
     "        totals[role_name] += quantity * weight\n",
     "        totals[role_name] += quantity\n"),
    ("role work: an unpriced item counts as one",
     "        weight = 1 if work_of_item is None else work_of_item.get(item_code)\n",
     "        weight = 1 if work_of_item is None else work_of_item.get(item_code, 1)\n"),
]
ROLE_WORK_PLAYER_MUTATIONS = [
    ("role work: the player never weighs the board",
     "        work_of_item = self._work_of_item(item_demand, state, game_data)\n",
     "        work_of_item = None\n"),
    ("role work: an unroutable item is weighed",
     "                if actions < UNOBTAINABLE_PER_UNIT}\n",
     "                }\n"),
]
```

`run_group(ROLE_SELECTION_SRC, ROLE_WORK_MUTATIONS, "tests/test_ai/test_role_selection.py", survivors)` and `run_group(PLAYER_SRC, ROLE_WORK_PLAYER_MUTATIONS, "tests/test_ai/test_player_coordination.py", survivors)`.

Run: `uv run python formal/diff/mutate.py --check-anchors` → `anchor check OK`.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/role_selection.py src/artifactsmmo_cli/ai/player.py \
  tests/test_ai/test_role_selection.py tests/test_ai/test_player_coordination.py formal/diff/mutate.py
git commit -m "feat(roles): role demand weighs the work it asks, not its units

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Then `uv run python formal/diff/mutate.py --only role_selection,test_player_coordination.py` — expected: no survivors.

---

### Task 6: Gate, ship, witness

**Files:**
- Modify: `/home/blentz/.claude/projects/-home-blentz-git-artifactsmmo/memory/` (new project memory + `MEMORY.md` line)

- [ ] **Step 1: Full gate**

Run: `bash formal/gate.sh > /tmp/gate.log 2>&1; echo rc=$?` then `tail -5 /tmp/gate.log`.
Expected: `rc=0`, `ALL GATE PARTS PASSED`, coverage 100%. Read the rc in its own call (never through `| tail`).

- [ ] **Step 2: Push**

```bash
git fetch -q origin && git merge-base --is-ancestor origin/main HEAD && git push origin HEAD:main
```

- [ ] **Step 3: Restart and witness (after the user restarts `play --all`)**

Record the restart time `T`. After ≥ 2 h, query `~/.cache/artifactsmmo/learning.db`:

```sql
-- holders
SELECT role, character FROM role_leases WHERE expires_at > datetime('now');
-- food share of busy time per character, and fleet XP/h, since T
WITH w AS (SELECT * FROM cycles WHERE ts >= :T AND outcome = 'ok')
SELECT character,
  round(sum(CASE WHEN action_repr LIKE 'Craft(cooked%' OR action_repr LIKE 'Gather(%trout%'
            OR action_repr LIKE 'Gather(%shrimp%' OR action_repr LIKE 'Gather(%gudgeon%'
            OR action_repr LIKE 'Gather(%bass%' THEN actual_cooldown_seconds ELSE 0 END)
        / sum(actual_cooldown_seconds), 2) AS food_share,
  sum(action_class = 'RestAction') AS rests
FROM w GROUP BY 1;
SELECT round(sum(delta_xp) * 3600.0 / ((julianday(max(ts)) - julianday(min(ts))) * 86400))
FROM cycles WHERE ts >= :T;
```

Also check `_work_of_item`'s cost: compare the median `planner_nodes`/cycle spacing before and after `T`, or time `_work_of_item` once against the live board with the CLI's game data; over 1 s per cycle → stop and report.

Expected vs baseline (2026-10-13 17:37–20:04Z): at most one `fisher` while fishing/cooking XP is not demanded; non-fisher `food_share` far below 0.69; fleet character XP/h above 3,160. Report the numbers as measured, whatever they are.

- [ ] **Step 4: Memory**

Write `project_fleet_food_role.md` (frontmatter `type: project`) with: the commit SHAs, the baseline and measured numbers, the residual (multi-fisher pile-on when food wins and no rival demand), and a link `[[project_role_driven_supply]]`; add one line to `MEMORY.md`.
