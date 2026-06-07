"""Static game knowledge cache loaded at startup."""

from dataclasses import dataclass, field

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.events.get_all_events_events_get import sync as get_all_events
from artifactsmmo_api_client.api.grand_exchange.get_ge_orders_grandexchange_orders_get import sync as get_ge_orders
from artifactsmmo_api_client.api.items.get_all_items_items_get import sync as get_all_items
from artifactsmmo_api_client.api.maps.get_all_maps_maps_get import sync as get_all_maps
from artifactsmmo_api_client.api.monsters.get_all_monsters_monsters_get import sync as get_all_monsters
from artifactsmmo_api_client.api.my_account.get_bank_details_my_bank_get import sync as get_bank_details
from artifactsmmo_api_client.api.np_cs.get_all_npcs_items_npcs_items_get import sync as get_all_npc_items
from artifactsmmo_api_client.api.resources.get_all_resources_resources_get import sync as get_all_resources
from artifactsmmo_api_client.models.ge_order_type import GEOrderType
from artifactsmmo_api_client.models.map_content_type import MapContentType
from artifactsmmo_api_client.models.map_layer import MapLayer
from artifactsmmo_api_client.types import Unset

_GATHERING_SKILLS = frozenset({"mining", "woodcutting", "fishing", "alchemy"})


@dataclass
class ItemStats:
    """Relevant stats for an item."""

    code: str
    level: int
    type_: str
    crafting_skill: str | None = None
    crafting_level: int = 0
    hp_restore: int = 0  # HP restored when consumed (0 for non-consumables)
    # skill -> effect value (e.g. woodcutting cooldown reduction)
    skill_effects: dict[str, int] = field(default_factory=dict)
    attack: dict[str, int] = field(default_factory=dict)        # element -> attack value (weapon)
    resistance: dict[str, int] = field(default_factory=dict)    # element -> resistance % (armor)
    dmg: int = 0                                                 # global damage % bonus
    dmg_elements: dict[str, int] = field(default_factory=dict)  # element -> dmg % bonus
    critical_strike: int = 0                                     # crit chance % bonus
    initiative: int = 0                                          # initiative bonus
    hp_bonus: int = 0                                            # flat max-HP bonus (gear)
    # OpenAPI conformance (Item 14 drift remediation): every ItemSchema
    # field the bot's decision-making logic touches must round-trip
    # from /v3/items so the planner sees what the server sees.
    tradeable: bool = True
    """`item.tradeable`. False → NpcSell rejects this item. Default True
    matches the legacy bot's assumption; populated from API in
    `_load_items`."""
    conditions: list[tuple[str, int]] = field(default_factory=list)
    """`item.conditions`: list of (condition_code, value) equip/use
    prerequisites. E.g. [("character_level", 10)]. Defaults to empty
    list; populated from API."""
    subtype: str = ""
    """`item.subtype` (e.g. weapon → 'sword'). Display + future
    subtype-aware gear scoring."""


