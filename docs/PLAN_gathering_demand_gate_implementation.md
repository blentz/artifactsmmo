# Gathering-Skill Demand Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop offering a gathering-skill grind root unless something actually needs that skill's level, so a character with no material demand climbs cooking instead of grinding fishing for 0 XP.

**Architecture:** One new pure module computes, for the roots the resolution is about to offer, the highest gather-skill level any of their requirement closures demands. `_orphan_skill_roots` gains a third admission conjunct reading that map, and emits the demanded level instead of `C+1` for an admitted skill. No ordering change. No change to `NeedSet` or the arbiter.

**Tech Stack:** Python 3.13, `uv`, pytest. No new dependencies.

**Spec:** `docs/PLAN_gathering_skill_demand_gate.md`

## Global Constraints

- Prefix every Python command with `uv run` (e.g. `uv run pytest`).
- Imports at the top of the file. No inline imports. No `if TYPE_CHECKING`.
- Never catch `Exception`. Multiple levels of error handling is a bug.
- One behavioural class per file.
- Use only API data or fail with an error. No defaulting around missing game data.
- Tests live in `tests/`. Success criteria: 0 errors, 0 warnings, 0 skipped.
- Never use `repr`/`str` sorting as a decision tiebreak; use a semantic key.
- The full gate is one command: `bash formal/gate.sh` (~6 min).

## Deviation from the spec, and why

The spec says `tiers/objective_needs.py::_add_skill_gate` gains the gather leg.
This plan does NOT touch it. Two reasons found by reading the consumers:

1. `means_worth._task_need_overlap` (means_worth.py:57) tests
   `_task_skills(...) & needs.skill_xp`, and `_task_skills` already unions
   `game_data.active_gathering_skills(task_code)`. Widening `skill_xp` with
   gather skills would make that intersection hit in cases it does not today,
   silently switching the PURSUE_TASK worth gate on. That is a live behaviour
   change outside this feature's scope.
2. `NeedSet.skill_xp` is a `frozenset[str]` and carries no level. The spec
   requires an admitted skill to emit the DEMANDED level, which needs
   `skill -> level`.

The spec's purpose for that change — making a gathered leaf's skill gate
visible — is met instead by consuming `RequirementGraph.gather_skill`, a public
field whose own docstring says it is "Populated but UNCONSUMED this epic ... a
model that cannot express a known livelock cause is not a unification." This
change is its first consumer. No new plumbing, and `NeedSet` keeps its meaning.

---

### Task 1: The gather-demand projection

**Files:**
- Create: `src/artifactsmmo_cli/ai/gather_demand.py`
- Test: `tests/test_ai/test_gather_demand.py`

**Interfaces:**
- Consumes: `RequirementGraph.gather_skill` (`Mapping[str, tuple[str, int]]`,
  item -> (skill, level)); `requirement_projections.requirement_closure(graph,
  roots) -> frozenset[str]`; `tiers.skill_grind_target.skill_grind_target(skill,
  state, game_data, reserved=frozenset(), ctx=NO_PROFILE_CONTEXT) -> str | None`.
- Produces: `gather_demand(roots: Sequence[MetaGoal], state: WorldState,
  game_data: GameData, ctx: SelectionContext) -> dict[str, int]` — skill ->
  highest UNMET demanded level. A skill whose demand is met is absent, so
  `.get(skill, 0)` is falsy exactly when nothing asks.

- [ ] **Step 1: Write the failing test**

