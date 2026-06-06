from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective, is_attainable
from artifactsmmo_cli.ai.world_state import SKILL_NAMES
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon", attack={"air": 4}),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon", attack={"fire": 30}),
        "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring", attack={"fire": 2}),
        "gold_ring": ItemStats(code="gold_ring", level=20, type_="ring", attack={"fire": 8}),
        "ruby_ring": ItemStats(code="ruby_ring", level=30, type_="ring", attack={"fire": 6}),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),  # not equippable
    }
    # Make the targeted gear attainable: each is craftable from one gatherable raw.
    gd._crafting_recipes = {
        c: {"bar": 1}
        for c in ("wooden_stick", "iron_sword", "copper_ring", "gold_ring", "ruby_ring")
    }
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    return gd


def test_target_char_and_skill_levels():
    obj = CharacterObjective.from_game_data(_gd())
    assert obj.target_char_level == 50
    assert obj.target_skill_levels == {s: 50 for s in SKILL_NAMES}


def test_best_gear_per_slot():
    obj = CharacterObjective.from_game_data(_gd())
    assert obj.target_gear["weapon_slot"] == "iron_sword"  # higher attack wins
    assert "copper_ore" not in obj.target_gear.values()    # resources excluded


def test_paired_ring_slots_get_top_two_distinct():
    obj = CharacterObjective.from_game_data(_gd())
    # gold_ring(8) > ruby_ring(6) > copper_ring(2): top-2 fill ring1/ring2.
    assert obj.target_gear["ring1_slot"] == "gold_ring"
    assert obj.target_gear["ring2_slot"] == "ruby_ring"


def test_slot_with_no_candidate_is_omitted():
    gd = GameData()
    gd._item_stats = {"only_weapon": ItemStats(code="only_weapon", level=1, type_="weapon", attack={"f": 1})}
    gd._crafting_recipes = {"only_weapon": {"bar": 1}}
    gd._resource_drops = {"rocks": "bar"}
    obj = CharacterObjective.from_game_data(gd)
    assert "weapon_slot" in obj.target_gear
    assert "boots_slot" not in obj.target_gear


def test_is_attainable_gatherable_and_craftable_chain():
    gd = GameData()
    gd._crafting_recipes = {"sword": {"bar": 2}, "bar": {"ore": 3}}
    gd._resource_drops = {"rocks": "ore"}
    assert is_attainable("ore", gd) is True          # gatherable raw
    assert is_attainable("sword", gd) is True         # sword<-bar<-ore all attainable


def test_is_attainable_false_for_drop_only_and_blocked_material():
    gd = GameData()
    gd._crafting_recipes = {"cursed": {"boss_drop": 1}}
    gd._resource_drops = {"rocks": "ore"}
    assert is_attainable("boss_drop", gd) is False    # no recipe, no drop
    assert is_attainable("cursed", gd) is False        # material unattainable


def test_is_attainable_false_for_cycle():
    gd = GameData()
    gd._crafting_recipes = {"a": {"a": 1}}
    assert is_attainable("a", gd) is False


def test_target_gear_prefers_attainable_over_higher_value_drop():
    gd = GameData()
    gd._item_stats = {
        "drop_blade": ItemStats(code="drop_blade", level=1, type_="weapon", attack={"f": 99}),  # unattainable
        "iron_blade": ItemStats(code="iron_blade", level=1, type_="weapon", attack={"f": 20}),    # craftable
    }
    gd._crafting_recipes = {"iron_blade": {"bar": 1}}
    gd._resource_drops = {"rocks": "bar"}
    obj = CharacterObjective.from_game_data(gd)
    assert obj.target_gear["weapon_slot"] == "iron_blade"  # attainable wins despite lower value


def test_gap_complete_fractions_zero_for_maxed_components():
    obj = CharacterObjective.from_game_data(_gd())
    maxed = make_state(
        level=50, skills={s: 50 for s in SKILL_NAMES},
        equipment={"weapon_slot": "iron_sword", "ring1_slot": "gold_ring", "ring2_slot": "ruby_ring"},
    )
    g = obj.gap(maxed)
    assert g.char_level_gap == 0
    assert g.skill_gaps == {}
    assert g.char_level_fraction == 0.0
    assert g.skills_fraction == 0.0


