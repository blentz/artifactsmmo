"""Increment 0 of `docs/PLAN_band_unification.md`: does the band ladder actually
suppress anything?

S-016 says a means and the objective step compete on cycles, and neither wins by
its band. The arbiter instead walks a strict band order and returns the first
plannable candidate, with discretionary last. An objective step was present in
14,064 of 14,064 traced cycles, so the claim is that discretionary means are
structurally unreachable.

That claim has two halves and only one of them has been measured. "A step is always
present" is measured. "A discretionary means WANTED to fire" is not — the arbiter
stops walking before it gets there, and `cycles` in the learning DB has no column
for it. This script measures the second half.

READ-ONLY. It drives the real decision path (`plan_from_state`) and reads the
snapshot the driver already takes for the trace (`StrategyArbiter.last_fires`), so
there is no second producer of the fired-kinds list.

If nothing fires, the band is moot and the epic dies here.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from artifactsmmo_cli.ai.acquisition_cost import acquisition_actions
from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import (
    SCENARIOS,
    load_bundle_game_data,
    scenario_state,
)
from artifactsmmo_cli.ai.tiers import means
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.api_wrapper import APIWrapper
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


def _fires_for(player: GamePlayer) -> dict[str, object]:
    player.plan_from_state()
    return dict(player._arbiter.last_fires)


def _observed(player: GamePlayer) -> tuple[object, dict[str, int],
                                           object | None]:
    """Run one real cycle and observe what it computed: the plan report, the
    licensed recyclable surplus, and the BOUND SelectionContext.

    The surplus map and the ctx are read by WRAPPING the production function the
    driver calls, not by recomputing them. `ctx.step_profile` is bound inside the
    driver and nothing exposes it afterwards, so observing the call is the only
    way to get the same ctx the decision used — recomputing it here would be a
    second producer of exactly the value under measurement."""
    seen: dict[str, object] = {}
    real = means.recyclable_surplus

    def recorder(state, game_data, ctx):  # type: ignore[no-untyped-def]
        out = real(state, game_data, ctx)
        seen["surplus"] = out
        seen["ctx"] = ctx
        return out

    means.recyclable_surplus = recorder  # type: ignore[assignment]
    try:
        report = player.plan_from_state()
    finally:
        means.recyclable_surplus = real  # type: ignore[assignment]
    surplus = dict(seen.get("surplus") or {})  # type: ignore[arg-type]
    return report, surplus, seen.get("ctx")


def _learn_db() -> str:
    return str(Path.home() / ".cache" / "artifactsmmo" / "learning.db")


def _recycle_worth(surplus: dict[str, int], player: GamePlayer,
                   ctx: object) -> tuple[int, int]:
    """`(cycles saved, cycles spent)` for recycling every licensed surplus copy.

    SAVED is what the materials would otherwise cost to obtain, priced by the one
    acquisition model. A recycle returns `max(1, n // 2)` of each recipe input
    (`obtain_sources._recycle_sources`), so that is what is credited. SPENT is
    one hop to the workshop plus one action per copy."""
    state, game_data = player.state, player.game_data
    assert state is not None and game_data is not None
    saved = 0
    copies_total = 0
    for code, copies in surplus.items():
        recipe = game_data.crafting_recipe(code) or {}
        copies_total += copies
        for mat, n in recipe.items():
            got = max(1, n // 2) * copies
            unit = acquisition_actions(mat, got, state, game_data, ctx,  # type: ignore[arg-type]
                                       equip=False, store=player.history)
            if unit < UNOBTAINABLE_PER_UNIT:
                saved += unit
    return saved, (1 + copies_total if copies_total else 0)


def _step_cost(report: object, player: GamePlayer, ctx: object) -> int | None:
    """What the objective step it chose costs, in the same units."""
    root = getattr(getattr(report, "decision", None), "chosen_root", None)
    code = getattr(root, "code", None)
    if code is None:
        return None      # ReachCharLevel — not an acquisition, not comparable
    state, game_data = player.state, player.game_data
    assert state is not None and game_data is not None
    # WITHOUT the store a skill-gated craft prices at UNOBTAINABLE — the grind
    # rate is the only thing that can price the gate, and only the store has one.
    # Measured: every live step read 1,000,001 until this was passed.
    return acquisition_actions(code, getattr(root, "quantity", 1), state,
                               game_data, ctx, equip=True,  # type: ignore[arg-type]
                               store=player.history)


def scenario_rows() -> list[tuple[str, dict[str, object]]]:
    game_data = load_bundle_game_data(BUNDLE)
    rows = []
    for name in sorted(SCENARIOS):
        player = GamePlayer(character=name, history=None)
        player.seed_offline(scenario_state(SCENARIOS[name], game_data), game_data)
        rows.append((name, _fires_for(player)))
    return rows


def live_rows() -> list[tuple[str, dict[str, object]]]:
    ClientManager().initialize(Config.from_token_file(None))
    client = ClientManager().client
    game_data = GameData.load(client)
    api = APIWrapper(client)
    rows = []
    for schema in api.get_my_characters().data:
        player = GamePlayer(character=schema.name, history=None)
        state = WorldState.from_character_schema(schema)
        player.seed_offline(state, game_data)
        rows.append((schema.name, _fires_for(player)))
    return rows


def report(rows: list[tuple[str, dict[str, object]]], label: str) -> Counter[str]:
    fired: Counter[str] = Counter()
    suppressed = 0
    print(f"\n=== {label}: {len(rows)} states ===")
    for name, f in rows:
        disc = list(f.get("discretionary") or [])
        # S-023: WAIT is the totality witness — it fires unconditionally and is
        # exempt from comparison, so counting it as a suppressed option would
        # report 100% suppression on any sample whatsoever.
        priced = [k for k in disc if k != "wait"]
        step = bool(f.get("step_present"))
        fired.update(priced)
        if priced and step:
            suppressed += 1
        print(f"  {name:<34} step={'Y' if step else 'n'}  "
              f"guards={len(f.get('guards') or [])}  "
              f"collect={','.join(f.get('collect') or []) or '-'}  "
              f"discretionary={','.join(priced) or '-'}"f"{'  +wait' if 'wait' in disc else ''}")
    print(f"\n  states where a PRICEABLE discretionary means fired AND a step "
          f"was present: "
          f"{suppressed}/{len(rows)}")
    if fired:
        print("  fired kinds (each one lost to the step by POSITION, not by price):")
        for kind, n in fired.most_common():
            print(f"    {kind:<26} {n}")
    else:
        print("  NOTHING fired. The band is moot on this sample.")
    return fired


def _scenario_players() -> list[tuple[str, GamePlayer]]:
    game_data = load_bundle_game_data(BUNDLE)
    out = []
    for name in sorted(SCENARIOS):
        player = GamePlayer(character=name, history=None)
        player.seed_offline(scenario_state(SCENARIOS[name], game_data), game_data)
        out.append((name, player))
    return out


def _live_players() -> list[tuple[str, GamePlayer]]:
    ClientManager().initialize(Config.from_token_file(None))
    client = ClientManager().client
    game_data = GameData.load(client)
    out = []
    for schema in APIWrapper(client).get_my_characters().data:
        store = LearningStore(db_path=_learn_db(), character=schema.name)
        player = GamePlayer(character=schema.name, history=store)
        player.seed_offline(WorldState.from_character_schema(schema), game_data)
        out.append((schema.name, player))
    return out


def _price(players: list[tuple[str, GamePlayer]], label: str) -> None:
    """Put the two sides of S-016 next to each other — and REFUSE a verdict.

    An earlier version of this function declared a winner by testing
    `recycle_net > step_cost`. That is a units error of exactly the kind this
    epic exists to remove: `recycle_net` is a BENEFIT (cycles the materials would
    otherwise cost) and `step_cost` is a COST (cycles to acquire the step). They
    are not on one scale, and comparing them produced a confident "0
    disagreements" from an arithmetic that meant nothing.

    Rendering the verdict needs the step's BENEFIT — its contribution to cycles
    to the horizon — which is precisely what no part of the system computes
    per-step today. That inability is the finding, so this prints the halves and
    stops."""
    print(f"--- {label} ---")
    priced_step = walled = no_scale = 0
    for name, player in players:
        plan_report, surplus, ctx = _observed(player)
        if ctx is None:
            print(f"  {name:<34} ctx never bound")
            continue
        saved, spent = _recycle_worth(surplus, player, ctx)
        step = _step_cost(plan_report, player, ctx)
        net = saved - spent
        if step is None:
            no_scale += 1
            note = "step is ReachCharLevel — not on the acquisition scale at all"
        elif step >= UNOBTAINABLE_PER_UNIT:
            walled += 1
            note = "step is UNPRICEABLE to the acquisition model"
        else:
            priced_step += 1
            note = ""
        print(f"  {name:<34} surplus={sum(surplus.values()):<3} "
              f"recycle_benefit={net:<7} step_cost="
              f"{step if step is not None else '-':<9} {note}")
    total = len(players)
    print(f"  step priced: {priced_step}/{total}   "
          f"step unpriceable: {walled}/{total}   "
          f"step off-scale: {no_scale}/{total}")
    print("  NO VERDICT: a benefit and a cost are not comparable. The step's "
          "benefit\n  is what S-016 needs and what nothing computes.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true", help="also drive live characters")
    ap.add_argument("--price", action="store_true",
                    help="stage 2: price the step against recycle_surplus")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rows = scenario_rows()
    out = {"scenarios": {n: f for n, f in rows}}
    fired = report(rows, "scenarios")
    if args.live:
        lrows = live_rows()
        out["live"] = {n: f for n, f in lrows}
        fired += report(lrows, "live characters")
    if args.price:
        print("\n=== stage 2: priced ===")
        print("  RECYCLE_SURPLUS is the one fired means priceable with today's "
              "model.\n  SELL_IDLE needs S-046, MAINTAIN_CONSUMABLES needs a "
              "survivability value,\n  ACCEPT_TASK needs S-018's reward term "
              "and the reward table is empty.\n")
        _price(_scenario_players(), "scenarios")
        if args.live:
            _price(_live_players(), "live characters")
    if args.json:
        print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
