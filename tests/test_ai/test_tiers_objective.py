from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.objective import (
    CharacterObjective,
    is_attainable,
    is_attainable_now,
)
from artifactsmmo_cli.ai.world_state import SKILL_NAMES
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
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


def test_paired_ring_slots_duplicate_best_over_second_distinct():
    """RE-DERIVED (Task 2, GAP-2 review, 2026-07-08): rings are duplicate-
    allowed (DUPLICATE_SLOT_TYPES), so a 2nd copy of the best ring
    (gold_ring, attack 8) strictly dominates the 2nd-ranked DISTINCT ring
    (ruby_ring, attack 6) — both slots target gold_ring. Previously pinned
    ring1=gold_ring/ring2=ruby_ring encoded the same "ranked-distinct" quirk
    Task 2 fixed for artifacts; rings share `_slot_assignments` and shared
    the bug."""
    obj = CharacterObjective.from_game_data(_gd())
    assert obj.target_gear["ring1_slot"] == "gold_ring"
    assert obj.target_gear["ring2_slot"] == "gold_ring"


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


def _gd_near_term() -> GameData:
    """Catalog with a usable low-level armor tier and an endgame BiS tier."""
    gd = GameData()
    gd._item_stats = {
        "copper_armor": ItemStats(code="copper_armor", level=5, type_="body_armor",
                                  resistance={"earth": 6}),
        "iron_armor": ItemStats(code="iron_armor", level=10, type_="body_armor",
                                resistance={"earth": 12}),
        "dragon_armor": ItemStats(code="dragon_armor", level=40, type_="body_armor",
                                  resistance={"earth": 40}),
        "copper_helmet": ItemStats(code="copper_helmet", level=5, type_="helmet",
                                   resistance={"air": 4}),
        "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring", attack={"fire": 2}),
        "silver_ring": ItemStats(code="silver_ring", level=5, type_="ring", attack={"fire": 4}),
        "drop_only_boots": ItemStats(code="drop_only_boots", level=1, type_="boots",
                                     resistance={"water": 3}),
    }
    gd._crafting_recipes = {
        c: {"bar": 1}
        for c in ("copper_armor", "iron_armor", "dragon_armor", "copper_helmet",
                  "copper_ring", "silver_ring")
    }
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    return gd


def test_near_term_gear_picks_best_usable_at_level():
    """Level 5: copper_armor (usable) wins body_armor_slot; iron (10) and
    dragon (40) are over-level and excluded."""
    obj = CharacterObjective.from_game_data(_gd_near_term())
    state = make_state(level=5)
    targets = obj.near_term_gear(state)
    assert targets["body_armor_slot"] == "copper_armor"
    assert targets["helmet_slot"] == "copper_helmet"


def test_near_term_gear_respects_level_gate():
    """Level 12: iron_armor becomes the near-term pick over copper."""
    obj = CharacterObjective.from_game_data(_gd_near_term())
    targets = obj.near_term_gear(make_state(level=12))
    assert targets["body_armor_slot"] == "iron_armor"


def test_near_term_gear_requires_strict_upgrade():
    """A slot already holding the best usable item gets no target."""
    obj = CharacterObjective.from_game_data(_gd_near_term())
    state = make_state(level=5, equipment={"body_armor_slot": "copper_armor"})
    targets = obj.near_term_gear(state)
    assert "body_armor_slot" not in targets


def test_near_term_gear_skips_unattainable_items():
    """drop_only_boots has no recipe and no resource drop → unattainable →
    boots slot has no near-term target."""
    obj = CharacterObjective.from_game_data(_gd_near_term())
    targets = obj.near_term_gear(make_state(level=5))
    assert "boots_slot" not in targets


def test_near_term_gear_fills_paired_ring_slots():
    """RE-DERIVED (Task 2, GAP-2 review, 2026-07-08): rings are duplicate-
    allowed, so both ring slots target the single best usable ring
    (silver_ring, attack 4) rather than the 2nd-ranked distinct copper_ring
    (attack 2) — duplicating the best strictly dominates. See
    test_paired_ring_slots_duplicate_best_over_second_distinct."""
    obj = CharacterObjective.from_game_data(_gd_near_term())
    targets = obj.near_term_gear(make_state(level=5))
    assert targets["ring1_slot"] == "silver_ring"
    assert targets["ring2_slot"] == "silver_ring"


