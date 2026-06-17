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


def _gd(hp, attack=None, resist=None, crit=0, initiative=0, code="mob", lifesteal=0,
        poison=0, barrier=0, burn=0, healing=0, reconstitution=0, void_drain=0,
        berserker_rage=0, frenzy=0, protective_bubble=0, corrupted=0):
    gd = GameData()
    gd._monster_hp = {code: hp}
    gd._monster_attack = {code: attack or {}}
    gd._monster_resistance = {code: resist or {}}
    gd._monster_critical_strike = {code: crit}
    gd._monster_initiative = {code: initiative}
    gd._monster_lifesteal = {code: lifesteal}
    gd._monster_poison = {code: poison}
    gd._monster_barrier = {code: barrier}
    gd._monster_burn = {code: burn}
    gd._monster_healing = {code: healing}
    gd._monster_reconstitution = {code: reconstitution}
    gd._monster_void_drain = {code: void_drain}
    gd._monster_berserker_rage = {code: berserker_rage}
    gd._monster_frenzy = {code: frenzy}
    gd._monster_protective_bubble = {code: protective_bubble}
    gd._monster_corrupted = {code: corrupted}
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


def test_predict_win_false_when_poison_outpaces_the_kill():
    """dieStep poison term: a fight the player would WIN on the initiative
    tiebreak (equal rounds) becomes a LOSS once the monster's per-turn poison
    shortens rounds_to_die. WITHOUT the poison term the bot predicts a win — the
    mutation gate checks the term flips it. Player raw 50 vs hp 100 ⇒ 2 rounds to
    kill; symmetric monster ⇒ 2 rounds to die (win, player first); poison 100/turn
    ⇒ 1 round to die ⇒ loss."""
    state = make_state(max_hp=100, attack={"fire": 50}, initiative=10)
    gd_no = _gd(hp=100, attack={"fire": 50}, initiative=10)
    assert predict_win(state, gd_no, "mob") is True
    gd_psn = _gd(hp=100, attack={"fire": 50}, initiative=10, poison=100)
    assert predict_win(state, gd_psn, "mob") is False


def test_predict_win_false_when_poison_kills_a_harmless_monster():
    """Removing the `raw_monster <= 0 => True` shortcut: a monster dealing ZERO
    direct damage is harmless (win) UNLESS it has poison, which kills over time.
    Pins that poison-only death is a loss (the old shortcut wrongly said win)."""
    state = make_state(max_hp=100, attack={"fire": 50}, initiative=10)
    gd_safe = _gd(hp=100, attack={}, initiative=10)        # no direct damage ⇒ win
    assert predict_win(state, gd_safe, "mob") is True
    gd_psn = _gd(hp=100, attack={}, initiative=10, poison=100)  # poison alone kills
    assert predict_win(state, gd_psn, "mob") is False


def test_predict_win_false_when_barrier_pushes_kill_past_death():
    """Barrier effective-HP term: a fight the player would WIN on the initiative
    tiebreak (rtk == rtd == 2) becomes a LOSS once the monster's absorbing barrier
    raises effective HP and stretches rounds_to_kill. WITHOUT the barrier term the
    bot predicts a win — the mutation gate checks the term flips it. Player raw 50
    vs hp 100 ⇒ 2 rounds; barrier 100 ⇒ effective hp 200 ⇒ 8 rounds > 2 ⇒ loss."""
    state = make_state(max_hp=100, attack={"fire": 50}, initiative=10)
    gd_no = _gd(hp=100, attack={"fire": 50}, initiative=10)
    assert predict_win(state, gd_no, "mob") is True
    gd_bar = _gd(hp=100, attack={"fire": 50}, initiative=10, barrier=100)
    assert predict_win(state, gd_bar, "mob") is False


