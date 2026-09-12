"""Live probe: the gear-target ranking for one character, untruncated.

`plan <char>` prints only the top of the resolution, which is exactly the end
of the list a demotion moves things to. This prints the whole ranking through
the REAL `WhichSlotIsFurthestBehind` key, plus the per-cycle cost of
`dead_target_slots`, so a "demoted, not dropped" claim is checkable.

Throwaway diagnostic — not imported by production, not covered by the gate.
"""

import sys
import time

from artifactsmmo_cli.ai.decisions.root import (
    _slot_order,
    dead_target_slots,
    resolve_root,
)
from artifactsmmo_cli.ai.drop_evidence import drop_evidence
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config


def main(character: str) -> int:
    config = Config.from_token_file()
    manager = ClientManager()
    manager.initialize(config)
    player = GamePlayer(character=character, history=None)
    client = manager.client
    player._initialize(client)
    state = player.state
    game_data = player.game_data
    assert state is not None and game_data is not None
    objective = CharacterObjective.from_game_data(game_data)

    targets = objective.gear_targets_with_blockers(state, None)
    start = time.perf_counter()
    dead = dead_target_slots(targets, state, game_data)
    dead_ms = (time.perf_counter() - start) * 1000

    start = time.perf_counter()
    ranked = sorted(targets.items(),
                    key=lambda item: _slot_order(item, state, game_data, dead))
    sort_ms = (time.perf_counter() - start) * 1000

    before = sorted(targets.items(),
                    key=lambda item: _slot_order(item, state, game_data, frozenset()))
    print("BEFORE (leading `dead` term forced to 0 for every slot):")
    for index, (slot, target) in enumerate(before):
        print(f"  {index:>2}  {slot:<14} {target.code}")
    print()

    print(f"{character}: level {state.level}, {len(targets)} blocked gear targets")
    print(f"dead_target_slots: {dead_ms:.1f} ms once per cycle; "
          f"sort over the cached set: {sort_ms:.3f} ms")
    print(f"dead slots: {sorted(dead) or '-'}")
    print()
    print(f"{'#':>2}  {'slot':<14} {'target':<22} {'key':<22} blocker evidence")
    for index, (slot, target) in enumerate(ranked):
        key = _slot_order((slot, target), state, game_data, dead)
        if target.blocker is not None and target.blocker != target.code:
            evidence = drop_evidence(target.blocker, state, game_data)
            note = (f"{target.blocker} live={evidence.on_live_tiles} "
                    f"closes={evidence.closes}")
        else:
            note = f"blocker={target.blocker} skill={target.blocking_skill}"
        mark = "DEAD" if slot in dead else "    "
        print(f"{index:>2}  {slot:<14} {target.code:<22} {key!s:<22} {mark} {note}")

    print()
    warm = []
    for _ in range(5):
        start = time.perf_counter()
        dead_target_slots(targets, state, game_data)
        warm.append((time.perf_counter() - start) * 1000)
    print("dead_target_slots warm x5: "
          + ", ".join(f"{ms:.1f}" for ms in warm) + " ms")

    timings = []
    for _ in range(5):
        start = time.perf_counter()
        resolution = resolve_root(state, game_data, objective, NO_PROFILE_CONTEXT, None)
        timings.append((time.perf_counter() - start) * 1000)
    print("resolve_root x5: " + ", ".join(f"{ms:.1f}" for ms in timings) + " ms")
    print(f"trail={resolution.trail}")
    print(f"root: {resolution.root!r}")
    for index, alternative in enumerate(resolution.alternatives):
        print(f"  alt[{index}] {alternative!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "HAL"))