```python
"""Gather-demand projection: which gathering skills the offered roots need."""

import pytest

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gather_demand import gather_demand
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachSkillLevel
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    """A catalogue with one craft whose material is a gathered leaf.

    `iron_boots` <- `iron_bar` <- `iron_ore`, and `iron_ore` is gathered from
    `iron_rocks` at mining@10 — the live shape, minimised.
    """
    gd = GameData()
    gd._item_stats = {
        "iron_boots": ItemStats(code="iron_boots", level=10, type_="boots",
                                crafting_skill="gearcrafting", crafting_level=10),
        "iron_bar": ItemStats(code="iron_bar", level=10, type_="resource",
                              crafting_skill="mining", crafting_level=10),
        "iron_ore": ItemStats(code="iron_ore", level=10, type_="resource"),
    }
    gd._all_item_stats = gd._item_stats
    gd._crafting_recipes = {"iron_boots": {"iron_bar": 6},
                            "iron_bar": {"iron_ore": 10}}
    gd._resource_drops_full = {"iron_rocks": [("iron_ore", 100, 1, 1)]}
    gd._resource_skill_levels = {"iron_rocks": ("mining", 10)}
    return gd


class TestGatherDemand:
    def test_names_the_skill_a_closure_leaf_gates_on(self):
        gd = _gd()
        state = make_state(level=20, skills={"mining": 1})
        assert gather_demand([ObtainItem(code="iron_boots", quantity=1)],
                             state, gd, NO_PROFILE_CONTEXT) == {"mining": 10}

    def test_silent_when_the_gate_is_already_met(self):
        gd = _gd()
        state = make_state(level=20, skills={"mining": 10})
        assert gather_demand([ObtainItem(code="iron_boots", quantity=1)],
                             state, gd, NO_PROFILE_CONTEXT) == {}

    def test_takes_the_highest_level_across_roots(self):
        """Two roots demanding the same skill collapse to the deeper gate."""
        gd = _gd()
        gd._resource_drops_full["coal_rocks"] = [("coal", 100, 1, 1)]
        gd._resource_skill_levels["coal_rocks"] = ("mining", 20)
        gd._item_stats["coal"] = ItemStats(code="coal", level=20, type_="resource")
        gd._crafting_recipes["steel_boots"] = {"coal": 4, "iron_ore": 2}
        gd._item_stats["steel_boots"] = ItemStats(
            code="steel_boots", level=20, type_="boots",
            crafting_skill="gearcrafting", crafting_level=20)
        gd._all_item_stats = gd._item_stats
        state = make_state(level=20, skills={"mining": 1})
        roots = [ObtainItem(code="iron_boots", quantity=1),
                 ObtainItem(code="steel_boots", quantity=1)]
        assert gather_demand(roots, state, gd, NO_PROFILE_CONTEXT) == {"mining": 20}

    def test_seeds_a_skill_root_through_its_grind_target(self):
        """A ReachSkillLevel root names no item, so its demand is invisible to a
        closure walk over `.code`. It is seeded with the item the character
        would craft for that rung."""
        gd = _gd()
        state = make_state(level=20, skills={"mining": 1, "gearcrafting": 1})
        demand = gather_demand([ReachSkillLevel(skill="gearcrafting", level=10)],
                               state, gd, NO_PROFILE_CONTEXT)
        assert demand == {"mining": 10}

    def test_a_gathering_skill_root_does_not_seed_itself(self):
        """Recursion guard: seeding a mining root from a mining grind target
        would let the root manufacture its own demand."""
        gd = _gd()
        state = make_state(level=20, skills={"mining": 1})
        assert gather_demand([ReachSkillLevel(skill="mining", level=2)],
                             state, gd, NO_PROFILE_CONTEXT) == {}

    def test_no_roots_is_no_demand(self):
        assert gather_demand([], make_state(), _gd(), NO_PROFILE_CONTEXT) == {}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_ai/test_gather_demand.py -q --no-cov`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.gather_demand'`

If instead it fails on a `GameData` attribute name, fix the fixture to match the
real private attribute names (read `src/artifactsmmo_cli/ai/game_data.py`); do
not change the assertions.

- [ ] **Step 3: Write the implementation**

