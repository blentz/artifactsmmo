"""THE model of how an item can be obtained — the one source of truth every
producer of a plan must consume.

The bot has two plan producers: the GOAP action pool (six ways to get an
item — gather, craft, withdraw, recycle, NPC-buy, fight-for-drop) and
`ai/craft_plan_gen`'s recipe-tree chain builder (`ai/next_craft_core.py`'s
`NextAction.kind`, which can express only THREE — gather, craft, withdraw,
because it walks recipe edges and nothing else). Every route beyond those
three was hand-bolted into the generator as a separate special case
(`_recycle_prefix`, `drop_fights`, a `LevelSkill` early-return, and NPC-buy
wasn't handled at all) — 578 lines of duplicated modeling. That duplication
is why the recycle-as-acquisition epic shipped seven green commits that were
INERT for any roomy bag: it taught the action pool about recycling, and the
generator — which answers first — could not express it.

`obtain_sources` is the fix: ONE pure function answers "how may I obtain this
item, right now?" for every consumer. Adding a SEVENTH source is one edit to
this module, and every consumer gains it structurally — the "which of the two
producers knows this route?" bug class becomes unrepresentable.

PRIORITY ORDER (the whole point of this file). `obtain_sources` returns
sources in this declared order — a descent takes the FIRST applicable one:

    1. WITHDRAW — a copy is already in the bank. Consumes nothing new.
    2. RECYCLE  — a licensed surplus item's recipe yields it. Turns dead
                  stock into the material.
    3. CRAFT    — it has a recipe, the crafting-skill gate is met, and a
                  workshop is known.
    4. GATHER   — some resource drops it.
    5. BUY      — a permanent (non-event) NPC vendor sells it and its
                  location is known.
    6. DROP     — a winnable monster drops it.

Rationale: prefer sources that consume stock ALREADY OWNED over sources that
create new work. This generalises the rule `next_craft_core._next` already
hard-codes (prefer a bank withdraw over descending into a recipe). RECYCLE
sits with WITHDRAW at the top because it also consumes stock already owned
(dead equipment) rather than spending a fresh gather/craft/buy/fight cycle.

ELIGIBILITY MIRRORS THE ACTION POOL, NOT MERELY WHAT `is_applicable` WOULD
SAY IF ASKED. A source the executor cannot actually serve is a LEAF WITH NO
PLAN — the livelock shape of `3166d390`. In particular:

- RECYCLE reproduces `ai/recoverable_materials.recoverable_materials`'s gates
  EXACTLY: the source item must have a recipe, a known `crafting_skill`, the
  character must meet its `crafting_level`, its workshop must be known, AND
  it must be EQUIPPABLE (`ITEM_TYPE_TO_SLOTS`) — `RecycleAction` objects are
  only ever CONSTRUCTED by `actions/factory.py` for equippable codes, so a
  craftable-but-non-equippable item (bars, planks, cooked food) has NO
  action in existence to serve the recycle, whatever `is_applicable` would
  say if asked. The yield term is `max(1, mat_qty // 2)` — the repeated
  UNIT-recycle yield `actions/factory` actually emits (quantity=1
  `RecycleAction`s), NOT the batch form `max(1, (mat_qty * n) // 2)`, which
  differs whenever `mat_qty == 1`.
- WITHDRAW requires `ctx.bank_accessible` — `WithdrawItemAction.is_applicable`
  refuses unconditionally when `not accessible`, and every construction site
  in `factory.py` threads `accessible=ctx.bank_accessible`. `bank_accessible`
  is a persisted, level-gated blocker that stays False for the whole early
  game while `state.bank_items` is populated regardless (the bank sync runs
  unconditionally), so without this gate a pre-unlock character would get a
  WITHDRAW source with no action in existence to serve it.
- CRAFT requires the skill gate met AND `workshop_location(skill)` known —
  a recipe with no workshop on file cannot be executed.
- BUY requires a PERMANENT vendor (`not is_event_npc`) whose location is
  known — an event vendor is not reliably reachable, so it cannot anchor a
  plan.
- GATHER requires the sourcing resource to have a currently-live tile in
  `game_data.all_resource_locations` — the same mapping `factory.py` builds
  `GatherAction`s from, which merges an event resource's tiles only while
  its event is active.
- DROP requires the dropper to be `is_winnable` AND have a currently-live
  tile in `game_data.all_monster_locations` — the same mapping `factory.py`
  builds `FightAction`s from. `is_winnable` is a pure combat-stat prediction
  and says nothing about reachability; an event monster whose event is
  inactive has no `FightAction` in existence, whatever its stats predict.

Pure: reads state/game_data/ctx only, no I/O. INERT — nothing calls this
yet. The parity census (a later task) will use this function AS ITS ORACLE:
if the GOAP pool can serve a material, this function must be able to name a
source for it, and vice versa. An oracle and its consumer written together
are wrong together, so this module is pinned by unit tests before any
consumer exists.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_keep import destroyable
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

# Sentinel capacity for a source kind that is never stock-limited (GATHER,
# BUY, DROP, CRAFT — you can always gather/buy/craft/fight again). A plain
# large int rather than `None` so every consumer's `min(deficit, capacity)`
# needs no None-branch.
UNBOUNDED_CAPACITY = 10**9


class SourceKind(Enum):
    """The six ways an item can be obtained, in ascending order of "creates
    new work" — see the module docstring for the declared priority policy."""

    WITHDRAW = "withdraw"
    RECYCLE = "recycle"
    CRAFT = "craft"
    GATHER = "gather"
    BUY = "buy"
    DROP = "drop"


