from fractions import Fraction

import pytest
from sqlmodel import Session

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.models import Session as SessionModel
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.strategic_value import strategic_value
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality
from artifactsmmo_cli.ai.tiers.strategy import (
    BALANCE_MAX,
    BALANCE_MIN,
    CHAR_GAP_PER_LEVEL,
    CHAR_GAP_PER_LEVEL_GEARED,
    CHAR_MARGINAL,
    EMPTY_SLOT_URGENCY,
    GEAR_EQUIP_SCALE,
    LEARN_SAMPLE_FULL,
    LEARN_W_MAX,
    POTION_SUPPLY_URGENCY,
    PRIOR_CHAR_LEVEL,
    PRIOR_COMBAT_CRAFT_SKILL,
    PRIOR_COMBAT_GEAR,
    PRIOR_CONSUMABLE_SKILL,
    PRIOR_GATHER_SKILL,
    PRIOR_UTILITY_GEAR,
    SKILL_GAP_CAP,
    SKILL_GAP_PER_LEVEL,
    SKILL_MARGINAL,
    STICKY_DOMINANCE_RATIO,
    XP_RATE_REFERENCE,
    StrategyEngine,
    _producible,
    actionable_step,
    desired_state_of,
    is_reachable,
    root_category,
    root_cost,
    unmet_closure_size,
)
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_skill_target_curve import _gd_with_recipes


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
    fill_monster_stat_defaults(gd)
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
    # Gear-free world so only char-level vs endgame skills compete. All crafting
    # skills sit AT the near-term bootstrap target (5) so the gap-proportional
    # catch-up boost is inert (gap 0) — this isolates the char-vs-skill
    # personality comparison on the flat endgame-50 marginal, as intended.
    # Skills: alchemy=9 (leader), laggards at 5 → balancing raw=1.5 (gap 4).
    # BalancedPersonality: char_level=1.48 > skill=0.6*0.2*1.5=0.18 → char wins.
    # SkillFirst (10x weight): skill=0.6*0.2*1.5*10=1.8 > 1.48 → skill wins.
    gd = GameData()
    gd._monster_level = {"chicken": 1}  # char level reachable (combat-capable)
    fill_monster_stat_defaults(gd)
    obj = CharacterObjective.from_game_data(gd)
    skill_levels = {s: 5 for s in obj.target_skill_levels}
    skill_levels["alchemy"] = 9  # leader, putting laggards 4 behind (balancing boost)
    state = make_state(level=1, skills=skill_levels)

    class SkillFirst:
        def category_weight(self, category: str) -> Fraction:
            # P4a: Personality.category_weight returns exact Fractions.
            return Fraction(10) if category == "skills" else Fraction(1)

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
    fill_monster_stat_defaults(gd)
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


def _gd_potions() -> GameData:
    """GameData with a heal potion (alchemy L5) and a non-heal utility item.

    fire_boost_potion has a positive equip-gain (resistance={"fire":20} →
    combat_raw > 0 → strategic_value > 0) but hp_restore == 0.  Without
    _consumable_effect_codes populated, stats_is_combat_bearing would return
    True for fire_boost_potion (resistance is non-empty), and consumable_types
    would be empty, causing combat_gear_types to (mis-)include "utility".  We
    seed _consumable_effect_codes with a boost_res_ prefix code so that
    consumable_types correctly contains "utility", matching production where the
    API populates effect codes for every consumable item.
    """
    gd = GameData()
    gd._item_stats = {
        "small_health_potion": ItemStats(
            code="small_health_potion", level=1, type_="utility",
            hp_restore=60, crafting_skill="alchemy", crafting_level=5),
        "sunflower": ItemStats(code="sunflower", level=1, type_="resource"),
        "fire_boost_potion": ItemStats(
            code="fire_boost_potion", level=1, type_="utility",
            hp_restore=0, resistance={"fire": 20},
            crafting_skill="alchemy", crafting_level=10),
    }
    # Seed consumable effect codes so consumable_types includes "utility".
    # "boost_res_fire" matches the _CONSUMABLE_PREFIX ("boost_res_") in
    # gear_taxonomy_core, making is_consumable() return True for
    # fire_boost_potion.  This mirrors production: the API supplies effect
    # codes for every consumable, keeping utility out of combat_gear_types
    # even when a utility item carries resistance stats.
    gd._consumable_effect_codes = {"fire_boost_potion": ["boost_res_fire"]}
    gd._crafting_recipes = {"small_health_potion": {"sunflower": 3}}
    gd._resource_drops = {"sunflower_field": "sunflower"}
    gd._resource_skill = {"sunflower_field": ("alchemy", 1)}
    gd._monster_level = {"chicken": 1}  # mirror _gd() so from_game_data has a combat monster
    fill_monster_stat_defaults(gd)
    return gd


