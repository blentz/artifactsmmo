"""Combat-outcome estimator implementing the documented artifactsmmo fight
formula (https://docs.artifactsmmo.com/concepts/stats_and_fights).

Pure functions over WorldState + GameData; no API, no RNG. Critical strikes are
modelled as their expected contribution (deterministic) since the planner needs
a stable verdict, not a sampled fight."""

import math
from dataclasses import dataclass, replace
from fractions import Fraction

from artifactsmmo_cli.ai.elements import ELEMENTS
from artifactsmmo_cli.ai.equipment.loadout_cache import pick_loadout_cached
from artifactsmmo_cli.ai.equipment.projection import ProjectedStats, project_loadout_stats
from artifactsmmo_cli.ai.fight_odds_core import RoundDamage, burn_ticks, fight_odds, odds_clear
from artifactsmmo_cli.ai.fight_odds_core import win_probability as odds_win
from artifactsmmo_cli.ai.fight_terms_core import LOSE_MARGIN as LOSE_MARGIN
from artifactsmmo_cli.ai.fight_terms_core import MAX_TURNS as MAX_TURNS
from artifactsmmo_cli.ai.fight_terms_core import SCALE, FightTerms, fight_terms, terms_margin
from artifactsmmo_cli.ai.fight_terms_core import WIN_MARGIN as WIN_MARGIN
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_value_core import Combat
from artifactsmmo_cli.ai.group_fight_core import PartyBoss, PartyMember
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.loadout_profiles import combat_key
from artifactsmmo_cli.ai.utility_slot import UTILITY_SLOTS, utility_slot_quantity
from artifactsmmo_cli.ai.world_state import WorldState

SPLASH_RESTORE = "splash_restore"
"""The API effect of a splash potion: "Restores X HP at the start of the turn to
another character" — `hp_restore` carries its value too, but it never heals the
wearer, so the solo loop refuses it rather than walking it as a restore."""

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


DEFAULT_WIN_THRESHOLD = Fraction(4, 5)
"""The win probability a fight needs before its loss cost is measured (USER
2026-10-15: "0.8 default win rate until we collect enough win/loss data to
derive loss costs"; spec fight-gates-odds §1)."""

SECURE_WIN = Fraction(3, 4)
"""Below this win probability a fight asks for gear first (USER 2026-10-15: "if
all of our fights are below 75% win rates, we probably need better gear";
spec fight-gates-odds §3)."""


def win_threshold(state: WorldState, monster_code: str) -> Fraction:
    """θ for a fight against `monster_code`: this character's loss-cost
    threshold (`WorldState.win_thresholds`), or DEFAULT_WIN_THRESHOLD before
    there is evidence."""
    return state.win_thresholds.get(monster_code, DEFAULT_WIN_THRESHOLD)


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


