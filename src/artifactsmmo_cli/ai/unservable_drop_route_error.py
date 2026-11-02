"""A walked DROP route whose dropper cannot be fought."""


class UnservableDropRouteError(RuntimeError):
    """The walk served a DROP route through a dropper whose fight the pool
    holds but the proved selection (`drop_fight_selection.select_drop_fight`)
    refused.

    The walk admits a DROP route on the same gates the selection's oracle asks
    (`obtain_model.drop_routes._fight_gates`: a routable spawn, winnable at
    restorable hp, xp-positive unless the item's `grey_ok`), so a priced route
    is servable by construction. Reaching this is that agreement broken: a
    defect, named, rather than a step that silently plans nothing (review I4).
    """

    def __init__(self, item: str, monster: str) -> None:
        super().__init__(f"the walk served {item} off {monster}, which no fight can serve")
        self.item = item
        self.monster = monster