class TestPotionSupplyUrgency:
    def test_constant_ties_empty_combat_slot(self):
        # POTION_SUPPLY_URGENCY applied to the utility prior lands exactly on the
        # empty-combat-slot score (2.5).
        assert PRIOR_UTILITY_GEAR * POTION_SUPPLY_URGENCY == PRIOR_COMBAT_GEAR * EMPTY_SLOT_URGENCY
        assert PRIOR_UTILITY_GEAR * POTION_SUPPLY_URGENCY == Fraction(5, 2)

    def test_under_baseline_heal_potion_scores_bootstrap_band(self):
        gd = _gd_potions()
        eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
        state = make_state(level=5)  # alchemy 1, utility slots empty, qty 0 < baseline 5
        root = ObtainItem("small_health_potion", slot="utility1_slot")
        assert eng._value(root, state, gd) == Fraction(5, 2)

    def test_at_baseline_no_boost(self):
        gd = _gd_potions()
        eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
        state = make_state(
            level=5,
            equipment={**make_state().equipment, "utility1_slot": "small_health_potion"},
            utility1_slot_quantity=5,  # == baseline at L5
        )
        root = ObtainItem("small_health_potion", slot="utility1_slot")
        assert eng._value(root, state, gd) < Fraction(5, 2)

    def test_non_heal_utility_not_boosted(self):
        # fire_boost_potion has resistance={"fire":20} → positive equip-gain
        # (combat_raw > 0 → strategic_value > 0 → gain > 0 → marginal > 0).
        # Despite the positive equip-gain the potion-supply gate must NOT fire
        # because hp_restore == 0.  The two-part assertion below proves the
        # gate discriminates on hp_restore specifically, not on "item has no
        # stats": score > 0 confirms positive gain exists; score < Fraction(5,2)
        # confirms the potion-supply urgency multiplier was not applied.
        gd = _gd_potions()
        eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
        state = make_state(level=5)  # fire_boost_potion slot empty, hp_restore == 0
        root = ObtainItem("fire_boost_potion", slot="utility1_slot")
        score = eng._value(root, state, gd)
        assert score > 0             # positive equip-gain (resistance → combat_raw > 0)
        assert score < Fraction(5, 2)  # hp_restore == 0 → NOT boosted by potion gate

    def test_baseline_is_level_scaled(self):
        gd = _gd_potions()
        eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
        root = ObtainItem("small_health_potion", slot="utility1_slot")
        # 10 equipped: below the L45 baseline (100) → boosted; at/above the L5
        # baseline (5) → not boosted. Same equipped qty, opposite result ⇒ the
        # threshold follows potion_baseline_pure, not a constant.
        equip = {**make_state().equipment, "utility1_slot": "small_health_potion"}
        hi = make_state(level=45, equipment=equip, utility1_slot_quantity=10)
        lo = make_state(level=5, equipment=equip, utility1_slot_quantity=10)
        assert eng._value(root, hi, gd) == Fraction(5, 2)
        assert eng._value(root, lo, gd) < Fraction(5, 2)


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
    fill_monster_stat_defaults(gd)
    return gd


def test_producible():
    from artifactsmmo_cli.ai.tiers.strategy import _producible
    gd = _reach_gd()
    s = make_state(level=1)
    assert _producible("iron_helm", s, gd) is True   # craftable
    assert _producible("iron_ore", s, gd) is True     # gatherable (iron_rocks drops it)
    assert _producible("drop_blade", s, gd) is False   # no recipe, drop, or winnable monster


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
    # ReachCharLevel reachable because the player can beat a monster once it can
    # deal damage (combat_capable now uses predict_win, not a level margin).
    assert is_reachable(ReachCharLevel(50), make_state(level=1, attack={"fire": 10}), gd) is True


def test_is_reachable_char_level_false_when_underequipped_and_no_makeable_weapon():
    gd = GameData()
    gd._monster_level = {"dragon": 40}
    fill_monster_stat_defaults(gd)
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
    fill_monster_stat_defaults(gd_empty)
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


