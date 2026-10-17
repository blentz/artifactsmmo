"""Differential pin for the `winnableAcrossBand_grounded` witness table.

The kernel proof (`Formal/Liveness/WinnableGrounded.lean`) verifies a per-level
WITNESS extracted from the Task-1 sweep: for each band level `L in [1, 49]` the
winning monster + the `pick_loadout` loadout + production `fight_split`'s
fight-odds `Terms`/`Damage` with the fight's HP, max HP and worn restore. The
kernel decides the counted-crit floor `Formal.FightOdds.critBound` over those
scalars against `witnessTheta` = 99/100 and lifts it to P(win) at every
θ <= 99/100 (`winProb_ge_critBound`); it TRUSTS the scalars only as far as THIS
test enforces them against production.

This is the ANTI-RIGGING gate. For every witness row it asserts:

  1. the emitted player-projection scalars (`p_crit`, `p_max_hp`,
     `p_initiative`, `p_crit_hit`, `p_lifesteal`, `p_antipoison`, `raw_player`,
     `raw_monster`, `player_first`) EQUAL what production `project_loadout_stats`
     (+ `predict_win`'s own element-damage sums) produce for the witness loadout
     at level `L` — the projection is faithful, not reverse-engineered;
  2. production `is_winnable`(witness loadout, witness monster) is True at `L`;
  3. every loadout item's `level <= L` (obtainable, backed by Task 3's
     `canonicalPlan` obtainability); and
  4. the witness monster is not over-leveled (`monster_level <= L + 2`) and the
     row's monster scalars match the live catalog;
  5. the fight-odds scalars (`t_*`, `d_*`, `fight_hp`, `fight_max_hp`,
     `restore`, `stock`) EQUAL production `fight_numbers` / `fight_split` /
     `fight_max_hp` / `worn_restore` for the witness monster at `L`;
  6. the Python mirror of the kernel's `critBound` over those scalars is at
     least `WITNESS_THETA` and never above production's exact P(win) (a floor,
     not an estimate); and
  7. the rows EMITTED into `GameDataFixture.lean` (both `winnableWitness` and
     `acquirableWitness`) carry exactly those scalars and crit budget — so the
     table the kernel decides is the one pinned here.

Skips cleanly when the real fixtures are absent (CI / `formal/gate.sh` stay
green until the data is captured), mirroring `test_winnable_across_band_diff.py`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from artifactsmmo_cli.ai.combat import (
    _crit_hit,
    _element_damage,
    fight_max_hp,
    fight_numbers,
    fight_split,
    is_winnable,
    worn_restore,
)
from artifactsmmo_cli.ai.elements import ELEMENTS
from artifactsmmo_cli.ai.equipment.level_loadout import (
    obtainable_hp_bonus_ceiling,
    obtainable_inventory_for_level,
)
from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout
from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats
from artifactsmmo_cli.ai.fight_odds_core import fight_odds, win_probability
from artifactsmmo_cli.ai.gear_value_core import Combat
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
from formal.sim.generate_lean_fixture import _acquirability_closure
from formal.sim.winnable_witness import (
    WITNESS_THETA,
    WitnessRow,
    _base_world_state,
    build_witness_row,
    build_witness_table,
    crit_bound,
)

FIXTURE = Path(__file__).resolve().parents[1] / "Formal/Liveness/GameDataFixture.lean"

# The fixture fields the kernel's fight-odds verdict reads, and the WitnessRow
# attribute each one is emitted from.
_ODDS_FIELDS = {
    "tRawPlayer": "t_raw_player", "tKillStep": "t_kill_step",
    "tMonsterHp": "t_monster_hp", "tRecon": "t_recon", "tDieStep": "t_die_step",
    "tPlayerFirst": "t_player_first", "dMonsterHp": "d_monster_hp",
    "dKillNormal": "d_kill_normal", "dKillCrit": "d_kill_crit", "dPCrit": "d_p_crit",
    "dDieNormal": "d_die_normal", "dDieCrit": "d_die_crit", "dMCrit": "d_m_crit",
    "dBurn": "d_burn", "dPHeal": "d_p_heal", "dMHeal": "d_m_heal", "fightHp": "fight_hp", "fightMaxHp": "fight_max_hp",
    "restore": "restore", "stock": "stock", "critBudget": "crit_budget",
}

_FIELD_RE = re.compile(r"(\w+) := (\[[^\]]*\]|\"[^\"]*\"|-?\d+|true|false)")


def _lean_value(value: object) -> str:
    """A WitnessRow attribute as the generator writes it into the fixture."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, tuple):
        return "[" + ", ".join(str(v) for v in value) + "]"
    return str(value)


def _emitted_rows(table: str) -> list[dict[str, str]]:
    """The `table` rows of `GameDataFixture.lean`, each as field -> Lean literal."""
    src = FIXTURE.read_text()
    body = src[src.index(f"def {table} : List WitnessRow :="):]
    body = body[:body.index("\n  ]\n")]
    return [{"level": chunk.split(",", 1)[0], **dict(_FIELD_RE.findall(chunk))}
            for chunk in body.split("{ level := ")[1:]]


