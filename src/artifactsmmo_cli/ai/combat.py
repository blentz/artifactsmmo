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

WIN_RATE_THRESHOLD = 0.5
"""Below this observed Fight success rate, the learned-loss veto fires."""

MIN_WIN_SAMPLES = 5
"""Observed fights required before the loss veto overrides the stat prediction."""


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
    best on-hand loadout (inventory + equipped) for it."""
    loadout = pick_loadout(monster_code, state, game_data)
    p = project_loadout_stats(state, loadout, game_data)
    player_hit = _expected_hit(
        p.attack, p.dmg, p.dmg_elements,
        game_data.monster_resistance(monster_code), p.critical_strike,
    )
    if player_hit <= 0:
        return False
    rounds_to_kill = math.ceil(game_data.monster_hp(monster_code) / player_hit)
    if rounds_to_kill > MAX_TURNS:
        return False
    monster_hit = _expected_hit(
        game_data.monster_attack(monster_code), 0, {},
        p.resistance, game_data.monster_critical_strike(monster_code),
    )
    if monster_hit <= 0:
        return True
    rounds_to_die = math.ceil(p.max_hp / monster_hit)
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
