"""The committed objective's unmet NEEDS — a cheap, state-only statement of what
would actually move the objective forward. Drives the arbiter's worth gate
(means that serve no need are distractions). No planning.

See docs/superpowers/specs/2026-06-09-objective-committed-need-gated-arbitration-design.md
(Component 2).
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import recipe_closure
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


def objective_needs(root: MetaGoal, state: WorldState, game_data: GameData) -> NeedSet:
    """Unmet needs of `root`. Empty NeedSet when the objective is already met."""
    if isinstance(root, ReachCharLevel):
        return NeedSet(frozenset(), frozenset(), frozenset(),
                       char_xp=state.level < root.level)
    if isinstance(root, ObtainItem):
        if _owned(root.code, state) >= root.quantity:
            return NeedSet(frozenset(), frozenset(), frozenset(), char_xp=False)
        resources, craftables = recipe_closure(game_data, [root.code])
        nodes = set(craftables) | {root.code}
        materials: set[str] = set()
        skill_xp: set[str] = set()
        buy_only: set[str] = set()
        for res in resources:
            drop = game_data.resource_drop_item(res)
            if drop is not None and _owned(drop, state) < 1:
                materials.add(drop)
        # collect all recipe ingredients across every craftable node (including root)
        all_ingredients: set[str] = set()
        for node in nodes:
            recipe = game_data.crafting_recipe(node)
            if recipe:
                all_ingredients.update(recipe.keys())
        # process craftable sub-items (not root) for skill gates and material needs
        for node in nodes:
            if node == root.code:
                continue
            if _owned(node, state) >= 1:
                continue
            # `nodes` are recipe_closure craftables (all producible); buy-only
            # leaves are handled by the all_ingredients loop below, so this else
            # is unreachable here.
            if _producible_by_self(node, game_data):
                materials.add(node)
            else:  # pragma: no cover
                buy_only.add(node)
            stats = game_data.item_stats(node)
            if (stats is not None and stats.crafting_skill
                    and stats.crafting_level > state.skills.get(stats.crafting_skill, 0)):
                skill_xp.add(stats.crafting_skill)
        # Classify recipe-ingredient LEAVES not already handled by the closure
        # nodes loop: gatherable/craftable → a material need; otherwise → buy-only.
        for ingredient in all_ingredients:
            if ingredient in nodes:
                continue  # already handled above
            if _owned(ingredient, state) >= 1:
                continue
            if _producible_by_self(ingredient, game_data):
                materials.add(ingredient)
            else:
                buy_only.add(ingredient)
        root_stats = game_data.item_stats(root.code)
        if (root_stats is not None and root_stats.crafting_skill
                and root_stats.crafting_level > state.skills.get(root_stats.crafting_skill, 0)):
            skill_xp.add(root_stats.crafting_skill)
        return NeedSet(frozenset(materials), frozenset(skill_xp),
                       frozenset(buy_only), char_xp=False)
    return NeedSet(frozenset(), frozenset(), frozenset(), char_xp=False)
