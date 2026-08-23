"""The combat target is the next uncleared tier's band, not an unbounded argmax.

`cheapest_path_to_level` filters `1 <= lvl <= sim_level + 1` — a floor of 1 —
and outranks the windowed picker, so four of five live characters were grinding
4 to 10 levels below themselves on 2026-08-23.
"""
import dataclasses

import artifactsmmo_cli.ai.tiers.band_target as mod
import artifactsmmo_cli.ai.tiers.tier_progress as tp
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.tiers.band_target import band_combat_target
from artifactsmmo_cli.ai.tiers.tier_ladder import band as raw_band
from artifactsmmo_cli.ai.tiers.tier_ladder import normal_band as real_normal_band
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
    """Genuinely discriminating rewrite. The prior version used a band where
    the only boss present (`king_slime`) was never a candidate either way,
    so swapping `normal_band` for `band` changed nothing — 8/8 tests passed
    under that mutation.

    This fixture makes the boss filter load-bearing: `strongboss` (type
    boss, level 10) sits in the SAME band as `other_normal` (type normal,
    level 10), both winnable, both same HP. The XP formula's monster-type
    multiplier is exact (`_MONSTER_TYPE_MULT10`: boss=20, normal=10 — see
    `monster_catalog.py`), so with identical level/hp `strongboss`'s XP is
    always exactly double `other_normal`'s — it wins the XP argmax if it is
    ever a candidate. `weakling` (normal, level 10, unwinnable) is what
    keeps T10 uncleared, since `tier_cleared` only reads the boss-filtered
    band and never consults the boss's winnability.

    band(10) = (other_normal, strongboss, weakling) -- includes the boss.
    normal_band(10) = (other_normal, weakling) -- excludes it.

    Correct (normal_band): winnable = [other_normal] -> target=other_normal.
    Mutated (band): winnable = [other_normal, strongboss], strongboss's XP
    (double) wins the argmax -> target=strongboss.

    Verified below by printing both candidates' xp_per_kill BEFORE the
    assertion, per the coordinator's instruction not to assume the ranking.
    """
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        return c != "weakling"
    monkeypatch.setattr(mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tp, "is_winnable", fake_is_winnable)

    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon"),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon"),
        "battlestaff": ItemStats(code="battlestaff", level=20, type_="weapon"),
    }
    gd._monster_level = {"chicken": 1, "weakling": 10, "other_normal": 10,
                         "strongboss": 10}
    gd._monster_type = {"chicken": "normal", "weakling": "normal",
                        "other_normal": "normal", "strongboss": "boss"}
    gd._monster_hp = {"chicken": 60, "weakling": 300, "other_normal": 300,
                      "strongboss": 300}
    state = make_state(level=12)

    # Verify the discriminating property directly, not by assumption:
    # band(10) includes the boss, normal_band(10) does not, and the boss
    # outranks the only other winnable candidate on XP.
    assert raw_band(gd, 10) == ("other_normal", "strongboss", "weakling")
    assert real_normal_band(gd, 10) == ("other_normal", "weakling")
    xp_other = gd.xp_per_kill("other_normal", state.level)
    xp_boss = gd.xp_per_kill("strongboss", state.level)
    print(f"sort key other_normal={xp_other} strongboss={xp_boss}")
    assert xp_boss > xp_other, (
        f"fixture must make the boss outrank the normal monster on XP: "
        f"other_normal={xp_other} strongboss={xp_boss}")

    target = band_combat_target(state, gd, None)
    assert target == "other_normal", (
        "boss must never be the target even though it outranks the only "
        f"other winnable candidate on XP; got {target!r}")


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


def test_hp_does_not_affect_winnable_list(bundle_game_data):
    """Route existence must not depend on incidental damage. Uses the REAL
    `is_winnable` (no monkeypatch) against the real game catalog, the same
    pattern as `test_gear_target_tier_is_independent_of_current_hp` in
    `test_tier_progress.py` — a stubbed predicate cannot exercise the HP
    path at all, since the fake merely re-encodes whatever assumption it was
    written with.

    Scenario: `l11_band_floor` (level 11, `derive_combat_stats=True` so its
    equipped gear yields real, non-zero attack/dmg stats — `is_winnable`
    reads 0 attack for every monster under the harness's zero-stat default,
    which would make this test vacuously None at every HP). Confirmed below
    that the full-HP target is not None before comparing it against the
    damaged-HP target — a None-vs-None comparison would be the same vacuity
    in a new costume.

    Damage to `max_hp // 3`, the same fraction the sibling test in
    `test_tier_progress.py` uses to prove `tier_cleared`'s rest-projection:
    material enough that `predict_win`'s CURRENT-hp-driven rounds-to-die
    calculation flips outcomes for this scenario's band candidates (verified
    separately: without rest-projection the target changes at this damage
    level — see the mutation proof in the task report)."""
    gd = bundle_game_data
    full_hp = scenario_state(SCENARIOS["l11_band_floor"], gd)
    assert full_hp.hp == full_hp.max_hp

    full_target = band_combat_target(full_hp, gd, None)
    assert full_target is not None, (
        "l11_band_floor must have a winnable band target at full HP for "
        "this test to say anything about HP-independence")

    damaged = dataclasses.replace(full_hp, hp=max(1, full_hp.max_hp // 3))
    assert damaged.hp != damaged.max_hp

    damaged_target = band_combat_target(damaged, gd, None)
    assert damaged_target == full_target, (
        f"band_combat_target depends on current hp: {full_target!r} at "
        f"full hp vs {damaged_target!r} damaged")


def test_semantic_tiebreak_uses_level_not_alphabetical(monkeypatch):
    """Secondary tiebreak uses monster_level not code. With genuine XP tie,
    alphabetical (max on code) picks zzz_low; level-semantic picks aaa_high.
    Mutation test kills this: reverting monster_levels[code] to code.

    Fixture details: both normal type, both in penalty band >= 5:
    zzz_low level 10, hp=625: (2000*10 + 4*625*20)*7*10*1000/(20*10M) = 25
    aaa_high level 15, hp=500: (2000*15 + 4*500*20)*7*10*1000/(20*10M) = 25
    max(..., code) wins zzz_low (alphabetically last string).
    max(..., monster_levels) wins aaa_high (higher level)."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        return True
    monkeypatch.setattr(mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tp, "is_winnable", fake_is_winnable)
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon"),
        "iron_sword": ItemStats(code="iron_sword", level=15, type_="weapon"),
    }
    gd._monster_level = {"zzz_low": 10, "aaa_high": 15}
    gd._monster_type = {"zzz_low": "normal", "aaa_high": "normal"}
    gd._monster_hp = {"zzz_low": 625, "aaa_high": 500}
    state = make_state(level=20)

    # Verify XP is truly tied
    xp_low = gd.xp_per_kill("zzz_low", state.level)
    xp_high = gd.xp_per_kill("aaa_high", state.level)
    assert xp_low == xp_high, f"XP must be tied: zzz_low={xp_low}, aaa_high={xp_high}"

    def fake_next_uncleared(s: object, g: object, h: object) -> int:
        return 15
    def fake_normal_band(g: object, t: object) -> tuple[str, ...]:
        return ("zzz_low", "aaa_high")
    monkeypatch.setattr(mod, "next_uncleared_tier", fake_next_uncleared)
    monkeypatch.setattr(mod, "normal_band", fake_normal_band)
    result = band_combat_target(state, gd, None)
    # XP is tied. max(..., code) picks zzz_low (alphabetically last).
    # max(..., monster_levels[code]) picks aaa_high (higher level).
    # Semantic tiebreak picks the higher level.
    assert result == "aaa_high"


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
