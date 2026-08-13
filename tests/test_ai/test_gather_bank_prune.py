"""GatherMaterialsGoal prunes gathers for bank-covered chain materials.

The live trace showed GatherMaterials(wooden_shield) building 43-step / 21.7k-node
plans because it admitted a GatherAction for every recipe-chain resource even when
the bank already held the material. The bank-aware shopping_list prunes a gather
whose drop is fully bank/inventory-covered, leaving the withdraw — bounding the
search. A material with a real deficit keeps its gather (no false pruning).
"""

from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.recipe_closure import gather_serves_closure
from artifactsmmo_cli.ai.shopping_list import fully_covered_materials
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_locations = {"copper_rocks": [(2, 0)]}
    return gd


def _actions() -> list:
    return [
        GatherAction(resource_code="copper_rocks", locations=frozenset({(2, 0)})),
        WithdrawItemAction(code="copper_ore", quantity=10),
        WithdrawItemAction(code="copper_bar", quantity=6),
    ]


def test_bank_covered_gather_pruned():
    """Need 6 copper_bar; bank has 485 ore (covers the 60 ore) -> prune the
    copper_rocks gather, keep the withdraw."""
    gd = _gd()
    goal = GatherMaterialsGoal(target_item="copper_dagger", needed={"copper_bar": 6})
    state = make_state(bank_items={"copper_ore": 485})
    kept = goal.relevant_actions(_actions(), state, gd)
    assert not any(isinstance(a, GatherAction) for a in kept)
    assert any(isinstance(a, WithdrawItemAction) and a.code == "copper_ore" for a in kept)


def test_gather_kept_when_bank_short():
    gd = _gd()
    goal = GatherMaterialsGoal(target_item="copper_dagger", needed={"copper_bar": 6})
    state = make_state(bank_items={"copper_ore": 5})
    kept = goal.relevant_actions(_actions(), state, gd)
    assert any(isinstance(a, GatherAction) for a in kept)


# --- closure sizing: both consuming goals emit gathers sized to the deficit ---


def _equippable_gd() -> GameData:
    """The `_gd()` chain with copper_dagger promoted to a craftable weapon, so
    UpgradeEquipmentGoal can commit to it as a target."""
    gd = _gd()
    gd._item_stats["copper_dagger"] = ItemStats(
        code="copper_dagger", level=1, type_="weapon", attack={"fire": 8},
        crafting_skill="weaponcrafting", crafting_level=1)
    gd._crafting_recipes["copper_dagger"] = {"copper_bar": 6}
    return gd


def test_gather_material_goal_emits_a_sized_gather():
    """6 copper_bar -> 60 copper_ore outstanding; the emitted gather must carry
    the batch, not quantity=1."""
    gd = _gd()
    goal = GatherMaterialsGoal(target_item="copper_dagger", needed={"copper_bar": 6})
    state = make_state()
    kept = goal.relevant_actions(_actions(), state, gd)
    gathers = [a for a in kept if isinstance(a, GatherAction)]
    assert gathers, "expected at least one closure gather"
    assert all(a.quantity > 1 for a in gathers), \
        f"gathers not batched: {[repr(a) for a in gathers]}"


def test_gather_material_goal_sizes_to_the_net_deficit():
    """Sizing is chain demand MINUS holdings: 55 ore banked leaves a 5 deficit,
    so the batch is 5 — not the full 60, and not the inventory cap."""
    gd = _gd()
    goal = GatherMaterialsGoal(target_item="copper_dagger", needed={"copper_bar": 6})
    state = make_state(bank_items={"copper_ore": 55})
    kept = goal.relevant_actions(_actions(), state, gd)
    gathers = [a for a in kept if isinstance(a, GatherAction)]
    assert [a.quantity for a in gathers] == [5]


def test_upgrade_equipment_goal_emits_a_sized_gather():
    gd = _equippable_gd()
    goal = UpgradeEquipmentGoal(committed_target=("copper_dagger", "weapon_slot"))
    state = make_state()
    actions = [*_actions(), EquipAction(code="copper_dagger", slot="weapon_slot")]
    kept = goal.relevant_actions(actions, state, gd)
    gathers = [a for a in kept if isinstance(a, GatherAction)]
    assert gathers, "expected at least one closure gather"
    assert all(a.quantity >= 1 for a in gathers)
    assert any(a.quantity > 1 for a in gathers), \
        f"the dagger chain needs 60 copper_ore; nothing was batched: {[repr(a) for a in gathers]}"


