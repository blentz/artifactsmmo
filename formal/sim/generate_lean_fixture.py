"""Generate Formal/Liveness/GameDataFixture.lean from the snapshot JSON.

Reads `formal/sim/game_data_snapshot.json` (captured by
`snapshot_game_data.py`) and emits a Lean module pinning the live
game-data recipes, monster stats, etc.

The fixture computes recipe `craftDepth` by topological sort over the
ingredient DAG (production game-data guarantees acyclicity by
construction). Items not in `crafting_recipes` are leaves (depth 0).

Output: Formal/Liveness/GameDataFixture.lean (overwrite mock fixture).

Run from the repo root as a module so the `formal` package resolves:

    uv run python -m formal.sim.generate_lean_fixture
"""

import json
from collections import defaultdict, deque
from pathlib import Path

from formal.sim.winnable_witness import (
    WitnessRow,
    build_witness_table,
    game_data_from_snapshot,
    item_stats_from_snapshot,
)

# Mirror of production ITEM_TYPE_TO_SLOTS (derived from CharacterSchema).
# Only item types listed here are equippable; all others (resource, consumable,
# currency, …) are skipped in the itemCatalog emission.
_EQUIPPABLE_TYPES: frozenset[str] = frozenset({
    "weapon", "rune", "shield", "helmet", "body_armor", "leg_armor",
    "boots", "ring", "amulet", "artifact", "utility", "bag",
})

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "sim" / "game_data_snapshot.json"
OUTPUT = ROOT / "Formal" / "Liveness" / "GameDataFixture.lean"


def compute_depths(recipes: dict[str, dict[str, int]]) -> dict[str, int]:
    """Topological sort over ingredient DAG. Returns code -> craft depth.
    Leaves (no recipe) get depth 0; crafts get max(ingredient depths) + 1."""
    depth: dict[str, int] = {}
    all_codes: set[str] = set(recipes.keys())
    for ingredients in recipes.values():
        all_codes.update(ingredients.keys())

    # Items without recipes are leaves.
    for code in all_codes:
        if code not in recipes:
            depth[code] = 0

    # Iterate until fixed point (acyclic ⇒ terminates in ≤ depth iterations).
    changed = True
    iterations = 0
    while changed and iterations < 50:
        changed = False
        iterations += 1
        for code, ingredients in recipes.items():
            if code in depth:
                continue
            if all(ing in depth for ing in ingredients):
                depth[code] = max(depth[ing] for ing in ingredients) + 1
                changed = True

    # Any code still missing means we hit a cycle (shouldn't happen) or
    # max iterations. Default to a depth above all known depths.
    if recipes:
        max_known = max(depth.values()) if depth else 0
        for code in recipes:
            if code not in depth:
                depth[code] = max_known + 1
                print(f"WARN: {code} depth defaulted (cycle or deep chain)")

    return depth


def escape_lean_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _safe(code: str) -> str:
    """Lean-safe identifier: replace non-alnum chars with '_'."""
    return "".join(c if c.isalnum() else "_" for c in code)


def _emit_monster_catalog(lines: list[str], snapshot: dict) -> None:
    """Emit per-monster defs and monsterCatalog list into lines."""
    lines.append("/-! ## Live monster catalog (sorted by code) -/")
    lines.append("")
    for code in sorted(snapshot["monster_level"]):
        safe = _safe(code)
        atk = snapshot["monster_attack"][code]
        res = snapshot["monster_resistance"][code]
        lines.append(f"def monster_{safe} : CatalogMonster :=")
        lines.append(f'  {{ code := "{escape_lean_string(code)}", level := {snapshot["monster_level"][code]}')
        lines.append(f'    hp := {snapshot["monster_hp"][code]}')
        lines.append(f'    attackFire := {atk.get("fire", 0)}, attackEarth := {atk.get("earth", 0)}, attackWater := {atk.get("water", 0)}, attackAir := {atk.get("air", 0)}')
        lines.append(f'    resFire := {res.get("fire", 0)}, resEarth := {res.get("earth", 0)}, resWater := {res.get("water", 0)}, resAir := {res.get("air", 0)}')
        lines.append(f'    crit := {snapshot["monster_critical_strike"][code]} }}')
        lines.append("")
    lines.append("def monsterCatalog : List CatalogMonster :=")
    lines.append("  [" + ", ".join(f"monster_{_safe(code)}" for code in sorted(snapshot["monster_level"])) + "]")
    lines.append("")


