"""Does a HELD task's target advance progression at all? (S-047, S-048)

A task is a DRAW, not a selection: the taskmaster assigns level-appropriate work
and its target is otherwise unguaranteed — a gathering task may ask for wood, ore
or fish (D-11). So the character's whole influence is in what it does with the
draw, and S-047 makes that one question: does completing this task advance the
character's level, or a skill?

Deliberately NOT "does it help the course in flight". Separating the two is what
lets S-049 keep a task that is merely untimely, and what lets S-050 treat a held
task as a standing premium on work the objective may choose later. A predicate that
asked about the current course could only ever answer "abandon it or drop it".

THE ZERO-YIELD BAND IS ASKED OF THE AUTHORITY, NOT RE-DERIVED. For a monsters task
that is `game_data.xp_per_kill`, the same function the projection walk uses to
decide a rung pays anything — measured live, a level-19 character's best beatable
monster is eleven levels down and pays exactly 0. For an items task it is
`skill_xp_positive`, which owns `GREY_SKILL_GAP`. Neither band is spelled as a
number here: a second copy of a band constant is how the two halves of a rule drift
apart.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.skill_xp_positive import skill_xp_positive
from artifactsmmo_cli.ai.world_state import WorldState


def task_advances_progression(state: WorldState, game_data: GameData) -> bool:
    """True iff finishing the held task would advance the character's level or a
    skill — S-047's single question, and S-048's discard condition negated.

    False when no task is held: there is nothing to judge, and reporting "advances
    nothing" for an absent task would make S-048 read as a standing instruction to
    discard. Callers gate on `state.task_code` before acting on this.

    NOT `task_feasibility.task_requirement`, and the distinction cost a rewrite.
    That function answers "what must the character RAISE to be able to do this
    task" and returns None when the task is ALREADY FEASIBLE — so a perfectly good,
    doable task reads as no-requirement, which a naive `is None -> False` turns
    into "advances nothing, discard it". Exactly backwards, and it would have
    thrown away every task the character could actually complete.
    """
    if not state.task_code or state.task_total <= 0:
        return False
    if state.task_type == "monsters":
        # The task code IS the monster code, so the authoritative answer is
        # available directly: what a kill pays this character right now. Same
        # function the projection walk uses to decide whether a rung pays at all.
        return game_data.xp_per_kill(state.task_code, state.level) > 0
    if state.task_type == "items":
        requirement = game_data.producing_requirement(state.task_code)
        if requirement is None:
            return False      # nothing known produces it; no progression to see
        skill, content_level = requirement
        return skill_xp_positive(content_level, state.skills.get(skill, 1))
    return False
