"""Tests for the documented combat-outcome estimator."""

import pytest

from artifactsmmo_cli.ai.combat import (
    LOSE_MARGIN,
    MIN_WIN_SAMPLES,
    WIN_MARGIN,
    _element_damage,
    _expected_hit,
    _round_half_up,
    combat_margin,
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
        berserker_rage=0, frenzy=0, protective_bubble=0, corrupted=0,
        sun_shield=0, greed=0, enchanted_mirror=0):
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
    gd._monster_sun_shield = {code: sun_shield}
    gd._monster_greed = {code: greed}
    gd._monster_enchanted_mirror = {code: enchanted_mirror}
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


def test_predict_win_false_when_sun_shield_zeroes_kill_step():
    """dieStep sun_shield term (Season 8): a monster that deals no direct damage is
    winnable, but sun_shield 100% halves-then-zeroes the player's per-turn damage so
    killStep ≤ 0 ⇒ unkillable ⇒ loss. WITHOUT the sun_shield term the bot predicts a
    win — the mutation gate checks the term flips it."""
    state = make_state(max_hp=100, attack={"fire": 50}, initiative=10)
    gd_no = _gd(hp=100, attack={}, initiative=10)
    assert predict_win(state, gd_no, "mob") is True
    gd_ss = _gd(hp=100, attack={}, initiative=10, sun_shield=100)
    assert predict_win(state, gd_ss, "mob") is False


def test_predict_win_false_when_greed_outpaces_the_kill():
    """dieStep greed term (Season 8): a fight won on the initiative tiebreak (rtk == rtd
    == 2) becomes a loss once the monster's 9-stack greed boost shortens rounds_to_die.
    Player raw 50 vs hp 100 ⇒ 2 rounds; symmetric monster ⇒ 2 rounds (win, player first);
    greed 20 ⇒ +9*20% monster damage ⇒ 1 round to die ⇒ loss."""
    state = make_state(max_hp=100, attack={"fire": 50}, initiative=10)
    gd_no = _gd(hp=100, attack={"fire": 50}, initiative=10)
    assert predict_win(state, gd_no, "mob") is True
    gd_greed = _gd(hp=100, attack={"fire": 50}, initiative=10, greed=20)
    assert predict_win(state, gd_greed, "mob") is False


def test_predict_win_false_when_enchanted_mirror_reflects_to_death():
    """dieStep enchanted_mirror term (Season 8): a monster that deals no direct damage is
    winnable, but reflecting 50% of the player's own output kills the (low-HP) player in 2
    rounds while the kill takes 4 (monster hp 200) ⇒ loss. WITHOUT the reflect term the bot
    predicts a win — the mutation gate checks the term flips it."""
    state = make_state(hp=50, max_hp=50, attack={"fire": 50}, initiative=10)
    gd_no = _gd(hp=200, attack={}, initiative=10)
    assert predict_win(state, gd_no, "mob") is True
    gd_mirror = _gd(hp=200, attack={}, initiative=10, enchanted_mirror=50)
    assert predict_win(state, gd_mirror, "mob") is False


def test_predict_win_antipoison_cancels_monster_poison():
    """Player antipoison (equipped antidote) CAPS the monster poison DoT at
    max(0, poison - antipoison) (PLAN #3b2, composes with #1 poison). A no-direct-damage
    monster with poison 100 kills via poison (loss); equipping an antipoison-100 antidote
    fully cancels it ⇒ harmless ⇒ win. WITHOUT capping the bot predicts a loss with the
    antidote — the mutation gate checks the cap flips it."""
    # No antidote: poison 100 kills the otherwise-harmless monster.
    state = make_state(max_hp=100, attack={"fire": 50}, initiative=50)
    gd_no = _gd(hp=100, attack={}, initiative=10, poison=100)
    assert predict_win(state, gd_no, "mob") is False
    # Equip an antidote (antipoison 100, valued via combat_buff so pick_loadout keeps it):
    gd_anti = _gd(hp=100, attack={}, initiative=10, poison=100)
    gd_anti._item_stats = {"antidote": ItemStats(code="antidote", level=1, type_="utility",
                                                 antipoison=100, combat_buff=100)}
    state_anti = make_state(max_hp=100, attack={"fire": 50}, initiative=50,
                            equipment={"utility1_slot": "antidote"})
    assert predict_win(state_anti, gd_anti, "mob") is True


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