def _gd_empty_slots() -> GameData:
    """Two empty-slot gear roots with EQUAL recipe depth (equal effort) but very
    different computed equip value: a body armor (hp_bonus 50 ⇒ equip_value 101)
    and an amulet (water resistance 4 ⇒ equip_value 9). Reproduces the trace
    where both saturate to EMPTY_SLOT_URGENCY and the sort tie must break."""
    gd = GameData()
    gd._item_stats = {
        "feather_coat": ItemStats(code="feather_coat", level=1, type_="body_armor",
                                  hp_bonus=50, crafting_skill="gearcrafting", crafting_level=1),
        "air_and_water_amulet": ItemStats(code="air_and_water_amulet", level=1, type_="amulet",
                                          resistance={"water": 4},
                                          crafting_skill="jewelrycrafting", crafting_level=1),
        "feather": ItemStats(code="feather", level=1, type_="resource"),
        "jasper": ItemStats(code="jasper", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"feather_coat": {"feather": 2},
                            "air_and_water_amulet": {"jasper": 2}}
    gd._resource_drops = {"feather_spot": "feather", "jasper_spot": "jasper"}
    gd._resource_skill = {"feather_spot": ("mining", 1), "jasper_spot": ("mining", 1)}
    gd._monster_level = {"chicken": 1}
    fill_monster_stat_defaults(gd)
    return gd


def test_empty_slot_tie_breaks_by_computed_protection_not_alphabet():
    """Trace 2026-06-17: empty amulet_slot and empty body_armor_slot both
    flatten to EMPTY_SLOT_URGENCY at equal cost; the old `(-final, effort, repr)`
    key handed the win to the amulet purely because 'air…' < 'feather…'. The
    protection tiebreak (computed equip-value gain) now picks the body armor."""
    gd = _gd_empty_slots()
    eng = _eng(gd, target_gear={"amulet_slot": "air_and_water_amulet",
                                "body_armor_slot": "feather_coat"})
    state = make_state(level=5, skills={"mining": 5, "gearcrafting": 5,
                                        "jewelrycrafting": 5})
    d = eng.decide(state, gd)

    gear = {rs.root_repr: rs for rs in d.ranking if "ObtainItem" in rs.root_repr}
    body = next(rs for r, rs in gear.items() if "feather_coat" in r)
    amulet = next(rs for r, rs in gear.items() if "air_and_water_amulet" in r)
    # The tie the bug rode on: equal saturated score AND equal effort.
    assert body.contribution == amulet.contribution
    assert body.cost == amulet.cost
    # Alphabet would seat the amulet first; computed protection outranks it.
    assert repr(amulet.root_repr) < repr(body.root_repr)
    assert equip_value(gd.item_stats("feather_coat")) > equip_value(
        gd.item_stats("air_and_water_amulet"))
    assert "feather_coat" in repr(d.chosen_root)
    assert "air_and_water_amulet" not in repr(d.chosen_root)


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
        gd, st = GameData(), make_state()
        assert eng._base_prior(ReachCharLevel(50), st, gd) == PRIOR_CHAR_LEVEL
        assert eng._base_prior(ReachSkillLevel("weaponcrafting", 50), st, gd) == PRIOR_COMBAT_CRAFT_SKILL
        assert eng._base_prior(ReachSkillLevel("mining", 50), st, gd) == PRIOR_GATHER_SKILL
        assert eng._base_prior(ReachSkillLevel("alchemy", 50), st, gd) == PRIOR_CONSUMABLE_SKILL

    def test_unknown_skill_prior_is_zero(self):
        eng = _eng(GameData())
        assert eng._base_prior(ReachSkillLevel("tailoring", 50), make_state(), GameData()) == 0.0   # not a known skill

    def test_gear_prior_combat_vs_utility(self):
        gd = GameData()
        # combat_gear_types is now data-derived: weapon must have actual combat stats
        # (attack/resistance/hp_bonus/etc.) to appear in combat_gear_types and thus
        # get PRIOR_COMBAT_GEAR. A weapon with no stats would score PRIOR_UTILITY_GEAR,
        # which is correct — such an item has no combat value.
        gd._item_stats = {"copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                                      attack={"fire": 6}),
                          "small_potion": ItemStats(code="small_potion", level=1, type_="utility")}
        eng = _eng(gd, target_gear={"weapon_slot": "copper_dagger", "utility1_slot": "small_potion"})
        st = make_state()
        assert eng._base_prior(ObtainItem("copper_dagger"), st, gd) == PRIOR_COMBAT_GEAR
        assert eng._base_prior(ObtainItem("small_potion"), st, gd) == PRIOR_UTILITY_GEAR


class TestMarginal:
    def test_gear_marginal_gain_over_empty_slot(self):
        gd = GameData()
        gd._item_stats = {"copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon", attack={"fire": 6})}
        eng = _eng(gd, target_gear={"weapon_slot": "copper_dagger"})
        state = make_state(equipment={"weapon_slot": None})
        # combat_monster set → combat-readiness urgency off, testing base marginal.
        m = eng._marginal(ObtainItem("copper_dagger"), state, gd, combat_monster="chicken")
        # #16: gear marginal is now strategic_value-based (combat × SCALE), not
        # equip_value; GEAR_EQUIP_SCALE is scaled to match.
        assert m == min(1.0, strategic_value(gd.item_stats("copper_dagger")) / GEAR_EQUIP_SCALE)
        assert m > 0

    def test_gear_marginal_zero_when_no_gain(self):
        gd = GameData()
        gd._item_stats = {"wand": ItemStats(code="wand", level=1, type_="weapon", attack={"fire": 3})}
        eng = _eng(gd, target_gear={"weapon_slot": "wand"})
        state = make_state(equipment={"weapon_slot": "wand"})
        # combat_monster set → combat-readiness urgency off, testing base marginal.
        assert eng._marginal(ObtainItem("wand"), state, gd, combat_monster="chicken") == 0.0

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
        # Anti-degeneracy: the runaway LEADING skill (alchemy=5, endgame-50 root)
        # must never be chosen. Gear, char level, or a LAGGING craft-skill
        # catch-up root (a below-bootstrap skill, the recipe-aware interleave)
        # may win — but never the already-leading skill.
        assert d.chosen_root != ReachSkillLevel("alchemy", 50)
        assert d.chosen_root != ReachSkillLevel("alchemy", 5)
        # if a skill root wins, it is a lagging catch-up, not the leader
        if root_category(d.chosen_root) == "skills":
            assert state.skills.get(d.chosen_root.skill, 1) < state.skills["alchemy"]

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
        expected = (eng._base_prior(root, state, GameData())
                    * eng._marginal(root, state, GameData()) * eng._balancing(root, state))
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
                        if rs.root_repr == "ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot')"), None)
        assert gear_rs is not None
        assert gear_rs.step_repr == "ReachSkillLevel(skill='weaponcrafting', level=3)"
        # value inherited from the gear root, not the skill's standalone 0.2 prior
        assert gear_rs.score == eng._value(ObtainItem("copper_dagger", slot="weapon_slot"), state, gd)


