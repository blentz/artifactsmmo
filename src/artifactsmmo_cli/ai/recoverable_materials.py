"""Materials recoverable by RECYCLING licensed surplus — the acquisition face
of recycle.

`ai/recycle_surplus.recyclable_surplus` answers a DISPOSAL question (which items
may I shed, and how many BAG copies). This answers an ACQUISITION question (which
MATERIALS can I obtain, and how many units) over bag+bank. The authority is the
same one: `inventory_keep.destroyable`. "May I recycle this for parts" IS "may I
destroy this", and the keep-unification epic already answered it — including the
WORKING_KIT / COMBAT_WEAPON reasons that protect the last copper_axe. No new
KeepReason exists here, by design.

YIELD FIDELITY. `actions/factory` emits quantity=1 RecycleActions, so GOAP
recovers n copies by applying a UNIT recycle n times, each yielding
`max(1, (qty * 1) // 2)` per `RecycleAction.apply`. The total is
`n * max(1, qty // 2)` — NOT the batch expression `max(1, (qty * n) // 2)`, which
differs whenever qty == 1 (4 unit recycles of a 1-qty ingredient recover 4; the
batch form predicts 2). If this term drifts from `RecycleAction.apply`, the tier
descent promises materials the executor cannot deliver and the bot stalls.

ELIGIBILITY MIRRORS THE ACTION POOL — NOT MERELY `is_applicable`. Five static
item/world properties gate a code here: a recipe exists, a crafting skill is
known, the character meets the crafting level, a workshop for that skill is
known, AND the item's type is EQUIPPABLE (`ITEM_TYPE_TO_SLOTS`). The last gate
is not one `RecycleAction.is_applicable` itself checks — it lives in
`actions/factory`, which constructs a `RecycleAction` ONLY for equippable
codes and silently skips every `resource`/`consumable` craftable (bars,
planks, cooked food). `is_applicable` is never even consulted for those codes
because no action instance exists to ask. The lesson: eligibility must mirror
what the ACTION POOL CONTAINS, not merely what `is_applicable` would answer if
asked — a gate enforced only by construction-time filtering is just as real as
one written inside `is_applicable`, and omitting it here is the same LEAF WITH
NO PLAN livelock shape as 3166d390.

DELIBERATELY OUT OF SCOPE: `is_applicable`'s slot-floor check (`recovered =
sum(...); net = recovered - quantity; return not (net > 0 and
state.inventory_free < net)`). That is a per-cycle AFFORDABILITY condition —
whether there is bag room to receive the recovered materials right now — not a
static property of the item. GOAP re-checks the real `is_applicable` at search
time, so omitting the slot-floor here does not make the map an undeliverable
promise; it makes it an imprecise HINT, which is fine for an oracle.

Pure: reads state/game_data/ctx only, no I/O. INERT — nothing calls this yet
(see the module's own epic notes); a later behavioral census will use this
function AS ITS ORACLE.
"""

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_keep import destroyable
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState


def recoverable_materials(state: WorldState, game_data: GameData,
                          ctx: SelectionContext) -> dict[str, int]:
    """Map each material code to the units recoverable by recycling LICENSED
    surplus held in the bag OR the bank."""
    out: dict[str, int] = {}
    bank = state.bank_items or {}
    codes = set(state.inventory) | set(bank)
    for code in codes:
        recipe = game_data.crafting_recipe(code)
        if recipe is None:
            continue
        stats = game_data.item_stats(code)
        if stats is None or not stats.crafting_skill:
            continue
        if not ITEM_TYPE_TO_SLOTS.get(stats.type_):
            continue  # not equippable -> factory never builds a RecycleAction
        if state.skills.get(stats.crafting_skill, 1) < stats.crafting_level:
            continue  # skill gate: the server rejects the recycle
        if game_data.workshop_location(stats.crafting_skill) is None:
            continue  # no workshop known -> RecycleAction.is_applicable is False
        copies = destroyable(code, state, game_data, ctx)
        if copies <= 0:
            continue
        for mat_code, mat_qty in recipe.items():
            out[mat_code] = out.get(mat_code, 0) + copies * max(1, mat_qty // 2)
    return out