def test_predict_win_false_when_burn_outpaces_the_kill():
    """Burn dieStep term: a fight the player would WIN on the initiative tiebreak
    (rtk == rtd == 2) becomes a LOSS once the monster's percent-of-attack burn DoT
    shortens rounds_to_die. WITHOUT the burn term the bot predicts a win — the
    mutation gate checks the term flips it. Player Σatk 50, burn 100% ⇒ +5e5/round
    ⇒ dieStep 1e6 ⇒ rtd 1 < rtk 2 ⇒ loss."""
    state = make_state(max_hp=100, attack={"fire": 50}, initiative=10)
    gd_no = _gd(hp=100, attack={"fire": 50}, initiative=10)
    assert predict_win(state, gd_no, "mob") is True
    gd_brn = _gd(hp=100, attack={"fire": 50}, initiative=10, burn=100)
    assert predict_win(state, gd_brn, "mob") is False


def test_predict_win_false_when_healing_outpaces_our_damage():
    """Healing killStep regen-subtract: a fight the player would WIN on the
    initiative tiebreak (rtk == rtd == 2) becomes a LOSS once the monster's regen
    shrinks killStep and stretches rounds_to_kill. WITHOUT the healing term the bot
    predicts a win — the mutation gate checks the term flips it. Monster hp 100,
    healing 40% ⇒ killStep 5e5 - 4e5 = 1e5 ⇒ rtk 10 > rtd 2 ⇒ loss."""
    state = make_state(max_hp=100, attack={"fire": 50}, initiative=10)
    gd_no = _gd(hp=100, attack={"fire": 50}, initiative=10)
    assert predict_win(state, gd_no, "mob") is True
    gd_heal = _gd(hp=100, attack={"fire": 50}, initiative=10, healing=40)
    assert predict_win(state, gd_heal, "mob") is False


def test_predict_win_false_when_healing_makes_monster_unkillable():
    """A monster whose regen meets/exceeds our per-round damage has killStep <= 0 ⇒
    unkillable ⇒ not winnable (the kill_step<=0 guard). Pins the guard interaction:
    hp 100, healing 50% ⇒ killStep 5e5 - 5e5 = 0 ⇒ unkillable."""
    state = make_state(max_hp=1000, attack={"fire": 50}, initiative=50)
    gd = _gd(hp=100, attack={"fire": 5}, initiative=10, healing=50)
    assert predict_win(state, gd, "mob") is False


def test_predict_win_false_when_reconstitution_outlasts_our_kill():
    """Reconstitution turn-cap: a comfortably winnable fight (rounds_to_kill 2 <<
    rounds_to_die) becomes a LOSS when the monster full-heals on a period <=
    rounds_to_kill — it reconstitutes before we finish. WITHOUT the guard the bot
    predicts a win; the mutation gate checks the guard flips it. Player raw 50 vs hp
    100 ⇒ rtk 2; weak monster ⇒ rtd large; reconstitution period 2 ⇒ loss."""
    state = make_state(max_hp=1000, attack={"fire": 50}, initiative=50)
    gd_no = _gd(hp=100, attack={"fire": 5}, initiative=10)
    assert predict_win(state, gd_no, "mob") is True
    gd_rec = _gd(hp=100, attack={"fire": 5}, initiative=10, reconstitution=2)
    assert predict_win(state, gd_rec, "mob") is False


def test_predict_win_false_when_void_drain_drains_and_heals():
    """Void drain hits BOTH sides: a fight the player would WIN on the tiebreak
    (rtk == rtd == 2) becomes a LOSS because the drain heals the monster (killStep
    down ⇒ rtk up) AND damages the player (dieStep up ⇒ rtd down). WITHOUT either
    term the bot predicts a win; the mutation gate checks each term flips it. Player
    hp 100, raw 50 vs hp 100; void 20% ⇒ killStep 3e5 (rtk 4), dieStep 7e5 (rtd 2)."""
    state = make_state(max_hp=100, attack={"fire": 50}, initiative=10)
    gd_no = _gd(hp=100, attack={"fire": 50}, initiative=10)
    assert predict_win(state, gd_no, "mob") is True
    gd_void = _gd(hp=100, attack={"fire": 50}, initiative=10, void_drain=20)
    assert predict_win(state, gd_void, "mob") is False