def _gd_drop_recipes() -> GameData:
    """Armor recipes that include MONSTER DROPS — the real low-level shape
    (copper_armor needs wool, life_amulet needs feather). chicken is winnable
    and located; dragon is unwinnable (huge stats)."""
    gd = GameData()
    gd._item_stats = {
        "feather_coat": ItemStats(code="feather_coat", level=5, type_="body_armor",
                                  resistance={"air": 5}),
        "dragon_helm": ItemStats(code="dragon_helm", level=5, type_="helmet",
                                 resistance={"fire": 8}),
        "stick": ItemStats(code="stick", level=1, type_="weapon", attack={"air": 5}),
    }
    gd._crafting_recipes = {
        "feather_coat": {"feather": 5, "bar": 1},
        "dragon_helm": {"dragon_scale": 2},
    }
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    gd._monster_level = {"chicken": 1, "dragon": 40}
    gd._monster_hp = {"chicken": 10, "dragon": 99999}
    gd._monster_attack = {"dragon": {"fire": 9999}}
    fill_monster_stat_defaults(gd)
    gd._monster_drops = {
        "chicken": [("feather", 10, 1, 2)],
        "dragon": [("dragon_scale", 10, 1, 1)],
    }
    gd._monster_locations = {"chicken": [(0, 1)], "dragon": [(9, 9)]}
    return gd


def test_is_attainable_now_accepts_winnable_monster_drop_chain():
    """Trace 2026-06-11 17:21 inert-fix bug: copper_armor (wool from a
    trivially-winnable monster) was rejected by the gathering-only
    is_attainable, leaving zero armor roots. The state-aware predicate must
    accept craft chains bottoming out in winnable, located monster drops."""
    gd = _gd_drop_recipes()
    state = make_state(level=5, attack={"air": 5})   # sheet attack → chicken winnable
    assert is_attainable_now("feather_coat", state, gd) is True
    targets = CharacterObjective.from_game_data(gd).near_term_gear(state)
    assert targets["body_armor_slot"] == "feather_coat"


def test_is_attainable_now_rejects_unwinnable_monster_drop():
    """dragon_scale only drops from an unbeatable monster → dragon_helm is
    NOT a near-term target (self-unlocks later as gear/level improve)."""
    gd = _gd_drop_recipes()
    state = make_state(level=5, attack={"air": 5})
    assert is_attainable_now("dragon_helm", state, gd) is False
    targets = CharacterObjective.from_game_data(gd).near_term_gear(state)
    assert "helmet_slot" not in targets


def test_is_attainable_now_requires_known_spawn():
    """A winnable dropper with no known map location does not count
    (mirrors strategy._producible's spawn-location gate)."""
    gd = _gd_drop_recipes()
    gd._monster_locations = {"dragon": [(9, 9)]}   # chicken spawn unknown
    state = make_state(level=5, attack={"air": 5})
    assert is_attainable_now("feather_coat", state, gd) is False


def test_is_attainable_now_cycle_safe():
    gd = GameData()
    gd._crafting_recipes = {"a": {"a": 1}}
    assert is_attainable_now("a", make_state(), gd) is False


def test_is_attainable_accepts_known_spawn_monster_drop():
    """Perfect-sheet leaf fix: feather_coat crafts from feather (a chicken drop,
    chicken has a known spawn) + bar (gatherable). The gathering-only
    is_attainable used to reject this and silently drop body_armor from the
    perfect sheet; the unified leaf accepts a known-spawn monster drop."""
    gd = _gd_drop_recipes()
    assert is_attainable("feather_coat", gd) is True


def test_is_attainable_ignores_winnability_for_perfect_sheet():
    """State-INDEPENDENT: dragon_helm crafts from dragon_scale (the dragon is
    unbeatable NOW, but at max progression it is farmable). The perfect sheet
    targets it; only is_attainable_now gates on current winnability."""
    gd = _gd_drop_recipes()
    assert is_attainable("dragon_helm", gd) is True
    assert is_attainable_now("dragon_helm", make_state(level=5, attack={"air": 5}), gd) is False


