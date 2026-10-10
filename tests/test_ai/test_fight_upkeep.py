"""A combat target's XP per action, upkeep included (USER 2026-10-07).

Live 2026-10-07, Lor's death_knight grind: ~3 small_health_potion per fight
(~9 sunflower gathers), 46% of 5.8h gathering, 40% resting, 11% fighting. The
band target ranked by XP per KILL, where upkeep is invisible."""

from fractions import Fraction

import artifactsmmo_cli.ai.tiers.band_target as band_mod
from artifactsmmo_cli.ai.best_loadout import BestLoadout
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.grind_heal_prep import HEAL_PREP_POLICY
from artifactsmmo_cli.ai.learning.fight_upkeep_core import FightUpkeep, xp_per_action
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.potion_supply import potion_level_ramp
from artifactsmmo_cli.ai.tiers.band_target import band_combat_target
from tests.test_ai.fixtures import make_best_loadout, make_state

POTION = "small_health_potion"


class TestXpPerAction:
    def test_one_action_and_nothing_consumed_is_xp_per_kill(self) -> None:
        assert xp_per_action(60, FightUpkeep(Fraction(1), {}), lambda _c: 99) == 60

    def test_actions_and_priced_consumables_divide_the_kill(self) -> None:
        """death_knight's live shape: 3 actions a kill and 3 potions at 3
        gathers each is 12 actions for one kill's XP."""
        upkeep = FightUpkeep(Fraction(3), {POTION: Fraction(3)})
        assert xp_per_action(120, upkeep, {POTION: 3}.__getitem__) == 10

    def test_a_cheap_monster_beats_a_rich_one_with_upkeep(self) -> None:
        rich = xp_per_action(120, FightUpkeep(Fraction(3), {POTION: Fraction(3)}), lambda _c: 3)
        cheap = xp_per_action(50, FightUpkeep(Fraction(2), {}), lambda _c: 3)
        assert cheap > rich


def _record(store: LearningStore, i: int, goal: str, action: str, outcome: str = "ok",
            consumed: str = "{}") -> None:
    store.record_cycle(Cycle(ts=f"2026-10-07T00:00:{i:02d}+00:00", session_id="s",
                             cycle_index=i, character="hero", outcome=outcome,
                             selected_goal=goal, action_repr=action,
                             consumables_expended_json=consumed))


class TestStoreFightUpkeep:
    def test_none_below_warmup(self, tmp_path) -> None:
        store = LearningStore(db_path=str(tmp_path / "u.db"), character="hero")
        store.start_session()
        for i in range(4):
            _record(store, i, "GrindCharacterXP(ogre)", "Fight(ogre)")
        assert store.fight_upkeep("ogre") is None
        store.close()

    def test_counts_every_grind_cycle_and_every_fight_consumable(self, tmp_path) -> None:
        """5 kills, 1 loss, 5 attributed rests, a move: 12 cycles / 5 kills.
        The loss's potion counts — it was spent."""
        store = LearningStore(db_path=str(tmp_path / "u.db"), character="hero")
        store.start_session()
        grind = "GrindCharacterXP(ogre)"
        i = 0
        _record(store, i, grind, "Move(1,0)")
        for _ in range(5):
            i += 1
            _record(store, i, grind, "Fight(ogre)", consumed=f'{{"{POTION}": 2}}')
            i += 1
            _record(store, i, "RestoreHP", "Rest")
        i += 1
        _record(store, i, grind, "Fight(ogre)", outcome="error:fight_lost",
                consumed=f'{{"{POTION}": 1}}')
        upkeep = store.fight_upkeep("ogre")
        assert upkeep == FightUpkeep(Fraction(12, 5), {POTION: Fraction(11, 5)})
        store.close()


class _Measured:
    """A store whose only measurement is `fight_upkeep`."""

    def __init__(self, upkeep: dict[str, FightUpkeep]) -> None:
        self._upkeep = upkeep

    def fight_upkeep(self, code: str) -> FightUpkeep | None:
        return self._upkeep.get(code)


def _band(monkeypatch) -> GameData:
    gd = GameData()
    gd._monster_level = {"death_knight": 30, "imp": 29}
    gd._monster_locations = {"death_knight": [(0, 0)], "imp": [(1, 0)]}
    monkeypatch.setattr(band_mod, "next_uncleared_tier", lambda s, g, h: 30)
    monkeypatch.setattr(band_mod, "normal_band", lambda g, t: ["death_knight", "imp"])
    monkeypatch.setattr(band_mod, "is_winnable", lambda s, g, c, h: True)
    monkeypatch.setattr(GameData, "xp_per_kill",
                        lambda self, code, level, wisdom=0: {"death_knight": 120, "imp": 50}[code])
    return gd


