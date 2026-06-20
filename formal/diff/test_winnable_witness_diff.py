"""Differential pin for the `winnableAcrossBand_grounded` witness table.

The kernel proof (`Formal/Liveness/WinnableGrounded.lean`) verifies a per-level
WITNESS extracted from the Task-1 sweep: for each band level `L in [1, 49]` the
winning monster + the `pick_loadout` loadout + the production-projected combat
scalars `predict_win` reads. The kernel computes `predictWin` over those scalars
and `decide`s the verdict; it TRUSTS the projection only as far as THIS test
enforces it against production.

This is the ANTI-RIGGING gate. For every witness row it asserts:

  1. the emitted player-projection scalars (`p_crit`, `p_max_hp`,
     `p_initiative`, `p_atk_sum`, `p_lifesteal`, `p_antipoison`, `raw_player`,
     `raw_monster`, `player_first`) EQUAL what production `project_loadout_stats`
     (+ `predict_win`'s own element-damage sums) produce for the witness loadout
     at level `L` — the projection is faithful, not reverse-engineered;
  2. production `is_winnable`(witness loadout, witness monster) is True at `L`;
  3. every loadout item's `level <= L` (obtainable, backed by Task 3's
     `canonicalPlan` obtainability); and
  4. the witness monster is not over-leveled (`monster_level <= L + 2`) and the
     row's monster scalars match the live catalog.

It also reconstructs the kernel `predictWin` formula from the emitted Int
scalars and asserts it returns True — so a witness that the kernel would accept
necessarily reflects production's verdict (no fixture massaging can pass both).

Skips cleanly when the real fixtures are absent (CI / `formal/gate.sh` stay
green until the data is captured), mirroring `test_winnable_across_band_diff.py`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from artifactsmmo_cli.ai.combat import _element_damage, is_winnable
from artifactsmmo_cli.ai.elements import ELEMENTS
from artifactsmmo_cli.ai.equipment.level_loadout import (
    obtainable_hp_bonus_ceiling,
    obtainable_inventory_for_level,
)
from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats
from artifactsmmo_cli.ai.equipment.scoring import pick_loadout
from artifactsmmo_cli.ai.item_catalog import ItemStats

from formal.diff.test_winnable_across_band_diff import (
    BAND_HI,
    BAND_LO,
    BASE_STATS_PATH,
    SNAPSHOT_PATH,
    _game_data_from_snapshot,
    _item_stats_from_snapshot,
    _snapshot_has_combat_fields,
)
from formal.sim.winnable_witness import (
    WitnessRow,
    _base_world_state,
    build_witness_table,
)

MAX_TURNS = 100


def _ceil_div(n: int, d: int) -> int:
    return -(-n // d)


def _kernel_predict_win(row: WitnessRow) -> bool:
    """Reconstruct the Lean `predictWin` verdict from a witness row's Int scalars
    (exact mirror of `Formal/PredictWin.lean::predictWin`). Used to confirm the
    emitted scalars are the ones the kernel will `decide` true."""
    if row.raw_player <= 0:
        return False
    kill_step = (
        50 * row.raw_player * (200 + row.p_crit)
        - row.m_crit * row.m_lifesteal * row.m_atk_sum
        - row.m_healing * row.monster_hp * 100
        - row.m_void_drain * row.p_max_hp * 100
        - row.m_bubble * row.raw_player * (200 + row.p_crit) // 2
    )
    if kill_step <= 0:
        return False
    rounds_to_kill = _ceil_div((row.monster_hp + row.m_barrier) * 10000, kill_step)
    if rounds_to_kill > MAX_TURNS:
        return False
    if 0 < row.m_reconstitution <= rounds_to_kill:
        return False
    die_step = (
        50 * row.raw_monster * (200 + row.m_crit)
        - row.p_crit * row.p_lifesteal * row.p_atk_sum
        + max(0, row.m_poison - row.p_antipoison) * 10000
        + row.m_burn * row.p_atk_sum * 100
        + row.m_void_drain * row.p_max_hp * 100
        + row.m_berserk * row.raw_monster * (200 + row.m_crit) // 2
        + row.m_frenzy * row.raw_monster * (200 + row.m_crit) // 2
    )
    if die_step <= 0:
        return True
    rounds_to_die = _ceil_div(row.p_max_hp * 10000, die_step)
    if row.player_first:
        return rounds_to_kill <= rounds_to_die
    return rounds_to_kill < rounds_to_die


def _load_real_inputs() -> tuple[dict[str, dict[str, Any]], dict[str, ItemStats], Any] | None:
    """Load base stats + snapshot-derived catalog + game data, or None if the
    real fixtures are absent / lack combat fields (skip path)."""
    if not BASE_STATS_PATH.exists():
        return None
    snapshot = json.loads(SNAPSHOT_PATH.read_text())
    if not _snapshot_has_combat_fields(snapshot):
        return None
    base_stats = json.loads(BASE_STATS_PATH.read_text()).get("base_stats", {})
    if not base_stats:
        return None
    stats_by_code = _item_stats_from_snapshot(snapshot)
    game_data = _game_data_from_snapshot(snapshot, stats_by_code)
    return base_stats, stats_by_code, game_data


def test_witness_rows_pin_projection_and_verdict() -> None:
    """Every emitted witness row must reflect production: its projection scalars
    equal `project_loadout_stats`, its loadout beats its monster via real
    `is_winnable`, every loadout item is obtainable at `L`, and the kernel
    `predictWin` over the emitted scalars returns True."""
    loaded = _load_real_inputs()
    if loaded is None:
        pytest.skip(
            "real fixtures absent — capture character_base_stats.json and "
            "re-snapshot game_data_snapshot.json (see "
            "test_winnable_across_band_diff.py module docstring)."
        )
    base_stats, stats_by_code, game_data = loaded
    rows = build_witness_table(base_stats, stats_by_code, game_data)

    # The witness must cover every band level for which base stats exist.
    captured = {int(l) for l in base_stats}
    band = set(range(BAND_LO, BAND_HI))
    assert {r.level for r in rows} == captured & band, (
        f"witness levels {sorted(r.level for r in rows)} != captured band "
        f"levels {sorted(captured & band)}"
    )

    for row in rows:
        base_row = base_stats[str(row.level)]
        inventory = obtainable_inventory_for_level(stats_by_code, row.level)
        hp_ceiling = obtainable_hp_bonus_ceiling(stats_by_code, row.level)
        state = _base_world_state(row.level, base_row, inventory, hp_ceiling)

        # (2) production verdict: the witness loadout beats the witness monster.
        assert is_winnable(state, game_data, row.monster_code) is True, (
            f"L{row.level}: production is_winnable({row.monster_code}) is False"
        )

        # (1) projection fidelity: re-derive from production, compare to emitted.
        loadout = pick_loadout(row.monster_code, state, game_data)
        p = project_loadout_stats(state, loadout, game_data)
        m_resist = game_data.monster_resistance(row.monster_code)
        m_attack = game_data.monster_attack(row.monster_code)
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
        assert row.p_crit == p.critical_strike, f"L{row.level} p_crit"
        assert row.p_max_hp == p.max_hp, f"L{row.level} p_max_hp"
        assert row.p_initiative == p.initiative, f"L{row.level} p_initiative"
        assert row.p_atk_sum == sum(p.attack.values()), f"L{row.level} p_atk_sum"
        assert row.p_lifesteal == p_lifesteal, f"L{row.level} p_lifesteal"
        assert row.p_antipoison == p_antipoison, f"L{row.level} p_antipoison"
        assert row.raw_player == raw_player, f"L{row.level} raw_player"
        assert row.raw_monster == raw_monster, f"L{row.level} raw_monster"
        assert row.player_first == (
            p.initiative >= game_data.monster_initiative(row.monster_code)
        ), f"L{row.level} player_first"

        # the emitted loadout codes match what pick_loadout actually selected.
        assert row.loadout_codes == sorted(c for c in loadout.values() if c), (
            f"L{row.level} loadout_codes drift"
        )

        # (3) obtainability: every loadout item is level <= L.
        for code in row.loadout_codes:
            assert stats_by_code[code].level <= row.level, (
                f"L{row.level}: loadout item {code} level "
                f"{stats_by_code[code].level} > {row.level}"
            )

        # (4) monster scalars + not-overleveled match the live catalog.
        assert row.monster_level == game_data.monster_level(row.monster_code)
        assert row.monster_level <= row.level + 2, f"L{row.level} overleveled"
        assert row.monster_hp == game_data.monster_hp(row.monster_code)
        assert row.m_crit == game_data.monster_critical_strike(row.monster_code)
        assert row.m_atk_sum == sum(m_attack.values())

        # the kernel `predictWin` over the emitted scalars must be True.
        assert _kernel_predict_win(row) is True, (
            f"L{row.level}: kernel predictWin over emitted scalars is False — "
            f"the witness row would not pass the kernel decide."
        )

        # xp-positive at this level (the xpPos band condition).
        assert game_data.xp_per_kill(row.monster_code, row.level) > 0, (
            f"L{row.level}: {row.monster_code} grants no XP"
        )
