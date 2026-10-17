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
  * the 20 integer closed-form `predictWin` inputs + the `playerFirst` boolean
    (kept for the projection pin; the kernel no longer decides them); and
  * the fight-odds inputs the kernel DOES decide: production `fight_split`'s
    `FightTerms` scalars (Lean `Formal.FightOutcome.Terms`) and `RoundDamage`
    (Lean `Formal.FightOdds.Damage`), the fight's start HP (`state.hp`), its max
    HP (`fight_max_hp`), and the worn restore potion (`worn_restore`).

The verdict is production's (spec 2026-10-15 fight-gates-odds §1/§5): a row's
monster is picked among the monsters production `is_winnable` accepts AND whose
counted-crit lower bound `crit_bound` (Lean `Formal.FightOdds.critBound`) is at
least `WITNESS_THETA` = 99/100: the single path on which the player never crits
and the monster crits its first `crit_budget` turns wins, so every path with at
most that many monster crits wins and P(win) >= P(Binomial(turns, m_crit%) <=
crit_budget). The kernel decides that bound per row
(`WinnableGrounded.rowWinnable`) and lifts it to P(win) at the row's real crit
chances and stock (`Formal.FightOdds.winProb_ge_critBound`).

The kernel TRUSTS these scalars only as far as the differential
(`formal/diff/test_winnable_witness_diff.py`) enforces them against production:
that test re-derives each row's projection and fight-odds scalars from
`project_loadout_stats` / `fight_split` and asserts production `is_winnable` and
the bound >= 99/100. So the witness reflects production — it is never
reverse-engineered to pass the kernel `decide`.

The witness rows are consumed by `generate_lean_fixture.py` to emit
`def winnableWitness : List WitnessRow` into `GameDataFixture.lean`.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from artifactsmmo_cli.ai.combat import (
    _crit_hit,
    _element_damage,
    fight_max_hp,
    fight_numbers,
    fight_split,
    is_winnable,
    moves_first,
    worn_restore,
)
from artifactsmmo_cli.ai.combat_picker import pick_winnable_monster_pure
from artifactsmmo_cli.ai.elements import ELEMENTS
from artifactsmmo_cli.ai.equipment.level_loadout import (
    obtainable_hp_bonus_ceiling,
    obtainable_inventory_for_level,
)
from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout
from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats
from artifactsmmo_cli.ai.fight_odds_core import RoundDamage, _refresh, _tick, absorb
from artifactsmmo_cli.ai.fight_terms_core import (
    MAX_TURNS,
    SCALE,
    FightExit,
    FightTerms,
    effective_player_hp,
)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_value_core import Combat
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.win_threshold_core import LIVENESS_THETA
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
    p_crit_hit: int
    p_lifesteal: int
    p_antipoison: int
    # The 20 integer `predictWin` inputs + playerFirst (computed as predict_win does).
    raw_player: int
    monster_hp: int
    raw_monster: int
    m_crit: int
    m_atk_sum: int
    m_crit_hit: int
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
    # The fight-odds inputs the kernel decides (production `fight_split`):
    # Lean `Terms` ...
    t_raw_player: int
    t_kill_step: int
    t_monster_hp: int
    t_recon: int
    t_die_step: int
    t_player_first: bool
    # ... Lean `Damage` at the row's real crit chances ...
    d_monster_hp: int
    d_kill_normal: int
    d_kill_crit: int
    d_p_crit: int
    d_die_normal: int
    d_die_crit: int
    d_m_crit: int
    d_burn: tuple[int, ...]
    d_p_heal: int
    d_m_heal: int
    # ... and the fight's start HP, max HP and worn restore potion.
    fight_hp: int
    fight_max_hp: int
    restore: int
    stock: int
    # The crit budget certificate the kernel's `critBound` reads.
    crit_budget: int


WITNESS_THETA = LIVENESS_THETA
"""The bound every witness row's P(win) is proved to reach (Lean
`WinnableGrounded.witnessTheta`, production `win_threshold_core.LIVENESS_THETA`):
liveness holds for any character threshold θ <= 99/100. A learned
θ = t_loss / (t_win + t_loss) exceeds 0.99 when a loss costs more than 99 wins."""


def _khit(damage: RoundDamage, crits_left: int) -> int:
    """The monster's hit on the counted-crit path (Lean `FightOdds.khit`): a crit
    while crits are left, else a normal hit."""
    return damage.die_crit if crits_left > 0 else damage.die_normal


