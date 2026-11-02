"""A planned drop priced at zero chance."""


class ImpossibleDropError(ValueError):
    """A leg was planned for a drop whose learned chance is zero.

    A drop nothing can yield has an infinite price, so no route should ever
    plan a leg for it: reaching the dry-streak rule with chance 0 is a pricing
    bug, named here instead of surfacing as a `ZeroDivisionError` from
    `ln(1 - 0) = 0` (`intention_progress.dry_within_luck`).
    """
