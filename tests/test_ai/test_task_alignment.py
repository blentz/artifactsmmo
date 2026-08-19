"""S-047/S-048: does a HELD task's target advance progression at all?

A task is a draw, not a selection, so the whole decision is what to do with what
arrives. These pin the one question S-047 asks and the discard condition S-048
turns on — including the case that made the first implementation exactly backwards.
"""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.skill_xp_positive import GREY_SKILL_GAP
from artifactsmmo_cli.ai.task_alignment import task_advances_progression
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._monster_level = {"chicken": 1, "ogre": 20}
    gd._monster_locations = {"chicken": [(0, 1)], "ogre": [(5, 5)]}
    fill_monster_stat_defaults(gd)
    gd._item_stats = {
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource",
                               crafting_skill="woodcutting", crafting_level=1),
        "steel_bar": ItemStats(code="steel_bar", level=20, type_="resource",
                               crafting_skill="mining", crafting_level=20),
    }
    gd._crafting_recipes = {"ash_plank": {"ash_wood": 1},
                            "steel_bar": {"iron_ore": 1}}
    return gd


def _monsters(code: str, level: int):
    return make_state(level=level, task_code=code, task_type="monsters",
                      task_total=10, task_progress=0)


def _items(code: str, **skills):
    base = {"woodcutting": 1, "mining": 1}
    base.update(skills)
    return make_state(task_code=code, task_type="items", task_total=10,
                      task_progress=0, skills=base)


def test_no_task_held_advances_nothing():
    """There is nothing to judge. Reporting False here is what keeps S-048 from
    reading as a standing instruction to discard; callers gate on `task_code`."""
    assert task_advances_progression(make_state(), _gd()) is False


def test_a_monsters_task_on_a_paying_monster_advances():
    assert task_advances_progression(_monsters("ogre", 20), _gd()) is True


def test_a_monsters_task_on_a_grey_monster_advances_nothing():
    """The S-048 discard case. A level-30 character's chicken task pays no
    character xp, so the work is dead — measured live, a level-19 character's best
    beatable monster is eleven levels down and pays exactly 0."""
    assert task_advances_progression(_monsters("chicken", 30), _gd()) is False


def test_a_feasible_task_is_not_mistaken_for_a_useless_one():
    """PINS THE ERROR THE FIRST IMPLEMENTATION MADE. It asked
    `task_feasibility.task_requirement`, which answers "what must be RAISED to do
    this task" and returns None when the task is ALREADY FEASIBLE. Read as "no
    requirement, so no progression", that discarded every task the character could
    actually complete — the exact opposite of the rule."""
    state = _monsters("chicken", 1)          # feasible AND paying at level 1
    assert task_advances_progression(state, _gd()) is True


def test_an_items_task_within_the_skill_band_advances():
    assert task_advances_progression(_items("steel_bar", mining=20), _gd()) is True


def test_an_items_task_past_the_grey_skill_band_advances_nothing():
    """`skill_xp_positive` owns the band; this asserts the boundary through it
    rather than restating the constant, so the two cannot drift apart."""
    gd = _gd()
    at_edge = _items("ash_plank", woodcutting=GREY_SKILL_GAP)       # 1 + 11 - 1
    past = _items("ash_plank", woodcutting=GREY_SKILL_GAP + 1)
    assert task_advances_progression(at_edge, gd) is True
    assert task_advances_progression(past, gd) is False


def test_an_items_task_nothing_produces_advances_nothing():
    gd = _gd()
    state = _items("mystery_relic")
    assert gd.producing_requirement("mystery_relic") is None
    assert task_advances_progression(state, gd) is False


def test_an_unknown_task_type_advances_nothing():
    state = make_state(task_code="whatever", task_type="riddle", task_total=3)
    assert task_advances_progression(state, _gd()) is False


def test_a_task_with_no_total_advances_nothing():
    state = make_state(task_code="ogre", task_type="monsters", task_total=0)
    assert task_advances_progression(state, _gd()) is False
