"""Project a hypothetical loadout's combat stats as a delta from current totals.

The server reports only total stats (base + equipped gear), never base, so a
loadout's projected stats are computed as: current totals + Σ_slot (picked item
contribution − currently-equipped item contribution). Pure; used by predict_win
to judge winnability with the best-attainable loadout before equipping it."""

from dataclasses import dataclass

from artifactsmmo_cli.ai.elements import ELEMENTS
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass(frozen=True)
class ProjectedStats:
    attack: dict[str, int]
    dmg: int
    dmg_elements: dict[str, int]
    resistance: dict[str, int]
    critical_strike: int
    initiative: int
    max_hp: int
    wisdom: int = 0
    """+1% xp per 10 points. THE stat `J` most directly cares about, since `J`'s
    benefit term is xp-driven cycles — and it was absent from this struct until
    2026-08-08, so a `wisdom_amulet` (+6% xp on every kill to level 50) projected
    byte-identically to doing nothing. `cheapest_path_to_level` had always
    CONSUMED wisdom (`xp_per_kill(..., wisdom=wisdom)`); it just read it from
    `state.wisdom`, the server total for gear already WORN, so a candidate's own
    wisdom never reached the formula that wanted it.

    `inventory_space` and `lifesteal` remain unprojected for a concrete reason:
    `WorldState` has no field for either, so there is no BASE total to add a
    delta to. This projection is a delta from server-authoritative totals, and a
    fabricated base would silently mis-state every candidate — worse than the
    absence it replaced. They stay declared in
    `audit/stat_projection_completeness.UNPRICED`, which is the difference
    between a known gap and a forgotten one."""
    prospecting: int = 0
    """+1% drop chance per 10 points. Pays by reducing kills-per-drop, so it
    makes every DROP-route acquisition cheaper — see
    `ai/acquisition_cost._drop_actions`. Unlike the three stats named above it
    HAS a `WorldState` base total to project a delta from."""


def _drop_zeros(d: dict[str, int]) -> dict[str, int]:
    # Drop only exact zeros; negative deltas (a downgrade) are kept — predict_win floors per-element damage at 0.
    return {k: v for k, v in d.items() if v != 0}


def project_loadout_stats(
    state: WorldState, loadout: dict[str, str | None], game_data: GameData,
) -> ProjectedStats:
    """Combat stats if `loadout` (slot -> item_code | None) were equipped."""
    attack = dict(state.attack)
    dmg = state.dmg
    dmg_elements = dict(state.dmg_elements)
    resistance = dict(state.resistance)
    critical_strike = state.critical_strike
    initiative = state.initiative
    max_hp = state.max_hp
    wisdom = state.wisdom
    prospecting = state.prospecting

    for slot, new_code in loadout.items():
        old_code = state.equipment.get(slot)
        if new_code == old_code:
            continue
        new_s: ItemStats | None = game_data.item_stats(new_code) if new_code else None
        old_s: ItemStats | None = game_data.item_stats(old_code) if old_code else None
        for elem in ELEMENTS:
            attack[elem] = (attack.get(elem, 0)
                            + (new_s.attack.get(elem, 0) if new_s else 0)
                            - (old_s.attack.get(elem, 0) if old_s else 0))
            dmg_elements[elem] = (dmg_elements.get(elem, 0)
                                  + (new_s.dmg_elements.get(elem, 0) if new_s else 0)
                                  - (old_s.dmg_elements.get(elem, 0) if old_s else 0))
            resistance[elem] = (resistance.get(elem, 0)
                                + (new_s.resistance.get(elem, 0) if new_s else 0)
                                - (old_s.resistance.get(elem, 0) if old_s else 0))
        dmg += (new_s.dmg if new_s else 0) - (old_s.dmg if old_s else 0)
        critical_strike += (new_s.critical_strike if new_s else 0) - (old_s.critical_strike if old_s else 0)
        initiative += (new_s.initiative if new_s else 0) - (old_s.initiative if old_s else 0)
        # max_hp may fall below current hp on a downgrade; intentional (conservative survivability) — do not clamp.
        max_hp += (new_s.hp_bonus if new_s else 0) - (old_s.hp_bonus if old_s else 0)
        # Same delta form as everything above -- the server reports TOTALS, so a
        # swap is (new contribution - old contribution). `haste` is deliberately
        # absent: it reduces cooldown SECONDS against an objective denominated in
        # ACTIONS. See `audit/stat_projection_completeness.UNPRICED`.
        wisdom += (new_s.wisdom if new_s else 0) - (old_s.wisdom if old_s else 0)
        prospecting += ((new_s.prospecting if new_s else 0)
                        - (old_s.prospecting if old_s else 0))

    return ProjectedStats(
        attack=_drop_zeros(attack),
        dmg=dmg,
        dmg_elements=_drop_zeros(dmg_elements),
        resistance=_drop_zeros(resistance),
        critical_strike=critical_strike,
        initiative=initiative,
        max_hp=max_hp,
        wisdom=wisdom,
        prospecting=prospecting,
    )
