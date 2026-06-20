# Objective-Step Arming + Gear-Feasibility Liveness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Discharge `perceptionRefresh`'s asserted `objectiveStepFires/IsFight := true` (below level 50) with a proof grounded in a winnable-monster-exists fact that is itself grounded from live game data two ways (differential sweep + pure-Lean kernel proof over the extracted catalog), and close "corner 3" (the `minGathers` craft-monotonicity coupling) for the demand-1 / no-surplus gear-obtainment class that underpins it.

**Architecture:** Five layers, built bottom-up. (C1) capture per-level base stats → un-skip the existing `WinnableAcrossBand` differential sweep (empirical grounding). (C1b-extract) emit the live monster catalog + base stats into `GameDataFixture.lean`. (C0) introduce a `NoSurplusPlan` invariant in `PlanModel.lean` and discharge the `corner3` craft-monotonicity obligation per-craft for that class, plus a constructive `canonicalPlan` obtainability witness. (C1b-proof) bridge the opaque `WinnableFn` to `predictWin` with a per-level `base + best_weapon_for_level` stat model and `decide` `WinnableAcrossBand` over the finite band × finite catalog. (C2) replace the `perceptionRefresh` assertion with a proof from combat-target-existence + structural fight-plannability + an O5.4-style production differential. (C3) re-prove `cycleStepF_reaches_fifty_of_fights` with `FightsBelowCap` discharged.

**Tech Stack:** Lean 4 + Mathlib (Liveness tier only; safety/core modules stay core-only), Python 3.13 (`uv`), Hypothesis differential tests, `formal/gate.sh` (lake build + axiom lint + differential + mutation).

## Global Constraints

- `uv` lives at `~/.local/bin/uv` (NOT on PATH); always invoke Python as `~/.local/bin/uv run …`.
- ALWAYS prefix Python with `uv run` (e.g. `~/.local/bin/uv run pytest`, `… mypy`).
- NEVER commit `sorry`, `admit`, `axiom` (beyond the signed-off liveness axioms), or `native_decide` without per-use justification recorded for the axiom gate. The final theorems must be 0-sorry.
- Liveness-tier modules MAY use Mathlib/classical tactics; safety/core modules (incl. `PlanModel.lean`, `PredictWin.lean`, `StepDispatch.lean`) stay CORE-ONLY (no `ring`/`set`/`norm_num`/`decide`-on-reals). `decide`/`native_decide` over the finite catalog is permitted ONLY in a Liveness-tier module and must be axiom-gate justified.
- SERIALIZE all formal gate work: NEVER run `formal/gate.sh` or `formal/diff/mutate.py` concurrently with ANYTHING that imports `src` (including the bot). Run them foreground, alone. `git diff src` after every `mutate.py` run to confirm no poisoned predicate leaked.
- Pre-commit's fast pytest EXCLUDES `formal/diff/`; run `~/.local/bin/uv run pytest formal/diff/ -n auto --no-cov` explicitly.
- Python: imports at top of file; no inline imports; no `if TYPE_CHECKING`; never catch `Exception`; one behavioral class per file; use only API/game data or fail with an error (no defaulting).
- Test suite success criteria: 0 errors, 0 warnings, 0 skipped (in scope), 100% coverage; all tests in `tests/` (Python) or `formal/diff/` (differential).
- Honesty culture: no flattering proofs; every named hypothesis/boundary stated in the theorem docstring; a final theorem that still carries an assumed hypothesis is NOT a discharge. After each Lean task, grep the final theorem to confirm the targeted hypothesis binder is gone.
- Commit messages end with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Spec: `docs/superpowers/specs/2026-06-20-objectivestep-arming-liveness-design.md`.

---

### Task 1: Ground `WinnableAcrossBand` empirically — base stats + full-loadout sweep (C1)

Do this FIRST: it confirms `WinnableAcrossBand` is actually TRUE against live data before investing in the kernel proof. Low-risk, independent, ships the empirical grounding.

**FINDING (2026-06-20, mid-task) — `[[project_winnableacrossband_grounding]]`:** the existing sweep used `best_weapon_for_level` (weapon-only, deliberately conservative). That proxy CANNOT witness `WinnableAcrossBand` past L17 — an unarmored body (resistance 0) loses `predict_win` even to far-lower monsters. Two corrections, human-approved:
1. **Best full obtainable loadout, not weapon-only.** Model the best obtainable FULL loadout at level L (best item per slot with `item.level ≤ L`, via production `pick_loadout` over the obtainable catalog), since that is the bot's faithful capability. SOUND for the EXISTENCE claim MODULO gear-obtainability — which is exactly Task 3 (corner 3); this tightens the C1↔C0 coupling.
2. **Full projected HP.** The harness `_base_world_state` set `state.hp = base_max_hp + weapon.hp_bonus`, so with armor equipped the character fought at base+weapon HP (armor HP dropped via `effective_hp = min(state.hp, proj.max_hp)`). Set `state.hp` to the FULL projected max (rest-to-full, armor HP counted) — the bot rests before fighting. This was a real harness bug.
With BOTH corrections the sweep is clean 1..49 (verified: zero gaps). The base-stats capture (commits `a56887c`, `26c7a96`) is already DONE; the remaining Task-1 work is the loadout-model upgrade below.

