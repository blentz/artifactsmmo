# BACKLOG: synergy weighting between short- and long-term targets

Status: **IDEA, not designed.** Captured 2026-07-20 (user). Not scheduled — do not
start without picking it up deliberately.

## The thought

A 20,000-gather currency target is not inherently bad. It is bad *in isolation*. It
becomes worth pursuing when it ALIGNS with other targets the bot needs anyway —
gathering, crafting, and skill/character XP it would be earning regardless.

So target selection should weight a short-term target by how well it advances
long-term goals, rather than judging each target only on its own cost.

## Relationship to the existing jitter/fall-off

This generalises what the focus-aging fall-off and d'Hondt interleave already do.
That mechanism exists to stop a single root monopolising, and it deliberately keeps
a positive floor so a decayed root is never fully abandoned.

The same shape applies here: **favour high-synergy targets, but still select a
lower-synergy target occasionally.** The occasional off-target pick is not noise —
it is what avoids deadlock and what makes high-complexity goals reachable at all,
because those goals depend on prerequisites that look poorly aligned in the short
term.

## Worked example (user's)

* L50 is the ultimate goal, so `ReachCharLevel(current + 1)` should be *slightly*
  favoured overall.
* But reaching it requires work that is NOT aligned in the near term — e.g. taking
  tasks to earn task tickets to buy a satchel.
* Task goals are RANDOM skill grinds. They quasi-align with long-term needs (skill
  levels are wanted eventually) but may align poorly with what is needed now.
* Concrete synergy to exploit: align `FinishCurrentTask` with targets that trigger
  SkillXP grinding **for the skill the current task requires**. Then the task and
  the skill grind stop competing and become one line of progress.

## Why this is not a scoring rewrite

Note the constraint discovered 2026-07-19: `goal.value()` is NOT consumed by
arbiter selection (`arbiter_select.py` picks by fixed ladder position), and
`planner.py` deliberately runs `h = 0` because a non-zero heuristic was
inadmissible. So "weight the targets" cannot mean "add a score to the arbiter" —
that would be re-introducing exactly what was removed.

Any design here must say WHERE the weighting lives: the tree's candidate ranking
(where the fall-off already lives, and where `gain` is already a real number), not
the arbiter band walk and not the planner heuristic.

## Open questions

1. What is the synergy MEASURE? Shared prerequisites? Overlap in the recipe/drop
   closure? Skill-XP contribution to a skill some other live target needs?
2. Does it belong in `gear_target_pick`'s `_gear_pref_key` (currently
   `(-gain, -level, code, slot)`), as a term in `gain`, or as a separate weight fed
   to the existing d'Hondt scaling?
3. How does it interact with the fall-off? A high-synergy root that is STUCK should
   still decay — synergy must not defeat anti-starvation.
4. Does the "slightly favour level-up" part belong here at all, or is it the
   trunk/branch precedence the progression tree already encodes?
