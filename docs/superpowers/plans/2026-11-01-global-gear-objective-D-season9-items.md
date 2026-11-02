# Global Gear Objective, Plan D: Season 9 Items

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** model the Season 9 crafting tools as a craft-duration axis of the gear objective, and move the test world to the live Season 9 catalogue.

**Architecture:**
- A crafting effect cuts a craft's priced seconds the way a gathering tool cuts a gather's.
- The craft loadout wears the best one for the craft's skill, as the gather loadout wears a pickaxe.
- The gear objective values a crafting tool by the seconds it saves on the crafts the character's climb actually plans (spec §2.6: "They join `T*` (2.2) on a craft-duration axis").

**Tech Stack:** Python 3.13, uv, pytest, the `formal/` Lean gate.

**Spec:** `docs/superpowers/specs/2026-10-18-global-gear-objective-design.md` (§2.2, §2.6). The Season 9 data facts below were read from the live v9 API on 2026-11-01 (openapi 9.0.0, `/items`, `/effects`, `/npcs`, `/resources`, `/monsters`).

## Preconditions (USER 2026-11-01: "After Plan C")

- Plan C is merged to main, Task 9 included. This plan builds on the post-ladder gear objective (`tool_objective.py`, `progression/`).
- The ticket-farm fix (`ticket-farm-fix`, seconds pricing in `acquisition_cost._in_actions`, per-kind seconds in `learning/fight_seconds_model.py`) is merged. A craft is priced through `LogType.CRAFTING` seconds per run there.
- The Season 9 client fix 4763f1fb is in main. It carves `<skill>_crafting` in `game_data._ITEM_EFFECT_CARVEOUTS` via `_CRAFTING_TIME_EFFECTS`. Task 1 removes that carve.

## Global Constraints

- Use only API data. An effect code with no model raises `GameDataCoverageError`. There is no default.
- Effect codes, verbatim from `/effects`:
  - Crafting: `<skill>_crafting`, "Reduces total <skill> crafting time by {value}%", for every `CraftSkill`: alchemy, cooking, gearcrafting, jewelrycrafting, mining, weaponcrafting, woodcutting.
  - Gathering: `<skill>_gathering` (renamed from the bare `<skill>` in Season 8).
  - Values are negative integers. -10 means 10% less time.
- Alchemy, mining and woodcutting are both a gathering skill and a craft skill. `apprentice_gloves` carries `alchemy_gathering -10` AND `alchemy_crafting -10`. The two bonuses must never share a key.
- The repo rules in CLAUDE.md apply:
  - One behavioral class per file.
  - No inline imports.
  - Never catch `Exception`.
  - No `if TYPE_CHECKING`.
  - Tests use `ARTIFACTSMMO_TOKEN=dummy`.
  - Coverage stays at 100%, with 0 skipped tests.
- No alphabetical tiebreaks; ties break on a semantic key.

## Season 9 item facts (live, 2026-11-01)

| Item | Slot/type | Level | Crafting effect | Source |
|---|---|---|---|---|
| ash_rolling_pin | weapon/tool | 1 | cooking -10 | craft |
| iron_knife | weapon/tool | 10 | cooking -20 | craft (cooking_level > 9) |
| steel_cleaver | weapon/tool | 20 | cooking -30 | craft |
| gold_knife | weapon/tool | 30 | cooking -40 | craft |
| mithril_cleaver | weapon/tool | 40 | cooking -50 | craft |
| adamite_spatula | weapon/tool | 50 | cooking -60 | craft |
| voidstone_knife | weapon/tool | 50 | cooking -70 | `nomadic_merchant`, 250000 gold, no sell price |
| apprentice … voidstone_gloves (7) | weapon/tool | 1–50 | alchemy -10 … -70 (new) | unchanged recipes; they keep `alchemy_gathering` |
| altar_doll | artifact | 1 | all 7 crafting effects -10, all 4 gathering effects -10 | achievement `a_helping_hand` (50 favors), 5 copies |
| altar_totem | artifact | 40 | none (dmg 20, prospecting 50, crit 5, res 5×4) | achievement `a_favored_champion` (500 favors), 5 copies |

Every cooking tool also carries `attack_fire 5`. That makes a knife look like a weak combat weapon to any code that classifies a weapon by "has no `skill_effects`".

