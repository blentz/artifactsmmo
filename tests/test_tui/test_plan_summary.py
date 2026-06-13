from rich.console import Console

from artifactsmmo_cli.ai.cycle_snapshot import RootScoreView
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.tui.plan_summary import build_plan_summary


def _text(renderable) -> str:
    console = Console(no_color=True, width=120)
    with console.capture() as cap:
        console.print(renderable)
    return cap.get()


def _gd() -> GameData:
    gd = GameData()
    gd._crafting_recipes = {
        "copper_boots": {"copper_bar": 6},
        "copper_bar": {"copper_ore": 10},
    }
    gd._item_stats = {
        "copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                  crafting_skill="gearcrafting", crafting_level=1),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                crafting_skill="mining", crafting_level=1),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    return gd


def test_obtain_chain_collapses_with_have_need():
    out = _text(build_plan_summary(
        chosen_root="ObtainItem(code='copper_boots', quantity=1)",
        ranking=[], inventory={"copper_ore": 42}, bank=None, game_data=_gd(),
        projected_cycles_to_max=None,
    ))
    # one line per item, raw-first, with [have/total]
    assert "copper_ore" in out and "42/60" in out      # need 6*10=60, have 42
    assert "copper_bar" in out and "0/6" in out
    assert "copper_boots" in out and "0/1" in out
    assert "Collect" in out and "Craft" in out
    # boots is equippable (type 'boots' in ITEM_TYPE_TO_SLOTS) -> Equip line
    assert "Equip" in out and "copper_boots" in out


def test_active_leaf_marked_now():
    out = _text(build_plan_summary(
        chosen_root="ObtainItem(code='copper_boots', quantity=1)",
        ranking=[], inventory={"copper_ore": 42}, bank=None, game_data=_gd(),
        projected_cycles_to_max=None,
    ))
    # deepest item with remaining need is copper_ore -> marked now
    assert "now" in out


def test_bank_credited_in_have():
    out = _text(build_plan_summary(
        chosen_root="ObtainItem(code='copper_boots', quantity=1)",
        ranking=[], inventory={"copper_ore": 20}, bank={"copper_ore": 40},
        game_data=_gd(), projected_cycles_to_max=None,
    ))
    assert "60/60" in out   # 20 inv + 40 bank covers the 60 needed
