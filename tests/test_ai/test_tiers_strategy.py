import pytest
from sqlmodel import Session

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.models import Session as SessionModel
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality
from artifactsmmo_cli.ai.tiers.strategy import (
    BALANCE_MAX,
    BALANCE_MIN,
    CHAR_MARGINAL,
    GEAR_EQUIP_SCALE,
    LEARN_SAMPLE_FULL,
    LEARN_W_MAX,
    PRIOR_CHAR_LEVEL,
    PRIOR_COMBAT_CRAFT_SKILL,
    PRIOR_COMBAT_GEAR,
    PRIOR_CONSUMABLE_SKILL,
    PRIOR_GATHER_SKILL,
    PRIOR_UTILITY_GEAR,
    SKILL_MARGINAL,
    XP_RATE_REFERENCE,
    StrategyEngine,
    actionable_step,
    desired_state_of,
    is_reachable,
    root_category,
    root_cost,
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
    # Gear-free world so only char-level vs skills compete.
    # Skills: alchemy=5 (leader), others=1 → laggards get balancing boost (raw=1.5).
    # BalancedPersonality: char_level=1.0 > weaponcrafting=0.6*0.2*1.5=0.18 → char wins.
    # SkillFirst (10x weight): weaponcrafting=0.6*0.2*1.5*10=1.8 > 1.0 → skill wins.
    gd = GameData()
    gd._monster_level = {"chicken": 1}  # char level reachable (combat-capable)
    obj = CharacterObjective.from_game_data(gd)
    skill_levels = {s: 1 for s in obj.target_skill_levels}
    skill_levels["alchemy"] = 5  # make alchemy the leader so others are laggards
    state = make_state(level=1, skills=skill_levels)

    class SkillFirst:
        def category_weight(self, category: str) -> float:
            return 10.0 if category == "skills" else 1.0

    assert root_category(StrategyEngine(obj, BalancedPersonality()).decide(state, gd).chosen_root) == "char_level"
    assert root_category(StrategyEngine(obj, SkillFirst()).decide(state, gd).chosen_root) == "skills"


def test_unmet_closure_size_dedups_shared_prereq():
    # X -> {A, B}; A -> {C}; B -> {C}: C is reached twice and deduped.
    gd = GameData()
    gd._crafting_recipes = {"X": {"A": 1, "B": 1}, "A": {"C": 1}, "B": {"C": 1}}
    gd._item_stats = {c: ItemStats(code=c, level=1, type_="resource") for c in "XABC"}
    assert unmet_closure_size(ObtainItem("X"), make_state(), gd) == 4  # X,A,B,C once each


def test_value_zero_for_unknown_node_type():
    gd = _gd()
    obj = CharacterObjective.from_game_data(gd)
    eng = StrategyEngine(obj, BalancedPersonality())

    class _Dummy:
        def is_satisfied(self, state, game_data) -> bool:
            return False

    assert eng._value(_Dummy(), make_state(), gd) == 0.0


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


def test_root_cost_is_levels_remaining_for_leaf_goals():
    gd = _gd()
    assert root_cost(ReachSkillLevel("mining", 50), make_state(skills={"mining": 3}), gd) == 47
    assert root_cost(ReachCharLevel(50), make_state(level=3), gd) == 47
    assert root_cost(ReachSkillLevel("mining", 5), make_state(skills={"mining": 5}), gd) == 1  # floor


def test_root_cost_for_gear_uses_closure_size():
    gd = _gd()
    assert root_cost(ObtainItem("copper_dagger"), make_state(), gd) == 3


def test_rootscore_instrumental_always_false():
    gd = _gd()
    obj = CharacterObjective.from_game_data(gd)
    d = StrategyEngine(obj, BalancedPersonality()).decide(make_state(level=5), gd)
    assert all(rs.instrumental is False for rs in d.ranking)


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


def _reach_gd():
    gd = GameData()
    gd._item_stats = {
        "drop_blade": ItemStats(code="drop_blade", level=1, type_="weapon", attack={"f": 50}),
        "iron_helm": ItemStats(code="iron_helm", level=1, type_="helmet", resistance={"fire": 10},
                               crafting_skill="gearcrafting", crafting_level=1),
        "iron_bar": ItemStats(code="iron_bar", level=1, type_="resource"),
        "iron_ore": ItemStats(code="iron_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"iron_helm": {"iron_bar": 5}, "iron_bar": {"iron_ore": 3}}
    gd._resource_drops = {"iron_rocks": "iron_ore"}
    gd._resource_skill = {"iron_rocks": ("mining", 1)}
    gd._monster_level = {"chicken": 1}
    return gd


def test_producible():
    from artifactsmmo_cli.ai.tiers.strategy import _producible
    gd = _reach_gd()
    assert _producible("iron_helm", gd) is True   # craftable
    assert _producible("iron_ore", gd) is True     # gatherable (iron_rocks drops it)
    assert _producible("drop_blade", gd) is False   # no recipe, no drop


def test_is_reachable_gatherable_and_craftable_chain():
    gd = _reach_gd()
    s = make_state(level=1)
    assert is_reachable(ObtainItem("iron_ore"), s, gd) is True
    assert is_reachable(ObtainItem("iron_helm"), s, gd) is True


def test_is_reachable_false_for_unproducible_and_blocked_material():
    gd = _reach_gd()
    s = make_state(level=1)
    assert is_reachable(ObtainItem("drop_blade"), s, gd) is False
    gd._crafting_recipes["cursed_helm"] = {"drop_blade": 1}
    gd._item_stats["cursed_helm"] = ItemStats(code="cursed_helm", level=1, type_="helmet")
    assert is_reachable(ObtainItem("cursed_helm"), s, gd) is False


def test_is_reachable_skill_and_char_level():
    gd = _reach_gd()
    assert is_reachable(ReachSkillLevel("mining", 50), make_state(level=1), gd) is True
    assert is_reachable(ReachCharLevel(50), make_state(level=1), gd) is True


def test_is_reachable_char_level_false_when_underequipped_and_no_makeable_weapon():
    gd = GameData()
    gd._monster_level = {"dragon": 40}
    gd._item_stats = {"drop_blade": ItemStats(code="drop_blade", level=1, type_="weapon", attack={"f": 9})}
    assert is_reachable(ReachCharLevel(50), make_state(level=1), gd) is False


def test_is_reachable_satisfied_and_cycle():
    gd = _reach_gd()
    assert is_reachable(ReachCharLevel(1), make_state(level=5), gd) is True
    cyc = GameData()
    cyc._crafting_recipes = {"a": {"a": 1}}
    cyc._item_stats = {"a": ItemStats(code="a", level=1, type_="resource")}
    assert is_reachable(ObtainItem("a"), make_state(), cyc) is False


def test_actionable_step_none_for_unproducible_leaf():
    gd = _reach_gd()
    assert actionable_step(ObtainItem("drop_blade"), make_state(), gd) is None


def test_decide_skips_root_unreachable_in_current_game_data():
    # Objective built from data where iron_helm is craftable (attainable → targeted),
    # but decide() runs against game data lacking that production → is_reachable
    # False → the root is skipped (defensive filter).
    gd_full = _reach_gd()
    obj = CharacterObjective.from_game_data(gd_full)
    assert obj.target_gear.get("helmet_slot") == "iron_helm"
    gd_empty = GameData()
    gd_empty._monster_level = {"chicken": 1}  # char reachable; iron_helm not producible here
    d = StrategyEngine(obj, BalancedPersonality()).decide(make_state(level=5), gd_empty)
    assert all("iron_helm" not in rs.root_repr for rs in d.ranking)


def test_unattainable_gear_not_targeted_but_craftable_is():
    gd = _reach_gd()  # drop_blade unattainable; iron_helm craftable-from-gatherables
    obj = CharacterObjective.from_game_data(gd)
    assert "weapon_slot" not in obj.target_gear           # drop_blade excluded at build
    assert obj.target_gear.get("helmet_slot") == "iron_helm"
    d = StrategyEngine(obj, BalancedPersonality()).decide(make_state(level=5), gd)
    reprs = [rs.root_repr for rs in d.ranking]
    assert any("iron_helm" in r for r in reprs)            # craftable gear is a candidate
    assert all("drop_blade" not in r for r in reprs)


def _eng(gd, target_gear=None):
    obj = CharacterObjective.from_game_data(gd)
    if target_gear is not None:
        obj = CharacterObjective(target_char_level=50,
                                 target_skill_levels=obj.target_skill_levels,
                                 target_gear=target_gear,
                                 _game_data=gd)
    return StrategyEngine(obj, BalancedPersonality())


class TestBalancing:
    def test_leader_suppressed(self):
        eng = _eng(GameData())
        state = make_state(skills={"alchemy": 5, "mining": 1, "woodcutting": 1, "fishing": 1,
                                   "weaponcrafting": 1, "gearcrafting": 1, "jewelrycrafting": 1, "cooking": 1})
        assert eng._balancing(ReachSkillLevel("alchemy", 50), state) == BALANCE_MIN

    def test_laggard_boosted(self):
        eng = _eng(GameData())
        state = make_state(skills={"alchemy": 7, "cooking": 1, "mining": 1, "woodcutting": 1,
                                   "fishing": 1, "weaponcrafting": 1, "gearcrafting": 1, "jewelrycrafting": 1})
        assert eng._balancing(ReachSkillLevel("cooking", 50), state) == BALANCE_MAX

    def test_two_behind_neutral(self):
        eng = _eng(GameData())
        state = make_state(skills={"alchemy": 5, "cooking": 3, "mining": 1, "woodcutting": 1,
                                   "fishing": 1, "weaponcrafting": 1, "gearcrafting": 1, "jewelrycrafting": 1})
        assert eng._balancing(ReachSkillLevel("cooking", 50), state) == 1.0

    def test_balancing_one_for_gear_and_char(self):
        eng = _eng(GameData())
        st = make_state()
        assert eng._balancing(ReachCharLevel(50), st) == 1.0
        assert eng._balancing(ObtainItem("x"), st) == 1.0


class TestBasePrior:
    def test_char_and_skill_family_priors(self):
        eng = _eng(GameData())
        assert eng._base_prior(ReachCharLevel(50)) == PRIOR_CHAR_LEVEL
        assert eng._base_prior(ReachSkillLevel("weaponcrafting", 50)) == PRIOR_COMBAT_CRAFT_SKILL
        assert eng._base_prior(ReachSkillLevel("mining", 50)) == PRIOR_GATHER_SKILL
        assert eng._base_prior(ReachSkillLevel("alchemy", 50)) == PRIOR_CONSUMABLE_SKILL

    def test_unknown_skill_prior_is_zero(self):
        eng = _eng(GameData())
        assert eng._base_prior(ReachSkillLevel("tailoring", 50)) == 0.0   # not a known skill

    def test_gear_prior_combat_vs_utility(self):
        gd = GameData()
        gd._item_stats = {"copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon"),
                          "small_potion": ItemStats(code="small_potion", level=1, type_="utility")}
        eng = _eng(gd, target_gear={"weapon_slot": "copper_dagger", "utility1_slot": "small_potion"})
        assert eng._base_prior(ObtainItem("copper_dagger")) == PRIOR_COMBAT_GEAR
        assert eng._base_prior(ObtainItem("small_potion")) == PRIOR_UTILITY_GEAR


class TestMarginal:
    def test_gear_marginal_gain_over_empty_slot(self):
        gd = GameData()
        gd._item_stats = {"copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon", attack={"fire": 6})}
        eng = _eng(gd, target_gear={"weapon_slot": "copper_dagger"})
        state = make_state(equipment={"weapon_slot": None})
        m = eng._marginal(ObtainItem("copper_dagger"), state, gd)
        assert m == min(1.0, equip_value(gd.item_stats("copper_dagger")) / GEAR_EQUIP_SCALE)
        assert m > 0

    def test_gear_marginal_zero_when_no_gain(self):
        gd = GameData()
        gd._item_stats = {"wand": ItemStats(code="wand", level=1, type_="weapon", attack={"fire": 3})}
        eng = _eng(gd, target_gear={"weapon_slot": "wand"})
        state = make_state(equipment={"weapon_slot": "wand"})
        assert eng._marginal(ObtainItem("wand"), state, gd) == 0.0

    def test_char_and_skill_marginal_constants(self):
        eng = _eng(GameData())
        st = make_state()
        assert eng._marginal(ReachCharLevel(50), st, GameData()) == CHAR_MARGINAL
        assert eng._marginal(ReachSkillLevel("mining", 50), st, GameData()) == SKILL_MARGINAL

    def test_gear_marginal_unknown_item_returns_zero(self):
        eng = _eng(GameData())   # empty item_stats
        assert eng._marginal(ObtainItem("nonexistent"), make_state(), GameData()) == 0.0


class TestAntiDegeneracy:
    def test_gear_outranks_runaway_leading_skill(self):
        gd = GameData()
        gd._item_stats = {
            "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                       attack={"fire": 6}, crafting_skill="weaponcrafting", crafting_level=1),
            "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
        }
        gd._crafting_recipes = {"copper_dagger": {"copper_bar": 6}, "copper_bar": {"copper_ore": 10}}
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        gd._resource_skill = {"copper_rocks": ("mining", 1)}
        eng = _eng(gd, target_gear={"weapon_slot": "copper_dagger"})
        state = make_state(level=2, equipment={"weapon_slot": None},
                           skills={"alchemy": 5, "mining": 3, "woodcutting": 1, "fishing": 1,
                                   "weaponcrafting": 1, "gearcrafting": 1, "jewelrycrafting": 1, "cooking": 1})
        d = eng.decide(state, gd)
        assert root_category(d.chosen_root) in ("gear", "char_level")
        assert d.chosen_root != ReachSkillLevel("alchemy", 50)

    def test_lagging_skill_outranks_leader(self):
        gd = GameData()
        eng = _eng(gd)
        state = make_state(level=1, skills={"alchemy": 7, "cooking": 1, "mining": 1, "woodcutting": 1,
                                            "fishing": 1, "weaponcrafting": 1, "gearcrafting": 1, "jewelrycrafting": 1})
        d = eng.decide(state, gd)
        skill_scores = {rs.root_repr: rs.score for rs in d.ranking if "ReachSkillLevel" in rs.root_repr}
        alchemy = skill_scores.get("ReachSkillLevel(skill='alchemy', level=50)", 0.0)
        assert max(skill_scores.values()) > alchemy   # a laggard beats the leader


class TestValueComposition:
    def test_value_is_prior_times_marginal_times_balancing(self):
        eng = _eng(GameData())
        state = make_state(skills={"alchemy": 5, "cooking": 1, "mining": 1, "woodcutting": 1,
                                   "fishing": 1, "weaponcrafting": 1, "gearcrafting": 1, "jewelrycrafting": 1})
        root = ReachSkillLevel("alchemy", 50)
        expected = eng._base_prior(root) * eng._marginal(root, state, GameData()) * eng._balancing(root, state)
        assert eng._value(root, state, GameData()) == expected


class TestLearnedBlend:
    def test_no_history_is_pure_heuristic(self):
        eng = _eng(GameData())
        assert eng._learned_blend(ReachCharLevel(50), 1.0, None, None) == 1.0

    def test_blend_only_applies_to_char_level(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "v.db"), character="hero")
        eng = _eng(GameData())
        try:
            assert eng._learned_blend(ReachSkillLevel("alchemy", 50), 0.3, store, "chicken") == 0.3
            assert eng._learned_blend(ObtainItem("copper_dagger"), 0.8, store, "chicken") == 0.8
        finally:
            store.close()

    def test_char_level_blended_with_observed_xp(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "v.db"), character="hero")
        store.start_session()
        with Session(store._engine) as s:
            s.add(SessionModel(session_id=store._session_id, started_at="2026-05-24T00:00:00Z", character="hero"))
            for i in range(LEARN_SAMPLE_FULL):
                s.add(Cycle(session_id=store._session_id, ts=f"2026-05-24T00:{i:02d}:00Z", cycle_index=i,
                            character="hero", selected_goal="FarmMonster(chicken)", action_repr="Fight(chicken)",
                            action_class="FightAction", outcome="ok", delta_xp=int(XP_RATE_REFERENCE),
                            delta_gold=0, delta_hp=0, delta_inv_used=0, task_progress=0, task_total=0))
            s.commit()
        eng = _eng(GameData())
        try:
            # heuristic 0.4 < normalized observed (~1.0); full samples -> w=LEARN_W_MAX -> blended up
            blended = eng._learned_blend(ReachCharLevel(50), 0.4, store, "chicken")
            expected = (1 - LEARN_W_MAX) * 0.4 + LEARN_W_MAX * 1.0
            assert blended == pytest.approx(expected)
        finally:
            store.close()

    def test_char_level_suppressed_by_low_observed_xp(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "low.db"), character="hero")
        store.start_session()
        with Session(store._engine) as s:
            s.add(SessionModel(session_id=store._session_id, started_at="2026-05-24T00:00:00Z", character="hero"))
            for i in range(LEARN_SAMPLE_FULL):
                s.add(Cycle(session_id=store._session_id, ts=f"2026-05-24T00:{i:02d}:00Z", cycle_index=i,
                            character="hero", selected_goal="FarmMonster(chicken)", action_repr="Fight(chicken)",
                            action_class="FightAction", outcome="ok", delta_xp=2,
                            delta_gold=0, delta_hp=0, delta_inv_used=0, task_progress=0, task_total=0))
            s.commit()
        eng = _eng(GameData())
        try:
            # heuristic 1.0, normalized = 2/10 = 0.2, w=0.5 -> (0.5)(1.0)+(0.5)(0.2)=0.6 < 1.0
            blended = eng._learned_blend(ReachCharLevel(50), 1.0, store, "chicken")
            assert blended < 1.0
            assert blended == pytest.approx((1 - LEARN_W_MAX) * 1.0 + LEARN_W_MAX * (2 / XP_RATE_REFERENCE))
        finally:
            store.close()

    def test_char_level_cold_start_returns_value(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "cold.db"), character="hero")
        eng = _eng(GameData())
        try:
            assert eng._learned_blend(ReachCharLevel(50), 1.0, store, "chicken") == 1.0
        finally:
            store.close()


