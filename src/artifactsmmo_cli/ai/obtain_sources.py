"""THE model of how an item can be obtained — the one source of truth every
producer of a plan must consume — now a view of `ai/obtain_model`.

The bot has two plan producers: the GOAP action pool and `ai/craft_plan_gen`'s
recipe-tree chain builder. Every route beyond gather/craft/withdraw used to be
hand-bolted into the generator separately (578 lines of duplicated modeling),
which is why the recycle-as-acquisition epic shipped seven green commits that
were INERT: it taught the action pool about recycling, and the generator — which
answers first — could not express it. One pure function answering "how may I
obtain this item, right now?" for every consumer made that bug class
unrepresentable.

PHASE 1 STEP 3 of docs/PLAN_decision_architecture_redesign.md: this module no
longer holds the rules. `obtain_sources(item)` is `ObtainModel.ready(item,
Policy.LEGACY)` converted to `Source`s; the routes, the gates, the priority order
and the reason behind each eligibility rule live in
`ai/obtain_model/obtain_model.py`. Before the switch, a census compared this
module's own rules with the model over every item of real game data (44
scenario worlds with the bank open and locked, and all five live characters):
zero differences. The selection is kernel-proved
(`formal/Formal/ObtainModelReady.lean`).

REQUIREMENT-MODEL UNIFICATION EPIC — Wave 8, R3 deviation, still true: this walk
is STATE-AWARE (the sources ready RIGHT NOW), while `RequirementGraph.leaves` is
its STATE-FREE counterpart, and their relationship is asserted
(`tests/test_audit/test_obtain_graph_agreement.py`).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import LEGACY, Policy
from artifactsmmo_cli.ai.obtain_model.route import UNBOUNDED_CAPACITY as UNBOUNDED_CAPACITY
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.source_kind import SourceKind as SourceKind
from artifactsmmo_cli.ai.world_state import WorldState


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


def _sources(model: ObtainModel, item: str, policy: Policy = LEGACY) -> list[Source]:
    return [Source(route.kind, route.via, route.yield_per, route.capacity)
            for route in model.ready(item, policy)]


def obtain_sources(
    item: str, state: WorldState, game_data: GameData, ctx: SelectionContext,
    *, policy: Policy = LEGACY,
) -> list[Source]:
    """Every way `item` can be obtained from the current state, in the declared
    priority order (WITHDRAW, RECYCLE, CRAFT, GATHER, BUY, GE_FILL, DROP, SELL).
    `policy` is LEGACY, the executor's readiness, unless a caller prices under
    its own (the skill grind's ranking treats a gathering-skill gate as open)."""
    return _sources(ObtainModel(state, game_data, ctx, datetime.now(UTC)), item, policy)


def obtain_source_map(
    items: Iterable[str], state: WorldState, game_data: GameData, ctx: SelectionContext
) -> dict[str, list[Source]]:
    """`obtain_sources` over a whole closure of items, keyed by item code. One
    model serves every item, so routes shared along the closure are built once."""
    model = ObtainModel(state, game_data, ctx, datetime.now(UTC))
    return {item: _sources(model, item) for item in items}


def has_non_craft_source(
    item: str, state: WorldState, game_data: GameData, ctx: SelectionContext
) -> bool:
    """Is there a READY way to get `item` that is not crafting it?

    A withdraw, a licensed recycle, a live gather, a located permanent vendor,
    a fillable GE order, or a winnable drop — anything but CRAFT.

    THE QUESTION LIVES HERE, NOT AT THE CALL SITE, and that placement is the
    point rather than tidiness. Obligation O8 (wave-6 routes design §7) forbids
    a `Decision` from branching on a `SourceKind`: route kinds are the obtain
    model's vocabulary, and a decision that reads them has quietly grown a
    second opinion about routing. `decisions/obtain_item` needs the ANSWER —
    "is crafting the only way?", to decide whether a craft-skill gate is worth
    grinding for — so it asks this named predicate and the kinds stay in here.
    The O8 census caught the first version doing the comparison inline."""
    return any(source.kind is not SourceKind.CRAFT
               for source in obtain_sources(item, state, game_data, ctx))