```python
"""Which gathering skills the roots on offer actually need, and to what level.

The demand side of the gathering-skill grind gate. `_orphan_skill_roots` offers
a standalone skill climb for every skill no gear target can name, which admits
every gathering skill by construction — gear is crafted by gearcrafting,
weaponcrafting and jewelrycrafting, so mining, woodcutting, fishing and alchemy
fall out as orphans whether or not anything wants them. Live 2026-09-09/10 that
sent R2D2 and Robby to fishing for ~617 cycles each at 0 character XP while
neither needed a fish.

This module answers the question that gate was missing: does any root on offer
bottom out in a leaf this character cannot gather yet? It reads
`RequirementGraph.gather_skill`, the item -> (skill, level) map the
requirement-model unification built and left unconsumed.
"""

from collections.abc import Sequence

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.requirement_projections import requirement_closure
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ObtainItem, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from artifactsmmo_cli.ai.world_state import WorldState


def gathering_skills(game_data: GameData) -> frozenset[str]:
    """Skills that gate a gathered leaf, read from the catalogue.

    NOT a hardcoded set: the gate must not name skills individually, or it
    encodes a difference the catalogue does not have. Live this is
    {alchemy, fishing, mining, woodcutting}; cooking gathers nothing and is
    therefore never gated.
    """
    graph = game_data.requirement_graph.graph()
    return frozenset(skill for skill, _level in graph.gather_skill.values())


def _seed(root: MetaGoal, state: WorldState, game_data: GameData,
          ctx: SelectionContext, gathering: frozenset[str]) -> str | None:
    """The item code whose requirements stand in for `root`.

    An `ObtainItem` names its own. A `ReachSkillLevel` names NO item, so its
    demand is invisible to a closure walk — the same blind spot recorded for the
    supply link — and is seeded with the item the character would craft for that
    rung. A root for a GATHERING skill is not seeded: letting it name its own
    grind target would let the root manufacture the demand that admits it.
    """
    if isinstance(root, ObtainItem):
        return root.code
    if isinstance(root, ReachSkillLevel) and root.skill not in gathering:
        return skill_grind_target(root.skill, state, game_data, ctx=ctx)
    return None


def gather_demand(roots: Sequence[MetaGoal], state: WorldState,
                  game_data: GameData, ctx: SelectionContext) -> dict[str, int]:
    """Skill -> the highest UNMET gather level any root's closure requires.

    A skill whose demand is already met is ABSENT rather than present-and-zero,
    so `.get(skill, 0)` is falsy exactly when nothing is asking.
    """
    graph = game_data.requirement_graph.graph()
    gathering = frozenset(skill for skill, _level in graph.gather_skill.values())
    demand: dict[str, int] = {}
    for root in roots:
        seed = _seed(root, state, game_data, ctx, gathering)
        if seed is None:
            continue
        for item in requirement_closure(graph, [seed]):
            gate = graph.gather_skill.get(item)
            if gate is None:
                continue
            skill, level = gate
            if state.skills.get(skill, 1) < level and level > demand.get(skill, 0):
                demand[skill] = level
    return demand
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_ai/test_gather_demand.py -q --no-cov`
Expected: PASS, 6 tests.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/gather_demand.py tests/test_ai/test_gather_demand.py
git commit -m "feat(demand): name the gathering skills the offered roots actually need

Reads RequirementGraph.gather_skill, the item -> (skill, level) map the
requirement-model unification built and explicitly left unconsumed. A
ReachSkillLevel root names no item, so it is seeded through skill_grind_target;
a root for a gathering skill is not seeded, or it would manufacture the demand
that admits it."
```

---

### Task 2: The third admission conjunct

**Files:**
- Modify: `src/artifactsmmo_cli/ai/decisions/root.py` (`_orphan_skill_roots`, lines 339-397; its call site at line 852)
- Test: `tests/test_ai/test_orphan_skill_roots_demand.py`

**Interfaces:**
- Consumes: `gather_demand(roots, state, game_data, ctx) -> dict[str, int]` and
  `gathering_skills(game_data) -> frozenset[str]` from Task 1.
- Produces: `_orphan_skill_roots(state, game_data, offered, ctx)` — signature
  widened from `(state, game_data)`. `offered` is the roots already on the
  table; `ctx` is the live `SelectionContext`.

- [ ] **Step 1: Write the failing test**

```python
"""The gathering-skill demand gate on `_orphan_skill_roots`."""

from artifactsmmo_cli.ai.decisions.root import _orphan_skill_roots
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_gather_demand import _gd

