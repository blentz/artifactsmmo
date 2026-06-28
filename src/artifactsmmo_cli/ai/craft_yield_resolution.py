"""Resolve each craftable item's effective output yield: learned > prior > 1."""

from collections.abc import Mapping
from typing import Protocol


class _YieldData(Protocol):
    """Minimal GameData interface needed by resolve_craft_yields."""

    @property
    def crafting_recipes(self) -> Mapping[str, dict[str, int]]: ...

    def craft_yield(self, code: str) -> int: ...


class _YieldHistory(Protocol):
    """Minimal LearningStore interface needed by resolve_craft_yields."""

    def observed_craft_yield(self, code: str) -> tuple[int, int] | None: ...


def resolve_craft_yields(
    game_data: _YieldData, history: _YieldHistory | None
) -> dict[str, int]:
    """{item_code: effective yield} for every craftable item.

    Prior = game_data.craft_yield(code) (CraftSchema.quantity, default 1).
    Override with history.observed_craft_yield(code)[0] (the observed produced
    quantity) when present. Learning never reaches the proved cores — callers
    pass the returned map in.
    """
    yields: dict[str, int] = {
        code: game_data.craft_yield(code) for code in game_data.crafting_recipes
    }
    if history is not None:
        for code in game_data.crafting_recipes:
            observed = history.observed_craft_yield(code)
            if observed is not None:
                yields[code] = observed[0]
    return yields
