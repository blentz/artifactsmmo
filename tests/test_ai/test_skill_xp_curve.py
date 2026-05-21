from artifactsmmo_cli.ai.learning.skill_xp_curve import DEFAULT_GROWTH_RATIO, SkillXpCurve


def test_required_xp_empty_curve_returns_zero() -> None:
    assert SkillXpCurve(observed={}).required_xp(3) == 0


def test_required_xp_uses_observed_value() -> None:
    curve = SkillXpCurve(observed={1: 100, 2: 200})
    assert curve.required_xp(1) == 100
    assert curve.required_xp(2) == 200

def test_required_xp_beyond_observed_uses_learned_ratio() -> None:
    curve = SkillXpCurve(observed={1: 100, 2: 200})  # observed ratio 2.0
    assert curve.required_xp(3) == 400
    assert curve.required_xp(4) == 800

def test_required_xp_default_ratio_with_one_observation() -> None:
    curve = SkillXpCurve(observed={1: 100})
    assert curve.required_xp(2) == int(100 * DEFAULT_GROWTH_RATIO)

def test_total_xp_to_reach_sums_levels() -> None:
    curve = SkillXpCurve(observed={1: 100, 2: 200})
    assert curve.total_xp_to_reach(current_level=1, target_level=3) == 300

def test_cycles_to_level_divides_by_rate() -> None:
    curve = SkillXpCurve(observed={1: 100, 2: 200})
    assert curve.cycles_to_level(current_level=1, target_level=3, xp_per_cycle=50.0) == 6.0

def test_cycles_to_level_zero_when_at_target() -> None:
    curve = SkillXpCurve(observed={1: 100})
    assert curve.cycles_to_level(current_level=5, target_level=5, xp_per_cycle=10.0) == 0.0

def test_cycles_to_level_infinite_when_no_rate() -> None:
    curve = SkillXpCurve(observed={1: 100})
    assert curve.cycles_to_level(current_level=1, target_level=3, xp_per_cycle=0.0) == float("inf")

def test_is_confident_only_when_gap_observed() -> None:
    curve = SkillXpCurve(observed={1: 100, 2: 200})
    assert curve.is_confident(current_level=1, target_level=2) is True
    assert curve.is_confident(current_level=1, target_level=6) is False


# --- Fix 1: required_xp anchors on nearest observed level AT OR BELOW ---

def test_required_xp_below_all_observed_returns_zero() -> None:
    """Level below the lowest observed entry — no requirement known."""
    curve = SkillXpCurve(observed={1: 100, 2: 200})
    assert curve.required_xp(0) == 0


def test_required_xp_gap_level_anchors_on_lower_observed() -> None:
    """Gap level between two observed levels should anchor on the lower one."""
    # observed {1:100, 2:200}, ratio=2.0; required_xp(3) anchors on 2 → 200 * 2.0**1 = 400
    curve = SkillXpCurve(observed={1: 100, 2: 200})
    assert curve.required_xp(3) == 400


def test_required_xp_gap_between_non_consecutive_anchors_on_lower() -> None:
    """observed {1:100, 4:800}; gap level 2 should anchor on level 1."""
    # {1:100, 4:800}: no consecutive pairs → DEFAULT_GROWTH_RATIO
    # required_xp(2): below=[1], anchor=1, steps=1 → 100 * DEFAULT_GROWTH_RATIO
    curve = SkillXpCurve(observed={1: 100, 4: 800})
    expected = int(100 * DEFAULT_GROWTH_RATIO)
    assert curve.required_xp(2) == expected


def test_required_xp_negative_level_below_observed_returns_zero() -> None:
    """Edge case: queried level -1 with observed starting at 1."""
    curve = SkillXpCurve(observed={1: 100})
    assert curve.required_xp(-1) == 0


# --- Fix 2: confidence() method ---

def test_confidence_all_gap_levels_observed_returns_one() -> None:
    curve = SkillXpCurve(observed={1: 100, 2: 200, 3: 400})
    assert curve.confidence(1, 3) == 1.0


def test_confidence_no_gap_levels_observed_returns_zero() -> None:
    curve = SkillXpCurve(observed={})
    assert curve.confidence(1, 4) == 0.0


def test_confidence_half_gap_levels_observed_returns_half() -> None:
    # gap = range(1, 5) = [1, 2, 3, 4]; 2 of 4 observed
    curve = SkillXpCurve(observed={1: 100, 3: 400})
    assert curve.confidence(1, 5) == 0.5


def test_confidence_current_equals_target_returns_one() -> None:
    """Empty gap → always confident."""
    curve = SkillXpCurve(observed={})
    assert curve.confidence(5, 5) == 1.0
