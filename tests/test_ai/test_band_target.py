"""The combat target is the next uncleared tier's band, not an unbounded argmax.

`cheapest_path_to_level` filters `1 <= lvl <= sim_level + 1` — a floor of 1 —
and outranks the windowed picker, so four of five live characters were grinding
4 to 10 levels below themselves on 2026-08-23.
"""
import dataclasses
from fractions import Fraction

import artifactsmmo_cli.ai.tiers.band_target as mod
import artifactsmmo_cli.ai.tiers.tier_progress as tp
from artifactsmmo_cli.ai.actions.combat import FIGHT_LEVEL_GAP_CEILING
from artifactsmmo_cli.ai.best_loadout import BestLoadout
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.party_loop import PartyLoop
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.tiers.band_target import band_combat_target, party_candidates, rank_rate
from artifactsmmo_cli.ai.tiers.tier_ladder import band as raw_band
from artifactsmmo_cli.ai.tiers.tier_ladder import normal_band as real_normal_band
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_best_loadout, make_state


def _no_party(_code: str) -> None:
    return None


def _never_priced(code: str) -> int:
    """No store, so no measured upkeep and no consumable to price."""
    raise AssertionError(f"priced {code} with no upkeep measured")


def _bare_loop(code: str) -> BestLoadout:
    """Every loadout's walk loses: the band is ranked on bare gear alone, one
    30 s loop a kill, so the rank is the kill's XP."""
    return make_best_loadout()


def _pick(state: WorldState, gd: GameData) -> str | None:
    target = band_combat_target(state, gd, None, _never_priced, _bare_loop, _no_party)
    return None if target is None else target.monster


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon"),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon"),
        "battlestaff": ItemStats(code="battlestaff", level=20, type_="weapon"),
    }
    gd._monster_level = {"chicken": 1, "mushmush": 10, "king_slime": 15,
                         "spider": 20, "ogre": 20}
    gd._monster_locations = {c: [(i, 0)] for i, c in enumerate(gd._monster_level)}
    gd._monster_type = {"chicken": "normal", "mushmush": "normal",
                        "king_slime": "boss", "spider": "normal",
                        "ogre": "normal"}
    gd._monster_hp = {"chicken": 60, "mushmush": 350, "king_slime": 1000,
                      "spider": 550, "ogre": 650}
    gd._monster_locations = {code: [(i, 0)] for i, code in enumerate(gd._monster_level)}
    return gd


def test_the_target_comes_from_the_next_uncleared_band(monkeypatch):
    """Only ogre is unwinnable, so T20 is uncleared and the target is drawn
    from band(T20) — not from the whole catalogue."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        return c != "ogre"
    monkeypatch.setattr(mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tp, "is_winnable", fake_is_winnable)
    assert _pick(make_state(level=30), _gd()) == "spider"


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
    gd._monster_locations = {c: [(i, 0)] for i, c in enumerate(gd._monster_level)}
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

    target = _pick(state, gd)
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
    assert _pick(make_state(level=30), _gd()) is None


def test_a_band_that_pays_no_xp_yields_none(monkeypatch):
    """`FightAction` refuses a monster that pays no XP (its `xp_per_kill > 0`
    floor), so a winnable band of greys is no target. Live 2026-10-03: Lor at
    L31 against T20 would get spider (L20, 0 XP) and `GrindCharacterXP`
    failed at one node on 561 of 561 searches. At L30 spider still pays, so
    the floor is the only thing that changes the answer."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        return c != "ogre"
    monkeypatch.setattr(mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tp, "is_winnable", fake_is_winnable)
    gd = _gd()
    assert gd.xp_per_kill("spider", 30) > 0
    assert gd.xp_per_kill("spider", 31) == 0
    assert _pick(make_state(level=30), gd) == "spider"
    assert _pick(make_state(level=31), gd) is None