def _record_wins(store: LearningStore, action_repr: str, n: int) -> None:
    _record_mixed(store, action_repr, wins=n, losses=0)


def test_monotonic_win_flags_lower_level_after_higher_win(tmp_path):
    """A win vs a level-2 monster flags a level-1 monster winnable even when the
    stat formula (predict_win) would lose against it."""
    state = make_state(max_hp=10, attack={"fire": 1}, initiative=0)
    gd = _gd(hp=10000, attack={"fire": 50}, initiative=100, code="chicken")
    gd._monster_level = {"chicken": 1, "slime": 2}
    store = LearningStore(db_path=str(tmp_path / "l.db"), character="h")
    _record_wins(store, "Fight(slime)", 1)
    assert predict_win(state, gd, "chicken") is False
    assert is_winnable(state, gd, "chicken", store) is True


def test_monotonic_win_does_not_flag_higher_level(tmp_path):
    """A win vs a level-1 monster does NOT flag a level-2 monster winnable."""
    state = make_state(max_hp=10, attack={"fire": 1}, initiative=0)
    gd = _gd(hp=10000, attack={"fire": 50}, initiative=100, code="slime")
    gd._monster_level = {"chicken": 1, "slime": 2}
    store = LearningStore(db_path=str(tmp_path / "l.db"), character="h")
    _record_wins(store, "Fight(chicken)", 1)
    assert is_winnable(state, gd, "slime", store) is False


def test_monotonic_win_vetoed_by_own_loss(tmp_path):
    """Having lost to THIS monster, the higher-level-win inference is suppressed
    (the 'until a future loss' caveat)."""
    state = make_state(max_hp=10, attack={"fire": 1}, initiative=0)
    gd = _gd(hp=10000, attack={"fire": 50}, initiative=100, code="chicken")
    gd._monster_level = {"chicken": 1, "slime": 2}
    store = LearningStore(db_path=str(tmp_path / "l.db"), character="h")
    _record_wins(store, "Fight(slime)", 1)
    _record_mixed(store, "Fight(chicken)", wins=0, losses=1)  # one loss to chicken
    assert is_winnable(state, gd, "chicken", store) is False


def test_monotonic_win_needs_an_actual_win(tmp_path):
    """A LOSS vs a higher-level monster is not a win — no inference."""
    state = make_state(max_hp=10, attack={"fire": 1}, initiative=0)
    gd = _gd(hp=10000, attack={"fire": 50}, initiative=100, code="chicken")
    gd._monster_level = {"chicken": 1, "slime": 2}
    store = LearningStore(db_path=str(tmp_path / "l.db"), character="h")
    _record_losses(store, "Fight(slime)", 1)
    assert is_winnable(state, gd, "chicken", store) is False


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


def test_is_winnable_keeps_marginal_grindable_winrate(tmp_path):
    """A monster won ~80% of observed fights is NOT vetoed: for character-XP
    grinding a loss only costs a rest cooldown, so a >40% winner is still the best
    use of cycles. The old 0.9 veto stranded a level-3 character whose ONLY in-window
    XP source (green_slime, ~80% from low HP) was sub-0.9 — it diverted to an endless
    gear grind that yields zero character XP (trace 2026-06-29). Threshold now 0.4."""
    state = make_state(max_hp=100, attack={"fire": 30}, initiative=50)
    gd = _gd(hp=30, attack={"fire": 5}, initiative=10)  # predict_win -> True
    store = LearningStore(db_path=str(tmp_path / "l.db"), character="h")
    _record_mixed(store, "Fight(mob)", wins=8, losses=2)  # 80% >= 0.4 threshold
    assert is_winnable(state, gd, "mob", store) is True
    store.close()


