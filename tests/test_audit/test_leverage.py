import pytest

from artifactsmmo_cli.audit.leverage import GapItem, leverage_score, rank_backlog


def test_invalid_kind_raises():
    with pytest.raises(ValueError, match="unknown gap kind"):
        GapItem(concept="foo", kind="INVALID", journey_impact=1, live_bottleneck=1, stall_risk=1)


def test_score_is_product_of_factors():
    g = GapItem(concept="grandexchange", kind="MISSING", journey_impact=3, live_bottleneck=2, stall_risk=1)
    assert leverage_score(g) == 6


def test_ignore_kind_scores_zero():
    g = GapItem(concept="leaderboard", kind="IGNORE", journey_impact=3, live_bottleneck=3, stall_risk=3)
    assert leverage_score(g) == 0


def test_rank_sorts_descending_stable_by_concept():
    a = GapItem("a", "MISSING", 1, 1, 1)   # 1
    b = GapItem("b", "WRONG-POLICY", 3, 2, 2)  # 12
    c = GapItem("c", "THIN", 2, 2, 1)      # 4
    assert [g.concept for g in rank_backlog([a, b, c])] == ["b", "c", "a"]
