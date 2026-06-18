"""gather_step_target: pick a budget-feasible gather target for a
depth-unreachable equippable root.

The from-scratch DEEP chain bug: `GatherMaterials(root, root's direct recipe)`
explodes the planner (1M+ nodes / 90s timeout) because its plan must gather
`min_gathers(root)` raw units through a multi-level recipe. The fix routes to the
strategy's DEEPEST actionable step (a flat raw gather) when the root exceeds the
equippable depth budget — sound because the step is a prerequisite ON the root's
path and never harder than the root.

Soundness anchor: formal/Formal/StepDispatch.lean (`gatherTarget_*`) +
min_gathers/PlannerDepthBound.
"""

from artifactsmmo_cli.ai.gather_step_target import gather_step_target
from artifactsmmo_cli.ai.min_gathers import min_gathers

# steel_boots <- 6 steel_bar <- 8 iron_bar <- 10 iron_ore  => 480 ore from scratch
_RECIPES = {
    "steel_boots": {"steel_bar": 6},
    "steel_bar": {"iron_bar": 8},
    "iron_bar": {"iron_ore": 10},
}


def test_unreachable_root_routes_to_deepest_step():
    """From scratch (no holdings), root needs 480 gathers >> equip_max_depth 15,
    so route to the deepest step (iron_ore, 480) — a FLAT gather."""
    target = gather_step_target("steel_boots", "iron_ore", 480, _RECIPES, {}, 15)
    assert target == ("iron_ore", 480)


def test_routed_step_is_flat_and_budget_feasible():
    """The routed target's min_gathers equals its quantity (flat raw) — no recipe
    sub-tree to explode — and is the same 480 as the root, never harder."""
    code, qty = gather_step_target("steel_boots", "iron_ore", 480, _RECIPES, {}, 15)
    flat = min_gathers(code, qty, _RECIPES, {})
    assert flat == qty == 480
    # Never harder than the declined root target.
    assert flat <= min_gathers("steel_boots", 1, _RECIPES, {})


def test_reachable_root_keeps_root_target():
    """When holdings make the root's gather cost fit the budget, target the root
    (the caller plans the short craft+equip chain directly)."""
    # 6 steel_bar already owned -> root cost is 0 gathers <= 15.
    owned = {"steel_bar": 6}
    target = gather_step_target("steel_boots", "iron_ore", 480, _RECIPES, owned, 15)
    assert target == ("steel_boots", 1)


def test_partial_holdings_still_unreachable_routes_to_step():
    """Owning some bars cuts the cost but if it still exceeds the budget, route to
    the step. 3 steel_bar -> need 3 more -> 240 ore > 15."""
    owned = {"steel_bar": 3}
    target = gather_step_target("steel_boots", "iron_ore", 240, _RECIPES, owned, 15)
    assert target == ("iron_ore", 240)


def test_boundary_exactly_at_budget_keeps_root():
    """root_cost == equip_max_depth is depth-REACHABLE (the gate is strict >),
    so the root is kept."""
    recipes = {"thing": {"ore": 15}}
    target = gather_step_target("thing", "ore", 15, recipes, {}, 15)
    assert target == ("thing", 1)


def test_one_over_budget_routes_to_step():
    recipes = {"thing": {"ore": 16}}
    target = gather_step_target("thing", "ore", 16, recipes, {}, 15)
    assert target == ("ore", 16)


def test_does_not_mutate_owned():
    owned = {"steel_bar": 3}
    gather_step_target("steel_boots", "iron_ore", 240, _RECIPES, owned, 15)
    assert owned == {"steel_bar": 3}


def test_multi_yield_unskips_marginal_chain():
    """A chain needing 16 raw units is over budget at yield 1 (16 > 15) but
    REACHABLE once the resource drops 2 per gather (ceil(16/2)=8 <= 15) — so the
    root is kept instead of being falsely routed to the deep step. This is the
    over-count bug the max_yield divisor fixes."""
    recipes = {"thing": {"ore": 16}}
    assert gather_step_target("thing", "ore", 16, recipes, {}, 15) == ("ore", 16)
    assert gather_step_target("thing", "ore", 16, recipes, {}, 15, 2) == ("thing", 1)


def test_multi_yield_still_skips_genuinely_deep_chain():
    """Dividing by yield stays a SOUND lower bound: a 480-unit chain at yield 3
    is still 160 gathers >> 15, so it is correctly routed to the deep step."""
    assert gather_step_target(
        "steel_boots", "iron_ore", 480, _RECIPES, {}, 15, 3) == ("iron_ore", 480)