def test_gap_measures_level_and_skill_and_gear_deficit():
    obj = CharacterObjective.from_game_data(_gd())
    state = make_state(level=10, skills={"mining": 5}, equipment={"weapon_slot": "wooden_stick"})
    g = obj.gap(state)
    assert g.char_level_gap == 40
    assert g.skill_gaps["mining"] == 45
    assert g.skill_gaps["woodcutting"] == 49  # default level 1 → gap 49
    # weapon target iron_sword(2*30+1=61) vs equipped wooden_stick(2*4+1=9)
    # → gap 52 (augmented equip_value: 2*raw + nonToolBonus).
    assert g.gear_gaps["weapon_slot"] == 52.0
    assert 0.0 < g.char_level_fraction <= 1.0
    assert 0.0 < g.gear_fraction <= 1.0


def test_empty_slot_scores_full_target_value():
    obj = CharacterObjective.from_game_data(_gd())
    state = make_state(level=50, skills={s: 50 for s in SKILL_NAMES}, equipment={})
    g = obj.gap(state)
    # Empty slot: full augmented iron_sword value = 2*30 + 1 (non-tool) = 61.
    assert g.gear_gaps["weapon_slot"] == 61.0


def test_gear_fraction_zero_and_complete_when_no_gear_targeted():
    gd = GameData()  # no items → no target gear
    obj = CharacterObjective.from_game_data(gd)
    g = obj.gap(make_state(level=50, skills={s: 50 for s in SKILL_NAMES}))
    assert g.gear_fraction == 0.0
    assert g.is_complete is True


def _gd_with_tools() -> GameData:
    """Fixture with combat weapons + skill tools sharing weapon_slot."""
    gd = GameData()
    gd._item_stats = {
        # Combat weapon: high attack, no skill_effects.
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                  attack={"earth": 5}),
        # Mining tool: 0 attack, mining cooldown reduction.
        "copper_pickaxe": ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                                   skill_effects={"mining": -1}),
        # Woodcutting tool.
        "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                               skill_effects={"woodcutting": -1}),
        # Stronger mining tool: cooldown reduction 2.
        "iron_pickaxe": ItemStats(code="iron_pickaxe", level=5, type_="weapon",
                                 skill_effects={"mining": -2}),
    }
    gd._crafting_recipes = {
        c: {"bar": 1}
        for c in ("copper_dagger", "copper_pickaxe", "copper_axe", "iron_pickaxe")
    }
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    return gd


def test_target_tools_picks_best_per_gathering_skill():
    """CharacterObjective.target_tools must include the highest-magnitude
    tool per gathering skill. iron_pickaxe beats copper_pickaxe for mining
    (effect -2 vs -1); copper_axe wins woodcutting unopposed."""
    obj = CharacterObjective.from_game_data(_gd_with_tools())
    assert obj.target_tools.get("mining") == "iron_pickaxe"
    assert obj.target_tools.get("woodcutting") == "copper_axe"
    # No fishing or alchemy tool → omitted.
    assert "fishing" not in obj.target_tools
    assert "alchemy" not in obj.target_tools


def test_target_gear_weapon_slot_unaffected_by_tools():
    """The combat-weapon target stays the highest-attack weapon. Tools
    score 0 on the combat axis so they never compete with copper_dagger
    for the weapon_slot gear pick."""
    obj = CharacterObjective.from_game_data(_gd_with_tools())
    assert obj.target_gear.get("weapon_slot") == "copper_dagger"


def test_tools_default_empty_for_backward_compat_constructor():
    """Direct constructor (legacy test fixtures) defaults target_tools to
    empty dict so existing call sites stay green."""
    gd = GameData()
    obj = CharacterObjective(
        target_char_level=50,
        target_skill_levels={s: 50 for s in SKILL_NAMES},
        target_gear={},
        _game_data=gd,
    )
    assert obj.target_tools == {}
