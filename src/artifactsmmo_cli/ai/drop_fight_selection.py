"""THE dropper-fight selection: given an item and the live action pool, the one
FightAction a goal should plan to hunt it with — or None when there is none.

Extracted 2026-07-27 from the two byte-identical copies that had grown in
`GatherMaterialsGoal.relevant_actions` and
`UpgradeEquipmentGoal._target_drop_fight`, at the point a THIRD caller was
needed (UpgradeEquipment's closure-material edges). One selection, three
callers — the repo's no-duplicate-implementations rule, and the reason the
proved `select_monster_for_drop` core has a single live wrapper again.

The selection itself is the proved core (`select_monster_for_drop`,
formal/Formal/MonsterDropSelection.lean): never plan a losing fight
(`is_winnable` gate), keep exactly ONE dropper (the lex-argmin of the
expected-kills metric over rate/quantity/distance).

`allow_grey` is the caller's policy, deliberately NOT decided here — the two
existing callers disagree on it for good reasons documented at their call
sites, and folding either default into this function would silently change the
other. A GREY dropper (zero xp at the character's level) makes the plain fight
inapplicable (the xpPositive gate), so hunting its drops requires the proven
drop_farm variant (formal/Formal/ActionApplicability.lean, dropFarm arm: every
structural gate still applies).
"""

import dataclasses

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.monster_drop_selection import (
    MonsterDropCandidate,
    select_monster_for_drop,
)
from artifactsmmo_cli.ai.nearest_tile import nearest_or_error
from artifactsmmo_cli.ai.world_state import WorldState


def select_drop_fight(item: str, actions: list[Action], state: WorldState,
                      game_data: GameData, *, allow_grey: bool) -> FightAction | None:
    """The winnable expected-kills-optimal dropper fight for `item`, or None.

    Returns None when the item has no droppers, when no dropper is winnable with
    the live loadout, or when the chosen dropper is GREY and `allow_grey` is
    False — all three are honest "no route from here", not a fallback to a fight
    the character would lose or gain nothing from.
    """
    droppers = game_data.monsters_dropping(item)
    if not droppers:
        return None
    fights_by_code: dict[str, FightAction] = {
        a.monster_code: a for a in actions if isinstance(a, FightAction)
    }
    drop_candidates: list[MonsterDropCandidate] = []
    winner_fights: dict[str, FightAction] = {}
    for monster_code, rate, mn, mx in droppers:
        fight = fights_by_code.get(monster_code)
        if fight is None:
            continue
        if not is_winnable(state, game_data, monster_code):
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
    if not allow_grey:
        return None
    return dataclasses.replace(fight, drop_farm=True)
