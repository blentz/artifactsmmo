"""Max potions craftable right now from held ingredients: the min over ingredients
of held//need, times the craft yield. Float-free; mirrored by
formal/Formal/MaxBatchFromHeld.lean."""


def max_batch_from_held_pure(needs: list[int], held: list[int], yield_per_craft: int) -> int:
    if not needs:
        return 0
    runs = min(held[i] // needs[i] for i in range(len(needs)))
    return runs * yield_per_craft
