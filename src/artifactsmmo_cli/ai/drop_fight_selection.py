"""THE dropper-fight selection: given an item and the live action pool, the one
FightAction a goal should plan to hunt it with — or None when there is none.

Extracted 2026-07-27 from the two byte-identical copies that had grown in
`GatherMaterialsGoal.relevant_actions` and
`UpgradeEquipmentGoal._target_drop_fight`, at the point a THIRD caller was
needed (UpgradeEquipment's closure-material edges). One selection, three
callers — the repo's no-duplicate-implementations rule, and the reason the
proved `select_monster_for_drop` core has a single live wrapper again.

WHICH droppers are eligible at all is NOT decided here: that is the shared
oracle `ai/drop_obtainability.fightable_droppers`, the same verdict the
reachability walks in `tiers/` consult (spawn-known + winnable + grey policy).
This module only RANKS what the oracle approved and looks up the action —
adding no refusal the oracle did not already predict, except the one named
residual in the oracle's docstring (no FightAction in the passed pool). Before
the unification the grey gate lived here as a post-argmin VETO, which both
duplicated the walks' liveness test and let a nearby grey dropper mask a
fightable xp-positive one.

The ranking itself is the proved core (`select_monster_for_drop`,
formal/Formal/MonsterDropSelection.lean): keep exactly ONE dropper, the
lex-argmin of the expected-kills metric over rate/quantity/distance.

`allow_grey` is the caller's policy, deliberately NOT decided here nor in the
oracle — the callers disagree on it for good reasons documented at their call
sites, and folding either default in would silently change the other. A GREY
dropper (zero xp at the character's level) makes the plain fight inapplicable
(the xpPositive gate), so hunting its drops requires the proven drop_farm
variant (formal/Formal/ActionApplicability.lean, dropFarm arm: every structural
gate still applies).
"""

import dataclasses

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.drop_obtainability import fightable_droppers
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.monster_drop_selection import (
    MonsterDropCandidate,
    select_monster_for_drop,
)
from artifactsmmo_cli.ai.nearest_tile import nearest_or_error
from artifactsmmo_cli.ai.world_state import WorldState


def select_drop_fight(item: str, actions: list[Action], state: WorldState,
                      game_data: GameData, *, allow_grey: bool) -> FightAction | None:
    """The expected-kills-optimal fight for `item` among the droppers the shared
    oracle approved, or None.

    None means the oracle found no fightable dropper (`drop_obtainable` is
    False — an honest "no route from here", never a fallback to a fight the
    character would lose or gain nothing from), OR the oracle's residual: this
    `actions` pool carries no `FightAction` for any approved dropper.
    """
    droppers = fightable_droppers(item, state, game_data, allow_grey=allow_grey)
    fights_by_code: dict[str, FightAction] = {
        a.monster_code: a for a in actions if isinstance(a, FightAction)
    }
    drop_candidates: list[MonsterDropCandidate] = []
    winner_fights: dict[str, FightAction] = {}
    for monster_code, rate, mn, mx in droppers:
        fight = fights_by_code.get(monster_code)
        if fight is None:
            continue
        if fight.locations:
            loc = nearest_or_error(state.x, state.y, fight.locations, "gather")
            dist = abs(loc[0] - state.x) + abs(loc[1] - state.y)
        else:
            dist = 0
        drop_candidates.append(MonsterDropCandidate(
            monster_code=monster_code, rate=rate,
            min_quantity=mn, max_quantity=mx, distance=dist))
        winner_fights[monster_code] = fight
    chosen = select_monster_for_drop(item, drop_candidates)
    if chosen is None:
        return None
    fight = winner_fights[chosen]
    if game_data.xp_per_kill(chosen, state.level) > 0:
        return fight
    # Grey, and the oracle let it through: `allow_grey` held. The plain fight
    # fails FightAction's xpPositive gate, so hunt with the proven drop_farm
    # variant. No second grey decision is taken here.
    return dataclasses.replace(fight, drop_farm=True)
