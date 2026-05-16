"""Static game knowledge cache loaded at startup."""

from dataclasses import dataclass, field

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.items.get_all_items_items_get import sync as get_all_items
from artifactsmmo_api_client.api.maps.get_all_maps_maps_get import sync as get_all_maps
from artifactsmmo_api_client.api.monsters.get_all_monsters_monsters_get import sync as get_all_monsters
from artifactsmmo_api_client.api.np_cs.get_all_npcs_items_npcs_items_get import sync as get_all_npc_items
from artifactsmmo_api_client.api.resources.get_all_resources_resources_get import sync as get_all_resources
from artifactsmmo_api_client.models.map_content_type import MapContentType
from artifactsmmo_api_client.models.map_layer import MapLayer
from artifactsmmo_api_client.types import Unset


@dataclass
class ItemStats:
    """Relevant stats for an item."""

    code: str
    level: int
    type_: str
    crafting_skill: str | None = None
    crafting_level: int = 0
    hp_restore: int = 0  # HP restored when consumed (0 for non-consumables)


@dataclass
class GameData:
    """Static cache of game world knowledge. Load once at startup, never mutate."""

    _monster_locations: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    _resource_locations: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    _workshop_locations: dict[str, tuple[int, int]] = field(default_factory=dict)  # skill -> (x, y)
    _bank_location: tuple[int, int] | None = None
    _taskmaster_location: tuple[int, int] | None = None
    _item_stats: dict[str, ItemStats] = field(default_factory=dict)
    _crafting_recipes: dict[str, dict[str, int]] = field(default_factory=dict)
    _resource_skill: dict[str, tuple[str, int]] = field(default_factory=dict)  # code -> (skill, level)
    _resource_drops: dict[str, str] = field(default_factory=dict)  # resource_code -> primary drop item
    _monster_level: dict[str, int] = field(default_factory=dict)
    _npc_locations: dict[str, tuple[int, int]] = field(default_factory=dict)  # npc_code -> (x, y)
    _npc_stock: dict[str, dict[str, int]] = field(default_factory=dict)  # npc_code -> {item_code: buy_price}
    _npc_sell_prices: dict[str, dict[str, int]] = field(default_factory=dict)  # npc_code -> {item_code: sell_price}

    def monster_locations(self, code: str) -> list[tuple[int, int]]:
        """Tiles where a monster spawns."""
        return self._monster_locations.get(code, [])

    def resource_locations(self, code: str) -> list[tuple[int, int]]:
        """Tiles where a resource appears."""
        return self._resource_locations.get(code, [])

    def workshop_location(self, skill: str) -> tuple[int, int] | None:
        """Location of the workshop for a crafting skill."""
        return self._workshop_locations.get(skill)

    def bank_location(self) -> tuple[int, int]:
        """Location of the bank."""
        if self._bank_location is None:
            raise RuntimeError("Bank location not found in map data")
        return self._bank_location

    def taskmaster_location(self) -> tuple[int, int]:
        """Location of the tasks master NPC."""
        if self._taskmaster_location is None:
            raise RuntimeError("Taskmaster location not found in map data")
        return self._taskmaster_location

    def item_stats(self, code: str) -> ItemStats | None:
        """Stats for an item."""
        return self._item_stats.get(code)

    def crafting_recipe(self, code: str) -> dict[str, int] | None:
        """Materials needed to craft an item, or None if not craftable."""
        return self._crafting_recipes.get(code)

    def resource_skill_level(self, code: str) -> tuple[str, int] | None:
        """Skill and level required to gather a resource."""
        return self._resource_skill.get(code)

    def resource_drop_item(self, code: str) -> str | None:
        """Primary item dropped when gathering this resource (for planning simulation)."""
        return self._resource_drops.get(code)

    def monster_level(self, code: str) -> int:
        """Level of a monster."""
        return self._monster_level.get(code, 0)

    def best_consumable(self, inventory: dict[str, int]) -> tuple[str, int] | None:
        """Return (item_code, hp_restore) for the highest-restore consumable in inventory, or None."""
        best: tuple[str, int] | None = None
        for code, qty in inventory.items():
            if qty <= 0:
                continue
            stats = self._item_stats.get(code)
            if stats is None or stats.hp_restore <= 0:
                continue
            if best is None or stats.hp_restore > best[1]:
                best = (code, stats.hp_restore)
        return best

    def npc_location(self, npc_code: str) -> tuple[int, int] | None:
        """Location of a named NPC on the map."""
        return self._npc_locations.get(npc_code)

    def npc_sells_item(self, npc_code: str, item_code: str) -> int | None:
        """Buy price of item_code from npc_code, or None if the NPC doesn't sell it."""
        return self._npc_stock.get(npc_code, {}).get(item_code)

    def npcs_selling_item(self, item_code: str) -> list[tuple[str, int]]:
        """Return [(npc_code, price)] for all NPCs that sell item_code, cheapest first."""
        results = [
            (npc_code, stock[item_code])
            for npc_code, stock in self._npc_stock.items()
            if item_code in stock
        ]
        return sorted(results, key=lambda x: x[1])

    def npc_buys_item(self, npc_code: str, item_code: str) -> int | None:
        """Price npc_code pays for item_code when the player sells it, or None if the NPC doesn't buy it."""
        return self._npc_sell_prices.get(npc_code, {}).get(item_code)

    def npcs_buying_item(self, item_code: str) -> list[tuple[str, int]]:
        """Return [(npc_code, price)] for all NPCs that buy item_code from the player, highest price first."""
        results = [
            (npc_code, prices[item_code])
            for npc_code, prices in self._npc_sell_prices.items()
            if item_code in prices
        ]
        return sorted(results, key=lambda x: -x[1])

    def nearest_location(self, x: int, y: int, locations: list[tuple[int, int]]) -> tuple[int, int] | None:
        """Find the nearest location to (x, y) by Manhattan distance."""
        if not locations:
            return None
        return min(locations, key=lambda loc: abs(loc[0] - x) + abs(loc[1] - y))

    @classmethod
    def load(cls, client: AuthenticatedClient) -> "GameData":
        """Load all game data from the API. Paginates until all data is fetched."""
        data = cls()
        data._load_maps(client)
        data._load_items(client)
        data._load_resources(client)
        data._load_monsters(client)
        data._load_npcs(client)
        return data

    def _load_maps(self, client: AuthenticatedClient) -> None:
        """Fetch all map tiles and build content location indexes."""
        page = 1
        while True:
            result = get_all_maps(client=client, layer=MapLayer.OVERWORLD, page=page, size=100)
            if result is None or not result.data:
                break

            for tile in result.data:
                content = tile.interactions.content
                if isinstance(content, Unset) or content is None:
                    continue

                loc = (tile.x, tile.y)
                ct = content.type_
                code = content.code

                if ct == MapContentType.MONSTER:
                    self._monster_locations.setdefault(code, []).append(loc)
                elif ct == MapContentType.RESOURCE:
                    self._resource_locations.setdefault(code, []).append(loc)
                elif ct == MapContentType.BANK:
                    self._bank_location = loc
                elif ct == MapContentType.TASKS_MASTER:
                    self._taskmaster_location = loc
                elif ct == MapContentType.NPC:
                    self._npc_locations[code] = loc
                elif ct == MapContentType.WORKSHOP:
                    # code is workshop identifier — match to crafting skills by substring
                    for skill in ("mining", "woodcutting", "weaponcrafting", "gearcrafting",
                                  "jewelrycrafting", "cooking", "alchemy", "fishing"):
                        if skill in code:
                            self._workshop_locations[skill] = loc
                            break

            if len(result.data) < 100:
                break
            page += 1

    def _load_items(self, client: AuthenticatedClient) -> None:
        """Fetch all items and build stats + recipe indexes."""
        page = 1
        while True:
            result = get_all_items(client=client, page=page, size=100)
            if result is None or not result.data:
                break

            for item in result.data:
                stats = ItemStats(code=item.code, level=item.level, type_=item.type_)
                self._item_stats[item.code] = stats

                if not isinstance(item.effects, Unset) and item.effects:
                    for effect in item.effects:
                        if effect.code == "heal":
                            stats.hp_restore = effect.value
                            break

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

            if len(result.data) < 100:
                break
            page += 1

    def _load_resources(self, client: AuthenticatedClient) -> None:
        """Fetch all resources and build skill requirement and drop item indexes."""
        page = 1
        while True:
            result = get_all_resources(client=client, page=page, size=100)
            if result is None or not result.data:
                break

            for res in result.data:
                self._resource_skill[res.code] = (res.skill.value, res.level)  # type: ignore[attr-defined]
                # Pick the primary drop: most common (lowest rate value = 1/rate)
                if res.drops:
                    self._resource_drops[res.code] = min(res.drops, key=lambda d: d.rate).code

            if len(result.data) < 100:
                break
            page += 1

    def _load_npcs(self, client: AuthenticatedClient) -> None:
        """Fetch all NPC items and build buy and sell stock indexes."""
        page = 1
        while True:
            result = get_all_npc_items(client=client, page=page, size=100)
            if result is None or not result.data:
                break
            for entry in result.data:
                buy_price = entry.buy_price
                if not isinstance(buy_price, Unset) and buy_price is not None:
                    self._npc_stock.setdefault(entry.npc, {})[entry.code] = buy_price
                sell_price = entry.sell_price
                if not isinstance(sell_price, Unset) and sell_price is not None:
                    self._npc_sell_prices.setdefault(entry.npc, {})[entry.code] = sell_price
            if len(result.data) < 100:
                break
            page += 1

    def _load_monsters(self, client: AuthenticatedClient) -> None:
        """Fetch all monsters and build level index."""
        page = 1
        while True:
            result = get_all_monsters(client=client, page=page, size=100)
            if result is None or not result.data:
                break

            for mon in result.data:
                self._monster_level[mon.code] = mon.level

            if len(result.data) < 100:
                break
            page += 1
