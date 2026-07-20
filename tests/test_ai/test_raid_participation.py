"""Raid participation gates (epic P4).

A raid is NOT judged by `is_winnable`. Upstream: "You win a raid fight by either
surviving all 100 turns or finishing the boss", and the boss has a shared HP pool
across every participating account -- so `predict_win` against it is meaningless.
Participation is THROUGHPUT: contribute damage, survive, collect
damage-thresholded rewards.

Two gates replace the win verdict:

* SURVIVABILITY -- one engagement must leave the character above the critical-HP
  floor. Raid death is ORDINARY death (respawn + death counter, no item loss), so
  this gate is not about fearing death: dying mid-window forfeits the rest of that
  window's damage throughput, which is the entire reason to engage.
* WORTH -- expected damage over the remaining window must clear at least one
  reward threshold, or the bot is spending cooldowns for nothing. Per changelog
  8.2.0 a raid yields 1 event ticket per 20,000 damage dealt.
"""

import pytest

from artifactsmmo_cli.ai.raid_participation import (
    raid_survivable_pure,
    raid_worth_pure,
)
from artifactsmmo_cli.ai.thresholds import CRITICAL_HP_FRACTION, RAID_TICKET_DAMAGE

# ─── survivability ───────────────────────────────────────────────────────────

def test_survivable_when_engagement_leaves_headroom():
    # 100 damage against 1000 max HP at full health: ends at 900, far above floor.
    assert raid_survivable_pure(hp=1000, max_hp=1000, expected_damage=100) is True


def test_not_survivable_when_engagement_would_drop_below_critical_floor():
    # floor = 0.75 * 1000 = 750; 300 damage from full ends at 700 -> refuse.
    assert raid_survivable_pure(hp=1000, max_hp=1000, expected_damage=300) is False


def test_not_survivable_when_already_below_the_floor():
    """Starting under the floor means rest first, whatever the damage."""
    assert raid_survivable_pure(hp=100, max_hp=1000, expected_damage=1) is False


def test_not_survivable_when_engagement_is_lethal():
    assert raid_survivable_pure(hp=500, max_hp=1000, expected_damage=500) is False


def test_survivability_uses_the_shared_critical_floor():
    """Pinned to the SAME constant the HP guard uses -- a second, independently
    tuned raid floor would drift from the guard that actually rests the bot."""
    max_hp = 1000
    floor = int(CRITICAL_HP_FRACTION * max_hp)
    # Landing exactly ON the floor is not above it -> refuse.
    assert raid_survivable_pure(hp=max_hp, max_hp=max_hp,
                                expected_damage=max_hp - floor) is False
    assert raid_survivable_pure(hp=max_hp, max_hp=max_hp,
                                expected_damage=max_hp - floor - 1) is True


@pytest.mark.parametrize("max_hp", [0, -10])
def test_survivability_rejects_degenerate_max_hp(max_hp):
    assert raid_survivable_pure(hp=10, max_hp=max_hp, expected_damage=1) is False


# ─── worth ───────────────────────────────────────────────────────────────────

def test_worth_when_window_damage_clears_a_reward_threshold():
    # 2000 dmg/fight * 10 fights = 20000 = exactly one ticket.
    assert raid_worth_pure(damage_per_fight=2000, fights_remaining=10) is True


def test_not_worth_when_window_damage_falls_short():
    assert raid_worth_pure(damage_per_fight=2000, fights_remaining=9) is False


def test_not_worth_for_a_character_that_contributes_nothing():
    """The honest case the design calls out: a weak character contributes
    nothing and should not be sent to die."""
    assert raid_worth_pure(damage_per_fight=0, fights_remaining=1000) is False


def test_not_worth_when_no_window_remains():
    assert raid_worth_pure(damage_per_fight=100000, fights_remaining=0) is False


def test_worth_threshold_is_the_documented_ticket_rate():
    """1 ticket per 20,000 damage (changelog 8.2.0)."""
    assert RAID_TICKET_DAMAGE == 20000
    assert raid_worth_pure(damage_per_fight=RAID_TICKET_DAMAGE, fights_remaining=1) is True
    assert raid_worth_pure(damage_per_fight=RAID_TICKET_DAMAGE - 1, fights_remaining=1) is False
