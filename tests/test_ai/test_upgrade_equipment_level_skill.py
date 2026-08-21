"""LevelSkill epic P3a Task 1: an under-skill CRAFTABLE equippable is now
plannable via the LevelSkill action — UpgradeEquipmentGoal sequences
`LevelSkill(gear_skill) -> ... -> Craft(gear) -> Equip(gear)`.

Before P3a, `UpgradeEquipmentGoal.is_plannable` fast-failed when the character
was under the gear's crafting_level (the pre-LevelSkill CPU guard), and its
`relevant_actions` never admitted the `skill_grind` tag — so a gear-unlock grind
had no planner-native route. This mirrors the P2 fix for `GatherMaterialsGoal`
(commits f262cec5 + ff4401ac): drop the under-skill gate and admit a SCOPED
LevelSkill (only the target's own gated (skill, level), never every grind).
"""

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.ge_fill_sell import GeFillSellOrderAction
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective


def _gd() -> GameData:
    """A craftable shield gated behind gearcrafting 5, plus a level-1
    gearcrafting rung (trinket) so `skill_grind_target` — and therefore
    `LevelSkill.is_applicable` — has an in-skill grinder to point at. gear_ore
    is a mining-gated resource drop leaf."""
    gd = GameData()
    gd._item_stats = {
        "gear_shield": ItemStats(code="gear_shield", level=5, type_="shield",
                                 crafting_skill="gearcrafting", crafting_level=5),
        "trinket": ItemStats(code="trinket", level=1, type_="resource",
                             subtype="craft", crafting_skill="gearcrafting",
                             crafting_level=1),
        "gear_ore": ItemStats(code="gear_ore", level=1, type_="resource",
                              subtype="mob"),
    }
    gd._crafting_recipes = {"gear_shield": {"gear_ore": 2}, "trinket": {"gear_ore": 1}}
    gd._resource_drops = {"gear_rocks": "gear_ore"}
    gd._resource_skill = {"gear_rocks": ("mining", 1)}
    gd._resource_locations = {"gear_rocks": [(3, 3)]}
    gd._workshop_locations = {"gearcrafting": (2, 2)}
    gd._bank_location = (0, 0)
    gd._taskmaster_location = (1, 1)
    return gd


def _under_skill_state(gd: GameData):
    """Level 5 (can wear the L5 shield), gearcrafting 1 (< the recipe's 5), the
    2 gear_ore materials already in hand (so the plan is a short
    grind->craft->equip, not a long from-scratch gather chain)."""
    return scenario_state(
        ScenarioCharacter(name="t", level=5,
                          skills={"gearcrafting": 1, "mining": 1},
                          inventory={"gear_ore": 2}), gd)


def test_is_plannable_true_when_under_gear_crafting_skill() -> None:
    """The under-skill craftable equippable is admitted: the LevelSkill action
    makes the gated final craft reachable, so is_plannable must no longer prune
    it at the crafting-skill gate."""
    gd = _gd()
    state = _under_skill_state(gd)
    goal = UpgradeEquipmentGoal(committed_target=("gear_shield", "shield_slot"))
    assert goal.is_plannable(state, gd) is True


def test_planner_sequences_level_skill_before_gear_craft() -> None:
    """With a LevelSkill(gearcrafting, 5) in the action set, the planner
    sequences the grind before Craft(gear_shield) and equips the target — the
    gear-unlock grind now routes through LevelSkill."""
    gd = _gd()
    state = _under_skill_state(gd)
    objective = CharacterObjective.from_game_data(gd)
    actions = build_actions(gd, state, objective, bank_accessible=True,
                            task_exchange_min_coins=0)
    actions.append(LevelSkill(skill="gearcrafting", target_level=5))
    goal = UpgradeEquipmentGoal(committed_target=("gear_shield", "shield_slot"))

    plan = GOAPPlanner().plan(state, goal, actions, gd, budget_seconds=10.0)

    reprs = [repr(a) for a in plan]
    craft_idx = next(i for i, a in enumerate(plan)
                     if isinstance(a, CraftAction) and a.code == "gear_shield")
    level_idx = next(i for i, a in enumerate(plan)
                     if isinstance(a, LevelSkill))
    assert level_idx < craft_idx, f"LevelSkill must precede Craft(gear_shield): {reprs}"
    assert any(isinstance(a, EquipAction) and a.code == "gear_shield"
               and a.slot == "shield_slot" for a in plan), reprs


