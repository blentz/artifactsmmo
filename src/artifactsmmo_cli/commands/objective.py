"""Objective command: print the unified objective's ranking and WHICH KEY DECIDED IT.

`plan` already prints the progression TREE's ranking — `RootScore` rows carrying a
per-category `score`. It does not print the objective's own inputs, and those are
what settle the gear-vs-XP pivot: `acquire_cost`, `reachable_level`,
`cycles_to_fifty`, the precedence band, and `J` where `J` means anything.

Those numbers have never been visible outside a `play-trace-*.jsonl`, which is
deleted periodically and is not a durable record. That blind spot hid a live
degeneracy for months: measured over 10,716 trace cycles, NO candidate ever landed
in the finite band, so `objective_j` never ran and the ranking was settled every
single cycle by S-006's second key — acquisition cost — where the XP trunk sits at
zero by construction and wins unopposed. The plan pane was reporting it honestly
the whole time as `->L26` on every row; nobody read that string as the diagnosis it
is.

So this command prints the terms AND names the clause that decided, on its own
line. "J never ran" becomes a printed fact rather than an inference.

Read-only: senses state (or seeds a scenario offline), runs ONE ranking, executes
no action and changes no decision.
"""

import json
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

import typer

from artifactsmmo_cli.ai.acquisition_cost import (
    acquisition_actions,
    bundle_acquisition_actions,
)
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.tiers.branch_objective import branch_ranking, finite_j
from artifactsmmo_cli.ai.tiers.progression_choice import (
    TARGET_LEVEL,
    ProgressionCandidate,
    candidate_band,
)
from artifactsmmo_cli.ai.tiers.progression_tree import objective_candidates
from artifactsmmo_cli.ai.tiers.progression_tree_core import milestone_pure
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config
from artifactsmmo_cli.utils.mutation_lock import check_mutation_lock, default_lock_path

_DEFAULT_BUNDLE = (
    Path(__file__).resolve().parents[3] / "tests" / "test_ai" / "scenarios"
    / "fixtures" / "gamedata_bundle.json")

_FINITE_BAND = candidate_band(ProgressionCandidate(
    identity="", acquire_cost=0, reachable_level=TARGET_LEVEL,
    cycles_to_fifty=0, failed=False))
"""The finite band's value, DERIVED by classifying a candidate that is finite by
construction rather than by repeating `progression_choice`'s private band literal.
Mirrors `branch_objective._FINITE_BAND` for the same reason: a copied literal can
drift from the core silently, this one cannot."""


def _default_learn_db_path() -> str:
    return str(Path.home() / ".cache" / "artifactsmmo" / "learning.db")


def band_name(candidate: ProgressionCandidate, target: int = TARGET_LEVEL) -> str:
    """The precedence band as the spec names it (S-006, S-012, S-014).

    `n/a` under a swept `--target`. `progression_choice.candidate_band` classifies
    against its own `TARGET_LEVEL`, mirrored in `Formal.ProgressionChoice`, and
    this command does not parameterise the proved core — see
    `branch_objective._outcome`. Re-deriving the band here against the swept
    target would be a SECOND banding implementation, which is the trap this repo
    keeps falling into; reporting the shipped band under a target it was not
    computed for would be a lie. So the column abstains, and the raw terms plus
    the spread carry the measurement instead."""
    if target != TARGET_LEVEL:
        return "n/a"
    if candidate.failed:
        return "FAILED"
    if candidate_band(candidate) == _FINITE_BAND:
        return "FINITE"
    return "UNREACHABLE"


def decided_by(ranked: list[ProgressionCandidate],
               target: int = TARGET_LEVEL) -> str:
    """Which clause actually separated the winner from the field.

    THE POINT OF THIS COMMAND. The ranking is a lexicographic triple (band, then
    `J` in the finite band / furthest-progress in the unreachable one, then
    acquisition cost), and reading the winner alone cannot tell you which
    component did the work. A ranking settled by S-006's cost key is a ranking in
    which the objective did not participate — the trunk wins for costing nothing,
    not for being worth more — and that is invisible unless it is stated.

    Reports the tie width on the key that did NOT decide, so a near-tie and a
    total tie are distinguishable: 9/9 tied on furthest progress is the live
    degeneracy, 2/9 is an ordinary close call.
    """
    if not ranked:
        return "nothing to decide — no candidates"
    if target != TARGET_LEVEL:
        return (f"n/a — ranking order is the SHIPPED banding against L{TARGET_LEVEL}; "
                f"only the projection was swept to L{target}. Read `spread`.")
    winner = ranked[0]
    if winner.failed:
        return f"every candidate FAILED ({len(ranked)}/{len(ranked)}) — no projection ran"
    if band_name(winner) == "FINITE":
        return f"S-005 (J) — winner J={finite_j(winner)}"
    live = [c for c in ranked if not c.failed]
    top_reach = max(c.reachable_level for c in live)
    tied = [c for c in live if c.reachable_level == top_reach]
    if len(tied) == 1:
        return (f"S-006 key 1 (furthest progress) — winner reaches L{top_reach}, "
                f"alone")
    return (f"S-006 key 2 (acquisition cost) — key 1 tied at reach=L{top_reach} "
            f"for {len(tied)}/{len(live)}; J never ran")