Other Season 9 data deltas, which need no new model, only the fixture refresh (Task 6):
- `lava_fish_spot` drop rate 100 → 1. The task renamed `laval_fish` → `lava_fish`.
- `copper_rocks` gains `diamond_stone` at 1/1500.
- `pixie` HP 600000 → 1200000; `sonnengott` HP 1500000 → 2000000.
- `diamond_armor` and `diamond_skirt` recipes changed.
- `malefic_crystal` dmg 6 → 8.
- `enchanted_mushroom` subtype mob → alchemy.
- `enchanted_rune` NPC buy price 200 → 150.
- Achievements `money_time` and `real_canadian` removed; the two favor achievements added.

## Review Focus

1. **A cooking tool must not enter a combat kit.** Check that `kit_selection` and every "weapon without skill_effects is combat gear" test stays correct for an item whose only tool effect is a crafting one. Test it in Task 1.
2. **Two keys for one skill name.** On `apprentice_gloves`, alchemy gathering and alchemy crafting must price two different actions. Test it in Task 1 and Task 2.
3. **Inventory dominance must not drop a crafting tool.** `inventory_caps` must not shed `iron_knife` because `copper_dagger` dominates it on attack, the way it already protects a pickaxe. Test it in Task 1.
4. **The learned seconds carry the effect of the tool worn when they were observed.** A craft seen while wearing `iron_knife` is 20% short. Pricing a craft from it as if no tool were worn double-counts the bonus. Test it in Task 2.
5. **Swapping the weapon to craft costs actions** (unequip, equip, re-equip for the next fight). The craft loadout must not swap when the saved seconds are below the swap cost. Test it in Task 3.

---

### Task 1: Read the crafting effects into their own field

**Files:**
- Modify: `src/artifactsmmo_cli/ai/item_catalog.py` (`ItemStats`)
- Modify: `src/artifactsmmo_cli/ai/game_data.py` (the `_build_items` effect dispatch; `_CRAFTING_TIME_EFFECTS`, `_ITEM_EFFECT_CARVEOUTS`)
- Modify: `src/artifactsmmo_cli/ai/equip_value.py`, `src/artifactsmmo_cli/ai/inventory_caps.py`, `src/artifactsmmo_cli/ai/kit_selection.py`
- Test: `tests/test_ai/test_game_data_item_effect_guard.py`, `tests/test_ai/test_inventory_caps*.py`, `tests/test_ai/test_kit_selection*.py`

**Interfaces:**
- Produces:
  - `ItemStats.craft_effects: dict[str, int]`, keyed by `CraftSkill` value, holding the signed percent.
  - `craft_tool_value(stats: ItemStats, skill: str) -> int`, equal to `abs(stats.craft_effects.get(skill, 0))`, in `equip_value.py`.
  - `is_tool(stats: ItemStats) -> bool`: true when `skill_effects or craft_effects`. Every "is a tool" test that today reads `skill_effects` alone uses it instead.

- [ ] **Step 1: Write the failing tests.**
  - `test_crafting_effect_reads_into_craft_effects`: `_item("iron_knife", "weapon", ["cooking_crafting", "attack_fire"])` gives `craft_effects == {"cooking": v}` and `skill_effects == {}`.
  - `test_gloves_keep_both_alchemy_bonuses_apart`: `apprentice_gloves` gives `skill_effects == {"alchemy": v}` and `craft_effects == {"alchemy": v}`.
  - `test_cooking_tool_is_not_a_combat_kit_weapon`: `kit_selection` excludes `iron_knife`.
  - `test_dominance_keeps_a_crafting_tool`: `copper_dagger` held does not mark `iron_knife` shed-able.
  - Delete `test_crafting_time_effect_is_carved_and_uncredited` and `test_crafting_time_effects_are_one_per_craft_skill`.
- [ ] **Step 2: Run them.** `ARTIFACTSMMO_TOKEN=dummy uv run pytest tests/test_ai/test_game_data_item_effect_guard.py -q --no-cov` fails on the missing field.
- [ ] **Step 3: Implement.**
  - The dispatch branch is `effect.code.removesuffix("_crafting") in {s.value for s in CraftSkill}` and stores into `craft_effects[skill]`.
  - Delete `_CRAFTING_TIME_EFFECTS` and its carve-out union.
  - Replace the `skill_effects`-only tool tests at the sites `grep -rn "skill_effects" src/` lists with `is_tool`. Check each site and record it in the report: some sites mean "gathering tool" only, and those stay as they are.