@dataclass
class GameData:
    """Static cache of game world knowledge. Load once at startup, never mutate."""

    _monster_locations: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    _resource_locations: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    _workshop_locations: dict[str, tuple[int, int]] = field(default_factory=dict)  # skill -> (x, y)
    _bank_location: tuple[int, int] | None = None
    _bank_location_open: bool = False  # True once _bank_location points at an unconditional bank
    _taskmaster_location: tuple[int, int] | None = None
    _grand_exchange_location: tuple[int, int] | None = None
    _item_stats: dict[str, ItemStats] = field(default_factory=dict)
    _crafting_recipes: dict[str, dict[str, int]] = field(default_factory=dict)
    _resource_skill: dict[str, tuple[str, int]] = field(default_factory=dict)  # code -> (skill, level)
    _resource_drops: dict[str, str] = field(default_factory=dict)  # resource_code -> primary drop item
    _resource_drops_full: dict[str, list[tuple[str, int, int, int]]] = field(default_factory=dict)
    """resource_code -> [(item_code, rate, min_quantity, max_quantity), ...]; full
    drop table (the primary `_resource_drops` keeps only the lowest-rate item)."""
    _monster_level: dict[str, int] = field(default_factory=dict)
    _monster_hp: dict[str, int] = field(default_factory=dict)
    _monster_type: dict[str, str] = field(default_factory=dict)  # "normal" / "elite" / "boss"
    _monster_attack: dict[str, dict[str, int]] = field(default_factory=dict)  # code -> {element: value}
    _monster_resistance: dict[str, dict[str, int]] = field(default_factory=dict)  # code -> {element: pct}
    _monster_critical_strike: dict[str, int] = field(default_factory=dict)  # code -> crit %
    _monster_initiative: dict[str, int] = field(default_factory=dict)  # code -> initiative
    # OpenAPI conformance (Item 14 remediation): monster reward + loot fields.
    _monster_drops: dict[str, list[tuple[str, int, int, int]]] = field(default_factory=dict)
    """code -> [(item_code, rate, min_quantity, max_quantity), ...]. Drop rate is
    1-in-N (smaller = more common per server convention). Loot prediction relies
    on this; was previously dropped at parse time. `min_quantity` is restored
    symmetric to `max_quantity` so avg_qty = (min+max)/2 is faithful (openapi
    DropRateSchema carries both)."""
    _monster_min_gold: dict[str, int] = field(default_factory=dict)
    """code -> min gold reward per fight win."""
    _monster_max_gold: dict[str, int] = field(default_factory=dict)
    """code -> max gold reward per fight win."""
    _npc_locations: dict[str, tuple[int, int]] = field(default_factory=dict)  # npc_code -> (x, y)
    _npc_stock: dict[str, dict[str, int]] = field(default_factory=dict)  # npc_code -> {item_code: buy_price}
    _npc_sell_prices: dict[str, dict[str, int]] = field(default_factory=dict)  # npc_code -> {item_code: sell_price}
    _ge_buy_orders: dict[str, tuple[str, int, int]] = field(default_factory=dict)
    """item_code -> (order_id, price, quantity) for the HIGHEST-price OPEN BUY
    order standing in the Grand Exchange — the one the player can fill by selling
    into it for immediate gold. Populated from the live GE-orders API read (the
    source of truth); never fabricated. A buy order is a real standing offer, so
    its price is realizable proceeds (unlike a speculative new sell order)."""
    _ge_sell_orders: dict[str, tuple[str, int, int]] = field(default_factory=dict)
    """item_code -> (order_id, price, quantity) for the LOWEST-price OPEN SELL
    order standing in the Grand Exchange — the cheapest one the player can BUY from
    by filling it (immediate, guaranteed acquisition). This is the DUAL of
    `_ge_buy_orders`: buying picks the lowest price, liquidating picks the highest.
    Populated from the live GE-orders API read (the source of truth); never
    fabricated. A sell order is a real standing offer, so its price is a realizable
    acquisition cost (unlike a speculative new buy order)."""
    _event_npc_spawns: dict[str, tuple[int, int]] = field(default_factory=dict)  # npc_code -> fixed event spawn tile
    _npc_event_code: dict[str, str] = field(default_factory=dict)  # npc_code -> event code (membership = is_event_npc)
    _bank_capacity: int = 0
    _next_expansion_cost: int = 0
    _slots_per_expansion: int = 0  # learned after the first expansion (response delta)
    _transition_tiles: set[tuple[int, int]] = field(default_factory=set)
    _known_tiles: set[tuple[int, int]] = field(default_factory=set)  # every overworld tile that exists, content or not

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

    def has_open_bank(self) -> bool:
        """True when the resolved bank is unconditionally accessible (no
        achievement gate). Used to drop a stale global bank-lock blocker."""
        return self._bank_location_open

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
        if self._taskmaster_location is None:
            raise RuntimeError("Taskmaster location not found in map data")
        return self._taskmaster_location

    def item_stats(self, code: str) -> ItemStats | None:
        """Stats for an item."""
        return self._item_stats.get(code)

    def max_recipe_demand(self, item_code: str) -> int:
        """Largest TRANSITIVE quantity of `item_code` consumed to produce any
        single end-item, recursively across the crafting chain. Used by the
        overstock cap: anything beyond this (plus a batch buffer) is dead
        weight in the inventory.

        Example: copper_bar needs 4 copper_ore; copper_ring needs 6 copper_bar.
        Direct demand on copper_ore is 4 (per bar). Transitive demand is
        4 × 6 = 24 (one ring chain). Without the transitive multiplier the
        cap is 20, but the bot needs 24 ore to satisfy GatherMaterials —
        DiscardOverstock then deletes ore the gather goal is actively
        trying to accumulate, causing a gather/delete pingpong.

        Returns 0 when no recipe uses the item.
        """
        return self._max_recipe_demand_recursive(item_code, frozenset())

    def _max_recipe_demand_recursive(self, item_code: str, visited: frozenset[str]) -> int:
        if item_code in visited:
            return 0
        next_visited = visited | {item_code}
        max_qty = 0
        for parent_code, recipe in self._crafting_recipes.items():
            direct = recipe.get(item_code, 0)
            if direct == 0:
                continue
            # Demand multiplied by how many of `parent_code` are themselves
            # demanded transitively. A leaf with no further demand counts
            # as 1 (the parent IS the end-item).
            parent_demand = max(1, self._max_recipe_demand_recursive(parent_code, next_visited))
            chain_demand = direct * parent_demand
            if chain_demand > max_qty:
                max_qty = chain_demand
        return max_qty

    def crafting_recipe(self, code: str) -> dict[str, int] | None:
        """Materials needed to craft an item, or None if not craftable."""
        return self._crafting_recipes.get(code)

    def resource_skill_level(self, code: str) -> tuple[str, int] | None:
        """Skill and level required to gather a resource."""
        return self._resource_skill.get(code)

    def resource_drop_item(self, code: str) -> str | None:
        """Primary item dropped when gathering this resource (for planning simulation)."""
        return self._resource_drops.get(code)

    def resource_drop_table(self, code: str) -> list[tuple[str, int, int, int]]:
        """Full (item, rate, min_q, max_q) drop rows for a resource; [] if unknown."""
        return self._resource_drops_full.get(code, [])

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

    # === Monster XP formula (documented) ===
    # Source: https://docs.artifactsmmo.com/concepts/stats_and_fights/
    #   XP = round((monster_level/player_level * 20 + monster_hp * 0.04)
    #              * level_penalty * monster_multiplier * wisdom_bonus)
    #
    # level_penalty: 1.0 when char_level <= monster_level + 4
    #                0.7 when char_level - monster_level >= 5
    #                0.0 when char_level - monster_level >= 10
    # monster_multiplier: normal=1.0, elite=1.4, boss=2.0
    # wisdom_bonus: 1 + wisdom * 0.001

    _MONSTER_TYPE_MULTIPLIER = {"normal": 1.0, "elite": 1.4, "boss": 2.0}

    def xp_per_kill(self, monster_code: str, char_level: int, wisdom: int = 0) -> int:
        """Compute documented XP gained from killing `monster_code`.

        Returns 0 if monster is unknown (no level on file).
        """
        monster_level = self._monster_level.get(monster_code, 0)
        if monster_level <= 0 or char_level <= 0:
            return 0
        monster_hp = self._monster_hp.get(monster_code, 0)
        diff = char_level - monster_level
        if diff >= 10:
            penalty = 0.0
        elif diff >= 5:
            penalty = 0.7
        else:
            penalty = 1.0
        mtype = self._monster_type.get(monster_code, "normal")
        multiplier = self._MONSTER_TYPE_MULTIPLIER.get(mtype, 1.0)
        wisdom_bonus = 1.0 + wisdom * 0.001
        raw = (monster_level / char_level * 20 + monster_hp * 0.04)
        return round(raw * penalty * multiplier * wisdom_bonus)

    def monster_attack(self, code: str) -> dict[str, int]:
        """{element: attack_value} for the monster. Raises `KeyError` when the
        monster is unknown — CLAUDE.md "use only API data or fail with an error":
        silent zero-default would make `predict_win` say True for any unknown
        monster (zero-attack, zero-hp ⇒ player_first ∧ monster_hit=0 ⇒ True).
        Single locus: callers iterate over `_monster_level` (the known set);
        no try/except needed."""
        return self._monster_attack[code]

    def monster_resistance(self, code: str) -> dict[str, int]:
        """{element: resistance_pct} for the monster. Raises `KeyError` when
        unknown — see `monster_attack` for rationale."""
        return self._monster_resistance[code]

    def monster_hp(self, code: str) -> int:
        """Max HP of a monster. Raises `KeyError` when unknown — silent zero
        would make `rounds_to_kill = ceil(0 / player_hit) = 0`, defeating the
        beatability verdict."""
        return self._monster_hp[code]

    def monster_critical_strike(self, code: str) -> int:
        """Critical-strike chance % of a monster. Raises `KeyError` when
        unknown — see `monster_attack`."""
        return self._monster_critical_strike[code]

    def monster_initiative(self, code: str) -> int:
        """Initiative (turn-order) stat of a monster. Raises `KeyError` when
        unknown — see `monster_attack`."""
        return self._monster_initiative[code]

    def monster_drops(self, code: str) -> list[tuple[str, int, int, int]]:
        """OpenAPI conformance (Item 14): drop table from a monster fight.
        Returns [(item_code, rate, min_quantity, max_quantity), ...]; empty list
        if no drops known or monster missing. Rate is 1-in-N (smaller = more
        common per server convention)."""
        return self._monster_drops.get(code, [])

    def monsters_dropping(self, item: str) -> list[tuple[str, int, int, int]]:
        """Every monster whose drop table contains `item`, as
        [(monster_code, rate, min_quantity, max_quantity), ...] in catalog
        order. Empty when nothing drops the item. Used by drop-driven monster
        selection (pick the monster minimizing expected kills for a needed
        drop)."""
        out: list[tuple[str, int, int, int]] = []
        for monster_code, drops in self._monster_drops.items():
            for drop_code, rate, min_q, max_q in drops:
                if drop_code == item:
                    out.append((monster_code, rate, min_q, max_q))
        return out

    def monster_min_gold(self, code: str) -> int:
        """OpenAPI conformance (Item 14): minimum gold reward per fight win.
        Returns 0 if unknown."""
        return self._monster_min_gold.get(code, 0)

    def monster_max_gold(self, code: str) -> int:
        """OpenAPI conformance (Item 14): maximum gold reward per fight win.
        Returns 0 if unknown."""
        return self._monster_max_gold.get(code, 0)

    def monster_level(self, code: str) -> int:
        """Level of a monster, or 0 when unknown.

        Invariant-OK silent default: every caller (FightAction.is_applicable,
        task_feasibility, unlock_bank, reach_unlock_level, tiers/guards) treats
        `0` as a documented "not a known monster" probe. Changing this to
        raise would force adding try/except in 5 places (multiple-error-handling
        antipattern). The probe semantics is the contract."""
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

    def active_gathering_skills(
        self, task_code: str | None, crafting_target: str | None = None
    ) -> set[str]:
        """Gathering skills involved in producing task_code AND the bot's current
        self-directed crafting target (walking each item's recipe tree).

        E.g. task_code="ash_plank" → recipe needs ash_wood → ash_tree resource →
        woodcutting. crafting_target="copper_dagger" → copper_bar → copper_ore →
        mining. Returns the union of distinct gather skills the player should
        prefer tool upgrades for — so mining a copper-gear's materials counts
        even when no taskmaster task drives it.
        """
        skills: set[str] = set()
        visited: set[str] = set()

        def walk(item: str) -> None:
            if item in visited:
                return
            visited.add(item)
            # Direct gather: any resource that drops this item contributes its skill.
            for res_code, drop in self._resource_drops.items():
                if drop == item:
                    sl = self._resource_skill.get(res_code)
                    if sl is not None:
                        skills.add(sl[0])
            # Indirect gather: recurse into the recipe (e.g. ash_plank → ash_wood).
            recipe = self._crafting_recipes.get(item) or {}
            for mat in recipe:
                walk(mat)

        for root in (task_code, crafting_target):
            if root:
                walk(root)
        return skills

    def npc_location(self, npc_code: str) -> tuple[int, int] | None:
        """Location of a named NPC: static map scan first, then event spawn tile."""
        loc = self._npc_locations.get(npc_code)
        if loc is not None:
            return loc
        return self._event_npc_spawns.get(npc_code)

    def is_event_npc(self, npc_code: str) -> bool:
        """True if this NPC only exists during a timed event window."""
        return npc_code in self._npc_event_code

    def npc_event_code(self, npc_code: str) -> str | None:
        """Event code whose active window spawns this NPC, or None if not an event NPC."""
        return self._npc_event_code.get(npc_code)

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

    def ge_best_buy_order(self, item_code: str) -> tuple[str, int, int] | None:
        """The highest-price OPEN BUY order for item_code as (order_id, price,
        quantity), or None if no such standing order exists. This is the order the
        player fills by selling into it (immediate gold). Only API-sourced orders
        appear here; absence is encoded as None (the anti-surrogate guard for
        liquidation_venue)."""
        return self._ge_buy_orders.get(item_code)

    def ge_best_sell_order(self, item_code: str) -> tuple[str, int, int] | None:
        """The lowest-price OPEN SELL order for item_code as (order_id, price,
        quantity), or None if no such standing order exists. This is the cheapest
        order the player fills by BUYING from it (immediate acquisition). It is the
        DUAL of `ge_best_buy_order`: buying minimizes price, liquidating maximizes
        it. Only API-sourced orders appear here; absence is encoded as None (the
        anti-surrogate guard for buy_source_venue)."""
        return self._ge_sell_orders.get(item_code)

    def grand_exchange_location(self) -> tuple[int, int] | None:
        """Tile of the Grand Exchange, or None if the map has no GE."""
        return self._grand_exchange_location

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
        data._load_events(client)
        data._load_ge_orders(client)
        data._load_bank_metadata(client)
        return data

    def _load_bank_metadata(self, client: AuthenticatedClient) -> None:
        """Fetch bank capacity and next expansion cost."""
        result = get_bank_details(client=client)
        if result is None or not hasattr(result, "data") or result.data is None:
            return
        self._bank_capacity = result.data.slots
        self._next_expansion_cost = result.data.next_expansion_cost

    def _load_maps(self, client: AuthenticatedClient) -> None:
        """Fetch all map tiles and build content location indexes."""
        page = 1
        while True:
            result = get_all_maps(client=client, layer=MapLayer.OVERWORLD, page=page, size=100)
            if result is None or not result.data:
                break

            for tile in result.data:
                loc = (tile.x, tile.y)
                self._known_tiles.add(loc)

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
                        if effect.code == "heal":
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
                        elif effect.code in _GATHERING_SKILLS:
                            # Tool bonus for a gather skill (e.g. axe → woodcutting).
                            # Game encodes as cooldown reduction (negative value = faster);
                            # store as-is so callers can compare magnitudes.
                            stats.skill_effects[effect.code] = effect.value

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
                self._resource_skill[res.code] = (res.skill.value, res.level)
                # Pick the primary drop: most common (lowest rate value = 1/rate)
                if res.drops:
                    self._resource_drops[res.code] = min(res.drops, key=lambda d: d.rate).code
                    self._resource_drops_full[res.code] = [
                        (d.code, d.rate, d.min_quantity, d.max_quantity) for d in res.drops
                    ]

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

    def _load_events(self, client: AuthenticatedClient) -> None:
        """Index event NPCs (code -> event code, code -> fixed spawn tile) from the catalog.

        Event merchants never appear in get_all_maps; their fixed spawn tile lives
        only in the events catalog, and they exist on the map only while their event
        is active.
        """
        page = 1
        while True:
            result = get_all_events(client=client, page=page, size=100)
            if result is None or not result.data:
                break
            for ev in result.data:
                if ev.content.type_ != MapContentType.NPC:
                    continue
                npc_code = ev.content.code
                self._npc_event_code[npc_code] = ev.code
                if ev.maps:
                    first = ev.maps[0]
                    self._event_npc_spawns[npc_code] = (first.x, first.y)
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

            if len(result.data) < 100:
                break
            page += 1
