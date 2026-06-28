# Sub-project B — Per-Task Loadout Optimizer — Design

**Status:** approved (brainstorm 2026-06-28) · **Epic:** Holistic Gear-Loadout
Architecture (`2026-06-28-gear-loadout-architecture-design.md`, on main).
**Branch:** `feat/gear-task-optimizer` (off main = sub-project 2 merged, tip `51d8f0de`).
**Build order:** sub-project 3 of 5 (A ✅ → unified ruler ✅ → **B** → {C, D}).

## Why

The loadout picker is **combat-only**: `pick_loadout(monster_code, …)` has 4 callers, all
passing a fight target; `pick_gather_loadout` is DEFINED BUT NEVER CALLED, so the bot gathers
with whatever weapon happens to be worn. The unified `gear_value(stats, purpose)` ruler
(sub-project 2) exists but the picker still calls the low-level scorers directly. B generalizes
the proved greedy picker to a **purpose**, folds in the dead gather picker, scores via the
unified ruler, and wires the gather path so the bot equips the right tool for the skill it is
gathering.

## Scope (approved decisions)

- **Generalize + wire gather.** Generalize `pick_loadout` to take a `purpose`
  (`Combat`/`Gather`/`Rank`), re-prove per-slot optimality ∀ purpose, route the 4 combat
  callers through `Combat(monster)`, AND wire the gather-loadout path (the only new live
  behavior). Craft/idle purposes are OUT.
- **The predict_win local-search improver is DEFERRED** to a later follow-up (it is
  proof-bearing — the "never worse" guarantee needs structure — adds predict_win calls to the
  loadout loop, this project's known CPU-peg risk, and overlaps with sub-project D's
  learned-loadout-vs-outcome). Greedy-per-slot via the unified ruler is B's final policy.

## Generalized greedy picker

`pick_loadout(monster_code, state, game_data)` → **`pick_loadout(purpose, state, game_data)`**,
`purpose ∈ {Combat(monster_attack, monster_resistance), Gather(skill), Rank}` (the value-objects
from `gear_value_core.py`). Folds in the dead `pick_gather_loadout`.

- Each slot's candidates are scored by a uniform **purpose-benefit** (higher = better),
  maximized per slot:
  - `Combat` → `gear_value(stats, Combat)` (already type-dispatches weapon→offense /
    armor→defense).
  - `Gather` → the tool-benefit magnitude, the **proven dual** of today's `argmin gather_score`
    (the codebase proves `tool_value = |gather_score|` and the argmax/argmin duality on the
    tool domain), so the existing `pickGatherSlot_score_optimal` transfers into one unified
    `pickSlot`.
  - `Rank` → `gear_value(stats, Rank)`.
- The realizability invariant, dual-ring cap, one-slot-per-code rule, and deterministic slot
  order are UNCHANGED (purpose-independent). `Formal.RealizableLoadout` and the per-slot
  optimality proof carry over, now parameterized by purpose.

## Generalized application + combat callers

`OptimizeLoadoutAction` carries a **`purpose`** instead of `target_monster_code`. Its two-pass
apply/execute, realizability assertions, one-slot-per-code, and dual-ring handling are already
purpose-agnostic — only `_swap_plan` changes to call `pick_loadout(self.purpose, …)`. The 4
combat callers build `Combat(monster_attack(m), monster_resistance(m))` from the monster they
already hold:
- `ai/combat.py:90` (predict_win), `ai/actions/combat.py:129` (FightAction.cost),
  `ai/actions/optimize_loadout.py:46`, `ai/goals/grind_character_xp.py:48`.

**No combat behavior change:** `Combat`-purpose scoring is bit-identical to today's
`weapon_score`/`armor_score` (proved in sub-project 2). A live regression test locks
`pick_loadout(Combat(m))` == today's `pick_loadout(m)` picks exactly.

## Gather wiring (the only new live behavior)

- **`OptimizeLoadoutAction(Gather(skill))` created per gather skill** — the 4 `GatheringSkill`
  enum values (mining/woodcutting/fishing/alchemy), derived generically from the enum (not
  hardcoded), the way combat creates one per monster.
