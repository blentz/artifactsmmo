# ROADMAP: remaining game-modeling work

**Status:** planned (2026-06-16). Origin: full-surface audit after the stat-audit
fixes ([[project_stat_audit_fixes]]). Game data: maps(476), items(485),
resources(24), monsters(48), npcs(95), events(16), bank.

## Priority order (user-set): 1 → 3 → 6 → 5 → 4 → 2

| # | Area | Plan | Core cost | Value |
|---|---|---|---|---|
| 1 | Monster combat abilities in predict_win (poison/barrier/burn/healing/boss exotics) | `PLAN_combat_abilities_model.md` | HIGH (proven core, multi-phase) | prevents mispredicted losses as Robby levels into elite/boss |
| 3 | Combat buff consumables (utility-slot boost_dmg/res/hp, restore, antipoison) | `PLAN_combat_buff_consumables.md` | (a) low value-lockstep, (b) proven core w/ #1 | win marginal fights; equip utility gear |
| 6 | Misc: cooking heal-supply (6a), teleport (6b, defer), threat (6c, carve-out) | `PLAN_misc_low_value.md` | LOW | 6a cuts rest-overhead; rest record-and-defer |
| 5 | Boss/elite pursuit + achievements | `PLAN_boss_achievement_progression.md` | discovery-bound | rare drops + achievement progression |
| 4 | Event content exploitation | `PLAN_event_content.md` | discovery-bound | time-limited drops |
| 2 | Gold/GE economy (already well-modeled; only active gold-farming likely worth it) | `PLAN_gold_ge_economy.md` | LOW | only if traces show gold blocking |

## Cross-cutting meta-fix (do alongside, cheap)

The root of the whole stat-audit class of bugs: the effect parser is a fixed
ALLOWLIST; unlisted codes are silently dropped. Add a **parser-coverage guard** — a
test (or load-time assertion) that FAILS when the game data carries an effect code the
parser neither maps nor explicitly carves out. Then any future stat the server adds
can't slip through silently (as wisdom/prospecting/inventory_space/haste/lifesteal
did). Maintain an allowlist + a documented carve-out list (threat, monster-only ability
codes already handled in predict_win, etc.). Build this early so #1/#3 additions
auto-register and the next unmodeled stat is caught at the gate, not in a trace.

## Notes
- #1 and #3(b) share the predict_win net-step machinery (built for lifesteal,
  267ce84) — do #1's poison/DoT terms first so #3's restore/antipoison have a per-turn
  term to compose with.
- #5/#4/#2 are DISCOVERY-bound: each opens with read-only verification questions; size
  them only after those answers. Don't pre-build.
- Everything decision-logic goes through the formal gate (parse→value/predict→Lean
  core→bridge→extraction→differential→mutation→full gate.sh). Template:
  `PLAN_combat_stats_haste_lifesteal.md` (value) + the lifesteal predict_win commit
  (proven-core restructure).
