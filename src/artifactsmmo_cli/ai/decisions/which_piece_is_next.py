"""The root walk's entry (spec 2026-10-18 §2.4): the next missing `L*` piece.

`ctx.gear_objective` is the cycle's `(L*, m*)`, computed once by the player.
While a piece of `L*` is missing the root is the next step on its acquisition
plan; only once `L*` is held does the character grind character XP, on `m*`.
A level-up is not an acquisition step (§6.2), so no `ReachCharLevel` heads the
walk while a piece is missing — except, INTERIM (ruling AI), when every missing
piece's step is declined and no gear action is available at all.
"""

# MODULE import, the idiom `root.py` uses on its own cycles: `root` imports
# this module to build its entry, so whichever of the two is reached first
# executes while the other is half built, and a NAME import of `RootWalk` /
# `IsThisTargetBlocked` would raise ImportError. Binding the module object
# defers the lookups to CALL time.
from artifactsmmo_cli.ai.decision import Decision
from artifactsmmo_cli.ai.decisions import root as _root
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import WorldState


def next_level(state: WorldState, game_data: GameData) -> ReachCharLevel | None:
    """The trunk: one more character level, or None at the API's level cap
    (`GameData.max_character_level`, final review F12). A `ReachCharLevel`
    above the cap can never be satisfied, and the character would grind `m*`
    for XP the game no longer awards."""
    if state.level >= game_data.max_character_level:
        return None
    return ReachCharLevel(level=state.level + 1)


class WhichPieceIsNext(Decision[MetaGoal]):
    """Which missing `L*` piece does the character acquire next?

    * `L*` held (§2.4.1): `ReachCharLevel(state.level + 1)` (none at the
      level cap, `next_level`), whose step fights
      `m*` (`ctx.combat_monster` is `m*` exactly while `L*` is held). One level,
      not a milestone: `(L*, m*)` is recomputed every cycle, so a level-up that
      makes better gear legal retargets the very next cycle.
    * a piece missing (§2.4.2): the FIRST piece, in `missing`'s own order
      (layer, then gain per price — never re-sorted here), whose step can be
      served this cycle (`RootWalk.serves`) goes to `IsThisTargetBlocked`: a
      crafting-skill gate becomes the next skill level, a missing material its
      `ObtainItem`. A piece whose step is declined is recorded with its reason
      and the next piece is asked.
    * every piece declined (INTERIM, ruling AI): no gear action is available
      this cycle, so XP is the next action that best advances the character
      (§2.4), and the root is `ReachCharLevel(state.level + 1)` on `m*`.
    * no objective: the wall, `None` — no achievable loadout pays XP on any
      monster, so there is neither a piece to build nor a fight to grind.

    A missing piece the decision's game data does not know RAISES: the
    objective and the catalogue disagree, which is a data fault, and a root
    classified against other data would hide it (API data or fail).
    """

    name = "WhichPieceIsNext"

    def __init__(self, objective: CharacterObjective, walk: "_root.RootWalk") -> None:
        self.objective = objective
        self.walk = walk

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision[MetaGoal] | MetaGoal | None":
        self.walk.trail.append(self.name)
        target = ctx.gear_objective
        if target is None:
            return None
        if target.held:
            return next_level(state, game_data)
        unknown = [piece.code for piece in target.missing
                   if game_data.item_stats(piece.code) is None]
        if unknown:
            # API data or fail: a piece the decision's catalogue does not know
            # is a data fault, never a root classified against other data.
            raise ValueError(f"gear objective names {unknown!r}, absent from game data")
        for piece in target.missing:
            gear = self.objective.classify_target(piece.code, state)
            if self.walk.serves(piece.slot, gear, state, game_data, ctx, history):
                return _root.IsThisTargetBlocked(piece.slot, gear, self.walk)
        # INTERIM (ruling AI, final review F1): every missing piece is declined,
        # so no gear step can be served. Returning None here shut the XP trunk
        # off for good whenever a piece the obtain model calls feasible maps to
        # no goal the walk can serve (live: `lich_race_trophy`, `no_step_goal`,
        # heads 3 of 5 objectives). Plan B must make the obtain model and the
        # walk agree, so `L*` never names such a piece; until then the trunk is
        # offered behind the declined pieces, which stay in `declined` by name.
        return next_level(state, game_data)
