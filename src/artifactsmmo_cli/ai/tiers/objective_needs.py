"""The committed objective's unmet NEEDS — a cheap, state-only statement of what
would actually move the objective forward. Drives the arbiter's worth gate
(means that serve no need are distractions). No planning.

See docs/superpowers/specs/2026-06-09-objective-committed-need-gated-arbitration-design.md
(Component 2).

Wave 3 of the requirement-model unification epic
(`docs/superpowers/specs/2026-07-19-requirement-model-unification-epic.md` §4.3):
this IS the `need_set` projection now — the closure walk comes from the shared
`RequirementGraph` (`requirement_closure`) instead of a private `recipe_closure`
call with two D-workarounds bolted on. The walk it replaced did three things the
one graph call now does directly:

  * translated RESOURCE-node codes to item codes (D1) via `resource_drop_item`;
  * added an `all_ingredients` ply to see buy-only leaves the two-set return was
    blind to (D2);
  * classified drop-only leaves through a separate resources loop.

The graph closure is already item-namespace and drop-aware, so all three fold
into one `requirement_closure`. Producibility classification (`_producible_by_self`)
and the skill/char semantics stay here unchanged — those read `WorldState` and are
NOT functions of the demand set (which is why §4.1's `NeedSet`-as-DemandSet-projection
framing was deferred to this wave). Output is behaviour-identical to the old walk;
the Wave 0 parity oracle staying green is the proof.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.requirement_projections import requirement_closure
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
)
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass(frozen=True)
class NeedSet:
    """Unmet needs of the committed objective."""
    materials: frozenset[str]   # closure items lacked (gatherable/craftable)
    skill_xp: frozenset[str]    # craft skills whose level gates the objective
    buy_only: frozenset[str]    # closure items obtainable ONLY by purchase
    char_xp: bool               # objective is / descends to a char-level gate

    @property
    def is_empty(self) -> bool:
        return not (self.materials or self.skill_xp or self.buy_only or self.char_xp)


def _owned(code: str, state: WorldState) -> int:
    bank = state.bank_items or {}
    equipped = sum(1 for c in state.equipment.values() if c == code)
    return state.inventory.get(code, 0) + bank.get(code, 0) + equipped


def _producible_by_self(code: str, game_data: GameData) -> bool:
    """Craftable (has a recipe), gatherable (some resource drops it — primary
    OR secondary; `_resource_drops` keeps only the primary, so the full drop
    tables must be consulted too, else a secondary-drop item is mis-read as
    purchase-only), or farmable (some monster drops it — run-17 2026-06-12:
    feather classified buy-only, distorting the worth gate, while FarmDrops
    can produce it from chickens)."""
    if game_data.crafting_recipe(code) is not None:
        return True
    if code in game_data.resource_drops.values():
        return True
    if any(item == code
           for table in game_data.resource_drops_full.values()
           for item, *_rest in table):
        return True
    if game_data.monsters_dropping(code):
        return True
    # NPC purchase with a self-producible currency (P3): tailor leathers for
    # hides, archaeologist items for shard/page drops, tasks_trader for coins.
    # One level deep — currencies are base items (gold handled by callers'
    # worth gates; task-earnable and drop/gather currencies count here).
    return any(
        game_data.is_task_earnable(currency)
        or currency in game_data.gatherable_drop_items()
        or bool(game_data.monsters_dropping(currency))
        for _npc, _price, currency in game_data.npc_purchases(code)
        if not game_data.is_event_npc(_npc) and game_data.npc_location(_npc) is not None)


def _add_skill_gate(code: str, state: WorldState, game_data: GameData,
                    skill_xp: set[str]) -> None:
    """Record `code`'s unmet crafting-skill gate, if any, into `skill_xp`."""
    stats = game_data.item_stats(code)
    if (stats is not None and stats.crafting_skill
            and stats.crafting_level > state.skills.get(stats.crafting_skill, 0)):
        skill_xp.add(stats.crafting_skill)


def objective_needs(root: MetaGoal, state: WorldState, game_data: GameData) -> NeedSet:
    """Unmet needs of `root`. Empty NeedSet when the objective is already met."""
    if isinstance(root, ReachCharLevel):
        return NeedSet(frozenset(), frozenset(), frozenset(),
                       char_xp=state.level < root.level)
    if isinstance(root, ObtainItem):
        if _owned(root.code, state) >= root.quantity:
            return NeedSet(frozenset(), frozenset(), frozenset(), char_xp=False)
        graph = game_data.requirement_graph.graph()
        materials: set[str] = set()
        skill_xp: set[str] = set()
        buy_only: set[str] = set()
        # ONE item-namespace, drop-aware closure replaces the old resource loop
        # + all_ingredients ply + resource->item translation (D1/D2 folded in).
        for item in requirement_closure(graph, [root.code]):
            if item == root.code:
                continue
            if _owned(item, state) >= 1:
                continue
            if _producible_by_self(item, game_data):
                materials.add(item)
            else:
                buy_only.add(item)
            # Skill gate only for CRAFTABLE closure items — the old code checked
            # skills solely in its craftables loop, never for ingredient leaves.
            if game_data.crafting_recipe(item) is not None:
                _add_skill_gate(item, state, game_data, skill_xp)
        _add_skill_gate(root.code, state, game_data, skill_xp)
        return NeedSet(frozenset(materials), frozenset(skill_xp),
                       frozenset(buy_only), char_xp=False)
    return NeedSet(frozenset(), frozenset(), frozenset(), char_xp=False)