def test_is_winnable_vetoes_genuine_loser(tmp_path):
    """A monster lost MORE than it wins (30%) IS vetoed — at the 0.4 threshold the
    veto deselects only genuinely costly targets (loses >60%), it does not starve
    the bot of marginal-but-grindable combat."""
    state = make_state(max_hp=100, attack={"fire": 30}, initiative=50)
    gd = _gd(hp=30, attack={"fire": 5}, initiative=10)  # predict_win -> True
    store = LearningStore(db_path=str(tmp_path / "l.db"), character="h")
    _record_mixed(store, "Fight(mob)", wins=3, losses=7)  # 30% < 0.4 threshold
    assert is_winnable(state, gd, "mob", store) is False
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


def test_predict_win_boolean_unchanged_by_helper_extraction():
    """Characterization: exact booleans across all key paths through predict_win.
    These values are captured pre-refactor; the extraction of _kill_step_net /
    _die_step / _effective_player_hp must not alter any of them.

    Covers: raw_player<=0 (False), kill_step<=0 (False), die_step<=0 (True,
    sustain), die_step>0 with poison-induced loss (False), normal win via
    initiative tiebreak (True), effective_hp==0 guard (False)."""
    # Case A: raw_player <= 0 — player cannot damage → False
    state_a = make_state(max_hp=100, attack={}, initiative=50)
    gd_a = _gd(hp=30, attack={"fire": 5})
    assert predict_win(state_a, gd_a, "mob") is False

    # Case B: kill_step <= 0 — monster lifesteal out-heals player → False
    state_b = make_state(max_hp=200, attack={"fire": 5}, resistance={"fire": 100},
                         initiative=50)
    gd_b = _gd(hp=30, attack={"fire": 200}, crit=50, lifesteal=10)
    assert predict_win(state_b, gd_b, "mob") is False

    # Case C: die_step <= 0 — player lifesteal out-sustains monster → True
    gd_c = _gd(hp=100, attack={"fire": 5}, crit=0)
    gd_c._item_stats = {
        "vamp": ItemStats(code="vamp", level=1, type_="weapon", lifesteal=100),
    }
    state_c = make_state(hp=10, max_hp=10, attack={"fire": 10}, critical_strike=50,
                         initiative=50, equipment={"weapon_slot": "vamp"})
    assert predict_win(state_c, gd_c, "mob") is True

    # Case D: die_step > 0, poison-only loss — poison raises die_step → False
    state_d = make_state(max_hp=100, attack={"fire": 50}, initiative=10)
    gd_d = _gd(hp=100, attack={"fire": 50}, initiative=10, poison=100)
    assert predict_win(state_d, gd_d, "mob") is False

    # Case E: normal win — player initiative tie favours player (rtk == rtd == 2) → True
    state_e = make_state(max_hp=100, attack={"fire": 50}, initiative=10)
    gd_e = _gd(hp=100, attack={"fire": 50}, initiative=10)
    assert predict_win(state_e, gd_e, "mob") is True

    # Case F: effective_hp == 0 — state.hp = 0, fight lost before it starts → False
    state_f = make_state(max_hp=100, hp=0, attack={"fire": 10}, initiative=50)
    gd_f = _gd(hp=30, attack={"fire": 1}, initiative=0)
    assert predict_win(state_f, gd_f, "mob") is False


def _predict_win_case_matrix() -> list[tuple]:
    """Return (label, state, gd, expected_win_bool) for the key predict_win branches.

    Excludes Case C (die_step<=0) because it requires special _item_stats wiring not
    supported by the plain _gd() helper; that branch is covered by the differential
    test (test_sustain_win_returns_win_margin) instead.
    """
    return [
        # Case A: raw_player=0 (no attack) → LOSE
        ("raw_player_zero",
         make_state(max_hp=100, attack={}, initiative=50),
         _gd(hp=30, attack={"fire": 5}),
         False),
        # Case B: kill_step <= 0 (monster lifesteal out-heals) → LOSE
        ("kill_step_zero",
         make_state(max_hp=200, attack={"fire": 5}, resistance={"fire": 100}, initiative=50),
         _gd(hp=30, attack={"fire": 200}, crit=50, lifesteal=10),
         False),
        # Case D: die_step > 0, poison raises cost → LOSE
        ("poison_loss",
         make_state(max_hp=100, attack={"fire": 50}, initiative=10),
         _gd(hp=100, attack={"fire": 50}, initiative=10, poison=100),
         False),
        # Case E: normal win, player-first tie (rtk == rtd == 2) → WIN
        ("normal_win_player_first",
         make_state(max_hp=100, attack={"fire": 50}, initiative=10),
         _gd(hp=100, attack={"fire": 50}, initiative=10),
         True),
        # Case F: state.hp=0 → effective_hp==0 guard → LOSE
        ("zero_hp_loss",
         make_state(max_hp=100, hp=0, attack={"fire": 10}, initiative=50),
         _gd(hp=30, attack={"fire": 1}, initiative=0),
         False),
    ]


