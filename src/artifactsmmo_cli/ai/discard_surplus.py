# discard_surplus

"""What the DISCARD route may shed, and when.

DISCARD is the LAST-RESORT disposal route: `disposal_route(recyclable, bank_ok,
future_value)` orders RECYCLE > DEPOSIT > DELETE, and the DELETE arm is the only
one that recovers NOTHING at all. So the copies it takes must be licensed by the
keep authority (`ai/inventory_keep.py`) and by nothing else.

PROTECTION IS THE AUTHORITY'S, NOT OURS (item-protection-authority epic, Task 9).
The discard path used to source its floor from TWO places, and both were the wrong
kind of thing:

  * `inventory_caps.useful_quantity_cap` — a "how many are USEFUL" heuristic, not a
    protection floor. It is blind to the BANK, so a tool whose spares sit in the bank
    is invisible to it;
  * `guards.active_profile` — a recipe closure over the `target_gear | target_tools`
    CODE-SET, i.e. "keep ALL copies of every BiS gear/tool code". `copper_axe` is a
    `target_tools` member: that blanket is one of the seven hoard bugs, and its type
    could not express anything else.

The licensed quantity is `min(bankable, destroyable)` — the copies surplus to BOTH
caps, the same composition RECYCLE (`ai/recycle_surplus.py`) and SELL
(`ai/accumulation_sell.py`) ship, because a discard is a BAG-side DESTRUCTION and
therefore answers to both:

  * `destroyable` (bag+bank beyond `keep_owned`) LICENSES it: destruction is
    IRREVERSIBLE, so the OWNED cap is the one that may permit it. Bank copies count
    toward satisfying that cap — they are still owned.
  * `bankable` (bag beyond `keep_in_bag`) BOUNDS it to the copies that may leave the
    BAG at all. The in-bag ladder is where `WORKING_KIT` / `COMBAT_WEAPON` /
    `HEALING_CONSUMABLE` / `COMMITTED_RECIPE` / `GOAL_MATERIALS` live, and
    `destroyable` ALONE would DELETE the one tool the gather re-arm is about to equip:
    with 1 axe ferried into the bag and 17 in the bank, `keep_owned` is 1 → 17
    destroyable, and the ONLY copy the deleter can reach is the working one.
    `min(bankable, destroyable)` = min(0, 17) = 0.

THE PRESSURE GATE STAYS — it decides WHEN to shed, not WHAT, and it is correct.
`inventory_caps.overstocked_items` is SPACE-DRIVEN (spec 2026-06-07, proved as
`Formal.InventoryProfile.overstockExcess`): below the high watermark the bag has real
free slots and NOTHING is overstock, so a hoard the authority would happily license is
still not deleted while there is room to hold it. It is a POLICY, exactly like the
RATIO gate SELL kept: the gate says WHETHER, the authority says HOW MANY.

Pure: reads state/game_data/ctx only, no I/O.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_caps import overstocked_items
from artifactsmmo_cli.ai.inventory_keep import bankable, destroyable
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState


def discardable_surplus(state: WorldState, game_data: GameData,
                        ctx: SelectionContext) -> dict[str, int]:
    """Map each shed-eligible held code to the number of BAG copies the keep
    authority licenses for disposal: `min(bankable, destroyable)`.

    Only codes the SPACE-PRESSURE gate reports as overstock are considered — see
    the module docstring: the watermark decides WHEN, the authority decides HOW MANY.
    A code the gate raises but the authority licenses 0 of (currency at any pile
    size; the ferried working tool) is simply not shed.

    `ctx` is the per-cycle `SelectionContext` the keep authority reads (`gear_keep` =
    the active-profile gear demand, `step_profile` = the active goal's material
    needs). It REPLACES the `profile` code-set closure `guards.active_profile` used
    to build."""
    out: dict[str, int] = {}
    for code in overstocked_items(state, game_data):
        surplus = min(bankable(code, state, game_data, ctx),
                      destroyable(code, state, game_data, ctx))
        if surplus > 0:
            out[code] = surplus
    return out
