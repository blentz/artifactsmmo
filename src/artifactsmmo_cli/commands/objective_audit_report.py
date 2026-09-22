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

Read-only: senses state, computes, prints. No actions, and the sensing store is
in-memory so a diagnostic run cannot write session rows into the fleet's db —
same discipline as `commands/combat_deficit_report.py`.
"""

import typer

from artifactsmmo_cli.ai.game_data import GameData
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


def objective_audit_command(
    character: str = typer.Argument(..., help="Character to audit"),
    window: int = typer.Option(5000, help="Cycles of history to read"),
) -> None:
    """Print the T1 objective audit for one character."""
    store = LearningStore(default_learn_db_path(), character=character)

    cycles = store.recent_cycles(window)
    print(f"== root groups ({character}, {len(cycles)} cycles) ==")
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

    goals = set(store.recent_selected_goals(window))
    rates = currency_rates({g: store.recent_goal_cycles(g, window) for g in goals})
    print("\n== currency rates ==")
    for row in rates:
        print(f"{row.goal:<45} {row.cycles:>6} cyc "
              f"{row.char_xp_per_second:>8.4f} char-xp/s "
              f"{row.skill_xp_per_second:>8.4f} skill-xp/s "
              f"{row.gold_per_second:>8.2f} gold/s")

    print("\n== pareto frontier ==")
    for row in frontier(rates):
        print(f"{row.goal:<45} {row.char_xp_per_second:>8.4f} char-xp/s "
              f"{row.skill_xp_per_second:>8.4f} skill-xp/s "
              f"{row.gold_per_second:>8.2f} gold/s")

    # Live state: same construction sequence as commands/combat_deficit_report.py.
    state, game_data = _sense(character)
    print("\n== gated xp sources (nearest gate first) ==")
    for source in gated_xp_sources(state, game_data)[:20]:
        print(f"{source.monster:<20} lvl {source.monster_level:>2} "
              f"blocked by {source.blocking_item} ({source.item_type}) · "
              f"{source.skill} {source.held_level}->{source.required_level} "
              f"(gap {source.gap})")
