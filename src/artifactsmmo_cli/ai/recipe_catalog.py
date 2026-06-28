"""Recipe/resource domain catalog: crafting recipes, gather skills, and drops."""

from dataclasses import dataclass, field


@dataclass
class RecipeCatalog:
    """Crafting-recipe and resource slice of the static game-world cache."""

    crafting_recipes: dict[str, dict[str, int]] = field(default_factory=dict)
    craft_yields: dict[str, int] = field(default_factory=dict)
    resource_skill: dict[str, tuple[str, int]] = field(default_factory=dict)  # code -> (skill, level)
    resource_drops: dict[str, str] = field(default_factory=dict)  # resource_code -> primary drop item
    resource_drops_full: dict[str, list[tuple[str, int, int, int]]] = field(default_factory=dict)
    """resource_code -> [(item_code, rate, min_quantity, max_quantity), ...]; full
    drop table (the primary `resource_drops` keeps only the lowest-rate item)."""
    locations: dict[str, list[tuple[int, int]]] = field(default_factory=dict)

    def resource_locations(self, code: str) -> list[tuple[int, int]]:
        """Tiles where a resource appears."""
        return self.locations.get(code, [])

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
        for parent_code, recipe in self.crafting_recipes.items():
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
        return self.crafting_recipes.get(code)

    def resource_skill_level(self, code: str) -> tuple[str, int] | None:
        """Skill and level required to gather a resource."""
        return self.resource_skill.get(code)

    def resource_drop_item(self, code: str) -> str | None:
        """Primary item dropped when gathering this resource (for planning simulation)."""
        return self.resource_drops.get(code)

    def resource_drop_table(self, code: str) -> list[tuple[str, int, int, int]]:
        """Full (item, rate, min_q, max_q) drop rows for a resource; [] if unknown."""
        return self.resource_drops_full.get(code, [])

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
            for res_code, drop in self.resource_drops.items():
                if drop == item:
                    sl = self.resource_skill.get(res_code)
                    if sl is not None:
                        skills.add(sl[0])
            # Indirect gather: recurse into the recipe (e.g. ash_plank → ash_wood).
            recipe = self.crafting_recipes.get(item) or {}
            for mat in recipe:
                walk(mat)

        for root in (task_code, crafting_target):
            if root:
                walk(root)
        return skills
