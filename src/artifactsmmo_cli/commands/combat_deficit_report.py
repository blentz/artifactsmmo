"""`artifactsmmo combat-deficit` — read-only: why a fight is lost, and what closes it.

The oracle for the `combat_deficit` work. Every later increment changes what the
bot DOES about a losing fight; this command is how "did that actually change live
behaviour" gets answered without restarting the fleet and reading traces — the
same role `objective` plays for the unified objective's ranking.

It answers, against LIVE character state, the question the bot could not answer
for C3P0 on 2026-08-20: `combat_margin` was -10 against a pig it had lost 42 times
out of 42, and four reachable upgrades closed it — while the bot spent ten hours
crafting toward boots it was already wearing.

Read-only: senses state, computes, prints. No actions, and the learning store is
in-memory so a diagnostic run cannot write session rows into the fleet's db.
"""

import typer

from artifactsmmo_cli.ai.acquisition_cost import acquisition_actions
from artifactsmmo_cli.ai.combat_deficit import CombatDeficit, combat_deficit
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config


def _print_deficit(monster: str, deficit: CombatDeficit | None, level: int) -> None:
    if deficit is None:
        print(f"{monster}: NO DEFICIT — predict_win says this fight is winnable now.")
        return
    verdict = "CLOSES" if deficit.closes else "DOES NOT CLOSE"
    print(f"{monster}: margin {deficit.baseline_margin} (losing) — chain {verdict}")
    if not deficit.chain:
        print("  nothing at or below character level "
              f"{level} improves the margin — this deficit needs a higher level, "
              "not more gear.")
        return
    for i, step in enumerate(deficit.chain, start=1):
        gate = (f"{step.crafting_skill}@{step.crafting_level}"
                if step.crafting_skill else "not craftable (drop/vendor)")
        cost = "?" if step.acquire_cost is None else f"{step.acquire_cost:.0f}"
        print(f"  {i}. {step.code:28s} L{step.item_level:<3} {step.item_type:12s} "
              f"{gate:24s} {cost:>9s} actions   margin -> {step.margin_after}")


def combat_deficit_command(
    character: str = typer.Argument(..., help="Character name"),
    monster: str | None = typer.Option(
        None, "--monster",
        help="Monster code (default: the character's active task monster)"),
    max_chain: int = typer.Option(8, "--max-chain", help="Bound on the greedy walk"),
) -> None:
    """Print why CHARACTER loses to MONSTER and which acquisitions close the gap."""
    config = Config.from_token_file()
    ClientManager().initialize(config)
    store = LearningStore(db_path=":memory:", character=character)
    store.start_session()
    try:
        player = GamePlayer(character=character, history=store,
                            game_data_ttl_minutes=config.game_data_ttl_minutes)
        player.plan_once()
        state, game_data, ctx = player.state, player.game_data, player._last_ctx
        if state is None or game_data is None:
            raise typer.BadParameter(f"could not sense state for {character!r}")
        target = monster or state.task_code
        if not target:
            raise typer.BadParameter(
                f"{character!r} holds no task monster; pass --monster explicitly")
        print(f"{character}: level={state.level} hp={state.hp}/{state.max_hp} "
              f"weapon={state.equipment.get('weapon_slot')}")
        print(f"task: {state.task_type}/{state.task_code} "
              f"{state.task_progress}/{state.task_total}")
        print("-" * 70)

        def actions_of(code: str, slot: str) -> int:
            """Actions to acquire ONE — the SAME function `J` prices routes with.

            This is what makes the chain answer clause (c) without a rule for it:
            a skill-gated craft carries `unlock_actions` (its grind, or the
            measured cost of asking a sibling), so preferring a low skill
            requirement and preferring a cheap acquisition are one ordering.
            """
            return acquisition_actions(code, 1, state, game_data, ctx,
                                       equip=slot is not None, store=store)

        _print_deficit(target, combat_deficit(state, game_data, target,
                                              max_chain=max_chain,
                                              actions_of=actions_of), state.level)
    finally:
        store.end_session(exit_reason="normal")
        store.close()