_BOOTS = ObtainItem(code="iron_boots", quantity=1)


def _skills(state, gd, offered):
    return [g.skill for g in _orphan_skill_roots(state, gd, offered, NO_PROFILE_CONTEXT)]


class TestGatheringSkillNeedsDemand:
    def test_dropped_when_nothing_demands_it(self):
        """R2D2's shape: mining is past every gate anything asks for."""
        gd = _gd()
        state = make_state(level=20, skills={"mining": 10, "cooking": 1})
        # Vacuity guard: the other two conjuncts hold, so only the new one can
        # be what removes mining below.
        assert "mining" not in _gear_nameable(gd)
        assert "mining" in _skills(state, gd, [])           # pre-gate admission
        assert _orphan_demand(state, gd, [_BOOTS]) == {}
        assert "mining" not in _skills(state, gd, [_BOOTS])

    def test_kept_when_a_root_demands_it(self):
        """HAL's shape: a root's closure bottoms out in a leaf out of reach."""
        gd = _gd()
        state = make_state(level=20, skills={"mining": 1, "cooking": 1})
        assert "mining" in _skills(state, gd, [_BOOTS])

    def test_an_admitted_skill_emits_the_demanded_level(self):
        """Not C+1. `mining->2` completes and re-emits; `mining->10` is the ask."""
        gd = _gd()
        state = make_state(level=20, skills={"mining": 1, "cooking": 1})
        roots = _orphan_skill_roots(state, gd, [_BOOTS], NO_PROFILE_CONTEXT)
        mining = next(g for g in roots if g.skill == "mining")
        assert mining.level == 10

    def test_a_non_gathering_skill_is_never_gated(self):
        """Cooking gathers nothing, so it never enters the conjunct and is the
        anti-Wait floor. Admitted with an empty demand set."""
        gd = _gd()
        gd._item_stats["cooked_gudgeon"] = ItemStats(
            code="cooked_gudgeon", level=1, type_="consumable",
            crafting_skill="cooking", crafting_level=1)
        gd._all_item_stats = gd._item_stats
        gd._crafting_recipes["cooked_gudgeon"] = {"gudgeon": 1}
        state = make_state(level=20, skills={"mining": 10, "cooking": 1})
        assert _orphan_demand(state, gd, []) == {}
        assert "cooking" in _skills(state, gd, [])
```

Add these two helpers at the top of the same test file, under the imports:

```python
from artifactsmmo_cli.ai.decisions.root import _gear_nameable_skills
from artifactsmmo_cli.ai.gather_demand import gather_demand


def _gear_nameable(gd):
    return _gear_nameable_skills(gd)


def _orphan_demand(state, gd, offered):
    return gather_demand(offered, state, gd, NO_PROFILE_CONTEXT)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_ai/test_orphan_skill_roots_demand.py -q --no-cov`
Expected: FAIL — `TypeError: _orphan_skill_roots() takes 2 positional arguments but 4 were given`

- [ ] **Step 3: Widen the signature and add the conjunct**

In `src/artifactsmmo_cli/ai/decisions/root.py`, add to the imports at the top:

```python
from artifactsmmo_cli.ai.gather_demand import gather_demand, gathering_skills
```

Replace the body of `_orphan_skill_roots` (its `return` block and the two lines
above it) with:

```python
    nameable = _gear_nameable_skills(game_data)
    gathering = gathering_skills(game_data)
    demand = gather_demand(offered, state, game_data, ctx)
    orphans = [
        skill for skill in SKILL_NAMES
        if skill not in nameable
        and level_skill.LevelSkill(
            skill=skill, target_level=state.skills.get(skill, 1) + 1
        ).is_applicable(state, game_data)
        # THIRD CONJUNCT: a skill that gates a gathered leaf must be ASKED FOR.
        # Conjunct 1 admits every gathering skill by construction, which is how
        # R2D2 and Robby came to grind fishing ~617 cycles each for 0 character
        # XP while neither needed a fish. Keyed on "does this skill gate a
        # gathered leaf", read from the catalogue, so no skill is named
        # individually — cooking gathers nothing, never enters the conjunct, and
        # is the floor that keeps this group from emptying into `Wait`.
        and (skill not in gathering or skill in demand)]
    orphans.sort(key=lambda skill: (state.skills.get(skill, 1) - state.level,
                                    SKILL_NAMES.index(skill)))
    # A demanded skill is offered the level that was ASKED FOR. `C+1` is a
    # one-rung nudge with no destination: it completes and re-emits, which is
    # the churn this gate exists to stop. An ungated skill keeps `C+1` because
    # nothing named a level for it.
    return tuple(ReachSkillLevel(
        skill=skill,
        level=demand.get(skill, state.skills.get(skill, 1) + 1))
        for skill in orphans)