def _m_up(damage: RoundDamage) -> int:
    """Lean `FightOdds.mUp`: the most the monster's lifesteal heals it in one
    turn, charged on every monster turn of the counted-crit path."""
    return max(0, damage.m_heal)


def crit_path_wins(damage: RoundDamage, player_first: bool, monster_pool: int,
                   player_pool: int, crits: int) -> bool:
    """Lean `FightOdds.kpath` from round 1 with `MAX_TURNS` rounds of fuel: the
    single path on which the player never crits (so never heals), the monster
    crits its first `crits` turns and then hits normal, healing `_m_up` every
    turn, with no restore stock, is won. The kill goes to the barrier first
    (`absorb`), refreshed by the monster's turn in every 5th round."""
    m, p, c = monster_pool, player_pool, crits
    up, full = _m_up(damage), damage.barrier * SCALE
    s = full
    for round_no in range(1, MAX_TURNS + 1):
        tick = _tick(damage, player_first, round_no)
        hit = _khit(damage, c)
        if player_first:
            if tick > 0 and p - tick <= 0:
                return False
            through, kept = absorb(s, damage.kill_normal)
            if m - through <= 0:
                return True
            if p - tick - hit <= 0:
                return False
            p = p - tick - hit
            m, s = m - through + up, _refresh(kept, full, round_no)
        else:
            if p - hit <= 0:
                return False
            if tick > 0 and p - hit - tick <= 0:
                return False
            through, s = absorb(_refresh(s, full, round_no), damage.kill_normal)
            if m + up - through <= 0:
                return True
            p = p - hit - tick
            m = m + up - through
        c = max(c - 1, 0)
    return False


def monster_turns(damage: RoundDamage, player_first: bool, monster_pool: int) -> int:
    """Lean `FightOdds.mturns` with `MAX_TURNS` rounds of fuel: the monster's turns
    before the player's never-critting kill, the monster healing `_m_up` each
    and its barrier absorbing the kill first (`crit_path_wins`)."""
    m, turns, up = monster_pool, 0, _m_up(damage)
    full = damage.barrier * SCALE
    s = full
    for round_no in range(1, MAX_TURNS + 1):
        if player_first:
            through, kept = absorb(s, damage.kill_normal)
            if m - through <= 0:
                return turns
            turns += 1
            m, s = m - through + up, _refresh(kept, full, round_no)
        else:
            turns += 1
            through, s = absorb(_refresh(s, full, round_no), damage.kill_normal)
            if m + up - through <= 0:
                return turns
            m = m + up - through
    return turns


def binom_at_most(m_crit: int, turns: int, crits: int) -> Fraction:
    """Lean `FightOdds.binom`: P(at most `crits` of `turns` monster turns crit),
    each crit at `m_crit`%."""
    wn, wc = Fraction(100 - m_crit, 100), Fraction(m_crit, 100)
    row: list[Fraction] = []
    for _n in range(turns):
        row = [wn * (row[c] if c < len(row) else 1)
               + wc * (0 if c == 0 else (row[c - 1] if c - 1 < len(row) else 1))
               for c in range(len(row) + 1)]
    return row[crits] if crits < len(row) else Fraction(1)


def crit_bound(terms: FightTerms, damage: RoundDamage, hp: int, max_hp: int,
               crits: int) -> Fraction:
    """Lean `FightOdds.critBound`: the proved lower bound on P(win) at no stock
    (`FightOdds.winProb_ge_critBound`, any stock by stock monotonicity). If the
    counted-crit path with `crits` crits wins, every path with at most `crits`
    monster crits wins, so P(win) >= P(Binomial(turns, m_crit%) <= crits)."""
    if terms.exit is FightExit.OUT_SUSTAIN:
        return Fraction(1)
    if terms.exit not in (FightExit.NONE, FightExit.DEAD):
        return Fraction(0)
    pool = effective_player_hp(hp, max_hp) * SCALE
    if pool <= 0:
        return Fraction(0)
    monster = damage.monster_hp * SCALE
    if not crit_path_wins(damage, terms.player_first, monster, pool, crits):
        return Fraction(0)
    return binom_at_most(damage.m_crit, monster_turns(damage, terms.player_first, monster), crits)


