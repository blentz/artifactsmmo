# PLAN: stat/item audit roadmap (effect-code coverage)

**Status:** planned (not started). Branch: (new feature branch for these fixes.)
**Origin:** 2026-06-15 audit of the cached game data after the novice_guide fix
([[project_utility_gear_value.md]]). 533 items, all distinct effect codes enumerated.

## Root pattern (the meta-bug)

The effect parser (`game_data.py:818-842`) is a fixed ALLOWLIST of codes
(heal/attack_*/res_*/dmg/dmg_*/critical_strike/initiative/hp/wisdom/prospecting/
gather-skills). EVERY unlisted code is silently dropped → the item's stat is invisible
→ undervalued/discarded/never-equipped. novice_guide (wisdom/prospecting) was one
instance; the audit found more. Consider a "known-but-unmodeled" assertion or a
coverage test that fails when game data carries an effect code the parser ignores, so
the next added stat can't slip through silently.

## Prioritized work items

| # | Stat / item | Count | Impact | Plan | Status |
|---|---|---|---|---|---|
| 1 | `inventory_space` (bags) | 9 | **highest** — equip bags → capacity → kills discard pressure | `PLAN_inventory_space_bags.md` | **DONE** (cd68214) |
| 2 | `haste` | 43 | combat damage output; skews predict_win | `PLAN_combat_stats_haste_lifesteal.md` | TODO |
| 3 | restore-family (`restore`/`splash_restore`) | 8 | heal potions invisible | `PLAN_consumable_effects.md` (Stage 1, cheapest) | **DONE** (7fc29bf; boost_hp deferred) |
| 4 | `lifesteal` | 6 | combat sustain in predict_win | `PLAN_combat_stats_haste_lifesteal.md` | TODO |
| 5 | `threat` | 45 | aggro — LOW for a solo bot; defer | (this doc) | deferred |
| 6 | buff potions (`boost_dmg_*`/`boost_res_*`), `antipoison`, `boost_hp` | ~12 | needs pre-fight-buff / status modeling; defer | `PLAN_consumable_effects.md` (Stage 2/3) | deferred |

**Done so far on this branch:** #3 restore-family (parser-only) + #1 bags/inventory_space
(full equip-value lockstep). Both followed the parse→value→formal-lockstep template.
**Next:** #2 haste — heavier (touches the proven `predict_win`); verify the haste
formula from docs.artifactsmmo.com first.

Monster-only ability codes (burn/poison/corrupted/frenzy/berserker_rage/void_drain/
protective_bubble/reconstitution/vampiric_strike/barrier/shell/guard/healing_aura) are
combat mechanics on monsters — only relevant if predict_win models them; out of scope
unless fights prove mispredicted because of them.

## Suggested sequence on the new branch

1. **restore-family → hp_restore** (Stage 1 of consumables) — cheapest, no proven-core
   change, good warm-up + immediately useful.
2. **inventory_space / bags** — highest value; verify server-vs-client capacity first.
3. **haste** — broad combat coverage; heavier (predict_win proven core).
4. **lifesteal** — combat sustain; with haste.
5. Add the parser-coverage guard (meta-fix) so future stats can't slip silently.

Each follows the established lockstep: parse → ItemStats field → downstream wiring
(scoring / equip_value / predict_win / consumable selection) → Lean cores + bridges +
extraction + differential + mutation → full `formal/gate.sh` green. Template:
`PLAN_artifact_utility_value.md`.