```

and change the signature line from

```python
def _orphan_skill_roots(state: WorldState,
                        game_data: GameData) -> tuple[ReachSkillLevel, ...]:
```

to

```python
def _orphan_skill_roots(state: WorldState, game_data: GameData,
                        offered: Sequence[MetaGoal],
                        ctx: SelectionContext) -> tuple[ReachSkillLevel, ...]:
```

Add `from collections.abc import Sequence` to the imports if not already present.

- [ ] **Step 4: Update the docstring's stale claim**

In the same function's docstring, replace:

```
    Measured on the committed bundle the rule admits exactly four skills:
    cooking, fishing, mining and woodcutting — the four whose every recipe
    produces a `consumable` or a `resource`. Cooking is the instance the epic
    named; the other three arrive because the rule is about the catalogue.
```

with:

```
    Measured on the live bundle 2026-09-10 the first two conjuncts admit FIVE
    skills: alchemy, cooking, fishing, mining and woodcutting — every skill
    whose recipes produce a `consumable` or a `resource`. (An earlier revision
    of this docstring said four and omitted alchemy.)

    THE THIRD CONJUNCT then holds the four that gather back until something asks
    for them, leaving cooking — which gathers nothing — as the unconditional
    floor. Measured across `ai/scenario.SCENARIOS`, cooking is admitted in 44 of
    44 scenarios and this group is empty in 0 of 44, so the fall-through to
    `Wait` this seam exists to prevent stays unreachable.
```

- [ ] **Step 5: Update the call site**

In `resolve_root`, change line 852 from

```python
    ordered.extend(_orphan_skill_roots(state, game_data))
```

to

```python
    ordered.extend(_orphan_skill_roots(state, game_data, [root, *ordered], ctx))
```

`[root, *ordered]` is deliberate: `ordered` holds the gear siblings and the
trunk but NOT the resolved root, and the root is the likeliest thing to be
demanding a material.

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run pytest tests/test_ai/test_orphan_skill_roots_demand.py -q --no-cov`
Expected: PASS, 4 tests.

- [ ] **Step 7: Fix the other callers**

Run: `uv run grep -rn "_orphan_skill_roots" src/ tests/ formal/`

Every call site must pass the two new arguments. Update each; in an offline
audit context pass `NO_PROFILE_CONTEXT` for `ctx`, matching
`open_rung_completeness.routed_skills`'s existing `history=None` convention.

- [ ] **Step 8: Run the full AI suite**

Run: `uv run pytest tests/test_ai/ -q --no-cov -m "not integration"`
Expected: PASS. If a test fails on the orphan ORDER, stop — the order was not
meant to change and a change there is a defect in this task, not a stale test.

- [ ] **Step 9: Commit**

```bash
git add src/artifactsmmo_cli/ai/decisions/root.py tests/test_ai/test_orphan_skill_roots_demand.py
git commit -m "fix(roots): a gathering skill is a grind target only when something asks

Conjunct 1 (no gear target names it) admits every gathering skill by
construction, so the seam offered fishing, mining, woodcutting and alchemy
whether or not anything wanted them. Live 2026-09-09/10 that sent R2D2 and Robby
to fishing for ~617 cycles each at 0 character XP while neither needed a fish.

Keyed on 'does this skill gate a gathered leaf', read from the catalogue rather
than a hardcoded set, so no skill is named individually. Cooking gathers nothing
and stays unconditional: admitted in 44 of 44 census scenarios, group empty in 0
of 44, so the fall-through to Wait stays unreachable.

An admitted skill now emits the demanded level rather than C+1, which completed
and re-emitted forever."
```

