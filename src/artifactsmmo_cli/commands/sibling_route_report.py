"""`artifactsmmo sibling-route-audit` — read-only: whether a sibling's
crafting skill changes any price.

The oracle for T2. Task 1 (`audit/sibling_route_census.py`) built the
differential that answers, per item, whether the sibling-craft route is
ELIGIBLE (behind this character's own gate, but a live sibling clears it),
PRICED (`route_options` actually returned it), and LOAD-BEARING (pricing the
item without it costs more). This command is what turns that census into a
live number: it enumerates the candidate items, runs the census over them
against this character's real state and the fleet's real `SkillLedger`, and
prints all three counts.

ALL THREE COUNTS PRINT, EVEN WHEN THE LOWER TWO ARE ZERO. "Eligible 30,
priced 0" is the finding that a gate suppresses the route entirely; a report
that only showed load-bearing rows would print nothing in that case, and
nothing reads as "no candidates" — a different and wrong conclusion. See
`audit/sibling_route_census.py`'s module docstring for the three failure
modes this distinction exists to tell apart.

`PRICED` IS STRUCTURALLY EITHER 0 OR EQUAL TO `ELIGIBLE`, NOT AN
INDEPENDENT PER-ROUTE CONFIRMATION, AND THE HEADER SAYS SO. `_eligible_candidates`
selects exactly `held < required <= best_sibling`, which is the negation of
`_sibling_craft_option`'s first two early returns (own skill already clears
the gate; no sibling clears it). `route_options` calls that option
unconditionally for every remaining item, with the same state/ctx/store. The
ONLY gate left is `store.fleet_supply_request_cycles()` — one scalar READ
ONCE PER RUN, identical for every item it prices — `None` or `<= 0` declines
every sibling route at once, any other value prices every eligible route at
once. So a reader cannot take "30 priced" as "30 routes independently
confirmed"; it is one global bit, and the header prints the scalar behind it
so that bit is never implicit.

SAVINGS ARE NOT STABLE ACROSS RUNS, AND THE HEADER SAYS THAT TOO.
`actions_without` prices the item through `_gated_craft_option`'s own grind
route, which reads `store.skill_grind_rate` off recent `LevelSkill` cycles —
a live, continuously-updated observation the fleet keeps re-measuring. Two
runs minutes apart can (and do) report the same eligible/priced/load-bearing
counts with a different headline saving. That is honest variance in what is
being measured, not a defect, but nothing about the number on its own says
so — the header does.

Read-only: senses state, computes, prints. No actions, and `_sense` uses an
in-memory `LearningStore` so a diagnostic run cannot write session rows into
the fleet's db — same discipline as `commands/objective_audit_report.py` and
`commands/combat_deficit_report.py`. The coordination and learning stores
this command reads FROM (`sibling_skill_levels`, `fleet_supply_request_cycles`)
are real, on-disk reads against the fleet's actual database — sensing live
state, not writing it.
"""

from dataclasses import replace
from datetime import UTC, datetime

import typer

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.coordination_store import CoordinationStore
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.audit.sibling_route_census import SiblingVerdict, sibling_route_verdicts
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config
from artifactsmmo_cli.learning_db_path import default_learn_db_path


