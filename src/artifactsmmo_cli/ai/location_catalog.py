"""World/location domain catalog: bank, workshops, NPCs, GE orders, and tiles."""

from dataclasses import dataclass, field


@dataclass
class LocationCatalog:
    """World-location slice of the static game-world cache: fixed facilities
    (bank, workshops, taskmaster, Grand Exchange), NPC trade indexes, event
    spawns, GE order books, bank metadata, and raw tile sets."""

    workshop_locations: dict[str, tuple[int, int]] = field(default_factory=dict)  # skill -> (x, y)
    raid_locations: dict[str, list[tuple[int, int]]] = field(default_factory=dict)  # raid_code -> tiles (P6)
    bank_tile: tuple[int, int] | None = None
    bank_tile_open: bool = False  # True once bank_tile points at an unconditional bank
    taskmaster_tile: tuple[int, int] | None = None
    grand_exchange_tile: tuple[int, int] | None = None
    npc_tiles: dict[str, tuple[int, int]] = field(default_factory=dict)  # npc_code -> (x, y)
    npc_stock: dict[str, dict[str, int]] = field(default_factory=dict)  # npc_code -> {item_code: buy_price}
    npc_buy_currency: dict[str, dict[str, str]] = field(default_factory=dict)  # npc_code -> {item_code: currency}
    """Currency the player PAYS to buy each stocked item (`NPCItem.currency`:
    "if it's not gold, it's the item code"). Parallel to `npc_stock`; populated
    from the same NPC items. `gold` is the common case, but several vendors take
    item currencies (`sandwhisper_coin`, `small_pearls`, `elemental_page`, …) so
    the buy PRICE alone is ambiguous without this. Acquisition planning recurses
    on currency attainability."""
    npc_sell_prices: dict[str, dict[str, int]] = field(default_factory=dict)  # npc_code -> {item_code: sell_price}
    ge_buy_orders: dict[str, tuple[str, int, int]] = field(default_factory=dict)
    """item_code -> (order_id, price, quantity) for the HIGHEST-price OPEN BUY
    order standing in the Grand Exchange — the one the player can fill by selling
    into it for immediate gold. Populated from the live GE-orders API read (the
    source of truth); never fabricated. A buy order is a real standing offer, so
    its price is realizable proceeds (unlike a speculative new sell order)."""
    ge_sell_orders: dict[str, tuple[str, int, int]] = field(default_factory=dict)
    """item_code -> (order_id, price, quantity) for the LOWEST-price OPEN SELL
    order standing in the Grand Exchange — the cheapest one the player can BUY from
    by filling it (immediate, guaranteed acquisition). This is the DUAL of
    `ge_buy_orders`: buying picks the lowest price, liquidating picks the highest.
    Populated from the live GE-orders API read (the source of truth); never
    fabricated. A sell order is a real standing offer, so its price is a realizable
    acquisition cost (unlike a speculative new buy order)."""
    event_npc_spawns: dict[str, tuple[int, int]] = field(default_factory=dict)  # npc_code -> fixed event spawn tile
    npc_event_codes: dict[str, str] = field(default_factory=dict)  # npc_code -> event code (membership = is_event_npc)
    # Event-spawned combat/gather content (PLAN #4 visibility slice). Loaded for ALL
    # events from the catalog; surfaced to the planner only while the spawning event is
    # in `active_event_codes` (refreshed per cycle from WorldState.active_events). Keyed
    # by the event monster/resource code; `event_code_of_content` maps that code back to
    # the gating event.
    event_monster_locations: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    event_resource_locations: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    event_code_of_content: dict[str, str] = field(default_factory=dict)  # monster/resource code -> event code
    active_event_codes: set[str] = field(default_factory=set)  # per-cycle: events live right now
    bank_capacity: int = 0
    next_expansion_cost: int = 0
    slots_per_expansion: int = 0  # learned after the first expansion (response delta)
    transition_tiles: set[tuple[int, int]] = field(default_factory=set)
    known_tiles: set[tuple[int, int]] = field(default_factory=set)  # every overworld tile that exists, content or not
    map_id_to_loc: dict[int, tuple[int, int]] = field(default_factory=dict)  # MapSchema.map_id -> (x, y); resolves teleport destinations

    def map_location_by_id(self, map_id: int) -> tuple[int, int] | None:
        """Tile (x, y) of a map by its `MapSchema.map_id`, or None if that map
        is not in the loaded overworld set. Used to resolve a teleport
        consumable's destination (its effect `value` is a map_id)."""
        return self.map_id_to_loc.get(map_id)

    def workshop_location(self, skill: str) -> tuple[int, int] | None:
        """Location of the workshop for a crafting skill."""
        return self.workshop_locations.get(skill)

    def raid_location_tiles(self, raid_code: str) -> list[tuple[int, int]]:
        """Map tiles carrying this raid's content (empty if unknown). The tile
        exists statically; the boss is fightable there only while the raid's
        window is active (WorldState.active_raids gates participation)."""
        return self.raid_locations.get(raid_code, [])

    def bank_location(self) -> tuple[int, int]:
        """Location of the bank."""
        if self.bank_tile is None:
            raise RuntimeError("Bank location not found in map data")
        return self.bank_tile

    def has_open_bank(self) -> bool:
        """True when the resolved bank is unconditionally accessible (no
        achievement gate). Used to drop a stale global bank-lock blocker."""
        return self.bank_tile_open

    def taskmaster_location(self) -> tuple[int, int]:
        """Location of the tasks master NPC."""
        if self.taskmaster_tile is None:
            raise RuntimeError("Taskmaster location not found in map data")
        return self.taskmaster_tile

    def npc_location(self, npc_code: str) -> tuple[int, int] | None:
        """Location of a named NPC: static map scan first, then event spawn tile."""
        loc = self.npc_tiles.get(npc_code)
        if loc is not None:
            return loc
        return self.event_npc_spawns.get(npc_code)

    def is_event_npc(self, npc_code: str) -> bool:
        """True if this NPC only exists during a timed event window."""
        return npc_code in self.npc_event_codes

    def _content_event_active(self, code: str) -> bool:
        """True iff `code` is event-spawned content whose event is live now."""
        ev = self.event_code_of_content.get(code)
        return ev is not None and ev in self.active_event_codes

    def active_event_monster_tiles(self, monster_code: str) -> list[tuple[int, int]]:
        """Event spawn tiles for `monster_code` while its event is active, else []."""
        if self._content_event_active(monster_code):
            return self.event_monster_locations.get(monster_code, [])
        return []

    def active_event_resource_tiles(self, resource_code: str) -> list[tuple[int, int]]:
        """Event spawn tiles for `resource_code` while its event is active, else []."""
        if self._content_event_active(resource_code):
            return self.event_resource_locations.get(resource_code, [])
        return []

    def active_event_monsters(self) -> dict[str, list[tuple[int, int]]]:
        """{monster_code -> event tiles} for every event monster live right now."""
        return {code: tiles for code, tiles in self.event_monster_locations.items()
                if self._content_event_active(code)}

    def active_event_resources(self) -> dict[str, list[tuple[int, int]]]:
        """{resource_code -> event tiles} for every event resource live right now."""
        return {code: tiles for code, tiles in self.event_resource_locations.items()
                if self._content_event_active(code)}

    def npc_event_code(self, npc_code: str) -> str | None:
        """Event code whose active window spawns this NPC, or None if not an event NPC."""
        return self.npc_event_codes.get(npc_code)

    def npc_sells_item(self, npc_code: str, item_code: str) -> int | None:
        """Buy price of item_code from npc_code, or None if the NPC doesn't sell it."""
        return self.npc_stock.get(npc_code, {}).get(item_code)

    def npcs_selling_item(self, item_code: str) -> list[tuple[str, int]]:
        """Return [(npc_code, price)] for NPCs selling item_code FOR GOLD, cheapest
        first. GOLD-ONLY by contract: every caller (craft_vs_buy.acquisition_method,
        progression_reserve, the gathering must-buy path) treats the returned price
        as gold — comparing a sandwhisper_coin/small_pearls price as gold would be a
        category error (#15). Non-gold purchases (rune/bag/artifact special vendors)
        are surfaced by the currency-aware `npc_purchases` and routed through the
        objective buy-edge / currency-earning sub-goal instead."""
        results = [
            (npc_code, stock[item_code])
            for npc_code, stock in self.npc_stock.items()
            if item_code in stock
            and (self.npc_buy_currency.get(npc_code, {}).get(item_code) or "gold") == "gold"
        ]
        return sorted(results, key=lambda x: x[1])

    def npc_purchase_currency(self, npc_code: str, item_code: str) -> str | None:
        """Currency the player pays npc_code to buy item_code, or None if the NPC
        doesn't sell it. `'gold'` for ordinary vendors; an item code otherwise."""
        return self.npc_buy_currency.get(npc_code, {}).get(item_code)

    def npc_purchases(self, item_code: str) -> list[tuple[str, int, str]]:
        """Return [(npc_code, price, currency)] for every NPC that sells
        item_code, cheapest first. The currency-aware companion to
        `npcs_selling_item` (which collapses to gold); acquisition planning needs
        the currency to recurse on its attainability."""
        results = [
            (npc_code, price, self.npc_buy_currency.get(npc_code, {}).get(item_code, "gold"))
            for npc_code, stock in self.npc_stock.items()
            for item, price in stock.items()
            if item == item_code
        ]
        return sorted(results, key=lambda x: x[1])

    def npc_buys_item(self, npc_code: str, item_code: str) -> int | None:
        """Price npc_code pays for item_code when the player sells it, or None if the NPC doesn't buy it."""
        return self.npc_sell_prices.get(npc_code, {}).get(item_code)

    def npcs_buying_item(self, item_code: str) -> list[tuple[str, int]]:
        """Return [(npc_code, price)] for all NPCs that buy item_code from the player, highest price first."""
        results = [
            (npc_code, prices[item_code])
            for npc_code, prices in self.npc_sell_prices.items()
            if item_code in prices
        ]
        return sorted(results, key=lambda x: -x[1])

    def ge_best_buy_order(self, item_code: str) -> tuple[str, int, int] | None:
        """The highest-price OPEN BUY order for item_code as (order_id, price,
        quantity), or None if no such standing order exists. This is the order the
        player fills by selling into it (immediate gold). Only API-sourced orders
        appear here; absence is encoded as None (the anti-surrogate guard for
        liquidation_venue)."""
        return self.ge_buy_orders.get(item_code)

    def ge_best_sell_order(self, item_code: str) -> tuple[str, int, int] | None:
        """The lowest-price OPEN SELL order for item_code as (order_id, price,
        quantity), or None if no such standing order exists. This is the cheapest
        order the player fills by BUYING from it (immediate acquisition). It is the
        DUAL of `ge_best_buy_order`: buying minimizes price, liquidating maximizes
        it. Only API-sourced orders appear here; absence is encoded as None (the
        anti-surrogate guard for buy_source_venue)."""
        return self.ge_sell_orders.get(item_code)

    def grand_exchange_location(self) -> tuple[int, int] | None:
        """Tile of the Grand Exchange, or None if the map has no GE."""
        return self.grand_exchange_tile

    @staticmethod
    def nearest_location(x: int, y: int, locations: list[tuple[int, int]]) -> tuple[int, int] | None:
        """Find the nearest location to (x, y) by Manhattan distance."""
        if not locations:
            return None
        return min(locations, key=lambda loc: abs(loc[0] - x) + abs(loc[1] - y))
