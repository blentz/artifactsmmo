"""Transition attempted from the wrong map layer."""


class TransitionLayerError(RuntimeError):
    """A `MapTransitionAction` was executed while the character stood on a
    different layer than its portal tile.

    Coordinates do not identify a tile — (layer, x, y) does — so a transition
    whose portal is at (5, 5) underground would, from (5, 5) on the overworld,
    see "already at the portal", skip its move leg, and POST
    `/action/transition` from whatever unrelated tile the character was really
    standing on. That is either a server error or, worse, a DIFFERENT door
    silently taken.

    This is unreachable through the planner, whose region gate confines an
    action to one access region and therefore one layer; it fires when a plan
    is executed against state it was not made for. Raising names that
    staleness instead of acting on it.
    """
