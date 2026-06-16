"""Tests for the documented combat-outcome estimator."""

import pytest

from artifactsmmo_cli.ai.combat import (
    MIN_WIN_SAMPLES,
    _element_damage,
    _expected_hit,
    _round_half_up,
    is_winnable,
    predict_win,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from tests.test_ai.fixtures import make_state


def _record_losses(store: LearningStore, action_repr: str, n: int) -> None:
    """Record n lost fights for action_repr so success_rate falls to 0."""
    store.start_session()
    for i in range(n):
        store.record_cycle(Cycle(
            ts=f"2026-05-25T00:00:{i:02d}+00:00", session_id="x", cycle_index=i,
            character="x", outcome="error:fight_lost", action_repr=action_repr,
        ))


def _record_mixed(store: LearningStore, action_repr: str, wins: int, losses: int) -> None:
    """Record `wins` won + `losses` lost fights so success_rate = wins/(wins+losses)."""
    store.start_session()
    i = 0
    for outcome in ["ok"] * wins + ["error:fight_lost"] * losses:
        store.record_cycle(Cycle(
            ts=f"2026-05-25T00:00:{i:02d}+00:00", session_id="x", cycle_index=i,
            character="x", outcome=outcome, action_repr=action_repr,
        ))
        i += 1


def _gd(hp, attack=None, resist=None, crit=0, initiative=0, code="mob", lifesteal=0):
    gd = GameData()
    gd._monster_hp = {code: hp}
    gd._monster_attack = {code: attack or {}}
    gd._monster_resistance = {code: resist or {}}
    gd._monster_critical_strike = {code: crit}
    gd._monster_initiative = {code: initiative}
    gd._monster_lifesteal = {code: lifesteal}
    return gd


def test_predict_win_false_when_monster_out_heals_via_lifesteal():
    """killStep ≤ 0: a high-crit/high-lifesteal monster heals more per turn than
    our weak attack removes → unkillable → not winnable (combat.py:100). The
    monster's own damage is fully RESISTED, so WITHOUT the lifesteal term the bot
    would (wrongly) predict a win — that is what the mutation gate checks."""
    state = make_state(max_hp=200, attack={"fire": 5}, resistance={"fire": 100},
                       initiative=50)
    gd = _gd(hp=30, attack={"fire": 200}, crit=50, lifesteal=10)
    assert predict_win(state, gd, "mob") is False


def test_predict_win_true_when_player_out_sustains_via_lifesteal():
    """dieStep ≤ 0: a high-crit player wearing strong lifesteal gear heals at least
    as much per turn as the monster deals → we out-sustain → win (combat.py:120).
    The monster WOULD win the damage race (low player HP), so WITHOUT the lifesteal
    term the bot predicts a loss — the mutation gate checks the term flips it."""
    gd = _gd(hp=100, attack={"fire": 5}, crit=0)
    gd._item_stats = {
        "vamp": ItemStats(code="vamp", level=1, type_="weapon", lifesteal=100),
    }
    state = make_state(hp=10, max_hp=10, attack={"fire": 10}, critical_strike=50,
                       initiative=50, equipment={"weapon_slot": "vamp"})
    assert predict_win(state, gd, "mob") is True


def test_round_half_up_rounds_half_upward():
    assert _round_half_up(2.5) == 3
    assert _round_half_up(2.4999) == 2
    assert _round_half_up(3.0) == 3


def test_element_damage_applies_bonus_then_resistance():
    # 100 attack + 30% damage = 130 output; 30% resistance blocks Round(130*0.3)=39
    assert _element_damage(100, 30, 30) == 130 - 39


def test_element_damage_clamps_to_zero():
    assert _element_damage(10, 0, 100) == 0


def test_expected_hit_sums_elements_and_applies_crit():
    # fire 10 + water 5 = 15 raw; crit 20% -> *1.10
    raw = _expected_hit({"fire": 10, "water": 5}, 0, {}, {}, 20)
    assert raw == pytest.approx(15 * 1.10)


def test_is_winnable_true_when_predicted_and_no_history():
    state = make_state(max_hp=100, attack={"fire": 30}, initiative=50)
    gd = _gd(hp=30, attack={"fire": 5}, initiative=10)
    assert is_winnable(state, gd, "mob", None) is True


def test_is_winnable_false_when_prediction_loses():
    state = make_state(max_hp=10, attack={"fire": 1}, initiative=0)
    gd = _gd(hp=1000, attack={"fire": 50}, initiative=100)
    assert is_winnable(state, gd, "mob", None) is False


def test_is_winnable_veto_overrides_optimistic_prediction(tmp_path):
    """A well-observed loss record vetoes a stat prediction that says we win."""
    state = make_state(max_hp=100, attack={"fire": 30}, initiative=50)
    gd = _gd(hp=30, attack={"fire": 5}, initiative=10)  # predict_win -> True
    store = LearningStore(db_path=str(tmp_path / "l.db"), character="h")
    _record_losses(store, "Fight(mob)", MIN_WIN_SAMPLES)
    assert is_winnable(state, gd, "mob", store) is False
    store.close()


def test_is_winnable_no_veto_below_sample_threshold(tmp_path):
    """Too few observed fights -> defer to the stat prediction (no veto)."""
    state = make_state(max_hp=100, attack={"fire": 30}, initiative=50)
    gd = _gd(hp=30, attack={"fire": 5}, initiative=10)
    store = LearningStore(db_path=str(tmp_path / "l.db"), character="h")
    _record_losses(store, "Fight(mob)", MIN_WIN_SAMPLES - 1)
    assert is_winnable(state, gd, "mob", store) is True
    store.close()


def test_is_winnable_vetoes_high_but_imperfect_winrate(tmp_path):
    """A monster won only ~80% of observed fights (lost >10%) is vetoed even though
    the stat prediction says win. The cooldown + death cost of marginal fights
    outweighs the XP — the blue_slime trace bug (13% loss from full HP, bot kept
    grinding it). Inert at the old 0.5 threshold; caught now."""
    state = make_state(max_hp=100, attack={"fire": 30}, initiative=50)
    gd = _gd(hp=30, attack={"fire": 5}, initiative=10)  # predict_win -> True
    store = LearningStore(db_path=str(tmp_path / "l.db"), character="h")
    _record_mixed(store, "Fight(mob)", wins=8, losses=2)  # 80% < threshold
    assert is_winnable(state, gd, "mob", store) is False
    store.close()


def test_is_winnable_keeps_reliable_winner(tmp_path):
    """A reliably-won monster (95%) is NOT vetoed — the threshold deselects only
    genuinely costly targets, it does not starve the bot of winnable combat."""
    state = make_state(max_hp=100, attack={"fire": 30}, initiative=50)
    gd = _gd(hp=30, attack={"fire": 5}, initiative=10)
    store = LearningStore(db_path=str(tmp_path / "l.db"), character="h")
    _record_mixed(store, "Fight(mob)", wins=19, losses=1)  # 95% >= threshold
    assert is_winnable(state, gd, "mob", store) is True
    store.close()


def test_predict_win_true_when_player_kills_first():
    state = make_state(max_hp=100, attack={"fire": 30}, initiative=50)
    gd = _gd(hp=30, attack={"fire": 5}, initiative=10)
    assert predict_win(state, gd, "mob") is True


def test_predict_win_false_when_monster_kills_first():
    state = make_state(max_hp=10, attack={"fire": 1}, initiative=0)
    gd = _gd(hp=1000, attack={"fire": 50}, initiative=100)
    assert predict_win(state, gd, "mob") is False


def test_predict_win_false_when_player_cannot_damage():
    state = make_state(max_hp=100, attack={}, initiative=50)
    gd = _gd(hp=30, attack={"fire": 5})
    assert predict_win(state, gd, "mob") is False


def test_predict_win_true_when_monster_cannot_damage():
    state = make_state(max_hp=100, attack={"fire": 10}, initiative=0)
    gd = _gd(hp=30, attack={}, initiative=100)
    assert predict_win(state, gd, "mob") is True


def test_predict_win_false_when_kill_exceeds_turn_cap():
    state = make_state(max_hp=10000, attack={"fire": 1}, initiative=100)
    gd = _gd(hp=10000, attack={"fire": 1})
    assert predict_win(state, gd, "mob") is False


def test_predict_win_resistance_lets_defender_survive_longer():
    state = make_state(max_hp=100, attack={"fire": 20}, initiative=0)
    weak = _gd(hp=40, attack={"fire": 15}, initiative=100)
    armored = _gd(hp=40, attack={"fire": 15}, resist={"fire": 75}, initiative=100, code="mob")
    assert predict_win(state, weak, "mob") is True
    assert predict_win(state, armored, "mob") is False


def test_predict_win_initiative_tie_favors_player():
    state = make_state(max_hp=20, attack={"fire": 20}, initiative=50)
    gd = _gd(hp=20, attack={"fire": 20}, initiative=50)
    assert predict_win(state, gd, "mob") is True


def test_predict_win_player_resistance_reduces_monster_damage():
    # Monster does 20 fire; player has 75% fire resistance -> 5 net/turn,
    # surviving 20 turns at max_hp=100 while killing the mob in 2.
    state = make_state(max_hp=100, attack={"fire": 20}, initiative=0, resistance={"fire": 75})
    gd = _gd(hp=40, attack={"fire": 20}, initiative=100)
    assert predict_win(state, gd, "mob") is True


def test_predict_win_global_dmg_bonus_changes_outcome():
    # Without +100% global dmg the player needs 2 rounds and the faster monster
    # kills first; with it the player one-shots and wins. Proves state.dmg is wired.
    mob = _gd(hp=20, attack={"fire": 8}, initiative=100)
    slow = make_state(max_hp=10, attack={"fire": 10}, initiative=0)
    boosted = make_state(max_hp=10, attack={"fire": 10}, dmg=100, initiative=0)
    assert predict_win(slow, mob, "mob") is False
    assert predict_win(boosted, mob, "mob") is True


def test_predict_win_uses_best_inventory_loadout():
    # Current weapon too weak (1 fire) to kill 200hp in <=100 turns; a strong
    # staff (80 fire) sits in inventory -> predict_win picks it via pick_loadout.
    gd = _gd(hp=200, attack={"fire": 1}, initiative=0)   # monster "mob"
    gd._item_stats = {
        "twig": ItemStats(code="twig", level=1, type_="weapon", attack={"fire": 1}),
        "staff": ItemStats(code="staff", level=1, type_="weapon", attack={"fire": 80}),
    }
    state = make_state(max_hp=100, attack={"fire": 1}, initiative=50, level=1,
                       equipment={"weapon_slot": "twig"}, inventory={"staff": 1})
    assert predict_win(state, gd, "mob") is True


def test_predict_win_identity_when_no_inventory_upgrade():
    # Twig equipped and known; empty inventory -> pick_loadout keeps the twig
    # (no candidate beats it) -> projection == current stats -> verdict unchanged.
    gd = _gd(hp=30, attack={"fire": 2}, initiative=0)   # weak monster
    gd._item_stats = {"twig": ItemStats(code="twig", level=1, type_="weapon", attack={"fire": 5})}
    state = make_state(max_hp=100, attack={"fire": 50}, initiative=50, level=1,
                       equipment={"weapon_slot": "twig"}, inventory={})
    assert predict_win(state, gd, "mob") is True


def test_predict_win_false_when_current_hp_low_despite_max_hp():
    """Regression: trace cycle 63 (run 9, 2026-06-03) had bot at HP=49/125
    (39%) predicted to win a chicken fight, fought, lost. The pre-fix code
    used p.max_hp (125) for rounds_to_die instead of current state.hp (49).
    Bot survived ⌈125/30⌉=5 rounds against chicken_attack=30 in the
    predictor's view, but only ⌈49/30⌉=2 actually.
    """
    # Player has enough attack to win at full HP but not at 49 HP.
    state = make_state(max_hp=100, hp=10, attack={"fire": 10}, initiative=50)
    # Monster: 30 HP (3 rounds to kill at 10 dmg) AND 20 attack (low HP
    # player dies in 1 round).
    gd = _gd(hp=30, attack={"fire": 20}, initiative=0)
    # At max_hp=100, rounds_to_die=5, player wins (3<5).
    # At hp=10 (current), rounds_to_die=1, player loses (3 rounds to kill).
    assert predict_win(state, gd, "mob") is False, (
        "Should refuse fight when current HP can't survive"
    )


def test_predict_win_true_when_current_hp_full():
    """Sanity check: with full HP, predict_win still wins as before."""
    state = make_state(max_hp=100, hp=100, attack={"fire": 10}, initiative=50)
    gd = _gd(hp=30, attack={"fire": 20}, initiative=0)
    assert predict_win(state, gd, "mob") is True


def test_predict_win_false_when_zero_hp():
    """Defensive: predict_win returns False when state.hp = 0."""
    state = make_state(max_hp=100, hp=0, attack={"fire": 10}, initiative=50)
    gd = _gd(hp=30, attack={"fire": 1}, initiative=0)
    assert predict_win(state, gd, "mob") is False
