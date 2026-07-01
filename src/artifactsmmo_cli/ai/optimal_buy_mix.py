"""Largest craft batch affordable by buying the per-ingredient deficit. cost(B) is
monotone non-decreasing in B, so we return the largest feasible B <= max_batch.
Float-free; mirrored by formal/Formal/OptimalBuyMix.lean."""


def _cost(needs: list[int], held: list[int], prices: list[int], batch: int) -> int:
    total = 0
    for i in range(len(needs)):
        deficit = batch * needs[i] - held[i]
        if deficit > 0:
            total += prices[i] * deficit
    return total


def optimal_buy_mix_pure(needs: list[int], held: list[int], prices: list[int],
                         gold: int, max_batch: int) -> int:
    best = 0
    for batch in range(1, max_batch + 1):
        if _cost(needs, held, prices, batch) <= gold:
            best = batch
        else:
            break  # cost monotone non-decreasing -> no larger batch is affordable
    return best