def _crit_hit(attack: dict[str, int], dmg_global: int, dmg_elements: dict[str, int],
              resist: dict[str, int]) -> int:
    """One CRITICAL turn's damage: each element's net hit ×1.5, rounded half up
    per element — the server's rule (2026-10-15 fight logs: 77 → 116, 83 → 125,
    64 → 96). `(3 × d + 1) // 2` is ⌊1.5 × d + ½⌋ exactly."""
    return sum(
        (3 * _element_damage(attack.get(e, 0), dmg_global + dmg_elements.get(e, 0), resist.get(e, 0)) + 1) // 2
        for e in ELEMENTS
    )


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
    monster_greed: int, monster_enchanted_mirror: int, m_atk_sum: int,
) -> int:
    """Net per-turn die rate (player receiving damage, ×10000 scale).

    Mirrors Lean `dieStep` (PredictWin.lean:134). All inputs are ints;
    output is an int. A non-positive result means the player out-sustains the
    monster. See predict_win for the modelling rationale behind each term.
    Burn is a share of the MONSTER's summed attack `m_atk_sum`."""
    return (50 * raw_monster * (200 + m_crit)
            - p_crit * p_lifesteal * p_atk_sum
            + max(0, monster_poison - player_antipoison) * 10000
            + monster_burn * m_atk_sum * 100
            + monster_void_drain * player_max_hp * 100
            + monster_berserk * raw_monster * (200 + m_crit) // 2
            + monster_frenzy * raw_monster * (200 + m_crit) // 2
            + GREED_MAX_STACKS * monster_greed * raw_monster * (200 + m_crit) // 2
            + monster_enchanted_mirror * raw_player * (200 + p_crit) // 2)


def fight_loadout(state: WorldState, game_data: GameData, monster_code: str) -> dict[str, str]:
    """The loadout a fight against `monster_code` is fought in: the best on-hand
    combat loadout (`pick_loadout_cached`), which `FightAction` requires be
    worn. `predict_win` evaluates it and the learned-loss veto asks about it."""
    loadout = pick_loadout_cached(
        Combat(game_data.monster_attack(monster_code),
               game_data.monster_resistance(monster_code), dict(state.attack)),
        state, game_data,
    )
    return {slot: code for slot, code in loadout.items() if code is not None}


def fight_record(state: WorldState, game_data: GameData, monster_code: str,
                 history: LearningStore) -> tuple[int, int]:
    """(fights, wins) against `monster_code` at this level in the loadout the
    fight is fought in — the one reader of the learned record, for the
    learned-loss veto (`is_winnable`) and the loss-risk price
    (`fight_records`). USER 2026-10-05: "Old losses are gear-specific and
    level-specific"."""
    return history.combat_record(
        combat_key(monster_code), state.level, fight_loadout(state, game_data, monster_code))


def fight_records(state: WorldState, game_data: GameData,
                  history: LearningStore) -> tuple[tuple[str, int, int], ...]:
    """(monster, fights, wins) for every monster this character has lost to at
    its level, in that fight's loadout: the learned loss rates a fight's price
    carries (`SelectionContext.fight_records`; USER 2026-10-08, "Price the loss
    risk"). A monster never lost to has no surcharge and is absent, and so is
    one lost to only in ANOTHER loadout: no fight in this one is no record."""
    prefix = combat_key("")
    records: list[tuple[str, int, int]] = []
    for key in history.lost_task_keys(state.level):
        if not key.startswith(prefix):
            continue
        monster = key[len(prefix):]
        samples, wins = fight_record(state, game_data, monster, history)
        if samples > 0:
            records.append((monster, samples, wins))
    return tuple(records)


def _fight_projection(state: WorldState, game_data: GameData,
                      monster_code: str) -> tuple[dict[str, str | None], ProjectedStats]:
    """The best on-hand loadout for a fight against `monster_code`, and the stats
    it projects: what `combat_terms` resolves and `fight_max_hp` reads."""
    loadout = pick_loadout_cached(
        Combat(game_data.monster_attack(monster_code),
               game_data.monster_resistance(monster_code), dict(state.attack)),
        state, game_data,
    )
    return loadout, project_loadout_stats(state, loadout, game_data)


def fight_max_hp(state: WorldState, game_data: GameData, monster_code: str) -> int:
    """The max HP a fight against `monster_code` is fought at: the projected
    loadout's, the same `max_hp` `combat_terms` builds the terms over."""
    return _fight_projection(state, game_data, monster_code)[1].max_hp


@dataclass(frozen=True)
class FightNumbers:
    """`combat_terms`' terms with what a party fight splits out of them: the
    raw hit, the cost of one monster hit (`die_step` less every term charged
    targeted or not), the loadout's max HP and threat."""

    terms: FightTerms
    raw_player: int
    hit: int
    max_hp: int
    threat: int
    damage: RoundDamage


def combat_terms(state: WorldState, game_data: GameData, monster_code: str) -> FightTerms:
    """`fight_numbers`' terms."""
    return fight_numbers(state, game_data, monster_code).terms


def boss_drain(game_data: GameData, monster_code: str) -> int:
    """The kill-step terms charged once per MONSTER turn — its lifesteal on
    crit and its healing — as a positive rate: `_kill_step_net` with no player
    side, negated."""
    return -_kill_step_net(
        0, 0, game_data.monster_critical_strike(monster_code),
        game_data.monster_lifesteal(monster_code),
        sum(game_data.monster_attack(monster_code).values()),
        game_data.monster_hp(monster_code), game_data.monster_healing(monster_code),
        0, 0, 0, 0)


def party_boss(game_data: GameData, monster_code: str) -> PartyBoss:
    """The boss's side of a party fight (`group_fight_core`)."""
    return PartyBoss(
        game_data.monster_hp(monster_code) + game_data.monster_barrier(monster_code),
        game_data.monster_reconstitution(monster_code), boss_drain(game_data, monster_code))


def party_member(state: WorldState, game_data: GameData, monster_code: str,
                 restore: int, stock: int) -> PartyMember:
    """One member of a party fight against `monster_code`, in its best on-hand
    loadout with `stock` restore potions of `restore` HP: its solo terms split
    so that `net - boss_drain` is its `kill_step` and `hit + area` its
    `die_step`."""
    n = fight_numbers(state, game_data, monster_code)
    return PartyMember(
        raw=n.raw_player, net=n.terms.kill_step + boss_drain(game_data, monster_code),
        hit=n.hit, area=n.terms.die_step - n.hit, hp=state.hp, max_hp=n.max_hp,
        first=n.terms.player_first, threat=n.threat, restore=restore, stock=stock)


def fight_numbers(state: WorldState, game_data: GameData, monster_code: str) -> FightNumbers:
    """The closed form's per-turn terms for a fight against `monster_code` in the
    best on-hand loadout (inventory + equipped) for it: `predict_win` and
    `combat_margin` read their verdict from these, and the consumable turn walk
    (`fight_outcome_core`) walks them.

    Uses CURRENT hp (state.hp), not projected max_hp. Prior version used
    p.max_hp which over-predicted wins when the player was already damaged
    — trace cycle 63 (run 9, 2026-06-03): bot at HP=49/125 (39%) was
    predicted to win a chicken fight, fought, lost. The fight starts at
    state.hp, not max_hp; project_loadout_stats may raise max_hp via
    equipment but doesn't refill current hp."""
    loadout, p = _fight_projection(state, game_data, monster_code)
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
    # Monster lifesteal heals it on ITS crit, lowering our NET kill rate.
    m_attack = game_data.monster_attack(monster_code)
    m_atk_sum = sum(m_attack.values())
    # Monster healing is per-turn regen (a % of its HP every 3 turns), modeled
    # conservatively as the full per-3-turn amount EVERY turn (3× upper bound):
    # subtract it from the net kill step. A monster we can't out-damage out-heals
    # itself ⇒ kill_step <= 0 ⇒ unkillable (the UNKILLABLE exit).
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
    # Barrier is an absorbing shield: model it conservatively as extra effective HP
    # the player must chew through (per-5-turn refresh deferred — first cut flat add).
    effective_monster_hp = game_data.monster_hp(monster_code) + game_data.monster_barrier(monster_code)
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
    # is a share of the MONSTER's attack (`fight_odds_core.burn_ticks`): the closed
    # form charges the first tick, unrounded, as burn% × m_atk_sum × 100 every round.
    # The ticks decay, so this bounds every LATER tick; the first is rounded half
    # up (15% x 45 = 6.75 -> 7), so it can exceed the charge by under 1 HP. The
    # odds walk charges the exact ticks instead.
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
        m_atk_sum,
    )
    # One monster hit: `_die_step` with every term a non-target also pays zeroed.
    hit = _die_step(
        raw_monster, m_crit, p.critical_strike, 0, p_atk_sum, 0, 0, p.max_hp, 0,
        game_data.monster_berserker_rage(monster_code),
        game_data.monster_frenzy(monster_code),
        0, 0, game_data.monster_greed(monster_code), 0, m_atk_sum,
    )
    threat = sum(
        st.threat for code in final_equip.values()
        if code and (st := game_data.item_stats(code)) is not None
    )
    terms = fight_terms(
        raw_player, kill_step, effective_monster_hp,
        game_data.monster_reconstitution(monster_code), die_step,
        state.hp, p.max_hp,
        p.initiative >= game_data.monster_initiative(monster_code),
    )
    crit_player = _crit_hit(p.attack, p.dmg, p.dmg_elements, m_resist)
    crit_monster = _crit_hit(m_attack, 0, {}, p.resistance)
    # Everything a round charges beyond the bare hit (spec 2026-10-15 §1): the
    # expected step less its hit term, applied to both crit outcomes.
    kill_rest = kill_step - raw_player * SCALE - 50 * raw_player * p.critical_strike
    # Burn is not one of them: the walk charges its decaying ticks (off the
    # MONSTER's attack, `burn_ticks`) instead of `die_step`'s per-round bound.
    flat_burn = game_data.monster_burn(monster_code) * m_atk_sum * 100
    die_rest = die_step - flat_burn - raw_monster * SCALE - 50 * raw_monster * m_crit
    damage = RoundDamage(
        effective_monster_hp,
        raw_player * SCALE + kill_rest, crit_player * SCALE + kill_rest, p.critical_strike,
        raw_monster * SCALE + die_rest, crit_monster * SCALE + die_rest, m_crit,
        burn_ticks(game_data.monster_burn(monster_code), m_atk_sum),
    )
    return FightNumbers(terms, raw_player, hit, p.max_hp, threat, damage)