def test_is_attainable_requires_known_spawn():
    """A monster drop with NO known spawn location is not producible (the bot
    could never reach the dropper). Removing chicken's spawn rejects
    feather_coat."""
    gd = _gd_drop_recipes()
    gd._monster_locations = {"dragon": [(9, 9)]}   # chicken spawn unknown
    assert is_attainable("feather_coat", gd) is False


def test_target_gear_surfaces_monster_drop_armor():
    """The headline #11 fix: monster-drop-crafted armor now appears in the
    perfect sheet's target_gear, not only in near_term_gear. Both feather_coat
    (body) and dragon_helm (helmet) are state-independently attainable."""
    obj = CharacterObjective.from_game_data(_gd_drop_recipes())
    assert obj.target_gear["body_armor_slot"] == "feather_coat"
    assert obj.target_gear["helmet_slot"] == "dragon_helm"


def _gd_npc_rune() -> GameData:
    """A rune slot whose only acquisition is an NPC purchase: lifesteal_rune has
    no recipe, no gather/drop, sold by a permanent rune_vendor for gold."""
    gd = GameData()
    gd._item_stats = {
        "lifesteal_rune": ItemStats(code="lifesteal_rune", level=20, type_="rune", lifesteal=10),
    }
    gd._npc_stock = {"rune_vendor": {"lifesteal_rune": 20000}}
    gd._npc_buy_currency = {"rune_vendor": {"lifesteal_rune": "gold"}}
    gd._npc_locations = {"rune_vendor": (8, 13)}
    return gd


def test_is_attainable_accepts_npc_gold_purchase():
    """Task #12: an NPC-only item bought for gold from a permanent vendor is
    attainable (perfect sheet assumes full gold)."""
    assert is_attainable("lifesteal_rune", _gd_npc_rune()) is True


def test_is_attainable_rejects_event_only_vendor():
    """A vendor that only spawns during a timed event is not a reliable
    perfect-sheet acquisition source."""
    gd = _gd_npc_rune()
    gd._npc_event_code["rune_vendor"] = "rune_festival"
    assert is_attainable("lifesteal_rune", gd) is False


def test_is_attainable_rejects_unlocated_vendor():
    """A vendor with no known map location cannot be reached."""
    gd = _gd_npc_rune()
    gd._npc_locations = {}
    assert is_attainable("lifesteal_rune", gd) is False


def test_is_attainable_npc_item_currency_recurses():
    """A purchase paid in an ITEM currency is attainable iff that currency is
    attainable. greater_lifesteal_rune costs sandwhisper_coin; the coin is a
    chicken drop (known spawn) → attainable, so the rune is too."""
    gd = _gd_npc_rune()
    gd._item_stats["greater_lifesteal_rune"] = ItemStats(
        code="greater_lifesteal_rune", level=40, type_="rune", lifesteal=20)
    gd._npc_stock["sandwhisper_trader"] = {"greater_lifesteal_rune": 100}
    gd._npc_buy_currency["sandwhisper_trader"] = {"greater_lifesteal_rune": "sandwhisper_coin"}
    gd._npc_locations["sandwhisper_trader"] = (-2, 18)
    gd._monster_drops = {"chicken": [("sandwhisper_coin", 10, 1, 1)]}
    gd._monster_locations = {"chicken": [(0, 1)]}
    assert is_attainable("greater_lifesteal_rune", gd) is True


def test_is_attainable_npc_unattainable_currency_rejected():
    """If the pay currency is itself unattainable (no gather/drop/craft/vendor),
    the purchase does not make the item attainable."""
    gd = _gd_npc_rune()
    gd._item_stats["cursed_rune"] = ItemStats(code="cursed_rune", level=40, type_="rune")
    gd._npc_stock["trader"] = {"cursed_rune": 1}
    gd._npc_buy_currency["trader"] = {"cursed_rune": "void_token"}  # nothing yields void_token
    gd._npc_locations["trader"] = (1, 1)
    assert is_attainable("cursed_rune", gd) is False


def test_is_attainable_buy_cycle_safe():
    """A purchase cycle (A paid in B, B paid in A), neither otherwise
    obtainable, is not attainable — the path guard breaks the loop."""
    gd = GameData()
    gd._item_stats = {"a": ItemStats(code="a", level=1, type_="rune"),
                      "b": ItemStats(code="b", level=1, type_="rune")}
    gd._npc_stock = {"v": {"a": 1, "b": 1}}
    gd._npc_buy_currency = {"v": {"a": "b", "b": "a"}}
    gd._npc_locations = {"v": (0, 0)}
    assert is_attainable("a", gd) is False


