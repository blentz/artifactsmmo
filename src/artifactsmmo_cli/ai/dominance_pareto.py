"""Per-monster Pareto dominance: a peer dominates an item iff it scores at least
as high against EVERY monster and strictly higher against at least one. Pure,
integer-exact (mirrors Lean `Formal.DominancePareto.paretoDominates`)."""


def pareto_dominates(peer_scores: list[int], item_scores: list[int]) -> bool:
    """True iff `peer_scores >= item_scores` componentwise AND strictly greater
    on at least one component. Empty vectors → False (nothing to dominate)."""
    geq_all = all(p >= i for p, i in zip(peer_scores, item_scores))
    gt_some = any(p > i for p, i in zip(peer_scores, item_scores))
    return geq_all and gt_some
