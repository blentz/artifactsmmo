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
    # code -> full-heal period in turns (effect; 0 if absent)
    reconstitution: dict[str, int] = field(default_factory=dict)
    # code -> drain % of player HP per cycle (effect; 0 if absent)
    void_drain: dict[str, int] = field(default_factory=dict)
    berserker_rage: dict[str, int] = field(default_factory=dict)  # code -> +% damage below 25% HP (effect; 0 if absent)
    frenzy: dict[str, int] = field(default_factory=dict)  # code -> +% damage on crit (effect; 0 if absent)
    # code -> % resist on rotating element (effect; 0 if absent)
    protective_bubble: dict[str, int] = field(default_factory=dict)
    # code -> per-hit resist-reduction % (effect; 0 if absent). HELPS the player.
    corrupted: dict[str, int] = field(default_factory=dict)
    # code -> first-hit-per-turn damage-reduction % (effect; 0 if absent)
    sun_shield: dict[str, int] = field(default_factory=dict)
    greed: dict[str, int] = field(default_factory=dict)  # code -> +% damage per 10% max-HP lost (effect; 0 if absent)
    # code -> reflect % of damage taken, once/3 turns (effect; 0 if absent)
    enchanted_mirror: dict[str, int] = field(default_factory=dict)
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
    #                0.7 when 5 <= char_level - monster_level <= 10
    #                0.0 when char_level - monster_level >= 11
    #
    # THE ZERO BOUNDARY IS OBSERVED, NOT ASSUMED. The doc prose is loose about
    # whether a gap of exactly 10 pays; it does, at the 0.7 penalty. Every
    # ok-Fight row in the learning store (49_263 cycles, 5 characters), each
    # read with its OWN `delta_xp` — see `formal/diff/xp_formula_replay.py`:
    #
    #     diff = char_level - monster_level    pays / zero
    #        8                                 2213 /   0
    #        9                                 2101 /   0
    #       10                                  372 /   0
    #       11                                    0 /  51   <-- band starts here
    #       14                                    0 /   1
    #       16                                    0 /  37
    #       20                                    0 /  18
    #
    # 10_750 paying fights, all at diff <= 10; 107 zero-xp fights, all at
    # diff >= 11; no exception at the boundary. The diff-10 payers are 4
    # characters over 5 distinct (monster, char_level) pairs, and their awards
    # match the 0.7 band exactly (342/372 at wisdom=0, the rest a positive
    # wisdom excess) — never the 1.0 band. The earlier `>= 10` here cited a
    # "399/399" corroboration produced when that replay recovered per-fight XP
    # by DIFFERENCING CONSECUTIVE STATE SNAPSHOTS — the same off-by-one
    # attribution that credited each craft with the FOLLOWING cycle's xp. It
    # never observed a single zero-band fight, so it never tested the boundary.
    # monster_multiplier: normal=1.0, elite=1.4, boss=2.0
    # wisdom_bonus: 1 + wisdom * 0.001

    _MONSTER_TYPE_MULT10 = {"normal": 10, "elite": 14, "boss": 20}  # multiplier x10, exact

    def monster_locations(self, code: str) -> list[tuple[int, int]]:
        """Tiles where a monster spawns."""
        return self.locations.get(code, [])

    def xp_per_kill(self, monster_code: str, char_level: int, wisdom: int = 0) -> int:
        """Compute documented XP gained from killing `monster_code`.

        Returns 0 if monster is unknown (no level on file).

        EXACT integer arithmetic (mechanical-extraction discipline — this value
        is in the decision path: unlock_boost ranks by it, combat_picker gates
        on it being positive). The documented formula is evaluated as a single
        rational num/den with round-half-UP (a tie goes to the larger award), so
        the Lean mirror (`Formal.XpValue.xpPerKill`) is bit-identical and no
        float rounding can flip a ranking. penalty and multiplier are carried
        x10 (0.7 -> 7, 1.4 -> 14), wisdom_bonus as (1000 + wisdom)/1000:

            num = (2000*ml + 4*hp*cl) * penalty10 * mult10 * (1000 + wisdom)
            den = cl * 10_000_000
        """
        monster_level = self.levels.get(monster_code, 0)
        if monster_level <= 0 or char_level <= 0:
            return 0
        monster_hp = self.hp.get(monster_code, 0)
        diff = char_level - monster_level
        if diff >= 11:
            return 0
        penalty10 = 7 if diff >= 5 else 10
        mtype = self.types.get(monster_code, "normal")
        mult10 = self._MONSTER_TYPE_MULT10.get(mtype, 10)
        num = ((2000 * monster_level + 4 * monster_hp * char_level)
               * penalty10 * mult10 * (1000 + wisdom))
        den = char_level * 10_000_000
        q, r = divmod(num, den)
        # HALF-UP, not half-to-even. This used to be Python's `round` semantics --
        # a TOOLCHAIN artifact standing in for a game rule nobody had read. Parity
        # of the quotient decided the award on a tie, so two monsters could be
        # ranked by which side of a half they landed on. Ratified 2026-08-10 as
        # half away from zero; on non-negative values that is this.
        if 2 * r >= den:
            return q + 1
        return q

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

    def monster_berserker_rage(self, code: str) -> int:
        """Berserker-rage damage-boost percent of a monster (the `berserker_rage`
        effect). Returns 0 when absent — an OPTIONAL monster ability (most monsters
        have none), so unlike the always-present combat stats this does not raise."""
        return self.berserker_rage.get(code, 0)

    def monster_frenzy(self, code: str) -> int:
        """Frenzy damage-boost percent of a monster (the `frenzy` effect). Returns 0
        when absent — an OPTIONAL monster ability (most monsters have none), so
        unlike the always-present combat stats this does not raise."""
        return self.frenzy.get(code, 0)

    def monster_protective_bubble(self, code: str) -> int:
        """Protective-bubble resistance percent of a monster (the
        `protective_bubble` effect). Returns 0 when absent — an OPTIONAL monster
        ability (most monsters have none), so unlike the always-present combat stats
        this does not raise."""
        return self.protective_bubble.get(code, 0)

    def monster_corrupted(self, code: str) -> int:
        """Per-hit resistance-reduction percent of a monster (the `corrupted`
        effect). Returns 0 when absent. corrupted HELPS the player (the monster's
        resist drops as it is hit), so predict_win deliberately does NOT credit it —
        it conservatively models the player's pre-corruption (minimum) damage. This
        accessor exists so the effect is parsed/covered, not silently dropped."""
        return self.corrupted.get(code, 0)

    def monster_sun_shield(self, code: str) -> int:
        """First-hit-per-turn damage-reduction percent of a monster (the `sun_shield`
        effect). Returns 0 when absent — an OPTIONAL monster ability (most monsters
        have none), so unlike the always-present combat stats this does not raise."""
        return self.sun_shield.get(code, 0)

    def monster_greed(self, code: str) -> int:
        """Greed ramp percent of a monster (the `greed` effect): +value% damage per
        10% max-HP the monster has lost. Returns 0 when absent — an OPTIONAL monster
        ability (most monsters have none), so unlike the always-present combat stats
        this does not raise."""
        return self.greed.get(code, 0)

    def monster_enchanted_mirror(self, code: str) -> int:
        """Enchanted-mirror reflect percent of a monster (the `enchanted_mirror`
        effect): reflects value% of damage taken back at the player. Returns 0 when
        absent — an OPTIONAL monster ability (most monsters have none), so unlike the
        always-present combat stats this does not raise."""
        return self.enchanted_mirror.get(code, 0)

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
