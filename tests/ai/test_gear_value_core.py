"""Tests for the unified gear value ruler core (combat_raw + rank_value) and
its ItemStats adapter/dispatch. Mirrors Formal/GearValue.lean."""

from artifactsmmo_cli.ai.equipment.scoring import armor_score, gather_score, weapon_score
from artifactsmmo_cli.ai.gear_value import gear_value
from artifactsmmo_cli.ai.gear_value_core import Combat, Gather, Rank, combat_raw, rank_value
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.tiers.equip_value import equip_value


def test_combat_raw_sums_eight_stats() -> None:
    assert combat_raw(attack=3, resistance=2, hp_restore=1, hp_bonus=4, dmg=5,
                      critical_strike=6, lifesteal=7, combat_buff=8) == 36


def test_rank_value_matches_equip_value_formula() -> None:
    # 2*(combat_raw + wisdom+prosp+inv+haste) + nonToolBonus
    cr = combat_raw(attack=10, resistance=0, hp_restore=0, hp_bonus=0, dmg=0,
                    critical_strike=0, lifesteal=0, combat_buff=0)
    assert rank_value(cr, wisdom=0, prospecting=0, inventory_space=0, haste=0,
                      subtype="weapon") == 2 * 10 + 1
    assert rank_value(cr, wisdom=0, prospecting=0, inventory_space=0, haste=0,
                      subtype="tool") == 2 * 10 + 0


def test_gear_value_rank_equals_legacy_equip_value() -> None:
    s = ItemStats(code="x", level=1, type_="weapon", attack={"fire": 6},
                  critical_strike=35, hp_bonus=10, dmg=3)
    assert gear_value(s, Rank) == equip_value(s)


def test_gear_value_accepts_rank_instance() -> None:
    s = ItemStats(code="x", level=1, type_="weapon", attack={"fire": 6},
                  critical_strike=35, hp_bonus=10, dmg=3)
    assert gear_value(s, Rank()) == equip_value(s)


def test_gear_value_rejects_unsupported_purpose() -> None:
    s = ItemStats(code="x", level=1, type_="weapon")
    try:
        gear_value(s, object())
    except ValueError as exc:
        assert "unsupported purpose" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for unsupported purpose")


def test_gear_value_rank_tool_subtype_no_bonus() -> None:
    s = ItemStats(code="net", level=1, type_="weapon", attack={"water": 5},
                  subtype="tool")
    # tool subtype: 2 * (5) + 0
    assert gear_value(s, Rank) == 10
    assert gear_value(s, Rank) == equip_value(s)


def test_gear_value_rank_full_utility_stats() -> None:
    s = ItemStats(code="guide", level=1, type_="utility", hp_bonus=25,
                  wisdom=25, prospecting=25)
    # raw = 25 (hp_bonus) + 25 wisdom + 25 prospecting -> 2*75 + 1 = 151
    assert gear_value(s, Rank) == 151
    assert gear_value(s, Rank) == equip_value(s)


def test_combat_purpose_matches_weapon_and_armor_score() -> None:
    weapon = ItemStats(code="w", level=1, type_="weapon", attack={"fire": 6},
                       critical_strike=20)
    armor = ItemStats(code="a", level=1, type_="body_armor", resistance={"fire": 30},
                      hp_bonus=15)
    m_res = {"fire": 25}
    m_atk = {"fire": 40}
    assert gear_value(weapon, Combat(m_atk, m_res)) == weapon_score(weapon, m_res)
    assert gear_value(armor, Combat(m_atk, m_res)) == armor_score(armor, m_atk)


def test_gather_purpose_matches_gather_score() -> None:
    tool = ItemStats(code="axe", level=1, type_="weapon",
                     skill_effects={"woodcutting": -10})
    assert gear_value(tool, Gather("woodcutting")) == gather_score(tool, "woodcutting")
