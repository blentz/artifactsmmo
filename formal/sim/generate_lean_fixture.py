"""Generate Formal/Liveness/GameDataFixture.lean from the snapshot JSON.

Reads `formal/sim/game_data_snapshot.json` (captured by
`snapshot_game_data.py`) and emits a Lean module pinning the live
game-data recipes, monster stats, etc.

The fixture computes recipe `craftDepth` by topological sort over the
ingredient DAG (production game-data guarantees acyclicity by
construction). Items not in `crafting_recipes` are leaves (depth 0).

Output: Formal/Liveness/GameDataFixture.lean (overwrite mock fixture).
"""

import json
from collections import defaultdict, deque
from pathlib import Path

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


def generate_lean(snapshot: dict) -> str:
    recipes = snapshot["crafting_recipes"]
    depths = compute_depths(recipes)

    sorted_recipes = sorted(recipes.items())

    lines = [
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
        "namespace Formal.Liveness.GameDataFixture",
        "",
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
        "  taskCoinsTotal := 0",
        "  taskExchangeMinCoins := 1",
        "  lowYieldCancelFires := false",
        "  taskCancelFires := false",
        "  pursueTaskFires := false",
        "  objectiveStepFires := false",
        "  bankItemsKnown := false",
        "  bankItemsCount := 0",
        "  bankCapacity := 0",
        "  nextExpansionCost := 1",
        "  taskLifecyclePhase := .accepted",
        "  actionsAttempted := 0",
        "  craftableSlots := 0",
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
        "end Formal.Liveness.GameDataFixture",
    ])

    return "\n".join(lines) + "\n"


def main() -> None:
    snapshot = json.loads(SNAPSHOT.read_text())
    lean_src = generate_lean(snapshot)
    OUTPUT.write_text(lean_src)
    print(f"Generated {OUTPUT} ({len(lean_src):,} chars, "
          f"{len(snapshot['crafting_recipes'])} recipes)")


if __name__ == "__main__":
    main()
