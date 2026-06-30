from artifactsmmo_cli.ai.marginal_potion_qty import marginal_potion_qty_pure


# constants used throughout: min=5, threshold=950, full=500, max_stack=100
def _q(win_permille, samples=10, filled=False, held=100):
    return marginal_potion_qty_pure(samples, win_permille, 5, 950, 500, 100, filled, held)


def test_not_marginal_above_threshold_returns_zero():
    assert _q(950) == 0
    assert _q(980) == 0


def test_cold_start_returns_zero():
    assert _q(800, samples=4) == 0  # < min_samples


def test_just_below_threshold_returns_one():
    assert _q(949) == 1  # ceil of a near-zero fraction, floored at 1


def test_full_stack_at_or_below_full_winrate():
    assert _q(500) == 100
    assert _q(450) == 100  # clamped (still fought: veto floor 0.40)


def test_midband_interpolates():
    # r=725 permille -> fraction=(950-725)/450=0.5 -> ceil(0.5*100)=50
    assert _q(725) == 50


def test_monotone_non_increasing_in_winrate():
    qs = [_q(p) for p in range(500, 951, 25)]
    assert all(a >= b for a, b in zip(qs, qs[1:]))  # higher win -> not more potions


def test_clamped_to_held():
    assert _q(500, held=7) == 7  # wants full stack, holds 7


def test_slot_filled_returns_zero():
    assert _q(500, filled=True) == 0


def test_no_heal_held_returns_zero():
    assert _q(500, held=0) == 0
