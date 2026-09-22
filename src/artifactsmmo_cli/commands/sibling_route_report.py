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

LOAD-BEARING ROWS PRINT ONE LINE PER GATE, NOT ONE PER ITEM. `saving` is a
per-(skill, required_level) grind quantity, not a per-item one — every item
behind the same gate reports the same magnitude, because the shared grind
unlock is what dominates it. A report that printed one row per item let a
reader sum the savings column and over-credit by roughly the group's size
(six identical `jewelrycrafting 13->20` rows summed to 6x the real saving of
clearing that one gate). `_group_by_gate` collapses that back to one line per
`(skill, required_level)`, listing every item behind it, and the header says
outright that the number is not additive across the listed items.

PRICED-BUT-NOT-LOAD-BEARING ROWS PRINT TOO. `priced` and `load_bearing` are
kept separate on purpose (see `audit/sibling_route_census.py`'s module
docstring) precisely so "outpriced" (priced, but an existing route already
undercuts it) can be told apart from "absent" (never priced at all) — a
report that only showed load-bearing rows made that distinction unreadable by
omission, so the outpriced items get their own short section instead of
vanishing into the difference between two counts.

T2.1 (`audit/root_sibling_census.py`) ADDS A SECOND, ROOT-LEVEL SECTION. T2.0
above answers whether `_sibling_craft_option` ever lowers a catalogue item's
priced cost; it says nothing about whether `decisions/root.resolve_root` —
the ONE place `decide_tree` gets its answer from — ever NAMES that item as
the thing to pursue. `_print_root_section` drives the same walk live and
classifies its own candidate set (`[resolution.root, *resolution.
alternatives]`, read off the resolution, never rebuilt), printing the count
of candidates, how many name an item, how many are sibling-priced, how many
are load-bearing, and the CHOSEN root's repr either way — because a chosen
root naming no item (`ReachCharLevel`, `ReachSkillLevel`) means the sibling
route could not apply this cycle at all, a different finding from the route
being priced and then outpriced.

