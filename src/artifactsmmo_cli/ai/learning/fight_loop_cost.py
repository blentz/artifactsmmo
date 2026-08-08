"""Cycles one KILL really costs: the fight, plus the recovery it forces.

`cheapest_path_to_level` priced a kill at exactly one cycle
(`FIGHT_CYCLES_PER_KILL`) — the fight action and nothing else. Measured over the
2026-08-07 traces, every character ran almost exactly one Rest per Fight:

    C3P0  22 fights / 21 rests      Lor   31 fights / 29 rests
    R2D2   1 fight  /  1 rest       Robby  4 fights /  4 rests

so fight actions were only ~51% of the combat loop and the projection was ~2x
optimistic. This is the same defect class as the constant it sits beside: a
quantity named "cycles to level 50" that counted some of the cycles. See
`FIGHT_CYCLES_PER_KILL`, which was a duration in SECONDS until 2026-08-07.

WHY IT MATTERS BEYOND THE FACTOR. A uniform 2x would cancel out of any ranking.
This one is not uniform — it is the ONLY channel through which DEFENSIVE gear can
pay. `reachable_level` moves only when the character can beat a HIGHER monster,
which is a weapon's job; armour's return is taking less damage and therefore
resting less. With rest cycles uncounted that return was exactly zero, and the
prediction is visible in the data: across 14 offline scenarios and two live trace
windows, every single GEAR verdict the unified objective ever produced was a
WEAPON. Never a shield, ring, amulet or armour piece.

DELIBERATELY NOT MODELLED: potion resupply. Live Robby drinks 5-8
`small_health_potion` per pig fight at ~4 gather-cycles each, which dwarfs even
the rest term — but that consumption is a POLICY the bot currently follows, not a
requirement of the fight (it wins those fights, and 271 HP of the loss is simply
rested off afterwards). Folding it in would bake today's behaviour into the
objective that is supposed to judge it, and `projected_heal_need_per_fight`'s
learned arm is not gear-sensitive anyway, so it would not move when armour
improved. The rest term is measured, gear-sensitive, and policy-free; the potion
term is none of the three.
"""

from artifactsmmo_cli.ai.thresholds import CRITICAL_HP_FRACTION

FIGHT_ACTIONS_PER_KILL = 1.0
"""The Fight action itself. One kill is one Fight, and the server cooldown after
it is wall-clock time, not another cycle."""

USABLE_HP_FRACTION = 1.0 - CRITICAL_HP_FRACTION
"""Share of max HP a character will actually spend before resting.

Derived from the HP_CRITICAL guard's own threshold (`tiers/guards`) rather than
restated, so the projection cannot drift from the policy the runtime runs."""


def rest_cycles_per_fight(expected_damage: int, max_hp: int) -> float:
    """Rest ACTIONS one fight forces, in [0, 1].

    A Rest refills to FULL in a single action (its duration varies, but duration
    is seconds and this is cycles — see `TYPICAL_FIGHT_COOLDOWN_SECONDS` for the
    other unit). So a character can chain every fight that fits inside the HP it
    is willing to spend, then pay exactly ONE rest to reset:

        usable HP  = (1 - CRITICAL_HP_FRACTION) * max_hp
        fights/rest = usable / damage
        rests/fight = damage / usable, capped at 1

    `CRITICAL_HP_FRACTION` (0.75) is the SAME threshold the HP_CRITICAL guard
    rests on (`tiers/guards`), not a second invented one — the projection must
    model the policy the runtime actually runs, or it prices a loop nobody
    executes.

    The cap at 1 is not a clamp for safety, it is the semantics: one Rest already
    restores everything, so no fight can ever force two. That also makes the term
    SATURATE, which is honest rather than convenient — while a fight still drops
    the character below the rest threshold, armour that merely reduces damage buys
    nothing here. The benefit arrives in a step, when damage finally fits inside
    the usable band and fights begin to chain.

    Calibration, live states against the 2026-08-07 traces (model / measured):
        Robby  vs pig        damage 462, max_hp 525 -> 1.00 / 1.00
        C3P0   vs red_slime  damage 144, max_hp 280 -> 1.00 / 0.95
        Lor    vs red_slime  damage 108, max_hp 280 -> 1.00 / 0.94
    All three saturate, which is why all three were observed resting after very
    nearly every fight.

    Across the FULL committed history (83 traces, `level_cost_replay.py`) the
    figure is 0.70 rests per fight, so the model runs ~1.4x high there. That gap
    is the sub-saturation regime being real: over months of play some fights were
    cheap enough relative to max HP to chain several per rest, which is precisely
    what this function returns below the threshold and precisely the regime a
    character escapes into by wearing better armour. Erring high is also the safe
    direction for a cost — it makes grinding look dearer than it is, never
    cheaper.

    Zero damage costs no rest, which is what keeps a genuinely trivial monster
    priced at the bare Fight action."""
    if expected_damage <= 0 or max_hp <= 0:
        return 0.0
    # `usable` is strictly positive here and needs no guard of its own: max_hp is
    # positive by the check above, and USABLE_HP_FRACTION is positive because
    # CRITICAL_HP_FRACTION is a fraction strictly below 1. A `usable <= 0` branch
    # stood here briefly and was dead code — unreachable, therefore untestable,
    # therefore a line asserting a fact no test could confirm. Should that
    # threshold ever be set to 1 or more, this raises ZeroDivisionError loudly
    # rather than quietly returning a plausible number for an impossible policy.
    return min(1.0, expected_damage / (USABLE_HP_FRACTION * max_hp))


def cycles_per_kill(expected_damage: int, max_hp: int) -> float:
    """Total planner actions one kill costs: the Fight plus the Rest it forces.

    This is the denominator `cheapest_path_to_level` divides xp-per-kill by, so
    it must be in the SAME unit as the xp figure it meets there — actions. Never
    seconds, and never a mix (`FIGHT_CYCLES_PER_KILL` was a 30-second cooldown
    named cycles until 2026-08-07, and the projection ran ~80x high)."""
    return FIGHT_ACTIONS_PER_KILL + rest_cycles_per_fight(expected_damage, max_hp)