def test_predict_win_void_drain_dieStep_term_alone_decides():
    """Isolate the void-drain dieStep (player-loss) term: a strong player vs a tanky
    weak-hitting monster, where the killStep void-heal barely moves rounds_to_kill but
    the dieStep void-loss collapses rounds_to_die below it. Dropping the dieStep term
    (mutation) leaves rtd large => win, but the real verdict is a loss => kills that
    mutant deterministically. raw 200 vs hp 1000 => rtk 6 (killStep void 2e6->1.8e6);
    weak monster raw 5, player hp 100, void 20% => dieStep 5e4->2.5e5 => rtd 4 < 6."""
    state = make_state(max_hp=100, attack={"fire": 200}, initiative=50)
    gd_no = _gd(hp=1000, attack={"fire": 5}, initiative=0)
    assert predict_win(state, gd_no, "mob") is True
    gd_void = _gd(hp=1000, attack={"fire": 5}, initiative=0, void_drain=20)
    assert predict_win(state, gd_void, "mob") is False


def test_predict_win_false_when_berserker_rage_boosts_monster_damage():
    """Berserker-rage's always-active monster-damage boost raises dieStep, flipping a
    won tiebreak (rtk == rtd == 2) to a loss. frenzy held at 0 so this isolates the
    berserker term (kills its mutation). Player hp 100, raw 50 vs hp 100; berserk 100%
    ⇒ dieStep 5e5 + 100*50*200//2=5e5 = 1e6 ⇒ rtd 1 < rtk 2."""
    state = make_state(max_hp=100, attack={"fire": 50}, initiative=10)
    gd_no = _gd(hp=100, attack={"fire": 50}, initiative=10)
    assert predict_win(state, gd_no, "mob") is True
    gd_b = _gd(hp=100, attack={"fire": 50}, initiative=10, berserker_rage=100)
    assert predict_win(state, gd_b, "mob") is False


def test_predict_win_false_when_frenzy_boosts_monster_damage():
    """Frenzy's always-active monster-damage boost (same shape as berserker) flips the
    same won tiebreak to a loss. berserk held at 0 so this isolates the frenzy term."""
    state = make_state(max_hp=100, attack={"fire": 50}, initiative=10)
    gd_no = _gd(hp=100, attack={"fire": 50}, initiative=10)
    assert predict_win(state, gd_no, "mob") is True
    gd_f = _gd(hp=100, attack={"fire": 50}, initiative=10, frenzy=100)
    assert predict_win(state, gd_f, "mob") is False


def test_predict_win_false_when_protective_bubble_resists_player():
    """Protective-bubble's always-on player-damage reduction shrinks killStep, raising
    rounds_to_kill past rounds_to_die and flipping a won tiebreak to a loss. WITHOUT
    the term the bot predicts a win; the mutation gate checks it flips. Player raw 50
    vs hp 100; bubble 50% ⇒ killStep 5e5 - 50*50*200//2=2.5e5 = 2.5e5 ⇒ rtk 4 > rtd 2."""
    state = make_state(max_hp=100, attack={"fire": 50}, initiative=10)
    gd_no = _gd(hp=100, attack={"fire": 50}, initiative=10)
    assert predict_win(state, gd_no, "mob") is True
    gd_bub = _gd(hp=100, attack={"fire": 50}, initiative=10, protective_bubble=50)
    assert predict_win(state, gd_bub, "mob") is False


def test_predict_win_ignores_corrupted_conservatively():
    """corrupted HELPS the player (the monster's resist drops as it is hit), so
    crediting it would risk predicting false wins. predict_win conservatively models
    the player's pre-corruption (minimum) damage ⇒ corrupted must NOT change the
    verdict. Locks the carve-out: same fight, with/without corrupted, identical
    verdict (a borderline tiebreak win that a damage boost could only over-call)."""
    state = make_state(max_hp=100, attack={"fire": 50}, initiative=10)
    gd_no = _gd(hp=100, attack={"fire": 50}, initiative=10)
    gd_cor = _gd(hp=100, attack={"fire": 50}, initiative=10, corrupted=50)
    assert predict_win(state, gd_no, "mob") == predict_win(state, gd_cor, "mob")


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