def _emit_base_stats_table(lines: list[str], base_doc: dict) -> None:
    """Emit per-level base-stats defs and baseStatsTable list into lines."""
    lines.append("/-! ## Character base stats by level (1..49) -/")
    lines.append("")
    sorted_levels = sorted(base_doc.get("base_stats", {}), key=int)
    for lvl in sorted_levels:
        row = base_doc["base_stats"][lvl]
        a = row["attack"]
        r = row["resistance"]
        lines.append(f"def baseStats_{lvl} : BaseStatsRow :=")
        lines.append(f'  {{ level := {lvl}, maxHp := {row["max_hp"]}')
        lines.append(f'    attackFire := {a.get("fire", 0)}, attackEarth := {a.get("earth", 0)}, attackWater := {a.get("water", 0)}, attackAir := {a.get("air", 0)}')
        lines.append(f'    resFire := {r.get("fire", 0)}, resEarth := {r.get("earth", 0)}, resWater := {r.get("water", 0)}, resAir := {r.get("air", 0)}')
        lines.append(f'    crit := {row["critical_strike"]}, initiative := {row["initiative"]} }}')
        lines.append("")
    lines.append("def baseStatsTable : List BaseStatsRow :=")
    lines.append("  [" + ", ".join(f"baseStats_{lvl}" for lvl in sorted_levels) + "]")
    lines.append("")


def _emit_item_catalog(lines: list[str], snapshot: dict) -> None:
    """Emit per-item defs and itemCatalog list for equippable items only."""
    lines.append("/-! ## Equippable item catalog (sorted by code) -/")
    lines.append("")
    equippable = sorted(
        (code, s) for code, s in snapshot["item_stats"].items()
        if s["type"] in _EQUIPPABLE_TYPES
    )
    for code, s in equippable:
        safe = _safe(code)
        atk = s.get("attack") or {}
        res = s.get("resistance") or {}
        lines.append(f"def item_{safe} : CatalogItem :=")
        lines.append(f'  {{ code := "{escape_lean_string(code)}", level := {s["level"]}, slotType := "{escape_lean_string(s["type"])}"')
        lines.append(f'    attackFire := {atk.get("fire", 0)}, attackEarth := {atk.get("earth", 0)}, attackWater := {atk.get("water", 0)}, attackAir := {atk.get("air", 0)}')
        lines.append(f'    hpBonus := {s.get("hp_bonus", 0)}')
        lines.append(f'    resFire := {res.get("fire", 0)}, resEarth := {res.get("earth", 0)}, resWater := {res.get("water", 0)}, resAir := {res.get("air", 0)}')
        lines.append(f'    crit := {s.get("critical_strike", 0)} }}')
        lines.append("")
    lines.append("def itemCatalog : List CatalogItem :=")
    lines.append("  [" + ", ".join(f"item_{_safe(code)}" for code, _ in equippable) + "]")
    lines.append("")


