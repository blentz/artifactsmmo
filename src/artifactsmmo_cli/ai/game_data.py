"""Static game knowledge cache loaded at startup.

`GameData` is the stable facade over four domain catalogs (items, monsters,
recipes/resources, world locations). All public names — including `ItemStats`
and `_GATHERING_SKILLS` re-exported here — keep their historical import path;
the catalogs own the state and domain queries, the facade owns the API-load
logic and delegates everything else.
"""

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from typing import Any

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.events.get_all_events_events_get import sync as get_all_events
from artifactsmmo_api_client.api.grand_exchange.get_ge_orders_grandexchange_orders_get import sync as get_ge_orders
from artifactsmmo_api_client.api.items.get_all_items_items_get import sync as get_all_items
from artifactsmmo_api_client.api.maps.get_all_maps_maps_get import sync as get_all_maps
from artifactsmmo_api_client.api.monsters.get_all_monsters_monsters_get import sync as get_all_monsters
from artifactsmmo_api_client.api.my_account.get_bank_details_my_bank_get import sync as get_bank_details
from artifactsmmo_api_client.api.np_cs.get_all_npcs_items_npcs_items_get import sync as get_all_npc_items
from artifactsmmo_api_client.api.resources.get_all_resources_resources_get import sync as get_all_resources
from artifactsmmo_api_client.models.bank_schema import BankSchema
from artifactsmmo_api_client.models.event_schema import EventSchema
from artifactsmmo_api_client.models.ge_order_type import GEOrderType
from artifactsmmo_api_client.models.item_schema import ItemSchema
from artifactsmmo_api_client.models.map_content_type import MapContentType
from artifactsmmo_api_client.models.map_layer import MapLayer
from artifactsmmo_api_client.models.map_schema import MapSchema
from artifactsmmo_api_client.models.monster_schema import MonsterSchema
from artifactsmmo_api_client.models.npc_item import NPCItem
from artifactsmmo_api_client.models.resource_schema import ResourceSchema
from artifactsmmo_api_client.types import Unset

from artifactsmmo_cli.ai.game_data_cache import GameDataCache
from artifactsmmo_cli.ai.item_catalog import _GATHERING_SKILLS, ItemCatalog, ItemStats
from artifactsmmo_cli.ai.location_catalog import LocationCatalog
from artifactsmmo_cli.ai.monster_catalog import MonsterCatalog
from artifactsmmo_cli.ai.recipe_catalog import RecipeCatalog

__all__ = ["_GATHERING_SKILLS", "GameData", "ItemStats"]


