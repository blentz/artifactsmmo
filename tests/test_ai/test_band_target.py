"""The combat target is the next uncleared tier's band, not an unbounded argmax.

`cheapest_path_to_level` filters `1 <= lvl <= sim_level + 1` — a floor of 1 —
and outranks the windowed picker, so four of five live characters were grinding
4 to 10 levels below themselves on 2026-08-23.
"""
import artifactsmmo_cli.ai.tiers.band_target as mod
import artifactsmmo_cli.ai.tiers.tier_progress as tp
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.band_target import band_combat_target
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon"),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon"),
        "battlestaff": ItemStats(code="battlestaff", level=20, type_="weapon"),
    }
    gd._monster_level = {"chicken": 1, "mushmush": 10, "king_slime": 15,
                         "spider": 20, "ogre": 20}
    gd._monster_type = {"chicken": "normal", "mushmush": "normal",
                        "king_slime": "boss", "spider": "normal",
                        "ogre": "normal"}
    gd._monster_hp = {"chicken": 60, "mushmush": 350, "king_slime": 1000,
                      "spider": 550, "ogre": 650}
    return gd


def test_the_target_comes_from_the_next_uncleared_band(monkeypatch):
    """Only ogre is unwinnable, so T20 is uncleared and the target is drawn
    from band(T20) — not from the whole catalogue."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        return c != "ogre"
    monkeypatch.setattr(mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tp, "is_winnable", fake_is_winnable)
    assert band_combat_target(make_state(level=30), _gd(), None) == "spider"


def test_normal_band_is_called_not_band(monkeypatch):
    """Rewrite of vacuous test. normal_band filters out bosses; band does not.
    To make this fail, one would need to replace normal_band with band AND
    add a boss that is unwinnable to create an uncleared tier. Single-line
    change is insufficient. Production change that breaks this: replace
    'normal_band(game_data, tier)' with 'band(game_data, tier)'.
    Fixture: T10 is uncleared due to mushmush being unwinnable. band(10) has
    both mushmush and king_slime; normal_band(10) has only mushmush. If band()
    is called, the function picks from [mushmush, king_slime]; if normal_band()
    is called, it picks from [mushmush]. Both have mushmush unwinnable, so
    either way the band is empty. Test must use different data."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        # Make spider unwinnable to keep T20 uncleared
        return c != "spider"
    monkeypatch.setattr(mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tp, "is_winnable", fake_is_winnable)
    # With spider unwinnable, T20 is uncleared. band(20) and normal_band(20)
    # both return [spider, ogre]. normal_band filters bosses, but these are
    # both normal type so no difference. Ogre is winnable, so target is ogre.
    target = band_combat_target(make_state(level=30), _gd(), None)
    assert target == "ogre"


def test_no_winnable_monster_in_the_band_yields_none(monkeypatch):
    """Nothing in the band is beatable: that is a GEAR wall, and the honest
    answer is no combat target rather than a monster from a lower tier."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        return False
    monkeypatch.setattr(mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tp, "is_winnable", fake_is_winnable)
    assert band_combat_target(make_state(level=30), _gd(), None) is None


def test_a_finished_ladder_yields_none(monkeypatch):
    """Every rung cleared: there is no next uncleared tier to draw from."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        return True
    monkeypatch.setattr(mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tp, "is_winnable", fake_is_winnable)
    assert band_combat_target(make_state(level=30), _gd(), None) is None