def test_combat_margin_sign_matches_predict_win():
    """Invariant: (combat_margin(...) > 0) == predict_win(...) for all case-matrix rows.

    Also verifies that the sentinel values LOSE_MARGIN and WIN_MARGIN are used at
    their respective exits: raw_player=0 and die_step=0 exits use sentinels, not
    arbitrary values that happen to have the right sign.
    """
    for label, state, gd, expected_win in _predict_win_case_matrix():
        margin = combat_margin(state, gd, "mob")
        pw = predict_win(state, gd, "mob")
        assert pw is expected_win, f"predict_win mismatch for {label}: {pw!r}"
        assert (margin > 0) is expected_win, (
            f"sign invariant broken for {label}: margin={margin} expected_win={expected_win}"
        )
    # Sentinel check: raw_player=0 case returns exactly LOSE_MARGIN
    _, state_a, gd_a, _ = _predict_win_case_matrix()[0]
    assert combat_margin(state_a, gd_a, "mob") == LOSE_MARGIN
    # Sentinel check: monster with no attack → die_step=0 → WIN_MARGIN
    state_sustain = make_state(max_hp=100, attack={"fire": 50}, initiative=10)
    gd_sustain = _gd(hp=100, attack={})  # no monster attack → die_step=0
    assert combat_margin(state_sustain, gd_sustain, "mob") == WIN_MARGIN


def test_combat_margin_magnitude_orders_by_cushion():
    """A player with more HP (bigger round cushion) has a strictly larger margin.

    Construction: keep rtk fixed (same attack vs same monster HP), vary player HP
    so rtd grows. Margin = rtd - rtk + 1 (player_first, tie in initiative).

    Larger rtd → larger margin, and the stronger player's margin > weaker player's.
    Also verifies the boundary: the exact-tie player (rtk == rtd, player_first) has
    margin==1 (win), while a player one round short has margin==0 (loss).

    Note: state.hp must equal max_hp so _effective_player_hp returns max_hp unchanged;
    make_state(max_hp=X) alone defaults state.hp=100 which would clamp eff_hp to 100.
    """
    gd_sym = _gd(hp=100, attack={"fire": 50}, initiative=10)

    # Tie: rtk==rtd==2, player_first → margin = 2-2+1 = 1.
    state_tie = make_state(max_hp=100, hp=100, attack={"fire": 50}, initiative=10)
    margin_tie = combat_margin(state_tie, gd_sym, "mob")
    assert margin_tie == 1, f"expected margin 1 for tie-win, got {margin_tie}"
    assert predict_win(state_tie, gd_sym, "mob") is True

    # Weaker player: rtd=1 → margin = 1-2+1 = 0 (loss).
    state_weak = make_state(max_hp=50, hp=50, attack={"fire": 50}, initiative=10)
    margin_weak = combat_margin(state_weak, gd_sym, "mob")
    assert margin_weak == 0, f"expected margin 0 for weak player, got {margin_weak}"
    assert margin_weak < margin_tie

    # Stronger player: rtd=4 → margin = 4-2+1 = 3 (cushion).
    state_strong = make_state(max_hp=200, hp=200, attack={"fire": 50}, initiative=10)
    margin_strong = combat_margin(state_strong, gd_sym, "mob")
    assert margin_strong == 3, f"expected margin 3 for strong player, got {margin_strong}"
    assert margin_strong > margin_tie
