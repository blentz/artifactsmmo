"""What one KILL really costs: the Fight, plus the share of a Rest it forces.

`cheapest_path_to_level` priced a kill at exactly one cycle
(`FIGHT_ACTIONS_PER_KILL`) — the fight action and nothing else. Measured over the
2026-08-07 traces, every character ran almost exactly one Rest per Fight:

    C3P0  22 fights / 21 rests      Lor   31 fights / 29 rests
    R2D2   1 fight  /  1 rest       Robby  4 fights /  4 rests

so fight actions were only ~51% of the combat loop and the projection was ~2x
optimistic. This is the same defect class as the constant it sits beside: a
quantity named "cycles to level 50" that counted some of the cycles. See
`FIGHT_ACTIONS_PER_KILL`, which was a duration in SECONDS until 2026-08-07.

WHY IT MATTERS BEYOND THE FACTOR. A uniform 2x would cancel out of any ranking.
This one is not uniform — it is the ONLY channel through which DEFENSIVE gear can
pay. `reachable_level` moves only when the character can beat a HIGHER monster,
which is a weapon's job; armour's return is taking less damage and therefore
resting less. With rest cycles uncounted that return was exactly zero, and the
prediction is visible in the data: across 14 offline scenarios and two live trace
windows, every single GEAR verdict the unified objective ever produced was a
WEAPON. Never a shield, ring, amulet or armour piece.

REST IS NOT ONE ACTION'S WORTH OF TIME, AND CHARGING IT AS ONE SATURATED THE
ARMOUR CHANNEL SHUT. The first version of this module charged `min(1, damage /
usable)` — a pure count, capped, on the reasoning that one Rest refills the bar so
no fight can force two. The count is right and the cost is wrong. The published
rule (`ai/rest_cooldown_core`) is one second per one percent of missing hit
points, minimum three, so a Rest is anywhere from three to a hundred seconds while
a Fight is about thirty. Against a character taking 46% of its bar per fight, that
cap said "one action" for what is really a ninety-second recovery — three fights'
worth of elapsed time — and, worse, said the SAME thing for every heavier hit. The
term saturated, so above the threshold better armour bought literally nothing and
the ranking could not see it. That is the defect this module was written to fix,
reintroduced one layer down.

So the unit stays actions and the conversion is declared: a Rest costs its
published cooldown divided by `TYPICAL_FIGHT_COOLDOWN_SECONDS`, i.e. it is priced
in FIGHT-EQUIVALENTS. This is not the seconds/cycles confusion returning. That bug
was a number denominated in seconds while NAMED cycles, so consumers divided a
duration into an XP figure and ran 80x high. Here the number is in fight-
equivalents, is named so, and the one action whose duration is not roughly uniform
is the only one that gets converted. Refusing to convert is its own error in the
opposite direction, and it cost the ranking the whole defensive-gear channel.

THE POOL SIZE FALLS OUT, WHICH IS THE POINT. A character chains fights until the
HP guard trips, then pays one Rest to reset. Above the three-second floor that
Rest costs one second per percent recovered, and the percent recovered is the pool
— so the seconds per FIGHT are `100 * damage / max_hp` no matter how the chain is
batched. Batching changes how many Rest ACTIONS are executed but not how many
seconds they take, and `USABLE_HP_FRACTION` cancels out of the per-fight figure
entirely. That is why the old model's per-kill charge and the exact executed count
could disagree about a rung's price: they disagreed about a constant that, priced
in time, does not matter. Only below the floor does batching genuinely pay, and at
a 25% pool the floor is unreachable (25% of a bar is 25 seconds, not 3).

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

from artifactsmmo_cli.ai.rest_cooldown_core import rest_cooldown_seconds
from artifactsmmo_cli.ai.thresholds import CRITICAL_HP_FRACTION

FIGHT_ACTIONS_PER_KILL = 1.0
"""The Fight action itself. One kill is one Fight, and one Fight is the UNIT —
every other action in this module is priced as a multiple of it."""

TYPICAL_FIGHT_COOLDOWN_SECONDS = 30.0
"""Wall-clock cooldown of one Fight, in seconds. Corroborated at 29.10s mean /
29.85s median over 2483 observed fights in the committed traces.

This is both the fallback duration callers reasoning about elapsed time want
(`tiers/strategic_weights` combines it with move and deposit cooldowns into a
round-trip time) AND the seconds-per-unit of this module's cost. Those are the
same number by DEFINITION rather than by coincidence: the unit is one Fight, so
the seconds in a unit are the seconds in a Fight. Naming it once and deriving both
readings from that definition is the opposite of the mistake that named a 30-second
cooldown `DEFAULT_FIGHT_CYCLES` and let two meanings hide under one word."""

USABLE_HP_FRACTION = 1.0 - CRITICAL_HP_FRACTION
"""Share of max HP a character will actually spend before resting.