def test_target_gear_surfaces_npc_purchased_rune():
    """The headline #12 fix: an NPC-bought rune now appears in target_gear, so
    the rune_slot is targeted by the perfect sheet."""
    obj = CharacterObjective.from_game_data(_gd_npc_rune())
    assert obj.target_gear["rune_slot"] == "lifesteal_rune"


def test_is_attainable_now_gold_purchase_gated_on_affordability():
    """Near-term: a gold purchase is attainable_now only when the character can
    afford it. 20000-gold rune: yes at 25000 gold, no at 5000."""
    gd = _gd_npc_rune()
    assert is_attainable_now("lifesteal_rune", make_state(level=20, gold=25000), gd) is True
    assert is_attainable_now("lifesteal_rune", make_state(level=20, gold=5000), gd) is False


def test_is_attainable_now_item_currency_recurses():
    """Near-term buy paid in an ITEM currency: attainable_now iff the currency is
    attainable_now. magic_dust is gatherable, so the rune is buyable now even at
    0 gold (no gold price to meet)."""
    gd = _gd_npc_rune()
    gd._item_stats["dust_rune"] = ItemStats(code="dust_rune", level=20, type_="rune")
    gd._npc_stock["dust_trader"] = {"dust_rune": 3}
    gd._npc_buy_currency["dust_trader"] = {"dust_rune": "magic_dust"}
    gd._npc_locations["dust_trader"] = (4, 4)
    gd._resource_drops = {"dust_node": "magic_dust"}  # magic_dust gatherable
    assert is_attainable_now("dust_rune", make_state(level=20, gold=0), gd) is True


def test_is_attainable_now_buy_cycle_safe():
    """Near-term purchase cycle (a paid in b, b paid in a), neither otherwise
    obtainable: not attainable_now — the path guard breaks the loop."""
    gd = GameData()
    gd._item_stats = {"a": ItemStats(code="a", level=1, type_="rune"),
                      "b": ItemStats(code="b", level=1, type_="rune")}
    gd._npc_stock = {"v": {"a": 1, "b": 1}}
    gd._npc_buy_currency = {"v": {"a": "b", "b": "a"}}
    gd._npc_locations = {"v": (0, 0)}
    assert is_attainable_now("a", make_state(level=5, gold=10000), gd) is False


def test_is_attainable_now_judges_winnability_at_full_hp():
    """A transiently-damaged character (hp 1) must not lose its gear
    targets: strategic attainability rests first (G3 winnable_at_max_hp).
    Live repro 2026-06-11 18:46+: Robby at 31/175 post-fight had every
    armor root evaporate and chosen_root flipped to a 0.24 skill root."""
    gd = _gd_drop_recipes()
    state = make_state(level=5, attack={"air": 5}, hp=1, max_hp=150)
    assert is_attainable_now("feather_coat", state, gd) is True


def test_ring_slots_duplicate_fill_when_one_attainable():
    """Only copper_ring attainable -> BOTH ring slots target it (you can wear
    two identical rings) instead of leaving ring2_slot untargeted."""
    gd = GameData()
    gd._item_stats = {
        "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring", attack={"fire": 2}),
        "iron_sword": ItemStats(code="iron_sword", level=1, type_="weapon", attack={"fire": 5}),
    }
    gd._crafting_recipes = {"copper_ring": {"bar": 1}, "iron_sword": {"bar": 1}}
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    obj = CharacterObjective.from_game_data(gd)
    assert obj.target_gear["ring1_slot"] == "copper_ring"
    assert obj.target_gear["ring2_slot"] == "copper_ring"


def test_artifact_slots_duplicate_filled():
    """Artifacts are duplicate-allowed (join rings in DUPLICATE_SLOT_TYPES): one
    attainable artifact fills ALL THREE artifact slots, mirroring the dual-ring
    carve-out. Acquisition is bounded by ownership downstream (min slots, owned)."""
    gd = GameData()
    gd._item_stats = {"ancient_relic": ItemStats(code="ancient_relic", level=1,
                                                  type_="artifact", attack={"fire": 3})}
    gd._crafting_recipes = {"ancient_relic": {"bar": 1}}
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    obj = CharacterObjective.from_game_data(gd)
    assert obj.target_gear["artifact1_slot"] == "ancient_relic"
    assert obj.target_gear["artifact2_slot"] == "ancient_relic"
    assert obj.target_gear["artifact3_slot"] == "ancient_relic"