def best_crit_budget(terms: FightTerms, damage: RoundDamage, hp: int, max_hp: int) -> int:
    """The most crits the counted-crit path survives, at most the monster's turns
    (0 when it survives none): the budget with the largest `crit_bound`, since
    the bound grows with the budget while the path still wins. The certificate
    the kernel checks; its soundness does not depend on this choice."""
    monster = damage.monster_hp * SCALE
    pool = effective_player_hp(hp, max_hp) * SCALE
    turns = monster_turns(damage, terms.player_first, monster)
    for crits in range(turns, -1, -1):
        if crit_path_wins(damage, terms.player_first, monster, pool, crits):
            return crits
    return 0


def witness_bound(state: WorldState, game_data: GameData, monster_code: str) -> tuple[int, Fraction]:
    """`(crit budget, crit_bound)` of the fight against `monster_code`, over
    production `fight_split` and `fight_max_hp`."""
    terms, damage = fight_split(state, game_data, monster_code)
    max_hp = fight_max_hp(state, game_data, monster_code)
    budget = best_crit_budget(terms, damage, state.hp, max_hp)
    return budget, crit_bound(terms, damage, state.hp, max_hp, budget)


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
        inventory_slots_max=40,
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
    with the real `is_winnable`, narrowed to the monsters whose `crit_bound` is
    at least `WITNESS_THETA` (the verdict the kernel decides). For the chosen
    monster it then runs `pick_loadout` + `project_loadout_stats` (production),
    computes the closed-form integer scalars as production does internally, and
    records production `fight_split`'s terms and damage.
    """
    inventory = obtainable_inventory_for_level(stats_by_code, level)
    hp_ceiling = obtainable_hp_bonus_ceiling(stats_by_code, level)
    state = _base_world_state(level, base_row, inventory, hp_ceiling)
    monster_code = pick_winnable_monster_pure(
        level,
        list(game_data.monster_levels.items()),
        lambda code: (is_winnable(state, game_data, code)
                      and witness_bound(state, game_data, code)[1] >= WITNESS_THETA),
        lambda code: game_data.xp_per_kill(code, level) > 0,
    )
    if monster_code is None:
        return None

    loadout = pick_loadout(
        Combat(game_data.monster_attack(monster_code),
               game_data.monster_resistance(monster_code),
               dict(state.attack)), state, game_data)
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

    numbers = fight_numbers(state, game_data, monster_code)
    terms, damage = numbers.terms, numbers.damage
    restore, stock = worn_restore(state, game_data)

    return WitnessRow(
        level=level,
        monster_code=monster_code,
        monster_level=game_data.monster_level(monster_code),
        loadout_codes=loadout_codes,
        p_crit=p.critical_strike,
        p_max_hp=p.max_hp,
        p_initiative=p.initiative,
        p_crit_hit=_crit_hit(p.attack, p.dmg, p.dmg_elements, m_resist),
        p_lifesteal=p_lifesteal,
        p_antipoison=p_antipoison,
        raw_player=raw_player,
        monster_hp=game_data.monster_hp(monster_code),
        raw_monster=raw_monster,
        m_crit=game_data.monster_critical_strike(monster_code),
        m_atk_sum=sum(m_attack.values()),
        m_crit_hit=_crit_hit(m_attack, 0, {}, p.resistance),
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
        player_first=moves_first(p.initiative, state.hp, game_data.monster_initiative(monster_code),
                                 game_data.monster_hp(monster_code)),
        t_raw_player=numbers.raw_player,
        t_kill_step=terms.kill_step,
        t_monster_hp=damage.monster_hp,
        t_recon=game_data.monster_reconstitution(monster_code),
        t_die_step=terms.die_step,
        t_player_first=terms.player_first,
        d_monster_hp=damage.monster_hp,
        d_kill_normal=damage.kill_normal,
        d_kill_crit=damage.kill_crit,
        d_p_crit=damage.p_crit,
        d_die_normal=damage.die_normal,
        d_die_crit=damage.die_crit,
        d_m_crit=damage.m_crit,
        d_burn=damage.burn,
        d_p_heal=damage.p_heal,
        d_m_heal=damage.m_heal,
        fight_hp=state.hp,
        fight_max_hp=fight_max_hp(state, game_data, monster_code),
        restore=restore,
        stock=stock,
        crit_budget=witness_bound(state, game_data, monster_code)[0],
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