NO `--all`: EVERY CHARACTER IS NAMED EXPLICITLY. The spec asks "for each
character", but the only roster source in this codebase is `GET
/my/characters` (`MultiRun.run`, `multi/multi_run.py:194`) — a real API
call, and this command's `_sense` seam exists specifically so a read-only
diagnostic can never reach one (see that seam's own docstring). Rather than
add a roster discovery path this command has never needed, `--character`/`-c`
is repeatable; the positional argument still works for a single character.
"""

from dataclasses import replace
from datetime import UTC, datetime

import typer

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.coordination_store import CoordinationStore
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.audit.root_sibling_census import RootSiblingVerdict, root_sibling_verdicts
from artifactsmmo_cli.audit.sibling_route_census import SiblingVerdict, sibling_route_verdicts
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config
from artifactsmmo_cli.learning_db_path import default_learn_db_path


def _sense(
    character: str,
) -> tuple[WorldState, GameData, SelectionContext, CharacterObjective]:
    """Live state, catalogue, selection context, and root objective for
    CHARACTER, sensed exactly as `objective-audit`/`combat-deficit` do it: a
    fresh, in-memory `LearningStore` so this read-only command cannot write
    session rows into the fleet's own database, and `GamePlayer.plan_once()`
    to populate `state`/`game_data`/`_last_ctx`/`_objective` before any of
    them is read.

    THE CONTEXT COMES FROM THE PLAYER, NOT `NO_PROFILE_CONTEXT`. This command
    used to price every route against `NO_PROFILE_CONTEXT`, a stand-in whose
    own docstring says it "is NOT a substitute for the player's real context"
    -- it forces `bank_accessible=True` unconditionally, carries no gear/step
    profile, no sibling bank/order claims, and no task draw, any one of which
    can flip a `load_bearing` verdict against what production would actually
    decide. `plan_once()` -> `plan_from_state()` sets `self._last_ctx = ctx`
    (`player.py:1087`) using the SAME `_selection_context` call production's
    own per-cycle decide uses (`commands/combat_deficit_report.py:62` is the
    working precedent for reading it in exactly this family of commands). The
    player's own `sibling_skills` is empty here -- `_refresh_sibling_reads`
    no-ops without an attached coordination store, which this read-only sense
    deliberately never attaches (see the module docstring) -- so the caller
    overrides only that one field, the same `replace`-one-field discipline
    `sibling_route_census.py` already uses for its own baseline arm.

    THE OBJECTIVE COMES FROM THE PLAYER TOO, NOT A SECOND CONSTRUCTION.
    `GamePlayer._initialize()` (called by `plan_once()`, BEFORE
    `plan_from_state()` sets `_last_ctx`) sets `self._objective =
    CharacterObjective.from_game_data(self.game_data)` unconditionally
    (`player.py:970`) -- the same object `decide_tree`/`resolve_root` use on
    every live cycle. Building a second `CharacterObjective` here would risk
    silently drifting from what production actually resolves against; reading
    the player's own attribute (same access pattern the rest of this test
    suite already uses for it, e.g. `test_player_strategy_shadow.py`) cannot.
    """
    config = Config.from_token_file()
    ClientManager().initialize(config)
    store = LearningStore(db_path=":memory:", character=character)
    store.start_session()
    try:
        player = GamePlayer(character=character, history=store,
                            game_data_ttl_minutes=config.game_data_ttl_minutes)
        player.plan_once()
        state, game_data, ctx = player.state, player.game_data, player._last_ctx
        objective = player._objective
        if state is None or game_data is None or objective is None:
            raise typer.BadParameter(f"could not sense state for {character!r}")
        return state, game_data, ctx, objective
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


def _group_by_gate(
    load_bearing: list[SiblingVerdict],
) -> list[tuple[str, int, list[SiblingVerdict]]]:
    """Load-bearing verdicts grouped by the GATE they share, `(skill,
    required_level)`, sorted largest-saving-first -- the level of granularity
    the printed magnitude is actually true at (I1).

    `_gated_craft_option`'s unlock key is `skill:{skill}:{level}` and
    `acquisition_cost_core.py` pays that unlock ONCE PER KEY, so every item
    behind the same gate shares one grind cost; `_sibling_craft_option`'s key
    is `sibling:{item}`, paid once PER ITEM. Printing one row per item put a
    per-gate quantity (the grind saving) on a per-item line, and a reader
    summing that column over-credited by roughly the group's size -- six
    `jewelrycrafting 13->20` items each reporting the identical 5,717-action
    saving summed to 34,302 when the real saving of clearing that one gate is
    ~5,717, not a multiple of it. Grouping by `(skill, required_level)`
    (not by item) is what makes that arithmetic honest: one line, one
    magnitude, the item list stays visible beside it.

    `held_level`/`best_sibling_level` are also gate-level facts, not
    per-item ones -- both are `state.skills.get(skill, ...)` /
    `ctx.sibling_skills.get(skill, ...)` reads keyed on the skill alone, so
    every member of a gate group carries the identical pair; this function
    does not need to reconcile them.
    """
    groups: dict[tuple[str, int], list[SiblingVerdict]] = {}
    for v in load_bearing:
        groups.setdefault((v.skill, v.required_level), []).append(v)
    ordered = sorted(
        groups.items(),
        key=lambda kv: max(v.saving for v in kv[1]), reverse=True)
    return [(skill, level, members) for (skill, level), members in ordered]


def _print_gate_line(skill: str, required_level: int, members: list[SiblingVerdict]) -> None:
    first = members[0]
    items = ", ".join(sorted(v.item for v in members))
    # Observed live: every item behind one gate reports the SAME saving,
    # because the dominant term on both arms is the shared unlock cost (the
    # grind, or the fleet's flat `fleet_supply_request_cycles` sibling-request
    # price) and per-item recipe-material costs are comparatively negligible.
    # Nothing in the pricer GUARANTEES that -- a gate whose members need
    # materially different quantities of their own recipe's materials could
    # print a genuine range -- so this prints the range honestly rather than
    # picking one member's number and hiding the rest.
    savings = sorted({v.saving for v in members})
    saving_desc = (f"saving {savings[0]}" if len(savings) == 1
                   else f"saving {savings[0]}-{savings[-1]} (varies within this gate)")
    print(f"{skill:<16} lvl {first.held_level}->{required_level} "
          f"(sibling holds {first.best_sibling_level}) {saving_desc} actions "
          f"-- {len(members)} item(s): {items}")


def _print_outpriced_row(v: SiblingVerdict) -> None:
    print(f"{v.item:<25} {v.skill:<16} lvl {v.held_level}->{v.required_level} "
          f"(sibling holds {v.best_sibling_level}) priced but not cheaper "
          f"(saving {v.saving})")


def _print_root_section(
    state: WorldState, game_data: GameData, objective: CharacterObjective,
    ctx: SelectionContext, store: LearningStore, character: str,
) -> None:
    """T2.1: does the sibling-craft route ever change what the ROOT WALK
    chooses, not just what a catalogue item costs.

    Drives `root_sibling_census.root_sibling_verdicts`, which runs the SAME
    `resolve_root` walk `decide_tree` uses on every live cycle
    (`ai/decisions/root.py`) and classifies every candidate it returns —
    `[resolution.root, *resolution.alternatives]`, read straight off the
    walk's own output, never rebuilt from the gate's inputs
    (`feedback_never_feed_a_walks_own_output_back_in`).

    ALL FOUR COUNTS PRINT, EVEN WHEN THE LOWER THREE ARE ZERO. A root-level
    count of 0 sibling-priced roots is a real and likely answer — the walk
    may simply never name an item behind a sibling-clearable gate — and
    T2.0 shipped a catalogue-level number that read as evidence while being
    a tautology; printing zero explicitly here is what keeps this section
    from repeating that shape.

    THE CHOSEN ROOT'S REPR ALWAYS PRINTS, WHETHER OR NOT IT NAMES AN ITEM.
    `ReachCharLevel`/`ReachSkillLevel` name no item at all, and a chosen
    root of that shape means the sibling route COULD NOT APPLY this cycle
    — a different finding from the route being priced and then outpriced by
    a cheaper existing route. The section says so explicitly so a reader
    cannot conflate "structurally unreachable" with "measured and rejected".
    """
    rows = root_sibling_verdicts(state, game_data, objective, ctx, store)
    named = [r for r in rows if r.item is not None]
    priced = [r for r in named if r.verdict is not None and r.verdict.priced]
    load_bearing = [r for r in named if r.verdict is not None and r.verdict.load_bearing]
    chosen: RootSiblingVerdict | None = next((r for r in rows if r.chosen), None)

    print(f"\n== root-sibling audit ({character}) ==")
    print("a CHOSEN root naming no item (ReachCharLevel, ReachSkillLevel) means "
          "the sibling route COULD NOT APPLY this cycle -- that is a different "
          "finding from the route being priced and then outpriced by a cheaper "
          "existing route.")
    print(f"{len(rows)} candidate root(s) (resolution.root + resolution.alternatives)")
    print(f"{len(named)} name an item")
    print(f"{len(priced)} sibling-priced")
    print(f"{len(load_bearing)} load-bearing")
    if chosen is None:
        print("chosen root: None (resolve_root returned no root this cycle -- the "
              "CanIClearMyTier wall case)")
        return
    print(f"chosen root: {chosen.root_repr}")
    if chosen.item is None:
        print("chosen root names no item -- the sibling route could not apply "
              "this cycle")
        return
    print(f"chosen root names item: {chosen.item}")
    chosen_priced = chosen.verdict is not None and chosen.verdict.priced
    chosen_load_bearing = chosen.verdict is not None and chosen.verdict.load_bearing
    print(f"chosen root sibling-priced: {chosen_priced}")
    print(f"chosen root load-bearing: {chosen_load_bearing}")


def _run_for_character(character: str) -> None:
    """Print the eligible / priced / load-bearing counts for the sibling-craft
    route, then the load-bearing rows grouped by gate (largest saving first),
    then the priced-but-not-load-bearing (outpriced) rows, then the T2.1
    root-level section for this one character."""
    state, game_data, player_ctx, objective = _sense(character)

    db_path = default_learn_db_path()
    coordination = CoordinationStore(db_path=db_path, character=character)
    sibling_skills = coordination.sibling_skill_levels(datetime.now(UTC))
    store = LearningStore(db_path, character=character)

    candidates = _eligible_candidates(state, game_data, sibling_skills)
    ctx = replace(player_ctx, sibling_skills=sibling_skills)
    verdicts = sibling_route_verdicts(state, game_data, ctx, store, candidates)

    priced = [v for v in verdicts if v.priced]
    load_bearing = [v for v in verdicts if v.load_bearing]
    outpriced = [v for v in priced if not v.load_bearing]
    gates = _group_by_gate(load_bearing)

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
    print(f"{len(load_bearing)} load-bearing ({len(gates)} gate(s))")
    print("priced can only diverge from eligible when fleet_supply_request_cycles "
          "is None or <= 0 (every route declines at once); priced == eligible is "
          "the expected case, not per-route confirmation.")
    print("these counts drift between runs too, not just the savings below: "
          "eligible/priced/load-bearing are read off THIS character's live "
          "skills, so a gate an earlier run reported as eligible drops out the "
          "moment the character's own level clears it.")
    if gates:
        print("\nload-bearing routes, grouped by gate (largest saving first):")
        print("savings are priced off a live-updating skill_grind_rate "
              "observation and will drift between runs -- a different number "
              "on a rerun is not a regression.")
        print("EACH LINE IS ONE GATE, NOT ONE ITEM: the grind unlock behind a "
              "gate is paid ONCE PER (skill, required_level), while the sibling "
              "unlock is paid once per item, so the saving below is NOT "
              "additive across the listed items -- do not multiply it by the "
              "item count.")
        for skill, required_level, members in gates:
            _print_gate_line(skill, required_level, members)
    if outpriced:
        print("\npriced but not load-bearing (an existing route already undercuts "
              "the sibling craft):")
        for v in sorted(outpriced, key=lambda v: v.item):
            _print_outpriced_row(v)

    _print_root_section(state, game_data, objective, ctx, store, character)


def sibling_route_audit_command(
    character: str | None = typer.Argument(
        None, help="Character to audit (omit and use --character instead for multiple)"),
    characters: list[str] = typer.Option(
        [], "--character", "-c",
        help="Character to audit; repeat for multiple, e.g. -c C3P0 -c R2D2. "
             "There is no --all: the only roster source in this codebase is "
             "GET /my/characters (`MultiRun.run`, `multi/multi_run.py:194`), a "
             "real API call this read-only command's own `_sense` seam is "
             "built specifically to keep out of reach -- so every character "
             "audited is named explicitly rather than discovered."),
) -> None:
    """Run the sibling-route audit -- eligible/priced/load-bearing catalogue
    counts (T2.0) and the T2.1 root-walk section -- for one or more
    characters, named either as the positional argument or via repeated
    `--character`/`-c`."""
    names = list(characters)
    if character is not None:
        names.append(character)
    if not names:
        print("name a character to audit: the positional argument, or one or "
              "more --character/-c options")
        raise typer.Exit(code=2)
    for name in names:
        _run_for_character(name)
