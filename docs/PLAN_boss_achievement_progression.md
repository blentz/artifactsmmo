# PLAN #5: boss/elite pursuit + achievements as progression

**Priority:** 5. **Status:** DESCOPED from the level-50 critical path (2026-06-18).
**Depends on:** #1 (need boss combat modeled to fight them safely).

> **Boss-drop check (2026-06-18, audit #1 of the level-50 todo):** queried live
> game data — for every equippable gear item at level 20-50, expanded its full
> recipe closure and checked whether any required leaf material drops ONLY from a
> boss/elite/over-band monster. Result: NONE. The only two over-band ingredients
> (`cyclops_eye` for `dreadful_ring` lvl20, `orc_bone` for `corrupted_stone_amulet`
> lvl35) come from NORMAL monsters (cyclops lvl25, orc lvl38) — beatable with
> band-appropriate gear, gated safely by `is_winnable`, with lower-level XP always
> available to grind toward them (no deadlock). The 6 boss + 3 elite monsters are
> lvl 50-55 endgame content; reaching level 50 does NOT require beating any of
> them. So boss-pursuit (and the `progression_reserve.boss_targets` stub) is
> FORWARD-LOOKING endgame/achievement work, not a level-50 blocker. Build it when
> targeting post-50 content, not before.

## Problem

- **Bosses/elites** (of the 48 monsters): the bot fights only safely-winnable
  monsters (combat-veto + predict_win), so it AVOIDS bosses/elites — but those drop
  rare materials and gate progression/achievements. Until #1 models their abilities,
  the bot CAN'T assess them; once it can, it should pursue them when winnable and
  worthwhile.
- **Achievements**: modeled only for bank-unlock (the achievement-gated desert-island
  bank, monster-kill achievements). The broader achievement system (achievement
  points, kill-count / gather-count / craft achievements, achievement-gated rewards
  like artifacts) is largely unmodeled — the bot doesn't pursue achievements as a
  progression driver.

## Open questions (verify FIRST — read-only)
1. Are achievements loaded into GameData at all (the cached snapshot had no
   `achievements` collection — they may load via a separate endpoint)? Find the
   achievement accessor + what `unlock_bank` uses.
2. Which achievements gate which content/items (e.g. does novice_guide come from an
   achievement)? Does any gear/recipe require an achievement the bot can't currently
   earn?
3. Are boss drops in the recipe-closure / objective targets the bot already pursues
   (so it WOULD fight a boss if it could win), or are boss-only materials invisible to
   the planner?

## Approach (after verification)
- **Boss pursuit**: once #1 makes boss winnability assessable, the EXISTING combat
  target picker + objective system should naturally pursue winnable bosses for needed
  drops — verify the picker considers elite/boss monsters (it may filter them). Likely
  a small relaxation, not new machinery.
- **Achievement progression**: if achievements gate real rewards, add an
  achievement-aware objective (pursue an achievement when its reward is a needed
  gear/unlock and it's reachable) — a new objective/goal akin to unlock_bank
  generalized. Scope depends on the achievement API surface (Q1).

## Risk / sizing
Mostly DISCOVERY-bound — until the achievement surface (Q1/Q2) is known, sizing is
open. Boss pursuit is likely cheap (relax the picker after #1). Achievement-driven
progression could be a larger objective-layer feature. DEFER detailed design until the
verification answers Q1-Q3.