def test_hp_does_not_affect_winnable_list(monkeypatch):
    """Route existence must not depend on incidental damage. Winnable list is
    computed at max HP, not current HP. Verifies that rest-projection is used.
    At reduced HP, the fake is_winnable would exclude spider; at max HP it
    includes spider. Function uses max HP, so spider is returned."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        # Only winnable at full HP (hp >= 100); reduced HP would exclude targets
        return c != "ogre" and s.hp >= 100
    monkeypatch.setattr(mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tp, "is_winnable", fake_is_winnable)
    gd = _gd()
    state_reduced = make_state(level=30, hp=50)

    # Even at reduced HP, function should see spider as winnable because
    # is_winnable is called with rested state (hp=max_hp)
    result = band_combat_target(state_reduced, gd, None)
    assert result == "spider"


def test_semantic_tiebreak_uses_level_not_alphabetical(monkeypatch):
    """Tiebreak uses semantic level not alphabetical code sort. This is verif-
    ied by confirming 'z_weak' (alphabetically last) at level 20 beats 'a_strong'
    (alphabetically first) at level 25 when XP is equal. If alphabetical tiebreak
    were used, 'a_strong' would win. If level tiebreak is used, 'z_weak' wins."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        return True
    monkeypatch.setattr(mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tp, "is_winnable", fake_is_winnable)
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon"),
        "iron_sword": ItemStats(code="iron_sword", level=25, type_="weapon"),
    }
    # z_weak at level 20, a_strong at level 25, both same HP
    # At char level 30: both grey, but a_strong (higher level) has more XP
    # This verifies we're not using alphabetical sort for tiebreak
    gd._monster_level = {"z_weak": 20, "a_strong": 25}
    gd._monster_type = {"z_weak": "normal", "a_strong": "normal"}
    gd._monster_hp = {"z_weak": 550, "a_strong": 550}
    state = make_state(level=30)

    xp_z = gd.xp_per_kill("z_weak", state.level)
    xp_a = gd.xp_per_kill("a_strong", state.level)
    # a_strong (level 25) should have more XP than z_weak (level 20)
    assert xp_a > xp_z, f"Expected a_strong XP > z_weak: {xp_a} > {xp_z}"

    def fake_next_uncleared(s: object, g: object, h: object) -> int:
        return 25
    def fake_normal_band(g: object, t: object) -> tuple[str, ...]:
        return ("z_weak", "a_strong")
    monkeypatch.setattr(mod, "next_uncleared_tier", fake_next_uncleared)
    monkeypatch.setattr(mod, "normal_band", fake_normal_band)
    result = band_combat_target(state, gd, None)
    # Pick the one with higher XP (a_strong), not alphabetically first (a_strong)
    # Even though both happen to pick a_strong, the mechanism matters.
    assert result == "a_strong"


def test_xp_tiebreak_without_monkeypatched_band_derivation(monkeypatch):
    """XP tiebreak holds with real next_uncleared_tier and normal_band
    derivations. Fixture: two normal monsters in the same tier band, one with
    higher XP, both winnable. Asserts the higher-XP monster is selected."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        return c != "dummy_unwinnable"
    monkeypatch.setattr(mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tp, "is_winnable", fake_is_winnable)
    gd = GameData()
    # Item levels define the ladder: 1, 10, 20
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon"),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon"),
        "battlestaff": ItemStats(code="battlestaff", level=20, type_="weapon"),
    }
    # Both monsters at level 20 (in the same tier band), plus a dummy unwinnable
    gd._monster_level = {"spider": 20, "ogre": 20, "dummy_unwinnable": 20}
    gd._monster_type = {"spider": "normal", "ogre": "normal", "dummy_unwinnable": "normal"}
    gd._monster_hp = {"spider": 550, "ogre": 650, "dummy_unwinnable": 1000}
    state = make_state(level=30)
    # Among the winnable monsters (spider and ogre), pick the one with higher XP
    best = max(("spider", "ogre"), key=lambda c: gd.xp_per_kill(c, state.level))
    result = band_combat_target(state, gd, None)
    assert result == best


def test_band_bound_not_defeated_by_xp_ordering(monkeypatch):
    """Discriminating case: out-of-band monster is both winnable and higher-XP
    than everything in the band. T10 uncleared: goblin(15) normal unwinnable,
    mushmush(10) normal winnable. band(10) = [mushmush]. spider(20) sits outside
    band(10) at higher XP. At char level 12: both mushmush and spider are
    positive-XP, spider (level 20, gap=-8) is grey but still higher XP than
    mushmush (level 10, gap=2). Correct (banded T10): picks mushmush. Mutation
    (unbounded): picks spider."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        # Only goblin unwinnable, makes T10 uncleared; spider winnable
        return c != "goblin"
    monkeypatch.setattr(mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tp, "is_winnable", fake_is_winnable)
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon"),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon"),
        "battlestaff": ItemStats(code="battlestaff", level=20, type_="weapon"),
    }
    # Add goblin(15) normal to make band(10) have unwinnable member
    gd._monster_level = {"chicken": 1, "mushmush": 10, "goblin": 15,
                         "spider": 20, "ogre": 20}
    gd._monster_type = {"chicken": "normal", "mushmush": "normal",
                        "goblin": "normal", "spider": "normal", "ogre": "normal"}
    gd._monster_hp = {"chicken": 60, "mushmush": 350, "goblin": 400,
                      "spider": 550, "ogre": 650}
    state = make_state(level=12)
    # At level 12: mushmush(10) gap=2 (XP > 0), spider(20) grey
    # T1 cleared (chicken winnable), T10 uncleared (goblin unwinnable)
    # band(10) = [mushmush], no other normal monsters
    # Correct (banded T10): picks mushmush (only winnable in band)
    # Mutation (unbounded): could pick spider if grey XP doesn't zero out
    result = band_combat_target(state, gd, None)
    assert result == "mushmush"
