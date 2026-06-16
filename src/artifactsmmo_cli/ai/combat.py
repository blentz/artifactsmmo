"""Combat-outcome estimator implementing the documented artifactsmmo fight
formula (https://docs.artifactsmmo.com/concepts/stats_and_fights).

Pure functions over WorldState + GameData; no API, no RNG. Critical strikes are
modelled as their expected contribution (deterministic) since the planner needs
a stable verdict, not a sampled fight."""

import math

from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats
from artifactsmmo_cli.ai.equipment.scoring import pick_loadout
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import ELEMENTS, WorldState

MAX_TURNS = 100
"""A fight unresolved by turn 100 is a loss (documented combat cap)."""

WIN_RATE_THRESHOLD = 0.9
"""Below this observed Fight success rate, the learned-loss veto fires. Set high
(0.9) because `predict_win` is an EXPECTED-value verdict: a marginal monster the
formula calls winnable can still lose ~10-15% to combat variance (crits), and each
loss burns a fight cooldown for zero progress and risks death. Trace 2026-06-15:
the bot ground blue_slime (won 87% from FULL HP, lost 13%) for 200+ cycles because
the old 0.5 threshold only vetoed monsters lost MORE than half the time. Vetoing
sub-0.9 win rates redirects the target picker to a reliably-winnable monster
(green_slime, 0% loss in the same trace). Runtime-only: the veto is applied where
`history` is passed (target selection), NOT in the stat-only planning gates, so it
does not perturb Fight-for-drops reachability."""

MIN_WIN_SAMPLES = 5
"""Observed fights required before the loss veto overrides the stat prediction.
Coupled to WARMUP_MIN_SAMPLES in store_warmup_core: success_rate returns 1.0
below that threshold, so a lower MIN_WIN_SAMPLES is INERT without also
lowering the warmup gate (which would broaden the contract across all
learned estimates)."""


def _round_half_up(value: float) -> int:
    """Round to nearest integer; exact halves round up (documented rule)."""
    return math.floor(value + 0.5)


def _element_damage(attack: int, dmg_pct: int, resist_pct: int) -> int:
    """Net damage for one element: apply the damage % bonus, then subtract the
    defender's resistance %. Never negative."""
    # resist_pct is assumed non-negative (game API never yields a resist debuff);
    # a negative would amplify rather than block, which max(0, ...) would not catch.
    output = attack + _round_half_up(attack * dmg_pct / 100)
    blocked = _round_half_up(output * resist_pct / 100)
    return max(0, output - blocked)


def _expected_hit(
    attack: dict[str, int],
    dmg_global: int,
    dmg_elements: dict[str, int],
    resist: dict[str, int],
    crit: int,
) -> float:
    """Expected per-turn damage across all elements, including the expected
    critical-strike contribution (crit% chance of a 1.5x hit)."""
    raw = sum(
        _element_damage(attack.get(e, 0), dmg_global + dmg_elements.get(e, 0), resist.get(e, 0))
        for e in ELEMENTS
    )
    return raw * (1 + (crit / 100) * 0.5)


def predict_win(state: WorldState, game_data: GameData, monster_code: str) -> bool:
    """True if the documented formula says the player beats the monster using the
    best on-hand loadout (inventory + equipped) for it.

    Uses CURRENT hp (state.hp), not projected max_hp. Prior version used
    p.max_hp which over-predicted wins when the player was already damaged
    — trace cycle 63 (run 9, 2026-06-03): bot at HP=49/125 (39%) was
    predicted to win a chicken fight, fought, lost. The fight starts at
    state.hp, not max_hp; project_loadout_stats may raise max_hp via
    equipment but doesn't refill current hp."""
    loadout = pick_loadout(monster_code, state, game_data)
    p = project_loadout_stats(state, loadout, game_data)
    m_resist = game_data.monster_resistance(monster_code)
    m_crit = game_data.monster_critical_strike(monster_code)
    # EXACT INTEGER arithmetic mirroring Formal/PredictWin.lean (×10000 scale, so the
    # heal `crit% × lifesteal% × Σattack` is exact). `_expected_hit`'s float form is
    # the same expected per-turn damage; here we keep it integral to match the proof
    # exactly under the finer lifesteal fractions.
    raw_player = sum(
        _element_damage(p.attack.get(e, 0), p.dmg + p.dmg_elements.get(e, 0), m_resist.get(e, 0))
        for e in ELEMENTS
    )
    if raw_player <= 0:
        return False
    # Monster lifesteal heals it on ITS crit, lowering our NET kill rate.
    m_attack = game_data.monster_attack(monster_code)
    m_atk_sum = sum(m_attack.values())
    kill_step = (50 * raw_player * (200 + p.critical_strike)
                 - m_crit * game_data.monster_lifesteal(monster_code) * m_atk_sum)
    if kill_step <= 0:
        return False  # the monster out-heals our damage — unkillable
    rounds_to_kill = -(-(game_data.monster_hp(monster_code) * 10000) // kill_step)  # ceil
    if rounds_to_kill > MAX_TURNS:
        return False
    raw_monster = sum(
        _element_damage(m_attack.get(e, 0), 0, p.resistance.get(e, 0)) for e in ELEMENTS
    )
    # Player lifesteal heals us on OUR crit, lowering our NET death rate. Sum the
    # lifesteal of the post-loadout equipment (loadout overrides changed slots).
    final_equip = dict(state.equipment)
    final_equip.update(loadout)
    player_lifesteal = sum(
        st.lifesteal for code in final_equip.values()
        if code and (st := game_data.item_stats(code)) is not None
    )
    p_atk_sum = sum(p.attack.values())
    # Monster poison is a flat per-turn DoT on the player (applied turn 1, ticks
    # every turn), so it RAISES the player's net death rate — even when the monster
    # deals no direct damage (raw_monster == 0), poison alone can kill.
    die_step = (50 * raw_monster * (200 + m_crit)
                - p.critical_strike * player_lifesteal * p_atk_sum
                + game_data.monster_poison(monster_code) * 10000)
    if die_step <= 0:
        return True  # we out-sustain the monster's damage (poison-inclusive)
    effective_hp = min(state.hp, p.max_hp) if state.hp > 0 else 0
    if effective_hp <= 0:
        return False
    rounds_to_die = -(-(effective_hp * 10000) // die_step)  # ceil
    player_first = p.initiative >= game_data.monster_initiative(monster_code)
    return rounds_to_kill <= rounds_to_die if player_first else rounds_to_kill < rounds_to_die


def is_winnable(
    state: WorldState,
    game_data: GameData,
    monster_code: str,
    history: LearningStore | None = None,
) -> bool:
    """The single combat-beatability verdict used across planning and runtime.

    Stat prediction (`predict_win`) gated by a learned-loss veto: a monster lost
    in >= MIN_WIN_SAMPLES observed fights at < WIN_RATE_THRESHOLD success is judged
    unwinnable regardless of the optimistic formula. A cold/absent history defers
    to the prediction. Pass history at runtime (target selection); the planning
    gates call it stat-only since the veto is already applied upstream.
    """
    if history is not None:
        samples = history.sample_count(f"Fight({monster_code})")
        if (samples >= MIN_WIN_SAMPLES
                and history.success_rate(f"Fight({monster_code})") < WIN_RATE_THRESHOLD):
            return False
    return predict_win(state, game_data, monster_code)