- [ ] **Step 4: Run the touched test files, then `mutate --only` on the touched source files.** Anchors refresh in the same commit.
- [ ] **Step 5: Commit.**

### Task 2: A craft is priced at the seconds of the tool it is made with

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/fight_seconds_model.py` (the per-kind seconds: craft runs from `_REPR_QUANTITY`)
- Modify: `src/artifactsmmo_cli/ai/learning/store.py`, plus a `Cycle` column for the craft effect worn and its migration (follow the existing `fight_turns` / `fight_haste` column pattern)
- Modify: `src/artifactsmmo_cli/ai/acquisition_cost.py` (the craft route's seconds)
- Test: `tests/test_ai/test_fight_seconds_model.py`, `tests/test_ai/test_acquisition_cost*.py`

**Interfaces:**
- Produces:
  - `craft_seconds(base: Fraction, effect_pct: int) -> Fraction`, equal to `base * (100 + effect_pct) / 100`. This is the server's "reduces total crafting time by N%".
  - `Cycle.craft_effect_pct: int | None`: the worn `craft_effects[skill]` of a recorded craft.
  - The learned `crafting` seconds are normalised to no tool: each observation is divided by `(100 + e) / 100`.

- [ ] **Step 1: Live witness first.** The model's factor rests on the server's rounding, which no doc states.
  - On one fresh character, craft one cooking recipe bare and once wearing `ash_rolling_pin`. Read both cooldowns from the action responses.
  - Record the rounding rule (floor, round or ceil, and whether per run or per batch) in the report.
  - This is a live action: ask the user before running it.
- [ ] **Step 2: Write the failing tests.**
  - `test_craft_seconds_scale_by_the_worn_effect`, with the witnessed rounding.
  - `test_learned_craft_seconds_are_normalised_to_no_tool`: a store row made at -20 reads back as base seconds.
  - `test_a_craft_route_is_cheaper_with_the_best_held_tool`.
- [ ] **Step 3: Implement.** Record the worn effect when a craft cycle is written. Normalise on read. Price the craft route at the best crafting tool the character holds (bag, bank or worn) for that skill. Task 3 pays the swap.
- [ ] **Step 4: Localized tests, plus `mutate --only` on the touched files.**
- [ ] **Step 5: Commit.**

### Task 3: The craft loadout wears the crafting tool

**Files:**
- Modify: the craft action and its loadout precondition. Mirror how `actions/gathering.py` and `goals/gathering.py` wear the gather tool, and how `craft_plan_gen.py` emits the equip before a craft (its fast path is a second plan producer; see the "two plan producers" memory).
- Test: `tests/test_ai/test_craft_plan_gen*.py`, the craft action tests.

**Interfaces:**
- Consumes: `craft_tool_value` (Task 1) and `craft_seconds` (Task 2).
- Produces: `best_craft_tool(skill, state, game_data) -> str | None`, the held tool that minimises the craft run's seconds plus the swap's seconds. It is None when no swap pays.

- [ ] **Step 1: Write the failing tests.**
  - `test_craft_plan_equips_the_knife_before_a_long_cooking_batch`
  - `test_a_one_run_craft_does_not_swap_when_the_swap_costs_more`
  - `test_both_plan_producers_agree_on_the_craft_loadout` (A* against `craft_plan_gen`)
- [ ] **Step 2: Implement.** One authority for the choice. Both producers call `best_craft_tool`.
- [ ] **Step 3: Localized tests and mutants. Run one live `plan` on a character holding a crafting tool: the plan must show the equip.**
- [ ] **Step 4: Commit.**

### Task 4: A crafting tool is a gear-objective target on the craft-duration axis

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tool_objective.py` (`tool_target`; its docstring already names Season 9 crafting tools)
- Modify: the `T*` gain term in the gear objective (spec §2.2), wherever Plan C left it
- Test: `tests/test_ai/test_tool_objective*.py`, gear-objective tests

