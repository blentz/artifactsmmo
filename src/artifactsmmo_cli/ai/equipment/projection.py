"""Project a hypothetical loadout's combat stats as a delta from current totals.

The server reports only total stats (base + equipped gear), never base, so for
gear slots a loadout's projected stats are computed as: current totals + Σ_slot
(picked item contribution − currently-equipped item contribution). Pure; used by predict_win
to judge winnability with the best-attainable loadout before equipping it.

THE UTILITY SLOTS are not in the totals. A utility potion's boost is a
combat-time effect the sheet leaves out: live 2026-10-28, three public sheets
wearing `earth_boost_potion` (+12% earth damage), `air_boost_potion` and
`health_boost_potion` (+250 HP) each read exactly base + the gear's stats.
So a worn potion is never subtracted, and the one a utility slot fights with
is added: the picked one, or the worn one kept while its slot holds a unit (a
slot with no stock is no potion, `combat.unpotioned`)."""

import dataclasses
from dataclasses import dataclass

from artifactsmmo_cli.ai.elements import ELEMENTS
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.utility_slot import UTILITY_SLOTS, utility_slot_quantity
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

    `lifesteal` remains unprojected for a concrete reason: `WorldState` has no
    field for it, so there is no BASE total to add a delta to. This projection
    is a delta from server-authoritative totals, and a fabricated base would
    silently mis-state every candidate — worse than the absence it replaced. It
    stays declared in `audit/stat_projection_completeness.UNPRICED`, which is
    the difference between a known gap and a forgotten one."""
    prospecting: int = 0
    """+1% drop chance per 10 points. Pays by reducing kills-per-drop, so it
    makes every DROP-route acquisition cheaper — see
    `ai/acquisition_cost._drop_actions`. Unlike the three stats named above it
    HAS a `WorldState` base total to project a delta from."""
    haste: int = 0
    """The fight-cooldown reduction a fight's seconds read
    (`fight_seconds_core`, spec 2026-10-18 §2.9). Projected since that spec
    priced a fight by its length: a haste piece shortens every fight."""
    inventory_max: int = 0
    """The bag's quantity cap: the server's `inventory_max_items` total, which
    a worn bag's `inventory_space` raises. The total IS a `WorldState` field
    (`inventory_max`), so a bag projects as a delta like every stat above.
    Projected since spec 2026-10-18 §2.10 counted the loop's bank trips: a
    bigger bag fills less often (`loop_rate`'s capacity)."""


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
    haste = state.haste
    inventory_max = state.inventory_max

    for slot, new_code in loadout.items():
        old_code = state.equipment.get(slot)
        if slot in UTILITY_SLOTS:
            # The sheet never holds a worn potion (module doc): nothing to take off.
            if new_code == old_code and utility_slot_quantity(state, slot) == 0:
                new_code = None
            old_code = None
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
        # swap is (new contribution - old contribution).
        wisdom += (new_s.wisdom if new_s else 0) - (old_s.wisdom if old_s else 0)
        prospecting += ((new_s.prospecting if new_s else 0)
                        - (old_s.prospecting if old_s else 0))
        haste += (new_s.haste if new_s else 0) - (old_s.haste if old_s else 0)
        inventory_max += ((new_s.inventory_space if new_s else 0)
                          - (old_s.inventory_space if old_s else 0))

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
        haste=haste,
        inventory_max=inventory_max,
    )


def with_totals(state: WorldState, totals: ProjectedStats,
                equipment: dict[str, str | None], *, hp: int) -> WorldState:
    """`state` wearing `equipment` with its sheet totals set to `totals` and
    current HP `hp`: THE one field list from `ProjectedStats` to `WorldState`,
    read by every reader that carries a projected swap onto a state
    (`wear_gear`, `gear_objective._wearing`), so a projected stat is carried
    by all of them or by none (final review minor 9)."""
    return dataclasses.replace(
        state,
        equipment=equipment,
        attack=totals.attack,
        dmg=totals.dmg,
        dmg_elements=totals.dmg_elements,
        resistance=totals.resistance,
        critical_strike=totals.critical_strike,
        initiative=totals.initiative,
        max_hp=totals.max_hp,
        hp=hp,
        wisdom=totals.wisdom,
        prospecting=totals.prospecting,
        haste=totals.haste,
        inventory_max=totals.inventory_max,
    )


def wear_gear(state: WorldState, equipment: dict[str, str | None],
              game_data: GameData) -> WorldState:
    """`state` wearing `equipment`, its totals moved by the gear it changes.

    The sheet's invariant (measured live, Task 14b): totals = base + the worn
    NON-utility gear. A planned equip, unequip or re-arm keeps it by moving the
    totals through `project_loadout_stats`, the one stat arithmetic: each gear
    slot that changes adds its new item's stats and takes off the old one's.
    A utility slot moves no total (module doc), so it is left out of the swap
    and only its code changes.

    Current HP is clamped to a lowered max HP: the server does (learning.db
    2026-10-30: of 798 equip/re-arm cycles whose max HP fell below the HP
    before, 784 read hp == the new max_hp and none of 567,610 recorded sheets
    reads hp > max_hp). `project_loadout_stats` does not clamp: it projects
    a fight's stats, whose HP the fight terms clamp themselves."""
    gear = {slot: code for slot, code in equipment.items()
            if slot not in UTILITY_SLOTS}
    totals = project_loadout_stats(state, gear, game_data)
    return with_totals(
        state, totals, equipment,
        hp=min(state.hp, totals.max_hp),
    )
