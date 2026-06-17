"""Monster domain catalog: levels, combat stats, spawns, drops, and XP math."""

from dataclasses import dataclass, field


@dataclass
class MonsterCatalog:
    """Monster-domain slice of the static game-world cache."""

    locations: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    levels: dict[str, int] = field(default_factory=dict)
    hp: dict[str, int] = field(default_factory=dict)
    types: dict[str, str] = field(default_factory=dict)  # "normal" / "elite" / "boss"
    attack: dict[str, dict[str, int]] = field(default_factory=dict)  # code -> {element: value}
    resistance: dict[str, dict[str, int]] = field(default_factory=dict)  # code -> {element: pct}
    critical_strike: dict[str, int] = field(default_factory=dict)  # code -> crit %
    initiative: dict[str, int] = field(default_factory=dict)  # code -> initiative
    lifesteal: dict[str, int] = field(default_factory=dict)  # code -> heal-on-crit % (effect; 0 if absent)
    poison: dict[str, int] = field(default_factory=dict)  # code -> flat per-turn DoT (effect; 0 if absent)
    barrier: dict[str, int] = field(default_factory=dict)  # code -> absorbing-shield HP (effect; 0 if absent)
    burn: dict[str, int] = field(default_factory=dict)  # code -> burn DoT % of player attack (effect; 0 if absent)
    healing: dict[str, int] = field(default_factory=dict)  # code -> regen % of monster HP (effect; 0 if absent)
    reconstitution: dict[str, int] = field(default_factory=dict)  # code -> full-heal period in turns (effect; 0 if absent)
    void_drain: dict[str, int] = field(default_factory=dict)  # code -> drain % of player HP per cycle (effect; 0 if absent)
    # OpenAPI conformance (Item 14 remediation): monster reward + loot fields.
    drops: dict[str, list[tuple[str, int, int, int]]] = field(default_factory=dict)
    """code -> [(item_code, rate, min_quantity, max_quantity), ...]. Drop rate is
    1-in-N (smaller = more common per server convention). Loot prediction relies
    on this; was previously dropped at parse time. `min_quantity` is restored
    symmetric to `max_quantity` so avg_qty = (min+max)/2 is faithful (openapi
    DropRateSchema carries both)."""
    min_gold: dict[str, int] = field(default_factory=dict)
    """code -> min gold reward per fight win."""
    max_gold: dict[str, int] = field(default_factory=dict)
    """code -> max gold reward per fight win."""

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

    def monster_locations(self, code: str) -> list[tuple[int, int]]:
        """Tiles where a monster spawns."""
        return self.locations.get(code, [])

    def xp_per_kill(self, monster_code: str, char_level: int, wisdom: int = 0) -> int:
        """Compute documented XP gained from killing `monster_code`.

        Returns 0 if monster is unknown (no level on file).
        """
        monster_level = self.levels.get(monster_code, 0)
        if monster_level <= 0 or char_level <= 0:
            return 0
        monster_hp = self.hp.get(monster_code, 0)
        diff = char_level - monster_level
        if diff >= 10:
            penalty = 0.0
        elif diff >= 5:
            penalty = 0.7
        else:
            penalty = 1.0
        mtype = self.types.get(monster_code, "normal")
        multiplier = self._MONSTER_TYPE_MULTIPLIER.get(mtype, 1.0)
        wisdom_bonus = 1.0 + wisdom * 0.001
        raw = (monster_level / char_level * 20 + monster_hp * 0.04)
        return round(raw * penalty * multiplier * wisdom_bonus)

    def monster_attack(self, code: str) -> dict[str, int]:
        """{element: attack_value} for the monster. Raises `KeyError` when the
        monster is unknown — CLAUDE.md "use only API data or fail with an error":
        silent zero-default would make `predict_win` say True for any unknown
        monster (zero-attack, zero-hp ⇒ player_first ∧ monster_hit=0 ⇒ True).
        Single locus: callers iterate over the known-monster level index;
        no try/except needed."""
        return self.attack[code]

    def monster_resistance(self, code: str) -> dict[str, int]:
        """{element: resistance_pct} for the monster. Raises `KeyError` when
        unknown — see `monster_attack` for rationale."""
        return self.resistance[code]

    def monster_hp(self, code: str) -> int:
        """Max HP of a monster. Raises `KeyError` when unknown — silent zero
        would make `rounds_to_kill = ceil(0 / player_hit) = 0`, defeating the
        beatability verdict."""
        return self.hp[code]

    def monster_critical_strike(self, code: str) -> int:
        """Critical-strike chance % of a monster. Raises `KeyError` when
        unknown — see `monster_attack`."""
        return self.critical_strike[code]

    def monster_lifesteal(self, code: str) -> int:
        """Heal-on-crit % of a monster (the `lifesteal` effect). Returns 0 when
        absent — lifesteal is an OPTIONAL monster ability (most monsters have
        none), so unlike the always-present combat stats this does not raise."""
        return self.lifesteal.get(code, 0)

    def monster_poison(self, code: str) -> int:
        """Flat per-turn poison DoT of a monster (the `poison` effect). Returns 0
        when absent — poison is an OPTIONAL monster ability (most monsters have
        none), so unlike the always-present combat stats this does not raise."""
        return self.poison.get(code, 0)

    def monster_barrier(self, code: str) -> int:
        """Absorbing-shield HP of a monster (the `barrier` effect). Returns 0 when
        absent — barrier is an OPTIONAL monster ability (most monsters have none),
        so unlike the always-present combat stats this does not raise."""
        return self.barrier.get(code, 0)

    def monster_burn(self, code: str) -> int:
        """Burn DoT percent (of player attack) of a monster (the `burn` effect).
        Returns 0 when absent — burn is an OPTIONAL monster ability (most monsters
        have none), so unlike the always-present combat stats this does not raise."""
        return self.burn.get(code, 0)

    def monster_healing(self, code: str) -> int:
        """Regen percent (of the monster's HP) of a monster (the `healing` effect).
        Returns 0 when absent — healing is an OPTIONAL monster ability (most monsters
        have none), so unlike the always-present combat stats this does not raise."""
        return self.healing.get(code, 0)

    def monster_reconstitution(self, code: str) -> int:
        """Full-heal period (in turns) of a monster (the `reconstitution` effect).
        Returns 0 when absent — reconstitution is an OPTIONAL monster ability (most
        monsters have none), so unlike the always-present combat stats this does not
        raise. 0 means no reconstitution."""
        return self.reconstitution.get(code, 0)

    def monster_void_drain(self, code: str) -> int:
        """Void-drain percent (of player HP, drained to heal the monster) of a
        monster (the `void_drain` effect). Returns 0 when absent — void_drain is an
        OPTIONAL monster ability (most monsters have none), so unlike the
        always-present combat stats this does not raise."""
        return self.void_drain.get(code, 0)

    def monster_initiative(self, code: str) -> int:
        """Initiative (turn-order) stat of a monster. Raises `KeyError` when
        unknown — see `monster_attack`."""
        return self.initiative[code]

    def monster_drops(self, code: str) -> list[tuple[str, int, int, int]]:
        """OpenAPI conformance (Item 14): drop table from a monster fight.
        Returns [(item_code, rate, min_quantity, max_quantity), ...]; empty list
        if no drops known or monster missing. Rate is 1-in-N (smaller = more
        common per server convention)."""
        return self.drops.get(code, [])

    def monsters_dropping(self, item: str) -> list[tuple[str, int, int, int]]:
        """Every monster whose drop table contains `item`, as
        [(monster_code, rate, min_quantity, max_quantity), ...] in catalog
        order. Empty when nothing drops the item. Used by drop-driven monster
        selection (pick the monster minimizing expected kills for a needed
        drop)."""
        out: list[tuple[str, int, int, int]] = []
        for monster_code, monster_drops in self.drops.items():
            for drop_code, rate, min_q, max_q in monster_drops:
                if drop_code == item:
                    out.append((monster_code, rate, min_q, max_q))
        return out

    def monster_min_gold(self, code: str) -> int:
        """OpenAPI conformance (Item 14): minimum gold reward per fight win.
        Returns 0 if unknown."""
        return self.min_gold.get(code, 0)

    def monster_max_gold(self, code: str) -> int:
        """OpenAPI conformance (Item 14): maximum gold reward per fight win.
        Returns 0 if unknown."""
        return self.max_gold.get(code, 0)

    def monster_level(self, code: str) -> int:
        """Level of a monster, or 0 when unknown.

        Invariant-OK silent default: every caller (FightAction.is_applicable,
        task_feasibility, unlock_bank, reach_unlock_level, tiers/guards) treats
        `0` as a documented "not a known monster" probe. Changing this to
        raise would force adding try/except in 5 places (multiple-error-handling
        antipattern). The probe semantics is the contract."""
        return self.levels.get(code, 0)