---

### Task 3: Verify the census and the live effect

**Files:**
- Test: `tests/test_ai/test_orphan_gate_scenarios.py`
- Read only: `src/artifactsmmo_cli/audit/open_rung_completeness.py`

**Interfaces:**
- Consumes: everything from Tasks 1-2; `ai.scenario.SCENARIOS`;
  `audit.open_rung_completeness.census_state(scenario, game_data)`.
- Produces: nothing further depends on this task.

- [ ] **Step 1: Write the scenario-sweep test**

```python
"""The gate, driven over the census scenario set through the REAL walk.

The spec makes two predictions and this pins both: the orphan group never
empties (so `Wait` stays unreachable), and cooking is the floor that guarantees
it. Runs `resolve_root` rather than `_orphan_skill_roots` directly, because the
walk is what production calls.
"""

import pytest

from artifactsmmo_cli.ai.decisions.root import resolve_root
from artifactsmmo_cli.ai.scenario import SCENARIOS
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.audit.open_rung_completeness import census_state


@pytest.mark.integration
def test_the_orphan_group_never_empties_across_the_scenario_set(scenario_game_data):
    gd = scenario_game_data
    objective = CharacterObjective.from_game_data(gd)
    empty = []
    for name, scenario in SCENARIOS.items():
        state = census_state(scenario, gd)
        res = resolve_root(state, gd, objective, NO_PROFILE_CONTEXT, None)
        skill_roots = [g for g in (res.root, *res.alternatives)
                       if isinstance(g, ReachSkillLevel)]
        if not skill_roots:
            empty.append(name)
    assert empty == [], (
        f"{len(empty)} scenarios lost every skill root, which is the `Wait` "
        f"fall-through this seam exists to prevent: {empty}")
```

Add the `scenario_game_data` fixture to `tests/test_ai/conftest.py` if it is not
already there. It loads the same committed bundle the census uses — no API call:

```python
import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData

_BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


@pytest.fixture(scope="session")
def scenario_game_data() -> GameData:
    """The committed catalogue bundle, exactly as `scripts/gen_open_rung.py`
    loads it, so this suite and the census cannot disagree about the data."""
    return GameData.from_cache_bundle(json.loads(_BUNDLE.read_text()))
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/test_ai/test_orphan_gate_scenarios.py -q --no-cov`
Expected: PASS.

- [ ] **Step 3: Run the O1 census before and after, and diff**

The spec predicts an UNCHANGED verdict distribution: the gate only shrinks the
routed set, and `O1_SILENT_STALL` fires on routed-AND-no-open-rung, which
conjunct 2 already prevents.

The census is offline: `scripts/gen_open_rung.py` reads the committed bundle
`tests/test_ai/scenarios/fixtures/gamedata_bundle.json`, so it needs no API and
is deterministic.

```bash
uv run python scripts/gen_open_rung.py --check > /tmp/census_after.txt 2>&1
echo "EXIT=$?"
```

For the baseline, copy the changed file aside and restore the committed version
in place — never `git checkout <path>` or `git stash`, either of which would
discard the uncommitted work:

```bash
cp src/artifactsmmo_cli/ai/decisions/root.py /tmp/root.FIXED.py
git show HEAD~1:src/artifactsmmo_cli/ai/decisions/root.py > src/artifactsmmo_cli/ai/decisions/root.py
uv run python scripts/gen_open_rung.py --check > /tmp/census_before.txt 2>&1
cp /tmp/root.FIXED.py src/artifactsmmo_cli/ai/decisions/root.py
git diff --stat -- src/artifactsmmo_cli/ai/decisions/root.py  # must show the fix restored
diff /tmp/census_before.txt /tmp/census_after.txt
```

