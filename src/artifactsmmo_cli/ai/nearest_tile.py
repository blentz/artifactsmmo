"""Manhattan-nearest tile selection — the single spatial-routing primitive every
gather/fight/move action resolves its destination against. On the live single-layer,
no-obstacle, single-hop movement model the Manhattan-nearest tile IS the least-cost
destination (cost = 6 + manhattan, monotone in distance), so this pick is the trusted
distance input feeding GatherSelection's candidate `distance` field. Ties on distance
are broken lexicographically by `(x, y)` for a deterministic, unique winner — the SAME
total order whether a step is being PLANNED (apply) or EXECUTED, closing the
apply/execute divergence (apply previously used `min(tiles)`, execute Manhattan-min).
Pure: no I/O. This is the differential target proved in formal/Formal/NearestTile.lean.
"""


def nearest_tile(
    origin_x: int, origin_y: int, tiles: frozenset[tuple[int, int]] | list[tuple[int, int]]
) -> tuple[int, int] | None:
    """Return the tile minimizing `(manhattan_distance, x, y)` from the origin, or
    `None` if `tiles` is empty. The lex tie-break on `(x, y)` makes the winner unique
    and deterministic across plan-time and execute-time callers."""
    if len(tiles) == 0:
        return None
    return min(
        tiles,
        key=lambda t: (abs(t[0] - origin_x) + abs(t[1] - origin_y), t[0], t[1]),
    )


def nearest_or_error(
    origin_x: int, origin_y: int, tiles: frozenset[tuple[int, int]] | list[tuple[int, int]], what: str
) -> tuple[int, int]:
    """`nearest_tile` for callers that require a destination: raises `ValueError`
    (naming `what` kind of locations were empty) instead of returning `None`."""
    dest = nearest_tile(origin_x, origin_y, tiles)
    if dest is None:
        raise ValueError(f"no {what} locations to choose from")
    return dest
