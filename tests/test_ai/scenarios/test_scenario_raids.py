"""A scenario must be able to declare an ACTIVE RAID (epic P3).

Until now `ScenarioCharacter` had no `raids` field, so no scenario could put a
live raid in the world. That blocks the l48_band_adequate resolution, which needs
BOTH polarities to be non-vacuous:

  * no raid active  -> the bot provably cannot plan (Wait is correct)
  * raid active     -> the bot plans raid participation

The negative half passes trivially today, so only the paired positive half proves
the planner gained anything -- and it cannot be written at all without this.

Mirrors `active_events`, which converts scenario codes into WorldState entries.
Raids differ: `RaidInfo.is_active()` keys on `status == "active"`, not on a
timestamp window, so a declared raid is active by construction.
"""

from artifactsmmo_cli.ai.scenario import SCENARIOS, ScenarioCharacter, scenario_state


def _sc_with_raid() -> ScenarioCharacter:
    base = SCENARIOS["l48_band_adequate"]
    return ScenarioCharacter(**{**vars(base), "raids": ("enchanted_fairy",)})


_DELIBERATE_RAID_SCENARIOS = {"l48_raid_active"}
"""Scenarios that declare a raid ON PURPOSE. Kept as an explicit allow-list so a
scenario cannot gain raid content by accident -- adding one here is a decision."""


def test_scenario_raids_are_opt_in():
    """Declaring a raid must be deliberate, or scenarios silently gain raid
    content and every raid-gated assertion elsewhere drifts."""
    declaring = {name for name, sc in SCENARIOS.items() if sc.raids}
    assert declaring == _DELIBERATE_RAID_SCENARIOS, declaring


def test_declared_raid_reaches_world_state_as_active():
    state = scenario_state(_sc_with_raid())
    assert [r.code for r in state.raids] == ["enchanted_fairy"]
    assert [r.code for r in state.active_raids] == ["enchanted_fairy"], (
        "a scenario-declared raid must read as ACTIVE; is_active() keys on "
        "status, so the conversion must set it"
    )


def test_undeclared_scenario_has_no_active_raid():
    """The negative pole of the l48 pair, at the state level."""
    state = scenario_state(SCENARIOS["l48_band_adequate"])
    assert state.raids == []
    assert state.active_raids == []