class TestStickyCommitment:
    """Tier-2 sticky commitment: previous chosen_root is kept when it
    survives the cycle's filters and the new top doesn't dominate."""

    def _two_root_gd(self):
        """Fixture with two craftable items so two roots compete."""
        gd = GameData()
        gd._item_stats = {
            "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                       attack={"fire": 6}, crafting_skill="weaponcrafting",
                                       crafting_level=1),
            "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield",
                                       resistance={"fire": 4}, crafting_skill="gearcrafting",
                                       crafting_level=1),
            "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
            "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
        }
        gd._crafting_recipes = {
            "copper_dagger": {"copper_bar": 6},
            "wooden_shield": {"ash_wood": 4},
        }
        gd._resource_drops = {"rocks": "copper_bar", "tree": "ash_wood"}
        gd._resource_skill = {"rocks": ("mining", 1), "tree": ("woodcutting", 1)}
        gd._monster_level = {"chicken": 1}
        fill_monster_stat_defaults(gd)
        return gd

    def test_sticky_kept_when_within_dominance_ratio(self):
        """When last_chosen_root has score >= top/1.5, sticky wins."""
        gd = self._two_root_gd()
        eng = _eng(gd)
        state = make_state(level=5)
        # First cycle: no sticky → pick natural top.
        d1 = eng.decide(state, gd)
        ranking = [(r.root_repr, r.score) for r in d1.ranking]
        # Precondition (deterministic in _two_root_gd): copper_dagger tops the
        # ranking (combat-gear prior * equip gain = 2.0) and the SECOND-ranked
        # root, ReachCharLevel(level=7) (~1.48), sits within the 1.5x dominance
        # ratio. Plain asserts so a fixture regression FAILS instead of skipping.
        assert len(ranking) >= 2, "fixture must produce 2+ competing roots"
        candidate, cand_score = ranking[1]
        top_score = ranking[0][1]
        assert cand_score > 0, "second-ranked root must have positive score"
        assert top_score <= 1.5 * cand_score, (
            f"fixture must keep second root within dominance ratio: "
            f"top={top_score} second={cand_score} "
            f"ratio={top_score/cand_score:.3f} (1.5 threshold)"
        )
        # Second cycle with the second-ranked root as prior commitment →
        # sticky wins over the natural top.
        d2 = eng.decide(state, gd, last_chosen_root=candidate)
        assert repr(d2.chosen_root) == candidate, (
            f"sticky should have won: top={top_score} sticky={cand_score} "
            f"ratio={top_score/cand_score:.3f} (1.5 threshold)"
        )

    def test_sticky_dropped_when_unreachable(self):
        """When last_chosen_root vanishes from candidates (e.g., satisfied or
        unreachable), sticky doesn't apply and the new top wins."""
        gd = self._two_root_gd()
        eng = _eng(gd)
        state = make_state(level=5)
        # last_chosen_root that doesn't exist in objective_roots.
        d = eng.decide(state, gd, last_chosen_root="ObtainItem(code='nonexistent', quantity=1)")
        # The decide() picks the natural top (sticky candidate not found).
        d_baseline = eng.decide(state, gd)
        assert repr(d.chosen_root) == repr(d_baseline.chosen_root)

    def test_sticky_dropped_when_new_top_dominates(self):
        """When the new top's score strictly exceeds 1.5x sticky's score,
        sticky correctly loses."""
        gd = self._two_root_gd()
        eng = _eng(gd)
        state = make_state(level=5)
        d_baseline = eng.decide(state, gd)
        ranking = [(r.root_repr, r.score) for r in d_baseline.ranking]
        # Find a candidate whose score is < top / 1.5 (dominated).
        top_root, top_score = ranking[0]
        dominated = next(
            ((repr_, score) for repr_, score in ranking[1:]
             if score > 0 and top_score > 1.5 * score),
            None,
        )
        # Precondition (deterministic in _two_root_gd): ReachCharLevel(level=50)
        # scores the flat 1.0 char-level prior while copper_dagger tops at 2.0
        # (> 1.5 * 1.0), so a strictly dominated candidate always exists. Plain
        # assert so a fixture regression FAILS instead of skipping.
        assert dominated is not None, (
            f"fixture must yield a dominated candidate below top/1.5: "
            f"top={top_score} ranking={ranking}"
        )
        # last_chosen_root is the dominated one → top still wins.
        d = eng.decide(state, gd, last_chosen_root=dominated[0])
        assert repr(d.chosen_root) == top_root


class TestRelevantToolBoost:
    """Active-task tool boost: when a target_tools item's skill matches
    the bot's active gathering skill, its score beats ReachCharLevel so
    the bot crafts the tool first instead of grinding bare-handed."""

    def _gd_with_tool(self):
        """Fixture: mining task + copper_pickaxe with mining skill_effect."""
        gd = GameData()
        gd._item_stats = {
            "copper_pickaxe": ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                                       skill_effects={"mining": -1}),
            "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
            "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        }
        gd._crafting_recipes = {
            "copper_pickaxe": {"copper_bar": 6},
            "copper_bar": {"copper_ore": 8},
        }
        # copper_rocks resource drops copper_ore (matches production data).
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        gd._resource_skill = {"copper_rocks": ("mining", 1)}
        gd._monster_level = {"chicken": 1}
        fill_monster_stat_defaults(gd)
        return gd

    def test_tool_boost_active_task_beats_char_level(self):
        """When active task is mining-related, copper_pickaxe's score
        EXCEEDS ReachCharLevel's. Pre-fix: pickaxe scored 0.1 forever."""
        gd = self._gd_with_tool()
        obj = CharacterObjective.from_game_data(gd)
        # Sanity: pickaxe is in target_tools.
        assert obj.target_tools.get("mining") == "copper_pickaxe"
        eng = StrategyEngine(obj, BalancedPersonality())
        # task_code is a copper_ore (gather copper_rocks → copper_bar).
        state = make_state(level=5, task_code="copper_ore", task_progress=10, task_total=100)
        d = eng.decide(state, gd)
        # The pickaxe ObtainItem must beat ReachCharLevel.
        ranking = {r.root_repr: r.score for r in d.ranking}
        pickaxe_score = ranking.get("ObtainItem(code='copper_pickaxe', quantity=1)", 0)
        char_score = ranking.get("ReachCharLevel(level=50)", 0)
        assert pickaxe_score > char_score, (
            f"pickaxe={pickaxe_score} should beat char_level={char_score}"
        )

    def test_no_boost_when_task_skill_mismatched(self):
        """copper_pickaxe should NOT be boosted when active task is a
        fishing task (no mining skill in active set)."""
        gd = self._gd_with_tool()
        obj = CharacterObjective.from_game_data(gd)
        eng = StrategyEngine(obj, BalancedPersonality())
        # No task → no active gathering skill → no boost.
        state = make_state(level=5, task_code=None)
        # combat_monster set → combat-readiness urgency off; isolates the
        # tool-boost mechanism (a not-combat-capable bot would correctly let
        # the weapon-slot urgency lift the pickaxe, defeating this assertion).
        d = eng.decide(state, gd, combat_monster="chicken")
        ranking = {r.root_repr: r.score for r in d.ranking}
        pickaxe_score = ranking.get("ObtainItem(code='copper_pickaxe', quantity=1)", 0)
        char_score = ranking.get("ReachCharLevel(level=50)", 0)
        assert pickaxe_score <= char_score, (
            f"no boost expected: pickaxe={pickaxe_score} char={char_score}"
        )