- **Gating on the active gather activity.** There is no "current gather skill" signal at
  loadout time today (only `SelectionContext.combat_monster`). B adds one: the active gather
  goal/step exposes the skill it is gathering (the targeted resource's skill), and a gather
  goal's satisfaction includes "gather-loadout optimal for that skill" (mirroring
  `GrindCharacterXPGoal._loadout_optimal`), so the planner inserts `OptimizeLoadout(Gather(skill))`
  before gathering — and the gather loadout NEVER fires while fighting (gated to gather
  activity). Pinning the exact goal/step hook is the implementation's main integration task
  (locate the gather-driving goal/step, expose its skill, add the loadout-optimal gate).

## Module layout (the layering-cycle resolution)

Sub-project 2 fixed the direction `gear_value → scoring` (gear_value delegates to the low-level
scorers `weapon_score`/`armor_score`/`gather_score`). B needs the picker to score via
`gear_value(purpose)` — the reverse — which would cycle (`gear_value → scoring → gear_value`).

**Resolution: relocate the picker out of `scoring.py` into a new module above `gear_value`** —
`ai/equipment/loadout_picker.py`: layering `loadout_picker → gear_value → scoring(low-level
scorers)`. `scoring.py` keeps ONLY `weapon_score`/`armor_score`/`gather_score` (+ the
`_candidates_for_slot`/`_ordered_slots`/realizability helpers the picker needs may move with
the picker or stay as shared low-level helpers — keep the cut clean). The 4 picker callers
update their import to `loadout_picker`. One dispatch (gear_value), no duplication — the seam
the epic meant to invert.

- Pure proved core stays extracted; the relocated picker keeps the proved per-slot structure.
- New leaf imports: `loadout_picker` imports `gear_value` + the low-level scorers; no
  `game_data`↔picker cycle.

## Formal lockstep

- Unify `pickSlot` to be purpose-parameterized in `Formal/EquipmentScoring.lean` /
  `Formal/PurposeRouting.lean`; prove `pickSlot_score_optimal ∀ purpose`. The existing
  `pickGatherSlot` (argmin on `gatherScore`) folds into the unified `pickSlot` via the
  already-proven `tool_value = |gather_score|` duality (Gather's "maximize tool benefit" =
  today's argmin), so no optimality content is lost.
- `RealizableLoadout` (dual-ring ~25 roles), `LoadoutProjection`, `OwnedCount` carry over
  UNCHANGED (purpose-independent) — verify their `Contracts.lean` pins still elaborate.
- `Contracts.lean` exact-pins + `Manifest.lean` roster for the purpose-parameterized
  `pickSlot_score_optimal`.
- Differential: `pick_loadout(purpose)` ≡ oracle on random `(purpose, owned pool)` for all 3
  purposes (NO `unique=True`). Mutation: the unified per-slot scorer + the per-purpose
  direction/benefit handling — each drop-term mutant killed.

## Testing & rollout

- **Combat regression lock**: `pick_loadout(Combat(m))` reproduces today's `pick_loadout(m)`
  selection EXACTLY on live data (no combat loadout change).
- **Gather behavior**: `pick_loadout(Gather(skill))` equips the best tool for that skill; a
  test that the gather loadout fires ONLY under gather activity and never mid-combat.
- **`pick_gather_loadout` removed** (dead code folded into the generalized picker) — confirm no
  surviving caller.
- Full unit suite ≥ current bar (100%); full `formal/gate.sh` green; serialize gate/mutation vs
  a live `artifactsmmo play`; re-run `extract_lean.py` after any source move (the drift gate is
  strict — a relocation shifts line numbers).

## Out of scope / non-goals (→ later sub-projects)

- The bounded `predict_win` local-search improver (deferred follow-up).
- `Craft(skill)` and idle/`Rank`-loadout purposes (not chosen).
- Loadout profiles / dedup / bank-space (C); learned per-monster loadout (D); modeling the 9
  carved rune abilities (the "Player rune abilities" follow-on).
- Joint combinatorial loadout search (greedy-per-slot remains the model).