def _same_loop(code: str) -> BestLoadout:
    """The model gives every monster the same 30 s loop."""
    return make_best_loadout()


def _unread(code: str) -> BestLoadout:
    raise AssertionError(f"modelled {code}, which has a measured upkeep")


def _target(gd: GameData, history: _Measured, loadout_of=_same_loop) -> str | None:
    target = band_combat_target(make_state(level=30), gd, history, lambda _c: 3, loadout_of)
    return None if target is None else target.monster


def test_without_upkeep_the_richer_kill_wins(monkeypatch) -> None:
    gd = _band(monkeypatch)
    assert _target(gd, _Measured({})) == "death_knight"


def test_upkeep_turns_the_rank(monkeypatch) -> None:
    """Lor's shape: death_knight pays 120 a kill for 3 actions and 3 potions at
    3 actions each (10/action); imp pays 50 for 2 actions and nothing (25)."""
    gd = _band(monkeypatch)
    history = _Measured({"death_knight": FightUpkeep(Fraction(3), {POTION: Fraction(3)}),
                         "imp": FightUpkeep(Fraction(2), {})})
    assert _target(gd, history, _unread) == "imp"


def test_a_measurement_is_counted_in_fight_seconds(monkeypatch) -> None:
    """One key for both: a measured action is one fight-equivalent, 30 s.
    death_knight measured 10 XP an action is 1/3 XP a second; imp modelled at
    50 XP over a 30 s fight and 120 s of recovery is also 1/3 — a tie the
    higher level takes. With 119 s of recovery imp pays more and is taken."""
    gd = _band(monkeypatch)
    history = _Measured({"death_knight": FightUpkeep(Fraction(3), {POTION: Fraction(3)})})
    imp_at = {120: make_best_loadout(xp=50, win=True, recovery=120),
              119: make_best_loadout(xp=50, win=True, recovery=119)}
    assert _target(gd, history, lambda code: imp_at[120]) == "death_knight"
    assert _target(gd, history, lambda code: imp_at[119]) == "imp"


def test_the_player_prices_a_replacement_unit(monkeypatch) -> None:
    """A fight burns the stock, so the price is making the NEXT one: every held
    copy is removed first (live, Lor's held potions priced at 0), and the unit
    is a batch's price over its size, the level ramp's batch."""
    player = GamePlayer(character="hero", history=None)
    player.state = make_state(level=30, inventory={POTION: 9, "sunflower": 3},
                              bank_items={POTION: 4, "apple": 1},
                              equipment={"utility1_slot": POTION, "weapon_slot": "iron_sword"})
    player.game_data = GameData()
    seen = {}

    def fake_actions(code, qty, state, game_data, ctx, equip, store, gated_drop, policy):
        seen.update(code=code, qty=qty, state=state, bank=ctx.bank_accessible, equip=equip,
                    gated_drop=gated_drop, policy=policy)
        return 130

    monkeypatch.setattr("artifactsmmo_cli.ai.player.acquisition_actions", fake_actions)
    batch = potion_level_ramp(30)
    assert player._consumable_price(POTION) == Fraction(130, batch)
    assert seen["code"] == POTION and seen["qty"] == batch and seen["bank"] is True
    assert seen["equip"] is False and seen["gated_drop"] is False
    assert seen["policy"] is HEAL_PREP_POLICY
    assert seen["state"].inventory == {"sunflower": 3}
    assert seen["state"].bank_items == {"apple": 1}
    assert seen["state"].equipment == {"utility1_slot": None, "weapon_slot": "iron_sword"}


def test_an_unvisited_bank_stays_unknown(monkeypatch) -> None:
    player = GamePlayer(character="hero", history=None)
    player.state = make_state(level=30, bank_items=None)
    player.game_data = GameData()
    seen = {}

    def fake_actions(code, qty, state, *rest, **kw):
        seen["bank_items"] = state.bank_items
        return 1

    monkeypatch.setattr("artifactsmmo_cli.ai.player.acquisition_actions", fake_actions)
    player._consumable_price(POTION)
    assert seen["bank_items"] is None