def test_near_term_gear_duplicate_fills_empty_second_ring():
    """near_term_gear: ring1 already holds copper_ring, ring2 empty, only
    copper_ring attainable-now -> ring2_slot also targets copper_ring."""
    gd = GameData()
    gd._item_stats = {"copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                               attack={"fire": 2})}
    gd._crafting_recipes = {"copper_ring": {"bar": 1}}
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    obj = CharacterObjective.from_game_data(gd)
    state = make_state(level=5, equipment={"ring1_slot": "copper_ring"})
    nt = obj.near_term_gear(state)
    assert nt.get("ring2_slot") == "copper_ring"  # empty 2nd ring slot still targeted


def test_artifact_slots_duplicate_best_over_second_ranked_distinct():
    """GAP-2 review quirk (Task 2, follow-up wave): with TWO distinct
    attainable artifacts, artifact2_slot must get a 2nd copy of the BEST
    artifact (perfect_relic, equip_value from attack 100) rather than the
    2nd-ranked DISTINCT artifact (lesser_relic, attack 5) — duplicating the
    top item is dup-allowed (DUPLICATE_SLOT_TYPES) and strictly higher value
    than any lower-ranked distinct item, since `attainable` is already
    sorted descending by value. Ownership is NOT a constraint at this
    target-setting layer (acquisition/ownership caps live downstream in
    scoring.py's pick_loadout) — mirrors the ring precedent
    (test_paired_ring_slots_duplicate_best_over_second_distinct)."""
    gd = GameData()
    gd._item_stats = {
        "perfect_relic": ItemStats(code="perfect_relic", level=1, type_="artifact",
                                    attack={"fire": 100}),
        "lesser_relic": ItemStats(code="lesser_relic", level=1, type_="artifact",
                                   attack={"fire": 5}),
    }
    gd._crafting_recipes = {"perfect_relic": {"bar": 1}, "lesser_relic": {"bar": 1}}
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    obj = CharacterObjective.from_game_data(gd)
    assert obj.target_gear["artifact1_slot"] == "perfect_relic"
    assert obj.target_gear["artifact2_slot"] == "perfect_relic"
    assert obj.target_gear["artifact3_slot"] == "perfect_relic"


# --- C1: task-currency leaf ---

def _gd_task_currency() -> GameData:
    """satchel craftable from jasper_crystal, which is bought from a permanent
    tasks_trader NPC using tasks_coin (a task-earnable currency)."""
    gd = GameData()
    gd._task_reward_item_codes = frozenset({"tasks_coin"})
    gd._crafting_recipes = {"satchel": {"jasper_crystal": 1}}
    gd._npc_stock = {"tasks_trader": {"jasper_crystal": 8}}
    gd._npc_buy_currency = {"tasks_trader": {"jasper_crystal": "tasks_coin"}}
    gd._npc_locations = {"tasks_trader": (1, 2)}
    return gd


def test_is_attainable_task_earnable_leaf():
    """tasks_coin is a task-earnable leaf — is_attainable must accept it
    so jasper_crystal (bought with it) becomes attainable."""
    gd = _gd_task_currency()
    assert is_attainable("jasper_crystal", gd) is True


def test_is_attainable_satchel_via_task_currency_chain():
    """satchel crafts from jasper_crystal which needs tasks_coin (task-earnable)
    — the full chain must resolve as attainable."""
    gd = _gd_task_currency()
    assert is_attainable("satchel", gd) is True


def _gd_with_potions() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon", attack={"fire": 4}),
        "small_health_potion": ItemStats(code="small_health_potion", level=5,
            type_="utility", hp_restore=50, crafting_skill="alchemy", crafting_level=5),
        "enhanced_health_potion": ItemStats(code="enhanced_health_potion", level=45,
            type_="utility", hp_restore=300, crafting_skill="alchemy", crafting_level=45),
    }
    gd._crafting_recipes = {
        "copper_dagger": {"bar": 1},
        "small_health_potion": {"sunflower": 3},
        "enhanced_health_potion": {"sunflower": 3},
    }
    gd._resource_drops = {"rocks": "bar", "sunflower_field": "sunflower"}
    gd._resource_skill = {"rocks": ("mining", 1), "sunflower_field": ("alchemy", 1)}
    return gd


