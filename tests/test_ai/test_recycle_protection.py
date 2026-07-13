"""Recycle protection semantics: caps beat blankets, the working tool is sacred.

Protection on the recycle path is the keep authority's (`ai/inventory_keep.py`),
a QUANTITY — never a code-SET, whose type can only say "keep ALL copies". Three
blankets died here, one bug each:

  * `_gear_protected` blanket-excluded every `gear_keep` KEY, so
    gear_keep['copper_helmet']=1 ("keep ONE") acted as "keep ALL 41" and the
    grind hoard stayed invisible to both the discretionary recycle and the
    urgency hoist (trace 2026-07-05).
  * the profile-less `target_gear | target_tools` fallback did the same for every
    BiS code — all 18 `copper_axe` (trace 2026-07-12).
  * meanwhile a `code in kit` skip shielded every copy of the best tool, while
    dropping the kit rule entirely would have EATEN the freshly ferried
    copper_pickaxe (in the bag, not yet equipped).

The authority resolves all three at once: recycle may destroy the copies above
BOTH `keep_in_bag` (which is where WORKING_KIT lives — keep the ONE tool) and
`keep_owned` (EQUIPPED / GEAR_DEMAND / RECIPE_DEMAND / ACTIVE_TASK / CURRENCY).
"""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.recycle_surplus import recyclable_surplus
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from tests.test_ai.fixtures import make_state


def _ctx(**kw: object) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
                gear_review_active=False)
    base.update(kw)
    return SelectionContext(**base)


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
    surplus = recyclable_surplus(state, gd, _ctx(gear_keep={"copper_helmet": 1}))
    assert surplus.get("copper_helmet") == 40


def test_bis_target_code_is_capped_not_blanketed() -> None:
    """The profile-less blanket is GONE: a `target_tools` / `target_gear` code is
    a PURSUIT target, not a hoard licence. 18 pickaxes with no loadout profile
    recorded → keep the 1 the re-arm will wear, reclaim 17."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_pickaxe": 18})
    ctx = _ctx(target_tools=frozenset({"copper_pickaxe"}),
               target_gear=frozenset({"copper_helmet"}))
    assert recyclable_surplus(state, gd, ctx) == {"copper_pickaxe": 17}


def test_best_gathering_tool_is_never_recyclable_surplus() -> None:
    """A ferried-but-not-yet-equipped tool is working kit, not scrap. The
    equip leg runs a cycle later — recycling must not race it."""
    gd = _gd()
    state = make_state(level=10, skills={"gearcrafting": 8, "weaponcrafting": 2},
                       inventory={"copper_pickaxe": 1},
                       equipment={"weapon_slot": "copper_dagger"})
    assert "copper_pickaxe" not in recyclable_surplus(state, gd, _ctx())


def test_working_tool_survives_even_when_the_bank_holds_the_spares() -> None:
    """The ownership cap ALONE would eat it: 18 owned (1 ferried into the bag by
    WithdrawTools, 17 banked by DepositAll), keep_owned 1 → 17 destroyable — and
    the ONLY reachable copy is the working one. `keep_in_bag` (WORKING_KIT) is
    what makes the bag copy untouchable, which is why the recycle path answers to
    both caps."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_pickaxe": 1},
                       bank_items={"copper_pickaxe": 17})
    assert recyclable_surplus(state, gd, _ctx()) == {}


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
    surplus = recyclable_surplus(state, gd, _ctx())
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
    surplus = recyclable_surplus(state, gd, _ctx())
    assert "copper_pickaxe" not in surplus
    assert surplus.get("rusty_pickaxe") == 2  # dominated by copper_pickaxe → keep 0