@dataclass(frozen=True)
class Source:
    """One concrete way to obtain a target item right now.

    Attributes:
        kind: Which of the six routes this is.
        code: The resource code (GATHER), the recipe/bank item code (CRAFT /
            WITHDRAW — identical to the target), the item to DESTROY (RECYCLE
            — the SOURCE item, never the target), the NPC code (BUY), or the
            monster code (DROP).
        yield_per: Units of the TARGET obtained per single application of
            this source (one gather, one craft run, one unit recycle, one
            purchase, one kill).
        capacity: Max units of the TARGET this source can deliver RIGHT NOW,
            given currently-known stock. RECYCLE is genuinely bounded —
            `destroyable(code) * yield_per`, the LICENSED (keep-authority
            applied) copies of the source item times its per-copy yield, NOT
            raw physical stock (which would license melting protected
            copies). WITHDRAW is bounded by the bank's current stock of the
            item (`yield_per` is always 1 there, so this equals the bank
            count). GATHER/BUY/DROP/CRAFT are never stock-limited by this
            model (you can always gather/buy/craft/fight again), so they
            carry the `UNBOUNDED_CAPACITY` sentinel.
    """

    kind: SourceKind
    code: str
    yield_per: int
    capacity: int


def obtain_sources(
    item: str, state: WorldState, game_data: GameData, ctx: SelectionContext
) -> list[Source]:
    """Every way `item` can be obtained from the current state, in the
    declared priority order (WITHDRAW, RECYCLE, CRAFT, GATHER, BUY, DROP).
    THE model — see the module docstring."""
    sources: list[Source] = []
    sources.extend(_withdraw_sources(item, state, ctx))
    sources.extend(_recycle_sources(item, state, game_data, ctx))
    sources.extend(_craft_sources(item, state, game_data))
    sources.extend(_gather_sources(item, game_data))
    sources.extend(_buy_sources(item, game_data))
    sources.extend(_drop_sources(item, state, game_data))
    return sources


def obtain_source_map(
    items: Iterable[str], state: WorldState, game_data: GameData, ctx: SelectionContext
) -> dict[str, list[Source]]:
    """`obtain_sources` over a whole closure of items, keyed by item code."""
    return {item: obtain_sources(item, state, game_data, ctx) for item in items}


def _withdraw_sources(
    item: str, state: WorldState, ctx: SelectionContext
) -> list[Source]:
    """A copy already sits in the bank AND the bank is currently reachable.

    `WithdrawItemAction.is_applicable` refuses unconditionally when
    `not self.accessible`, and every construction site in `factory.py`
    threads `accessible=ctx.bank_accessible`. `bank_accessible` is a
    persisted, level-gated blocker (`not blockers.is_blocked("bank")`) that
    stays False for the whole early game — and `state.bank_items` is
    populated regardless (the bank sync runs unconditionally), so without
    this gate a pre-unlock character would get a WITHDRAW source with no
    action in existence to serve it."""
    if not ctx.bank_accessible:
        return []
    bank = state.bank_items or {}
    stock = bank.get(item, 0)
    if stock > 0:
        return [Source(SourceKind.WITHDRAW, item, 1, stock)]
    return []