def reached_spread(ranked: list[ProgressionCandidate], target: int) -> int | None:
    """`max(cycles) - min(cycles)` over candidates whose walk actually REACHED
    `target`, or None when fewer than two did.

    E2's recorded quantity, and the one C needs to be non-zero: it is how much the
    benefit term can discriminate at this horizon. Measured live 2026-08-18 —
    Lor L16 to milestone 20 spread 229 cycles, R2D2 L19 to milestone 20 spread 0
    — which is why the horizon has two degenerate ends and not one.

    Candidates whose walk stopped short are excluded, not counted as zero: their
    cycles figure is a filler (`_outcome` returns 0 on a blocked walk), and
    folding a filler into a spread would report a discrimination that does not
    exist."""
    reached = [c.cycles_to_fifty for c in ranked
               if not c.failed and c.reachable_level >= target]
    if len(reached) < 2:
        return None
    return max(reached) - min(reached)


def _rows(ranked: list[ProgressionCandidate],
          target: int = TARGET_LEVEL) -> list[dict[str, object]]:
    """One JSON-able row per candidate, in rank order."""
    return [
        {
            "rank": i,
            "identity": c.identity,
            "acquire_cost": c.acquire_cost,
            "reachable_level": c.reachable_level,
            "cycles_to_target": (c.cycles_to_fifty
                                 if c.reachable_level >= target and not c.failed
                                 else None),
            "j": finite_j(c) if target == TARGET_LEVEL else None,
            "band": band_name(c, target),
        }
        for i, c in enumerate(ranked)
    ]


def _print_report(header: dict[str, object],
                  ranked: list[ProgressionCandidate],
                  elapsed_ms: float, target: int) -> None:
    print("=" * 78)
    print(f"=== {header['subject']}  level={header['level']}  "
          f"milestone={header['milestone']}  target={header['target']}  "
          f"candidates={len(ranked)}")
    print(f"    store: {header['store']}")
    # LEGACY BANNER (wave 3a fix-round 1). `decide_tree` stopped consulting `J`
    # when the resolution walk replaced the ranking, so this command is the last
    # `branch_ranking` caller in the tree and its WINNER can disagree with the
    # root the bot actually pursues — measured 2026-08-23: Lor's decision was
    # `ReachSkillLevel(gearcrafting, 10)` while this printed
    # `artifact1_slot:lich_race_trophy`. A diagnostic that silently contradicts
    # production is worse than none, so it says so until wave 3b deletes `J`.
    print("    NOTE: LEGACY — this is the retired `J` ranking, NOT the "
          "decision. Since wave 3a the root is RESOLVED by ai/decisions/root.py;")
    print("          run `artifactsmmo plan <char>` for what the bot will "
          "actually do. Deleted with `J` in wave 3b.")
    print("-" * 78)
    print(f"{'identity':<44}{'cost':>10}{'reach':>7}{'cycles':>8}"
          f"{'J':>9}  band")
    for row in _rows(ranked, target):
        cycles = "-" if row["cycles_to_target"] is None else row["cycles_to_target"]
        j = "-" if row["j"] is None else row["j"]
        print(f"{row['identity']!s:<44}{row['acquire_cost']:>10}"
              f"{row['reachable_level']:>7}{cycles:>8}{j:>9}  {row['band']}")
    print("-" * 78)
    spread = reached_spread(ranked, target)
    print(f"SPREAD: {'n/a (<2 candidates reached the target)' if spread is None else spread}"
          f"  (max-min cycles among candidates that reached L{target})")
    print(f"DECIDED BY: {decided_by(ranked, target)}")
    print(f"WINNER: {ranked[0].identity if ranked else '<none>'}")
    walks = len(ranked)
    mean = elapsed_ms / walks if walks else 0.0
    print(f"timing: {walks} walks, {elapsed_ms:.0f}ms total, {mean:.1f}ms mean")
    print("=" * 78)