def _assert_emitted(table: str, rows: list[WitnessRow]) -> None:
    """The fixture's `table` carries exactly `rows`' fight-odds scalars."""
    emitted = _emitted_rows(table)
    assert len(emitted) == len(rows), f"{table}: {len(emitted)} emitted vs {len(rows)} built"
    for lean, row in zip(emitted, rows, strict=True):
        assert int(lean["level"]) == row.level, f"{table} level order"
        for field, attr in _ODDS_FIELDS.items():
            assert lean[field] == _lean_value(getattr(row, attr)), (
                f"{table} L{row.level} {field}: emitted {lean[field]} != "
                f"{_lean_value(getattr(row, attr))}"
            )


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
    captured = {int(lvl) for lvl in base_stats}
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
        loadout = pick_loadout(
            Combat(game_data.monster_attack(row.monster_code),
                   game_data.monster_resistance(row.monster_code),
                   dict(state.attack)), state, game_data)
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
        assert row.p_crit_hit == _crit_hit(p.attack, p.dmg, p.dmg_elements, m_resist), (
            f"L{row.level} p_crit_hit")
        assert row.p_lifesteal == p_lifesteal, f"L{row.level} p_lifesteal"
        assert row.p_antipoison == p_antipoison, f"L{row.level} p_antipoison"
        assert row.raw_player == raw_player, f"L{row.level} raw_player"
        assert row.raw_monster == raw_monster, f"L{row.level} raw_monster"
        m_init = game_data.monster_initiative(row.monster_code)
        assert row.player_first == (
            p.initiative > m_init
            or (p.initiative == m_init and state.hp > game_data.monster_hp(row.monster_code))
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
        assert row.m_crit_hit == _crit_hit(m_attack, 0, {}, p.resistance), f"L{row.level} m_crit_hit"

        # (5) fight-odds fidelity: the scalars the kernel decides are production's.
        numbers = fight_numbers(state, game_data, row.monster_code)
        terms, damage = fight_split(state, game_data, row.monster_code)
        max_hp = fight_max_hp(state, game_data, row.monster_code)
        restore, stock = worn_restore(state, game_data)
        assert (terms, damage) == (numbers.terms, numbers.damage), f"L{row.level} split"
        assert row.t_raw_player == numbers.raw_player, f"L{row.level} t_raw_player"
        assert row.t_kill_step == terms.kill_step, f"L{row.level} t_kill_step"
        assert row.t_monster_hp == damage.monster_hp, f"L{row.level} t_monster_hp"
        assert row.t_recon == game_data.monster_reconstitution(row.monster_code)
        assert row.t_die_step == terms.die_step, f"L{row.level} t_die_step"
        assert row.t_player_first == terms.player_first, f"L{row.level} t_player_first"
        assert (row.d_monster_hp, row.d_kill_normal, row.d_kill_crit, row.d_p_crit,
                row.d_die_normal, row.d_die_crit, row.d_m_crit, row.d_burn,
                row.d_p_heal, row.d_m_heal) == (
            damage.monster_hp, damage.kill_normal, damage.kill_crit, damage.p_crit,
            damage.die_normal, damage.die_crit, damage.m_crit, damage.burn,
            damage.p_heal, damage.m_heal,
        ), f"L{row.level} damage"
        assert (row.fight_hp, row.fight_max_hp) == (state.hp, max_hp), f"L{row.level} hp"
        assert (row.restore, row.stock) == (restore, stock), f"L{row.level} restore"

        # (6) the floor the kernel decides holds, and is a floor of the exact odds.
        bound = crit_bound(terms, damage, state.hp, max_hp, row.crit_budget)
        assert bound >= WITNESS_THETA, (
            f"L{row.level}: crit_bound {float(bound)} < {WITNESS_THETA} — the "
            f"witness row would not pass the kernel decide."
        )
        exact = win_probability(fight_odds(terms, damage, state.hp, max_hp, restore, stock))
        assert bound <= exact, f"L{row.level}: floor {bound} above exact P(win) {exact}"

        # xp-positive at this level (the xpPos band condition).
        assert game_data.xp_per_kill(row.monster_code, row.level) > 0, (
            f"L{row.level}: {row.monster_code} grants no XP"
        )

    # (7) the emitted fixture table is the table pinned above.
    _assert_emitted("winnableWitness", rows)


def test_acquirable_rows_pin_fight_odds() -> None:
    """The cert-restricted table the kernel also decides (`acquirableWitness`,
    `WitnessAcquirable.acquirable_rows_winnable`): every band level has a row,
    each row's production `is_winnable` is True and its floor is at least
    `WITNESS_THETA`, and the fixture carries exactly those scalars."""
    loaded = _load_real_inputs()
    if loaded is None:
        pytest.skip("real fixtures absent (see test_winnable_across_band_diff.py).")
    base_stats, stats_by_code, game_data = loaded
    _gather, _drops, cert = _acquirability_closure(json.loads(SNAPSHOT_PATH.read_text()))
    acq_stats = {c: st for c, st in stats_by_code.items() if c in set(cert)}
    rows = []
    for level in range(BAND_LO, BAND_HI):
        row = build_witness_row(level, base_stats[str(level)], acq_stats, game_data)
        assert row is not None, f"L{level}: no acquirable witness (a frontier level)"
        state = _base_world_state(
            level, base_stats[str(level)], obtainable_inventory_for_level(acq_stats, level),
            obtainable_hp_bonus_ceiling(acq_stats, level))
        assert is_winnable(state, game_data, row.monster_code) is True, f"L{level} is_winnable"
        terms, damage = fight_split(state, game_data, row.monster_code)
        bound = crit_bound(terms, damage, state.hp,
                           fight_max_hp(state, game_data, row.monster_code), row.crit_budget)
        assert bound >= WITNESS_THETA, f"L{level}: crit_bound {float(bound)} < {WITNESS_THETA}"
        rows.append(row)
    _assert_emitted("acquirableWitness", rows)
