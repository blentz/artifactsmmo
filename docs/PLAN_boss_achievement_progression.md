# PLAN #5: boss/elite pursuit + achievements as progression

**Priority:** 5. **Status:** planned. **Depends on:** #1 (need boss combat modeled to
fight them safely).

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
