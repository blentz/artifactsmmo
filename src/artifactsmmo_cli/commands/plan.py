"""Plan command: print what the AI player WOULD do this cycle, without executing.

Offline plan inspection so mismatches (e.g. "committed to feather_coat but grinding
slimes") can be diagnosed without restarting the bot and reading traces. Senses live
state, runs ONE decide+select cycle, prints the chosen objective, the selected goal,
the planned action sequence, and the per-goal planner attempts (which surface
explosions: plan_len 0 after thousands of nodes)."""

from pathlib import Path

import typer

from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.plan_report import PlanReport
from artifactsmmo_cli.config import Config
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.utils.mutation_lock import check_mutation_lock, default_lock_path


def _default_learn_db_path() -> str:
    return str(Path.home() / ".cache" / "artifactsmmo" / "learning.db")


def _print_report(player: GamePlayer, report: PlanReport) -> None:
    s = player.state
    d = report.decision
    print("=" * 70)
    if report.simulated_doomed or report.simulated_committed is not None:
        print("SIMULATED in-memory arbiter state (diagnostic injection):")
        if report.simulated_doomed:
            print(f"  doomed-memo: {list(report.simulated_doomed)}")
        if report.simulated_committed is not None:
            print(f"  committed (sticky): {report.simulated_committed}")
        print("-" * 70)
    if s is not None:
        print(f"state: level={s.level} xp={s.xp}/{s.max_xp} hp={s.hp}/{s.max_hp} "
              f"pos=({s.x},{s.y}) inv={s.inventory_used}/{s.inventory_max} gold={s.gold}")
    print(f"chosen_root: {d.chosen_root!r}")
    print(f"chosen_step: {d.chosen_step!r}")
    print(f"selected_goal: {report.selected_goal!r}")
    print("-" * 70)
    print(f"PLAN ({len(report.plan)} actions):")
    if report.plan:
        for i, a in enumerate(report.plan):
            print(f"  {i + 1:2d}. {a!r}")
    else:
        print("  <no plan> — the selected goal produced no action sequence")
    print("-" * 70)
    print("goals_tried (planner attempts — watch for plan_len=0 after many nodes):")
    for g in report.goals_tried:
        flag = "  <-- NO PLAN" if g.get("plan_len") == 0 else ""
        timed = " TIMED_OUT" if g.get("timed_out") else ""
        # NODE_CAP = the memory bound truncated the search (a subset of
        # timed_out); distinguish it so a too-tight cap is diagnosable live.
        timed += " NODE_CAP" if g.get("node_capped") else ""
        print(f"  {g.get('goal')}: nodes={g.get('nodes')} depth={g.get('depth')} "
              f"plan_len={g.get('plan_len')}{timed}{flag}")
    if report.drop_inputs:
        print("-" * 70)
        print("monster-drop recipe inputs (winnable with the LIVE loadout?):")
        for di in report.drop_inputs:
            win = di.get("winnable") or []
            verdict = f"WINNABLE via {win}" if win else "NOT WINNABLE — gear unbuildable!"
            print(f"  {di.get('item')}: droppers={di.get('droppers')} -> {verdict}")
    print("-" * 70)
    print("root ranking (top 8):")
    for rs in d.ranking[:8]:
        print(f"  {rs.score} {rs.category:11s} {rs.root_repr}  ->  step={rs.step_repr}")
    print("=" * 70)


def plan(
    character: str = typer.Argument(..., help="Character name to plan for"),
    learn: bool = typer.Option(False, "--learn",
                                help="Use the learning DB (match a --learn bot's plan) instead of ephemeral"),
    learn_db: str | None = typer.Option(None, "--learn-db", help="Learning DB path"),
    refresh_game_data: bool = typer.Option(
        False, "--refresh-game-data", help="Re-fetch static game data from the API"),
    doom: list[str] = typer.Option(
        [], "--doom", help="Seed the arbiter's doomed-memo with this goal repr "
        "(repeatable) to reproduce a live in-memory suppression offline, "
        "e.g. --doom 'GrindCharacterXP(green_slime)'"),
    committed: str | None = typer.Option(
        None, "--committed", help="Seed the arbiter's sticky commitment with this "
        "goal repr to reproduce a live committed-goal hold"),
) -> None:
    """Print the plan the bot WOULD execute this cycle for CHARACTER, without acting."""
    lock = check_mutation_lock(default_lock_path())
    if lock.state == "active":
        print(f"mutation run in progress (pid {lock.pid}) — src/ has live mutants; retry later")
        raise typer.Exit(code=2)
    config = Config.from_token_file()
    if learn:
        store = LearningStore(db_path=learn_db or _default_learn_db_path(), character=character)
    else:
        store = LearningStore(db_path=":memory:", character=character)
    store.start_session()
    try:
        player = GamePlayer(
            character=character, history=store,
            game_data_ttl_minutes=config.game_data_ttl_minutes,
            refresh_game_data=refresh_game_data,
        )
        report = player.plan_once(doomed=doom, committed=committed)
        _print_report(player, report)
    finally:
        store.end_session(exit_reason="normal")
        store.close()