def _emit_witness_table(lines: list[str], rows: list[WitnessRow]) -> None:
    """Emit `winnableWitness : List WitnessRow` — one verified row per band level.

    The rows are produced by `formal.sim.winnable_witness.build_witness_table`
    (the real production sweep) and differential-pinned by
    `formal/diff/test_winnable_witness_diff.py`. Consumed by the kernel proof
    `Formal/Liveness/WinnableGrounded.lean`."""
    lines.append("/-! ## WinnableAcrossBand witness table (one row per band level 1..49)")
    lines.append("")
    lines.append("  Each row: the winning monster + `pick_loadout` loadout + the")
    lines.append("  production-projected `predictWin` scalars at that level. The")
    lines.append("  projection's fidelity is pinned by")
    lines.append("  `formal/diff/test_winnable_witness_diff.py`. -/")
    lines.append("")
    lines.append("def winnableWitness : List WitnessRow :=")
    lines.append("  [")
    row_strs: list[str] = []
    for r in rows:
        codes = ", ".join(f'"{escape_lean_string(c)}"' for c in r.loadout_codes)
        first = "true" if r.player_first else "false"
        row_strs.append(
            "    { level := " + str(r.level)
            + f', monsterCode := "{escape_lean_string(r.monster_code)}"'
            + f", monsterLevel := {r.monster_level}\n"
            + f"      loadoutCodes := [{codes}]\n"
            + f"      pCrit := {r.p_crit}, pMaxHp := {r.p_max_hp}, pInitiative := {r.p_initiative}\n"
            + f"      pAtkSum := {r.p_atk_sum}, pLifesteal := {r.p_lifesteal}, pAntipoison := {r.p_antipoison}\n"
            + f"      rawPlayer := {r.raw_player}, monsterHp := {r.monster_hp}, rawMonster := {r.raw_monster}\n"
            + f"      mCrit := {r.m_crit}, mAtkSum := {r.m_atk_sum}, mLifesteal := {r.m_lifesteal}\n"
            + f"      mPoison := {r.m_poison}, mBarrier := {r.m_barrier}, mBurn := {r.m_burn}\n"
            + f"      mHealing := {r.m_healing}, mReconstitution := {r.m_reconstitution}, mVoidDrain := {r.m_void_drain}\n"
            + f"      mBerserk := {r.m_berserk}, mFrenzy := {r.m_frenzy}, mBubble := {r.m_bubble}\n"
            + f"      playerFirst := {first} }}"
        )
    lines.append(",\n".join(row_strs))
    lines.append("  ]")
    lines.append("")