def _print_bundle(player: GamePlayer, store: LearningStore, codes: list[str]) -> None:
    """Price `codes` one at a time, then as one plan, and name the shared keys.

    THE MEASUREMENT THAT SEPARATES OPTION C FROM OPTION B. `J` prices every
    candidate independently today, so a prerequisite behind five gear pieces is
    charged five times and all five are rejected for a cost they would have
    shared. `acquisition_cost_core`'s `paid` ledger already charges a pay-once key
    once per PLAN; this asks what that is worth when the plan is the whole set.

    Read-only, and wired into no decision."""
    state, game_data = player.state, player.game_data
    assert state is not None and game_data is not None
    ctx = player._selection_context()
    singly: dict[str, int] = {}
    timings: dict[str, float] = {}
    with store.search_cache():
        for code in codes:
            start = time.perf_counter()
            singly[code] = acquisition_actions(code, 1, state, game_data, ctx,
                                               equip=True, store=store)
            timings[code] = (time.perf_counter() - start) * 1000.0
        roots = [(c, 1) for c in codes]
        total, paid = bundle_acquisition_actions(roots, state, game_data, ctx,
                                                 equip=True, store=store)
    print("-" * 78)
    print("BUNDLE PRICING (analysis only — no decision path calls this)")
    for code, cost in singly.items():
        print(f"  individually  {code:<28} {cost:>10}  {timings[code]:>8.1f}ms")
    total_singly = sum(singly.values())
    print(f"  {'sum of the parts':<42} {total_singly:>10}")
    print(f"  {'as ONE plan':<42} {total:>10}")
    saved = total_singly - total
    pct = (100.0 * saved / total_singly) if total_singly else 0.0
    print(f"  {'amortised':<42} {saved:>10}  ({pct:.0f}%)")
    shared = {k: v for k, v in sorted(paid.items()) if v > 0}
    print(f"  pay-once keys the one plan touched ({len(shared)}):")
    for key, price in shared.items():
        print(f"    {key:<40} {price:>10}")
    if not shared:
        print("    <none> — nothing was shared, so bundling buys nothing here")
    # E4's second term. Option C moves `acquisition_actions` from once per
    # CANDIDATE to once per candidate per RUNG, so whether it is cheaper than
    # today turns on this figure against the walk's ~per-rung cost. Printed here
    # because this is the only place the pricer is called in isolation.
    mean_ms = sum(timings.values()) / len(timings) if timings else 0.0
    print(f"  acquisition_actions: {len(timings)} calls, "
          f"{sum(timings.values()):.0f}ms total, {mean_ms:.1f}ms mean")


def _rank(player: GamePlayer, store: LearningStore,
          target: int) -> tuple[list[ProgressionCandidate], float]:
    """One `branch_ranking` over the production candidate set, timed.

    The search cache is opened here exactly as `GamePlayer._decide_band` opens it
    around the live decision — without it `branch_ranking` is ~14x slower and the
    timing this command prints would not be the timing the bot pays."""
    state, game_data = player.state, player.game_data
    assert state is not None and game_data is not None
    assert player._objective is not None
    ctx = player._selection_context()
    candidates = objective_candidates(state, game_data, player._objective)
    with store.search_cache():
        start = time.perf_counter()
        ranked = branch_ranking(state, game_data, candidates, store, ctx, target)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
    return ranked, elapsed_ms