def test_reach_char_level_marginal_scales_with_inverse_gap():
    """User request 2026-06-06: bot should grind char XP when under-
    leveled (PursueTask deprioritized when GrindCharacterXP is needed).
    Implemented via inverse-gap urgency on `_marginal(ReachCharLevel)`:
    the bootstrap root (small gap) outranks tools so its step
    (GrindCharacterXP) takes the step slot. Long-haul (large gap) stays
    at base CHAR_MARGINAL so the bootstrap-bypass in objective_step_goal
    (e27779e) doesn't get triggered on the wrong step.level."""
    gd = GameData()
    fill_monster_stat_defaults(gd)
    obj = CharacterObjective.from_game_data(gd)
    eng = StrategyEngine(obj, BalancedPersonality())
    state = make_state(level=3)
    # Bootstrap-class root (gap=2): high marginal — boost = (10-2)*0.06 = 0.48.
    boot_value = eng._value(ReachCharLevel(5), state, gd)
    # Long-haul root (gap=47, outside the 10-level horizon): no boost.
    long_value = eng._value(ReachCharLevel(50), state, gd)
    assert boot_value > long_value, (
        f"bootstrap value {boot_value} should outrank long-haul {long_value} "
        f"so the bootstrap step wins decide() and triggers GrindCharacterXP"
    )
    # And the bootstrap value must beat PRIOR_RELEVANT_TOOL (1.1) so it
    # also outranks active-task tools.
    assert boot_value > 1.1, (
        f"bootstrap value {boot_value} must exceed PRIOR_RELEVANT_TOOL=1.1 "
        f"so tools don't preempt the combat grind when the bot is "
        f"under-leveled"
    )


def test_reach_char_level_marginal_zero_bonus_when_already_at_target():
    """Sanity: target == current → gap = 0 → reach = horizon → full
    bonus. Edge-case behavior. (Actually `decide()` filters satisfied
    roots out first, so this scenario doesn't fire in practice — but
    `_value` should still return a sane number.)"""
    gd = GameData()
    fill_monster_stat_defaults(gd)
    obj = CharacterObjective.from_game_data(gd)
    eng = StrategyEngine(obj, BalancedPersonality())
    state = make_state(level=10)
    v = eng._value(ReachCharLevel(10), state, gd)
    # gap=0, reach=10, bonus=10*0.06=0.6 → marginal=1.6 → value=1.6
    assert abs(v - 1.6) < 0.001, (
        f"at target: gap=0 → full reach window bonus, expected ~1.6, got {v}"
    )


def _combat_gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon",
                                crafting_skill="weaponcrafting", crafting_level=10,
                                attack={"fire": 20}),
        "iron_bar": ItemStats(code="iron_bar", level=10, type_="resource",
                              crafting_skill="mining", crafting_level=10),
        "iron_ore": ItemStats(code="iron_ore", level=10, type_="resource"),
        "iron_pickaxe": ItemStats(code="iron_pickaxe", level=10, type_="weapon",
                                  crafting_skill="weaponcrafting", crafting_level=10,
                                  skill_effects={"mining": 10}),
    }
    gd._crafting_recipes = {"iron_sword": {"iron_bar": 6}, "iron_pickaxe": {"iron_bar": 4},
                            "iron_bar": {"iron_ore": 1}}
    gd._resource_drops = {"iron_rocks": "iron_ore"}
    gd._resource_skill = {"iron_rocks": ("mining", 1)}
    return gd


def _combat_obj(gd: GameData) -> CharacterObjective:
    return CharacterObjective(
        target_char_level=50, target_skill_levels={},
        target_gear={"weapon_slot": "iron_sword"}, _game_data=gd,
        target_tools={"mining": "iron_pickaxe"})


def test_weapon_root_is_chosen_when_not_combat_capable():
    gd = _combat_gd()
    eng = StrategyEngine(_combat_obj(gd), BalancedPersonality())
    state = make_state(level=4, skills={"weaponcrafting": 1, "mining": 1})
    d = eng.decide(state, gd, history=None, combat_monster=None)
    assert "iron_sword" in repr(d.chosen_root)


def test_decide_returns_a_root_when_combat_capable():
    gd = _combat_gd()
    eng = StrategyEngine(_combat_obj(gd), BalancedPersonality())
    state = make_state(level=4, skills={"weaponcrafting": 1, "mining": 1})
    d = eng.decide(state, gd, history=None, combat_monster="chicken")
    assert d.chosen_root is not None


