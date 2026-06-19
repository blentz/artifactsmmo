"""Differential sweep — validate the Lean residual `WinnableAcrossBand` against
live data by running PRODUCTION's real `is_winnable` per character level.

Workstream B Phase-1 final infra for `docs/PLAN_faithfulness_modeling.md`.

## The Lean claim this validates

`Formal/Liveness/GearTierLeveling.lean` defines

    InLevelingBand L := 1 ≤ L ∧ L < 50
    notOverleveled L m := decide (m.level ≤ L + 2)
    WinnableAcrossBand winnable xpPos xs :=
      ∀ L, InLevelingBand L → ∃ m ∈ xs,
        winnable m ∧ xpPos m ∧ notOverleveled L m

i.e. for EVERY character level `L` in the leveling band `[1, 50)`, the live
monster catalog contains a monster that is winnable, XP-positive, and not
over-leveled (`m.level ≤ L + 2`). This sweep checks that claim against the live
catalog using production's REAL beatability verdict — not a re-implemented
formula. The downstream picker theorem
(`combatTargetExists_of_gearTier`) shows this hypothesis grounds combat-target
existence at every band level; here we test the hypothesis itself, empirically.

## How the faithful level-L WorldState is built (THE CRUX)

`is_winnable(state, gd, code)` → `predict_win` → `pick_loadout(code, state, gd)`
picks the best loadout from the items the character OWNS, then
`project_loadout_stats(state, loadout, gd)` returns the projected combat totals
as `state.<stat> + Σ_slot (picked − equipped)`. `predict_win` reads ONLY the
projected stats (`p.attack[e]`, `p.max_hp`, `p.resistance[e]`,
`p.critical_strike`, `p.initiative`, `p.dmg`, `p.dmg_elements`) plus `state.hp`.

So to feed `is_winnable` the totals `base + best_weapon`, we construct the
WorldState as:

  * stat fields (`attack`, `max_hp`, `resistance`, `critical_strike`,
    `initiative`, `dmg`, `dmg_elements`) = the captured per-level BASE stats,
    with NO gear baked in;
  * `equipment = {}` (nothing equipped) so the weapon contributes its FULL
    stats (no `new == old` cancellation in projection);
  * `inventory = {weapon.code: 1}` so `pick_loadout`'s owned-item scan finds
    the weapon as the sole weapon-slot candidate and equips it;
  * `level = L` so `state.level >= weapon.level` (the `_candidates_for_slot`
    gate) — the best weapon is `item.level <= L` by construction;
  * `hp = projected_max_hp = base.max_hp + weapon.hp_bonus` so
    `effective_hp = min(state.hp, p.max_hp) == p.max_hp` — i.e. the verdict is
    rendered at FULL projected HP (a character entering a fight rested).

After `pick_loadout` equips the weapon, `project_loadout_stats` adds the
weapon's `attack`, `dmg`, `dmg_elements`, `resistance`, `critical_strike`,
`initiative`, `hp_bonus` on top of the base fields. The totals fed to
`predict_win` therefore equal **base + best weapon** — exactly the claim's
projected player. We call the REAL `is_winnable` / `pick_winnable_monster_pure`
/ `xp_per_kill` — never a re-derived predicate.

## SOUNDNESS GAP (documented, not hidden)

This is the OPTIMISTIC-WEAPON proxy and it is intentionally one-sided:

  1. ONLY the weapon is modelled. Base armor/ring/amulet/utility contributions
     are NOT added beyond the captured base. Real gear ADDS attack/resistance/
     hp/crit, so the real character is at least as strong as this proxy ⇒ any
     monster this proxy calls winnable is winnable for the real (better-geared)
     character too. The proxy is CONSERVATIVE for "winnable exists": a gap it
     reports (no winnable at level L) could still be closed by armor the proxy
     ignores, so a reported gap is an UPPER BOUND on the true gap, not proof of
     one. (`best_weapon_for_level` is the catalog-wide upper bound on the weapon
     itself; the proxy is optimistic about ACQUISITION — the bot may not yet own
     the best weapon — and pessimistic about non-weapon gear.)
  2. Monster effect maps (poison/lifesteal/…) are whatever the snapshot
     carries; the live snapshot currently only captures the core monster stats,
     so exotic abilities default to 0 (matching `GameData`'s 0-fallback). This
     matches what `predict_win` sees for a monster with no captured effects.

## Skip-on-missing-data

The real fixtures do not exist until the user captures them:
  * `formal/sim/character_base_stats.json` — produced by
    `uv run python formal/sim/capture_base_stats.py <character>` (run once per
    level over a real session; RESUMABLE).
  * The snapshot's `item_stats` must carry combat fields (attack/hp_bonus/…);
    re-run `uv run python formal/sim/snapshot_game_data.py` against the live API
    (the writer now emits them; an OLD snapshot predates them).
When either is absent the real sweep `pytest.skip(...)`s with a message naming
the missing fixture + how to produce it, so CI / `formal/gate.sh` stay GREEN
until the data is captured.

## Placement

`formal/diff/` has NO module-level pytest marker and no per-file skip; the
files run in the default `pytest` collection (gated by coverage config, run in
the gate via `formal/gate.sh`). This file follows the same convention — plain
test functions, a snapshot-driven real sweep that skips on missing data, and a
SYNTHETIC self-test that exercises the whole harness end-to-end with no live
data so the machinery is covered NOW.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.combat_picker import pick_winnable_monster_pure
from artifactsmmo_cli.ai.equipment.level_loadout import best_weapon_for_level
from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats
from artifactsmmo_cli.ai.equipment.scoring import pick_loadout
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.world_state import WorldState

# The leveling band from `GearTierLeveling.InLevelingBand`: 1 ≤ L < 50. We sweep
# the integer levels the character actually traverses, 1..49 inclusive.
BAND_LO = 1
BAND_HI = 50  # exclusive upper bound (the level cap)

SIM_DIR = Path(__file__).resolve().parents[1] / "sim"
BASE_STATS_PATH = SIM_DIR / "character_base_stats.json"
SNAPSHOT_PATH = SIM_DIR / "game_data_snapshot.json"

# item_stats keys that prove the snapshot carries combat fields (the
# re-snapshot). An OLD snapshot has only level/type/crafting_* — no `attack`.
COMBAT_FIELD_MARKER = "attack"


# ---------------------------------------------------------------------------
# WorldState construction — base + best weapon (the faithful level-L player).
# ---------------------------------------------------------------------------


def _base_world_state(level: int, base_row: dict[str, Any], weapon: ItemStats,
                      ) -> WorldState:
    """Construct the faithful level-`level` combat WorldState.

    Stat fields = BASE stats (no gear baked in). `weapon` sits in inventory and
    nothing is equipped, so production's `pick_loadout` equips the weapon and
    `project_loadout_stats` adds its full contribution ⇒ the totals fed to
    `predict_win` are `base + weapon`. `hp` is set to the projected max
    (`base.max_hp + weapon.hp_bonus`) so the verdict renders at full HP.

    See the module docstring "How the faithful level-L WorldState is built".
    """
    base_attack = {e: v for e, v in base_row["attack"].items() if v != 0}
    base_resistance = {e: v for e, v in base_row["resistance"].items() if v != 0}
    projected_max_hp = base_row["max_hp"] + weapon.hp_bonus
    return WorldState(
        character="sweep",
        level=level,
        xp=0,
        max_xp=999999,
        hp=projected_max_hp,
        max_hp=base_row["max_hp"],
        gold=0,
        skills={},
        x=0,
        y=0,
        inventory={weapon.code: 1},
        inventory_max=40,
        equipment={},
        cooldown_expires=None,
        task_code=None,
        task_type=None,
        task_progress=0,
        task_total=0,
        bank_items=None,
        bank_gold=None,
        pending_items=None,
        attack=base_attack,
        dmg=0,
        dmg_elements={},
        resistance=base_resistance,
        critical_strike=base_row["critical_strike"],
        initiative=base_row["initiative"],
    )


# ---------------------------------------------------------------------------
# The sweep harness — REAL production calls, no re-implementation.
# ---------------------------------------------------------------------------


def _winnable_in_band_target(
    level: int, base_row: dict[str, Any], stats_by_code: dict[str, ItemStats],
    game_data: GameData,
) -> str | None:
    """Production verdict: the picked winnable, XP-positive, not-overleveled
    monster for a level-`level` character wielding the best obtainable weapon,
    or `None` if no such monster exists (a `WinnableAcrossBand` gap).

    Drives the REAL chain: `best_weapon_for_level` → faithful WorldState →
    `pick_winnable_monster_pure` over the live catalog with the REAL
    `is_winnable` and the REAL `xp_per_kill > 0` predicate. The picker's
    own not-overleveled (suicide-guard) filter (`level <= char_level + 2`) is
    exactly the Lean `notOverleveled`, so a returned target witnesses all three
    band conditions."""
    weapon = best_weapon_for_level(stats_by_code, level)
    if weapon is None:
        # No obtainable weapon at this level — the proxy cannot even arm the
        # character. Treat as no winnable target (a genuine gap).
        return None
    state = _base_world_state(level, base_row, weapon)
    return pick_winnable_monster_pure(
        level,
        list(game_data.monster_levels.items()),
        lambda code: is_winnable(state, game_data, code),
        lambda code: game_data.xp_per_kill(code, level) > 0,
    )


def _sweep_band(
    base_stats: dict[str, dict[str, Any]],
    stats_by_code: dict[str, ItemStats],
    game_data: GameData,
) -> tuple[dict[int, str], list[int], list[int]]:
    """Run the harness across every band level for which base stats exist.

    Returns `(winners, gaps, missing)`:
      * `winners`: {level -> picked monster code} where a winnable in-band
        target exists.
      * `gaps`: levels WITH base stats but NO winnable in-band target — the real
        `WinnableAcrossBand` gaps.
      * `missing`: band levels with NO captured base-stats row (not yet sampled).
    """
    winners: dict[int, str] = {}
    gaps: list[int] = []
    missing: list[int] = []
    for level in range(BAND_LO, BAND_HI):
        base_row = base_stats.get(str(level))
        if base_row is None:
            missing.append(level)
            continue
        target = _winnable_in_band_target(level, base_row, stats_by_code, game_data)
        if target is None:
            gaps.append(level)
        else:
            winners[level] = target
    return winners, gaps, missing


# ---------------------------------------------------------------------------
# Snapshot / fixture loading (real-data path).
# ---------------------------------------------------------------------------


def _load_snapshot() -> dict[str, Any]:
    return json.loads(SNAPSHOT_PATH.read_text())


def _snapshot_has_combat_fields(snapshot: dict[str, Any]) -> bool:
    """True iff the snapshot's item_stats carry the combat fields the sweep
    needs (an OLD snapshot has only level/type/crafting_*)."""
    item_stats = snapshot.get("item_stats")
    if not item_stats:
        return False
    sample = next(iter(item_stats.values()))
    return COMBAT_FIELD_MARKER in sample


def _item_stats_from_snapshot(snapshot: dict[str, Any]) -> dict[str, ItemStats]:
    """Reconstruct the `code -> ItemStats` catalog from the snapshot's combat
    fields (the same fields `snapshot_game_data.py` writes)."""
    out: dict[str, ItemStats] = {}
    for code, row in snapshot["item_stats"].items():
        out[code] = ItemStats(
            code=code,
            level=row["level"],
            type_=row["type"],
            crafting_skill=row.get("crafting_skill"),
            crafting_level=row.get("crafting_level", 0),
            attack=dict(row.get("attack", {})),
            resistance=dict(row.get("resistance", {})),
            dmg=row.get("dmg", 0),
            dmg_elements=dict(row.get("dmg_elements", {})),
            critical_strike=row.get("critical_strike", 0),
            initiative=row.get("initiative", 0),
            hp_bonus=row.get("hp_bonus", 0),
            lifesteal=row.get("lifesteal", 0),
            antipoison=row.get("antipoison", 0),
            subtype=row.get("subtype", ""),
        )
    return out


def _game_data_from_snapshot(
    snapshot: dict[str, Any], stats_by_code: dict[str, ItemStats],
) -> GameData:
    """Build a `GameData` carrying the snapshot's monster catalog + item stats.

    Monster effect maps (poison/lifesteal/…) are not in the snapshot; they
    default to 0 — matching `GameData`'s own 0-fallback for an effect-less
    monster, which is what `predict_win` sees."""
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
    for attr in (
        "_monster_lifesteal", "_monster_poison", "_monster_barrier",
        "_monster_burn", "_monster_healing", "_monster_reconstitution",
        "_monster_void_drain", "_monster_berserker_rage", "_monster_frenzy",
        "_monster_protective_bubble", "_monster_corrupted",
    ):
        setattr(gd, attr, {code: 0 for code in codes})
    return gd


# ===========================================================================
# REAL sweep — validates WinnableAcrossBand against the live catalog. SKIPS
# cleanly until both fixtures are captured (CI/gate stay green).
# ===========================================================================


def test_winnable_across_band_real_sweep() -> None:
    """For every band level `1 ≤ L < 50` with captured base stats, assert the
    live catalog has a winnable, XP-positive, not-overleveled monster (the
    `WinnableAcrossBand` claim) using production's real `is_winnable`.

    Skips when the real fixtures are absent (see module docstring "Skip-on-
    missing-data"). Aggregates and reports any band levels with NO winnable
    in-band target — the real `WinnableAcrossBand` gaps."""
    if not BASE_STATS_PATH.exists():
        pytest.skip(
            "character_base_stats.json absent — capture it with "
            "`uv run python formal/sim/capture_base_stats.py <character>` "
            "(run once per level reached over a real session; resumable)."
        )
    snapshot = _load_snapshot()
    if not _snapshot_has_combat_fields(snapshot):
        pytest.skip(
            "game_data_snapshot.json item_stats lack combat fields "
            "(attack/hp_bonus/…) — re-snapshot the live API with "
            "`uv run python formal/sim/snapshot_game_data.py`."
        )

    document = json.loads(BASE_STATS_PATH.read_text())
    base_stats = document.get("base_stats", {})
    if not base_stats:
        pytest.skip(
            "character_base_stats.json has no captured rows yet — run "
            "`uv run python formal/sim/capture_base_stats.py <character>`."
        )

    stats_by_code = _item_stats_from_snapshot(snapshot)
    game_data = _game_data_from_snapshot(snapshot, stats_by_code)
    winners, gaps, missing = _sweep_band(base_stats, stats_by_code, game_data)

    # The sweep must have evaluated at least one band level (else nothing was
    # captured and we should have skipped above).
    assert winners or gaps, (
        f"no band level evaluated; missing base-stats rows for all levels "
        f"(captured rows: {sorted(base_stats)})"
    )
    assert not gaps, (
        f"WinnableAcrossBand gaps — no winnable, XP-positive, not-overleveled "
        f"monster at band level(s) {gaps} (optimistic-weapon proxy; armor the "
        f"proxy ignores could still close these). Winners covered: "
        f"{sorted(winners)}. Uncaptured levels (skipped): {missing}."
    )


# ===========================================================================
# SYNTHETIC self-test — exercises the WHOLE harness end-to-end with an
# in-memory catalog + base stats, using the REAL is_winnable (not mocked), so
# the WorldState construction + production wiring is covered NOW, before any
# real fixture lands.
# ===========================================================================


def _synthetic_stats_by_code() -> dict[str, ItemStats]:
    """A tiny catalog: one obtainable, clearly-winning weapon at level 1."""
    return {
        "iron_sword": ItemStats(
            code="iron_sword", level=1, type_="weapon", attack={"fire": 40},
            critical_strike=0, initiative=0, hp_bonus=0,
        ),
    }


def _synthetic_game_data(stats_by_code: dict[str, ItemStats]) -> GameData:
    """A GameData with one beatable monster (low HP, weak single-element
    attack) at the test level, all exotic effect maps zeroed."""
    gd = GameData()
    gd._item_stats = dict(stats_by_code)
    gd._monster_level = {"chicken": 5}
    gd._monster_hp = {"chicken": 12}
    gd._monster_attack = {"chicken": {"fire": 1}}
    gd._monster_resistance = {"chicken": {}}
    gd._monster_critical_strike = {"chicken": 0}
    gd._monster_initiative = {"chicken": 0}
    gd._monster_type = {"chicken": "normal"}
    for attr in (
        "_monster_lifesteal", "_monster_poison", "_monster_barrier",
        "_monster_burn", "_monster_healing", "_monster_reconstitution",
        "_monster_void_drain", "_monster_berserker_rage", "_monster_frenzy",
        "_monster_protective_bubble", "_monster_corrupted",
    ):
        setattr(gd, attr, {"chicken": 0})
    return gd


def _synthetic_base_stats() -> dict[str, dict[str, Any]]:
    """Plausible base stats for a level-5 character (single captured row)."""
    return {
        "5": {
            "max_hp": 145,
            "attack": {"fire": 0, "earth": 0, "water": 0, "air": 0},
            "resistance": {"fire": 0, "earth": 0, "water": 0, "air": 0},
            "critical_strike": 0,
            "initiative": 0,
        },
    }


def test_synthetic_harness_reports_monster_winnable() -> None:
    """End-to-end self-test of the harness on an in-memory catalog: the
    constructed base+weapon WorldState must let production's REAL `is_winnable`
    beat the synthetic monster, and the sweep must pick it as the in-band
    winnable target for the captured level. Proves the WorldState construction
    and production-call wiring work before real fixtures exist."""
    stats_by_code = _synthetic_stats_by_code()
    game_data = _synthetic_game_data(stats_by_code)
    base_stats = _synthetic_base_stats()

    # Direct: the faithful WorldState (base + iron_sword) beats the chicken via
    # the REAL is_winnable.
    weapon = best_weapon_for_level(stats_by_code, 5)
    assert weapon is not None and weapon.code == "iron_sword"
    state = _base_world_state(5, base_stats["5"], weapon)
    assert is_winnable(state, game_data, "chicken") is True

    # The projected totals are base + weapon (the construction is faithful):
    # base attack {} + iron_sword fire 40 ⇒ projected fire attack 40.
    loadout = pick_loadout("chicken", state, game_data)
    projected = project_loadout_stats(state, loadout, game_data)
    assert projected.attack.get("fire") == 40, projected.attack
    assert projected.max_hp == 145  # base.max_hp + weapon.hp_bonus(0)

    # Full sweep: level 5 has a winnable in-band target; no gaps; other band
    # levels are "missing" (no captured row), not gaps.
    winners, gaps, missing = _sweep_band(base_stats, stats_by_code, game_data)
    assert winners == {5: "chicken"}, winners
    assert gaps == [], gaps
    assert set(missing) == set(range(BAND_LO, BAND_HI)) - {5}


def test_synthetic_gap_when_no_winnable_target() -> None:
    """Mirror polarity: with ONLY an over-leveled, unbeatable monster the sweep
    reports the level as a `WinnableAcrossBand` gap (no winnable in-band target)
    — proving the harness surfaces gaps rather than silently passing."""
    stats_by_code = _synthetic_stats_by_code()
    gd = GameData()
    gd._item_stats = dict(stats_by_code)
    # A dragon far above the band window AND unbeatable (huge HP + attack).
    gd._monster_level = {"dragon": 40}
    gd._monster_hp = {"dragon": 5000}
    gd._monster_attack = {"dragon": {"fire": 500}}
    gd._monster_resistance = {"dragon": {}}
    gd._monster_critical_strike = {"dragon": 0}
    gd._monster_initiative = {"dragon": 0}
    gd._monster_type = {"dragon": "normal"}
    for attr in (
        "_monster_lifesteal", "_monster_poison", "_monster_barrier",
        "_monster_burn", "_monster_healing", "_monster_reconstitution",
        "_monster_void_drain", "_monster_berserker_rage", "_monster_frenzy",
        "_monster_protective_bubble", "_monster_corrupted",
    ):
        setattr(gd, attr, {"dragon": 0})

    base_stats = _synthetic_base_stats()
    winners, gaps, missing = _sweep_band(base_stats, stats_by_code, gd)
    assert winners == {}, winners
    assert gaps == [5], gaps