**Interfaces:**
- Consumes: `craft_tool_value`, `craft_seconds`, and the climb's planned crafts.
- Produces: `tool_target(skill, …)` ranks on `craft_effects` for a craft skill climb and on `skill_effects` for a gathering climb. For alchemy, mining and woodcutting the axis comes from the climb's action kind, not the skill name.

- [ ] **Step 1: Write the failing tests.**
  - `test_a_cooking_climb_fetches_the_rolling_pin_first`, at cooking level 1, with a held `copper_dagger`.
  - `test_the_tool_is_skipped_when_its_price_exceeds_the_seconds_it_saves`. The 250000-gold `voidstone_knife` against a short remaining climb is the live case.
  - `test_alchemy_gather_climb_ranks_gloves_on_gathering_not_crafting`.
- [ ] **Step 2: Implement.** The gain of a crafting tool is the seconds it saves across the crafts left in the climb, at `craft_seconds`, against its acquisition price in the same unit.
- [ ] **Step 3: Localized tests and mutants. Run the craft-completeness and skill-climb census `--check`s.**
- [ ] **Step 4: Commit.**

### Task 5: The altar artifacts are fixed-supply rewards

**Files:**
- Modify: `obtain_sources` and the achievement-reward source, only if the tests below fail. They check that the existing fixed-supply rule (the `novice_guide` case) covers achievement-only artifacts.
- Test: `tests/test_ai/test_obtain_sources*.py`

- [ ] **Step 1: Write the tests.**
  - `test_altar_doll_is_not_a_buildable_target_until_held`: no craft, NPC, drop or GE source, so it is never an `L*` piece the character must obtain.
  - `test_a_held_altar_doll_counts_its_gathering_and_crafting_effects`: in the artifact slot, its 11 effects reach both loadouts.
  - `test_voidstone_knife_is_an_npc_buy_at_its_gold_price`, via `nomadic_merchant`. Check whether that NPC is event-gated (see the "Every buyer is an event NPC" memory) and test the gate.
- [ ] **Step 2: Fix only what fails. Run localized tests. Commit.**

The offerings, the favors and how to earn the doll are out of scope. They go in a separate Seasonal Altar spec (USER 2026-11-01).

### Task 6: Move the test world to the Season 9 catalogue

**Files:**
- Regenerate: `tests/test_ai/scenarios/fixtures/gamedata_bundle.json`, `formal/sim/game_data_snapshot.json`, and every fixture `grep -rln "laval_fish\|money_time\|real_canadian" tests formal` finds.
- Regenerate: every census matrix under `docs/behavioral_completeness/` through its `scripts/gen_*.py`. If `formal/Formal/Liveness/GameDataFixture.lean` derives from the snapshot, regenerate it too.
- Modify: tests that hard-code a Season 8 value from the delta list above.

- [ ] **Step 1: Recapture.** Use each fixture's own capture path (find its writer with grep), with the live token read in place. The snapshot holds API data only, not the token: grep the new files for `eyJ`.
- [ ] **Step 2: Regenerate the census docs. Then write every verdict that moved, and the Season 9 delta that moved it, into the report.** A PASS → FAIL that no delta explains is a defect: stop and report it.
- [ ] **Step 3: Run the full gate once** (`formal/gate.sh`, live token). It runs from a checkout with a `TOKEN` file, per the user's 2026-11-01 ruling: a symlink, removed after.
- [ ] **Step 4: Commit fixtures and docs in separate commits.**

### Task 7: Final review, live witness, merge

- [ ] Run `plan` live for Alpha, Beta, Gamma, Delta and Epsilon, using `--learn` on a learning-DB backup copy. Report every root, goal or plan that names a crafting tool, and explain each.
- [ ] Final opus review of the whole branch, covering the Review Focus list.
- [ ] Gate green, then `git push origin HEAD:main`, fast-forward local main, and tell the user to restart the fleet.

## Out of scope, recorded

- Seasonal Altar offerings and favors: a separate spec.
- **Fresh-install cold start:** with an empty learning DB and characters with no fights, `fight_seconds_model.solve` raises "no fight with a positive cooldown to fit fight seconds on". Seen live on 2026-11-01 for `plan Alpha` without `--learn`. The fleet is unaffected because it reads the Season 8 history. This predates Season 9 and needs its own ruling.
- `CharacterStatsSchema.items_crafted` (new) and the `rename` endpoint: no decision uses them.
