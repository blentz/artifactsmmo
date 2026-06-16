"""Item domain catalog: per-item stats and consumable selection."""

from dataclasses import dataclass, field

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
    wisdom: int = 0                                              # +xp gain % (1% per 10 wisdom); utility/artifacts
    prospecting: int = 0                                         # +drop chance % (1% per 10 PP); utility/artifacts
    inventory_space: int = 0                                     # +inventory slots (bags); server raises inventory_max on equip
    haste: int = 0                                               # +cooldown reduction % on fights (faster actions); efficiency utility
    # OpenAPI conformance (Item 14 drift remediation): every ItemSchema
    # field the bot's decision-making logic touches must round-trip
    # from /v3/items so the planner sees what the server sees.
    tradeable: bool = True
    """`item.tradeable`. False → NpcSell rejects this item. Default True
    matches the legacy bot's assumption; populated from API in
    `GameData._load_items`."""
    conditions: list[tuple[str, int]] = field(default_factory=list)
    """`item.conditions`: list of (condition_code, value) equip/use
    prerequisites. E.g. [("character_level", 10)]. Defaults to empty
    list; populated from API."""
    subtype: str = ""
    """`item.subtype` (e.g. weapon → 'sword'). Display + future
    subtype-aware gear scoring."""


@dataclass
class ItemCatalog:
    """Item-domain slice of the static game-world cache."""

    stats: dict[str, ItemStats] = field(default_factory=dict)

    def item_stats(self, code: str) -> ItemStats | None:
        """Stats for an item."""
        return self.stats.get(code)

    def best_consumable(self, inventory: dict[str, int]) -> tuple[str, int] | None:
        """Return (item_code, hp_restore) for the highest-restore consumable in inventory, or None."""
        best: tuple[str, int] | None = None
        for code, qty in inventory.items():
            if qty <= 0:
                continue
            stats = self.stats.get(code)
            if stats is None or stats.hp_restore <= 0:
                continue
            if best is None or stats.hp_restore > best[1]:
                best = (code, stats.hp_restore)
        return best