def fight_split(state: WorldState, game_data: GameData, monster_code: str) -> tuple[FightTerms, RoundDamage]:
    """`fight_numbers`' terms and the round's crit split, from the same integers."""
    n = fight_numbers(state, game_data, monster_code)
    return n.terms, n.damage


def worn_restore(state: WorldState, game_data: GameData) -> tuple[int, int]:
    """`(restore HP, stock)` of the first worn utility potion that heals the
    wearer, `(0, 0)` without one. A `splash_restore` heals another character."""
    for slot in UTILITY_SLOTS:
        code = state.equipment.get(slot)
        if not code or SPLASH_RESTORE in game_data.effect_codes(code):
            continue
        stats = game_data.item_stats(code)
        if stats is not None and stats.hp_restore > 0:
            return stats.hp_restore, utility_slot_quantity(state, slot)
    return 0, 0


def unpotioned(state: WorldState) -> WorldState:
    """`state` fighting on BARE gear: the worn restore potions stay worn but
    none is drunk (`worn_restore` reads stock 0; it is the only fight reader of
    a utility slot's quantity). Every GEAR question asks it — a rung cleared
    (`tier_progress.tier_cleared`), the band's bare fight
    (`band_target.BandTarget.bare_fight`), a fight secure enough to need no
    gear (`SelectionContext.combat_risky`, `combat_deficit`'s routing walk) —
    so a potion-propped win never hides a gear upgrade. Live probe 2026-10-16:
    40 worn greater health potions take `l25_currency_leaf_unfunded` from P 0
    to P 1 against every rung-20 to rung-30 monster."""
    return replace(state, utility1_slot_quantity=0, utility2_slot_quantity=0)