def generate_lean(snapshot: dict) -> str:
    recipes = snapshot["crafting_recipes"]
    depths = compute_depths(recipes)

    sorted_recipes = sorted(recipes.items())

    lines = [
        "import Formal.Liveness.CatalogTypes",
        "import Formal.Liveness.RecipeChainClosure",
        "import Formal.Liveness.SkillGapClosure",
        "import Formal.Liveness.TaskCompleteReachable",
        "import Formal.Liveness.Measure",
        "import Formal.Liveness.TaskLifecyclePhase",
        "import Mathlib.Tactic",
        "",
        "/-! # GameDataFixture — Phase 24 LIVE SNAPSHOT",
        "",
        f"  Captured: {snapshot['captured_at']}",
        f"  API: {snapshot['api_base_url']}",
        f"  Counts: {len(snapshot['monster_level'])} monsters, "
        f"{len(snapshot['item_stats'])} items, "
        f"{len(snapshot['crafting_recipes'])} recipes, "
        f"{len(snapshot['resource_skill'])} resources.",
        "",
        "  Generated from formal/sim/game_data_snapshot.json by",
        "  formal/sim/generate_lean_fixture.py. Regenerate after",
        "  snapshot_game_data.py captures a new snapshot.",
        "",
        "  Recipe `craftDepth` field computed by topological sort over",
        "  ingredient DAG (production game-data guarantees acyclicity).",
        "  Leaves (no crafting_recipes entry) get depth 0; crafts get",
        "  max(ingredient depths) + 1.",
        "",
        "  This fixture instantiates Phase 23d-8's universal",
        "  recipe_then_complete_reachable theorem against LIVE data.",
        "  NO new axioms; pure structural data + instantiation. -/",
        "",
        "set_option maxRecDepth 8192",
        "",
        "namespace Formal.Liveness.GameDataFixture",
        "",
        "open Formal.Liveness",
        "open Formal.Liveness.Plan",
        "open Formal.Liveness.PlanAction",
        "open Formal.Liveness.Measure",
        "open Formal.Liveness.TaskLifecyclePhase",
        "open Formal.Liveness.TaskCompleteReachable",
        "open Formal.Liveness.SkillGapClosure",
        "open Formal.Liveness.RecipeChainClosure",
        "",
        f"/-- Snapshot timestamp (UTC ISO 8601). -/",
        f'def snapshotCapturedAt : String := "{snapshot["captured_at"]}"',
        "",
        f"/-- Snapshot API base URL. -/",
        f'def snapshotApiBaseUrl : String := "{snapshot["api_base_url"]}"',
        "",
        "/-! ## Live recipes (sorted by output code) -/",
        "",
    ]

    # Emit each recipe as a def.
    # The constructed `Recipe` value has output, ingredients (List (String × Nat)), craftDepth.
    for code, ingredients in sorted_recipes:
        ing_pairs = ", ".join(
            f'("{escape_lean_string(ing_code)}", {qty})'
            for ing_code, qty in sorted(ingredients.items())
        )
        depth = depths[code]
        # Lean-safe identifier from item code (replace non-alnum with _).
        safe = "".join(c if c.isalnum() else "_" for c in code)
        lines.append(f"/-- Recipe for `{code}` (craftDepth {depth}). -/")
        lines.append(f"def recipe_{safe} : Recipe :=")
        lines.append(f'  {{ output := "{escape_lean_string(code)}"')
        lines.append(f"    ingredients := [{ing_pairs}]")
        lines.append(f"    craftDepth := {depth} }}")
        lines.append("")

    lines.append("/-- All recipes in the live snapshot. -/")
    lines.append("def allRecipes : List Recipe :=")
    lines.append("  [")
    rec_refs = []
    for code, _ in sorted_recipes:
        safe = "".join(c if c.isalnum() else "_" for c in code)
        rec_refs.append(f"    recipe_{safe}")
    lines.append(",\n".join(rec_refs))
    lines.append("  ]")
    lines.append("")

    # Sanity theorems
    lines.extend([
        "/-! ## Sanity theorems (live snapshot) -/",
        "",
        "/-- The snapshot contains the expected number of recipes. -/",
        f"theorem snapshot_recipe_count : allRecipes.length = {len(sorted_recipes)} := by",
        "  rfl",
        "",
        "/-! ## Fixture instantiation: prove a representative recipe is completable -/",
        "",
        "/-- A fixture State with an items task whose target is the first recipe",
        "    in `allRecipes` (lexicographic order). Demonstrates the Phase 23d-8",
        "    universal applied to LIVE game-data shape. -/",
        "noncomputable def fixtureFreshState : State where",
        "  level := 1",
        "  xp := 0",
        "  taskProgress := 0",
        "  taskTotal := 1",
        "  inventoryUsed := 0",
        "  inventoryMax := 30",
        "  hp := 100",
        "  maxHp := 100",
        '  taskType := some "items"',
        f'  taskCode := some "{sorted_recipes[0][0]}"',
        "  projectedSkillXpDelta := 0",
        "  targetSkillXp := 0",
        "  gold := 0",
        "  bankAccessible := true",
        "  bankUnlockMonsterPresent := false",
        "  initialXp := 0",
        "  unlockMonsterLevel := 0",
        "  bankRequiredLevel := 0",
        "  hasOverstockItems := false",
        "  selectBankDepositsNonempty := false",
        "  pendingItemsNonempty := false",
        "  sellableInventoryNonempty := false",
        "  recyclableSurplusNonempty := false",
        "  taskCoinsTotal := 0",
        "  taskExchangeMinCoins := 1",
        "  lowYieldCancelFires := false",
        "  taskCancelFires := false",
        "  pursueTaskFires := false",
        "  objectiveStepFires := false",
        "  craftReliefFires := false",
        "  restForCombatReady := false",
        "  gearReviewFires := false",
        "  bankItemsKnown := false",
        "  bankItemsCount := 0",
        "  bankCapacity := 0",
        "  nextExpansionCost := 1",
        "  taskLifecyclePhase := .accepted",
        "  actionsAttempted := 0",
        "  craftableSlots := 0",
        "  taskFeasibleProjected := true",
        "  -- Item 1g-A1: task pool tracking. Default empty for legacy fixtures",
        "  -- (no pool-depletion reasoning); 1g-A2 populates from allRecipes.",
        "  taskPool := []",
        "  taskCodesSeen := []",
        "  -- Item 4a: inventory composition + gather target. Legacy fixture",
        "  -- defaults to empty + none.",
        "  inventoryItems := []",
        "  gatherTarget := none",
        "  -- Item 4b: equipment composition. Legacy fixture: nothing equipped,",
        "  -- no pending equip/unequip.",
        "  equipment := []",
        "  equipTarget := none",
        "  unequipTarget := none",
        "  -- Item 4c: position. Legacy fixture spawns at (0, 0); no pending move.",
        "  posX := 0",
        "  posY := 0",
        "  moveTarget := none",
        "  -- Item 4e: per-skill XP map + skill targets. Legacy fixture: empty",
        "  -- map, no pending gather/craft skill.",
        "  skillXpDelta := []",
        "  gatherSkill := none",
        "  craftSkill := none",
        "  -- Item 8: state field gap closure. Legacy fixture defaults to empty",
        "  -- maps + zero bank gold.",
        "  skillLevels := []",
        "  bankItemsCatalog := []",
        "  bankGold := 0",
        "  pendingItemCodes := []",
        "  npcStock := []",
        "  eventSpawns := []",
        "",
        "/-- **Live-fixture items-task completable**.",
        "",
        "    Instantiates Phase 23d-8 against the first live recipe.",
        "    Witnesses an explicit K_gather + K_craft + K_taskTrade plan",
        "    reaching `phase = .complete`. NO new axioms; pure",
        "    instantiation of the universal theorem against LIVE data. -/",
        "theorem live_first_recipe_completable :",
        "    ∃ (K_gather K_craft K_taskTrade : Nat),",
        "      (applyPlan",
        "        ((List.replicate K_gather .gather)",
        "          ++ (List.replicate K_craft .craft)",
        "          ++ (List.replicate K_taskTrade .taskTrade))",
        "        fixtureFreshState).taskLifecyclePhase = TaskLifecyclePhase.complete := by",
        f"  apply recipe_then_complete_reachable recipe_"
        + "".join(c if c.isalnum() else "_" for c in sorted_recipes[0][0])
        + " fixtureFreshState",
        "  · decide",
        "  · decide",
        "  · decide",
        "",
    ])

    # Monster catalog
    _emit_monster_catalog(lines, snapshot)

    # Base stats table
    base_stats_path = ROOT / "sim" / "character_base_stats.json"
    base_doc = json.loads(base_stats_path.read_text())
    _emit_base_stats_table(lines, base_doc)

    # Item catalog
    _emit_item_catalog(lines, snapshot)

    # WinnableAcrossBand witness table (built from the real production sweep).
    stats_by_code = item_stats_from_snapshot(snapshot)
    game_data = game_data_from_snapshot(snapshot, stats_by_code)
    witness_rows = build_witness_table(
        base_doc.get("base_stats", {}), stats_by_code, game_data,
    )
    _emit_witness_table(lines, witness_rows)

    lines.append("end Formal.Liveness.GameDataFixture")

    return "\n".join(lines) + "\n"


def main() -> None:
    snapshot = json.loads(SNAPSHOT.read_text())
    lean_src = generate_lean(snapshot)
    OUTPUT.write_text(lean_src)
    print(f"Generated {OUTPUT} ({len(lean_src):,} chars, "
          f"{len(snapshot['crafting_recipes'])} recipes)")


if __name__ == "__main__":
    main()
