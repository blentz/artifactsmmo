import dataclasses
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import patch

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import LEGACY
from artifactsmmo_cli.ai.suppliable import is_suppliable
from artifactsmmo_cli.ai.tiers import objective as objective_mod
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective, is_attainable
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import NO_DROPS_CONTEXT, make_state, obtainable_now


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon", attack={"air": 4}),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon", attack={"fire": 30}),
        "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring", hp_bonus=2),
        "gold_ring": ItemStats(code="gold_ring", level=20, type_="ring", hp_bonus=8),
        "ruby_ring": ItemStats(code="ruby_ring", level=30, type_="ring", hp_bonus=6),
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


def test_is_attainable_gatherable_and_craftable_chain():
    gd = GameData()
    gd._crafting_recipes = {"sword": {"bar": 2}, "bar": {"ore": 3}}
    gd._resource_drops = {"rocks": "ore"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    assert is_attainable("ore", gd) is True          # gatherable raw
    assert is_attainable("sword", gd) is True         # sword<-bar<-ore all attainable


def test_is_attainable_false_for_drop_only_and_blocked_material():
    gd = GameData()
    gd._crafting_recipes = {"cursed": {"boss_drop": 1}}
    gd._resource_drops = {"rocks": "ore"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    assert is_attainable("boss_drop", gd) is False    # no recipe, no drop
    assert is_attainable("cursed", gd) is False        # material unattainable


def test_is_attainable_false_for_cycle():
    gd = GameData()
    gd._crafting_recipes = {"a": {"a": 1}}
    assert is_attainable("a", gd) is False


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
        "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring", hp_bonus=2),
        "silver_ring": ItemStats(code="silver_ring", level=5, type_="ring", hp_bonus=4),
        "drop_only_boots": ItemStats(code="drop_only_boots", level=1, type_="boots",
                                     resistance={"water": 3}),
    }
    gd._crafting_recipes = {
        c: {"bar": 1}
        for c in ("copper_armor", "iron_armor", "dragon_armor", "copper_helmet",
                  "copper_ring", "silver_ring")
    }
    _crafted_at(gd, "gearcrafting", "copper_armor", "iron_armor", "dragon_armor", "copper_helmet")
    _crafted_at(gd, "jewelrycrafting", "copper_ring", "silver_ring")
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    gd._resource_locations = {"rocks": [(1, 0)]}
    return gd


def _crafted_at(gd: GameData, skill: str, *codes: str) -> None:
    """Give each recipe item its crafting skill and the skill a workshop, as
    every real recipe has: the obtain model counts a craft only where the
    executor could perform it."""
    for code in codes:
        gd._item_stats[code] = dataclasses.replace(gd._item_stats[code], crafting_skill=skill,
                                                   crafting_level=1)
    gd._workshop_locations = {**gd._workshop_locations, skill: (0, len(gd._workshop_locations))}


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
    _crafted_at(gd, "gearcrafting", "feather_coat", "dragon_helm")
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    gd._resource_locations = {"rocks": [(1, 0)]}
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


def test_obtainable_now_accepts_winnable_monster_drop_chain():
    """Trace 2026-06-11 17:21 inert-fix bug: copper_armor (wool from a
    trivially-winnable monster) was rejected by the gathering-only
    is_attainable, leaving zero armor roots. The state-aware predicate must
    accept craft chains bottoming out in winnable, located monster drops."""
    gd = _gd_drop_recipes()
    state = make_state(level=5, attack={"air": 5})   # sheet attack → chicken winnable
    assert obtainable_now("feather_coat", state, gd) is True


def test_obtainable_now_rejects_unwinnable_monster_drop():
    """dragon_scale only drops from an unbeatable monster → dragon_helm is
    NOT a near-term target (self-unlocks later as gear/level improve)."""
    gd = _gd_drop_recipes()
    state = make_state(level=5, attack={"air": 5})
    assert obtainable_now("dragon_helm", state, gd) is False


def test_obtainable_now_requires_known_spawn():
    """A winnable dropper with no known map location does not count
    (mirrors strategy._producible's spawn-location gate)."""
    gd = _gd_drop_recipes()
    gd._monster_locations = {"dragon": [(9, 9)]}   # chicken spawn unknown
    state = make_state(level=5, attack={"air": 5})
    assert obtainable_now("feather_coat", state, gd) is False