def win_probability(state: WorldState, game_data: GameData, monster_code: str) -> Fraction:
    """P(win) of fighting now: from `state.hp`, in the on-hand loadout
    `predict_win` reads, drinking the worn restore potion (spec §4)."""
    terms, damage = fight_split(state, game_data, monster_code)
    restore, stock = worn_restore(state, game_data)
    return odds_win(fight_odds(terms, damage, state.hp,
                               fight_max_hp(state, game_data, monster_code), restore, stock))


def predict_win(state: WorldState, game_data: GameData, monster_code: str) -> bool:
    """The fight verdict every gate reads (spec 2026-10-15 fight-gates-odds §1):
    the exact P(win) from `state.hp` in the best on-hand loadout with the worn
    restore potion (`win_probability`), at least this character's threshold for
    the monster (`win_threshold`).

    It was the closed form's expected-round race (`terms_win`), which reads
    crit at its mean: C3P0 v cyclops at margin 1 was "won" at P 0.51, and lost
    52 of 140 fights since 2026-10-10."""
    return odds_clear(win_probability(state, game_data, monster_code),
                      win_threshold(state, monster_code))


def secure_win(state: WorldState, game_data: GameData, monster_code: str) -> bool:
    """A fight won often enough that gear is not the better use of time (spec
    §3): P(win) at least max(θ, SECURE_WIN). The gear arm reads it
    (`combat_deficit`, `SelectionContext.combat_risky`)."""
    return odds_clear(win_probability(state, game_data, monster_code),
                      max(win_threshold(state, monster_code), SECURE_WIN))


