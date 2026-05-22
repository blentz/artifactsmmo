from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality
from artifactsmmo_cli.ai.tiers.strategy import (
    StrategyEngine,
    actionable_step,
    desired_state_of,
    root_category,
    unmet_closure_size,
)
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   attack={"fire": 12}, crafting_skill="weaponcrafting", crafting_level=1),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"copper_dagger": {"copper_bar": 6}, "copper_bar": {"copper_ore": 10}}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    gd._monster_level = {"chicken": 1}
    return gd


def test_actionable_step_descends_to_ready_node():
    gd = _gd()
    step = actionable_step(ObtainItem("copper_dagger"), make_state(), gd)
    assert step == ObtainItem("copper_ore", 10)


def test_actionable_step_blocked_returns_none():
    gd = GameData()
    gd._crafting_recipes = {"a": {"a": 1}}  # self-referential, no gather/leaf path
    gd._item_stats = {"a": ItemStats(code="a", level=1, type_="resource")}
    assert actionable_step(ObtainItem("a"), make_state(), gd) is None


def test_unmet_closure_size_counts_unmet_nodes():
    gd = _gd()
    assert unmet_closure_size(ObtainItem("copper_dagger"), make_state(), gd) == 3
    assert unmet_closure_size(ObtainItem("copper_ore"), make_state(), gd) == 1


def test_root_category():
    assert root_category(ReachCharLevel(50)) == "char_level"
    assert root_category(ReachSkillLevel("mining", 50)) == "skills"
    assert root_category(ObtainItem("x")) == "gear"


def test_desired_state_of():
    assert desired_state_of(ObtainItem("copper_ore", 6)) == {"have": {"copper_ore": 6}}
    assert desired_state_of(ReachSkillLevel("mining", 7)) == {"skill": {"mining": 7}}
    assert desired_state_of(ReachCharLevel(12)) == {"level": 12}
    assert desired_state_of(None) == {}


def test_decide_skips_satisfied_and_ranks_reachable():
    gd = _gd()
    obj = CharacterObjective.from_game_data(gd)
    eng = StrategyEngine(objective=obj, personality=BalancedPersonality())
    d = eng.decide(make_state(level=5, skills={"mining": 3}), gd)
    assert d.chosen_root is not None
    assert d.chosen_step is not None
    assert d.desired_state
    assert all(rs.cost >= 1 for rs in d.ranking)


def test_decide_hp_interrupt_flag_only():
    gd = _gd()
    eng = StrategyEngine(objective=CharacterObjective.from_game_data(gd),
                         personality=BalancedPersonality())
    low = make_state(level=5, hp=10, max_hp=100)   # 10% < 25%
    assert eng.decide(low, gd).interrupt == "restore_hp"
    ok = make_state(level=5, hp=90, max_hp=100)
    assert eng.decide(ok, gd).interrupt is None


def test_personality_reweighting_changes_choice():
    gd = _gd()
    obj = CharacterObjective.from_game_data(gd)
    state = make_state(level=49, skills={s: 1 for s in obj.target_skill_levels})

    class SkillFirst:
        def category_weight(self, category: str) -> float:
            return 10.0 if category == "skills" else 1.0

    skill_choice = StrategyEngine(obj, SkillFirst()).decide(state, gd).chosen_root
    assert root_category(skill_choice) == "skills"


def test_unmet_closure_size_dedups_shared_prereq():
    # X -> {A, B}; A -> {C}; B -> {C}: C is reached twice and deduped.
    gd = GameData()
    gd._crafting_recipes = {"X": {"A": 1, "B": 1}, "A": {"C": 1}, "B": {"C": 1}}
    gd._item_stats = {c: ItemStats(code=c, level=1, type_="resource") for c in "XABC"}
    assert unmet_closure_size(ObtainItem("X"), make_state(), gd) == 4  # X,A,B,C once each


def test_contribution_zero_for_unknown_node_type():
    gd = _gd()
    obj = CharacterObjective.from_game_data(gd)
    eng = StrategyEngine(obj, BalancedPersonality())

    class _Dummy:
        def is_satisfied(self, state, game_data) -> bool:
            return False

    assert eng._contribution(_Dummy(), obj.gap(make_state()), gd) == 0.0


def test_decide_skips_blocked_unmet_root():
    # A weapon whose only recipe is self-referential → its gear root is unmet
    # but has no actionable step, so decide skips it (the `step is None` path).
    gd = GameData()
    gd._monster_level = {"chicken": 1}
    gd._item_stats = {"cursed_blade": ItemStats(code="cursed_blade", level=1, type_="weapon", attack={"f": 5})}
    gd._crafting_recipes = {"cursed_blade": {"cursed_blade": 1}}
    obj = CharacterObjective.from_game_data(gd)
    eng = StrategyEngine(obj, BalancedPersonality())
    d = eng.decide(make_state(level=5), gd)
    # the cursed_blade gear root is excluded from ranking (blocked)
    assert all("cursed_blade" not in rs.root_repr for rs in d.ranking)
    # but other roots (skills/level) still produce a decision
    assert d.chosen_root is not None


def test_decide_empty_when_nothing_reachable():
    gd = GameData()
    obj = CharacterObjective.from_game_data(gd)
    eng = StrategyEngine(obj, BalancedPersonality())
    maxed = make_state(level=50, skills={s: 50 for s in obj.target_skill_levels})
    d = eng.decide(maxed, gd)
    assert d.chosen_root is None
    assert d.desired_state == {}
    td = d.to_trace()
    assert td["chosen_root"] is None and td["ranking"] == []
