"""Combat-outcome estimator implementing the documented artifactsmmo fight
formula (https://docs.artifactsmmo.com/concepts/stats_and_fights).

Pure functions over WorldState + GameData; no API, no RNG. Critical strikes are
modelled as their expected contribution (deterministic) since the planner needs
a stable verdict, not a sampled fight."""

import math

from artifactsmmo_cli.ai.elements import ELEMENTS
from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout
from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_value_core import Combat
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

MAX_TURNS = 100
"""A fight unresolved by turn 100 is a loss (documented combat cap)."""

WIN_MARGIN = MAX_TURNS + 1
"""Sentinel margin for the die_step<=0 (out-sustain) win branch of `combat_margin`."""

LOSE_MARGIN = -(MAX_TURNS + 1)
"""Sentinel margin for all losing / unkillable branches of `combat_margin`."""

GREED_MAX_STACKS = 9
"""Max `greed` stacks the closed-form model assumes (conservative upper bound).

`greed` gives the monster +value% damage for each 10% max-HP it has lost. A monster
triggers it at 10%..90% HP lost = 9 times while still alive and dealing damage (the
10th, at 100% lost, coincides with death). predict_win has no turn counter, so it
models the monster as ALWAYS at this max-stack count — an upper bound on monster
damage that keeps the verdict a safe veto."""

WIN_RATE_THRESHOLD = 0.4
"""Below this observed Fight success rate, the learned-loss veto fires. The veto
exists to deselect monsters that are GENUINELY costly — lost more often than won —
not merely imperfect. A loss while grinding character XP costs only a rest cooldown
(no item / no permanent setback), so a monster won even ~40-60% of the time is still
the best use of cycles when it is the strongest available XP source.

Set to 0.4 (was 0.9). The 0.9 value over-fired: trace 2026-06-29 showed a level-3
character whose only in-window XP source was green_slime (~80% win, the losses
traced to STARTING fights at low HP). A single sub-0.9 loss flipped green_slime to
"unwinnable", the target picker returned None, and the ReachCharLevel objective stood
down — diverting the bot into an endless gear grind (copper_helmet) that awards ZERO
character XP. The right bar for "don't bother" is "loses more than it wins", i.e. 0.4;
avoidable low-HP losses are addressed at engagement time (pre-fight HP / consumables),
not by abandoning the only grindable monster.

Runtime-only: the veto is applied where `history` is passed (target selection), NOT
in the stat-only planning gates, so it does not perturb Fight-for-drops reachability."""

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