Derived from the HP_CRITICAL guard's own threshold (`tiers/guards`) rather than
restated, so the projection cannot drift from the policy the runtime runs. It
sets how many fights CHAIN between rests; above the three-second floor it does
not affect the per-fight cost, because a longer chain ends in a proportionally
longer Rest."""


def fights_per_rest(expected_damage: int, max_hp: int) -> int:
    """How many Fights the character chains before the HP guard forces a Rest.

    The guard reads hit points BEFORE a fight, not after, so the character
    commits to the fight that carries it across the threshold. It therefore
    chains one more fight than the pool strictly pays for, and finishes the chain
    below the threshold rather than exactly on it. Modelling the tidier
    `pool / damage` would price a loop the executor does not run.

    That boundary also carries the per-kill cost's MONOTONICITY, which is not
    obvious and was found by ratifying the spec rather than by a failing run.
    Chain length is a step function of damage, so where the two readings differ --
    a damage that divides the band exactly -- the tidier one shortens the chain by
    a whole fight and drops the per-kill share BELOW that of a slightly smaller
    damage. A heavier monster would then be cheaper per kill, and better armour
    could raise a rung's price. Swept over every whole bar from 20 to 2500 hit
    points and every whole damage, `rest_actions_per_fight` never decreases.

    Never returns less than one: whatever the damage, the character always takes
    at least one fight from full before any recovery is due. `expected_damage`
    and `max_hp` must both be positive — a fight that costs nothing forces no
    rest at all and has no chain length, and a character with no hit-point bar is
    not a state this game produces. Both raise loudly here rather than returning a
    plausible number for an impossible loop; `rest_actions_per_fight` screens them
    off before they reach this function.
    """
    return int(USABLE_HP_FRACTION * max_hp // expected_damage) + 1


def rest_actions_per_fight(expected_damage: int, max_hp: int) -> float:
    """Rest cost one Fight forces, in Fight-equivalents.

    One Rest is paid at the end of each chain and amortised over the fights in
    it. Its cooldown is the published one for the damage the whole chain
    accumulated — capped inside `rest_cooldown_seconds` at a full bar, since a
    Rest restores at most everything.

        chain    = fights_per_rest(damage, max_hp)
        seconds  = rest_cooldown_seconds(chain * damage, max_hp)
        per fight = seconds / (chain * TYPICAL_FIGHT_COOLDOWN_SECONDS)

    The result is monotone in damage across the WHOLE range and does not
    saturate, which is the property the capped version lacked and the reason
    armour can now pay continuously instead of in one step. Its ceiling is
    100 / 30 = 3.33 — a character rests off a full bar after every fight and
    spends three fights' worth of time doing it.

    Calibration, live states against the 2026-08-07 traces (this model / the
    superseded capped one / measured rest ACTIONS per fight):
        Robby  vs pig        damage 462, max_hp 525 -> 2.93 / 1.00 / 1.00
        C3P0   vs red_slime  damage 144, max_hp 280 -> 1.73 / 1.00 / 0.95
        Lor    vs red_slime  damage 108, max_hp 280 -> 1.29 / 1.00 / 0.94

    The measured column counts ACTIONS and all three sit at one, which is exactly
    what the capped model reproduced and exactly why it looked calibrated. Those
    same rests took 88, 52 and 39 seconds. The action count was never in dispute;
    what it cost was.

    Zero damage costs no rest, which is what keeps a genuinely trivial monster
    priced at the bare Fight action.
    """
    if expected_damage <= 0 or max_hp <= 0:
        return 0.0
    chain = fights_per_rest(expected_damage, max_hp)
    seconds = rest_cooldown_seconds(chain * expected_damage, max_hp)
    return seconds / (chain * TYPICAL_FIGHT_COOLDOWN_SECONDS)


def cycles_per_kill(expected_damage: int, max_hp: int) -> float:
    """Total planner actions one kill costs: the Fight plus the Rest it forces.

    This is the denominator `cheapest_path_to_level` divides xp-per-kill by, so
    it must be in the SAME unit as the xp figure it meets there — Fight-
    equivalents, never raw seconds and never a mix (`FIGHT_CYCLES_PER_KILL` was a
    30-second cooldown named cycles until 2026-08-07, and the projection ran ~80x
    high)."""
    return FIGHT_ACTIONS_PER_KILL + rest_actions_per_fight(expected_damage, max_hp)
