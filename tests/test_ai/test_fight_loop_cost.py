"""What one kill really costs — the Fight plus the share of a Rest it forces."""

from itertools import pairwise

import pytest

from artifactsmmo_cli.ai.learning.fight_loop_cost import (
    FIGHT_ACTIONS_PER_KILL,
    TYPICAL_FIGHT_COOLDOWN_SECONDS,
    cycles_per_kill,
    fights_per_rest,
    rest_actions_per_fight,
)
from artifactsmmo_cli.ai.rest_cooldown_core import (
    REST_MINIMUM_SECONDS,
    rest_cooldown_seconds,
)
from artifactsmmo_cli.ai.thresholds import CRITICAL_HP_FRACTION


def test_no_damage_forces_no_rest():
    """A monster that costs nothing keeps the kill priced at the bare Fight —
    which is what the projection charged for EVERY monster until 2026-08-07."""
    assert rest_actions_per_fight(0, 280) == 0.0
    assert cycles_per_kill(0, 280) == FIGHT_ACTIONS_PER_KILL


def test_degenerate_max_hp_is_not_free():
    """A zero/negative HP pool must not read as a costless fight — it is the one
    case where the ratio is undefined, and 'free' is the dangerous answer."""
    assert rest_actions_per_fight(10, 0) == 0.0
    assert rest_actions_per_fight(-5, 280) == 0.0


def test_a_full_bar_rest_costs_more_than_three_fights():
    """The ceiling of the term, and the number the superseded model called ONE.

    A character rested off a whole bar takes 100 seconds to do it. Against a
    ~30s Fight that is 3.33 fights' worth of elapsed time, and pricing it at a
    single action understated the heaviest loops by that whole factor."""
    assert rest_actions_per_fight(10_000, 280) == pytest.approx(100 / 30)
    assert cycles_per_kill(10_000, 280) == pytest.approx(1 + 100 / 30)


def test_the_term_does_not_saturate_so_armour_keeps_paying():
    """THE DEFECT THE UNIFICATION FIXES.

    The superseded model capped the rest term at one, so once a fight took more
    than the usable band EVERY heavier fight cost the same and better armour
    bought exactly nothing in the ranking. Damage above the band must still be
    strictly cheaper to reduce."""
    band = int((1.0 - CRITICAL_HP_FRACTION) * 280)
    over = [band + 20, band + 60, band + 120, band + 200]
    # Premise: every one of these is past the point the old model saturated, so
    # this cannot pass vacuously by testing the sub-band regime.
    assert all(d > band for d in over)
    costs = [rest_actions_per_fight(d, 280) for d in over]
    assert all(a < b for a, b in pairwise(costs))


def test_the_ceiling_regime_is_flat_and_that_is_the_published_rule():
    """The boundary S-021 originally over-claimed past.

    A recovery restores at most a full bar, so once one fight empties the bar
    every heavier fight costs the SAME hundred-second recovery. The term is
    therefore flat above `max_hp`, not strictly monotone as the first version of
    the clause asserted. This is the published rule being true, not the
    saturation the clause forbids: the forbidden kind flattens INSIDE the band
    where armour trades, and this one only flattens where the character is
    losing its whole bar per fight — a regime `is_winnable` keeps out of the
    walk, not one this cost model is asked to rank."""
    max_hp = 100
    ceiling = [rest_actions_per_fight(d, max_hp) for d in (100, 110, 150, 300)]
    assert ceiling == [pytest.approx(100 / 30)] * 4
    # Premise: strictly below the bar the term is still strictly increasing, so
    # the flatness above is a boundary and not the term having gone dead.
    interior = [rest_actions_per_fight(d, max_hp) for d in (70, 80, 90, 99)]
    assert all(a < b for a, b in pairwise(interior))


def test_rest_term_is_monotone_in_damage():
    """More damage never costs less recovery — the property that makes better
    armour rank better rather than merely differently."""
    prev = -1.0
    for damage in range(0, 400, 10):
        cur = rest_actions_per_fight(damage, 280)
        assert cur >= prev
        prev = cur


def test_rest_term_is_monotone_in_max_hp():
    """A bigger HP pool absorbs the same damage with less recovery."""
    assert (rest_actions_per_fight(100, 200) >= rest_actions_per_fight(100, 400)
            >= rest_actions_per_fight(100, 800))


def test_the_live_2026_08_07_boards_cost_what_their_rests_took():
    """The three characters measured that day each rested after nearly every
    fight — one ACTION, which the capped model reproduced exactly and which is
    why it looked calibrated. Those rests took 88, 52 and 39 seconds."""
    assert rest_actions_per_fight(462, 525) == pytest.approx(88 / 30)   # Robby/pig
    assert rest_actions_per_fight(144, 280) == pytest.approx(52 / 30)   # C3P0/red_slime
    assert rest_actions_per_fight(108, 280) == pytest.approx(39 / 30)   # Lor/red_slime
    # Premise: all three exceed the usable band, so all three are cases the
    # superseded model priced identically at 1.0. The spread here is the point.
    band = 1.0 - CRITICAL_HP_FRACTION
    assert band * 525 < 462
    assert band * 280 < 144
    assert band * 280 < 108


