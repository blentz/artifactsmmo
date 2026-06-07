"""Craft-vs-buy acquisition decision. For a needed item an NPC sells, choose BUY
over CRAFT only when buying is strictly fewer cooldowns AND affordable above a gold
reserve. Cooldowns is the optimization metric; gold is a HARD constraint (the
reserve), never converted. The pure `cheaper_acquisition` is the differential
target proved in formal/Formal/CraftVsBuy.lean; `acquisition_method` is the impure
adapter that assembles inputs from GameData and delegates.
"""

from enum import Enum

GOLD_RESERVE = 500
"""Gold kept in reserve for essentials (e.g. bank expansion); buying a needed item
may not drop gold below this. Tunable; the proof is parametric in `reserve`."""


class Method(Enum):
    CRAFT = "craft"
    BUY = "buy"


def cheaper_acquisition(
    craft_cooldowns: int, buy_cooldowns: int, total_price: int, gold: int, reserve: int
) -> Method:
    """BUY iff affordable above the reserve AND strictly fewer cooldowns; else CRAFT."""
    affordable = gold - total_price >= reserve
    return Method.BUY if (affordable and buy_cooldowns < craft_cooldowns) else Method.CRAFT
