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


def test_a_boss_in_the_band_is_never_the_target(monkeypatch):
    """king_slime sits in band(10) and is type=boss. It must not be picked even
    when it is the only unwinnable thing keeping the rung open."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        return c != "king_slime"
    monkeypatch.setattr(mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tp, "is_winnable", fake_is_winnable)
    target = band_combat_target(make_state(level=30), _gd(), None)
    assert target != "king_slime"


def test_the_target_is_winnable(monkeypatch):
    """An unwinnable monster is what keeps the rung open; it is never the thing
    to go and fight. Lower tiers are all winnable, tier 20 has unwinnable
    monsters, so the target is drawn from tier 20's band."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        # Make tiers 1-15 all winnable, but tier 20 has ogre unwinnable
        return c != "ogre"
    monkeypatch.setattr(mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tp, "is_winnable", fake_is_winnable)
    assert band_combat_target(make_state(level=30), _gd(), None) == "spider"


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


def test_the_highest_xp_winnable_in_the_band_wins(monkeypatch):
    """XP tiebreak: the choice is the best XP per kill within the band.
    Band derivation is covered by the other five tests. This test pins XP
    tiebreak only, using monkeypatched band/tier derivations."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        return True
    monkeypatch.setattr(mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tp, "is_winnable", fake_is_winnable)
    gd = _gd()
    gd._monster_level = {"spider": 20, "ogre": 22}
    gd._monster_type = {"spider": "normal", "ogre": "normal"}
    gd._monster_hp = {"spider": 550, "ogre": 650}
    state = make_state(level=20)
    best = max(("spider", "ogre"), key=lambda c: gd.xp_per_kill(c, state.level))
    def fake_next_uncleared(s: object, g: object, h: object) -> int:
        return 20
    def fake_normal_band(g: object, t: object) -> tuple[str, ...]:
        return ("spider", "ogre")
    monkeypatch.setattr(mod, "next_uncleared_tier", fake_next_uncleared)
    monkeypatch.setattr(mod, "normal_band", fake_normal_band)
    assert band_combat_target(state, gd, None) == best


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