# --- the unknown-drop fallback is unobservable in the emitted action set ---
#
# `GatherMaterialsGoal` resolves a gather's effective drop with the shared
# `GatherAction.drop_item`, which falls back to `self.resource_code` when the
# resource has no drop-table entry. The two skips at the top of the loop
# therefore see a NAME where the old open-coded `override or
# resource_drop_item(...)` saw `None`, and `None in covered` was always False.
# Whether that changes the emitted set was argued in comments across three
# review rounds and got a different answer each time, so it is settled here
# executably instead.

_GHOST = "ghost_rocks"   # a RESOURCE code that is ALSO a recipe material code


def _unknown_drop_gd() -> GameData:
    """`widget` is crafted from `ghost_rocks` + `copper_ore`. `copper_rocks`
    drops `copper_ore` normally; `ghost_rocks` has NO drop-table entry, so its
    effective drop is `None` under the old rule and the resource code itself
    under the new one — and that code IS a closure material, which is what
    makes the fallback reachable at all."""
    gd = GameData()
    gd._item_stats = {
        _GHOST: ItemStats(code=_GHOST, level=1, type_="resource"),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        "widget": ItemStats(code="widget", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"widget": {_GHOST: 2, "copper_ore": 3}}
    gd._resource_drops = {"copper_rocks": "copper_ore"}   # no _GHOST entry
    gd._resource_locations = {"copper_rocks": [(2, 0)], _GHOST: [(3, 0)]}
    return gd


def _unknown_drop_actions() -> list:
    return [
        GatherAction(resource_code=_GHOST, locations=frozenset({(3, 0)})),
        GatherAction(resource_code="copper_rocks", locations=frozenset({(2, 0)})),
    ]


def _gather_codes(kept: list) -> set[str]:
    return {a.resource_code for a in kept if isinstance(a, GatherAction)}


def test_unknown_drop_fixture_actually_exercises_the_fallback():
    """Fixture liveness. Without all three of these the equivalence test below
    passes for the wrong reason."""
    gd = _unknown_drop_gd()
    ghost = GatherAction(resource_code=_GHOST, locations=frozenset({(3, 0)}))

    # 1. The two drop-resolution rules genuinely DISAGREE for this action.
    assert ghost.drop_item(gd) == _GHOST
    assert (ghost.drop_item_override or gd.resource_drop_item(_GHOST)) is None

    # 2. The resource code really lands in `covered`, so the early skip fires
    #    under the new rule (`None in covered` could never fire under the old).
    owned = {_GHOST: 2, "copper_ore": 3}
    assert _GHOST in fully_covered_materials("widget", 1, gd.crafting_recipes, owned)

    # 3. The downstream guard rejects it on the MISSING DROP, not on closure
    #    membership — `_GHOST` is passed as a closure material here and it is
    #    still False. This is the mechanism that makes the fallback moot.
    assert gather_serves_closure(_GHOST, None, gd.resource_drops, {_GHOST: 99}) is False


def test_unknown_drop_gather_is_excluded_under_both_drop_rules():
    """The emitted action set is IDENTICAL whichever rule resolves the drop.

    Two runs of the real goal:

    * `covered` HOLDS the resource code (bank stocked) — the new rule's early
      skip fires and drops the gather.
    * `covered` does NOT hold it (bank empty) — the early skip cannot fire,
      which is exactly the old rule's behaviour, since `None in covered` was
      False for every `covered`. The gather still never reaches `result`: the
      `elif` chain's only GatherAction arm calls `gather_serves_closure`, which
      returns False on the missing drop, and no other disjunct in that chain
      can match a GatherAction (its tags are {"gather", "produces_skill_xp"},
      so the recovery / deposit / skill_grind arms are all False, and the rest
      are isinstance checks for other action types).

    `copper_rocks` is the positive control: it is admitted in BOTH runs, so a
    wrongly-admitted gather would demonstrably show up here rather than being
    invisible to the assertion.
    """
    gd = _unknown_drop_gd()
    goal = GatherMaterialsGoal(target_item="widget", needed={"widget": 1})

    early_skip_can_fire = goal.relevant_actions(
        _unknown_drop_actions(), make_state(bank_items={_GHOST: 2}), gd)
    early_skip_cannot_fire = goal.relevant_actions(
        _unknown_drop_actions(), make_state(bank_items={}), gd)

    assert _gather_codes(early_skip_can_fire) == _gather_codes(early_skip_cannot_fire)
    assert _GHOST not in _gather_codes(early_skip_can_fire)
    assert _GHOST not in _gather_codes(early_skip_cannot_fire)
    # Positive control: gathers DO reach `result` in both runs.
    assert "copper_rocks" in _gather_codes(early_skip_can_fire)
    assert "copper_rocks" in _gather_codes(early_skip_cannot_fire)
