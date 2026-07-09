"""Grey-mob drop-farming policy: when may the planner fight a zero-xp monster?

FightAction's xpPositive gate (proven, Formal/ActionApplicability.lean) rejects
monsters >=10 levels below the character — correct for xp grinding, but it also
made mob-drop GATHERING impossible: live Robby (L12) could not hunt feathers
from chickens (L1) even though the server still drops loot from grey mobs, so
GatherMaterials(feather) was only servable from bank stock.

Policy (user directive 2026-07-06): grey farming is allowed IFF
  1. the drop SERVES A DEMAND — some crafting recipe consumes it, or it is
     the CURRENCY of an NPC purchase (Fight×N → NpcBuy chains, e.g.
     sandwhisper_coin @ sea_marauder buying greater_lifesteal_rune).
     Structural: only the demand-serving goals emit drop-farm fights —
     GatherMaterialsGoal for closure items under THIS policy, and (GAP-6,
     2026-07-08) UpgradeEquipmentGoal for its OWN equip target's dropper,
     where the demand gate holds structurally (the drop IS the goal's
     target) and this policy's next-tier suppression is deliberately not
     consulted (rationale on UpgradeEquipmentGoal._target_drop_fight: the
     tree's attainable-argmax already arbitrated the target against every
     craftable same-family alternative, and nothing arms a grind toward a
     not-yet-attainable one). A grey fight can never enter an xp-grind
     plan either way. AND
  2. the NEXT-TIER recipe of that recipe's family is too far a skill-grind
     away (or absent). When a same-family recipe just a few levels up exists
     (health_potion at alchemy 18 vs large_health_potion at 20), grinding the
     skill and crafting the better item beats farming greys for the obsolete
     one; when the next tier is a whole band away (satchel's next bag), the
     grey farm is the honest path.

"Family" is data-driven, never hardcoded item names: same `type_`, same
`subtype`, same `crafting_skill`, and a restorative recipe (hp_restore > 0)
only matches restorative candidates — so a boost potion two levels up does
not suppress farming for a health potion's materials.
"""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.world_state import WorldState

GREY_FARM_NEXT_TIER_MARGIN = 5
"""'Too far' threshold: the next-tier recipe suppresses grey farming only when
its crafting_level is within this many levels of the current skill (half a
10-level tier — close enough that grinding the skill is the better spend)."""


def _next_tier_level(recipe_item: ItemStats, game_data: GameData) -> int | None:
    """Smallest crafting_level strictly above `recipe_item`'s among craftable
    same-family items, or None when no higher tier exists."""
    levels = [
        stats.crafting_level
        for stats in game_data.all_item_stats.values()
        if stats.crafting_skill == recipe_item.crafting_skill
        and stats.type_ == recipe_item.type_
        and stats.subtype == recipe_item.subtype
        and stats.crafting_level > recipe_item.crafting_level
        and game_data.crafting_recipe(stats.code) is not None
        and (recipe_item.hp_restore <= 0 or stats.hp_restore > 0)
    ]
    return min(levels) if levels else None


def grey_farm_allowed(item_code: str, state: WorldState,
                      game_data: GameData) -> bool:
    """True when fighting a zero-xp dropper of `item_code` is worth it.

    Farm-worthy IFF the drop serves AT LEAST ONE crafting recipe whose next
    same-family tier is too far a skill-grind away (or absent) — i.e. some
    live, not-about-to-be-obsolete demand needs it. When EVERY consuming
    recipe has a near next tier, grinding the skill for the better item beats
    farming greys for the soon-obsolete one (the user's 2026-07-06 directive:
    health_potion vs large_health_potion two alchemy levels up).

    GAP-9 (2026-07-08): the old heuristic evaluated only the LOWEST-level
    consumer as "the reference recipe", so farming feather for a committed
    iron_boots (gearcrafting 10, next boot tier far — legitimately farmable)
    was wrongly suppressed because feather's globally-lowest consumer is an
    unrelated apprentice_gloves (gearcrafting 1, next tool tier close). The
    demand that armed the farm is a specific committed recipe, unknown to this
    policy (the goal step is ObtainItem(feather), the committed gear root is
    upstream) — so instead of guessing one reference, we allow when ANY
    consumer is non-obsolete. This is the honest reading of the directive
    across every recipe the drop serves."""
    consumers = [
        stats
        for stats in game_data.all_item_stats.values()
        if item_code in (game_data.crafting_recipe(stats.code) or {})
    ]
    if not consumers:
        # No recipe consumes it — but a drop that is the CURRENCY of an NPC
        # purchase serves a demand the same way (Fight×N → NpcBuy). There is
        # no recipe tier to grind toward instead, so it is farmable outright.
        purchase_currencies = {
            currency
            for per_item in game_data.world.npc_buy_currency.values()
            for currency in per_item.values()
        }
        return item_code in purchase_currencies
    for recipe_item in consumers:
        next_tier = _next_tier_level(recipe_item, game_data)
        if next_tier is None:
            return True
        skill = state.skills.get(recipe_item.crafting_skill or "", 0)
        if next_tier > skill + GREY_FARM_NEXT_TIER_MARGIN:
            return True
    return False