def test_obtainable_now_cycle_safe():
    gd = GameData()
    gd._crafting_recipes = {"a": {"a": 1}}
    assert obtainable_now("a", make_state(), gd) is False


# ---------------------------------------------------------------------------
# is_suppliable — CAN this character ever hold the code, as opposed to
# `classify_target`'s can it get one TODAY. Live case: `novice_guide`.
#
# Coverage note (this project sets `branch = false`): every arm below is pinned
# to BOTH outcomes, not merely executed once.
# ---------------------------------------------------------------------------

def _gd_fixed_supply() -> GameData:
    """A world with one minted item and one fixed-supply item.

    `relic` is `novice_guide`'s shape: real item stats, so the graph knows it
    exists and gear ranking will happily rank it, but no recipe, no resource
    drop, no monster drop and no vendor — nothing that can ever mint one.
    """
    gd = _gd_drop_recipes()
    gd._item_stats["relic"] = ItemStats(code="relic", level=1, type_="artifact",
                                        hp_bonus=25)
    return gd


def test_is_suppliable_true_for_a_producible_target_that_is_blocked_today():
    """THE INVARIANT THAT MUST NOT BREAK. `dragon_helm` crafts from a drop off
    an unbeatable monster: unattainable NOW, but something mints it, so it is
    suppliable and the walk must keep grinding toward it. If this ever flips to
    False the gate has become a second near-term walk and it has silently
    cancelled every skill-grind and gear-grind root in the game."""
    gd = _gd_fixed_supply()
    state = make_state(level=5, attack={"air": 5})
    assert obtainable_now("dragon_helm", state, gd) is False
    assert is_suppliable("dragon_helm", state, gd) is True


def test_is_suppliable_false_for_a_fixed_supply_item_with_no_free_copy():
    """Nothing mints `relic` and this character holds none, so no sequence of
    actions can ever put one in its hands. A copy a sibling is WEARING is in no
    inventory this character reads and not in the bank, so it correctly fails to
    count as supply here — that is the live `novice_guide` case, where one copy
    exists on the account and a sibling wears it."""
    gd = _gd_fixed_supply()
    state = make_state(level=5)
    assert is_suppliable("relic", state, gd) is False


def test_is_suppliable_true_when_the_fixed_supply_copy_is_in_inventory():
    gd = _gd_fixed_supply()
    state = make_state(level=5, inventory={"relic": 1})
    assert is_suppliable("relic", state, gd) is True


def test_is_suppliable_true_when_the_fixed_supply_copy_is_in_the_bank():
    """The bank is ACCOUNT-WIDE, so a banked copy is free for whichever
    character withdraws it first."""
    gd = _gd_fixed_supply()
    state = make_state(level=5, bank_items={"relic": 1})
    assert is_suppliable("relic", state, gd) is True


def test_is_suppliable_true_for_a_task_earnable_item_the_graph_cannot_see():
    """The task board is a mint `RequirementGraph` has no `SourceKind` for, so
    the graph alone reports `tasks_coin` routeless. In the live bundle it is the
    ONLY task-earnable item among the ten the graph calls routeless; without
    this arm its funding loop would be declared dead."""
    gd = _gd_fixed_supply()
    gd._item_stats["coin"] = ItemStats(code="coin", level=1, type_="currency")
    gd._task_reward_item_codes = {"coin"}
    state = make_state(level=5)
    assert gd.is_task_earnable("coin") is True
    assert is_suppliable("coin", state, gd) is True


def test_classify_target_still_reports_a_sourceless_code_as_its_own_blocker():
    """`classify_target`'s FOURTH shape: an item with no recipe and no
    acquisition source classifies as its own blocker (`blocker == code`). The
    arm must stay: the material loop exhausts whenever a recipe's materials
    are all attainable-now, and `classify_target` is public."""
    gd = _gd_fixed_supply()
    state = make_state(level=5, attack={"air": 5})
    target = CharacterObjective.from_game_data(gd).classify_target("relic", state)
    assert target.attainable is False
    assert target.blocking_skill is None
    assert target.blocker == "relic"