def test_a_monster_with_no_spawn_is_no_target(monkeypatch):
    """`FightAction` is built only for a monster with spawn tiles (the action
    factory's `all_monster_locations`), so an event monster that is not up
    is a target nothing can fight. Live 2026-10-04: Robby's band named
    `full_moon_vampire` (L24, 32 XP, winnable, no tiles) and `GrindCharacterXP`
    failed 23 of 23 searches. Spider is the band's only other winnable monster."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        return c != "ogre"
    monkeypatch.setattr(mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tp, "is_winnable", fake_is_winnable)
    gd = _gd()
    assert _pick(make_state(level=30), gd) == "spider"
    gd._monster_locations = {k: v for k, v in gd._monster_locations.items() if k != "spider"}
    assert _pick(make_state(level=30), gd) is None


def test_a_finished_ladder_yields_none(monkeypatch):
    """Every rung cleared: there is no next uncleared tier to draw from."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        return True
    monkeypatch.setattr(mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tp, "is_winnable", fake_is_winnable)
    assert _pick(make_state(level=30), _gd()) is None


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

    full_target = _pick(full_hp, gd)
    assert full_target is not None, (
        "l11_band_floor must have a winnable band target at full HP for "
        "this test to say anything about HP-independence")

    damaged = dataclasses.replace(full_hp, hp=max(1, full_hp.max_hp // 3))
    assert damaged.hp != damaged.max_hp

    damaged_target = _pick(damaged, gd)
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
    gd._monster_locations = {c: [(i, 0)] for i, c in enumerate(gd._monster_level)}
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
    result = _pick(state, gd)
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
    gd._monster_locations = {c: [(i, 0)] for i, c in enumerate(gd._monster_level)}
    gd._monster_type = {"spider": "normal", "ogre": "normal", "dummy_unwinnable": "normal"}
    gd._monster_hp = {"spider": 550, "ogre": 650, "dummy_unwinnable": 1000}
    state = make_state(level=30)
    # Among the winnable monsters (spider and ogre), pick the one with higher XP
    best = max(("spider", "ogre"), key=lambda c: gd.xp_per_kill(c, state.level))
    result = _pick(state, gd)
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
    gd._monster_locations = {c: [(i, 0)] for i, c in enumerate(gd._monster_level)}
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
    result = _pick(state, gd)
    assert result == "mushmush"


def test_stat_winnable_but_out_of_window_yields_none(monkeypatch):
    """GAP-8 / task 5.2 fix round 1: `is_winnable` is a pure stat question and
    knows nothing about `FightAction`'s own `state.level +
    FIGHT_LEVEL_GAP_CEILING` structural ceiling. Live 2026-08-23:
    `l10_bag_pursuit` (char level 10) had tier 10 (flying_snake, mushmush)
    read CLEARED, so `next_uncleared_tier` advanced to tier 15, whose band
    is (highwayman L15, pig L19, skeleton L18, wolf L15) — `highwayman` was
    stat-winnable with that loadout, so the OLD `band_combat_target`
    offered it, but 15 > 10+2 so `FightAction` refused it outright and
    `GrindCharacterXP(highwayman)` planned to zero nodes.

    Fixture: `highwayman` (L15) is the band's ONLY stat-winnable member —
    `pig` (L19, also outside the window) stays unwinnable so tier 15 itself
    stays uncleared (the point under test is the CANDIDATE filter, not tier
    clearance). At char level 10 both band members sit above
    `10 + FIGHT_LEVEL_GAP_CEILING`, so the fixed `band_combat_target` must
    filter both out and return None — a gear wall, not an unfightable
    target."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        return c != "pig"
    monkeypatch.setattr(mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tp, "is_winnable", fake_is_winnable)
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon"),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon"),
        "steel_sword": ItemStats(code="steel_sword", level=15, type_="weapon"),
    }
    gd._monster_level = {"chicken": 1, "mushmush": 10, "highwayman": 15, "pig": 19}
    gd._monster_locations = {c: [(i, 0)] for i, c in enumerate(gd._monster_level)}
    gd._monster_type = {"chicken": "normal", "mushmush": "normal",
                        "highwayman": "normal", "pig": "normal"}
    gd._monster_hp = {"chicken": 60, "mushmush": 350, "highwayman": 500, "pig": 600}
    state = make_state(level=10)

    # Sanity: highwayman is genuinely outside the executor's window here —
    # this test says nothing if the fixture accidentally sits inside it.
    assert gd.monster_levels["highwayman"] > state.level + FIGHT_LEVEL_GAP_CEILING

    assert _pick(state, gd) is None


# ---------------------------------------------------------------------------
# The loadout picks the monster (USER 2026-10-10)
# ---------------------------------------------------------------------------

class _Record:
    """A store with no measured upkeep."""

    def fight_upkeep(self, code: str) -> None:
        return None


def _spider_bare_ogre_on_potions(monkeypatch) -> GameData:
    """T20 uncleared; spider winnable bare, ogre only on its best loadout."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        return c != "ogre"
    monkeypatch.setattr(mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tp, "is_winnable", fake_is_winnable)
    return _gd()


def _loops(spider_recovery: int, ogre_win: bool, ogre_consumed: int):
    gd = _gd()
    spider = make_best_loadout(xp=gd.xp_per_kill("spider", 30), win=True, recovery=spider_recovery)
    ogre = make_best_loadout(("small_health_potion",), xp=gd.xp_per_kill("ogre", 30), win=ogre_win,
                             consumed=ogre_consumed)
    return {"spider": spider, "ogre": ogre}.__getitem__


def test_a_potion_propped_monster_that_pays_more_is_the_target(monkeypatch):
    """ogre loses bare and wins on a potion; at 30 s a loop it pays more per
    second than spider's 30 s fight and 60 s rest, so the loadout picks it."""
    gd = _spider_bare_ogre_on_potions(monkeypatch)
    target = band_combat_target(make_state(level=30), gd, None, _never_priced,
                                _loops(spider_recovery=60, ogre_win=True, ogre_consumed=0), _no_party)
    assert target is not None and target.monster == "ogre"
    assert target.bare_fight is True
    assert target.rate == Fraction(gd.xp_per_kill("ogre", 30), 30)


def test_a_potion_that_pays_less_does_not_pick_the_monster(monkeypatch):
    """"We don't pick sub-standard loadouts just because they're available":
    the potion's price makes ogre's loop slower than spider's bare one."""
    gd = _spider_bare_ogre_on_potions(monkeypatch)
    target = band_combat_target(make_state(level=30), gd, None, _never_priced,
                                _loops(spider_recovery=0, ogre_win=True, ogre_consumed=600), _no_party)
    assert target is not None and target.monster == "spider"


def test_a_monster_no_loadout_beats_is_no_candidate(monkeypatch):
    gd = _spider_bare_ogre_on_potions(monkeypatch)
    target = band_combat_target(make_state(level=30), gd, None, _never_priced,
                                _loops(spider_recovery=600, ogre_win=False, ogre_consumed=0), _no_party)
    assert target is not None and target.monster == "spider"


def test_a_band_fought_only_on_potions_has_no_bare_fight(monkeypatch):
    """Nothing in the band is winnable bare: the band still names ogre, and
    says bare gear has no fight in it — what every gear decision reads."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        return c not in ("spider", "ogre")
    monkeypatch.setattr(mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tp, "is_winnable", fake_is_winnable)
    target = band_combat_target(make_state(level=30), _gd(), None, _never_priced,
                                _loops(spider_recovery=0, ogre_win=True, ogre_consumed=0), _no_party)
    assert target is not None and target.monster == "ogre" and target.bare_fight is False


def test_the_learned_loss_veto_refuses_a_potion_propped_fight(monkeypatch):
    """A monster lost to on the record is no target whatever a potion would do
    in the model; the same fight unvetoed is taken."""
    gd = _spider_bare_ogre_on_potions(monkeypatch)
    loops = _loops(spider_recovery=60, ogre_win=True, ogre_consumed=0)
    monkeypatch.setattr(mod, "loss_vetoed", lambda s, g, c, h: c == "ogre")
    vetoed = band_combat_target(make_state(level=30), gd, _Record(), _never_priced, loops, _no_party)
    assert vetoed is not None and vetoed.monster == "spider"
    monkeypatch.setattr(mod, "loss_vetoed", lambda s, g, c, h: False)
    taken = band_combat_target(make_state(level=30), gd, _Record(), _never_priced, loops, _no_party)
    assert taken is not None and taken.monster == "ogre"


def test_a_win_on_the_record_is_ranked_at_the_models_rate(monkeypatch):
    """`is_winnable` says spider is beaten (the record) while the model's odds
    are nil: the record decides the win filter, the model's rate the rank."""
    gd = _spider_bare_ogre_on_potions(monkeypatch)
    xp = gd.xp_per_kill("spider", 30)
    lost_walk = make_best_loadout(xp=xp, win=False, recovery=90)
    assert rank_rate(xp, None, lambda: lost_walk, _never_priced) == 0


def test_a_sure_win_ranks_at_the_old_loop_rate():
    sure = make_best_loadout(xp=60, win=True, recovery=30)
    assert rank_rate(60, None, lambda: sure, _never_priced) == Fraction(60, 60)


def test_a_risky_monster_ranks_below_a_sure_one_that_pays_less_per_kill(monkeypatch):
    """ogre's full-XP loop is faster (30 s, 3x spider's XP) but it wins one fight
    in three: its expected rate falls below spider's sure one."""
    gd = _spider_bare_ogre_on_potions(monkeypatch)
    spider_xp, ogre_xp = gd.xp_per_kill("spider", 30), gd.xp_per_kill("ogre", 30)
    spider = make_best_loadout(xp=spider_xp, win=True, recovery=0)
    ogre = make_best_loadout(("small_health_potion",), xp=ogre_xp, win=True,
                             p_win=Fraction(1, 100))
    assert Fraction(ogre_xp, 30) > Fraction(spider_xp, 30)
    target = band_combat_target(make_state(level=30), gd, None, _never_priced,
                                {"spider": spider, "ogre": ogre}.__getitem__, _no_party)
    assert target is not None and target.monster == "spider"


def _party_of(xp: int):  # type: ignore[no-untyped-def]
    """A party of one joiner beats king_slime in one 30 s loop paying `xp`."""
    def party_of(code: str) -> PartyLoop | None:
        assert code == "king_slime"
        return PartyLoop((), (0,), make_best_loadout(xp=xp, win=True).rate)
    return party_of


def test_a_party_boss_that_pays_more_is_the_target(monkeypatch):
    """USER 2026-10-10: "use groups for boss xp, too" — king_slime as a party
    pays more per second than the band's spider, so the band names it and
    the joiner it needs."""
    gd = _spider_bare_ogre_on_potions(monkeypatch)
    state = make_state(level=30)
    state = dataclasses.replace(state, party=(state,))
    loops = _loops(spider_recovery=0, ogre_win=False, ogre_consumed=0)
    spider = Fraction(gd.xp_per_kill("spider", 30), 30)
    rich = band_combat_target(state, gd, None, _never_priced, loops,
                              _party_of(gd.xp_per_kill("spider", 30) * 2))
    assert rich is not None and (rich.monster, rich.joiners, rich.rate) == ("king_slime", (0,), spider * 2)
    poor = band_combat_target(state, gd, None, _never_priced, loops, _party_of(1))
    assert poor is not None and (poor.monster, poor.joiners) == ("spider", ())


def test_party_candidates_are_spawning_bosses_under_the_ceiling() -> None:
    gd = _gd()
    alone = make_state(level=13)
    assert party_candidates(alone, gd) == []
    party = dataclasses.replace(alone, party=(alone,))
    assert party_candidates(party, gd) == ["king_slime"]
    low = dataclasses.replace(party, level=15 - FIGHT_LEVEL_GAP_CEILING - 1)
    assert party_candidates(low, gd) == []
    gd._monster_locations = {**gd._monster_locations, "king_slime": []}
    assert party_candidates(party, gd) == []


def test_a_cleared_ladder_still_farms_a_party_boss(monkeypatch):
    monkeypatch.setattr(mod, "next_uncleared_tier", lambda s, g, h: None)
    gd = _gd()
    state = make_state(level=30)
    party = dataclasses.replace(state, party=(state,))
    target = band_combat_target(party, gd, None, _never_priced, _bare_loop, _party_of(500))
    assert target is not None and target.monster == "king_slime"
    assert band_combat_target(party, gd, None, _never_priced, _bare_loop, _no_party) is None


def test_bare_fight_is_asked_without_a_worn_potion(monkeypatch):
    """`bare_fight` judges bare gear: a band won only by drinking the worn
    restore potions (here: any state with stock) has no bare fight, so the
    gear decisions that read it still see the gap."""
    def wins_on_worn_stock(s: WorldState, g: object, c: str, h: object) -> bool:
        return s.utility1_slot_quantity > 0
    monkeypatch.setattr(mod, "is_winnable", wins_on_worn_stock)
    monkeypatch.setattr(tp, "is_winnable", lambda s, g, c, h: c not in ("spider", "ogre"))
    state = dataclasses.replace(make_state(level=30), utility1_slot_quantity=40)
    target = band_combat_target(state, _gd(), None, _never_priced,
                                _loops(spider_recovery=0, ogre_win=True, ogre_consumed=0), _no_party)
    assert target is not None and target.bare_fight is False


def test_a_potion_loadout_short_of_the_threshold_is_no_candidate(monkeypatch):
    """The potion arm reads the loadout's odds against θ, like every other
    gate: a loop the closed form calls a win at P 1/2 is short of the default
    4/5, so ogre is no candidate and spider is the target."""
    gd = _spider_bare_ogre_on_potions(monkeypatch)
    spider = make_best_loadout(xp=gd.xp_per_kill("spider", 30), win=True, recovery=600)
    ogre = make_best_loadout(("small_health_potion",), xp=gd.xp_per_kill("ogre", 30), win=True,
                             p_win=Fraction(1, 2))
    target = band_combat_target(make_state(level=30), gd, None, _never_priced,
                                {"spider": spider, "ogre": ogre}.__getitem__, _no_party)
    assert target is not None and target.monster == "spider"


def test_a_potion_loadout_at_a_lower_measured_threshold_is_a_candidate(monkeypatch):
    """θ is this character's measured threshold for the monster: at θ 2/5 the
    same P 1/2 loadout makes ogre a candidate, and it pays more per second."""
    gd = _spider_bare_ogre_on_potions(monkeypatch)
    spider = make_best_loadout(xp=gd.xp_per_kill("spider", 30), win=True, recovery=600)
    ogre = make_best_loadout(("small_health_potion",), xp=gd.xp_per_kill("ogre", 30), win=True,
                             p_win=Fraction(1, 2))
    state = dataclasses.replace(make_state(level=30), win_thresholds={"ogre": Fraction(2, 5)})
    target = band_combat_target(state, gd, None, _never_priced,
                                {"spider": spider, "ogre": ogre}.__getitem__, _no_party)
    assert target is not None and target.monster == "ogre"


def test_a_loop_no_loadout_can_run_ranks_at_zero():
    """Spec 2026-10-18 §2.10: with no room in the bag for its drops no loadout's
    loop runs (`best_loadout` None), and an unmeasured loop that does not run
    earns nothing."""
    assert rank_rate(60, None, lambda: None, _never_priced) == 0


def test_a_potion_propped_fight_no_loadout_can_run_is_no_target(monkeypatch):
    """The ogre is won only on a potion; with no loop that runs against it, its
    odds clear nothing, so the bare-winnable spider is the target."""
    gd = _spider_bare_ogre_on_potions(monkeypatch)
    loops = _loops(spider_recovery=60, ogre_win=True, ogre_consumed=0)

    def no_ogre_loop(code: str):
        return None if code == "ogre" else loops(code)
    target = band_combat_target(make_state(level=30), gd, None, _never_priced, no_ogre_loop,
                                _no_party)
    assert target is not None and target.monster == "spider"
    ran = band_combat_target(make_state(level=30), gd, None, _never_priced, loops, _no_party)
    assert ran is not None and ran.monster == "ogre"
