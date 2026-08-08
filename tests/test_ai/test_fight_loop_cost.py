"""Cycles one kill really costs — the Fight plus the Rest its damage forces."""

import pytest

from artifactsmmo_cli.ai.learning.fight_loop_cost import (
    FIGHT_ACTIONS_PER_KILL,
    cycles_per_kill,
    rest_cycles_per_fight,
)
from artifactsmmo_cli.ai.thresholds import CRITICAL_HP_FRACTION


def test_no_damage_forces_no_rest():
    """A monster that costs nothing keeps the kill priced at the bare Fight —
    which is what the projection charged for EVERY monster until 2026-08-07."""
    assert rest_cycles_per_fight(0, 280) == 0.0
    assert cycles_per_kill(0, 280) == FIGHT_ACTIONS_PER_KILL


def test_damage_beyond_the_usable_band_saturates_at_one_rest():
    """One Rest restores everything, so no single fight can ever force two. The
    cap is the semantics of resting, not a safety clamp."""
    assert rest_cycles_per_fight(10_000, 280) == 1.0
    assert cycles_per_kill(10_000, 280) == 2.0


def test_light_damage_lets_fights_chain():
    """Below the rest threshold several fights fit between rests, so the rest
    term is a FRACTION — the regime armour moves a character into."""
    max_hp = 1000
    usable = (1.0 - CRITICAL_HP_FRACTION) * max_hp   # 250
    assert rest_cycles_per_fight(25, max_hp) == pytest.approx(0.1)
    assert rest_cycles_per_fight(int(usable), max_hp) == pytest.approx(1.0)
    assert cycles_per_kill(25, max_hp) == pytest.approx(1.1)


def test_rest_term_is_monotone_in_damage():
    """More damage never costs fewer rests — the property that makes better
    armour rank better rather than merely differently."""
    prev = -1.0
    for damage in range(0, 400, 10):
        cur = rest_cycles_per_fight(damage, 280)
        assert cur >= prev
        prev = cur


def test_rest_term_is_monotone_in_max_hp():
    """A bigger HP pool absorbs the same damage with fewer rests."""
    assert (rest_cycles_per_fight(100, 200) >= rest_cycles_per_fight(100, 400)
            >= rest_cycles_per_fight(100, 800))


def test_the_live_2026_08_07_boards_all_saturate():
    """The three characters measured that day all took more than the usable band
    in one fight, which is why each was observed resting after nearly every
    fight (0.94-1.00 rests/fight)."""
    assert rest_cycles_per_fight(462, 525) == 1.0   # Robby vs pig
    assert rest_cycles_per_fight(144, 280) == 1.0   # C3P0 vs red_slime
    assert rest_cycles_per_fight(108, 280) == 1.0   # Lor  vs red_slime


def test_degenerate_max_hp_is_not_free():
    """A zero/negative HP pool must not read as a costless fight — it is the one
    case where the ratio is undefined, and 'free' is the dangerous answer."""
    assert rest_cycles_per_fight(10, 0) == 0.0
    assert rest_cycles_per_fight(-5, 280) == 0.0


def test_threshold_is_the_guard_the_runtime_rests_on():
    """The usable band comes from the SAME constant the HP_CRITICAL guard rests
    on. A projection modelling a policy the runtime does not run prices a loop
    nobody executes."""
    max_hp = 400
    usable = (1.0 - CRITICAL_HP_FRACTION) * max_hp
    just_under = rest_cycles_per_fight(int(usable) - 1, max_hp)
    assert just_under < 1.0
    assert rest_cycles_per_fight(int(usable) + 1, max_hp) == 1.0