def test_target_gear_excludes_utility():
    obj = CharacterObjective.from_game_data(_gd_with_potions())
    assert all("utility" not in slot for slot in obj.target_gear)
    assert "enhanced_health_potion" not in obj.target_gear.values()


def test_near_term_gear_excludes_utility():
    obj = CharacterObjective.from_game_data(_gd_with_potions())
    targets = obj.near_term_gear(make_state(level=10, skills={**make_state().skills, "alchemy": 16}))
    assert all("utility" not in slot for slot in targets)


def test_utility_potion_targets_picks_craftable_now():
    obj = CharacterObjective.from_game_data(_gd_with_potions())
    targets = obj.utility_potion_targets(make_state(level=10, skills={**make_state().skills, "alchemy": 16}))
    assert targets == {"utility1_slot": "small_health_potion"}


def test_is_attainable_now_credits_task_earnable_currency():
    """A leaf priced in a TASK-EARNABLE currency (jasper_crystal @ 8
    tasks_coin) is attainable-now even with 0 coins on hand: the C4 funding
    loop (accept -> fight -> complete, 2ba14d9c) is always available, so the
    currency is producible the same way a winnable monster drop is. The old
    now-leaf only consulted gather/winnable-drop/vendor-affordable and
    silently dropped satchel from near_term_gear forever (live 2026-07-06:
    bag_slot's only root was an unequippable L50 BiS bag)."""
    gd = _gd_drop_recipes()
    gd._item_stats["satchel"] = ItemStats(code="satchel", level=5, type_="bag",
                                          inventory_space=15,
                                          crafting_skill="gearcrafting",
                                          crafting_level=5)
    # satchel needs feather (winnable chicken) + jasper (tasks_coin buy).
    gd._crafting_recipes["satchel"] = {"feather": 2, "jasper_crystal": 1}
    gd._npc_stock = {"tasks_trader": {"jasper_crystal": 8}}
    gd._npc_buy_currency = {"tasks_trader": {"jasper_crystal": "tasks_coin"}}
    gd._npc_locations = {"tasks_trader": (5, 11)}
    gd._task_reward_item_codes = {"tasks_coin"}
    state = make_state(level=5, attack={"air": 5})
    assert state.inventory.get("tasks_coin") is None
    assert is_attainable_now("jasper_crystal", state, gd) is True
    assert is_attainable_now("satchel", state, gd) is True
    targets = CharacterObjective.from_game_data(gd).near_term_gear(state)
    assert targets.get("bag_slot") == "satchel"


def test_is_attainable_now_still_rejects_unaffordable_gold_leaf():
    """The task-earnable arm must not weaken the gold gate: a gold-priced
    leaf with insufficient gold stays not-attainable-now."""
    gd = _gd_drop_recipes()
    gd._crafting_recipes["gold_helm"] = {"rare_gem": 1}
    gd._item_stats["gold_helm"] = ItemStats(code="gold_helm", level=5, type_="helmet",
                                            resistance={"fire": 2})
    gd._npc_stock = {"jeweler": {"rare_gem": 5000}}
    gd._npc_buy_currency = {"jeweler": {"rare_gem": "gold"}}
    gd._npc_locations = {"jeweler": (1, 1)}
    gd._task_reward_item_codes = {"tasks_coin"}
    state = make_state(level=5, attack={"air": 5}, gold=10)
    assert is_attainable_now("gold_helm", state, gd) is False


# --- GAP-1: held/banked stock credits is_attainable_now (2026-07-07) --------

def test_is_attainable_now_credits_banked_leaf():
    """A recipe-leaf material with NO current acquisition source (dragon,
    its only dropper, is unwinnable) still reads attainable-now when the
    full recipe demand is already sitting in the bank — held stock is its
    own acquisition source, independent of gather/drop/task/vendor."""
    gd = _gd_drop_recipes()
    state = make_state(level=5, attack={"air": 5}, bank_items={"dragon_scale": 2})
    assert is_attainable_now("dragon_scale", state, gd) is True
    assert is_attainable_now("dragon_helm", state, gd) is True  # propagates