def _kill_step_net(
    raw_player: int, p_crit: int, m_crit: int, m_lifesteal: int,
    m_atk_sum: int, monster_hp: int, monster_healing: int,
    player_max_hp: int, monster_void_drain: int,
    monster_bubble: int, monster_sun_shield: int,
) -> int:
    """Net per-turn kill rate (player vs monster, ×10000 scale).

    Mirrors Lean `killStepNet` (PredictWin.lean:122). All inputs are ints;
    output is an int. A non-positive result means the monster is unkillable.
    See predict_win for the modelling rationale behind each term."""
    return (50 * raw_player * (200 + p_crit)
            - m_crit * m_lifesteal * m_atk_sum
            - monster_healing * monster_hp * 100
            - monster_void_drain * player_max_hp * 100
            - (monster_bubble
               + monster_sun_shield) * raw_player * (200 + p_crit) // 2)


def _die_step(
    raw_monster: int, m_crit: int, p_crit: int, p_lifesteal: int,
    p_atk_sum: int, monster_poison: int, monster_burn: int,
    player_max_hp: int, monster_void_drain: int,
    monster_berserk: int, monster_frenzy: int,
    player_antipoison: int, raw_player: int,
    monster_greed: int, monster_enchanted_mirror: int,
) -> int:
    """Net per-turn die rate (player receiving damage, ×10000 scale).

    Mirrors Lean `dieStep` (PredictWin.lean:134). All inputs are ints;
    output is an int. A non-positive result means the player out-sustains the
    monster. See predict_win for the modelling rationale behind each term."""
    return (50 * raw_monster * (200 + m_crit)
            - p_crit * p_lifesteal * p_atk_sum
            + max(0, monster_poison - player_antipoison) * 10000
            + monster_burn * p_atk_sum * 100
            + monster_void_drain * player_max_hp * 100
            + monster_berserk * raw_monster * (200 + m_crit) // 2
            + monster_frenzy * raw_monster * (200 + m_crit) // 2
            + GREED_MAX_STACKS * monster_greed * raw_monster * (200 + m_crit) // 2
            + monster_enchanted_mirror * raw_player * (200 + p_crit) // 2)


def _effective_player_hp(hp: int, max_hp: int) -> int:
    """Player HP at fight start: current HP capped at max_hp, or 0 if already dead."""
    return min(hp, max_hp) if hp > 0 else 0


def predict_win(state: WorldState, game_data: GameData, monster_code: str) -> bool:
    """True if the documented formula says the player beats the monster using the
    best on-hand loadout (inventory + equipped) for it.

    Uses CURRENT hp (state.hp), not projected max_hp. Prior version used
    p.max_hp which over-predicted wins when the player was already damaged
    — trace cycle 63 (run 9, 2026-06-03): bot at HP=49/125 (39%) was
    predicted to win a chicken fight, fought, lost. The fight starts at
    state.hp, not max_hp; project_loadout_stats may raise max_hp via
    equipment but doesn't refill current hp."""
    loadout = pick_loadout(
        Combat(game_data.monster_attack(monster_code), game_data.monster_resistance(monster_code)),
        state, game_data,
    )
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
    # Monster healing is per-turn regen (a % of its HP every 3 turns), modeled
    # conservatively as the full per-3-turn amount EVERY turn (3× upper bound):
    # subtract it from the net kill step. A monster we can't out-damage out-heals
    # itself ⇒ kill_step <= 0 ⇒ unkillable (the guard below).
    # Void drain (every 4 turns the monster drains a % of player HP to heal itself,
    # modeled conservatively as the full per-4-turn amount EVERY turn) heals the
    # monster ⇒ subtract its per-turn self-heal from the net kill step.
    # Protective-bubble grants value% resistance to a rotating element each turn;
    # modeled conservatively as the bubble always covering the player's damage (value%
    # reduction every turn) ⇒ reduce killStep by value% of the player-damage term
    # (= value * raw_player * (200+crit) / 2). // 2 matches the Lean `/ 2` on non-negs.
    # Sun-shield reduces the FIRST hit the monster takes each turn by value%; modeled
    # conservatively as a value% reduction of the player's damage EVERY turn (same shape
    # as protective_bubble). bubble and sun_shield both reduce the player's per-turn
    # damage, so they are SUMMED into one (bubble+sun_shield)% reduction inside a SINGLE
    # floor-divide — two separate `// 2` floors would double-round and break the proved
    # monotonicity of kill_step in raw_player (real monsters carry at most one of them,
    # so this is identical for live data). // 2 matches the Lean `/ 2` on non-negatives.
    kill_step = _kill_step_net(
        raw_player, p.critical_strike, m_crit,
        game_data.monster_lifesteal(monster_code), m_atk_sum,
        game_data.monster_hp(monster_code),
        game_data.monster_healing(monster_code),
        p.max_hp,
        game_data.monster_void_drain(monster_code),
        game_data.monster_protective_bubble(monster_code),
        game_data.monster_sun_shield(monster_code),
    )
    if kill_step <= 0:
        return False  # the monster out-damages/out-heals/out-resists us — unkillable
    # Barrier is an absorbing shield: model it conservatively as extra effective HP
    # the player must chew through (per-5-turn refresh deferred — first cut flat add).
    effective_monster_hp = game_data.monster_hp(monster_code) + game_data.monster_barrier(monster_code)
    rounds_to_kill = -(-(effective_monster_hp * 10000) // kill_step)  # ceil
    if rounds_to_kill > MAX_TURNS:
        return False
    # Reconstitution: the monster regains ALL HP every N turns. If we can't kill it
    # strictly faster than that period, it fully heals before dying ⇒ unwinnable
    # (conservative: win needs rounds_to_kill < period).
    reconstitution = game_data.monster_reconstitution(monster_code)
    if 0 < reconstitution <= rounds_to_kill:
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
    # Player antipoison (equipped antidote potions) removes N poison/turn, CAPPING the
    # monster's poison DoT at max(0, poison - antipoison) (PLAN #3b2; composes with #1
    # poison). Summed over the post-loadout equipment, like lifesteal.
    player_antipoison = sum(
        st.antipoison for code in final_equip.values()
        if code and (st := game_data.item_stats(code)) is not None
    )
    p_atk_sum = sum(p.attack.values())
    # Monster poison is a flat per-turn DoT on the player (applied turn 1, ticks
    # every turn), so it RAISES the player's net death rate — even when the monster
    # deals no direct damage (raw_monster == 0), poison alone can kill. Monster burn
    # is a percent-of-player-attack DoT, modeled conservatively as flat per-turn (no
    # decay — an upper bound on the real decaying burn): burn% × p_atk_sum × 100.
    # Berserker-rage (+% dmg below 25% HP, permanent) and frenzy (+% dmg on crit)
    # both raise monster damage; modeled conservatively as ALWAYS active — each adds
    # value% of the monster's per-turn damage (= value * raw_monster * (200+m_crit) / 2,
    # the 50*...*value/100 reduced). Floor (//) matches the Lean `/ 2` on non-negatives.
    # Greed adds +value% monster damage per 10% max-HP lost; modeled at the max
    # GREED_MAX_STACKS=9 stacks always active (= 9 * value% of monster damage).
    # Enchanted-mirror reflects value% of the damage the MONSTER takes (= the player's
    # output) back at the player, once per 3 turns; modeled conservatively as every turn
    # (3× upper bound, mirroring healing) ⇒ add value% of the player-damage term. This is
    # the only die_step term scaled by the player's raw output (raw_player, p.crit).
    die_step = _die_step(
        raw_monster, m_crit, p.critical_strike, player_lifesteal,
        p_atk_sum,
        game_data.monster_poison(monster_code),
        game_data.monster_burn(monster_code),
        p.max_hp,
        game_data.monster_void_drain(monster_code),
        game_data.monster_berserker_rage(monster_code),
        game_data.monster_frenzy(monster_code),
        player_antipoison, raw_player,
        game_data.monster_greed(monster_code),
        game_data.monster_enchanted_mirror(monster_code),
    )
    if die_step <= 0:
        return True  # we out-sustain the monster's damage (poison-inclusive)
    effective_hp = _effective_player_hp(state.hp, p.max_hp)
    if effective_hp <= 0:
        return False
    rounds_to_die = -(-(effective_hp * 10000) // die_step)  # ceil
    player_first = p.initiative >= game_data.monster_initiative(monster_code)
    return rounds_to_kill <= rounds_to_die if player_first else rounds_to_kill < rounds_to_die


def combat_margin(state: WorldState, game_data: GameData, monster_code: str) -> int:
    """Signed margin whose sign equals the `predict_win` verdict.

    Invariant: ``predict_win(...) == (combat_margin(...) > 0)`` for all inputs.

    Mirrors `predict_win`'s exact control flow, returning int sentinels or the
    round-cushion at each exit:
    * ``raw_player <= 0``                        → ``LOSE_MARGIN``
    * ``kill_step <= 0``                         → ``LOSE_MARGIN``
    * ``rounds_to_kill > MAX_TURNS``             → ``LOSE_MARGIN``
    * reconstitution kills before we do          → ``LOSE_MARGIN``
    * ``die_step <= 0`` (out-sustain)            → ``WIN_MARGIN``
    * ``effective_hp <= 0``                      → ``LOSE_MARGIN``
    * numeric regime: ``rounds_to_die - rounds_to_kill + (1 if player_first else 0)``

    Mirrors Lean ``Formal.PredictWin.combatMargin`` (PredictWin.lean).
    """
    loadout = pick_loadout(
        Combat(game_data.monster_attack(monster_code), game_data.monster_resistance(monster_code)),
        state, game_data,
    )
    p = project_loadout_stats(state, loadout, game_data)
    m_resist = game_data.monster_resistance(monster_code)
    m_crit = game_data.monster_critical_strike(monster_code)
    raw_player = sum(
        _element_damage(p.attack.get(e, 0), p.dmg + p.dmg_elements.get(e, 0), m_resist.get(e, 0))
        for e in ELEMENTS
    )
    if raw_player <= 0:
        return LOSE_MARGIN
    m_attack = game_data.monster_attack(monster_code)
    m_atk_sum = sum(m_attack.values())
    kill_step = _kill_step_net(
        raw_player, p.critical_strike, m_crit,
        game_data.monster_lifesteal(monster_code), m_atk_sum,
        game_data.monster_hp(monster_code),
        game_data.monster_healing(monster_code),
        p.max_hp,
        game_data.monster_void_drain(monster_code),
        game_data.monster_protective_bubble(monster_code),
        game_data.monster_sun_shield(monster_code),
    )
    if kill_step <= 0:
        return LOSE_MARGIN
    effective_monster_hp = game_data.monster_hp(monster_code) + game_data.monster_barrier(monster_code)
    rounds_to_kill = -(-(effective_monster_hp * 10000) // kill_step)  # ceil
    if rounds_to_kill > MAX_TURNS:
        return LOSE_MARGIN
    reconstitution = game_data.monster_reconstitution(monster_code)
    if 0 < reconstitution <= rounds_to_kill:
        return LOSE_MARGIN
    raw_monster = sum(
        _element_damage(m_attack.get(e, 0), 0, p.resistance.get(e, 0)) for e in ELEMENTS
    )
    final_equip = dict(state.equipment)
    final_equip.update(loadout)
    player_lifesteal = sum(
        st.lifesteal for code in final_equip.values()
        if code and (st := game_data.item_stats(code)) is not None
    )
    player_antipoison = sum(
        st.antipoison for code in final_equip.values()
        if code and (st := game_data.item_stats(code)) is not None
    )
    p_atk_sum = sum(p.attack.values())
    die_step = _die_step(
        raw_monster, m_crit, p.critical_strike, player_lifesteal,
        p_atk_sum,
        game_data.monster_poison(monster_code),
        game_data.monster_burn(monster_code),
        p.max_hp,
        game_data.monster_void_drain(monster_code),
        game_data.monster_berserker_rage(monster_code),
        game_data.monster_frenzy(monster_code),
        player_antipoison, raw_player,
        game_data.monster_greed(monster_code),
        game_data.monster_enchanted_mirror(monster_code),
    )
    if die_step <= 0:
        return WIN_MARGIN
    effective_hp = _effective_player_hp(state.hp, p.max_hp)
    if effective_hp <= 0:
        return LOSE_MARGIN
    rounds_to_die = -(-(effective_hp * 10000) // die_step)  # ceil
    player_first = p.initiative >= game_data.monster_initiative(monster_code)
    return rounds_to_die - rounds_to_kill + (1 if player_first else 0)


def is_winnable(
    state: WorldState,
    game_data: GameData,
    monster_code: str,
    history: LearningStore | None = None,
) -> bool:
    """The single combat-beatability verdict used across planning and runtime.

    Three gates, in order, when a history is supplied:
    1. LEARNED-LOSS veto: a monster lost in >= MIN_WIN_SAMPLES observed fights at
       < WIN_RATE_THRESHOLD success is judged unwinnable regardless of the formula.
    2. MONOTONIC-WIN inference: an observed win against ANY monster of level >= this
       one's level proves this (no-harder) monster is winnable too — until a future
       loss against it appears. Beating a level-2 slime flags every level-1 monster
       (e.g. chicken) winnable, so a pessimistic `predict_win` can't block an
       already-demonstrated-easy fight (the feather/chicken hunt). Skipped if we've
       ourselves lost to this monster (any sub-threshold result), honouring the
       "until a future loss" caveat.
    3. STAT PREDICTION (`predict_win`): the optimistic formula, used cold.

    A cold/absent history defers to the prediction. Pass history at runtime (target
    selection); the planning gates call it stat-only since the veto is applied
    upstream.
    """
    if history is not None:
        samples = history.sample_count(f"Fight({monster_code})")
        if (samples >= MIN_WIN_SAMPLES
                and history.success_rate(f"Fight({monster_code})") < WIN_RATE_THRESHOLD):
            return False
        if _won_at_or_above_level(history, game_data, monster_code):
            return True
    return predict_win(state, game_data, monster_code)


def _won_at_or_above_level(
    history: LearningStore, game_data: GameData, monster_code: str) -> bool:
    """True when we've recorded an actual WIN (>=1 outcome 'ok') against some monster
    whose level is >= this monster's level, and we have NOT lost to this monster
    ourselves. A win against a no-easier monster is monotonic evidence this one is
    winnable too. Uses raw `win_count` (NOT warmup-gated `success_rate`, which reads
    1.0 below 5 samples and can't see a single win). The own-loss guard — any recorded
    fight against this monster that was not a win — honours "until a future loss"."""
    target_repr = f"Fight({monster_code})"
    if history.sample_count(target_repr) > history.win_count(target_repr):
        return False  # at least one loss against this monster -> defer to prediction
    target_level = game_data.monster_level(monster_code)
    for other, level in game_data.monster_levels.items():
        if level >= target_level and history.win_count(f"Fight({other})") >= 1:
            return True
    return False
