"""GearLatch: set on level-up or predicted-winnable fight loss; clear when gear is
level-appropriate; monotone (stays set until clear holds)."""
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_latch import GearLatch
from tests.test_ai.fixtures import make_state


def _gd_with_boots():
    gd = GameData()
    gd._item_stats = {"copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                                crafting_skill="gearcrafting", crafting_level=1)}
    gd._crafting_recipes = {"copper_boots": {"copper_bar": 8}, "copper_bar": {"copper_ore": 10}}
    return gd


def test_starts_inactive():
    assert GearLatch().active is False


def test_sets_on_level_up():
    latch = GearLatch()
    latch.update(prev_level=4, state=make_state(level=5), last_outcome="ok", game_data=_gd_with_boots())
    assert latch.active is True


def test_sets_on_fight_loss():
    latch = GearLatch()
    latch.update(prev_level=4, state=make_state(level=4), last_outcome="error:fight_lost",
                 game_data=_gd_with_boots())
    assert latch.active is True


def test_clears_when_no_craftable_upgrade():
    latch = GearLatch()
    empty_gd = GameData()
    empty_gd._item_stats = {}
    empty_gd._crafting_recipes = {}
    latch.update(prev_level=4, state=make_state(level=5), last_outcome="ok", game_data=empty_gd)
    assert latch.active is False  # set by level-up but immediately cleared: nothing to craft


def test_monotone_stays_set_until_clear():
    latch = GearLatch()
    gd = _gd_with_boots()
    latch.update(prev_level=4, state=make_state(level=5), last_outcome="ok", game_data=gd)
    assert latch.active is True
    # next cycle, no level-up, no loss, upgrade still available → stays set
    latch.update(prev_level=5, state=make_state(level=5), last_outcome="ok", game_data=gd)
    assert latch.active is True
