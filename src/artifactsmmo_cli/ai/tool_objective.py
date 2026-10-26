"""The tool a skill climb fetches first (spec 2026-10-18 §2.6, plan B Task 8).

A tool is any item whose `skill_effects` name the skill (`tool_value`): the
fishing net's -10 fishing, and a Season 9 crafting tool's effect on its craft
skill alike, so no skill is special-cased. Before the character climbs a skill
it first obtains the best such tool it can: the climb's cooldown shrinks for
every action after.

Prospecting is the drop axis's tool (§2.8, plan B Task 12b): before the drop
work a step still holds, the character first obtains the prospecting item whose
gain to the loadout that work is done in pays for itself.
"""

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime

from artifactsmmo_cli.ai.acquisition_cost import acquisition_actions, drop_work_actions
from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
from artifactsmmo_cli.ai.drop_leg import DropLeg
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import PIECE_POLICY
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.tiers.equip_value import tool_value
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachSkillLevel, StepDecline
from artifactsmmo_cli.ai.world_state import WorldState


def _owned(state: WorldState) -> frozenset[str]:
    """Every code in the bag, the bank or worn."""
    bank = state.bank_items or {}
    return frozenset({code for code, n in state.inventory.items() if n > 0}
                     | {code for code in state.equipment.values() if code}
                     | {code for code, n in bank.items() if n > 0})


def tool_target(skill: str, state: WorldState, game_data: GameData,
                ctx: SelectionContext, now: datetime) -> str | None:
    """The level-legal item with the largest `tool_value` for `skill` among
    those achievable under `PIECE_POLICY` (the policy `L*` pieces are judged
    achievable by), or None when none is, or when that best one is already
    owned. A tie goes to the owned copy (nothing to fetch), then to the lower
    item level; a full tie keeps the catalogue's own order. `now` is the caller's
    cycle clock (the obtain model's event gates read it)."""
    owned = _owned(state)
    candidates = [(tool_value(stats, skill), code in owned, -stats.level, code)
                  for code, stats in game_data.items.stats.items()
                  if stats.level <= state.level and tool_value(stats, skill) > 0]
    # Stable sort, descending on the semantic key only.
    candidates.sort(key=lambda row: row[:3], reverse=True)
    model = ObtainModel(state, game_data, ctx, now)
    for _value, held, _level, code in candidates:
        if held:
            return None
        if model.feasible(code, 1, PIECE_POLICY):
            return code
    return None


def tool_first(climb: ReachSkillLevel, state: WorldState, game_data: GameData,
               ctx: SelectionContext, now: datetime,
               step_decline: StepDecline) -> ObtainItem | ReachSkillLevel:
    """The best tool's `ObtainItem` while the character does not yet own the
    best tool it could for the climbed skill (§2.6), else `climb`. The tool is
    an accelerator, not a gate (ruling T8a): a tool whose step `step_decline`
    refuses this cycle leaves the plain climb, never a declined piece."""
    tool = tool_target(climb.skill, state, game_data, ctx, now)
    if tool is None:
        return climb
    root = ObtainItem(tool, 1)
    if step_decline(root) is not None:
        return climb
    return root


def _owned_view(state: WorldState) -> WorldState:
    """`state` with the bank's stock in the bag: the loadout a drop leg is
    attempted in is picked from everything the character owns, so a banked
    prospecting item counts as held (the gear walk equips owned gear) and is
    never fetched a second time."""
    bag = dict(state.inventory)
    for code, n in (state.bank_items or {}).items():
        bag[code] = bag.get(code, 0) + n
    return replace(state, inventory=bag)


def drop_tool_target(work: Sequence[DropLeg], state: WorldState,
                     game_data: GameData, ctx: SelectionContext) -> str | None:
    """The level-legal prospecting item `t` with the highest prospecting that
    pays for itself on `work`, the remaining drop work of the step it would
    precede (spec 2026-10-18 §2.8: a tool is worth its saving, ruling T12j):

        price(t) < W(owned) - W(owned + t)

    or None. `W` is `drop_work_actions`, the one drop model (`ctx.drops()`), each
    leg at the prospecting of the loadout it is attempted in, picked from what
    the character owns (bag, bank and worn: `_owned_view`). So `t`'s gain is
    what that loadout gains by owning it — its prospecting less what it
    displaces, and nothing at all for an item the leg's loadout would not wear
    (a gather never wears body armour) or a copy already held. `price(t)` is
    the acquisition walk's price for one `t` under `PIECE_POLICY`; at
    `UNOBTAINABLE_PER_UNIT` or more it is out of reach.

    Candidates go by prospecting descending, then the lower level, then the
    catalogue's own order; the first that pays is the answer. One that saves
    nothing is passed over before its price is walked (ruling T12l), so the
    walks are one per candidate that would actually be worn."""
    owned = _owned_view(state)
    base = drop_work_actions(work, owned, game_data, ctx)
    candidates = [(stats.prospecting, -stats.level, code)
                  for code, stats in game_data.items.stats.items()
                  if stats.level <= state.level and stats.prospecting > 0]
    # Stable sort, descending on the semantic key only.
    candidates.sort(key=lambda row: row[:2], reverse=True)
    for _prospecting, _level, code in candidates:
        with_tool = replace(owned, inventory={**owned.inventory,
                                              code: owned.inventory.get(code, 0) + 1})
        saving = base - drop_work_actions(work, with_tool, game_data, ctx)
        if saving <= 0:
            continue
        price = acquisition_actions(code, 1, state, game_data, ctx, equip=False,
                                    policy=PIECE_POLICY)
        if price < UNOBTAINABLE_PER_UNIT and price < saving:
            return code
    return None