def _recycle_sources(
    item: str, state: WorldState, game_data: GameData, ctx: SelectionContext
) -> list[Source]:
    """Licensed surplus items (bag + bank) whose recipe consumes `item` —
    mirrors `recoverable_materials.recoverable_materials`'s gates exactly,
    per-source-item rather than aggregated into a material map."""
    out: list[Source] = []
    bank = state.bank_items or {}
    codes = sorted(set(state.inventory) | set(bank))
    for code in codes:
        recipe = game_data.crafting_recipe(code)
        if recipe is None or item not in recipe:
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
        yield_per = max(1, recipe[item] // 2)
        out.append(Source(SourceKind.RECYCLE, code, yield_per, copies * yield_per))
    return out


def _craft_sources(item: str, state: WorldState, game_data: GameData) -> list[Source]:
    """`item` has a recipe, the crafting-skill gate is met, and a workshop
    for that skill is known."""
    recipe = game_data.crafting_recipe(item)
    if recipe is None:
        return []
    stats = game_data.item_stats(item)
    if stats is None or not stats.crafting_skill:
        return []
    if state.skills.get(stats.crafting_skill, 1) < stats.crafting_level:
        return []
    if game_data.workshop_location(stats.crafting_skill) is None:
        return []
    return [Source(SourceKind.CRAFT, item, game_data.craft_yield(item), UNBOUNDED_CAPACITY)]


def _gather_sources(item: str, game_data: GameData) -> list[Source]:
    """Some resource drops `item`, and that resource has a currently-live
    gathering location.

    `GatherAction` is only CONSTRUCTED by `factory.py` from
    `game_data.all_resource_locations`, which merges an event resource's
    tiles ONLY while its event is active. Gating on the same mapping (rather
    than re-deriving event-liveness) keeps this in lockstep with what the
    executor can actually serve."""
    if item not in game_data.gatherable_drop_items():
        return []
    found = game_data.resource_for_drop(item)
    if found is None:  # pragma: no cover
        # `gatherable_drop_items` and `resource_for_drop` both derive from the
        # same `resource_drops` / `resource_drops_full` tables, so membership
        # in the former guarantees a hit in the latter. Kept as a guard (not
        # an assert) so a future data-source divergence degrades to "no
        # source" rather than crashing the model.
        return []
    resource_code, _rate = found
    if not game_data.all_resource_locations.get(resource_code):
        return []  # no live tiles (e.g. event resource, event inactive)
    return [Source(SourceKind.GATHER, resource_code, 1, UNBOUNDED_CAPACITY)]


def _buy_sources(item: str, game_data: GameData) -> list[Source]:
    """Permanent (non-event) NPC vendors, reachable, selling `item`."""
    out: list[Source] = []
    for npc_code, _price, _currency in game_data.npc_purchases(item):
        if game_data.is_event_npc(npc_code):
            continue  # not reliably reachable -> cannot anchor a plan
        if game_data.npc_location(npc_code) is None:
            continue
        out.append(Source(SourceKind.BUY, npc_code, 1, UNBOUNDED_CAPACITY))
    return out


def _drop_sources(item: str, state: WorldState, game_data: GameData) -> list[Source]:
    """Winnable monsters that drop `item` AND are currently reachable.

    `is_winnable` is a pure combat-stat prediction and says nothing about
    reachability. `FightAction` is only CONSTRUCTED by `factory.py` from
    `game_data.all_monster_locations`, which merges an event monster's tiles
    ONLY while its event is active — `monsters_dropping` reads a static
    content-drop catalog that is independent of event liveness. Gating on
    the same mapping factory.py builds from (rather than re-deriving
    event-liveness via `is_event_monster`) keeps this in lockstep with what
    the executor can actually serve."""
    out: list[Source] = []
    for monster_code, _rate, _min_q, _max_q in game_data.monsters_dropping(item):
        if not game_data.all_monster_locations.get(monster_code):
            continue  # no live tiles (e.g. event monster, event inactive)
        if is_winnable(state, game_data, monster_code):
            out.append(Source(SourceKind.DROP, monster_code, 1, UNBOUNDED_CAPACITY))
    return out
