"""Does the sibling-craft route ever change what the root walk CHOOSES?

`audit/sibling_route_census.py` (T2.0) answers whether `_sibling_craft_option`
lowers the priced cost of a catalogue item. That is a fact about
`acquisition_cost` alone — it says nothing about whether `decisions/root.
resolve_root` ever NAMES that item as the thing to pursue. A lower price only
matters if it moves the root walk's answer, and `resolve_root` is the ONLY
place that answer comes from (`decide_tree` calls it directly; see that
module's own docstring). This module drives it and classifies what it
returns.

THE CANDIDATE SET IS READ OFF THE RESOLUTION, NEVER REBUILT. `RootResolution.
alternatives` is "the ordered remainder of the ONE walk" — `resolve_root`'s
own docstring says so explicitly — NOT a ranking a caller could reconstruct
from the gate's inputs. A previous session in this codebase "confirmed" a fix
by rebuilding `alternatives` from what feeds the gate and was measuring its
own reconstruction rather than the walk's actual output
(`feedback_never_feed_a_walks_own_output_back_in`). `root_sibling_verdicts`
calls `resolve_root` exactly once and reads `resolution.root` /
`resolution.alternatives` straight off the return value — nothing here
recomputes what the walk visited or in what order.

THREE OUTCOMES PER CANDIDATE, KEPT SEPARATE ON PURPOSE (same discipline T2.0
uses, for the same reason):

  1. The candidate names NO item at all (`ReachCharLevel`, `ReachSkillLevel`)
     -- `item=None`, `verdict=None`. This is not a gap in the audit: it is the
     answer, in the case where the sibling route could not possibly apply
     this cycle because the root the walk is pursuing has no item for any
     route to price. Dropping this row would make "N roots, M sibling-priced"
     lie about its own denominator.
  2. The candidate names an item, but that item is not a skill-gated
     craftable at all (no recipe, or a recipe with no `crafting_skill`) --
     `item` is set, `verdict=None`, because `sibling_route_verdicts` itself
     silently skips such an item (see its own docstring). This is a real and
     distinct outcome from (1): the root asked for something, the sibling
     route simply has nothing to say about that specific thing.
  3. The candidate names a skill-gated craftable item -- `verdict` is exactly
     what `sibling_route_verdicts` returns for it, unmodified. This module
     never re-derives ELIGIBLE/PRICED/LOAD-BEARING; it calls the existing
     census over exactly the one item the candidate names.

`CHOSEN` IS AN IDENTITY CHECK AGAINST `resolution.root`, NEVER A POSITION
CHECK. `resolve_root` already guarantees no member of `alternatives` is
value-equal to `root` (`ordered` is filtered with `alt != root` before it
becomes `alternatives`), so `candidate is resolution.root` and `candidate ==
resolution.root` agree on every real resolution. What they do NOT agree on is
position: `root` can be `None` (`CanIClearMyTier`'s wall case), and when it
is, `[resolution.root, *resolution.alternatives]` with `None` filtered starts
with the FIRST ALTERNATIVE, not with "nothing chosen". A position check
(`index == 0`) would misreport that first alternative as chosen even though
the walk chose nothing; an identity check against `resolution.root` -- which
is `None` -- correctly matches no candidate at all, because no `MetaGoal`
instance is ever `is None`.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.decisions.root import resolve_root
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.audit.sibling_route_census import SiblingVerdict, sibling_route_verdicts


@dataclass(frozen=True)
class RootSiblingVerdict:
    """One candidate root's answer to "does the sibling route ever apply
    here, and is this the root the walk actually chose".

    `root_repr` is `repr(candidate)`, not the item code alone: `ReachCharLevel`
    and `ReachSkillLevel` name no item and still need a printable identity,
    and `ObtainItem`'s own `__repr__` already carries `slot` when set, which a
    bare `item` string would lose.
    """

    root_repr: str
    item: str | None
    chosen: bool
    verdict: SiblingVerdict | None


def root_sibling_verdicts(
    state: WorldState, game_data: GameData, objective: CharacterObjective,
    ctx: SelectionContext, store: LearningStore,
) -> list[RootSiblingVerdict]:
    """Drive `resolve_root` once and classify every candidate it returns.

    `store` does double duty, exactly as `commands/sibling_route_report.py`'s
    own `store` already does for T2.0: it is `resolve_root`'s `history`
    (`CanIClearMyTier` reads `next_uncleared_tier(state, game_data, history)`
    off it) AND `sibling_route_verdicts`'s `store` (`fleet_supply_request_
    cycles`, `skill_grind_rate`). One real store, read from, never written to
    -- this function performs no action and commits no session row.

    The candidate set is `[resolution.root, *resolution.alternatives]` with
    `None` filtered, in the order the walk returned them -- `root` is the
    wall case (`CanIClearMyTier` can return `None`), and `Sequence[MetaGoal]`
    cannot type a `None` member, which is why `resolve_root` itself filters
    it out of `ordered` before building `alternatives`; this function applies
    the identical filter to its own leading `root` slot for the same reason.
    """
    resolution = resolve_root(state, game_data, objective, ctx, store)
    candidates = [g for g in (resolution.root, *resolution.alternatives) if g is not None]

    rows: list[RootSiblingVerdict] = []
    for candidate in candidates:
        item = candidate.code if isinstance(candidate, ObtainItem) else None
        verdict: SiblingVerdict | None = None
        if item is not None:
            priced = sibling_route_verdicts(state, game_data, ctx, store, [item])
            verdict = priced[0] if priced else None
        rows.append(RootSiblingVerdict(
            root_repr=repr(candidate),
            item=item,
            chosen=candidate is resolution.root,
            verdict=verdict,
        ))
    return rows
