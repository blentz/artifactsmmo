from artifactsmmo_cli.ai.learning.skill_xp_curve import DEFAULT_GROWTH_RATIO, SkillXpCurve


def test_required_xp_uses_observed_value():
    curve = SkillXpCurve(observed={1: 100, 2: 200})
    assert curve.required_xp(1) == 100
    assert curve.required_xp(2) == 200

def test_required_xp_beyond_observed_uses_learned_ratio():
    curve = SkillXpCurve(observed={1: 100, 2: 200})  # observed ratio 2.0
    assert curve.required_xp(3) == 400
    assert curve.required_xp(4) == 800

def test_required_xp_default_ratio_with_one_observation():
    curve = SkillXpCurve(observed={1: 100})
    assert curve.required_xp(2) == int(100 * DEFAULT_GROWTH_RATIO)

def test_total_xp_to_reach_sums_levels():
    curve = SkillXpCurve(observed={1: 100, 2: 200})
    assert curve.total_xp_to_reach(current_level=1, target_level=3) == 300

def test_cycles_to_level_divides_by_rate():
    curve = SkillXpCurve(observed={1: 100, 2: 200})
    assert curve.cycles_to_level(current_level=1, target_level=3, xp_per_cycle=50.0) == 6.0

def test_cycles_to_level_zero_when_at_target():
    curve = SkillXpCurve(observed={1: 100})
    assert curve.cycles_to_level(current_level=5, target_level=5, xp_per_cycle=10.0) == 0.0

def test_cycles_to_level_infinite_when_no_rate():
    curve = SkillXpCurve(observed={1: 100})
    assert curve.cycles_to_level(current_level=1, target_level=3, xp_per_cycle=0.0) == float("inf")

def test_is_confident_only_when_gap_observed():
    curve = SkillXpCurve(observed={1: 100, 2: 200})
    assert curve.is_confident(current_level=1, target_level=2) is True
    assert curve.is_confident(current_level=1, target_level=6) is False
