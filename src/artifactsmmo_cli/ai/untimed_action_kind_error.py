"""A priced action kind this account never timed."""


class UntimedActionKindError(LookupError):
    """The pricer asked the seconds of an action kind neither the learning
    store's recorded server cooldowns nor, on a fresh install, the `/my/logs`
    bootstrap ever timed (the user's I2 ruling, 2026-10-31: "learning DB, then
    raise"; `fight_seconds_model.learned_kind_seconds`).

    No default stands in for it. It used to be priced as one mean planner
    action (~36 s): a 3 s withdraw at twelve times its cost.
    """

    def __init__(self, kind: str) -> None:
        super().__init__(f"no recorded cooldown times an action of kind {kind!r}")
        self.kind = kind