class TestGearGatedSkillInheritsValue:
    def test_skill_gated_gear_step_is_scored_under_gear_root(self):
        # copper_dagger needs weaponcrafting L3; char has weaponcrafting 1 and the
        # materials ready -> the gear root's actionable_step is the skill gate, and
        # it is scored at the gear root's value (combat prior * equip-gain), NOT the
        # skill's 0.2 standalone prior.
        gd = GameData()
        gd._item_stats = {
            "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                       attack={"fire": 6}, crafting_skill="weaponcrafting", crafting_level=3),
            "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
        }
        gd._crafting_recipes = {"copper_dagger": {"copper_bar": 6}}
        gd._resource_drops = {}
        gd._resource_skill = {}
        eng = _eng(gd, target_gear={"weapon_slot": "copper_dagger"})
        state = make_state(equipment={"weapon_slot": None},
                           inventory={"copper_bar": 6},
                           skills={"weaponcrafting": 1, "alchemy": 1, "mining": 1, "woodcutting": 1,
                                   "fishing": 1, "gearcrafting": 1, "jewelrycrafting": 1, "cooking": 1})
        d = eng.decide(state, gd)
        gear_rs = next((rs for rs in d.ranking
                        if rs.root_repr == "ObtainItem(code='copper_dagger', quantity=1)"), None)
        assert gear_rs is not None
        assert gear_rs.step_repr == "ReachSkillLevel(skill='weaponcrafting', level=3)"
        # value inherited from the gear root, not the skill's standalone 0.2 prior
        assert gear_rs.score == eng._value(ObtainItem("copper_dagger"), state, gd)
