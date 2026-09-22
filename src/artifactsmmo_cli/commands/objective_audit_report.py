"""`artifactsmmo objective-audit` — read-only: what the walk chose, what it paid,
and what it cannot reach.

The oracle for T1. The season-9 capstone moves from "level 50" to the character
leaderboard's `total_xp`, and this command is how the shape of that change gets
decided against measurement rather than a guess — the same role `combat-deficit`
plays for the combat-deficit work.

Four sections: the root-group census (what the walk chose), the currency-rate
census (what each goal paid, over slices that already carry the recovery its
fighting forced), the Pareto frontier over those bundles, and the gated-source
census (which XP sources are walled behind which skill level).

ONE WINDOW, PRINTED. `--window` used to mean three different things in one
report. The root-group section read `recent_cycles(window)` = the last N raw
rows; the rate section read `recent_selected_goals(window)`, which skips
NULL-goal rows and so reaches further back; and `recent_goal_cycles(g, window)`
widens its own read to `window * _RECOVERY_STREAM_FACTOR` (10) raw rows and caps
only the OWNED result. Measured at `--window 5000` on C3P0's 45,036 rows, the
header covered ids 196146..220897 (09-17 -> 09-22) while
`GrindCharacterXP(skeleton)` covered 172327..198287 (09-12 -> 09-17) — a window
that ENDS where the header's begins — and `DepositInventory` spanned the whole
lifetime. The slices summed to 15,629 cycles under a heading that said 5,000, so
the Pareto frontier compared bundles measured in different eras.

Now ONE read of `recent_cycles(window)` defines the era: its id floor bounds
every goal slice, and the goal set is taken from those same rows rather than
from a query with a different reach. Each section then PRINTS the window it
actually used — row count, id span, timestamp span — because a report whose
sections can disagree about the era must not be able to do so silently.

Read-only: senses state, computes, prints. No actions, and the sensing store is
in-memory so a diagnostic run cannot write session rows into the fleet's db —
same discipline as `commands/combat_deficit_report.py`.
"""

import typer

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.audit.currency_rate_census import currency_rates
from artifactsmmo_cli.audit.pareto_frontier import frontier
from artifactsmmo_cli.audit.root_group_census import root_group_counts
from artifactsmmo_cli.audit.xp_gate_census import gated_xp_sources
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config
from artifactsmmo_cli.learning_db_path import default_learn_db_path


