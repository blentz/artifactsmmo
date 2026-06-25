# accumulation_sell

"""Ratio-driven, space-pressure-independent sell-down of accumulated multiples.

Pure integer-exact core (no float, so it mirrors the Lean `AccumulationSell`
def byte-for-byte under the differential gate). An item is over-accumulated when
its held quantity is a large multiple of its keep-cap (`useful_quantity_cap`);
the bot sheds the surplus down to the cap by selling, with urgency rising
geometrically (one step per doubling of the ratio).
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_caps import useful_quantity_cap
from artifactsmmo_cli.ai.world_state import WorldState


ACCUM_MULT = 5
"""Fire the accumulation sell when `held >= ACCUM_MULT * max(cap, 1)`."""

SEVERE_STEPS = 5
"""`accumulation_steps >= SEVERE_STEPS` (held >= cap*32) escalates the sell above
the progression band (see `tiers/means.py` SELL_PRESSURED)."""


def accumulation_steps(held: int, cap: int) -> int:
    """Geometric severity: the largest `k >= 0` with `eff_cap * 2**k <= held`
    (= floor(log2(held / eff_cap))), `eff_cap = max(cap, 1)`. 0 when held is
    below `eff_cap`. Integer-exact doubling — no float."""
    eff_cap = cap if cap > 1 else 1
    if held < eff_cap:
        return 0
    k = 0
    bound = eff_cap
    while bound * 2 <= held:
        bound = bound * 2
        k = k + 1
    return k


def accumulation_excess(held: int, cap: int) -> int:
    """`held - max(cap, 0)` when `held >= ACCUM_MULT * max(cap, 1)`, else 0.
    The RATIO gate uses `eff_cap = max(cap, 1)`; the amount kept is the TRUE cap,
    so a dominated item (cap 0) past the gate sells down to 0, a kept item
    (cap 1) sells down to 1."""
    eff_cap = cap if cap > 1 else 1
    if held < ACCUM_MULT * eff_cap:
        return 0
    keep = cap if cap > 0 else 0
    return held - keep


def _is_sellable(code: str, game_data: GameData) -> bool:
    """An item with a reachable NPC buyer that is tradeable — the per-item rule
    behind `tiers/guards._has_sellable`."""
    stats = game_data.item_stats(code)
    if stats is not None and not stats.tradeable:
        return False
    return bool(game_data.npcs_buying_item(code))


def sellable_accumulation(state: WorldState, game_data: GameData) -> dict[str, int]:
    """Map each SELLABLE over-ratio inventory code to its sell-down-to-cap excess."""
    out: dict[str, int] = {}
    for code, held in state.inventory.items():
        if held <= 0 or not _is_sellable(code, game_data):
            continue
        cap = useful_quantity_cap(code, state, game_data)
        excess = accumulation_excess(held, cap)
        if excess > 0:
            out[code] = excess
    return out


def worst_accumulation_steps(state: WorldState, game_data: GameData) -> int:
    """Max `accumulation_steps` over sellable over-ratio items (0 if none) —
    the severity signal driving the SELL_PRESSURED escalation."""
    worst = 0
    for code, held in state.inventory.items():
        if held <= 0 or not _is_sellable(code, game_data):
            continue
        cap = useful_quantity_cap(code, state, game_data)
        if accumulation_excess(held, cap) > 0:
            steps = accumulation_steps(held, cap)
            if steps > worst:
                worst = steps
    return worst