**Files:**
- Run: `formal/sim/capture_base_stats.py` (exists; CLI `uv run python formal/sim/capture_base_stats.py <character> [output]`)
- Run: `formal/sim/snapshot_game_data.py` (re-snapshot so `item_stats` carry combat fields)
- Create (data, committed): `formal/sim/character_base_stats.json`
- Refresh (data, committed): `formal/sim/game_data_snapshot.json`
- Test: `formal/diff/test_winnable_across_band_diff.py::test_winnable_across_band_real_sweep` (exists; currently skips on missing `character_base_stats.json`)

**Interfaces:**
- Consumes: live API (TOKEN must be present in the worktree; see `[[reference_worktree_runtime_setup]]`).
- Produces: `formal/sim/character_base_stats.json` shape `{"base_stats": {"<level>": {max_hp, attack{fire,earth,water,air}, resistance{…}, critical_strike, initiative}}, …}`; a green (un-skipped) real-sweep test asserting no band gaps for levels 1..49.

- [ ] **Step 1: Confirm the sweep currently skips**

Run: `~/.local/bin/uv run pytest formal/diff/test_winnable_across_band_diff.py::test_winnable_across_band_real_sweep -v --no-cov`
Expected: SKIPPED ("character_base_stats.json absent …").

- [ ] **Step 2: Capture per-level base stats**

Run: `~/.local/bin/uv run python formal/sim/capture_base_stats.py Robby`
Expected: writes `formal/sim/character_base_stats.json` with one `base_stats["<level>"]` row per reachable level. The script is resumable (re-merges per level); re-run if it stops early. If the live character cannot exercise every level 1..49, capture what is reachable and record in the commit message which levels are present (the sweep classifies an absent level as `missing`, distinct from a `gap`).

- [ ] **Step 3: Re-snapshot game data (combat fields)**