class TestEmptySlotUrgency:
    """Runtime bridge for Formal.GearPolicy.armor_strictly_dominates_empty_slot:
    a usable-at-level armor filling an EMPTY combat slot must outrank the
    char-level bootstrap (1.48) even through sticky commitment (x 3/2)."""

    def _gd(self):
        gd = GameData()
        gd._item_stats = {
            "copper_armor": ItemStats(code="copper_armor", level=5, type_="body_armor",
                                      resistance={"earth": 6}),
            "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                       attack={"air": 6}),
        }
        gd._crafting_recipes = {c: {"bar": 1} for c in ("copper_armor", "copper_dagger")}
        gd._resource_drops = {"rocks": "bar"}
        gd._resource_skill = {"rocks": ("mining", 1)}
        return gd

    def test_empty_armor_slot_beats_char_bootstrap_through_sticky(self):
        gd = self._gd()
        obj = CharacterObjective.from_game_data(gd)
        eng = StrategyEngine(obj, BalancedPersonality())
        state = make_state(level=6, equipment={"weapon_slot": "copper_dagger"})
        d = eng.decide(state, gd, combat_monster="chicken",
                       last_chosen_root=repr(ReachCharLevel(8)))
        assert d.chosen_root == ObtainItem("copper_armor", slot="body_armor_slot")
        ranking = {r.root_repr: r.score for r in d.ranking}
        armor = ranking["ObtainItem(code='copper_armor', quantity=1, slot='body_armor_slot')"]
        assert armor == EMPTY_SLOT_URGENCY            # prior 1 x max(m,1)x5/2 x bal 1
        assert armor > STICKY_DOMINANCE_RATIO * Fraction(37, 25)   # > 3/2 x 1.48

    def test_no_urgency_when_slot_filled(self):
        gd = self._gd()
        obj = CharacterObjective.from_game_data(gd)
        eng = StrategyEngine(obj, BalancedPersonality())
        # Crafting skills held AT the bootstrap target (5) so the recipe-aware
        # catch-up roots are inert (gap 0) — this isolates the empty-slot-urgency
        # behaviour under test from the skill-curve interleave.
        state = make_state(
            level=6,
            skills={"mining": 3, "woodcutting": 2, "fishing": 1, "cooking": 1,
                    "alchemy": 1, "weaponcrafting": 5, "gearcrafting": 5,
                    "jewelrycrafting": 5},
            equipment={"weapon_slot": "copper_dagger",
                       "body_armor_slot": "copper_armor"})
        d = eng.decide(state, gd, combat_monster="chicken")
        ranking = {r.root_repr: r.score for r in d.ranking}
        # Slot filled with the item itself → root satisfied, out of ranking.
        assert "ObtainItem(code='copper_armor', quantity=1, slot='body_armor_slot')" not in ranking
        # No empty-slot urgency; char bootstrap takes over.
        assert d.chosen_root == ReachCharLevel(8)

    def test_no_urgency_for_over_level_item(self):
        gd = self._gd()
        gd._item_stats["copper_armor"] = ItemStats(
            code="copper_armor", level=20, type_="body_armor", resistance={"earth": 6})
        obj = CharacterObjective.from_game_data(gd)
        eng = StrategyEngine(obj, BalancedPersonality())
        state = make_state(level=6, equipment={"weapon_slot": "copper_dagger"})
        m = eng._marginal(ObtainItem("copper_armor"), state, gd, combat_monster="chicken")
        gain = Fraction(strategic_value(gd.item_stats("copper_armor")))  # #16: strategic_value-based
        assert m == min(Fraction(1), gain / GEAR_EQUIP_SCALE)   # plain marginal, no boost

    def test_gear_slot_resolution_prefers_weakest_ring(self):
        gd = self._gd()
        # Three rings: BiS top-2 = silver + bronze (target_gear ring1/ring2);
        # copper_ring stays OUTSIDE target_gear → exercises type fallback.
        gd._item_stats["silver_ring"] = ItemStats(
            code="silver_ring", level=5, type_="ring", attack={"fire": 4})
        gd._item_stats["bronze_ring"] = ItemStats(
            code="bronze_ring", level=3, type_="ring", attack={"fire": 3})
        gd._item_stats["copper_ring"] = ItemStats(
            code="copper_ring", level=1, type_="ring", attack={"fire": 2})
        gd._crafting_recipes.update(
            {c: {"bar": 1} for c in ("silver_ring", "bronze_ring", "copper_ring")})
        obj = CharacterObjective.from_game_data(gd)
        assert "copper_ring" not in obj.target_gear.values()
        eng = StrategyEngine(obj, BalancedPersonality())
        state = make_state(level=6, equipment={"weapon_slot": "copper_dagger",
                                               "ring1_slot": "silver_ring"})
        # ring2 (absent → empty, value 0) is weaker than ring1 (silver) →
        # the upgrade would fill ring2_slot.
        assert eng._gear_slot("copper_ring", state, gd) == "ring2_slot"

    def test_gear_slot_none_for_unknown_item(self):
        gd = self._gd()
        obj = CharacterObjective.from_game_data(gd)
        eng = StrategyEngine(obj, BalancedPersonality())
        assert eng._gear_slot("no_such_item", make_state(), gd) is None

    def test_gear_slot_none_for_unequippable_type(self):
        gd = self._gd()
        gd._item_stats["copper_ore"] = ItemStats(code="copper_ore", level=1, type_="resource")
        obj = CharacterObjective.from_game_data(gd)
        eng = StrategyEngine(obj, BalancedPersonality())
        assert eng._gear_slot("copper_ore", make_state(), gd) is None

    def test_gear_slot_none_for_target_tools(self):
        gd = self._gd()
        gd._item_stats["copper_pickaxe"] = ItemStats(
            code="copper_pickaxe", level=1, type_="weapon", skill_effects={"mining": -1})
        gd._crafting_recipes["copper_pickaxe"] = {"bar": 1}
        obj = CharacterObjective.from_game_data(gd)
        eng = StrategyEngine(obj, BalancedPersonality())
        state = make_state(level=6)
        assert eng._gear_slot("copper_pickaxe", state, gd) is None


def _engine_with_recipes() -> tuple[StrategyEngine, GameData]:
    """Engine over a game with a weaponcrafting recipe at craft_level 5 (water_bow,
    item_level 5), so the near-term skill curve target for weaponcrafting is 5 at
    char level 7. Mirrors the production from_game_data construction used by the
    other strategy tests."""
    gd = _gd_with_recipes()
    obj = CharacterObjective.from_game_data(gd)
    return StrategyEngine(obj, BalancedPersonality()), gd


