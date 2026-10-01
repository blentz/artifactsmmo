"""`skill_is_grindable`: the "an open rung exists" predicate the walk's skill-gate
sub-task, the orphan-skill roots and the open-rung census ask (Phase 2d). It used
to be pinned through the `LevelSkill` macro's differential; the macro is gone."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.skill_grindable import skill_is_grindable
from tests.test_ai.fixtures import make_state


def _gd(resources: dict[str, tuple[str, int]]) -> GameData:
    gd = GameData()
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_drops = {code: f"{code}_drop" for code in resources}
    gd._resource_skill = dict(resources)
    gd._resource_locations = {code: [(3, 0)] for code in resources}
    gd._bank_location = (4, 0)
    return gd


def test_a_gather_rung_opens_a_skill_with_no_craft_rung() -> None:
    """Alchemy at 1 grinds by gathering sunflower: the gather arm alone."""
    gd = _gd({"sunflower_field": ("alchemy", 1)})
    assert skill_is_grindable("alchemy", 5, make_state(skills={"alchemy": 1}), gd)


def test_at_or_past_the_target_nothing_is_open() -> None:
    gd = _gd({"sunflower_field": ("alchemy", 1)})
    assert not skill_is_grindable("alchemy", 5, make_state(skills={"alchemy": 5}), gd)
    assert not skill_is_grindable("alchemy", 5, make_state(skills={"alchemy": 6}), gd)


def test_no_rung_means_no_grind() -> None:
    """Under the target but with nothing to gather or craft in the skill."""
    gd = _gd({"copper_rocks": ("mining", 1)})
    assert not skill_is_grindable("alchemy", 5, make_state(skills={"alchemy": 1}), gd)