def test_relevant_actions_scopes_level_skill_to_target_gated_skill() -> None:
    """A LevelSkill enters the search ONLY when the target's own closure
    craftable is gated behind that exact (skill, level) and the char is under
    it. An unconditional admission fans ~15 grind actions into every search and
    times out under load (the P2 ff4401ac regression) — the mining-9 grind (no
    closure craftable gated on it) must be excluded."""
    gd = _gd()
    ls_gear5 = LevelSkill(skill="gearcrafting", target_level=5)
    ls_mining9 = LevelSkill(skill="mining", target_level=9)  # irrelevant grind
    actions = [ls_gear5, ls_mining9]
    goal = UpgradeEquipmentGoal(committed_target=("gear_shield", "shield_slot"))

    # under-skill (gearcrafting 1 < 5): admits the gearcrafting grind, not mining.
    under = _under_skill_state(gd)
    admitted = goal.relevant_actions(actions, under, gd)
    assert ls_gear5 in admitted
    assert ls_mining9 not in admitted

    # at-skill (gearcrafting 5, not gated): NO LevelSkill admitted.
    at = scenario_state(
        ScenarioCharacter(name="t", level=5,
                          skills={"gearcrafting": 5, "mining": 1},
                          inventory={"gear_ore": 2}), gd)
    assert not [a for a in goal.relevant_actions(actions, at, gd)
                if isinstance(a, LevelSkill)]


def test_relevant_actions_admits_the_ge_fill_for_the_goals_own_target() -> None:
    """THE C3P0 WAIT DEADLOCK. `obtain_sources` emits a `SourceKind.GE_FILL` for
    any item with a live sell order, and that source is what tells
    `forced_craft_grind` the craft is AVOIDABLE — which zeroes this goal's
    heuristic. Nothing used to admit the matching action, so the goal was left
    with h=0 AND no access to the route that zeroed it, and an unguided search
    over a mandatory skill-grind edge timed out. `GatherMaterialsGoal`
    synthesizes this action only for a closure MATERIAL that an NPC also sells,
    and nothing sells crafted gear, so that path can never cover a goal's own
    target.

    Measured live: C3P0 held 14,532 gold against a standing 1,498-gold order for
    `adventurer_pants` and Waited for 84 consecutive cycles."""
    gd = _gd()
    gd._ge_sell_orders = {"gear_shield": ("ord-shield", 40, 3)}
    gd._grand_exchange_location = (2, 2)
    state = _under_skill_state(gd)
    goal = UpgradeEquipmentGoal(committed_target=("gear_shield", "shield_slot"))
    rel = goal.relevant_actions([], state, gd)
    fills = [a for a in rel if isinstance(a, GeFillSellOrderAction)]
    assert [(a.item_code, a.order_id, a.price, a.quantity) for a in fills] \
        == [("gear_shield", "ord-shield", 40, 1)]
    # The equip leg has to come with it, or the bought item never reaches the slot.
    assert any(isinstance(a, EquipAction) and a.code == "gear_shield"
               and a.slot == "shield_slot" for a in rel)


def test_no_ge_fill_admitted_when_no_order_stands() -> None:
    """The route is a live order, not a wish. Without one the goal is back to
    the craft chain, which is what makes the previous test meaningful rather
    than incidental."""
    gd = _gd()
    gd._grand_exchange_location = (2, 2)
    state = _under_skill_state(gd)
    goal = UpgradeEquipmentGoal(committed_target=("gear_shield", "shield_slot"))
    rel = goal.relevant_actions([], state, gd)
    assert not [a for a in rel if isinstance(a, GeFillSellOrderAction)]


def test_no_ge_fill_admitted_when_the_target_is_already_held() -> None:
    """Owned already: the withdraw/equip edges serve it and buying another copy
    is not this goal's business — the same guard the dropper-fight arm uses."""
    gd = _gd()
    gd._ge_sell_orders = {"gear_shield": ("ord-shield", 40, 3)}
    gd._grand_exchange_location = (2, 2)
    state = scenario_state(
        ScenarioCharacter(name="t", level=5,
                          skills={"gearcrafting": 1, "mining": 1},
                          inventory={"gear_ore": 2, "gear_shield": 1}), gd)
    goal = UpgradeEquipmentGoal(committed_target=("gear_shield", "shield_slot"))
    rel = goal.relevant_actions([], state, gd)
    assert not [a for a in rel if isinstance(a, GeFillSellOrderAction)]