Run: `~/.local/bin/uv run python formal/sim/snapshot_game_data.py`
Expected: refreshes `formal/sim/game_data_snapshot.json`; verify `item_stats` entries carry `attack`/`hp_bonus` fields (the sweep's `_snapshot_has_combat_fields` guard must pass).

- [ ] **Step 4: Run the real sweep**

Run: `~/.local/bin/uv run pytest formal/diff/test_winnable_across_band_diff.py::test_winnable_across_band_real_sweep -v --no-cov`
Expected: PASS (no `gaps`). If it reports gaps (a band level with NO winnable XP-positive not-overleveled monster under the best-weapon proxy), STOP — that is a real finding: `WinnableAcrossBand` is FALSE at that band for the captured character. Do not patch the test; report the gap (it falsifies the spec's central assumption and must be escalated to the human before any kernel proof).

- [ ] **Step 5: Commit**

```bash
git add formal/sim/character_base_stats.json formal/sim/game_data_snapshot.json
git commit -m "test(formal): ground WinnableAcrossBand from live data — capture base stats, un-skip real sweep

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Emit the live monster catalog + base stats into the Lean fixture (C1b-extract)

**Files:**
- Modify: `formal/sim/generate_lean_fixture.py` (`generate_lean()` ~line 65; recipe loop ~line 123; `return "\n".join(lines)` ~line 224)
- Regenerate (committed): `formal/Formal/Liveness/GameDataFixture.lean`
- Test: `formal/diff/test_game_data_fixture_diff.py` (exists; note `gate.sh` `--ignore`s it in the diff phase — run it explicitly here)

**Interfaces:**
- Consumes: `game_data_snapshot.json` keys `monster_level`/`monster_hp`/`monster_attack`/`monster_resistance`/`monster_critical_strike` (each a dict keyed by monster code); `character_base_stats.json` from Task 1.
- Produces, in `GameDataFixture.lean` (namespace `Formal.Liveness.GameDataFixture` — match the existing file's namespace):
  - `def monsterCatalog : List CatalogMonster` where `CatalogMonster` carries `code : String`, `level : Int`, `hp : Int`, `attackFire/Earth/Water/Air : Int`, `resFire/Earth/Water/Air : Int`, `crit : Int`.
  - `def baseStatsTable : List BaseStatsRow` (each row carries its own `level` field) where `BaseStatsRow` carries `level`, `maxHp`, `attack{4}`, `res{4}`, `crit`, `initiative`.
  - `def itemCatalog : List CatalogItem` — the combat-relevant equippable item stats (needed by Task 4's full-loadout kernel proof, per the full-loadout finding `[[project_winnableacrossband_grounding]]`). `CatalogItem` carries `code : String`, `level : Int`, `slotType : String` (the item `type`/subtype determining its equip slot), `attackFire/Earth/Water/Air : Int`, `hpBonus : Int`, `resFire/Earth/Water/Air : Int`, `crit : Int`. Emit from `snapshot["item_stats"]` (skip non-equippable items — those with no slot type). Mirror the production `ITEM_TYPE_TO_SLOTS` slot mapping so the Lean best-loadout matches production.
  - The `CatalogMonster`/`BaseStatsRow`/`CatalogItem` structures live in a NEW small core module `formal/Formal/Liveness/CatalogTypes.lean` (one cohesive group of plain data structs — allowed by the one-class rule), imported by `GameDataFixture.lean`.

- [ ] **Step 1: Write the failing fixture-diff assertion**

Add to `formal/diff/test_game_data_fixture_diff.py` a test asserting the emitted `monsterCatalog` length and one spot-checked monster match the snapshot:

```python
def test_monster_catalog_matches_snapshot() -> None:
    snapshot = json.loads((SIM_DIR / "game_data_snapshot.json").read_text())
    fixture = (FORMAL_DIR / "Formal" / "Liveness" / "GameDataFixture.lean").read_text()
    # every monster code in the snapshot appears as a monster_<safe> def
    for code in snapshot["monster_level"]:
        safe = "".join(c if c.isalnum() else "_" for c in code)
        assert f"def monster_{safe} : CatalogMonster" in fixture, code
    # spot-check one fully-specified monster
    assert 'code := "bandit_lizard"' in fixture
    assert "level := 25" in fixture
    # the item catalog is emitted with equippable items + a slotType
    assert "def itemCatalog : List CatalogItem" in fixture
    assert "slotType :=" in fixture
```

Also assert the `itemCatalog` includes a known weapon (e.g. `'code := "steel_battleaxe"'`) and excludes a non-equippable resource — verify against `ITEM_TYPE_TO_SLOTS` membership.

- [ ] **Step 2: Run to verify it fails**

Run: `~/.local/bin/uv run pytest formal/diff/test_game_data_fixture_diff.py::test_monster_catalog_matches_snapshot -v --no-cov`
Expected: FAIL (no `monster_<safe>` defs in the fixture yet).

- [ ] **Step 3: Create the catalog types core module**

Create `formal/Formal/Liveness/CatalogTypes.lean`:

```lean
namespace Formal.Liveness

structure CatalogMonster where
  code : String
  level : Int
  hp : Int
  attackFire : Int
  attackEarth : Int
  attackWater : Int
  attackAir : Int
  resFire : Int
  resEarth : Int
  resWater : Int
  resAir : Int
  crit : Int
deriving Repr, DecidableEq

structure BaseStatsRow where
  level : Int
  maxHp : Int
  attackFire : Int
  attackEarth : Int
  attackWater : Int
  attackAir : Int
  resFire : Int
  resEarth : Int
  resWater : Int
  resAir : Int
  crit : Int
  initiative : Int
deriving Repr, DecidableEq

structure CatalogItem where
  code : String
  level : Int
  slotType : String
  attackFire : Int
  attackEarth : Int
  attackWater : Int
  attackAir : Int
  hpBonus : Int
  resFire : Int
  resEarth : Int
  resWater : Int
  resAir : Int
  crit : Int
deriving Repr, DecidableEq

end Formal.Liveness
```

- [ ] **Step 4: Extend the generator to emit monsters + base stats**

In `formal/sim/generate_lean_fixture.py`, after the recipe block (before `return`), add a monster loop and a base-stats loop. Read `character_base_stats.json` alongside the snapshot. Emit, for each `code` in `sorted(snapshot["monster_level"])`:

```python
    base_stats_path = ROOT.parent / "sim" / "character_base_stats.json"  # adjust to actual ROOT
    base_doc = json.loads(base_stats_path.read_text())
    lines.append("")
    for code in sorted(snapshot["monster_level"]):
        safe = "".join(c if c.isalnum() else "_" for c in code)
        atk = snapshot["monster_attack"][code]
        res = snapshot["monster_resistance"][code]
        lines.append(f"def monster_{safe} : CatalogMonster :=")
        lines.append(f'  {{ code := "{escape_lean_string(code)}", level := {snapshot["monster_level"][code]}')
        lines.append(f'    hp := {snapshot["monster_hp"][code]}')
        lines.append(f'    attackFire := {atk["fire"]}, attackEarth := {atk["earth"]}, attackWater := {atk["water"]}, attackAir := {atk["air"]}')
        lines.append(f'    resFire := {res["fire"]}, resEarth := {res["earth"]}, resWater := {res["water"]}, resAir := {res["air"]}')
        lines.append(f'    crit := {snapshot["monster_critical_strike"][code]} }}')
        lines.append("")
    lines.append("def monsterCatalog : List CatalogMonster :=")
    lines.append("  [" + ", ".join(f"monster_{''.join(c if c.isalnum() else '_' for c in code)}" for code in sorted(snapshot["monster_level"])) + "]")
    lines.append("")
    # base stats rows
    for lvl in sorted(base_doc.get("base_stats", {}), key=int):
        row = base_doc["base_stats"][lvl]
        a, r = row["attack"], row["resistance"]
        lines.append(f"def baseStats_{lvl} : BaseStatsRow :=")
        lines.append(f'  {{ level := {lvl}, maxHp := {row["max_hp"]}')
        lines.append(f'    attackFire := {a["fire"]}, attackEarth := {a["earth"]}, attackWater := {a["water"]}, attackAir := {a["air"]}')
        lines.append(f'    resFire := {r["fire"]}, resEarth := {r["earth"]}, resWater := {r["water"]}, resAir := {r["air"]}')
        lines.append(f'    crit := {row["critical_strike"]}, initiative := {row["initiative"]} }}')
        lines.append("")
    lines.append("def baseStatsTable : List BaseStatsRow :=")
    lines.append("  [" + ", ".join(f"baseStats_{lvl}" for lvl in sorted(base_doc.get('base_stats', {}), key=int)) + "]")
```

Then add an item loop emitting `itemCatalog`: for each equippable `code, s` in `sorted(snapshot["item_stats"].items())` whose `s["type"]` (or subtype) maps to an equip slot in the production `ITEM_TYPE_TO_SLOTS` (import/mirror that mapping; SKIP items with no equip slot), emit `def item_{safe} : CatalogItem := { code, level := s["level"], slotType := "<type>", attackFire/Earth/Water/Air := s["attack"][e] (0 if absent), hpBonus := s["hp_bonus"], resFire/.../resAir := s["resistance"][e], crit := s["critical_strike"] }`, then `def itemCatalog : List CatalogItem := [ … ]`. Pull the per-element attack/resistance from the snapshot's `item_stats` dict fields (default 0 when an element is absent — that is the game's real value, not a fabricated default).

Add `import Formal.Liveness.CatalogTypes` and `open Formal.Liveness` to the fixture header the generator emits.

- [ ] **Step 5: Regenerate the fixture and build**

Run: `~/.local/bin/uv run python formal/sim/generate_lean_fixture.py`
Then: `cd formal && lake build Formal.Liveness.GameDataFixture`
Expected: build OK; `GameDataFixture.lean` now contains `monsterCatalog` + `baseStatsTable`.

- [ ] **Step 6: Run the fixture-diff test**

Run: `~/.local/bin/uv run pytest formal/diff/test_game_data_fixture_diff.py -v --no-cov`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add formal/sim/generate_lean_fixture.py formal/Formal/Liveness/CatalogTypes.lean formal/Formal/Liveness/GameDataFixture.lean formal/diff/test_game_data_fixture_diff.py
git commit -m "feat(formal): emit live monster catalog + base stats into GameDataFixture

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Close corner 3 for the no-surplus gear-obtainment class (C0)

The research-grade task. `corner3` is currently an assumed binder in `minGathers_le_gathers_of_corner3` (`PlanModel.lean:3352`): `∀ c G, … minGathersCount item 1 recipes G ≤ minGathersCount item 1 recipes (afterCraft c G)`. Discharge it by introducing a `NoSurplusPlan` invariant under which every craft in the plan is on-path (its output is consumed downstream), making the per-craft monotonicity provable, and thread it through the existing induction so the final theorem carries NO `corner3` binder. CORE-ONLY (PlanModel is a safety module).

**The structural basis (why no-surplus is FORCED, not assumed) — `[[project_gear_demand_economy]]`:** the equipment economy makes every craft in a gear-obtainment plan on-path:
- recipes are **monotone** (ingredient→output non-decreasing toward the target on the cost/mass ladder — already captured by `wf_weight_rec` cost-neutrality + `costMass_mono_dom` in this file);
- equippable gear demand is **per-slot exactly 1, exactly 2 for rings** (consumables excluded);
- **strict per-slot tier dominance** — a superseding tier retires the lower, which is never re-demanded;
- this hierarchy is **invariant** under events/tasks/grand-exchange.
So `NoSurplusPlan` is the proof encoding of a structural truth, not a convenient restriction. Define gear demand from the slot cap (1, rings 2) and prove the per-craft on-path obligation from tier-dominance + monotone recipe. The production-side shadow of the same invariant is the dup-free-EXCEPT-rings per-slot ownership cap (`[[project_dual_ring_carveout]]` / `RealizableLoadout`) — reuse its slot/ring distinction so the model and production agree on demand-2-for-rings.

**Files:**
- Modify: `formal/Formal/PlanModel.lean` (add `NoSurplusPlan`, the per-craft monotonicity lemma, `minGathers_le_gathers_nosurplus`, `canonicalPlan` + obtainability)
- Build: `cd formal && lake build Formal.PlanModel`

**Interfaces:**
- Consumes: existing `Action`, `Plan`, `ValidPlan`, `ValidCraftAt`, `Reaches`, `planHoldings`, `planGathers`, `minGathersCount`, `runPlan`, `applyAction`, `costMass` from `PlanModel.lean`/`StepDispatch.lean`.
- Produces:
  - `def NoSurplusPlan (recipes) (owned) (plan) : Prop` — every `Action.craft c` in `plan` produces output that is consumed by a later action or remains as exactly the demanded final quantity (no strictly-surplus craft). Concretely: for the suffix after each craft, the crafted unit is required by the remaining plan's net demand for the target. Per-slot demand cap = 1, EXCEPT rings = 2 (match `[[project_dual_ring_carveout]]`); the equip target's slot determines the cap.
  - `theorem craft_monotone_of_onpath` — the per-craft `corner3` obligation, proved from the no-surplus invariant for the specific `c` crafted.
  - `theorem minGathers_le_gathers_nosurplus (recipes) (rank) (… same domain hyps as corner3 version …) (item owned plan) (hns : NoSurplusPlan recipes owned plan) (hv : ValidPlan recipes owned plan) (hprod : 1 ≤ getD (planHoldings recipes plan owned) item 0) : minGathersCount item 1 recipes owned ≤ (planGathers recipes plan owned : Int)` — NO `corner3` binder.
  - `def canonicalPlan (recipes) (item) (owned) : Plan` — bottom-up: gather raw leaves, craft the closure in rank order, equip `item`.
  - `theorem canonicalPlan_valid` : `ValidPlan recipes owned (canonicalPlan recipes item owned)` and `NoSurplusPlan …` and `SatisfiesEquip (canonicalPlan …) item owned recipes`.
  - `theorem canonicalPlan_gathers` : `planGathers recipes (canonicalPlan recipes item owned) owned = (minGathersCount item 1 recipes owned).toNat` (the witness achieves the lower bound).
  - `theorem gear_obtainable_of_minPlanLength_le` : a length bound `(canonicalPlan …).length ≤ d` follows when `minPlanLength` (mints+crafts+equip) `≤ d`, giving EXISTENCE of an obtaining+equipping valid plan within depth.

- [ ] **Step 1: State `NoSurplusPlan` + the no-surplus lower-bound theorem with `sorry`**

In `PlanModel.lean`, add the `NoSurplusPlan` def and:

```lean
theorem minGathers_le_gathers_nosurplus (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank)
    (hRB : ∀ item, rank item ≤ recipes.length) (hrnd : RecipeNoDup recipes)
    (item : String) (owned : Dict Int) (plan : Plan)
    (hnn : NonNeg owned) (he : EntriesNonNeg owned) (hnd : NoDupKeys owned)
    (hns : NoSurplusPlan recipes owned plan)
    (hv : ValidPlan recipes owned plan)
    (hprod : 1 ≤ getD (planHoldings recipes plan owned) item 0) :
    minGathersCount item 1 recipes owned ≤ (planGathers recipes plan owned : Int) := by
  sorry
```

- [ ] **Step 2: Build to confirm it elaborates (with sorry)**

Run: `cd formal && lake build Formal.PlanModel 2>&1 | tail -20`
Expected: builds with a `sorry` warning on the new theorem; no elaboration errors (the statement type-checks).

- [ ] **Step 3: Prove `craft_monotone_of_onpath` (the corner3 obligation, per-craft)**

Develop the lemma: for a craft `c` that is on-path under `NoSurplusPlan` (consumed downstream), `minGathersCount item 1 recipes G ≤ minGathersCount item 1 recipes (applyAction … (Action.craft c)).holdings`. Use the lean4:proof-repair / lean4:sorry-filler-deep subagent with the goal state. Strategy: crafting `c` consumes `c`'s recipe inputs and adds one `c`; because `c` is consumed downstream, the produced `c` offsets exactly one unit of `item`'s residual demand routed through `c`, and the consumed inputs were already counted in `minGathersCount` — so the count is non-increasing. Reuse the existing `wf_weight_rec` cost-neutrality and `minGathers_agree` off-path invariance lemmas (already 0-sorry in this file). CORE-ONLY tactics.

- [ ] **Step 4: Discharge the `sorry` in `minGathers_le_gathers_nosurplus`**

Thread `craft_monotone_of_onpath` through the same induction structure used by `minGathers_le_gathers_of_corner3`, supplying the per-craft obligation from `hns` instead of the universal `corner3` binder. Iterate with the proof-repair subagent until 0-sorry.

- [ ] **Step 5: Verify no `corner3` binder remains**

Run: `cd formal && lake build Formal.PlanModel` then `grep -n "corner3" formal/Formal/PlanModel.lean`
Expected: `minGathers_le_gathers_nosurplus` does NOT mention `corner3`; the only `corner3` occurrences are in the OLD `*_of_corner3` theorems (left intact as the general-DAG banked version) and `star_of_corner3`. Confirm the new theorem's signature is corner3-free.

- [ ] **Step 6: Construct `canonicalPlan` + obtainability witness with `sorry`s, then prove**

Add `canonicalPlan`, `canonicalPlan_valid`, `canonicalPlan_gathers`, `gear_obtainable_of_minPlanLength_le` (statements first with `sorry`, build, then develop proofs via subagent). `canonicalPlan` is a structural recursion over the recipe closure in `rank` order; its validity and no-surplus property are constructive; `canonicalPlan_gathers` matches the witness gather count to `minGathersCount` by the same mass-conservation identity (`minGathers_recon`, already proven).

- [ ] **Step 7: Full module build, 0-sorry check, docstrings**

Run: `cd formal && lake build Formal.PlanModel && bash gate/check_no_sorry.sh`
Expected: 0 sorry. Add a docstring to each new theorem stating the no-surplus / demand-1 gear-obtainment boundary explicitly ("not the general arbitrary-surplus DAG lower bound").

- [ ] **Step 8: Commit**

```bash
git add formal/Formal/PlanModel.lean
git commit -m "feat(formal): discharge corner3 for no-surplus gear-obtainment class + canonical obtainability witness

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

> If Step 3 or 4 hits the SAME wall as the general corner 3 (the no-surplus restriction fails to make the per-craft obligation provable), STOP after 3 proof attempts and escalate to the human per systematic-debugging Phase 4.5 — do not assume a fresh binder. The no-surplus restriction is the hypothesis under test, not a guarantee.

---

### Task 4: Kernel-prove `WinnableAcrossBand` over the extracted catalog (C1b-proof)

**Files:**
- Create: `formal/Formal/Liveness/WinnableGrounded.lean`
- Build: `cd formal && lake build Formal.Liveness.WinnableGrounded`

**Interfaces:**
- Consumes: `monsterCatalog`, `baseStatsTable` (Task 2); `predictWin`, `predict_win_mono_player` (`PredictWin.lean`); `Monster`, `WinnableFn`, `notOverleveled`, `WinnableAcrossBand`, `InLevelingBand` (Task §4 anchors); `gear_obtainable_of_minPlanLength_le` (Task 3, for the obtainability note on `bestWeaponForLevel`).
- Produces:
  - `def catalogAsMonsters : List Monster` — project `monsterCatalog` to the `Monster` (code, level) shape used by `WinnableAcrossBand` (encode `code : String` to the `Int` field via a stable index, or extend the bridge to carry the full `CatalogMonster`; keep the `WinnableAcrossBand` signature).
  - `def bestWeaponForLevel (L : Int) : ItemStatsScalars` — mirrors production `best_weapon_for_level` over the extracted item stats (max-attack weapon with `item.level ≤ L`).
  - `def playerScalarsAtLevel (L : Int) : PlayerScalars` — `baseStatsTable` row for `L` reduced to `predictWin`'s scalar inputs, plus `bestWeaponForLevel L`.
  - `def winnableConcrete : WinnableFn` and `def xpPosConcrete : WinnableFn` — `winnableConcrete m = predictWin (playerScalarsAtLevel …) (monster scalars of m) …` and `xpPosConcrete m = decide (xpPerKillModel m L > 0)`.
  - `theorem winnableAcrossBand_grounded : WinnableAcrossBand winnableConcrete xpPosConcrete catalogAsMonsters` — kernel-checked.

- [ ] **Step 1: State `winnableAcrossBand_grounded` with `sorry`, build**

Create `WinnableGrounded.lean` with the defs above (bodies may start minimal) and the theorem ending in `sorry`. Build: `cd formal && lake build Formal.Liveness.WinnableGrounded` — confirm it type-checks.

- [ ] **Step 2: Implement the per-level stat reduction**

Implement `playerScalarsAtLevel` and the monster-scalar projection so they feed `predictWin` exactly as production's `project_loadout_stats` → `predict_win` does. Cross-check ONE level against production by a differential (add to Task 6's diff or a focused assertion): `predictWin (playerScalarsAtLevel L) (scalars of m)` equals production `predict_win` for a sampled `(L, m)`.

- [ ] **Step 3: Prove `winnableAcrossBand_grounded` by `decide` over band × catalog**

`WinnableAcrossBand` unfolds to `∀ L, InLevelingBand L → ∃ m ∈ catalog, …`. The band is `1 ≤ L < 50` (49 values); the catalog is finite (48). Convert the bounded `∀ L` to a `List.all` over `[1..49]` and `decide`/`native_decide` the finite check. If `native_decide` is needed for performance, isolate it and add the per-use justification for `gate/check_axioms.sh`. Use the lean4:proof-repair subagent for the conversion lemmas (bounded-∀ ↔ list-all).

- [ ] **Step 4: 0-sorry + axiom gate**

Run: `cd formal && lake build Formal.Liveness.WinnableGrounded && bash gate/check_no_sorry.sh && bash gate/check_axioms.sh`
Expected: 0 sorry; axiom check passes (only signed-off classical/LIV-001 + any justified `native_decide`). Docstring states the conservative best-weapon-proxy boundary and cites Task 3's obtainability for `bestWeaponForLevel`.

- [ ] **Step 5: Commit**

```bash
git add formal/Formal/Liveness/WinnableGrounded.lean
git commit -m "feat(formal): kernel-prove WinnableAcrossBand over the extracted catalog

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Discharge the `perceptionRefresh` arming (C2)

Replace the asserted `objectiveStepFires/IsFight := true` with a proof from combat-target-existence (Task 4) + structural fight-plannability + a production differential pinning `objective_step_goal(ReachCharLevel) → fight`.

**Files:**
- Modify: `formal/Formal/Liveness/PerceptionRefresh.lean`
- Create: `formal/diff/test_objectivestep_arming_diff.py`
- Reference (production, unchanged): `src/artifactsmmo_cli/ai/strategy_driver.py:583-617`

**Interfaces:**
- Consumes: `winnableAcrossBand_grounded` (Task 4) → `combatObjective_live_below_fifty` (`GearTierLeveling.lean:84`); the `State` fields `objectiveStepFires`/`objectiveStepIsFight` (`Measure.lean:153/169`); production `objective_step_goal` / `GrindCharacterXPGoal` (`strategy_driver.py`).
- Produces:
  - In `PerceptionRefresh.lean`: an `armed_of_below_fifty` lemma showing the arming is JUSTIFIED — `s.level < 50 → ∃ target, pickWinnableWindowed s.level winnableConcrete xpPosConcrete catalogAsMonsters = some target ∧ (perceptionRefresh s).objectiveStepIsFight = true`. The `perceptionRefresh` def keeps setting the Bools, but the new lemma proves the set value is BACKED by an existing winnable target (no longer a free assertion); the existing `perceptionRefresh_objectiveStepIsFight` is restated to consume this justification.
  - `formal/diff/test_objectivestep_arming_diff.py::test_objectivestep_arming_matches_production` — for sampled below-50 states with a winnable target, production `objective_step_goal` returns a `GrindCharacterXPGoal` (fight), matching the Lean `objectiveStepIsFight = true` arming. Template: `test_ladder_fires_diff.py` (`_production_answers`/`_lean_answers`, assert agreement).

- [ ] **Step 1: Write the failing production differential**

Create `formal/diff/test_objectivestep_arming_diff.py` modeled on `test_ladder_fires_diff.py`:

```python
@given(scn=arming_scenarios())
def test_objectivestep_arming_matches_production(scn) -> None:
    ctx, state, game_data = _build(scn)
    goal = objective_step_goal(...)  # ReachCharLevel step, combat_monster set, level < 50
    produced_fight = isinstance(goal, GrindCharacterXPGoal)
    lean_armed = scn.level < 50 and scn.winnable_target_exists
    assert produced_fight == lean_armed, (scn, goal)
```

Run: `~/.local/bin/uv run pytest formal/diff/test_objectivestep_arming_diff.py -v --no-cov`
Expected: FAIL (file/test new; or assertion gaps to resolve against production semantics — encode the `bootstrap_gap > 4 ∧ items-task-active` defer branch from `strategy_driver.py:600` into `lean_armed` so the binding is faithful, not flattering).

- [ ] **Step 2: Make the differential green against real production semantics**

Adjust the scenario generator + `lean_armed` to exactly mirror `strategy_driver.py`'s branch (return `None` when `combat_monster is None`, or when long-haul items-task defer; else `GrindCharacterXPGoal`). The test must pin production, not be rigged — include scenarios that hit BOTH the fire and the defer paths.

Run: `~/.local/bin/uv run pytest formal/diff/test_objectivestep_arming_diff.py -v --no-cov`
Expected: PASS.

- [ ] **Step 3: Add `armed_of_below_fifty` to `PerceptionRefresh.lean`, prove**

State the lemma binding the arming to `combatObjective_live_below_fifty winnableConcrete xpPosConcrete catalogAsMonsters winnableAcrossBand_grounded`. Prove with the proof-repair subagent. Keep the module's existing theorems green.

- [ ] **Step 4: Build + 0-sorry + axiom gate**

Run: `cd formal && lake build Formal.Liveness.PerceptionRefresh && bash gate/check_no_sorry.sh && bash gate/check_axioms.sh`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add formal/Formal/Liveness/PerceptionRefresh.lean formal/diff/test_objectivestep_arming_diff.py
git commit -m "feat(formal): discharge perceptionRefresh arming from grounded combat-target existence + production diff

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Re-prove the reach-50 capstone with `FightsBelowCap` discharged (C3)

**Files:**
- Modify: `formal/Formal/Liveness/LevelingDescent.lean` (or a new `formal/Formal/Liveness/ReachFiftyGrounded.lean` that consumes it)
- Build: `cd formal && lake build Formal.Liveness.LevelingDescent`

**Interfaces:**
- Consumes: `cycleStepF_reaches_fifty_of_fights` (`LevelingDescent.lean:114`), `FightsBelowCap` (`:103`), `armed_of_below_fifty` (Task 5), `winnableAcrossBand_grounded` (Task 4).
- Produces:
  - `theorem fightsBelowCap_of_grounded (s : State) (… the residual hyps: blockers-quiet, LIV-001, runtime invariants …) : FightsBelowCap s` — `FightsBelowCap` now a RESULT from the grounded arming, NOT an assertion, modulo the explicitly-named residuals.
  - `theorem ai_reaches_fifty_grounded (s : State) (… residual hyps …) : ∃ k, (cycleStepFN k s).level ≥ 50` — the capstone on the discharged arming.

- [ ] **Step 1: State `fightsBelowCap_of_grounded` with `sorry`, enumerating residual hyps explicitly**

The `FightsBelowCap` disjunction (`:103`) requires, at each below-50 `cycleStepFN k s`, that `productionLadder (perceptionRefresh …)` selects `bankUnlock`/`reachUnlockLevel`/`objectiveStep ∧ objectiveStepIsFight`. The arming (Task 5) gives `objectiveStepIsFight = true`; the SELECTION of `objectiveStep` over chores is the *blockers-quiet* residual. State it as a named hypothesis `(hquiet : ∀ k, (cycleStepFN k s).level < 50 → objectiveStepSelected (perceptionRefresh (cycleStepFN k s)))`. Do NOT silently assume it — name it in the signature and docstring.

- [ ] **Step 2: Build (with sorry)**

Run: `cd formal && lake build Formal.Liveness.LevelingDescent 2>&1 | tail -20`
Expected: type-checks with sorry.

- [ ] **Step 3: Prove `fightsBelowCap_of_grounded` and `ai_reaches_fifty_grounded`**

Thread `armed_of_below_fifty` (arming = true) + `hquiet` (selection) into the `FightsBelowCap` disjunction's third branch, then apply `cycleStepF_reaches_fifty_of_fights`. Use the proof-repair subagent. The remaining hypotheses are exactly {blockers-quiet `hquiet`, LIV-001, positive-capacity/runtime invariants} — confirm nothing else is assumed.

- [ ] **Step 4: 0-sorry + axiom gate + confirm the discharge**

Run: `cd formal && lake build Formal.Liveness.LevelingDescent && bash gate/check_no_sorry.sh && bash gate/check_axioms.sh`
Then grep the capstone: confirm `objectiveStepIsFight := true` is no longer a free assertion feeding it — the arming arrives via `armed_of_below_fifty`. Docstring lists the residuals {blockers-quiet, LIV-001}.

- [ ] **Step 5: Commit**

```bash
git add formal/Formal/Liveness/LevelingDescent.lean
git commit -m "feat(formal): re-prove reach-50 capstone with FightsBelowCap discharged (modulo blockers-quiet, LIV-001)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Full gate, mutation anchors, memory update

**Files:**
- Run: `formal/gate.sh`, `formal/diff/mutate.py`
- Modify (if mutation surfaces stale anchors after the PlanModel/Liveness edits): `formal/diff/mutate.py`
- Update: `/home/blentz/.claude/projects/-home-blentz-git-artifactsmmo/memory/` (`project_plannability_soundness.md`, the level-50 residual memories) + `MEMORY.md`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: a fully-green `gate.sh`; refreshed mutation anchors covering the new theorems; updated memory recording corner-3-closed-for-gear-class + arming-discharged + residuals.

- [ ] **Step 1: Refresh mutation anchors (PlanModel + Liveness edits move them)**

Run (FOREGROUND, ALONE — no bot/src import concurrent): `cd /home/blentz/git/artifactsmmo && ~/.local/bin/uv run python formal/diff/mutate.py`
Then: `git diff src` — confirm NO src mutation leaked. If anchors are stale (new theorems unanchored), update `mutate.py` to add mutants that the new differentials kill (e.g. weaken `minGathers_le_gathers_nosurplus`'s no-surplus guard; flip the arming bind).

- [ ] **Step 2: Run the full gate FOREGROUND, ALONE**

Run: `cd /home/blentz/git/artifactsmmo/formal && bash gate.sh 2>&1 | tee /tmp/gate.log`
Expected: ALL GATE PARTS PASSED — (a) kernel build, (a'/a'') no-orphan/no-sorry, (b) axiom lint, (b'..b''') manifest/proof-concept/extraction, (d) differential (incl. the new diffs), (c) mutation all-killed. If the proof-concept index is stale, regenerate it. If a part fails, fix in place; never background the gate.

- [ ] **Step 3: Full Python suite**

Run: `cd /home/blentz/git/artifactsmmo && ~/.local/bin/uv run pytest -q` then `~/.local/bin/uv run pytest formal/diff/ -n auto --no-cov`
Expected: 100% coverage, 0 failures, 0 skipped (the WinnableAcrossBand real sweep now runs, not skips).

- [ ] **Step 4: Update memory**

Update `project_plannability_soundness.md` (corner 3 now CLOSED for the no-surplus gear class; general DAG bound remains banked), `project_level_fifty_residual_perimeter.md` / `project_faithfulness_modeling.md` (arming discharged; residuals = {blockers-quiet, LIV-001}), and add a `MEMORY.md` line pointer. Convert any relative dates to absolute (2026-06-20).

- [ ] **Step 5: Commit**

```bash
git add formal/diff/mutate.py
git commit -m "test(formal): refresh mutation anchors for gear-class corner3 + arming discharge

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Notes on formal-task execution

- Lean proof tasks do NOT fit the literal "write failing test → minimal impl → pass" loop. The adapted cycle per theorem: (1) state it ending in `sorry`; (2) `lake build` to confirm the STATEMENT type-checks; (3) develop the proof body with the `lean4:proof-repair` / `lean4:sorry-filler-deep` subagents against the live goal state; (4) `lake build` + `check_no_sorry.sh` to confirm 0-sorry; (5) `check_axioms.sh`. The "failing test" is the `sorry`-bearing build; "passing" is 0-sorry.
- Tasks 1 and 2 are mechanical (cheap model). Task 5 (production diff) and Task 6 are integration (standard model). Tasks 3 and 4 are the hard proofs (most capable model + proof-repair subagents).
- Hard dependency order: Task 1 → 2 → {3, 4 partially parallel: 4 needs 2; 4's obtainability note needs 3} → 5 (needs 4) → 6 (needs 5) → 7. Task 3 may proceed in parallel with Task 4's stat-model scaffolding but Task 4's final docstring cites Task 3.
