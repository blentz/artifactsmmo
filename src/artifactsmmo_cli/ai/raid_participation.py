"""Whether to engage an active raid boss this cycle.

A raid is deliberately NOT judged by `is_winnable`. Upstream states the win
condition as "surviving all 100 turns or finishing the boss", and the boss carries
a shared HP pool across every participating account, so `predict_win` against it
answers a question nobody is asking. Participation is THROUGHPUT: deal damage,
stay alive, collect damage-thresholded rewards (1 event ticket per 20,000 damage,
changelog 8.2.0, delivered to pending items after the raid ends).

Two gates replace the win verdict.

Death on a raid is ORDINARY death (user, 2026-07-20, per the changelog): respawn
at spawn point, death counter incremented. No item loss. So a raid loss is a TIME
cost -- the walk back plus the cooldowns spent -- not a catastrophe.

The survivability gate is kept anyway, and deliberately so: dying mid-window
forfeits the rest of that window's damage throughput, which is the whole point of
engaging. Avoiding death here is about not wasting the raid, not about fearing it.
"""

from artifactsmmo_cli.ai.thresholds import CRITICAL_HP_FRACTION, RAID_TICKET_DAMAGE


def raid_survivable_pure(hp: int, max_hp: int, expected_damage: int) -> bool:
    """True when one engagement leaves the character STRICTLY above the critical
    HP floor.

    Uses the same `CRITICAL_HP_FRACTION` the HP guard rests on, rather than a
    second raid-specific floor: two independently tuned floors would drift, and
    the guard is what actually rests the bot between engagements.

    Strictly above, not at: landing exactly on the floor arms the HP guard on the
    next cycle, which would leave the bot alternating rest and engage instead of
    contributing damage.

    Not a fear of death -- death is an ordinary respawn -- but of forfeiting the
    remaining window, which is where the damage throughput lives.
    """
    if max_hp <= 0 or expected_damage < 0:
        return False
    floor = int(CRITICAL_HP_FRACTION * max_hp)
    if hp <= floor:
        return False              # rest first, whatever the engagement costs
    return hp - expected_damage > floor


def raid_worth_pure(damage_per_fight: int, fights_remaining: int) -> bool:
    """True when expected damage across the remaining window clears at least one
    reward threshold.

    Below the bar the goal must not fire: a character that cannot reach a
    threshold spends its cooldowns and gets nothing, which is the honest reading
    of a weak character's contribution rather than a reason to send it anyway.
    """
    if damage_per_fight <= 0 or fights_remaining <= 0:
        return False
    return damage_per_fight * fights_remaining >= RAID_TICKET_DAMAGE