def _sense(character: str) -> tuple[WorldState, GameData]:
    """Live state and catalogue for CHARACTER, sensed exactly as `combat-deficit`
    does it: a fresh, in-memory `LearningStore` so this read-only command cannot
    write session rows into the fleet's own database, and `GamePlayer.plan_once()`
    to populate `state`/`game_data` before either is read.
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


def _span(cycles: list[Cycle]) -> str:
    """The window a section actually covered: its id range and its time range.

    Printed on every section so two sections cannot quietly report different
    eras under one `--window`. Ids come back from SQLite already assigned, so an
    id-less row here is a broken read and the `IndexError` it raises is the
    correct outcome — silently spanning a subset would be the defect this line
    exists to expose.
    """
    if not cycles:
        return "no rows"
    ids = sorted(c.id for c in cycles if c.id is not None)
    return (f"ids {ids[0]}..{ids[-1]} · "
            f"{min(c.ts for c in cycles)} -> {max(c.ts for c in cycles)}")


def objective_audit_command(
    character: str = typer.Argument(..., help="Character to audit"),
    window: int = typer.Option(5000, help="Cycles of history to read"),
) -> None:
    """Print the T1 objective audit for one character."""
    store = LearningStore(default_learn_db_path(), character=character)

    # THE ONE READ THAT DEFINES THE ERA. Every other section is bounded to the
    # ids this one returned — see the module docstring for the three-window
    # divergence that made a Pareto frontier compare different months.
    cycles = store.recent_cycles(window)
    print(f"== root groups ({character}, {len(cycles)} cycles, {_span(cycles)}) ==")
    for counts in root_group_counts(cycles):
        if counts.attributed == 0:
            print(f"{counts.character}: 0 attributed, {counts.unattributed} pre-migration")
            continue
        parts = []
        for group in sorted(counts.counts):
            share = counts.share(group)
            share_text = f"{share:.1%}" if share is not None else "n/a"
            parts.append(f"{group}={counts.counts[group]} ({share_text})")
        shares = " ".join(parts)
        print(f"{counts.character}: {shares} · {counts.unattributed} pre-migration")

    # The goal set comes from the SAME rows, not from `recent_selected_goals`,
    # which filters NULL `selected_goal` out of its own `window` and therefore
    # reaches further back than the header. `floor_id` then clips each attributed
    # slice to this era — `recent_goal_cycles` reads 10x `window` raw rows by
    # design (it needs each recovery cycle's predecessor) and caps only the owned
    # result, so unclipped it can return a slice that predates the header
    # entirely. Attribution still runs over the wide stream; only the REPORTED
    # rows are bounded.
    floor_id = min((c.id for c in cycles if c.id is not None), default=0)
    goals = {c.selected_goal for c in cycles if c.selected_goal is not None}
    slices = {g: [c for c in store.recent_goal_cycles(g, window)
                  if c.id is not None and c.id >= floor_id]
              for g in goals}
    rates = currency_rates(slices)
    # DEDUPLICATED BY ID. A recovery cycle appears in TWO slices — its owner's,
    # because `recent_goal_cycles` attributes it there, and `RestoreHP`'s own,
    # because recovery owns its rows as well. Summing the slices therefore
    # reported more rows than the window holds (5,714 over a 5,000-row window on
    # C3P0's first run under this header), which is the inflated-total shape this
    # section exists to make impossible.
    in_scope = list({c.id: c for s in slices.values() for c in s}.values())
    print(f"\n== currency rates ({len(in_scope)} attributed rows, {_span(in_scope)}) ==")
    print("RestoreHP is excluded: forced recovery is not a choosable bundle, and "
          "its rows are already inside every grind that forced them.")
    for row in rates:
        print(f"{row.goal:<45} {row.cycles:>6} cyc "
              f"{row.char_xp_per_second:>8.4f} char-xp/s "
              f"{row.skill_xp_per_second:>8.4f} skill-xp/s "
              f"{row.gold_per_second:>8.2f} gold/s")

    print("\n== pareto frontier ==")
    # `cyc` is printed here too, deliberately: the frontier does NOT weight by
    # sample size, so a 3-cycle bundle sits beside a 5,000-cycle one with nothing
    # else to tell them apart. Gold is NOT net of inputs either — a settlement
    # row (`DiscardOverstock` leading at 6.615 gold/s is every one of them a
    # `GeFill(...)`) credits the whole sale to the goal that happened to settle
    # it, while the gathering that produced the stock was paid for under another.
    print("n is unweighted; gold is gross, not net of the inputs another goal paid for.")
    for row in frontier(rates):
        print(f"{row.goal:<45} {row.cycles:>6} cyc "
              f"{row.char_xp_per_second:>8.4f} char-xp/s "
              f"{row.skill_xp_per_second:>8.4f} skill-xp/s "
              f"{row.gold_per_second:>8.2f} gold/s")

    # Live state: same construction sequence as commands/combat_deficit_report.py.
    # Ordered by the MONSTER's binding gap, not by any one step's — every step in
    # a closing chain is required, so the deepest gate is the fight's real price.
    state, game_data = _sense(character)
    print("\n== gated xp sources (nearest binding gate first) ==")
    for source in gated_xp_sources(state, game_data)[:20]:
        binding = source.binding
        print(f"{source.monster:<20} lvl {source.monster_level:>2} · "
              f"gap {source.gap:>2} binds on {binding.blocking_item} "
              f"({binding.item_type}) · {binding.skill} "
              f"{binding.held_level}->{binding.required_level}")
        # The rest of the chain, printed UNDER the monster it belongs to rather
        # than as peers competing for a slot in the top 20. A shallower step is
        # not a cheaper fight; it is part of the same bill.
        for step in [s for s in source.steps if s is not binding]:
            print(f"{'':<20}   also needs {step.blocking_item} ({step.item_type}) · "
                  f"{step.skill} {step.held_level}->{step.required_level} "
                  f"(gap {step.gap})")
