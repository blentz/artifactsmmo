"""Drop-vs-craft route-preference pin (follow-up wave Task 4, GAP-6 review's ask).

GAP-6 (2026-07-08) taught `GatherMaterialsGoal.relevant_actions` to emit a
winnable-dropper `FightAction` for ANY item in the recipe closure that some
monster drops (`goals/gathering.py` ~:289-347) — including the TOP-LEVEL
requested item itself (`chain` always contains the requested code at its own
demanded quantity, per `closure_demand`). Separately, the CraftAction branch
(~:232) admits a Craft action for any closure item that also has a recipe
(`craftable_mats`, from `recipe_closure`, includes the requested root when it
is itself craftable). Neither admission checks the OTHER route at all — so an
item that is BOTH craftable (with its materials already banked) AND dropped
by a winnable monster gets BOTH routes admitted into `relevant_actions`'
output simultaneously. GAP-6's review asked for a test pinning WHICH route
the least-cost GOAP planner (`planner.py`, Dijkstra with h=0 — proven optimal,
`formal/Formal/PlannerAdmissibility.lean`) actually picks in that case,
derived from the cost model rather than asserted by fiat.

THE CATALOG CASE: a one-time scan of the live scenario bundle
(`tests/test_ai/scenarios/fixtures/gamedata_bundle.json`, verified in
`test_enchanted_potion_is_the_live_catalogs_dual_route_case` below) finds
exactly ONE item in the whole catalog that is both craftable and monster-
dropped: `enchanted_potion` (level 40 consumable, recipe
`enchanted_mushroom x1 + salmon x1`, ALSO dropped 100% by `dryad`, a level-40
monster with 140 air attack). Reproducing a genuinely winnable fight against
the real dryad needs realistic level-40 gear far beyond what a compact unit
fixture should carry, and would smuggle unrelated combat-formula behavior
into a test that is about the COST MODEL, not combat capability. So the main
pin below builds a SYNTHETIC `GameData` with the identical item/recipe/
dropper SHAPE (a craftable consumable also dropped by a monster) but trivial,
fully-controlled stats (zero travel distances, a harmless 1-HP/0-attack
dropper, guaranteed win) — isolating the cost-model comparison from combat
and travel noise, the same synthetic-fixture pattern already used throughout
this file's sibling `test_craft_vs_buy_wiring.py` (`_gold_vendor_gd()` etc.).

THE COST-MODEL DERIVATION (verdict, not judgment):

  Craft route: Withdraw(enchanted_mushroom x1) + Withdraw(salmon x1) +
  Craft(enchanted_potion x1). Action.cost formulas (all `dist=0` in this
  fixture): WithdrawItemAction = 2.0 + dist = 2.0 each; CraftAction =
  5.0*quantity + dist = 5.0. Total = 2.0 + 2.0 + 5.0 = 9.0.

  Fight route: Fight(dryad) alone (100% drop rate, min=max=1 -> one kill
  guarantees the unit). FightAction.cost = 10.0 + dist (+`LOADOUT_PENALTY`
  5.0 if the character is not already wielding its best owned loadout for
  the fight — `actions/combat.py:31`). Best case (already optimally geared)
  = 10.0; realistic case (weapon owned but not pre-equipped, so the planner's
  loadout pick differs from the current equipment) = 15.0.

  9.0 < 10.0 in BOTH cases (even the Fight route's best case), so the
  least-cost planner picks CRAFT regardless of the loadout-penalty edge —
  the 3-Withdraw/Craft chain is strictly cheaper than any single Fight.
"""

import json
from pathlib import Path

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"


def test_enchanted_potion_is_the_live_catalogs_dual_route_case() -> None:
    """Regression-documents the real-catalog case this pin mirrors: exactly
    one item is both craftable and monster-dropped. If a future catalog
    update adds or removes such an item, this test flags it loudly (enumerate
    -and-compare, not just membership) rather than letting the mirrored
    synthetic fixture silently drift from reality."""
    gd = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
    dual_route = {
        code for code, stats in gd.all_item_stats.items()
        if gd.crafting_recipe(code) is not None and gd.monsters_dropping(code)
    }
    assert dual_route == {"enchanted_potion"}, dual_route
    assert gd.crafting_recipe("enchanted_potion") == {
        "enchanted_mushroom": 1, "salmon": 1}
    assert [m for m, *_rest in gd.monsters_dropping("enchanted_potion")] == ["dryad"]


def _gd() -> GameData:
    """Synthetic mirror of the enchanted_potion/dryad shape (see module
    docstring): craftable consumable ALSO dropped by a monster, with every
    distance zeroed and the dropper trivially winnable so the test isolates
    the cost-model comparison."""
    gd = GameData()
    gd._item_stats = {
        "basic_sword": ItemStats(
            code="basic_sword", level=1, type_="weapon", attack={"fire": 50}),
        "enchanted_potion": ItemStats(
            code="enchanted_potion", level=1, type_="consumable",
            crafting_skill="alchemy", crafting_level=1),
    }
    gd._crafting_recipes = {"enchanted_potion": {"enchanted_mushroom": 1, "salmon": 1}}
    gd._workshop_locations = {"alchemy": (0, 0)}
    gd._monster_level = {"dryad": 1}
    gd._monster_hp = {"dryad": 1}  # harmless: one hit kills it
    fill_monster_stat_defaults(gd)  # 0 attack -> the player can never lose
    gd._monster_drops = {"dryad": [("enchanted_potion", 100, 1, 1)]}
    gd._monster_locations = {"dryad": (0, 0)}
    return gd