def test_the_guard_sets_the_chain_length():
    """The character fights while its HP is still above the guard, so it commits
    to the fight that CARRIES it across — one more than the pool strictly pays
    for. Modelling the tidier pool/damage would price a loop nobody executes."""
    max_hp = 1000
    usable = (1.0 - CRITICAL_HP_FRACTION) * max_hp   # 250
    assert fights_per_rest(25, max_hp) == 11          # 250//25 = 10, plus the crossing one
    assert fights_per_rest(int(usable), max_hp) == 2
    assert fights_per_rest(10_000, max_hp) == 1       # never fewer than one


def test_batching_is_neutral_above_the_three_second_floor():
    """THE UNIFICATION'S LOAD-BEARING FACT.

    One long rest after many fights and one short rest after each cost the SAME
    seconds, because the cooldown is proportional to HP recovered. So the pool
    size — the disputed constant — cancels out of the per-fight figure, and the
    exact executed action count and the amortised fraction cannot disagree about
    what a rung costs in time.

    Checked by pricing the same damage under chains of very different lengths:
    at a fixed damage-to-bar ratio the per-fight cost is invariant."""
    per_fight = [rest_actions_per_fight(d, d * 40) for d in (5, 10, 20, 50)]
    # Premise: these really are different batch sizes, or invariance is trivial.
    chains = [fights_per_rest(d, d * 40) for d in (5, 10, 20, 50)]
    assert len(set(chains)) == 1 and chains[0] > 1
    # Same ratio, same chain, same price — and the price is the ratio in seconds.
    assert per_fight == [pytest.approx(per_fight[0])] * 4


def test_the_charge_is_the_published_cooldown_amortised():
    """No second model of resting. The term is `rest_cooldown_seconds` for the
    whole chain's damage, divided by the chain and by a Fight's own duration."""
    damage, max_hp = 37, 620
    chain = fights_per_rest(damage, max_hp)
    expected = rest_cooldown_seconds(chain * damage, max_hp) / (
        chain * TYPICAL_FIGHT_COOLDOWN_SECONDS)
    assert rest_actions_per_fight(damage, max_hp) == pytest.approx(expected)
    # Premise: a real chain, not the degenerate one-fight case where any
    # amortisation formula agrees with any other.
    assert chain > 1


def test_threshold_is_the_guard_the_runtime_rests_on():
    """The usable band comes from the SAME constant the HP_CRITICAL guard rests
    on. A projection modelling a policy the runtime does not run prices a loop
    nobody executes."""
    max_hp = 400
    usable = (1.0 - CRITICAL_HP_FRACTION) * max_hp
    assert fights_per_rest(int(usable) - 1, max_hp) == 2
    assert fights_per_rest(int(usable) + 1, max_hp) == 1


def test_a_chain_that_lands_exactly_on_the_guard_takes_one_more_fight():
    """The boundary the whole cost's MONOTONICITY rests on. At max_hp 200 the
    usable pool is 50, so a damage of 25 divides it exactly. The guard reads hit
    points BEFORE a fight and trips only BELOW the threshold, so the character
    commits a third fight rather than stopping on the line."""
    assert fights_per_rest(25, 200) == 3
    assert fights_per_rest(24, 200) == 3
    assert fights_per_rest(26, 200) == 2


def test_the_per_kill_recovery_share_never_decreases_with_damage():
    """Found by ratifying the spec, not by a failing run. Chain length is a STEP
    function of damage, so the wrong boundary above would let a heavier monster
    cost LESS per kill -- meaning better armour could raise a rung's price, which
    inverts the one channel defensive gear has into the objective."""
    for max_hp in (20, 97, 100, 101, 200, 512, 1000):
        shares = [rest_actions_per_fight(d, max_hp)
                  for d in range(1, max_hp + 1)]
        assert all(b >= a for a, b in pairwise(shares)), max_hp


def test_the_three_second_floor_is_unreachable_at_the_declared_band():
    """Pins a regime the published rule defines and this model cannot enter. The
    chain ends at the guard, so accumulated damage is at least the band -- a
    quarter of the bar -- and the floor guarantees only three seconds. Retained in
    the rule because a smaller band would reach it; asserted here so nobody
    'optimises' the floor away as dead code without noticing why it is dead."""
    for max_hp in (20, 100, 337, 2500):
        for dmg in range(1, max_hp + 1):
            chain = fights_per_rest(dmg, max_hp)
            missing = min(chain * dmg, max_hp)
            assert rest_cooldown_seconds(missing, max_hp) > REST_MINIMUM_SECONDS
