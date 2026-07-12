"""Recycle protection semantics: caps beat blankets, working kit is sacred.

Regression (trace 2026-07-05, post-restart): `_gear_protected` blanket-excluded
every gear_keep KEY from recyclable_surplus, so gear_keep['copper_helmet']=1
("keep ONE") acted as "keep ALL 41" and the grind hoard stayed invisible to
both the discretionary recycle and the urgency hoist. Meanwhile the freshly
ferried copper_pickaxe (in the bag, not yet equipped) showed up as recyclable
surplus — recycling would have EATEN the working kit.
"""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.recycle_surplus import recyclable_surplus
from artifactsmmo_cli.ai.tiers.guards import SelectionContext, recycle_protected_codes
from tests.test_ai.fixtures import make_state


def _ctx(**kw: object) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
                gear_review_active=False)
    base.update(kw)
    return SelectionContext(**base)


def test_with_profile_caps_no_blanket_protection() -> None:
    """gear_keep quantities are enforced INSIDE recyclable_surplus via
    useful_quantity_cap — a blanket code exclusion on top turns 'keep 1'
    into 'keep all'."""
    ctx = _ctx(gear_keep={"copper_helmet": 1, "iron_boots": 2})
    assert recycle_protected_codes(ctx) == frozenset()


def test_without_profile_legacy_blanket_stands() -> None:
    ctx = _ctx(target_gear=frozenset({"iron_helm"}),
               target_tools=frozenset({"iron_pickaxe"}))
    assert recycle_protected_codes(ctx) == frozenset({"iron_helm", "iron_pickaxe"})


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_helmet": ItemStats(code="copper_helmet", level=1, type_="helmet",
                                   crafting_skill="gearcrafting", crafting_level=1),
        "copper_pickaxe": ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                                    attack={"earth": 5}, skill_effects={"mining": -10},
                                    crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {"copper_helmet": {"copper_bar": 6},
                            "copper_pickaxe": {"copper_bar": 6}}
    gd._workshop_locations = {"gearcrafting": (2, 1), "weaponcrafting": (3, 1)}
    return gd


def test_grind_hoard_visible_with_cap_only_protection() -> None:
    """The live shape: 41 helmets in the bag, one worn, profile keep=1 —
    surplus must be 40, not zero."""
    gd = _gd()
    state = make_state(level=10, skills={"gearcrafting": 8, "weaponcrafting": 2},
                       inventory={"copper_helmet": 41},
                       equipment={"helmet_slot": "copper_helmet"})
    ctx = _ctx(gear_keep={"copper_helmet": 1})
    surplus = recyclable_surplus(state, gd, recycle_protected_codes(ctx),
                                 gear_keep=ctx.gear_keep or None)
    assert surplus.get("copper_helmet") == 40


def test_best_gathering_tool_is_never_recyclable_surplus() -> None:
    """A ferried-but-not-yet-equipped tool is working kit, not scrap. The
    equip leg runs a cycle later — recycling must not race it."""
    gd = _gd()
    state = make_state(level=10, skills={"gearcrafting": 8, "weaponcrafting": 2},
                       inventory={"copper_pickaxe": 1},
                       equipment={"weapon_slot": "copper_dagger"})
    surplus = recyclable_surplus(state, gd, frozenset(), gear_keep={})
    assert "copper_pickaxe" not in surplus


def test_working_kit_keeps_ONE_and_recycles_the_spares() -> None:
    """The kit rule protects the TOOL, not the HOARD. Live Robby 2026-07-12:
    18 copper_axe + 7 fishing_net sat in the bag — both are weaponcrafting GRIND
    RUNGS, so the skill grind kept crafting them, and both are the best owned
    tool for their skill, so the blanket `code in kit` skip shielded EVERY copy.
    recyclable_surplus reported only {copper_ring:1, water_bow:1} while 25 junk
    items filled the bag (17/20 slots) and never came back as materials.

    Same blanket-vs-cap flaw the equipped-code skip already fixed (copper_helmet
    x41): keep ONE (the tool the gather re-arm is about to wear) and reclaim the
    rest."""
    gd = _gd()
    state = make_state(level=10, skills={"gearcrafting": 8, "weaponcrafting": 2},
                       inventory={"copper_pickaxe": 18})
    surplus = recyclable_surplus(state, gd, frozenset(), gear_keep={})
    assert surplus.get("copper_pickaxe") == 17


def test_outclassed_spare_tool_is_still_recyclable() -> None:
    """Only the BEST owned tool per skill is kit; a worse spare stays scrap."""
    gd = _gd()
    gd._item_stats["rusty_pickaxe"] = ItemStats(
        code="rusty_pickaxe", level=1, type_="weapon", attack={"earth": 2},
        skill_effects={"mining": -5}, crafting_skill="weaponcrafting",
        crafting_level=1)
    gd._crafting_recipes["rusty_pickaxe"] = {"copper_bar": 4}
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_pickaxe": 1, "rusty_pickaxe": 2})
    surplus = recyclable_surplus(state, gd, frozenset(), gear_keep={})
    assert "copper_pickaxe" not in surplus
    assert surplus.get("rusty_pickaxe") == 2  # cap 0 under profile mode
