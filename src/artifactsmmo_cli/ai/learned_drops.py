"""The fleet's drop evidence for one cycle (spec 2026-10-18 §2.8, ruling T16a):
what every drop consumer prices and ranks a drop by.

One immutable value, built once per cycle where the learning store is in hand
(`learning.drop_observations.learned_drops`, through the store's per-episode
memo) and carried on `SelectionContext.learned_drops` beside the other learned
inputs (`fight_records`, `fight_seconds`). Where a consumer holds no context it
is handed the same value explicitly: the gather and fight actions the factory
builds carry it (`GatherAction.learned_drops`, `FightAction.learned_drops`),
so the planner's gather price, the goal pools' source narrowing and the
dropper-fight pick read the very value the acquisition walk and the obtain
model's gather order read from the context.

A world with no store (a scenario, a census, a test) passes `empty()`: nothing
observed and no prospecting slope, which prices every drop at its API prior
`1/rate` (`drop_chance_core.units_per_attempt`).
"""

from dataclasses import dataclass, field
from fractions import Fraction

from artifactsmmo_cli.ai.drop_chance_core import units_per_attempt


@dataclass(frozen=True)
class LearnedDrops:
    """This season's `(attempts, hits)` per `(source, item)` and the fleet's
    prospecting slope `k`.

    `attempts` holds each observed source's attempt count, `hits` each
    `(source, item)` pair's hits; a pair absent from either is 0. Both are
    sorted tuples so the value is hashable: a cache that prices through it
    keys on it (`tiers.skill_grind_target`)."""

    attempts: tuple[tuple[str, int], ...]
    hits: tuple[tuple[tuple[str, str], int], ...]
    k: Fraction
    _attempts: dict[str, int] = field(init=False, repr=False, compare=False)
    _hits: dict[tuple[str, str], int] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # The lookups every price asks, built once: the walk asks per route.
        object.__setattr__(self, "_attempts", dict(self.attempts))
        object.__setattr__(self, "_hits", dict(self.hits))

    @classmethod
    def empty(cls) -> "LearnedDrops":
        """Nothing observed: every drop at its API prior."""
        return cls((), (), Fraction(0))

    def counts(self, source: str, item: str) -> tuple[int, int]:
        """`(attempts, hits)` of `item` at `source`."""
        return self._attempts.get(source, 0), self._hits.get((source, item), 0)

    def units_per_attempt(self, source: str, item: str, rate: int, min_quantity: int,
                          max_quantity: int, prospecting: int) -> Fraction:
        """Units of `item` one attempt at `source` yields, expected, at
        `prospecting` (`drop_chance_core.units_per_attempt`)."""
        attempts, hits = self.counts(source, item)
        return units_per_attempt(rate, min_quantity, max_quantity, attempts, hits,
                                 self.k, prospecting)

    def attempts_per_unit(self, source: str, item: str, rate: int, min_quantity: int,
                          max_quantity: int, prospecting: int) -> Fraction:
        """Attempts at `source` one unit of `item` takes, expected: the
        reciprocal of `units_per_attempt`. The key every source picker ranks by
        and the count the planner's gather and the walk's routes price."""
        return 1 / self.units_per_attempt(source, item, rate, min_quantity, max_quantity,
                                          prospecting)
