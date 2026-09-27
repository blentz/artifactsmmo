"""Does the obtain model reproduce `obtain_sources` under the LEGACY policy?

Phase 1 step 1 of `docs/PLAN_decision_architecture_redesign.md`: the model is
built beside the old walk, and no consumer moves onto it until this census
reports zero differences over every item of real game data, for every world
it is given (the scenario fixtures, and the live fleet's states).

Later steps change policy defaults one disagreement (D-x) at a time. Each such
change must show up here as a classified difference against the legacy answer,
never as an unexplained one.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import LEGACY
from artifactsmmo_cli.ai.obtain_sources import Source, obtain_sources
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import GOLD_CODE, WorldState


@dataclass(frozen=True)
class LegacyDifference:
    """One item whose model answer differs from `obtain_sources`."""

    item: str
    legacy: tuple[Source, ...]
    model: tuple[Source, ...]


def census_items(game_data: GameData) -> list[str]:
    """Every item code in the catalogue, plus gold (the SELL route's target)."""
    return [*sorted(game_data.all_item_stats), GOLD_CODE]


def legacy_differences(state: WorldState, game_data: GameData, ctx: SelectionContext,
                       now: datetime, items: Iterable[str]) -> list[LegacyDifference]:
    """Items whose `ready(item, LEGACY)` is not exactly `obtain_sources(item)`,
    compared as ordered `Source` lists."""
    model = ObtainModel(state, game_data, ctx, now)
    out: list[LegacyDifference] = []
    for item in items:
        legacy = tuple(obtain_sources(item, state, game_data, ctx))
        mine = tuple(Source(r.kind, r.via, r.yield_per, r.capacity)
                     for r in model.ready(item, LEGACY))
        if legacy != mine:
            out.append(LegacyDifference(item, legacy, mine))
    return out