def objective(
    character: str | None = typer.Argument(
        None, help="Character name to rank for (omit when using --scenario)"),
    scenario: str | None = typer.Option(
        None, "--scenario",
        help="Rank a named synthetic scenario offline (no API). "
             "Names: see artifactsmmo_cli.ai.scenario.SCENARIOS"),
    bundle: str | None = typer.Option(
        None, "--bundle", help="GameData cache-bundle JSON for --scenario "
                               "(default: the committed test fixture)"),
    learn: bool = typer.Option(
        False, "--learn",
        help="Use the persistent learning DB (match a --learn bot's ranking) "
             "instead of an ephemeral in-memory store"),
    learn_db: str | None = typer.Option(None, "--learn-db", help="Learning DB path"),
    target: int | None = typer.Option(
        None, "--target",
        help="Sweep the PROJECTION's target level (default: the shipped 50). "
             "Ranking order and the band column still come from the shipped "
             "banding — only the projection moves. Read SPREAD."),
    bundle_price: str | None = typer.Option(
        None, "--bundle-price",
        help="Comma-separated item codes: price them individually and then as "
             "ONE plan, and name the pay-once keys they share. Analysis only."),
    json_out: bool = typer.Option(
        False, "--json", help="Emit the ranking as JSON instead of a table"),
) -> None:
    """Print the unified objective's candidate ranking, and which key decided it."""
    lock = check_mutation_lock(default_lock_path())
    if lock.state == "active":
        print(f"mutation run in progress (pid {lock.pid}) — src/ has live mutants; retry later")
        raise typer.Exit(code=2)
    # Every Option-backed parameter is isinstance-guarded, matching `plan`'s
    # documented pattern: a direct (non-Click) call that omits one — as the tests
    # in tests/test_ai/test_objective_command.py do — leaves the raw
    # `typer.models.OptionInfo` sentinel in place rather than its declared
    # default, so trusting the default here raises deep inside LearningStore.
    scenario_name = scenario if isinstance(scenario, str) else None
    bundle_arg = bundle if isinstance(bundle, str) else None
    use_learn = learn if isinstance(learn, bool) else False
    learn_db_arg = learn_db if isinstance(learn_db, str) else None
    as_json = json_out if isinstance(json_out, bool) else False
    target_level = target if isinstance(target, int) else TARGET_LEVEL
    bundle_codes = ([c.strip() for c in bundle_price.split(",") if c.strip()]
                    if isinstance(bundle_price, str) else [])
    subject = scenario_name or (character if isinstance(character, str) else None)
    if subject is None:
        print("give a CHARACTER name or --scenario NAME")
        raise typer.Exit(code=2)
    if scenario_name is not None and scenario_name not in SCENARIOS:
        print(f"unknown scenario '{scenario_name}'; known: {', '.join(sorted(SCENARIOS))}")
        raise typer.Exit(code=2)

    # A store is REQUIRED, not optional: `branch_ranking` is the store-fed `J`
    # path, and `decide_tree` falls back to the legacy boolean pivot without one.
    # Ranking against no store would print a pivot this command does not claim to
    # show. An in-memory store is cold — `cheapest_path_to_level` then uses the
    # documented xp formula rather than measured rates — which is deterministic
    # and reproducible, and is why the store is named in the header.
    db_path = (learn_db_arg or _default_learn_db_path()) if use_learn else ":memory:"
    store = LearningStore(db_path=db_path, character=subject)
    store.start_session()
    try:
        # UNDER --json, STDOUT IS A PAYLOAD, NOT A LOG. Sensing prints progress
        # (`Loading game data...`, `Fetching character state...`, the blocker
        # seed count) on stdout, and `play` wants those visible — so they are not
        # moved. Here they are redirected to stderr for the duration of setup,
        # which keeps the promise `--json` makes to the spike's experiments that
        # pipe it, without changing what any other command prints.
        with redirect_stdout(sys.stderr if as_json else sys.stdout):
            if scenario_name is not None:
                game_data = load_bundle_game_data(
                    Path(bundle_arg) if bundle_arg is not None else _DEFAULT_BUNDLE)
                player = GamePlayer(character=scenario_name, history=store)
                player.seed_offline(
                    scenario_state(SCENARIOS[scenario_name], game_data), game_data)
            else:
                config = Config.from_token_file()
                player = GamePlayer(character=subject, history=store,
                                    game_data_ttl_minutes=config.game_data_ttl_minutes)
                player._initialize(ClientManager().client)
            ranked, elapsed_ms = _rank(player, store, target_level)
        state = player.state
        assert state is not None
        header: dict[str, object] = {
            "subject": subject,
            "level": state.level,
            "milestone": milestone_pure(state.level),
            "target": target_level,
            "store": ("persistent " + db_path if use_learn
                      else "ephemeral :memory: (cold — a skill-gated craft "
                           "cannot be priced without an observed grind rate, "
                           "so a cost of 1000001 here may be the COLD STORE "
                           "and not a real wall; re-run with --learn)"),
        }
        if as_json:
            print(json.dumps({
                **header,
                "decided_by": decided_by(ranked, target_level),
                "spread": reached_spread(ranked, target_level),
                "winner": ranked[0].identity if ranked else None,
                "elapsed_ms": round(elapsed_ms, 1),
                "candidates": _rows(ranked, target_level),
            }, indent=2))
        else:
            _print_report(header, ranked, elapsed_ms, target_level)
            if bundle_codes:
                _print_bundle(player, store, bundle_codes)
    finally:
        store.end_session(exit_reason="normal")
        store.close()