def _state() -> object:
    # basic_sword OWNED (in inventory) but NOT pre-equipped: `pick_loadout`
    # must pick it for the fight, and the delta from "not currently equipped"
    # is what makes raw_player > 0 (predict_win: an unarmed 0-attack loadout
    # never wins — `combat.py:project_loadout_stats` deltas off `state.attack`,
    # which is 0 with nothing equipped). This also means the Fight route pays
    # the realistic LOADOUT_PENALTY (character isn't already optimally
    # geared), the WORSE case for Fight in the derivation above.
    return make_state(
        level=5, x=0, y=0, skills={"alchemy": 1},
        inventory={"basic_sword": 1},
        bank_items={"enchanted_mushroom": 1, "salmon": 1},
        inventory_max=20,
    )


def _actions() -> list:
    return [
        CraftAction(code="enchanted_potion", quantity=1, workshop_location=(0, 0)),
        WithdrawItemAction(code="enchanted_mushroom", quantity=1),
        WithdrawItemAction(code="salmon", quantity=1),
        FightAction(monster_code="dryad", locations=frozenset({(0, 0)})),
    ]


def test_both_routes_are_admitted_into_relevant_actions() -> None:
    """Precondition for the pin to mean anything: BOTH the Craft route's
    actions AND the Fight route are actually offered to the planner
    simultaneously — proving this is a genuine least-cost CHOICE, not a
    narrowing that already excluded one side."""
    gd = _gd()
    state = _state()
    goal = GatherMaterialsGoal(target_item="enchanted_potion", needed={"enchanted_potion": 1})
    relevant = goal.relevant_actions(_actions(), state, gd)
    assert any(isinstance(a, CraftAction) and a.code == "enchanted_potion" for a in relevant)
    assert any(isinstance(a, WithdrawItemAction) and a.code == "enchanted_mushroom"
               for a in relevant)
    assert any(isinstance(a, WithdrawItemAction) and a.code == "salmon" for a in relevant)
    assert any(isinstance(a, FightAction) and a.monster_code == "dryad" for a in relevant)


def test_planner_picks_the_cheaper_craft_route_over_the_winnable_drop() -> None:
    """THE PIN: with both routes admitted and the dropper genuinely winnable,
    the least-cost GOAP search picks CRAFT (cost 9.0: 2.0 Withdraw + 2.0
    Withdraw + 5.0 Craft) over FIGHT (cost 15.0: 10.0 base + 5.0
    LOADOUT_PENALTY) — the cost-model verdict derived in the module
    docstring, not an asserted preference."""
    gd = _gd()
    state = _state()
    goal = GatherMaterialsGoal(target_item="enchanted_potion", needed={"enchanted_potion": 1})
    actions = _actions()
    plan = GOAPPlanner().plan(state, goal, actions, gd)
    reprs = [repr(a) for a in plan]
    assert reprs == [
        "Withdraw(enchanted_mushroom×1)", "Withdraw(salmon×1)", "Craft(enchanted_potion×1)",
    ], reprs
    assert not any(isinstance(a, FightAction) for a in plan), reprs


def test_fight_route_would_still_lose_even_without_the_loadout_penalty() -> None:
    """Strengthens the pin: even in Fight's BEST case (10.0, no loadout
    penalty — the character already optimally geared), Craft's 9.0 still
    wins. The preference is not an artifact of the penalty; it holds on the
    base action-count/cooldown-shape difference alone (2 withdraws + 1 craft
    vs 1 fight, 9 < 10)."""
    gd = _gd()
    # Pre-equip the sword so the planner's picked loadout matches current
    # equipment exactly -> FightAction.cost's `optimal != current` check
    # never fires -> no LOADOUT_PENALTY.
    equipment = dict(make_state().equipment)
    equipment["weapon_slot"] = "basic_sword"
    state = make_state(
        level=5, x=0, y=0, skills={"alchemy": 1},
        inventory={"basic_sword": 1}, equipment=equipment,
        bank_items={"enchanted_mushroom": 1, "salmon": 1},
        inventory_max=20,
    )
    fight = FightAction(monster_code="dryad", locations=frozenset({(0, 0)}))
    assert fight.cost(state, gd) == 10.0, "fixture drifted: this test needs the zero-penalty case"
    plan = GOAPPlanner().plan(state, goal := GatherMaterialsGoal(
        target_item="enchanted_potion", needed={"enchanted_potion": 1}), _actions(), gd)
    assert [repr(a) for a in plan] == [
        "Withdraw(enchanted_mushroom×1)", "Withdraw(salmon×1)", "Craft(enchanted_potion×1)",
    ], (plan, goal)