def _sense(character: str) -> tuple[WorldState, GameData]:
    """Live state and catalogue for CHARACTER, sensed exactly as
    `objective-audit`/`combat-deficit` do it: a fresh, in-memory
    `LearningStore` so this read-only command cannot write session rows into
    the fleet's own database, and `GamePlayer.plan_once()` to populate
    `state`/`game_data` before either is read.
    """
    config = Config.from_token_file()
    ClientManager().initialize(config)
    store = LearningStore(db_path=":memory:", character=character)
    store.start_session()
    try:
        player = GamePlayer(character=character, history=store,
                            game_data_ttl_minutes=config.game_data_ttl_minutes)
        player.plan_once()
        state, game_data = player.state, player.game_data
        if state is None or game_data is None:
            raise typer.BadParameter(f"could not sense state for {character!r}")
        return state, game_data
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def _eligible_candidates(
    state: WorldState, game_data: GameData, sibling_skills: dict[str, int],
) -> list[str]:
    """Every craftable item this character is behind the crafting gate on AND
    some live sibling clears — ELIGIBLE (`held_level < required_level <=
    best_sibling_level`), read straight off the item catalogue.

    `sibling_route_verdicts` deliberately does NOT filter to eligible on its
    own (its docstring: a caller auditing "did I miss an eligible pair" must
    see every item it asked about) — enumerating the eligible set is this
    command's job, not the census's, per the task-1 ruling that kept the
    census pure and testable. An item with no `crafting_skill` names no gate
    at all and is skipped, same as the census's own skip branch.

    ALSO requires `game_data.crafting_recipe(item) is not None`, matching
    `sibling_route_verdicts`'s own skip condition exactly (`recipe is None or
    stats is None or not stats.crafting_skill`). Without this check an item
    that names a `crafting_skill` but has no recipe would count toward
    `eligible` here while the census silently skips it (emits no verdict at
    all), so `eligible` could exceed `len(verdicts)` and the
    priced/load-bearing counts (both derived from `verdicts`) would then be
    measured against a denominator this function never actually asked the
    census about. On live data `crafting_skill` and the recipe always come
    from the same `item.craft` API block, so this never diverges from the
    skill-only check today — but the check is what keeps that a fact about
    the data rather than an assumption this function bakes in.
    """
    candidates = []
    for code, stats in sorted(game_data.items.stats.items()):
        skill = stats.crafting_skill
        if not skill or game_data.crafting_recipe(code) is None:
            continue
        required = stats.crafting_level
        held = state.skills.get(skill, 1)
        best_sibling = sibling_skills.get(skill, 0)
        if held < required <= best_sibling:
            candidates.append(code)
    return candidates


def _print_load_bearing_row(v: SiblingVerdict) -> None:
    print(f"{v.item:<25} {v.skill:<16} lvl {v.held_level}->{v.required_level} "
          f"(sibling holds {v.best_sibling_level}) "
          f"saving {v.saving} actions ({v.actions_with} with vs "
          f"{v.actions_without} without)")


def sibling_route_audit_command(
    character: str = typer.Argument(..., help="Character to audit"),
) -> None:
    """Print the eligible / priced / load-bearing counts for the sibling-craft
    route, then the load-bearing rows, largest saving first."""
    state, game_data = _sense(character)

    db_path = default_learn_db_path()
    coordination = CoordinationStore(db_path=db_path, character=character)
    sibling_skills = coordination.sibling_skill_levels(datetime.now(UTC))
    store = LearningStore(db_path, character=character)

    candidates = _eligible_candidates(state, game_data, sibling_skills)
    ctx = replace(NO_PROFILE_CONTEXT, sibling_skills=sibling_skills)
    verdicts = sibling_route_verdicts(state, game_data, ctx, store, candidates)

    priced = [v for v in verdicts if v.priced]
    load_bearing = sorted((v for v in verdicts if v.load_bearing),
                          key=lambda v: v.saving, reverse=True)

    print(f"== sibling-route audit ({character}) ==")
    # THE ONE SCALAR `priced` ACTUALLY TURNS ON. `_sibling_craft_option` reads
    # this once per run and applies the SAME None-or-<=0 decision to every
    # eligible item, so `priced` can only land at 0 or at `eligible` -- never
    # strictly between them. Printing the scalar makes that global bit
    # explicit instead of letting "N priced" read as N independent
    # confirmations.
    supply_cycles = store.fleet_supply_request_cycles()
    print(f"fleet_supply_request_cycles: {supply_cycles}")
    print(f"{len(candidates)} eligible")
    print(f"{len(priced)} priced")
    print(f"{len(load_bearing)} load-bearing")
    print("priced can only diverge from eligible when fleet_supply_request_cycles "
          "is None or <= 0 (every route declines at once); priced == eligible is "
          "the expected case, not per-route confirmation.")
    if load_bearing:
        print("\nload-bearing routes (largest saving first):")
        print("savings are priced off a live-updating skill_grind_rate "
              "observation and will drift between runs -- a different number "
              "on a rerun is not a regression.")
        for v in load_bearing:
            _print_load_bearing_row(v)