@dataclass
class GameData:
    """Static cache of game world knowledge. Load once at startup, never mutate."""

    items: ItemCatalog = field(default_factory=ItemCatalog)
    monsters: MonsterCatalog = field(default_factory=MonsterCatalog)
    recipes_catalog: RecipeCatalog = field(default_factory=RecipeCatalog)
    world: LocationCatalog = field(default_factory=LocationCatalog)

    # === Legacy private-state accessors ===
    # Tests and fixtures seed GameData through these historical private
    # names; each delegates to the owning catalog so in-place mutation
    # (`gd._item_stats[code] = ...`) and rebinding (`gd._item_stats = {...}`)
    # both keep working. Attrs never rebound anywhere are getter-only.

    @property
    def _monster_locations(self) -> dict[str, list[tuple[int, int]]]:
        return self.monsters.locations

    @_monster_locations.setter
    def _monster_locations(self, value: dict[str, list[tuple[int, int]]]) -> None:
        self.monsters.locations = value

    @property
    def _resource_locations(self) -> dict[str, list[tuple[int, int]]]:
        return self.recipes_catalog.locations

    @_resource_locations.setter
    def _resource_locations(self, value: dict[str, list[tuple[int, int]]]) -> None:
        self.recipes_catalog.locations = value

    @property
    def _workshop_locations(self) -> dict[str, tuple[int, int]]:
        return self.world.workshop_locations

    @_workshop_locations.setter
    def _workshop_locations(self, value: dict[str, tuple[int, int]]) -> None:
        self.world.workshop_locations = value

    @property
    def _bank_location(self) -> tuple[int, int] | None:
        return self.world.bank_tile

    @_bank_location.setter
    def _bank_location(self, value: tuple[int, int] | None) -> None:
        self.world.bank_tile = value

    @property
    def _bank_location_open(self) -> bool:
        return self.world.bank_tile_open

    @_bank_location_open.setter
    def _bank_location_open(self, value: bool) -> None:
        self.world.bank_tile_open = value

    @property
    def _taskmaster_location(self) -> tuple[int, int] | None:
        return self.world.taskmaster_tile

    @_taskmaster_location.setter
    def _taskmaster_location(self, value: tuple[int, int] | None) -> None:
        self.world.taskmaster_tile = value

    @property
    def _grand_exchange_location(self) -> tuple[int, int] | None:
        return self.world.grand_exchange_tile

    @_grand_exchange_location.setter
    def _grand_exchange_location(self, value: tuple[int, int] | None) -> None:
        self.world.grand_exchange_tile = value

    @property
    def _item_stats(self) -> dict[str, ItemStats]:
        return self.items.stats

    @_item_stats.setter
    def _item_stats(self, value: dict[str, ItemStats]) -> None:
        self.items.stats = value

    @property
    def _crafting_recipes(self) -> dict[str, dict[str, int]]:
        return self.recipes_catalog.crafting_recipes

    @_crafting_recipes.setter
    def _crafting_recipes(self, value: dict[str, dict[str, int]]) -> None:
        self.recipes_catalog.crafting_recipes = value

    @property
    def _resource_skill(self) -> dict[str, tuple[str, int]]:
        return self.recipes_catalog.resource_skill

    @_resource_skill.setter
    def _resource_skill(self, value: dict[str, tuple[str, int]]) -> None:
        self.recipes_catalog.resource_skill = value

    @property
    def _resource_drops(self) -> dict[str, str]:
        return self.recipes_catalog.resource_drops

    @_resource_drops.setter
    def _resource_drops(self, value: dict[str, str]) -> None:
        self.recipes_catalog.resource_drops = value

    @property
    def _resource_drops_full(self) -> dict[str, list[tuple[str, int, int, int]]]:
        return self.recipes_catalog.resource_drops_full

    @_resource_drops_full.setter
    def _resource_drops_full(self, value: dict[str, list[tuple[str, int, int, int]]]) -> None:
        self.recipes_catalog.resource_drops_full = value

    @property
    def _monster_level(self) -> dict[str, int]:
        return self.monsters.levels

    @_monster_level.setter
    def _monster_level(self, value: dict[str, int]) -> None:
        self.monsters.levels = value

    @property
    def _monster_hp(self) -> dict[str, int]:
        return self.monsters.hp

    @_monster_hp.setter
    def _monster_hp(self, value: dict[str, int]) -> None:
        self.monsters.hp = value

    @property
    def _monster_type(self) -> dict[str, str]:
        return self.monsters.types

    @_monster_type.setter
    def _monster_type(self, value: dict[str, str]) -> None:
        self.monsters.types = value

    @property
    def _monster_attack(self) -> dict[str, dict[str, int]]:
        return self.monsters.attack

    @_monster_attack.setter
    def _monster_attack(self, value: dict[str, dict[str, int]]) -> None:
        self.monsters.attack = value

    @property
    def _monster_resistance(self) -> dict[str, dict[str, int]]:
        return self.monsters.resistance

    @_monster_resistance.setter
    def _monster_resistance(self, value: dict[str, dict[str, int]]) -> None:
        self.monsters.resistance = value

    @property
    def _monster_critical_strike(self) -> dict[str, int]:
        return self.monsters.critical_strike

    @_monster_critical_strike.setter
    def _monster_critical_strike(self, value: dict[str, int]) -> None:
        self.monsters.critical_strike = value

    @property
    def _monster_lifesteal(self) -> dict[str, int]:
        return self.monsters.lifesteal

    @_monster_lifesteal.setter
    def _monster_lifesteal(self, value: dict[str, int]) -> None:
        self.monsters.lifesteal = value

    @property
    def _monster_poison(self) -> dict[str, int]:
        return self.monsters.poison

    @_monster_poison.setter
    def _monster_poison(self, value: dict[str, int]) -> None:
        self.monsters.poison = value

    @property
    def _monster_barrier(self) -> dict[str, int]:
        return self.monsters.barrier

    @_monster_barrier.setter
    def _monster_barrier(self, value: dict[str, int]) -> None:
        self.monsters.barrier = value

    @property
    def _monster_burn(self) -> dict[str, int]:
        return self.monsters.burn

    @_monster_burn.setter
    def _monster_burn(self, value: dict[str, int]) -> None:
        self.monsters.burn = value

    @property
    def _monster_healing(self) -> dict[str, int]:
        return self.monsters.healing

    @_monster_healing.setter
    def _monster_healing(self, value: dict[str, int]) -> None:
        self.monsters.healing = value

    @property
    def _monster_reconstitution(self) -> dict[str, int]:
        return self.monsters.reconstitution

    @_monster_reconstitution.setter
    def _monster_reconstitution(self, value: dict[str, int]) -> None:
        self.monsters.reconstitution = value

    @property
    def _monster_void_drain(self) -> dict[str, int]:
        return self.monsters.void_drain

    @_monster_void_drain.setter
    def _monster_void_drain(self, value: dict[str, int]) -> None:
        self.monsters.void_drain = value

    @property
    def _monster_berserker_rage(self) -> dict[str, int]:
        return self.monsters.berserker_rage

    @_monster_berserker_rage.setter
    def _monster_berserker_rage(self, value: dict[str, int]) -> None:
        self.monsters.berserker_rage = value

    @property
    def _monster_frenzy(self) -> dict[str, int]:
        return self.monsters.frenzy

    @_monster_frenzy.setter
    def _monster_frenzy(self, value: dict[str, int]) -> None:
        self.monsters.frenzy = value

    @property
    def _monster_protective_bubble(self) -> dict[str, int]:
        return self.monsters.protective_bubble

    @_monster_protective_bubble.setter
    def _monster_protective_bubble(self, value: dict[str, int]) -> None:
        self.monsters.protective_bubble = value

    @property
    def _monster_corrupted(self) -> dict[str, int]:
        return self.monsters.corrupted

    @_monster_corrupted.setter
    def _monster_corrupted(self, value: dict[str, int]) -> None:
        self.monsters.corrupted = value

    @property
    def _monster_initiative(self) -> dict[str, int]:
        return self.monsters.initiative

    @_monster_initiative.setter
    def _monster_initiative(self, value: dict[str, int]) -> None:
        self.monsters.initiative = value

    @property
    def _monster_drops(self) -> dict[str, list[tuple[str, int, int, int]]]:
        return self.monsters.drops

    @_monster_drops.setter
    def _monster_drops(self, value: dict[str, list[tuple[str, int, int, int]]]) -> None:
        self.monsters.drops = value

    @property
    def _monster_min_gold(self) -> dict[str, int]:
        return self.monsters.min_gold

    @property
    def _monster_max_gold(self) -> dict[str, int]:
        return self.monsters.max_gold

    @property
    def _npc_locations(self) -> dict[str, tuple[int, int]]:
        return self.world.npc_tiles

    @_npc_locations.setter
    def _npc_locations(self, value: dict[str, tuple[int, int]]) -> None:
        self.world.npc_tiles = value

    @property
    def _npc_stock(self) -> dict[str, dict[str, int]]:
        return self.world.npc_stock

    @_npc_stock.setter
    def _npc_stock(self, value: dict[str, dict[str, int]]) -> None:
        self.world.npc_stock = value

    @property
    def _npc_sell_prices(self) -> dict[str, dict[str, int]]:
        return self.world.npc_sell_prices

    @_npc_sell_prices.setter
    def _npc_sell_prices(self, value: dict[str, dict[str, int]]) -> None:
        self.world.npc_sell_prices = value

    @property
    def _ge_buy_orders(self) -> dict[str, tuple[str, int, int]]:
        return self.world.ge_buy_orders

    @_ge_buy_orders.setter
    def _ge_buy_orders(self, value: dict[str, tuple[str, int, int]]) -> None:
        self.world.ge_buy_orders = value

    @property
    def _ge_sell_orders(self) -> dict[str, tuple[str, int, int]]:
        return self.world.ge_sell_orders

    @_ge_sell_orders.setter
    def _ge_sell_orders(self, value: dict[str, tuple[str, int, int]]) -> None:
        self.world.ge_sell_orders = value

    @property
    def _event_npc_spawns(self) -> dict[str, tuple[int, int]]:
        return self.world.event_npc_spawns

    @property
    def _npc_event_code(self) -> dict[str, str]:
        return self.world.npc_event_codes

    @property
    def _bank_capacity(self) -> int:
        return self.world.bank_capacity

    @_bank_capacity.setter
    def _bank_capacity(self, value: int) -> None:
        self.world.bank_capacity = value

    @property
    def _next_expansion_cost(self) -> int:
        return self.world.next_expansion_cost

    @_next_expansion_cost.setter
    def _next_expansion_cost(self, value: int) -> None:
        self.world.next_expansion_cost = value

    @property
    def _transition_tiles(self) -> set[tuple[int, int]]:
        return self.world.transition_tiles

    @_transition_tiles.setter
    def _transition_tiles(self, value: set[tuple[int, int]]) -> None:
        self.world.transition_tiles = value

    @property
    def _known_tiles(self) -> set[tuple[int, int]]:
        return self.world.known_tiles

    @_known_tiles.setter
    def _known_tiles(self, value: set[tuple[int, int]]) -> None:
        self.world.known_tiles = value

    # === Public query API (delegates to the domain catalogs) ===

    def monster_locations(self, code: str) -> list[tuple[int, int]]:
        """Tiles where a monster spawns."""
        return self.monsters.monster_locations(code)

    def resource_locations(self, code: str) -> list[tuple[int, int]]:
        """Tiles where a resource appears."""
        return self.recipes_catalog.resource_locations(code)

    def workshop_location(self, skill: str) -> tuple[int, int] | None:
        """Location of the workshop for a crafting skill."""
        return self.world.workshop_location(skill)

    def bank_location(self) -> tuple[int, int]:
        """Location of the bank."""
        return self.world.bank_location()

    def has_open_bank(self) -> bool:
        """True when the resolved bank is unconditionally accessible (no
        achievement gate). Used to drop a stale global bank-lock blocker."""
        return self.world.has_open_bank()

    def teleport_destination(self, item_code: str) -> tuple[int, int] | None:
        """Destination tile of a teleport consumable (PLAN #6b), or None when the
        item is not a teleport item OR its destination map is not in the loaded
        overworld set. The item's `teleport` effect value is a MapSchema.map_id;
        resolve it to coordinates via the map_id index."""
        stats = self.item_stats(item_code)
        if stats is None or stats.teleport_map_id <= 0:
            return None
        return self.world.map_location_by_id(stats.teleport_map_id)

    @staticmethod
    def _bank_tile_open(tile: object) -> bool:
        """True when a bank tile has no access conditions (open to everyone)."""
        access = getattr(tile, "access", None)
        if access is None or isinstance(access, Unset):
            return True
        conditions = getattr(access, "conditions", None)
        if conditions is None or isinstance(conditions, Unset):
            return True
        return len(conditions) == 0

    def taskmaster_location(self) -> tuple[int, int]:
        """Location of the tasks master NPC."""
        return self.world.taskmaster_location()

    def item_stats(self, code: str) -> ItemStats | None:
        """Stats for an item."""
        return self.items.item_stats(code)

    def max_recipe_demand(self, item_code: str) -> int:
        """Largest TRANSITIVE quantity of `item_code` consumed to produce any
        single end-item, recursively across the crafting chain. Used by the
        overstock cap: anything beyond this (plus a batch buffer) is dead
        weight in the inventory. Returns 0 when no recipe uses the item.
        Full worked example on `RecipeCatalog.max_recipe_demand`.
        """
        return self.recipes_catalog.max_recipe_demand(item_code)

    def crafting_recipe(self, code: str) -> dict[str, int] | None:
        """Materials needed to craft an item, or None if not craftable."""
        return self.recipes_catalog.crafting_recipe(code)

    def resource_skill_level(self, code: str) -> tuple[str, int] | None:
        """Skill and level required to gather a resource."""
        return self.recipes_catalog.resource_skill_level(code)

    def resource_drop_item(self, code: str) -> str | None:
        """Primary item dropped when gathering this resource (for planning simulation)."""
        return self.recipes_catalog.resource_drop_item(code)

    def resource_drop_table(self, code: str) -> list[tuple[str, int, int, int]]:
        """Full (item, rate, min_q, max_q) drop rows for a resource; [] if unknown."""
        return self.recipes_catalog.resource_drop_table(code)

    MAX_CHARACTER_LEVEL = 50
    """Documented character level cap.
    Source: https://docs.artifactsmmo.com/concepts/stats_and_fights/ —
    "Characters progress through 50 levels...level 50 being the maximum."
    Note: monster levels above 50 exist (event/boss monsters); the
    PROGRESSION cap is 50.
    """

    @property
    def max_character_level(self) -> int:
        """Documented character-level cap. Constant from official docs."""
        return self.MAX_CHARACTER_LEVEL

    MAX_SKILL_LEVEL = 50
    """Documented skill level cap.
    Source: https://docs.artifactsmmo.com/concepts/skills —
    "Your characters have 8 skills that can gain XP and reach up to level 50."
    Equals the character-level cap.
    """

    @property
    def max_skill_level(self) -> int:
        """Documented per-skill level cap. Constant from official docs."""
        return self.MAX_SKILL_LEVEL

    def xp_per_kill(self, monster_code: str, char_level: int, wisdom: int = 0) -> int:
        """Compute documented XP gained from killing `monster_code`.

        Returns 0 if monster is unknown (no level on file). Formula and
        sources documented on `MonsterCatalog.xp_per_kill`.
        """
        return self.monsters.xp_per_kill(monster_code, char_level, wisdom)

    def monster_attack(self, code: str) -> dict[str, int]:
        """{element: attack_value} for the monster. Raises `KeyError` when the
        monster is unknown — CLAUDE.md "use only API data or fail with an error":
        rationale on `MonsterCatalog.monster_attack`."""
        return self.monsters.monster_attack(code)

    def monster_resistance(self, code: str) -> dict[str, int]:
        """{element: resistance_pct} for the monster. Raises `KeyError` when
        unknown — see `monster_attack` for rationale."""
        return self.monsters.monster_resistance(code)

    def monster_hp(self, code: str) -> int:
        """Max HP of a monster. Raises `KeyError` when unknown — silent zero
        would make `rounds_to_kill = ceil(0 / player_hit) = 0`, defeating the
        beatability verdict."""
        return self.monsters.monster_hp(code)

    def monster_critical_strike(self, code: str) -> int:
        """Critical-strike chance % of a monster. Raises `KeyError` when
        unknown — see `monster_attack`."""
        return self.monsters.monster_critical_strike(code)

    def monster_lifesteal(self, code: str) -> int:
        """Heal-on-crit % of a monster (optional `lifesteal` effect; 0 if absent).
        Feeds predict_win: a lifesteal monster sustains itself, lowering our net
        kill rate."""
        return self.monsters.monster_lifesteal(code)

    def monster_poison(self, code: str) -> int:
        """Flat per-turn poison DoT of a monster (optional `poison` effect; 0 if
        absent). Feeds predict_win: poison raises our net death rate every turn,
        even when the monster deals no direct damage."""
        return self.monsters.monster_poison(code)

    def monster_barrier(self, code: str) -> int:
        """Absorbing-shield HP of a monster (optional `barrier` effect; 0 if
        absent). Feeds predict_win: barrier raises the monster's effective HP, so
        the player needs more rounds to kill it."""
        return self.monsters.monster_barrier(code)

    def monster_burn(self, code: str) -> int:
        """Burn DoT percent (of player attack) of a monster (optional `burn`
        effect; 0 if absent). Feeds predict_win: burn raises the player's net death
        rate each turn (modeled conservatively as flat, no decay)."""
        return self.monsters.monster_burn(code)

    def monster_healing(self, code: str) -> int:
        """Regen percent (of the monster's HP) of a monster (optional `healing`
        effect; 0 if absent). Feeds predict_win: healing lowers our net kill rate
        (subtracted from kill_step; an un-out-damageable healer is unkillable)."""
        return self.monsters.monster_healing(code)

    def monster_reconstitution(self, code: str) -> int:
        """Full-heal period in turns of a monster (optional `reconstitution`
        effect; 0 if absent). Feeds predict_win: if we can't kill the monster
        faster than this period, it fully heals before dying ⇒ unwinnable."""
        return self.monsters.monster_reconstitution(code)

    def monster_void_drain(self, code: str) -> int:
        """Void-drain percent (of player HP) of a monster (optional `void_drain`
        effect; 0 if absent). Feeds predict_win: it BOTH raises the player's death
        rate (drain) and lowers our kill rate (the monster heals by the drain)."""
        return self.monsters.monster_void_drain(code)

    def monster_berserker_rage(self, code: str) -> int:
        """Berserker-rage damage-boost percent of a monster (optional
        `berserker_rage` effect; 0 if absent). Feeds predict_win: modeled as an
        always-active monster damage boost (raises the player's death rate)."""
        return self.monsters.monster_berserker_rage(code)

    def monster_frenzy(self, code: str) -> int:
        """Frenzy damage-boost percent of a monster (optional `frenzy` effect; 0 if
        absent). Feeds predict_win: modeled as an always-active monster damage boost
        (raises the player's death rate)."""
        return self.monsters.monster_frenzy(code)

    def monster_protective_bubble(self, code: str) -> int:
        """Protective-bubble resistance percent of a monster (optional
        `protective_bubble` effect; 0 if absent). Feeds predict_win: modeled as an
        always-on player-damage reduction (lowers our kill rate)."""
        return self.monsters.monster_protective_bubble(code)

    def monster_corrupted(self, code: str) -> int:
        """Per-hit resistance-reduction percent of a monster (optional `corrupted`
        effect; 0 if absent). corrupted HELPS the player, so predict_win conservatively
        does NOT credit it (models pre-corruption minimum damage). Parsed/covered, not
        used by the win prediction — see monster_catalog.monster_corrupted."""
        return self.monsters.monster_corrupted(code)

    def monster_initiative(self, code: str) -> int:
        """Initiative (turn-order) stat of a monster. Raises `KeyError` when
        unknown — see `monster_attack`."""
        return self.monsters.monster_initiative(code)

    def monster_drops(self, code: str) -> list[tuple[str, int, int, int]]:
        """OpenAPI conformance (Item 14): drop table from a monster fight.
        Returns [(item_code, rate, min_quantity, max_quantity), ...]; empty list
        if no drops known or monster missing. Rate is 1-in-N (smaller = more
        common per server convention)."""
        return self.monsters.monster_drops(code)

    def monsters_dropping(self, item: str) -> list[tuple[str, int, int, int]]:
        """Every monster whose drop table contains `item`, as
        [(monster_code, rate, min_quantity, max_quantity), ...] in catalog
        order. Empty when nothing drops the item. Used by drop-driven monster
        selection (pick the monster minimizing expected kills for a needed
        drop)."""
        return self.monsters.monsters_dropping(item)

    def monster_min_gold(self, code: str) -> int:
        """OpenAPI conformance (Item 14): minimum gold reward per fight win.
        Returns 0 if unknown."""
        return self.monsters.monster_min_gold(code)

    def monster_max_gold(self, code: str) -> int:
        """OpenAPI conformance (Item 14): maximum gold reward per fight win.
        Returns 0 if unknown."""
        return self.monsters.monster_max_gold(code)

    def monster_level(self, code: str) -> int:
        """Level of a monster, or 0 when unknown.

        Invariant-OK silent default: rationale on `MonsterCatalog.monster_level`
        (callers treat 0 as a documented "not a known monster" probe)."""
        return self.monsters.monster_level(code)

    def best_consumable(self, inventory: dict[str, int]) -> tuple[str, int] | None:
        """Return (item_code, hp_restore) for the highest-restore consumable in inventory, or None."""
        return self.items.best_consumable(inventory)

    def active_gathering_skills(
        self, task_code: str | None, crafting_target: str | None = None
    ) -> set[str]:
        """Gathering skills involved in producing task_code AND the bot's current
        self-directed crafting target (walking each item's recipe tree).
        Worked example on `RecipeCatalog.active_gathering_skills`.
        """
        return self.recipes_catalog.active_gathering_skills(task_code, crafting_target)

    def npc_location(self, npc_code: str) -> tuple[int, int] | None:
        """Location of a named NPC: static map scan first, then event spawn tile."""
        return self.world.npc_location(npc_code)

    def is_event_npc(self, npc_code: str) -> bool:
        """True if this NPC only exists during a timed event window."""
        return self.world.is_event_npc(npc_code)

    def npc_event_code(self, npc_code: str) -> str | None:
        """Event code whose active window spawns this NPC, or None if not an event NPC."""
        return self.world.npc_event_code(npc_code)

    def npc_sells_item(self, npc_code: str, item_code: str) -> int | None:
        """Buy price of item_code from npc_code, or None if the NPC doesn't sell it."""
        return self.world.npc_sells_item(npc_code, item_code)

    def npcs_selling_item(self, item_code: str) -> list[tuple[str, int]]:
        """Return [(npc_code, price)] for all NPCs that sell item_code, cheapest first."""
        return self.world.npcs_selling_item(item_code)

    def npc_buys_item(self, npc_code: str, item_code: str) -> int | None:
        """Price npc_code pays for item_code when the player sells it, or None if the NPC doesn't buy it."""
        return self.world.npc_buys_item(npc_code, item_code)

    def npcs_buying_item(self, item_code: str) -> list[tuple[str, int]]:
        """Return [(npc_code, price)] for all NPCs that buy item_code from the player, highest price first."""
        return self.world.npcs_buying_item(item_code)

    def ge_best_buy_order(self, item_code: str) -> tuple[str, int, int] | None:
        """The highest-price OPEN BUY order for item_code as (order_id, price,
        quantity), or None if no such standing order exists. This is the order the
        player fills by selling into it (immediate gold). Only API-sourced orders
        appear here; absence is encoded as None (the anti-surrogate guard for
        liquidation_venue)."""
        return self.world.ge_best_buy_order(item_code)

    def ge_best_sell_order(self, item_code: str) -> tuple[str, int, int] | None:
        """The lowest-price OPEN SELL order for item_code as (order_id, price,
        quantity), or None if no such standing order exists. This is the cheapest
        order the player fills by BUYING from it (immediate acquisition). It is the
        DUAL of `ge_best_buy_order`: buying minimizes price, liquidating maximizes
        it. Only API-sourced orders appear here; absence is encoded as None (the
        anti-surrogate guard for buy_source_venue)."""
        return self.world.ge_best_sell_order(item_code)

    def grand_exchange_location(self) -> tuple[int, int] | None:
        """Tile of the Grand Exchange, or None if the map has no GE."""
        return self.world.grand_exchange_location()

    def nearest_location(self, x: int, y: int, locations: list[tuple[int, int]]) -> tuple[int, int] | None:
        """Find the nearest location to (x, y) by Manhattan distance."""
        return self.world.nearest_location(x, y, locations)

    # === Whole-mapping read-only views ===
    # External code that iterates, membership-tests, or passes a whole index
    # to a pure helper reads it through these properties instead of touching
    # the private fields. Each returns the underlying mapping unchanged
    # (bracket access still raises KeyError on a miss) typed as a read-only
    # Mapping/Set view.

    @property
    def crafting_recipes(self) -> Mapping[str, dict[str, int]]:
        """item_code -> {material: quantity} for every craftable item."""
        return self.recipes_catalog.crafting_recipes

    @property
    def resource_drops(self) -> Mapping[str, str]:
        """resource_code -> primary drop item."""
        return self.recipes_catalog.resource_drops

    @property
    def resource_drops_full(self) -> Mapping[str, list[tuple[str, int, int, int]]]:
        """resource_code -> full (item, rate, min_q, max_q) drop table."""
        return self.recipes_catalog.resource_drops_full

    @property
    def monster_levels(self) -> Mapping[str, int]:
        """monster_code -> level for every known monster."""
        return self.monsters.levels

    @property
    def all_item_stats(self) -> Mapping[str, ItemStats]:
        """item_code -> ItemStats for every known item."""
        return self.items.stats

    @property
    def all_monster_locations(self) -> Mapping[str, list[tuple[int, int]]]:
        """monster_code -> spawn tiles for every known monster."""
        return self.monsters.locations

    @property
    def all_resource_locations(self) -> Mapping[str, list[tuple[int, int]]]:
        """resource_code -> tiles for every known resource."""
        return self.recipes_catalog.locations

    @property
    def workshop_locations(self) -> Mapping[str, tuple[int, int]]:
        """crafting skill -> workshop tile."""
        return self.world.workshop_locations

    @property
    def npc_locations(self) -> Mapping[str, tuple[int, int]]:
        """npc_code -> static map tile (event spawns live elsewhere)."""
        return self.world.npc_tiles

    @property
    def npc_stock(self) -> Mapping[str, dict[str, int]]:
        """npc_code -> {item_code: buy_price} for items the NPC sells."""
        return self.world.npc_stock

    @property
    def npc_sell_prices(self) -> Mapping[str, dict[str, int]]:
        """npc_code -> {item_code: sell_price} the NPC pays the player."""
        return self.world.npc_sell_prices

    @property
    def resource_skills(self) -> Mapping[str, tuple[str, int]]:
        """resource_code -> (skill, level) gathering requirement."""
        return self.recipes_catalog.resource_skill

    @property
    def transition_tiles(self) -> AbstractSet[tuple[int, int]]:
        """Overworld tiles with a map-layer transition (doors)."""
        return self.world.transition_tiles

    @property
    def known_tiles(self) -> AbstractSet[tuple[int, int]]:
        """Every overworld tile that exists, content or not."""
        return self.world.known_tiles

    @property
    def bank_capacity(self) -> int:
        """Bank slot capacity as of the startup snapshot."""
        return self.world.bank_capacity

    @property
    def next_expansion_cost(self) -> int:
        """Gold cost of the next bank expansion."""
        return self.world.next_expansion_cost

    @property
    def bank_location_or_none(self) -> tuple[int, int] | None:
        """Bank tile, or None when the map has no bank (display-safe
        counterpart to the raising `bank_location()`)."""
        return self.world.bank_tile

    @property
    def taskmaster_location_or_none(self) -> tuple[int, int] | None:
        """Tasks-master tile, or None when unknown (display-safe counterpart
        to the raising `taskmaster_location()`)."""
        return self.world.taskmaster_tile

    @classmethod
    def load(
        cls,
        client: AuthenticatedClient,
        ttl_minutes: int = 30,
        force_refresh: bool = False,
        cache: "GameDataCache | None" = None,
    ) -> "GameData":
        """Build GameData. Reuse the disk cache for the STATIC loaders when fresh
        (< ttl_minutes); else fetch from the API and rewrite it. GE orders are
        ALWAYS fetched live (the market order book changes constantly).

        _fetch_* return schema OBJECTS; the cache stores their .to_dict()s; a warm
        load reconstructs schemas via .from_dict(). _build_* always sees schema
        objects, so its logic (and the legacy _load_* tests) are unchanged."""
        data = cls()
        if cache is None:
            cache = GameDataCache(api_base_url=client._base_url)
        raw = None if force_refresh else cache.read(ttl_minutes)
        # Heterogeneous string-keyed bundle of schema objects (lists per page, plus
        # the lone bank schema or None); the same shape the cache round-trips as
        # JSON, so its values are genuinely per-key heterogeneous -> Any.
        objs: dict[str, Any]
        if raw is None:
            fetched: dict[str, Any] = {
                "maps": data._fetch_maps(client),
                "items": data._fetch_items(client),
                "resources": data._fetch_resources(client),
                "monsters": data._fetch_monsters(client),
                "npcs": data._fetch_npcs(client),
                "events": data._fetch_events(client),
                "bank": data._fetch_bank(client),
            }
            raw = {
                k: (
                    [o.to_dict() for o in v]
                    if isinstance(v, list)
                    else (v.to_dict() if v is not None else None)
                )
                for k, v in fetched.items()
            }
            try:
                cache.write(raw)
            except OSError as e:
                # Data is already in hand; a failed cache write must not crash the
                # run — the next start simply re-fetches.
                print(f"[game_data] cache write failed: {e}")
            objs = fetched
        else:
            objs = {
                "maps": [MapSchema.from_dict(d) for d in raw["maps"]],
                "items": [ItemSchema.from_dict(d) for d in raw["items"]],
                "resources": [ResourceSchema.from_dict(d) for d in raw["resources"]],
                "monsters": [MonsterSchema.from_dict(d) for d in raw["monsters"]],
                "npcs": [NPCItem.from_dict(d) for d in raw["npcs"]],
                "events": [EventSchema.from_dict(d) for d in raw["events"]],
                "bank": BankSchema.from_dict(raw["bank"]) if raw["bank"] is not None else None,
            }
        data._build_maps(objs["maps"])
        data._build_items(objs["items"])
        data._build_resources(objs["resources"])
        data._build_monsters(objs["monsters"])
        data._build_npcs(objs["npcs"])
        data._build_events(objs["events"])
        data._build_bank(objs["bank"])
        data._load_ge_orders(client)
        return data

    def _fetch_bank(self, client: AuthenticatedClient) -> BankSchema | None:
        """Fetch the single bank-details schema object, or None when absent."""
        result = get_bank_details(client=client)
        if result is None or not hasattr(result, "data") or result.data is None:
            return None
        return result.data

    def _build_bank(self, item: BankSchema | None) -> None:
        """Set bank capacity and next expansion cost from the bank schema object."""
        if item is None:
            return
        self._bank_capacity = item.slots
        self._next_expansion_cost = item.next_expansion_cost

    def _load_bank_metadata(self, client: AuthenticatedClient) -> None:
        """Fetch bank capacity and next expansion cost."""
        self._build_bank(self._fetch_bank(client))

    def _fetch_maps(self, client: AuthenticatedClient) -> list[MapSchema]:
        """Page all overworld map tiles; return the list of schema objects."""
        out: list[MapSchema] = []
        page = 1
        while True:
            result = get_all_maps(client=client, layer=MapLayer.OVERWORLD, page=page, size=100)
            if result is None or not result.data:
                break
            out.extend(result.data)
            if len(result.data) < 100:
                break
            page += 1
        return out

    def _build_maps(self, tiles: list[MapSchema]) -> None:
        """Build content location indexes from map tile schema objects."""
        for tile in tiles:
            loc = (tile.x, tile.y)
            self._known_tiles.add(loc)
            self.world.map_id_to_loc[tile.map_id] = loc  # teleport destinations resolve map_id -> coords

            transition = tile.interactions.transition
            if not isinstance(transition, Unset) and transition is not None:
                self._transition_tiles.add(loc)

            content = tile.interactions.content
            if isinstance(content, Unset) or content is None:
                continue

            ct = content.type_
            code = content.code

            if ct == MapContentType.MONSTER:
                self._monster_locations.setdefault(code, []).append(loc)
            elif ct == MapContentType.RESOURCE:
                self._resource_locations.setdefault(code, []).append(loc)
            elif ct == MapContentType.BANK:
                # Prefer an OPEN bank. Some banks are achievement-gated
                # (e.g. the desert-island bank needs `secure_the_island`);
                # moving to one returns HTTP 496 and the bot wrongly records
                # a global "bank locked" blocker. Latch onto an unconditional
                # bank and only fall back to a gated one if none is open.
                if self._bank_tile_open(tile):
                    self._bank_location = loc
                    self._bank_location_open = True
                elif not self._bank_location_open:
                    self._bank_location = loc
            elif ct == MapContentType.TASKS_MASTER:
                self._taskmaster_location = loc
            elif ct == MapContentType.GRAND_EXCHANGE:
                self._grand_exchange_location = loc
            elif ct == MapContentType.NPC:
                self._npc_locations[code] = loc
            elif ct == MapContentType.WORKSHOP:
                # code is workshop identifier — match to crafting skills by substring
                for skill in ("mining", "woodcutting", "weaponcrafting", "gearcrafting",
                              "jewelrycrafting", "cooking", "alchemy", "fishing"):
                    if skill in code:
                        self._workshop_locations[skill] = loc
                        break

    def _load_maps(self, client: AuthenticatedClient) -> None:
        """Fetch all map tiles and build content location indexes."""
        self._build_maps(self._fetch_maps(client))

    def _fetch_items(self, client: AuthenticatedClient) -> list[ItemSchema]:
        """Page all items; return the list of schema objects."""
        out: list[ItemSchema] = []
        page = 1
        while True:
            result = get_all_items(client=client, page=page, size=100)
            if result is None or not result.data:
                break
            out.extend(result.data)
            if len(result.data) < 100:
                break
            page += 1
        return out

    def _build_items(self, items: list[ItemSchema]) -> None:
        """Build stats + recipe indexes from item schema objects."""
        for item in items:
            stats = ItemStats(code=item.code, level=item.level, type_=item.type_)
            self._item_stats[item.code] = stats
            # OpenAPI conformance fields (Item 14 remediation).
            # tradeable: server is authoritative; defensive
            # `getattr` with default True preserves legacy behavior
            # when an older client lacks the field.
            stats.tradeable = bool(getattr(item, "tradeable", True))
            subtype = getattr(item, "subtype", "")
            if isinstance(subtype, Unset):
                subtype = ""
            stats.subtype = str(subtype or "")
            raw_conditions = getattr(item, "conditions", None)
            if raw_conditions is not None and not isinstance(raw_conditions, Unset):
                for cond in raw_conditions:
                    code = getattr(cond, "code", None)
                    value = getattr(cond, "value", None)
                    if code is not None and value is not None:
                        stats.conditions.append((str(code), int(value)))

            if not isinstance(item.effects, Unset) and item.effects:
                for effect in item.effects:
                    if effect.code in ("heal", "restore", "splash_restore"):
                        # The HP-restoration family: `heal` (cooked food), `restore`
                        # (potions, e.g. enchanted_health_potion=300), `splash_restore`
                        # (splash potions). All restore HP on use → one hp_restore field
                        # so the consumable picker ranks them together. `boost_hp` is
                        # deliberately excluded — "boost" is a temporary max-HP buff, not
                        # an instant restore (see docs/PLAN_consumable_effects.md).
                        stats.hp_restore = effect.value
                    elif effect.code.startswith("attack_"):
                        elem = effect.code[len("attack_"):]
                        stats.attack[elem] = effect.value
                    elif effect.code.startswith("res_"):
                        elem = effect.code[len("res_"):]
                        stats.resistance[elem] = effect.value
                    elif effect.code == "dmg":
                        stats.dmg = effect.value
                    elif effect.code.startswith("dmg_"):
                        stats.dmg_elements[effect.code[len("dmg_"):]] = effect.value
                    elif effect.code == "critical_strike":
                        stats.critical_strike = effect.value
                    elif effect.code == "initiative":
                        stats.initiative = effect.value
                    elif effect.code == "hp":
                        stats.hp_bonus = effect.value
                    elif effect.code == "wisdom":
                        stats.wisdom = effect.value
                    elif effect.code == "prospecting":
                        stats.prospecting = effect.value
                    elif effect.code == "inventory_space":
                        stats.inventory_space = effect.value
                    elif effect.code == "haste":
                        stats.haste = effect.value
                    elif effect.code == "lifesteal":
                        stats.lifesteal = effect.value
                    elif effect.code.startswith("boost_dmg_"):
                        # +% element damage (utility potion). PLAN #3b: route into the
                        # player's per-element dmg% so project_loadout_stats folds it and
                        # predict_win's element-damage sum sees the buff (bigger killStep)
                        # — no predict_win change, it's the same field gear dmg% uses.
                        # ALSO count it as combat-buff VALUE (dmg_elements is not otherwise
                        # in equip_value, so this is the only place it's valued). Accumulate.
                        elem = effect.code[len("boost_dmg_"):]
                        stats.dmg_elements[elem] = stats.dmg_elements.get(elem, 0) + effect.value
                        stats.combat_buff += effect.value
                    elif effect.code.startswith("boost_res_"):
                        # +% element resistance (utility potion). PLAN #3b: route into the
                        # player's resistance so projection folds it and predict_win's
                        # raw_monster (monster dmg vs player resist) drops (bigger dieStep).
                        # Valued via the resistance term ⇒ NOT also in combat_buff. Accumulate.
                        elem = effect.code[len("boost_res_"):]
                        stats.resistance[elem] = stats.resistance.get(elem, 0) + effect.value
                    elif effect.code == "boost_hp":
                        # +flat HP for the fight. PLAN #3b: route into hp_bonus so projection
                        # folds it into max_hp and predict_win's effective HP rises. Valued
                        # via hp_bonus ⇒ NOT also in combat_buff.
                        stats.hp_bonus += effect.value
                    elif effect.code == "antipoison":
                        # removes N poison/turn. Stored in its own field so predict_win can
                        # CAP the monster's poison (PLAN #3b2: max(0, poison - antipoison)),
                        # AND summed into combat_buff so the bot VALUES + equips antidotes.
                        # Accumulate (an item could carry several).
                        stats.antipoison += effect.value
                        stats.combat_buff += effect.value
                    elif effect.code in _GATHERING_SKILLS:
                        # Tool bonus for a gather skill (e.g. axe → woodcutting).
                        # Game encodes as cooldown reduction (negative value = faster);
                        # store as-is so callers can compare magnitudes.
                        stats.skill_effects[effect.code] = effect.value
                    elif effect.code == "teleport":
                        # PLAN #6b: a fast-travel consumable. The effect `value` is the
                        # destination MapSchema.map_id; TeleportAction resolves it to (x, y)
                        # via game_data.teleport_destination and lets the planner prefer a
                        # warp over a long walk.
                        stats.teleport_map_id = effect.value
                    elif effect.code == "threat":
                        # PLAN #6c carve-out: `threat` is aggro/taunt (pulls a monster's
                        # focus off allies). Irrelevant for a SOLO bot — no allies to
                        # protect — so it is DELIBERATELY not modeled. Handled here so it
                        # is covered (not silently dropped); revisit if party play lands.
                        pass

            if not isinstance(item.craft, Unset) and item.craft is not None:
                craft = item.craft
                if not isinstance(craft.skill, Unset) and craft.skill is not None:
                    stats.crafting_skill = craft.skill.value
                if not isinstance(craft.level, Unset) and craft.level is not None:
                    stats.crafting_level = craft.level

                if not isinstance(craft.items, Unset) and craft.items:
                    recipe: dict[str, int] = {}
                    for mat in craft.items:
                        recipe[mat.code] = mat.quantity
                    self._crafting_recipes[item.code] = recipe

    def _load_items(self, client: AuthenticatedClient) -> None:
        """Fetch all items and build stats + recipe indexes."""
        self._build_items(self._fetch_items(client))

    def _fetch_resources(self, client: AuthenticatedClient) -> list[ResourceSchema]:
        """Page all resources; return the list of schema objects."""
        out: list[ResourceSchema] = []
        page = 1
        while True:
            result = get_all_resources(client=client, page=page, size=100)
            if result is None or not result.data:
                break
            out.extend(result.data)
            if len(result.data) < 100:
                break
            page += 1
        return out

    def _build_resources(self, resources: list[ResourceSchema]) -> None:
        """Build skill requirement and drop item indexes from resource schema objects."""
        for res in resources:
            self._resource_skill[res.code] = (res.skill.value, res.level)
            # Pick the primary drop: most common (lowest rate value = 1/rate)
            if res.drops:
                self._resource_drops[res.code] = min(res.drops, key=lambda d: d.rate).code
                self._resource_drops_full[res.code] = [
                    (d.code, d.rate, d.min_quantity, d.max_quantity) for d in res.drops
                ]

    def _load_resources(self, client: AuthenticatedClient) -> None:
        """Fetch all resources and build skill requirement and drop item indexes."""
        self._build_resources(self._fetch_resources(client))

    def _fetch_npcs(self, client: AuthenticatedClient) -> list[NPCItem]:
        """Page all NPC items; return the list of schema objects."""
        out: list[NPCItem] = []
        page = 1
        while True:
            result = get_all_npc_items(client=client, page=page, size=100)
            if result is None or not result.data:
                break
            out.extend(result.data)
            if len(result.data) < 100:
                break
            page += 1
        return out

    def _build_npcs(self, entries: list[NPCItem]) -> None:
        """Build buy and sell stock indexes from NPC item schema objects."""
        for entry in entries:
            buy_price = entry.buy_price
            if not isinstance(buy_price, Unset) and buy_price is not None:
                self._npc_stock.setdefault(entry.npc, {})[entry.code] = buy_price
            sell_price = entry.sell_price
            if not isinstance(sell_price, Unset) and sell_price is not None:
                self._npc_sell_prices.setdefault(entry.npc, {})[entry.code] = sell_price

    def _load_npcs(self, client: AuthenticatedClient) -> None:
        """Fetch all NPC items and build buy and sell stock indexes."""
        self._build_npcs(self._fetch_npcs(client))

    def _load_ge_orders(self, client: AuthenticatedClient) -> None:
        """Index, per item, the highest-price OPEN BUY order and the lowest-price
        OPEN SELL order from the live GE order book. Filling a BUY order sells the
        item for immediate gold (realizable proceeds); filling a SELL order buys the
        item for immediate, guaranteed acquisition (realizable cost). We page each
        side of the order book and keep, per item, the single best order (BUY: max
        price; SELL: min price; ties broken by larger quantity, then order id for
        determinism). The API is the source of truth; no order is fabricated."""
        page = 1
        while True:
            result = get_ge_orders(client=client, type_=GEOrderType.BUY, page=page, size=100)
            if result is None or not result.data:
                break
            for order in result.data:
                candidate = (order.id, order.price, order.quantity)
                current = self._ge_buy_orders.get(order.code)
                if current is None or (order.price, order.quantity, order.id) > (
                    current[1], current[2], current[0]
                ):
                    self._ge_buy_orders[order.code] = candidate
            if len(result.data) < 100:
                break
            page += 1
        # SELL side (the DUAL): index the LOWEST-price open sell order per item.
        # Filling such an order BUYS the item for immediate, guaranteed acquisition,
        # so its price is a realizable cost (the cheapest fillable buy source). We
        # keep, per item, the single lowest-price order (ties broken by larger
        # quantity, then order id for determinism — same tie-break shape as the BUY
        # pass). The API is the source of truth; no order is fabricated.
        page = 1
        while True:
            result = get_ge_orders(client=client, type_=GEOrderType.SELL, page=page, size=100)
            if result is None or not result.data:
                break
            for order in result.data:
                candidate = (order.id, order.price, order.quantity)
                current = self._ge_sell_orders.get(order.code)
                if current is None or (-order.price, order.quantity, order.id) > (
                    -current[1], current[2], current[0]
                ):
                    self._ge_sell_orders[order.code] = candidate
            if len(result.data) < 100:
                break
            page += 1

    def _fetch_events(self, client: AuthenticatedClient) -> list[EventSchema]:
        """Page all events; return the list of schema objects."""
        out: list[EventSchema] = []
        page = 1
        while True:
            result = get_all_events(client=client, page=page, size=100)
            if result is None or not result.data:
                break
            out.extend(result.data)
            if len(result.data) < 100:
                break
            page += 1
        return out

    def _build_events(self, events: list[EventSchema]) -> None:
        """Index event NPCs (code -> event code, code -> fixed spawn tile) from the catalog.

        Event merchants never appear in get_all_maps; their fixed spawn tile lives
        only in the events catalog, and they exist on the map only while their event
        is active.
        """
        for ev in events:
            if ev.content.type_ != MapContentType.NPC:
                continue
            npc_code = ev.content.code
            self._npc_event_code[npc_code] = ev.code
            if ev.maps:
                first = ev.maps[0]
                self._event_npc_spawns[npc_code] = (first.x, first.y)

    def _load_events(self, client: AuthenticatedClient) -> None:
        """Fetch all events and index event NPCs."""
        self._build_events(self._fetch_events(client))

    def _fetch_monsters(self, client: AuthenticatedClient) -> list[MonsterSchema]:
        """Page all monsters; return the list of schema objects."""
        out: list[MonsterSchema] = []
        page = 1
        while True:
            result = get_all_monsters(client=client, page=page, size=100)
            if result is None or not result.data:
                break
            out.extend(result.data)
            if len(result.data) < 100:
                break
            page += 1
        return out

    def _build_monsters(self, monsters: list[MonsterSchema]) -> None:
        """Build level, stat, and drop indexes from monster schema objects."""
        for mon in monsters:
            self._monster_level[mon.code] = mon.level
            self._monster_hp[mon.code] = mon.hp
            self._monster_type[mon.code] = (
                mon.type_.value if hasattr(mon.type_, "value") else str(mon.type_ or "normal")
            )
            self._monster_attack[mon.code] = {
                elem: getattr(mon, f"attack_{elem}", 0) for elem in ("fire", "earth", "water", "air")
            }
            self._monster_resistance[mon.code] = {
                elem: getattr(mon, f"res_{elem}", 0) for elem in ("fire", "earth", "water", "air")
            }
            self._monster_critical_strike[mon.code] = mon.critical_strike
            self._monster_initiative[mon.code] = mon.initiative
            # Lifesteal, poison, barrier, burn and healing are optional monster
            # abilities carried in `effects` (most monsters have none). Parse; ⇒ 0.
            self._monster_lifesteal[mon.code] = 0
            self._monster_poison[mon.code] = 0
            self._monster_barrier[mon.code] = 0
            self._monster_burn[mon.code] = 0
            self._monster_healing[mon.code] = 0
            self._monster_reconstitution[mon.code] = 0
            self._monster_void_drain[mon.code] = 0
            self._monster_berserker_rage[mon.code] = 0
            self._monster_frenzy[mon.code] = 0
            self._monster_protective_bubble[mon.code] = 0
            self._monster_corrupted[mon.code] = 0
            mon_effects = getattr(mon, "effects", None)
            if mon_effects and not isinstance(mon_effects, Unset):
                for effect in mon_effects:
                    if getattr(effect, "code", None) == "lifesteal":
                        self._monster_lifesteal[mon.code] = effect.value
                    elif getattr(effect, "code", None) == "poison":
                        self._monster_poison[mon.code] = effect.value
                    elif getattr(effect, "code", None) == "barrier":
                        self._monster_barrier[mon.code] = effect.value
                    elif getattr(effect, "code", None) == "burn":
                        self._monster_burn[mon.code] = effect.value
                    elif getattr(effect, "code", None) == "healing":
                        self._monster_healing[mon.code] = effect.value
                    elif getattr(effect, "code", None) == "reconstitution":
                        self._monster_reconstitution[mon.code] = effect.value
                    elif getattr(effect, "code", None) == "void_drain":
                        self._monster_void_drain[mon.code] = effect.value
                    elif getattr(effect, "code", None) == "berserker_rage":
                        self._monster_berserker_rage[mon.code] = effect.value
                    elif getattr(effect, "code", None) == "frenzy":
                        self._monster_frenzy[mon.code] = effect.value
                    elif getattr(effect, "code", None) == "protective_bubble":
                        self._monster_protective_bubble[mon.code] = effect.value
                    elif getattr(effect, "code", None) == "corrupted":
                        # corrupted HELPS the player; predict_win conservatively ignores
                        # it (parsed/covered here so it is not silently dropped).
                        self._monster_corrupted[mon.code] = effect.value
            # OpenAPI conformance fields (Item 14 remediation).
            # Defensive getattr keeps older API clients green.
            min_gold = getattr(mon, "min_gold", 0)
            max_gold = getattr(mon, "max_gold", 0)
            if isinstance(min_gold, Unset):
                min_gold = 0
            if isinstance(max_gold, Unset):
                max_gold = 0
            self._monster_min_gold[mon.code] = int(min_gold or 0)
            self._monster_max_gold[mon.code] = int(max_gold or 0)
            raw_drops = getattr(mon, "drops", None)
            if raw_drops is not None and not isinstance(raw_drops, Unset):
                drops: list[tuple[str, int, int, int]] = []
                for d in raw_drops:
                    drop_code = getattr(d, "code", None)
                    rate = getattr(d, "rate", None)
                    min_q = getattr(d, "min_quantity", None)
                    max_q = getattr(d, "max_quantity", None)
                    if drop_code is not None and rate is not None:
                        drops.append((
                            str(drop_code), int(rate),
                            int(min_q if min_q is not None else 1),
                            int(max_q if max_q is not None else 1),
                        ))
                self._monster_drops[mon.code] = drops

    def _load_monsters(self, client: AuthenticatedClient) -> None:
        """Fetch all monsters and build level index."""
        self._build_monsters(self._fetch_monsters(client))