class TestGapProportionalSkillMarginal:
    def test_skill_root_marginal_gap_proportional(self):
        # gap 1 (current 4) vs gap 3 (current 2) -> larger gap, larger marginal.
        eng, gd = _engine_with_recipes()
        s1 = make_state(level=7, skills={"weaponcrafting": 4, "woodcutting": 4})
        s3 = make_state(level=7, skills={"weaponcrafting": 2, "woodcutting": 4})
        root = ReachSkillLevel("weaponcrafting", 5)
        m1 = eng._marginal(root, s1, gd)
        m3 = eng._marginal(root, s3, gd)
        assert m3 > m1

    def test_endgame_skill_root_stays_flat(self):
        eng, gd = _engine_with_recipes()
        state = make_state(level=7, skills={"weaponcrafting": 2})
        endgame = ReachSkillLevel("weaponcrafting", gd.max_skill_level)
        assert eng._marginal(endgame, state, gd) == SKILL_MARGINAL

    def test_far_behind_skill_root_outranks_char_bootstrap(self):
        # The run-7 scenario: char 7, weaponcrafting 2, curve target 5 (gap 3).
        # The skill root's value must beat the level+2 char bootstrap (so the
        # skill rises BEFORE the gear commit forces a freeze).
        eng, gd = _engine_with_recipes()
        state = make_state(level=7, skills={"weaponcrafting": 2, "woodcutting": 8})
        skill_root = ReachSkillLevel("weaponcrafting", 5)
        char_boot = ReachCharLevel(state.level + 2)
        assert eng._value(skill_root, state, gd) > eng._value(char_boot, state, gd)

    def test_near_curve_skill_root_loses_to_char_bootstrap(self):
        # gap 1 must NOT hijack leveling.
        eng, gd = _engine_with_recipes()
        state = make_state(level=7, skills={"weaponcrafting": 4, "woodcutting": 4})
        skill_root = ReachSkillLevel("weaponcrafting", 5)
        char_boot = ReachCharLevel(state.level + 2)
        assert eng._value(skill_root, state, gd) < eng._value(char_boot, state, gd)

    def test_skill_marginal_capped_at_gap_cap(self):
        """A large gap is clamped to SKILL_GAP_CAP (1.5): marginal tops out at
        SKILL_MARGINAL + 1.5 = 1.7 no matter how far behind the curve target."""
        eng, gd = _engine_with_recipes()
        state = make_state(level=10, skills={"weaponcrafting": 1})
        root = ReachSkillLevel("weaponcrafting", 9)  # gap 8, clamped to 1.5
        assert eng._marginal(root, state, gd) == (
            SKILL_MARGINAL + SKILL_GAP_CAP * SKILL_GAP_PER_LEVEL)

    def test_moderate_gap_balanced_skill_loses_to_gear_and_char(self):
        """Trace 2026-06-13: char 3, crafting skills all ~3 (no runaway leader),
        curve target 5 (gap 2). With SKILL_GAP_CAP lowered to 1.5 the general
        skill root no longer out-ranks combat gear or the level+2 char
        bootstrap — general skill-XP grinding is a low-priority backstop."""
        eng, gd = _engine_with_recipes()
        state = make_state(
            level=3,
            skills={"weaponcrafting": 3, "gearcrafting": 3,
                    "jewelrycrafting": 3, "woodcutting": 3},
        )
        skill_root = ReachSkillLevel("weaponcrafting", 5)
        char_boot = ReachCharLevel(state.level + 2)
        skill_v = eng._value(skill_root, state, gd)
        assert skill_v < eng._value(char_boot, state, gd)
        gear_root = ObtainItem(code="water_bow", quantity=1)
        assert skill_v < eng._value(gear_root, state, gd)


class TestGearedCharBoost:
    """Char-leveling out-ranks general skill grinding (≈2.04) ONLY once the bot
    is combat-capable AND every fillable combat armor slot is equipped — bump
    only after the empty armor slots are filled (2026-06-14). While an armor
    slot is empty or the bot can't fight, char stays at the base rate (1.48) so
    gear/weapon urgency wins first."""

    @staticmethod
    def _gd() -> GameData:
        gd = GameData()
        gd._item_stats = {
            "copper_armor": ItemStats(code="copper_armor", level=2,
                                      type_="body_armor", resistance={"earth": 6}),
            "bar": ItemStats(code="bar", level=1, type_="resource"),
        }
        gd._crafting_recipes = {"copper_armor": {"bar": 1}}
        gd._resource_drops = {"rocks": "bar"}
        gd._resource_skill = {"rocks": ("mining", 1)}
        gd._monster_level = {"chicken": 1}
        fill_monster_stat_defaults(gd)
        return gd

    def _eng(self, gd: GameData) -> StrategyEngine:
        return StrategyEngine(CharacterObjective.from_game_data(gd),
                              BalancedPersonality())

    def test_base_rate_while_armor_slot_empty(self):
        gd = self._gd()
        eng = self._eng(gd)
        state = make_state(level=6)  # body_armor_slot empty, copper_armor usable
        m = eng._marginal(ReachCharLevel(8), state, gd, combat_monster="chicken")
        assert m == CHAR_MARGINAL + 8 * CHAR_GAP_PER_LEVEL          # 1.48

    def test_boosted_when_armor_filled_and_combat_capable(self):
        gd = self._gd()
        eng = self._eng(gd)
        state = make_state(level=6, equipment={"body_armor_slot": "copper_armor"})
        m = eng._marginal(ReachCharLevel(8), state, gd, combat_monster="chicken")
        assert m == CHAR_MARGINAL + 8 * CHAR_GAP_PER_LEVEL_GEARED   # 2.25

    def test_base_rate_when_not_combat_capable_even_if_armored(self):
        gd = self._gd()
        eng = self._eng(gd)
        state = make_state(level=6, equipment={"body_armor_slot": "copper_armor"})
        m = eng._marginal(ReachCharLevel(8), state, gd, combat_monster=None)
        assert m == CHAR_MARGINAL + 8 * CHAR_GAP_PER_LEVEL          # 1.48