Note the baseline run will fail at import if Task 2 renamed a symbol the
committed `root.py` does not have; if so, restore the fixed file immediately and
take the baseline from `HEAD~1` in a scratch clone instead.

Expected: no difference in the verdict counts, and residuals 0 in both.

**If any cell moves, STOP and report it rather than adjusting the census.** The
spec states this reasoning is a prediction, not a proof; a moved cell means the
prediction is wrong and the design needs review.

- [ ] **Step 4: Confirm the live effect on the two characters that motivated this**

```bash
uv run artifactsmmo plan R2D2 2>&1 | tail -25
uv run artifactsmmo plan Robby 2>&1 | tail -25
```

Expected: neither resolution lists a `ReachSkillLevel(skill='fishing', ...)`
among its alternatives. Both previously did.

This is the runtime-activation check — green tests are not evidence that a
planner change fires in production. If `fishing` still appears, the gate is not
reaching the live walk and the task is not done.

Note the fleet is live and its state moves. If either character's state has
drifted such that fishing IS now demanded, say so and check a character whose
demand is empty rather than declaring the step passed.

- [ ] **Step 5: Run the full gate**

Run: `bash formal/gate.sh > /tmp/gate.log 2>&1; echo "EXIT=${PIPESTATUS[0]}"`
Then: `tail -30 /tmp/gate.log`

Expected: EXIT=0. A failure in `test_effect_coverage_audit_live.py` with
`RateLimitedError: HTTP 429` is environmental — the live players share the
per-IP budget. Re-run that file alone to confirm before dismissing it.

- [ ] **Step 6: Commit**

```bash
git add tests/test_ai/test_orphan_gate_scenarios.py
git commit -m "test(roots): pin the anti-Wait floor across the census scenario set

Drives the real resolve_root over every scenario and asserts the orphan group
never loses its last skill root. The spec's census prediction is verified by
before/after diff at implementation time; this suite is the standing guard."
```

---

## Self-Review

**Spec coverage:**
- Third admission conjunct, uniform, catalogue-keyed — Task 2 Step 3.
- Demanded level instead of `C+1` — Task 2 Steps 3 and 1.
- Cooking as unconditional anti-`Wait` floor — Task 2 Step 3, pinned Task 3 Step 1.
- Gather leg made visible — Task 1, via `RequirementGraph.gather_skill` rather
  than `_add_skill_gate` (deviation recorded above, with reasons).
- `ReachSkillLevel` seeded through `skill_grind_target` — Task 1 Step 3.
- Recursion guard on gathering roots — Task 1 Step 3, tested Task 1 Step 1.
- Ordering unchanged — asserted by Task 2 Step 8's stop condition.
- O1 census unchanged — Task 3 Step 3, with an explicit stop-and-report.
- Stale docstring (four skills -> five) — Task 2 Step 4.
- Live runtime activation — Task 3 Step 4.

**Placeholder scan:** no TBD/TODO. Two steps name a condition rather than an
exact edit — Task 2 Step 7 (other call sites) and Task 3 Step 1 (the scenario
fixture) — because both depend on what the tree holds at execution time. Each
gives the command that enumerates the work and the rule for resolving it.

**Type consistency:** `gather_demand(roots, state, game_data, ctx) ->
dict[str, int]` and `gathering_skills(game_data) -> frozenset[str]` are used
with those names and argument orders in Tasks 2 and 3.
`_orphan_skill_roots(state, game_data, offered, ctx)` is consistent between its
definition, its call site, and both test files.

## Risks

- **The `GameData` fixture in Task 1.** It sets private attributes
  (`_item_stats`, `_crafting_recipes`, `_resource_drops_full`,
  `_resource_skill_levels`). If those names are wrong the tests fail at setup,
  not at the assertion — Task 1 Step 2 says to fix the fixture and leave the
  assertions alone.
- **`_orphan_skill_roots` is private but has audit callers.** Task 2 Step 7
  enumerates them; missing one is a hard `TypeError`, not a silent skip.
- **Near-inert for mining and woodcutting on today's fleet.** Expected and
  correct — nothing asks for those levels right now. Do not "fix" it by
  loosening the gate.
