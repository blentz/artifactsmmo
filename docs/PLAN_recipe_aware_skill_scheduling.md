# PLAN: recipe-aware skill scheduling (just-in-time skilling)

Status: CLOSED 2026-06-13 — IMPLEMENTED on branch `feature/recipe-aware-skilling`.
Spec: docs/superpowers/specs/2026-06-13-recipe-aware-skill-scheduling-design.md.
Plan: docs/superpowers/plans/2026-06-13-recipe-aware-skill-scheduling.md.
All 11 tasks done; full pytest 3217 passed @ 100% cov; formal gate green
(lake build 6177 jobs, axiom lint OK, extraction drift clean, differential 501
passed, mutation gate OK with the three skill_target_curve anchors killed + zero
survivors). Live dry-run confirms near-term curve ReachSkillLevel roots score
gap-proportionally (3.84 catch-up) and outrank the gear-gather freeze, while
endgame skill-50 roots stay flat (0.24). The pure core `skill_curve_target_pure`
is kernel-proven (monotone-in-char-level, ≤max) and extraction-bridged.

## Motivation (user, verbatim intent)

> Not a bug. The skill needs leveling up because we need the better gear for
> continued success in combat. The real question is what is the optimal
> methodology or order to progress? Was such a large jump necessary in
> hindsight? Robby is leveled up quite a bit. Should he have prioritized
> skilling up along the way? We know the recipe progression. We should be able
> to identify when to prioritize skilling up each skill so we can make use of
> the recipes unlocked.

## The observed symptom (run-7 trace 2026-06-12 23:01)

Robby char-level 7, weaponcrafting **2**. Arbiter committed to
`ObtainItem(water_bow)` (lvl-5 weapon, attack_water 16 — a 2.6x upgrade over
copper_dagger's air 6). water_bow craft needs **weaponcrafting 5**. So from a
standing start the bot must grind weaponcrafting 2→5 NOW — a multi-hour freeze
of char-level progress — instead of having skilled it gradually while leveling.
ReachCharLevel(9) actually out-scored water_bow per-cycle (1.48 vs 1.0) but the
committed gear objective overrode it (intended objective-commitment).

## Desired behavior

Spread crafting-skill XP investment over the leveling curve so that each
crafting skill is at (or near) the level its tier of recipes needs, BEFORE the
char-level makes those recipes the best available gear. No big catch-up grind:
skilling happens "along the way." We KNOW the recipe progression (the crafting
recipe tree + each recipe's craft skill+level), so the schedule is computable.

## Open design questions (for the grill / brainstorm)

1. **Target curve**: for each crafting skill, what skill-level should the bot
   hold at each char-level? Derive from the recipe tree: skill_target(skill,
   char_level) = max craft_level over recipes whose item_level <= char_level
   for that skill? Or a softer "stay within K of the next needed level"?
2. **Interleaving budget**: how much of each level's cycles go to proactive
   skilling vs combat? A fixed fraction, or driven by the gap between current
   skill and its target curve?
3. **Which skills**: all crafting skills, or only those on the path to the
   character objective's target gear? (Avoid grinding cooking if no recipe on
   the gear path needs it.)
4. **Where it lives**: a new strategy tier that emits ReachSkillLevel roots with
   a proactive (not just-in-time) trigger, vs. tuning the existing arbiter cost
   model so skill-gate steps are priced by their true horizon (the deferred
   "time-aware step cost" item — related, possibly subsumed).
5. **Proof obligation**: the scheduler is decision logic on the gear path →
   likely a pure core under the formal gate (recipe→skill-target is a pure
   function of game data). Mirror the existing extraction policy.

## Relationship to prior deferred items

Supersedes the framing of the Phase-3 deferred "skill-gate cost model prices
grinds at ~cost 2 vs real ~12h" (PLAN_drop_farming.md). That item said "make the
cost honest so the arbiter avoids the freeze"; the user's direction is stronger
— don't just avoid the freeze, PREVENT it by skilling proactively so the recipe
is already craftable when wanted.

## Next step

`/cs:grill-me docs/PLAN_recipe_aware_skill_scheduling.md` to walk the decision
tree (target-curve shape first), then write the spec.
