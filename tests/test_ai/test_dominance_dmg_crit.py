"""The delete-dominance gate now scores dmg+crit (the fixed divergence), but the
skill-coverage guard still blocks a non-tool from dominating an uncovered tool.

Spec: docs/superpowers/specs/2026-06-28-gear-unified-ruler-design.md
"""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_value import gear_value
from artifactsmmo_cli.ai.gear_value_core import Rank
from artifactsmmo_cli.ai.inventory_caps import _is_equippable_dominated
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import EQUIPMENT_SLOTS, WorldState


def _make_state(**overrides: object) -> WorldState:
    """Minimal WorldState for dominance-gate tests (mirrors test_ai/fixtures.py)."""
    defaults: dict[str, object] = dict(
        character="testchar",
        level=5,
        xp=100,
        max_xp=500,
        hp=100,
        max_hp=150,
        gold=50,
        skills={"mining": 3, "woodcutting": 2, "fishing": 1, "weaponcrafting": 1,
                "gearcrafting": 1, "jewelrycrafting": 1, "cooking": 1, "alchemy": 1},
        x=0,
        y=0,
        inventory={},
        inventory_max=20,
        inventory_slots_max=20,
        equipment={slot: None for slot in EQUIPMENT_SLOTS},
        cooldown_expires=None,
        task_code=None,
        task_type=None,
        task_progress=0,
        task_total=0,
        bank_items=None,
        bank_gold=None,
        bank_capacity=None,
        pending_items=None,
    )
    defaults.update(overrides)
    defaults.setdefault(
        "task_lifecycle_phase",
        derive_task_lifecycle_phase(
            defaults["task_code"], defaults["task_progress"], defaults["task_total"]  # type: ignore[arg-type]
        ),
    )
    return WorldState(**defaults)  # type: ignore[arg-type]


def test_higher_dmg_crit_now_outvalues_at_gate() -> None:
    """gear_value(Rank) includes dmg+crit; an amulet with both outvalues a plain one.

    Under the OLD _equip_value both amulets had the same score (hp_bonus=5 each,
    dmg/crit ignored) → they tied → plain was NOT dominated. With gear_value(Rank)
    sharp strictly wins, fixing the divergence.

    Spec: 2026-06-28-gear-unified-ruler-design.md — "The one documented behavior
    change: the delete-dominance gate now scores on dmg + critical_strike."
    """
    plain = ItemStats(code="plain", level=1, type_="amulet", hp_bonus=5)
    sharp = ItemStats(code="sharp", level=1, type_="amulet", hp_bonus=5, dmg=10,
                      critical_strike=20)
    # Under the OLD _equip_value (no dmg/crit) these tied; now sharp strictly wins.
    assert gear_value(sharp, Rank) > gear_value(plain, Rank)


def test_dmg_crit_dominate_at_gate() -> None:
    """An amulet with higher dmg+crit now dominates a plain amulet at the delete gate.

    Under the OLD _equip_value both scored only hp_bonus=5 → tied → plain was NOT
    dominated (strictly-higher comparison returned False). With gear_value(Rank)
    sharp scores 2*(5+10+20)+1=71 vs plain's 2*5+1=11 → dominated.

    Using amulet (single-slot) so one copy of sharp suffices to satisfy the
    slot-count threshold (_is_dominated_pure: dominator_owned >= len(slots) = 1).

    Spec: 2026-06-28-gear-unified-ruler-design.md — _is_equippable_dominated routes
    through gear_value(Rank) which scores dmg+critical_strike.
    """
    gd = GameData()
    gd._item_stats = {
        "plain": ItemStats(code="plain", level=1, type_="amulet", hp_bonus=5),
        "sharp": ItemStats(code="sharp", level=1, type_="amulet", hp_bonus=5, dmg=10,
                           critical_strike=20),
    }
    gd._crafting_recipes = {}
    state = _make_state(inventory={"plain": 1, "sharp": 1})
    # sharp strictly dominates plain now that dmg+crit count
    assert _is_equippable_dominated("plain", state, gd) is True
    # sharp has no dominator
    assert _is_equippable_dominated("sharp", state, gd) is False


def test_tool_coverage_guard_blocks_non_tool_from_dominating_tool() -> None:
    """The skill-coverage guard still prevents a non-tool from dominating a tool whose
    skill_effects it fails to cover, even after the ruler swap.

    A weapon with much higher dmg+crit (and thus much higher gear_value) cannot
    dominate a pickaxe because it carries no mining skill_effect — the covers check
    fails and the pickaxe stays protected.

    Spec: 2026-06-28-gear-unified-ruler-design.md — "covers" criterion unchanged;
    only the 'higher' criterion ruler is updated.
    """
    gd = GameData()
    gd._item_stats = {
        "copper_pickaxe": ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                                    attack={"fire": 3},
                                    skill_effects={"mining": -10}),
        "iron_sword": ItemStats(code="iron_sword", level=5, type_="weapon",
                                attack={"fire": 50}, dmg=30, critical_strike=20),
    }
    gd._crafting_recipes = {}
    state = _make_state(inventory={"copper_pickaxe": 1, "iron_sword": 1})
    # iron_sword has gear_value >> copper_pickaxe but lacks mining skill_effect
    assert _is_equippable_dominated("copper_pickaxe", state, gd) is False
