"""Differential test: real Python `task_batch_size` clamp must agree with proved Lean `batchSize`.

`task_batch_size` reads `mats_per_unit` from the recipe walk (`_raw_units`) and
`held_recipe` from the closure + the inventory. To compare the CLAMP logic (not
the recipe math, which is proved and differentially tested elsewhere) against
the Lean model with the SAME mats/held inputs, we construct a REAL one-recipe
game world realizing any chosen `(mats, held)` pair — no monkeypatching:

* recipes: `{"T": {"M": mats}}` with `"M"` raw, so `raw_material_units("T") == mats`.
* drops: `{"R": "M"}`, so the closure's needed resource is `"R"` and
  `held_recipe` is the inventory count of its drop `"M"` — the chosen `held`.
* `inventory == {"M": held}` and `inventory_max == free + held`, so
  `inventory_free == free`.

This makes the Python `usable = (free + held) - 3` and `fit = usable // mats`
identical to the Lean inputs, isolating the max/min/cap clamp for the differential.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.task_batch import BATCH_CAP, craft_batch_size_pure, task_batch_size
from artifactsmmo_cli.ai.world_state import WorldState
from formal.diff.oracle_client import run_oracle


def _make_state(task_branch: bool, remaining: int, free: int, held: int) -> WorldState:
    if task_branch:
        task_type = "items"
        task_code = "T"
        task_total = remaining
        task_progress = 0
    else:
        # Force the non-task branch: not an items task.
        task_type = "monsters"
        task_code = "T"
        task_total = remaining
        task_progress = 0
    inventory = {"M": held} if held > 0 else {}
    return WorldState(
        character="c", level=1, xp=0, max_xp=100, hp=10, max_hp=10, gold=0,
        skills={}, x=0, y=0, inventory=inventory, inventory_max=free + held,
        equipment={}, cooldown_expires=None, task_code=task_code, task_type=task_type,
        task_progress=task_progress, task_total=task_total, bank_items=None,
        bank_gold=None, pending_items=None,
    )


def _gd(mats: int) -> GameData:
    gd = GameData()
    gd._crafting_recipes = {"T": {"M": mats}}
    gd._resource_drops = {"R": "M"}
    return gd


@settings(max_examples=300)
@given(
    task_branch=st.booleans(),
    remaining=st.integers(min_value=1, max_value=50),
    mats=st.integers(min_value=1, max_value=8),
    free=st.integers(min_value=0, max_value=40),
    held=st.integers(min_value=0, max_value=40),
)
def test_python_matches_lean(task_branch, remaining, mats, free, held):
    game_data = _gd(mats)
    state = _make_state(task_branch, remaining, free, held)
    py = task_batch_size(state, game_data)

    lean = run_oracle(
        "task_batch",
        [[1 if task_branch else 0, remaining, mats, free, held]],
    )[0]
    assert py == lean["k"]


@settings(max_examples=300)
@given(
    demand=st.integers(min_value=1, max_value=50),
    mats=st.integers(min_value=1, max_value=8),
    free=st.integers(min_value=0, max_value=40),
    held=st.integers(min_value=0, max_value=40),
)
def test_craft_batch_matches_lean(demand, mats, free, held):
    # Same one-recipe world realizing (mats, held, demand): "T" needs `mats`
    # raw "M", drop "R"->"M", inventory holds `held` M, free slots = free. The
    # code-agnostic core must agree with the proved `batchSize true demand mats
    # free held` (the task path is exactly the demand = remaining case).
    recipes = {"T": {"M": mats}}
    drops = {"R": "M"}
    inventory = {"M": held} if held > 0 else {}
    py = craft_batch_size_pure("T", demand, inventory, free, recipes, drops)

    lean = run_oracle(
        "task_batch",
        [[1, demand, mats, free, held]],
    )[0]
    assert py == lean["k"]


def test_craft_batch_zero_mats_per_unit():
    # mats_per_unit == 0 (a degenerate zero-quantity recipe) is OUTSIDE the
    # hand model's mats >= 1 assumption (Lean fdiv-by-0 -> 0), so the code guard
    # short-circuits to max(1, min(demand, cap)) with no division. Asserted
    # directly (the oracle's batchSize does not model this branch).
    # The demand >= 1 cases (demand=4, demand=999) genuinely hit the mats==0
    # branch. demand=0 returns via the earlier `demand <= 0: return 1` guard
    # (NOT the mats==0 branch); it is harmless coverage of the demand-floor path.
    zero_recipe = {"Z": {"M": 0}}
    drops = {"R": "M"}
    assert craft_batch_size_pure("Z", 4, {}, 100, zero_recipe, drops) == 4    # mats==0 branch: max(1, min(4, 10)) = 4
    assert craft_batch_size_pure("Z", 999, {}, 100, zero_recipe, drops) == BATCH_CAP  # mats==0 branch: capped at 10
    assert craft_batch_size_pure("Z", 0, {}, 100, zero_recipe, drops) == 1    # demand<=0 guard fires first, not mats==0