def test_classify_target_asks_one_obtain_model_per_call() -> None:
    """Plan B Task 14c fix round 1: the target and each of its recipe's
    materials are asked of one state, so one obtain model answers them all;
    the classification is the one the near-term model gives each alone."""
    gd = _gd_drop_recipes()
    state = make_state(level=5, attack={"air": 5})
    obj = CharacterObjective.from_game_data(gd)
    built: list[ObtainModel] = []
    real = objective_mod.ObtainModel

    def counting(*args: object) -> ObtainModel:
        model = real(*args)  # type: ignore[arg-type]
        built.append(model)
        return model

    with patch.object(objective_mod, "ObtainModel", counting):
        helm = obj.classify_target("dragon_helm", state)
        coat = obj.classify_target("feather_coat", state)
    assert len(built) == 2
    assert (helm.attainable, helm.blocker) == (False, "dragon_scale")
    assert not obtainable_now("dragon_helm", state, gd)
    assert not obtainable_now("dragon_scale", state, gd)
    assert (coat.attainable, coat.blocker) == (True, None)


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
    targets it; only the near-term model gates on current winnability."""
    gd = _gd_drop_recipes()
    assert is_attainable("dragon_helm", gd) is True
    assert obtainable_now("dragon_helm", make_state(level=5, attack={"air": 5}), gd) is False


def test_is_attainable_requires_known_spawn():
    """A monster drop with NO known spawn location is not producible (the bot
    could never reach the dropper). Removing chicken's spawn rejects
    feather_coat."""
    gd = _gd_drop_recipes()
    gd._monster_locations = {"dragon": [(9, 9)]}   # chicken spawn unknown
    assert is_attainable("feather_coat", gd) is False


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


def test_obtainable_now_gold_purchase_gated_on_affordability():
    """Near-term: a gold purchase is attainable_now only when the character can
    afford it. 20000-gold rune: yes at 25000 gold, no at 5000."""
    gd = _gd_npc_rune()
    assert obtainable_now("lifesteal_rune", make_state(level=20, gold=25000), gd) is True
    assert obtainable_now("lifesteal_rune", make_state(level=20, gold=5000), gd) is False


def test_obtainable_now_item_currency_recurses():
    """Near-term buy paid in an ITEM currency: attainable_now iff the currency is
    attainable_now. magic_dust is gatherable, so the rune is buyable now even at
    0 gold (no gold price to meet)."""
    gd = _gd_npc_rune()
    gd._item_stats["dust_rune"] = ItemStats(code="dust_rune", level=20, type_="rune")
    gd._npc_stock["dust_trader"] = {"dust_rune": 3}
    gd._npc_buy_currency["dust_trader"] = {"dust_rune": "magic_dust"}
    gd._npc_locations["dust_trader"] = (4, 4)
    gd._resource_drops = {"dust_node": "magic_dust"}  # magic_dust gatherable
    gd._resource_skill = {"dust_node": ("alchemy", 1)}
    gd._resource_locations = {"dust_node": [(5, 5)]}
    assert obtainable_now("dust_rune", make_state(level=20, gold=0), gd) is True


def test_obtainable_now_buy_cycle_safe():
    """Near-term purchase cycle (a paid in b, b paid in a), neither otherwise
    obtainable: not attainable_now — the path guard breaks the loop."""
    gd = GameData()
    gd._item_stats = {"a": ItemStats(code="a", level=1, type_="rune"),
                      "b": ItemStats(code="b", level=1, type_="rune")}
    gd._npc_stock = {"v": {"a": 1, "b": 1}}
    gd._npc_buy_currency = {"v": {"a": "b", "b": "a"}}
    gd._npc_locations = {"v": (0, 0)}
    assert obtainable_now("a", make_state(level=5, gold=10000), gd) is False


def test_obtainable_now_judges_winnability_at_full_hp():
    """A transiently-damaged character (hp 1) must not lose its gear
    targets: strategic attainability rests first (G3 winnable_at_max_hp).
    Live repro 2026-06-11 18:46+: Robby at 31/175 post-fight had every
    armor root evaporate and chosen_root flipped to a 0.24 skill root."""
    gd = _gd_drop_recipes()
    state = make_state(level=5, attack={"air": 5}, hp=1, max_hp=150)
    assert obtainable_now("feather_coat", state, gd) is True


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


def test_obtainable_now_credits_task_earnable_currency():
    """A leaf priced in a TASK-EARNABLE currency (jasper_crystal @ 8
    tasks_coin) is attainable-now even with 0 coins on hand: the C4 funding
    loop (accept -> fight -> complete, 2ba14d9c) is always available, so the
    currency is producible the same way a winnable monster drop is. The old
    now-leaf only consulted gather/winnable-drop/vendor-affordable and
    silently dropped satchel from the near-term gear forever (live 2026-07-06:
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
    assert obtainable_now("jasper_crystal", state, gd) is True
    assert obtainable_now("satchel", state, gd) is True


def test_obtainable_now_still_rejects_unaffordable_gold_leaf():
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
    assert obtainable_now("gold_helm", state, gd) is False


# --- GAP-1: held/banked stock credits the near-term model (2026-07-07) --------

def test_obtainable_now_credits_banked_leaf():
    """A recipe-leaf material with NO current acquisition source (dragon,
    its only dropper, is unwinnable) still reads attainable-now when the
    full recipe demand is already sitting in the bank — held stock is its
    own acquisition source, independent of gather/drop/task/vendor."""
    gd = _gd_drop_recipes()
    state = make_state(level=5, attack={"air": 5}, bank_items={"dragon_scale": 2})
    assert obtainable_now("dragon_scale", state, gd) is True
    assert obtainable_now("dragon_helm", state, gd) is True  # propagates


def test_obtainable_now_credits_inventory_leaf():
    """Same held-stock credit via CARRIED inventory instead of the bank —
    either counts (mirrors strategy._producible's `inventory or bank`)."""
    gd = _gd_drop_recipes()
    state = make_state(level=5, attack={"air": 5}, inventory={"dragon_scale": 2})
    assert obtainable_now("dragon_scale", state, gd) is True
    assert obtainable_now("dragon_helm", state, gd) is True


def test_obtainable_now_credits_banked_crafted_item_itself():
    """Held stock of the CRAFTED item itself short-circuits the recipe walk:
    a banked dragon_helm reads attainable-now even though its material
    (dragon_scale) is neither held NOR producible — the walk never needs to
    descend into the recipe at all once the crafted item is already in
    hand."""
    gd = _gd_drop_recipes()
    state = make_state(level=5, attack={"air": 5}, bank_items={"dragon_helm": 1})
    assert obtainable_now("dragon_scale", state, gd) is False  # material alone: still closed
    assert obtainable_now("dragon_helm", state, gd) is True    # but the crafted item short-circuits


def test_obtainable_now_bank_none_not_credited():
    """`bank_items=None` means UNKNOWN (bank not yet visited), not zero —
    but it must not be conflated with 'everything available' either: with
    no bank data and nothing carried, an otherwise-unattainable material
    stays unattainable (no crash, no false credit)."""
    gd = _gd_drop_recipes()
    state = make_state(level=5, attack={"air": 5}, bank_items=None)
    assert state.bank_items is None
    assert obtainable_now("dragon_scale", state, gd) is False
    assert obtainable_now("dragon_helm", state, gd) is False


def test_obtainable_now_counts_stock_in_the_quantity_the_recipe_needs():
    """Holding 1 of the 2 dragon_scale the recipe needs, with the dragon
    unwinnable, makes the scale attainable but NOT the helm. The old walk
    credited any single copy, and the helm then became a target that could not
    be finished; quantity is now part of the question (step 4 of
    docs/PLAN_decision_architecture_redesign.md)."""
    gd = _gd_drop_recipes()
    state = make_state(level=5, attack={"air": 5}, bank_items={"dragon_scale": 1})
    assert obtainable_now("dragon_scale", state, gd) is True
    assert obtainable_now("dragon_helm", state, gd) is False
    full = make_state(level=5, attack={"air": 5}, bank_items={"dragon_scale": 2})
    assert obtainable_now("dragon_helm", full, gd) is True


def _gd_item_currency_no_other_source() -> GameData:
    """A recipe-less rune sold by a permanent vendor for an ITEM currency
    (magic_dust) that has NO gather/drop/task/vendor acquisition path of
    its own — the only way to credit it is the held/banked-stock arm
    threaded into the currency-recursion `_attainable_closure` call inside
    the near-term walk's `leaf_ok` (GAP-1 fold-in)."""
    gd = GameData()
    gd._item_stats = {
        "dust_rune": ItemStats(code="dust_rune", level=5, type_="rune"),
    }
    gd._npc_stock = {"dust_trader": {"dust_rune": 3}}
    gd._npc_buy_currency = {"dust_trader": {"dust_rune": "magic_dust"}}
    gd._npc_locations = {"dust_trader": (4, 4)}
    return gd


def test_obtainable_now_credits_held_bank_currency():
    """GAP-1 fold-in (task-2 review): a purchase paid in an ITEM currency
    the character already holds in the BANK is attainable-now through the
    stock short-circuit, even though magic_dust has no other production
    source at all (not gatherable, not dropped, not task-earnable, no
    vendor sells it) — the currency-recursion call inside `leaf_ok` passes
    `stock_ok` through, so `_attainable_closure(currency, ...)` finds the
    held stock before it would otherwise fail every leaf arm."""
    gd = _gd_item_currency_no_other_source()
    state = make_state(level=5, gold=0, bank_items={"magic_dust": 20})
    assert obtainable_now("dust_rune", state, gd) is True


def test_obtainable_now_bank_none_currency_not_credited():
    """Negative twin: `bank_items=None` (bank unknown) must not be conflated
    with 'the currency is available' — with no bank data and nothing
    carried, and no other acquisition source for magic_dust, the purchase
    stays unattainable."""
    gd = _gd_item_currency_no_other_source()
    state = make_state(level=5, gold=0, bank_items=None)
    assert state.bank_items is None
    assert obtainable_now("dust_rune", state, gd) is False


def test_obtainable_now_counts_no_ge_order():
    """Goal emission fills a GE order only as the cheaper venue for an item an
    NPC also sells, so a target a GE order alone supplies would be a root
    nothing plans. Live 2026-09-27: counting fills gave every character 8-10
    such targets. The same order IS a route to the model, under LEGACY."""
    gd = _gd_npc_rune()
    gd._npc_stock = {}
    gd._ge_sell_orders = {"lifesteal_rune": ("order", 100, 3)}
    gd.world.grand_exchange_tile = (2, 2)
    state = make_state(level=20, gold=1000)
    model = ObtainModel(state, gd, NO_DROPS_CONTEXT, datetime.now(UTC))
    assert model.feasible("lifesteal_rune", 1, LEGACY), "vacuous: the GE order is no route"
    assert obtainable_now("lifesteal_rune", state, gd) is False


def test_obtainable_now_counts_a_reachable_underground_resource():
    """A resource with no overworld tile but a reachable layered one is
    gathered by the action pool (an underground `gold_rocks`), so a gear piece
    made from it is attainable now."""
    gd = _gd_near_term()
    gd._resource_locations = {}
    state = make_state(level=5)
    assert obtainable_now("copper_armor", state, gd) is False
    # Its layered tile lies in the character's own region (ruling I-3: a
    # gather counts where the walk reaches).
    with (patch.object(GameData, "resource_spawn_known", return_value=True),
          patch.object(GameData, "layered_locations",
                       return_value=[(state.x, state.y, state.layer)])):
        assert obtainable_now("copper_armor", state, gd) is True


def test_obtainable_now_pays_from_the_pocket_not_from_future_fights():
    """Near-term attainability is about what the character can afford NOW:
    a winnable monster that pays gold does not make an unaffordable vendor
    item attainable (the step graph, which works toward a target over time,
    does count fight gold)."""
    gd = _gd_npc_rune()
    gd._monster_level = {"chicken": 1}
    gd._monster_hp = {"chicken": 1}
    gd._monster_locations = {"chicken": [(1, 1)]}
    fill_monster_stat_defaults(gd)
    gd.monsters.min_gold = {"chicken": 1}
    gd.monsters.max_gold = {"chicken": 3}
    state = make_state(level=20, gold=100, attack={"fire": 50})
    model = ObtainModel(state, gd, NO_DROPS_CONTEXT, datetime.now(UTC))
    assert model.feasible("gold", 20000, replace(LEGACY, fight_gold=True)), \
        "vacuous: the chicken is no gold route"
    assert obtainable_now("lifesteal_rune", state, gd) is False