def test_is_attainable_now_credits_inventory_leaf():
    """Same held-stock credit via CARRIED inventory instead of the bank —
    either counts (mirrors strategy._producible's `inventory or bank`)."""
    gd = _gd_drop_recipes()
    state = make_state(level=5, attack={"air": 5}, inventory={"dragon_scale": 2})
    assert is_attainable_now("dragon_scale", state, gd) is True
    assert is_attainable_now("dragon_helm", state, gd) is True


def test_is_attainable_now_credits_banked_crafted_item_itself():
    """Held stock of the CRAFTED item itself short-circuits the recipe walk:
    a banked dragon_helm reads attainable-now even though its material
    (dragon_scale) is neither held NOR producible — the walk never needs to
    descend into the recipe at all once the crafted item is already in
    hand."""
    gd = _gd_drop_recipes()
    state = make_state(level=5, attack={"air": 5}, bank_items={"dragon_helm": 1})
    assert is_attainable_now("dragon_scale", state, gd) is False  # material alone: still closed
    assert is_attainable_now("dragon_helm", state, gd) is True    # but the crafted item short-circuits


def test_is_attainable_now_bank_none_not_credited():
    """`bank_items=None` means UNKNOWN (bank not yet visited), not zero —
    but it must not be conflated with 'everything available' either: with
    no bank data and nothing carried, an otherwise-unattainable material
    stays unattainable (no crash, no false credit)."""
    gd = _gd_drop_recipes()
    state = make_state(level=5, attack={"air": 5}, bank_items=None)
    assert state.bank_items is None
    assert is_attainable_now("dragon_scale", state, gd) is False
    assert is_attainable_now("dragon_helm", state, gd) is False


def test_is_attainable_now_partial_stock_still_credits_boolean():
    """Attainability is boolean, not quantity-aware: holding only 1 of the
    2 dragon_scale the recipe needs still credits the leaf (and the
    material's own attainability doesn't even need to match the FULL
    recipe count — quantity accounting stays the planner's job, not this
    gate's)."""
    gd = _gd_drop_recipes()
    state = make_state(level=5, attack={"air": 5}, bank_items={"dragon_scale": 1})
    assert is_attainable_now("dragon_scale", state, gd) is True
    assert is_attainable_now("dragon_helm", state, gd) is True


def _gd_item_currency_no_other_source() -> GameData:
    """A recipe-less rune sold by a permanent vendor for an ITEM currency
    (magic_dust) that has NO gather/drop/task/vendor acquisition path of
    its own — the only way to credit it is the held/banked-stock arm
    threaded into the currency-recursion `_attainable_closure` call inside
    `is_attainable_now`'s `leaf_ok` (objective.py ~:210, GAP-1 fold-in)."""
    gd = GameData()
    gd._item_stats = {
        "dust_rune": ItemStats(code="dust_rune", level=5, type_="rune"),
    }
    gd._npc_stock = {"dust_trader": {"dust_rune": 3}}
    gd._npc_buy_currency = {"dust_trader": {"dust_rune": "magic_dust"}}
    gd._npc_locations = {"dust_trader": (4, 4)}
    return gd


def test_is_attainable_now_credits_held_bank_currency():
    """GAP-1 fold-in (task-2 review): a purchase paid in an ITEM currency
    the character already holds in the BANK is attainable-now through the
    stock short-circuit, even though magic_dust has no other production
    source at all (not gatherable, not dropped, not task-earnable, no
    vendor sells it) — the currency-recursion call inside `leaf_ok` passes
    `stock_ok` through, so `_attainable_closure(currency, ...)` finds the
    held stock before it would otherwise fail every leaf arm."""
    gd = _gd_item_currency_no_other_source()
    state = make_state(level=5, gold=0, bank_items={"magic_dust": 20})
    assert is_attainable_now("dust_rune", state, gd) is True


def test_is_attainable_now_bank_none_currency_not_credited():
    """Negative twin: `bank_items=None` (bank unknown) must not be conflated
    with 'the currency is available' — with no bank data and nothing
    carried, and no other acquisition source for magic_dust, the purchase
    stays unattainable."""
    gd = _gd_item_currency_no_other_source()
    state = make_state(level=5, gold=0, bank_items=None)
    assert state.bank_items is None
    assert is_attainable_now("dust_rune", state, gd) is False
