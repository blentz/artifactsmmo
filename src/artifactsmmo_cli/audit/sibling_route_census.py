"""Does the sibling-craft route ever change an answer?

`ai.acquisition_cost._sibling_craft_option` prices a route no single-character
model has: a crafting-skill gate this character has not met, opened because a
LIVE SIBLING already holds the skill (`SelectionContext.sibling_skills`). It is
one more deferred `RouteOption` beside the gated-craft and gated-drop options
`route_options` already prices, and it competes on cost exactly like any other
route. This module measures whether that competition ever matters.

THREE QUESTIONS, KEPT DISTINCT ON PURPOSE. A skill-gated item can fail this
audit in three different ways, and each points at a different fix:

  1. ELIGIBLE — the character is behind the gate (`held_level < required_level`)
     and a sibling clears it (`best_sibling_level >= required_level`). This is a
     fact about `state.skills` and `ctx.sibling_skills` alone; it says nothing
     about whether the route was actually priced.
  2. PRICED — `route_options` returns an option whose `unlock` starts with
     `"sibling:"` (`_sibling_craft_option`'s own key, `acquisition_cost.py:421`).
     An item can be ELIGIBLE and UNPRICED: `_sibling_craft_option` also requires
     `store.fleet_supply_request_cycles()` to be a positive observation, so a
     fleet that has never served a supply request suppresses the gate even
     though the sibling genuinely qualifies.
  3. LOAD-BEARING — pricing the item with the real `ctx.sibling_skills` costs
     FEWER actions than pricing it with `sibling_skills` emptied
     (`SiblingVerdict.load_bearing`). An item can be PRICED and NOT LOAD-BEARING:
     the route exists but the character's own routes (a cheaper drop, a vendor,
     a recipe it can already satisfy some other way) already undercut it.

Collapsing these three into one verdict is how this audit would produce a
confident wrong answer: "104 eligible pairs" says nothing about whether the
route ever fires, and "N priced routes" says nothing about whether any of them
ever change what a plan would pick.

THE NO-SIBLING BASELINE IS `dataclasses.replace(ctx, sibling_skills={})`, NOT A
FRESH CONTEXT. `SelectionContext` carries ~20 other fields (gold reserve, task
draw, gear/step profiles, coordination claims) that `acquisition_actions` reads
indirectly through the routes it prices, and a from-scratch context would differ
from the real one in every one of them, not just this one. That would stop the
differential from isolating `sibling_skills` and turn it into a comparison
against an unrelated world. `replace` changes exactly the one field under audit
and nothing else — the same discipline `_ctx_with_siblings` in
`test_acquisition_cost_wrapper.py` already uses.

`priced` STAYS A CONJUNCT IN `load_bearing`, EVEN THOUGH IT LOOKS REDUNDANT.
Emptying `sibling_skills` changes one input to a walk (`acquisition_actions`)
that reads many others — bank stock, gold, gear, event availability. If the two
action counts differ while `route_options` never actually returned a sibling
option, that difference came from somewhere else in the walk, and crediting it
to this route would manufacture evidence for the very thing being audited.
"""

from dataclasses import dataclass, replace

from artifactsmmo_cli.ai.acquisition_cost import acquisition_actions, route_options
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass(frozen=True)
class SiblingVerdict:
    """One item's answer to all three questions the census asks.

    `held_level`/`best_sibling_level`/`required_level` together answer
    ELIGIBLE (`held_level < required_level <= best_sibling_level`) without a
    redundant boolean field — the three numbers ARE the fact, and restating it
    as a flag would let the two drift. `priced` and `saving`/`load_bearing`
    answer the other two questions; see the module docstring for why all three
    stay separate rather than collapsing into one pass/fail.
    """

    item: str
    skill: str
    required_level: int
    held_level: int
    best_sibling_level: int
    priced: bool
    actions_with: int
    actions_without: int

    @property
    def saving(self) -> int:
        """Actions the sibling route removes from the price, however it got
        there. Can be non-zero even when `priced` is False — see
        `load_bearing`, which is why this is NOT the census verdict on its
        own."""
        return self.actions_without - self.actions_with

    @property
    def load_bearing(self) -> bool:
        """The route was priced AND pricing the item without it costs more.

        `priced` is a conjunct, not a formality. Emptying `sibling_skills`
        changes one input to a walk that reads many; if the two prices differ
        while no sibling route was returned, the difference came from
        somewhere else and crediting it here would manufacture evidence for
        the thing being audited.
        """
        return self.priced and self.saving > 0


def sibling_route_verdicts(
    state: WorldState, game_data: GameData, ctx: SelectionContext,
    store: LearningStore, items: list[str],
) -> list[SiblingVerdict]:
    """One `SiblingVerdict` per skill-gated craftable item in `items`.

    An item with no recipe, or no `crafting_skill` on its recipe, names no
    skill gate for a sibling to clear and is silently skipped — the sibling
    route has nothing to say about it, so a verdict for it would be noise
    (or worse, `skill=""`, `required_level=0` rows a caller could mistake for
    a real, met gate).

    Every remaining item gets a verdict regardless of whether this character
    is actually behind the gate: ELIGIBLE is a property readers compute FROM
    the verdict (`held_level < required_level <= best_sibling_level`), not a
    filter this function applies, so a caller auditing "did I miss an eligible
    pair" can see every candidate it asked about, not just the ones this
    function already judged eligible.
    """
    verdicts: list[SiblingVerdict] = []
    for item in items:
        recipe = game_data.crafting_recipe(item)
        stats = game_data.item_stats(item)
        if recipe is None or stats is None or not stats.crafting_skill:
            continue
        skill = stats.crafting_skill
        routes = route_options(item, state, game_data, ctx, store)
        priced = any(route.unlock.startswith("sibling:") for route in routes)
        actions_with = acquisition_actions(
            item, 1, state, game_data, ctx, equip=False, store=store)
        no_sibling_ctx = replace(ctx, sibling_skills={})
        actions_without = acquisition_actions(
            item, 1, state, game_data, no_sibling_ctx, equip=False, store=store)
        verdicts.append(SiblingVerdict(
            item=item, skill=skill, required_level=stats.crafting_level,
            held_level=state.skills.get(skill, 1),
            best_sibling_level=ctx.sibling_skills.get(skill, 0),
            priced=priced, actions_with=actions_with,
            actions_without=actions_without,
        ))
    return verdicts