def combat_margin(state: WorldState, game_data: GameData, monster_code: str) -> int:
    """The closed form's signed round cushion, whose sign equals its own
    expected-round verdict (`fight_terms_core.terms_win`): a gear-ranking
    signal (`combat_deficit` ranks candidates on its gain), NOT the fight
    verdict, which reads the odds (`predict_win`, spec 2026-10-15
    fight-gates-odds §4). Part C replaces it with the odds.

    Read from `combat_terms` (`fight_terms_core.terms_margin`), returning int
    sentinels or the round-cushion at each exit:
    * ``raw_player <= 0``                        → ``LOSE_MARGIN``
    * ``kill_step <= 0``                         → ``LOSE_MARGIN``
    * ``rounds_to_kill > MAX_TURNS``             → ``LOSE_MARGIN``
    * reconstitution kills before we do          → ``LOSE_MARGIN``
    * ``die_step <= 0`` (out-sustain)            → ``WIN_MARGIN``
    * ``effective_hp <= 0``                      → ``LOSE_MARGIN``
    * numeric regime: ``rounds_to_die - rounds_to_kill + (1 if player_first else 0)``

    Mirrors Lean ``Formal.PredictWin.combatMargin`` (PredictWin.lean).
    """
    return terms_margin(combat_terms(state, game_data, monster_code))


def is_winnable(
    state: WorldState,
    game_data: GameData,
    monster_code: str,
    history: LearningStore | None = None,
) -> bool:
    """The single combat-beatability verdict used across planning and runtime.

    Two gates, in order:
    1. LEARNED-LOSS veto, when a history is supplied: a monster lost in >=
       MIN_WIN_SAMPLES observed fights at < WIN_RATE_THRESHOLD success is judged
       unwinnable regardless of the odds — counting ONLY fights at this level in
       this loadout (`fight_loadout`).
    2. THE ODDS (`predict_win`): exact P(win) against this character's threshold.

    There was a MONOTONIC-WIN shortcut between them: a win against any monster
    of level >= this one's made this one winnable until a loss against it. It
    rescued a pessimistic closed form; the odds are calibrated (part A's live
    check, 2026-10-15), and the shortcut said "winnable" for a coin-flip fight
    until its first loss (spec 2026-10-15 fight-gates-odds §4).

    A cold/absent history defers to the prediction. Pass history at runtime (target
    selection); the planning gates call it stat-only since the veto is applied
    upstream.
    """
    # LEVEL- AND GEAR-SCOPED (USER 2026-10-05: "Old losses are gear-specific
    # and level-specific"). The veto read every Fight(monster) cycle ever
    # recorded, so a monster lost to once could never be fought again — and
    # a vetoed monster is never fought, so no later evidence could clear it.
    # Live: C3P0 lost 42/42 to its task pig at level 19 (2026-08-20); at
    # level 30 the stats win and the veto still refused, holding the task
    # inert. Evidence about another level or another loadout is evidence
    # about a different fight.
    if history is not None and loss_vetoed(state, game_data, monster_code, history):
        return False
    return predict_win(state, game_data, monster_code)


def loss_vetoed(state: WorldState, game_data: GameData, monster_code: str,
                history: LearningStore) -> bool:
    """The LEARNED-LOSS veto (`is_winnable`'s first gate): at least
    MIN_WIN_SAMPLES recorded fights against `monster_code` at this level in the
    loadout the fight is fought in (`fight_record`), won below
    WIN_RATE_THRESHOLD. Also the band target's: a fight carried by consumables
    (`band_target.band_combat_target`) is refused on the same record."""
    return _vetoes(*fight_record(state, game_data, monster_code, history))


def _vetoes(samples: int, wins: int) -> bool:
    """The learned-loss veto's rule on a record of `samples` fights and `wins`."""
    return samples >= MIN_WIN_SAMPLES and wins < WIN_RATE_THRESHOLD * samples


def lost_fights(state: WorldState, game_data: GameData, history: LearningStore) -> frozenset[str]:
    """Every monster the learned-loss veto refuses this character at its level,
    in that fight's loadout (`fight_records`, `loss_vetoed`'s rule): the
    `WorldState.lost_fights` the drop gate's solo arms read."""
    return frozenset(monster for monster, samples, wins in fight_records(state, game_data, history)
                     if _vetoes(samples, wins))

