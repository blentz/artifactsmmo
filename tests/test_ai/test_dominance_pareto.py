from artifactsmmo_cli.ai.dominance_pareto import pareto_dominates


def test_pareto_dominates_truth_table():
    assert pareto_dominates([5, 5], [3, 4]) is True     # >= all, > some
    assert pareto_dominates([5, 4], [3, 4]) is True      # tie on one, > other
    assert pareto_dominates([3, 4], [3, 4]) is False     # equal everywhere
    assert pareto_dominates([5, 2], [3, 4]) is False     # loses on monster 2
    assert pareto_dominates([], []) is False             # no monsters → not dominated
    assert pareto_dominates([3], [5]) is False