def test_second_ring_root_scored_against_its_own_empty_slot():
    """With ring1 filled and ring2 empty, the ring1 root is satisfied while the
    slot-tagged ring2 root scores its OWN empty slot (positive marginal) so it's
    pursued — not read as satisfied off ring1."""
    gd = GameData()
    gd._item_stats = {"copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                               attack={"fire": 6})}
    gd._crafting_recipes = {"copper_ring": {"bar": 1}}
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
    state = make_state(level=5, equipment={"ring1_slot": "copper_ring"})
    ring2 = ObtainItem("copper_ring", slot="ring2_slot")
    assert not ring2.is_satisfied(state, gd)
    assert eng._marginal(ring2, state, gd) > 0


def test_equip_gain_zero_when_item_stats_unknown():
    """_equip_gain returns 0 for an ObtainItem whose code has no stats in
    GameData (stats is None) — a non-gear / unknown root contributes no gear
    gain to the marginal score or the protection tiebreak."""
    gd = GameData()
    gd._item_stats = {}  # no stats for any code
    eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
    state = make_state(level=5)
    assert eng._equip_gain(ObtainItem("mystery_item", 1), state, gd) == 0


# --- C1: task-currency producibility ---

def test_producible_recognizes_task_earnable_currency():
    """tasks_coin is listed in task_reward_item_codes → _producible must
    return True without needing a recipe, resource-drop, or winnable fight."""
    gd = GameData()
    gd._task_reward_item_codes = frozenset({"tasks_coin"})
    assert _producible("tasks_coin", make_state(), gd) is True


def _gd_task_vendor() -> GameData:
    """jasper_crystal sold by a permanent, located tasks_trader NPC for tasks_coin
    (a task-earnable currency). No recipe, no gather/drop, no monster."""
    gd = GameData()
    gd._task_reward_item_codes = frozenset({"tasks_coin"})
    gd._npc_stock = {"tasks_trader": {"jasper_crystal": 8}}
    gd._npc_buy_currency = {"tasks_trader": {"jasper_crystal": "tasks_coin"}}
    gd._npc_locations = {"tasks_trader": (1, 2)}
    gd._item_stats = {
        "jasper_crystal": ItemStats(code="jasper_crystal", level=1, type_="resource"),
    }
    return gd


def test_producible_recognizes_currency_buy_with_task_earnable_currency():
    """jasper_crystal has no recipe, no resource-drop, and no winnable dropper;
    it is sold by a permanent vendor for tasks_coin (task-earnable) →
    _producible must return True (Finding A fix)."""
    gd = _gd_task_vendor()
    assert _producible("jasper_crystal", make_state(), gd) is True


def test_not_producible_for_currency_buy_with_unattainable_currency():
    """An NPC-sold item whose currency is neither gold nor task-earnable must
    NOT be producible — the flat currency check must not over-admit."""
    gd = GameData()
    gd._task_reward_item_codes = frozenset()
    gd._npc_stock = {"mystery_shop": {"rare_gem": 1}}
    gd._npc_buy_currency = {"mystery_shop": {"rare_gem": "void_token"}}  # not earnable
    gd._npc_locations = {"mystery_shop": (3, 3)}
    gd._item_stats = {"rare_gem": ItemStats(code="rare_gem", level=1, type_="resource")}
    assert _producible("rare_gem", make_state(), gd) is False


def _gd_bag() -> GameData:
    """GameData with the craftable bag (satchel, gearcrafting L5) plus an empty
    combat helmet, for the bag-slot urgency tests. satchel's only stat is
    inventory_space, so its equip_value and cold strategic_value are both 0 —
    the exact zero-collapse the BAG_SLOT_URGENCY floor addresses. iron_helmet
    carries hp_bonus (combat-bearing) so helmet_slot is an empty COMBAT slot,
    giving a concrete 'below combat' comparison target."""
    gd = GameData()
    gd._item_stats = {
        "satchel": ItemStats(
            code="satchel", level=5, type_="bag", inventory_space=20,
            crafting_skill="gearcrafting", crafting_level=5),
        "iron_helmet": ItemStats(
            code="iron_helmet", level=5, type_="helmet", hp_bonus=20,
            crafting_skill="gearcrafting", crafting_level=5),
        "cowhide": ItemStats(code="cowhide", level=8, type_="resource"),
    }
    gd._crafting_recipes = {"satchel": {"cowhide": 5}, "iron_helmet": {"cowhide": 5}}
    gd._monster_level = {"chicken": 1}  # gives from_game_data a combat monster
    fill_monster_stat_defaults(gd)
    return gd


def _bag_state(gearcrafting: int = 5):
    """State at level 11 with empty bag + helmet slots and the given
    gearcrafting skill. Copies make_state's default skills so only gearcrafting
    is overridden (bag branch gates on gearcrafting >= satchel.crafting_level)."""
    base = make_state(level=11)
    return make_state(
        level=11,
        skills={**base.skills, "gearcrafting": gearcrafting},
        equipment={**base.equipment, "bag_slot": None, "helmet_slot": None},
    )


def test_empty_bag_slot_scores_nonzero():
    gd = _gd_bag()
    eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
    root = ObtainItem("satchel", slot="bag_slot")
    assert eng._value(root, _bag_state(), gd) > 0


def test_empty_bag_slot_below_empty_combat_slot():
    gd = _gd_bag()
    eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
    state = _bag_state()
    bag = eng._value(ObtainItem("satchel", slot="bag_slot"), state, gd)
    helmet = eng._value(ObtainItem("iron_helmet", slot="helmet_slot"), state, gd)
    assert 0 < bag < helmet


def test_bag_floor_gated_on_craft_skill():
    gd = _gd_bag()
    eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
    # gearcrafting 1 < satchel.crafting_level 5 → not craftable yet → no floor.
    root = ObtainItem("satchel", slot="bag_slot")
    assert eng._value(root, _bag_state(gearcrafting=1), gd) == 0
