"""Per-level WITNESS builder for the kernel `winnableAcrossBand_grounded` proof.

The Task-1 sweep (`formal/diff/test_winnable_across_band_diff.py`) already
verified, with production's real `is_winnable`, that `WinnableAcrossBand` holds
49/49 over the live catalog under the best-full-obtainable-loadout + full-HP
model. This module re-runs that exact production chain and, for each band level
`L in [1, 49]`, records the WITNESS the kernel proof verifies:

  * the winning monster code chosen by `pick_winnable_monster_pure`;
  * the `pick_loadout` loadout item codes (every item `level <= L`);
  * the production-projected player combat scalars from `project_loadout_stats`
    (`p.attack` per element, `p.critical_strike`, `p.max_hp`, `p.initiative`,
    `p.dmg`, `p.dmg_elements`, player lifesteal / antipoison summed over the
    loadout) — the exact inputs `predict_win` reads; and
  * the 20 integer `predictWin` inputs + the `playerFirst` boolean, computed
    EXACTLY as `predict_win` computes them internally (reusing production's
    `_element_damage`), so the kernel `predictWin` over these scalars reproduces
    production's verdict.

The kernel TRUSTS this projection only as far as the differential
(`formal/diff/test_winnable_witness_diff.py`) enforces it against production:
that test re-derives each row's projection scalars from `project_loadout_stats`
and asserts the verdict equals production `is_winnable`. So the witness reflects
production — it is never reverse-engineered to pass the kernel `decide`.

The witness rows are consumed by `generate_lean_fixture.py` to emit
`def winnableWitness : List WitnessRow` into `GameDataFixture.lean`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from artifactsmmo_cli.ai.combat import _element_damage, is_winnable
from artifactsmmo_cli.ai.combat_picker import pick_winnable_monster_pure
from artifactsmmo_cli.ai.elements import ELEMENTS
from artifactsmmo_cli.ai.equipment.level_loadout import (
    obtainable_hp_bonus_ceiling,
    obtainable_inventory_for_level,
)
from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout
from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_value_core import Combat
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.world_state import WorldState

# Leveling band from `GearTierLeveling.InLevelingBand`: 1 <= L < 50.
BAND_LO = 1
BAND_HI = 50  # exclusive

# item_stats keys that prove the snapshot carries combat fields (an OLD snapshot
# has only level/type/crafting_* — no `attack`).
COMBAT_FIELD_MARKER = "attack"

# Monster effect maps absent from the snapshot default to 0 (matching GameData's
# 0-fallback) — exactly what predict_win sees for an effect-less monster.
_MONSTER_EFFECT_ATTRS = (
    "_monster_lifesteal", "_monster_poison", "_monster_barrier",
    "_monster_burn", "_monster_healing", "_monster_reconstitution",
    "_monster_void_drain", "_monster_berserker_rage", "_monster_frenzy",
    "_monster_protective_bubble", "_monster_corrupted",
)


def snapshot_has_combat_fields(snapshot: dict[str, Any]) -> bool:
    """True iff the snapshot's item_stats carry the combat fields the witness
    needs (an OLD snapshot has only level/type/crafting_*)."""
    item_stats = snapshot.get("item_stats")
    if not item_stats:
        return False
    sample = next(iter(item_stats.values()))
    return COMBAT_FIELD_MARKER in sample


def item_stats_from_snapshot(snapshot: dict[str, Any]) -> dict[str, ItemStats]:
    """Reconstruct the `code -> ItemStats` catalog from the snapshot's combat
    fields (the same fields `snapshot_game_data.py` writes)."""
    out: dict[str, ItemStats] = {}
    for code, row in snapshot["item_stats"].items():
        out[code] = ItemStats(
            code=code, level=row["level"], type_=row["type"],
            crafting_skill=row.get("crafting_skill"),
            crafting_level=row.get("crafting_level", 0),
            attack=dict(row.get("attack", {})),
            resistance=dict(row.get("resistance", {})),
            dmg=row.get("dmg", 0), dmg_elements=dict(row.get("dmg_elements", {})),
            critical_strike=row.get("critical_strike", 0),
            initiative=row.get("initiative", 0), hp_bonus=row.get("hp_bonus", 0),
            lifesteal=row.get("lifesteal", 0), antipoison=row.get("antipoison", 0),
            subtype=row.get("subtype", ""),
        )
    return out


def game_data_from_snapshot(
    snapshot: dict[str, Any], stats_by_code: dict[str, ItemStats],
) -> GameData:
    """Build a `GameData` carrying the snapshot's monster catalog + item stats.
    Monster effect maps default to 0 (matching GameData's own 0-fallback)."""
    gd = GameData()
    gd._item_stats = dict(stats_by_code)
    gd._monster_level = dict(snapshot["monster_level"])
    gd._monster_hp = dict(snapshot["monster_hp"])
    gd._monster_attack = {k: dict(v) for k, v in snapshot["monster_attack"].items()}
    gd._monster_resistance = {
        k: dict(v) for k, v in snapshot["monster_resistance"].items()
    }
    gd._monster_critical_strike = dict(snapshot["monster_critical_strike"])
    gd._monster_initiative = dict(snapshot["monster_initiative"])
    codes = list(snapshot["monster_level"].keys())
    gd._monster_type = {code: "normal" for code in codes}
    for attr in _MONSTER_EFFECT_ATTRS:
        setattr(gd, attr, {code: 0 for code in codes})
    return gd


@dataclass(frozen=True)
class WitnessRow:
    """One band level's verified winnability witness — the exact data the kernel
    `winnableAcrossBand_grounded` proof verifies (mirrors Lean `WitnessRow`)."""

    level: int
    monster_code: str
    monster_level: int
    loadout_codes: list[str]
    # Player-projection scalars (pinned to `project_loadout_stats` by the diff).
    p_crit: int
    p_max_hp: int
    p_initiative: int
    p_atk_sum: int
    p_lifesteal: int
    p_antipoison: int
    # The 20 integer `predictWin` inputs + playerFirst (computed as predict_win does).
    raw_player: int
    monster_hp: int
    raw_monster: int
    m_crit: int
    m_atk_sum: int
    m_lifesteal: int
    m_poison: int
    m_barrier: int
    m_burn: int
    m_healing: int
    m_reconstitution: int
    m_void_drain: int
    m_berserk: int
    m_frenzy: int
    m_bubble: int
    player_first: bool


def _base_world_state(
    level: int, base_row: dict[str, Any], inventory: dict[str, int],
    hp_bonus_ceiling: int,
) -> WorldState:
    """Faithful level-`level` combat WorldState (base stats, no gear equipped,
    full obtainable inventory, full projected HP) — identical to the Task-1
    sweep's construction so the loadout the kernel verifies is the one production
    picks at that band."""
    base_attack = {e: v for e, v in base_row["attack"].items() if v != 0}
    base_resistance = {e: v for e, v in base_row["resistance"].items() if v != 0}
    return WorldState(
        character="witness", level=level, xp=0, max_xp=999999,
        hp=base_row["max_hp"] + hp_bonus_ceiling, max_hp=base_row["max_hp"],
        gold=0, skills={}, x=0, y=0, inventory=inventory, inventory_max=40,
        equipment={}, cooldown_expires=None, task_code=None, task_type=None,
        task_progress=0, task_total=0, bank_items=None, bank_gold=None,
        pending_items=None, attack=base_attack, dmg=0, dmg_elements={},
        resistance=base_resistance, critical_strike=base_row["critical_strike"],
        initiative=base_row["initiative"],
    )


def build_witness_row(
    level: int, base_row: dict[str, Any], stats_by_code: dict[str, ItemStats],
    game_data: GameData,
) -> WitnessRow | None:
    """Production-driven witness for one band level, or `None` if no winnable
    in-band target exists (a real `WinnableAcrossBand` gap).

    Runs the SAME chain as the Task-1 sweep: full obtainable inventory ->
    faithful WorldState -> `pick_winnable_monster_pure` over the live catalog
    with the real `is_winnable`. For the chosen monster it then runs
    `pick_loadout` + `project_loadout_stats` (production) and computes the
    `predict_win` integer scalars EXACTLY as production does internally.
    """
    inventory = obtainable_inventory_for_level(stats_by_code, level)
    hp_ceiling = obtainable_hp_bonus_ceiling(stats_by_code, level)
    state = _base_world_state(level, base_row, inventory, hp_ceiling)
    monster_code = pick_winnable_monster_pure(
        level,
        list(game_data.monster_levels.items()),
        lambda code: is_winnable(state, game_data, code),
        lambda code: game_data.xp_per_kill(code, level) > 0,
    )
    if monster_code is None:
        return None

    loadout = pick_loadout(
        Combat(game_data.monster_attack(monster_code),
               game_data.monster_resistance(monster_code)), state, game_data)
    p = project_loadout_stats(state, loadout, game_data)
    m_resist = game_data.monster_resistance(monster_code)
    m_attack = game_data.monster_attack(monster_code)

    # raw_player / raw_monster — exactly predict_win's per-element damage sums.
    raw_player = sum(
        _element_damage(p.attack.get(e, 0), p.dmg + p.dmg_elements.get(e, 0),
                        m_resist.get(e, 0))
        for e in ELEMENTS
    )
    raw_monster = sum(
        _element_damage(m_attack.get(e, 0), 0, p.resistance.get(e, 0))
        for e in ELEMENTS
    )

    final_equip = dict(state.equipment)
    final_equip.update(loadout)
    p_lifesteal = sum(
        st.lifesteal for code in final_equip.values()
        if code and (st := game_data.item_stats(code)) is not None
    )
    p_antipoison = sum(
        st.antipoison for code in final_equip.values()
        if code and (st := game_data.item_stats(code)) is not None
    )

    # Loadout codes that pick_loadout actually selected (slot -> code | None).
    loadout_codes = sorted(c for c in loadout.values() if c)

    return WitnessRow(
        level=level,
        monster_code=monster_code,
        monster_level=game_data.monster_level(monster_code),
        loadout_codes=loadout_codes,
        p_crit=p.critical_strike,
        p_max_hp=p.max_hp,
        p_initiative=p.initiative,
        p_atk_sum=sum(p.attack.values()),
        p_lifesteal=p_lifesteal,
        p_antipoison=p_antipoison,
        raw_player=raw_player,
        monster_hp=game_data.monster_hp(monster_code),
        raw_monster=raw_monster,
        m_crit=game_data.monster_critical_strike(monster_code),
        m_atk_sum=sum(m_attack.values()),
        m_lifesteal=game_data.monster_lifesteal(monster_code),
        m_poison=game_data.monster_poison(monster_code),
        m_barrier=game_data.monster_barrier(monster_code),
        m_burn=game_data.monster_burn(monster_code),
        m_healing=game_data.monster_healing(monster_code),
        m_reconstitution=game_data.monster_reconstitution(monster_code),
        m_void_drain=game_data.monster_void_drain(monster_code),
        m_berserk=game_data.monster_berserker_rage(monster_code),
        m_frenzy=game_data.monster_frenzy(monster_code),
        m_bubble=game_data.monster_protective_bubble(monster_code),
        player_first=p.initiative >= game_data.monster_initiative(monster_code),
    )


def build_witness_table(
    base_stats: dict[str, dict[str, Any]],
    stats_by_code: dict[str, ItemStats],
    game_data: GameData,
) -> list[WitnessRow]:
    """Witness rows for every band level with captured base stats. Raises if any
    captured band level has no winnable in-band target (a `WinnableAcrossBand`
    gap) — the witness table must cover every band level the kernel proof needs."""
    rows: list[WitnessRow] = []
    gaps: list[int] = []
    for level in range(BAND_LO, BAND_HI):
        base_row = base_stats.get(str(level))
        if base_row is None:
            continue
        row = build_witness_row(level, base_row, stats_by_code, game_data)
        if row is None:
            gaps.append(level)
        else:
            rows.append(row)
    if gaps:
        raise ValueError(
            f"WinnableAcrossBand gap at band level(s) {gaps}: no winnable, "
            f"XP-positive, not-overleveled monster — the witness table cannot "
            f"cover these levels for the kernel proof."
        )
    return rows
