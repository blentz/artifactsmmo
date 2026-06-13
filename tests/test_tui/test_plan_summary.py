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
    # the SHALLOWEST pending item (copper_ore, being gathered now) gets the
    # marker — NOT the final copper_boots craft that can't start yet.
    line = next(ln for ln in out.splitlines() if "now" in ln)
    assert "copper_ore" in line
    assert "copper_boots" not in line


def test_bank_credited_in_have():
    out = _text(build_plan_summary(
        chosen_root="ObtainItem(code='copper_boots', quantity=1)",
        ranking=[], inventory={"copper_ore": 20}, bank={"copper_ore": 40},
        game_data=_gd(), projected_cycles_to_max=None,
    ))
    assert "60/60" in out   # 20 inv + 40 bank covers the 60 needed


def test_none_root_empty_state():
    out = _text(build_plan_summary(None, [], {}, None, _gd(), None))
    assert "No committed objective" in out


def test_reach_char_level_line():
    out = _text(build_plan_summary(
        "ReachCharLevel(level=3)", [], {}, None, _gd(), None,
        ))
    assert "char XP" in out and "L3" in out


def test_reach_skill_level_line():
    out = _text(build_plan_summary("ReachSkillLevel(skill='gearcrafting', level=5)",
                                   [], {}, None, _gd(), None))
    assert "gearcrafting" in out and "L5" in out


def test_header_and_eta_and_alternatives():
    ranking = [
        RootScoreView(root_repr="ObtainItem(code='copper_boots', quantity=1)",
                      category="gear", score=2.5),
        RootScoreView(root_repr="ReachCharLevel(level=3)", category="char_level", score=1.48),
    ]
    out = _text(build_plan_summary(
        "ObtainItem(code='copper_boots', quantity=1)", ranking,
        {"copper_ore": 42}, None, _gd(), 18.0))
    assert "COMMITTED" in out and "copper_boots" in out
    assert "ETA" in out and "18" in out
    assert "ALTERNATIVES" in out and "ReachCharLevel" in out and "1.48" in out
    # the committed root is NOT repeated in the alternatives list


def test_pursue_task_line():
    out = _text(build_plan_summary(
        "PursueTask(task_code='cook_beef')", [], {}, None, _gd(), None,
        task_code="cook_beef", task_progress=3, task_total=10))
    assert "Task cook_beef" in out and "3/10" in out


def test_unrecognized_root_falls_back_to_plain_plan_line():
    out = _text(build_plan_summary("MysteryRoot(x=1)", [], {}, None, _gd(), None))
    assert "Plan:" in out and "MysteryRoot" in out
