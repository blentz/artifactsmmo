"""The cycle's gear objective onto its `SelectionContext` (spec 2026-10-18 §2.4,
§6.2): ONE function for every driver of the root walk.

The player calls `attach_gear_objective` once per cycle in
`GamePlayer._selection_context`; the offline drivers of the same walk (the
scenario harness through the player, the currency- and drop-wall censuses)
call the same function, so a census sees the objective the live cycle would
and no second producer of it exists.

Ruling W (Task 5): the step was the player's own code, moved here whole.
"""

from collections import Counter
from contextlib import nullcontext
from dataclasses import replace

from artifactsmmo_cli.ai.combat import secure_win, unpotioned
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_objective import gear_objective
from artifactsmmo_cli.ai.gear_objective_result import GearObjective
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.loadout_profiles import active_profile_gear
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.winnable_cascade import CascadeInputs, winnable_farm_target_pure
from artifactsmmo_cli.ai.world_state import WorldState


def farm_target(task_monster: str | None, objective: GearObjective | None) -> str | None:
    """The cycle's grind target (spec 2026-10-18 §2.4, §6.2): the held
    monsters task's monster first, as always; otherwise `m*` of the cycle's
    gear objective while `L*` is held, and None while a piece of it is
    missing, so no fight is chosen for XP then (acquisition fights still pay
    theirs). The proved cascade (`winnable_farm_target_pure`) keeps the
    precedence: `m*` is its path tier, winnable exactly when held, and nothing
    is picked below it."""
    return winnable_farm_target_pure(CascadeInputs(
        task_monster=task_monster,
        path_monster=objective.monster if objective is not None else None,
        path_winnable=objective is not None and objective.held,
        pick_winnable=None,
    ))


def gear_keep_for(state: WorldState, game_data: GameData, history: LearningStore | None,
                  combat_monster: str | None,
                  near_term_targets: frozenset[str]) -> dict[str, int]:
    """The active-profile gear-demand KEEP map {code: keep_count} threaded to
    the keep economy (spec 2026-06-28-gear-loadout-profiles): the deduped
    per-code demand across the active loadout profiles UNION the in-flight
    upgrade codes (near_term gear + tools currently being pursued, kept at 1
    spare). Empty when no profiles are recorded and no in-flight upgrade — the
    consumers then fall back to the legacy blanket equippable keep.

    `gather_skills` is passed empty (mirrors the BANK_EXPAND wiring): the
    recent-window inside `active_profile_gear` still contributes gather task
    profiles via the learning history."""
    keep: dict[str, int] = {}
    if history is not None:
        keep = dict(active_profile_gear(state, game_data, history,
                                        combat_monster, frozenset()))
    for code in near_term_targets:
        keep.setdefault(code, 1)
    return keep


def gear_objective_line(objective: GearObjective | None) -> str:
    """The per-cycle log line naming the target monster `m*` and the first
    missing `L*` piece (final review F8): nothing measures cycle-to-cycle
    flips of either, and a flipped root breaks a commitment at once, so the
    live witness logs both every time the cycle decides."""
    if objective is None:
        return "Gear objective: none (no loadout pays XP)"
    if objective.held:
        return f"Gear objective: target {objective.monster}; L* held"
    first = objective.missing[0]
    return (f"Gear objective: target {objective.monster}; first missing "
            f"{first.code} ({first.slot}); {len(objective.missing)} missing")


def with_objective_keep(keep: dict[str, int],
                        objective: GearObjective | None) -> dict[str, int]:
    """`keep` with every `L*` code kept at the copies `L*` wears (two of a
    ring worn twice), held or missing (ruling AM, final review F6).

    A non-empty keep switches the blanket equippable keep off for every slot
    an active profile names (`inventory_keep._gear_demand`), so an `L*` piece
    the active profiles do not name kept 0 copies: banked while missing, it
    was drained; carried, it was recycled or sold. `L*` is what the character
    is building, so it is never surplus."""
    if objective is None:
        return keep
    out = dict(keep)
    for code, worn in Counter(objective.loadout.values()).items():
        out[code] = max(out.get(code, 0), worn)
    return out


def attach_gear_objective(state: WorldState, game_data: GameData, ctx: SelectionContext,
                          history: LearningStore | None) -> SelectionContext:
    """`ctx` with the cycle's gear objective and the grind target it names.

    `ctx` arrives with the held monsters task's monster (or None) as its
    `combat_monster` — the only grind target known before the objective — and
    its gear keep built for that monster. The objective is priced on that
    context; then the grind target is `farm_target`'s, the keep follows the
    final target (`ctx.near_term_targets` are the in-flight upgrades) and
    keeps every `L*` piece (`with_objective_keep`), and the risk is judged on
    it, bare of potions and at full hp.

    The objective is priced inside one `search_cache` episode: every drop and
    gather route it prices reads the learned drop tally and slope
    (`learning.drop_observations`) once, not once per route. Nothing here
    writes the store."""
    task_monster = ctx.combat_monster
    with history.search_cache() if history is not None else nullcontext():
        objective = gear_objective(state, game_data, ctx, history)
    combat_monster = farm_target(task_monster, objective)
    return replace(
        ctx, gear_objective=objective, combat_monster=combat_monster,
        gear_keep=with_objective_keep(
            ctx.gear_keep if combat_monster == task_monster
            else gear_keep_for(state, game_data, history, combat_monster,
                               ctx.near_term_targets),
            objective),
        combat_risky=(combat_monster is not None
                      and not secure_win(unpotioned(replace(state, hp=state.max_hp)),
                                         game_data, combat_monster)))
