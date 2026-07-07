# Progression Tree — Phase 2: Tree Module + Pure Cores + Lean

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the progression-tree selector as a standalone, proven module — pure cores (`milestone`, `branch_pick`, `gear_target_pick`, potion-type weights), a `decide_tree()` assembly returning a `StrategyDecision`, Lean proofs, mutation binding, and scenario-driven module tests. NOT wired into `StrategyEngine.decide` (that is Phase 3's shadow work).

**Architecture:** `progression_tree_core.py` holds the pure decision functions (no GameData/WorldState — the repo's extracted-core convention); `progression_tree.py` composes them with existing helpers (`near_term_gear`, `utility_potion_targets`, `actionable_step`, `equip_value`) into a `StrategyDecision`-compatible output. `Formal/ProgressionTree.lean` proves the cores; a new mutation group binds them to the unit tests.

**Tech Stack:** Python 3.13 (`uv`), Lean 4 + lake (formal/), pytest. No new dependencies.

## Global Constraints (spec + repo rules)

- Spec: `docs/superpowers/specs/2026-07-06-progression-tree-design.md`. Phase 2 scope: module + cores + Lean + tests, **not wired** into decide().
- Trunk milestone formula, verbatim from spec: `min(50, (level // 10 + 1) * 10)`.
- Branch rule, verbatim: gear iff (NOT band_adequate AND gear_target_exists), else xp.
- Potion weights: per-effect-family `Fraction` table, health/restore maximized now; the table is the ONLY consumable tuning surface.
- Exact arithmetic only — `Fraction`/int in every decision path, no floats.
- Semantic tiebreaks only — never repr/alphabetical as a DECISION key (a code string may appear as the FINAL disambiguator after all semantic keys, per the picker-tie precedent).
- `uv run` prefix; imports at top; one behavioral class per file; never catch Exception; TDD; 100% coverage; mypy strict.
- Lean: zero-vacuousness (every theorem non-vacuous, witnesses for hypotheses); `cd formal && lake build` green; no new axioms.
- Never run gate.sh/mutate.py while the bot is running (`ps aux | grep "[a]rtifactsmmo play"` must be empty).
- Do not modify: `StrategyEngine.decide`, arbiter, guards/means, planner.

---

### Task 1: Pure cores — `progression_tree_core.py`

**Files:**
- Create: `src/artifactsmmo_cli/ai/tiers/progression_tree_core.py`
- Test: `tests/test_ai/test_progression_tree_core.py`

**Interfaces (produced — later tasks and Lean mirror these EXACTLY):**
- `class Branch(Enum): GEAR = "gear"; XP = "xp"`
- `milestone_pure(level: int) -> int`
- `branch_pick_pure(band_adequate: bool, gear_target_exists: bool) -> Branch`
- `POTION_TYPE_WEIGHTS: dict[str, Fraction]` — keys are effect families: `"hp_restore"` (Fraction(1)), `"boost"` (Fraction(1, 4)), `"resist"` (Fraction(1, 4)), `"antipoison"` (Fraction(1, 4)). Health maximized per the spec decision; others start conservative and are tuned later.
- `potion_type_weight(family: str) -> Fraction` — table lookup; UNKNOWN family returns `Fraction(0)` (explicitly: an unmodeled consumable family must never outrank modeled gear; documented, not silent defaulting — the family universe is closed by the table).
- `@dataclass(frozen=True) GearCandidate: slot: str; code: str; gain: Fraction; level: int` — `gain` is the WEIGHTED value gain (caller applies potion weights before constructing candidates).
- `gear_target_pick(candidates: list[GearCandidate]) -> GearCandidate | None` — argmax by `(-gain, -level, code, slot)`: biggest weighted gain, then higher item level (newer generation), then code, then slot as pure disambiguators. Returns None on empty. MUST be insertion-order independent.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ai/test_progression_tree_core.py
"""Pure cores of the progression-tree selector (spec 2026-07-06).

Mirrored by Formal/ProgressionTree.lean; the PROGRESSION_TREE_MUTATIONS
group binds these tests to the source."""

from fractions import Fraction

from artifactsmmo_cli.ai.tiers.progression_tree_core import (
    POTION_TYPE_WEIGHTS,
    Branch,
    GearCandidate,
    branch_pick_pure,
    gear_target_pick,
    milestone_pure,
    potion_type_weight,
)


class TestMilestone:
    def test_next_band_boundary(self):
        assert milestone_pure(1) == 10
        assert milestone_pure(9) == 10
        assert milestone_pure(10) == 20
        assert milestone_pure(11) == 20
        assert milestone_pure(39) == 40
        assert milestone_pure(49) == 50

    def test_capped_at_fifty(self):
        assert milestone_pure(50) == 50
        assert milestone_pure(55) == 50

    def test_strictly_above_level_below_cap(self):
        for level in range(1, 50):
            m = milestone_pure(level)
            assert level < m <= 50


class TestBranchPick:
    def test_truth_table(self):
        # gear iff (not adequate) and (target exists) — all four cases:
        assert branch_pick_pure(False, True) is Branch.GEAR
        assert branch_pick_pure(False, False) is Branch.XP
        assert branch_pick_pure(True, True) is Branch.XP
        assert branch_pick_pure(True, False) is Branch.XP


class TestPotionWeights:
    def test_health_is_maximal(self):
        assert all(POTION_TYPE_WEIGHTS["hp_restore"] >= w
                   for w in POTION_TYPE_WEIGHTS.values())

    def test_lookup_and_unknown(self):
        assert potion_type_weight("hp_restore") == Fraction(1)
        assert potion_type_weight("charm_of_unmodeled") == Fraction(0)

    def test_all_weights_exact_nonnegative(self):
        for w in POTION_TYPE_WEIGHTS.values():
            assert isinstance(w, Fraction) and w >= 0


class TestGearTargetPick:
    def test_empty_is_none(self):
        assert gear_target_pick([]) is None

    def test_biggest_gain_wins(self):
        a = GearCandidate(slot="weapon_slot", code="iron_sword", gain=Fraction(30), level=10)
        b = GearCandidate(slot="boots_slot", code="iron_boots", gain=Fraction(5), level=10)
        assert gear_target_pick([a, b]) == a
        assert gear_target_pick([b, a]) == a  # insertion-order independent

    def test_gain_tie_higher_level_wins(self):
        a = GearCandidate(slot="ring1_slot", code="old_ring", gain=Fraction(4), level=5)
        b = GearCandidate(slot="ring1_slot", code="new_ring", gain=Fraction(4), level=15)
        assert gear_target_pick([a, b]) == b
        assert gear_target_pick([b, a]) == b

    def test_full_tie_falls_to_code_then_slot(self):
        # Semantically identical candidates: code is a PURE disambiguator
        # (picker-tie precedent — canonical total order, not hash roulette).
        a = GearCandidate(slot="ring1_slot", code="aaa_ring", gain=Fraction(4), level=5)
        b = GearCandidate(slot="ring1_slot", code="bbb_ring", gain=Fraction(4), level=5)
        assert gear_target_pick([a, b]) == a
        assert gear_target_pick([b, a]) == a
        c = GearCandidate(slot="ring2_slot", code="aaa_ring", gain=Fraction(4), level=5)
        assert gear_target_pick([c, a]) == a
        assert gear_target_pick([a, c]) == a
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_progression_tree_core.py -q --no-cov`
Expected: FAIL — `ModuleNotFoundError: ...progression_tree_core`

- [ ] **Step 3: Implement**

```python
# src/artifactsmmo_cli/ai/tiers/progression_tree_core.py
"""PURE cores of the progression-tree selector (spec 2026-07-06). No
GameData/WorldState — plain data only, mirrored by Formal/ProgressionTree.lean.

The tree replaces the flat scalar root ranking: trunk (L10..L50 milestones),
two branches (gear | xp) switched by band adequacy, tertiary untouched."""

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

TRUNK_CAP = 50
BAND = 10


class Branch(Enum):
    GEAR = "gear"
    XP = "xp"


def milestone_pure(level: int) -> int:
    """Next trunk milestone: min(50, (level // 10 + 1) * 10). Strictly above
    `level` until the cap; the L50 capstone is the fixed point."""
    return min(TRUNK_CAP, (level // BAND + 1) * BAND)


def branch_pick_pure(band_adequate: bool, gear_target_exists: bool) -> Branch:
    """Gear-first until the band's loadout is adequate; then xp to the next
    milestone. One boolean pivot — no scalar competition (the design's core
    bet). Gear also yields when it has no reachable target (nothing to do)."""
    if not band_adequate and gear_target_exists:
        return Branch.GEAR
    return Branch.XP


POTION_TYPE_WEIGHTS: dict[str, Fraction] = {
    "hp_restore": Fraction(1),
    "boost": Fraction(1, 4),
    "resist": Fraction(1, 4),
    "antipoison": Fraction(1, 4),
}
"""Per-effect-family consumable weights — the ONLY tuning surface for
potions in the gear branch (user decision 2026-07-06: health maximized now,
other families dialed later). Applied as a multiplier on the candidate's
value gain before gear_target_pick."""


def potion_type_weight(family: str) -> Fraction:
    """Table lookup. An UNKNOWN family weighs 0: an unmodeled consumable
    must never outrank modeled gear — the family universe is closed by the
    table, and extending it is a deliberate tuning act, not a default."""
    return POTION_TYPE_WEIGHTS.get(family, Fraction(0))


@dataclass(frozen=True)
class GearCandidate:
    """One upgrade candidate for the gear branch. `gain` is the WEIGHTED
    value gain (potion-family weight already applied by the assembler)."""
    slot: str
    code: str
    gain: Fraction
    level: int


def gear_target_pick(candidates: list[GearCandidate]) -> GearCandidate | None:
    """Deterministic argmax: biggest weighted gain, then higher item level
    (newer gear generation), then code and slot as PURE disambiguators
    (canonical total order — insertion-order and hash-seed independent)."""
    if not candidates:
        return None
    return min(candidates, key=lambda c: (-c.gain, -c.level, c.code, c.slot))
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_progression_tree_core.py -q --no-cov`
Expected: PASS (all)

- [ ] **Step 5: Full suite, commit**

Run: `uv run pytest -q` — all pass, 100% coverage.

```bash
git add src/artifactsmmo_cli/ai/tiers/progression_tree_core.py tests/test_ai/test_progression_tree_core.py
git commit -m "feat(tree): progression-tree pure cores — milestone, branch pick, gear argmax, potion weights"
```

---

### Task 2: Lean proofs — `Formal/ProgressionTree.lean`

**Files:**
- Create: `formal/Formal/ProgressionTree.lean`
- Modify: whichever aggregator imports Formal modules (check `formal/Formal.lean` or the lakefile root import — follow how `Formal/BankExpansionTiming.lean` is registered).

**Interfaces:**
- Consumes: Task 1's definitions (mirror them 1:1 — same names in lowerCamelCase: `milestonePure`, `branchPick`, `gearTargetPick` over a `GearCand` structure, `potionWeight` over a closed inductive family).

- [ ] **Step 1: Write the Lean module (proof-first; `lake build` is the test)**

```lean
/- Formal/ProgressionTree.lean
   Mirrors src/artifactsmmo_cli/ai/tiers/progression_tree_core.py
   (spec docs/superpowers/specs/2026-07-06-progression-tree-design.md).
   The Python cores are bound to these semantics by the
   PROGRESSION_TREE_MUTATIONS group (unit-killed, formal/diff/mutate.py). -/
namespace Formal.ProgressionTree

def trunkCap : Nat := 50
def band : Nat := 10

def milestonePure (level : Nat) : Nat :=
  min trunkCap ((level / band + 1) * band)

/-- The milestone strictly exceeds the level below the cap. -/
theorem milestone_gt_level (level : Nat) (h : level < trunkCap) :
    level < milestonePure level := by
  unfold milestonePure trunkCap band
  omega_nat_div  -- placeholder name: use `omega` after introducing
                 -- `Nat.div_add_mod level 10` to expose the division
-- ACTUAL PROOF OBLIGATION (the implementer writes a real proof; the
-- following skeleton is the known-good shape):
--   have hd := Nat.div_add_mod level 10
--   have hm : level % 10 < 10 := Nat.mod_lt _ (by decide)
--   simp only [milestonePure, trunkCap, band, min_def]
--   split <;> omega

/-- The milestone never exceeds the cap. -/
theorem milestone_le_cap (level : Nat) : milestonePure level ≤ trunkCap := by
  unfold milestonePure; exact Nat.min_le_left _ _

/-- Milestones are band boundaries: divisible by 10. -/
theorem milestone_band_aligned (level : Nat) : milestonePure level % band = 0 := by
  unfold milestonePure trunkCap band
  rcases Nat.le_total 50 ((level / 10 + 1) * 10) with h | h
  · simp [Nat.min_eq_left h]  -- adjust: min picks 50, 50 % 10 = 0
  · simp [Nat.min_eq_right h, Nat.mul_mod_left]

/-- Crossing a milestone strictly advances it (trunk descent): at the cap it
is a fixed point; below, reaching the milestone yields a bigger one. -/
theorem milestone_advances (level : Nat) (h : milestonePure level < trunkCap) :
    milestonePure level < milestonePure (milestonePure level) := by
  -- from band-alignment: m = milestonePure level has m % 10 = 0, so
  -- milestonePure m = min 50 (m + 10); with m < 50: m < m + 10 ≤ 50-aligned.
  sorry_free_obligation  -- implementer proves; no `sorry` may remain

inductive Branch | gear | xp
deriving DecidableEq, Repr

def branchPick (bandAdequate gearTargetExists : Bool) : Branch :=
  if !bandAdequate && gearTargetExists then .gear else .xp

/-- Exhaustive truth table (4 cases, decide). -/
theorem branchPick_table :
    branchPick false true = .gear ∧ branchPick false false = .xp ∧
    branchPick true true = .xp ∧ branchPick true false = .xp := by
  decide

/-- Gear is picked IFF work exists and the band is not yet adequate. -/
theorem branchPick_gear_iff (a e : Bool) :
    branchPick a e = .gear ↔ (a = false ∧ e = true) := by
  cases a <;> cases e <;> simp [branchPick]

inductive PotionFamily | hpRestore | boost | resist | antipoison | unknown
deriving DecidableEq, Repr

def potionWeight : PotionFamily → Rat
  | .hpRestore => 1
  | .boost => 1/4
  | .resist => 1/4
  | .antipoison => 1/4
  | .unknown => 0

/-- Health dominates every family (the user's tuning decision, pinned). -/
theorem potionWeight_health_maximal (f : PotionFamily) :
    potionWeight f ≤ potionWeight .hpRestore := by
  cases f <;> simp [potionWeight] <;> norm_num

/-- Unknown families never outrank anything with positive weight. -/
theorem potionWeight_unknown_floor (f : PotionFamily) :
    potionWeight .unknown ≤ potionWeight f := by
  cases f <;> simp [potionWeight] <;> norm_num

structure GearCand where
  slot : String
  code : String
  gain : Rat
  level : Nat
deriving DecidableEq, Repr

/-- The strict total preference order (mirrors Python's argmax key
    (-gain, -level, code, slot)). -/
def better (a b : GearCand) : Bool :=
  if a.gain ≠ b.gain then a.gain > b.gain
  else if a.level ≠ b.level then a.level > b.level
  else if a.code ≠ b.code then a.code < b.code
  else a.slot < b.slot

def pickFold (best : Option GearCand) (c : GearCand) : Option GearCand :=
  match best with
  | none => some c
  | some b => if better c b then some c else some b

def gearTargetPick (cs : List GearCand) : Option GearCand :=
  cs.foldl pickFold none

/-- Empty list picks nothing; non-empty always picks. -/
theorem gearTargetPick_none_iff (cs : List GearCand) :
    gearTargetPick cs = none ↔ cs = [] := by
  cases cs with
  | nil => simp [gearTargetPick]
  | cons h t =>
    simp [gearTargetPick]
    -- foldl over (some h) never returns to none:
    -- prove auxiliary: ∀ acc ≠ none, foldl pickFold acc t ≠ none
    sorry_free_obligation  -- implementer proves via induction on t

/-- The pick is a member of its input. -/
theorem gearTargetPick_mem (cs : List GearCand) (c : GearCand)
    (h : gearTargetPick cs = some c) : c ∈ cs := by
  sorry_free_obligation  -- induction on cs, mirroring BankSelection's
                         -- bestWeaponFold membership proof shape

end Formal.ProgressionTree
```

NOTE to implementer: `sorry_free_obligation` is NOT Lean syntax — it marks
proof obligations YOU must complete; the file must compile with `lake build`
with ZERO `sorry`/`admit` (the gate's no-sorry check enforces this). The
comment skeletons give the known-good proof shapes; `Formal/BankSelection.lean`
(betterWeapon/bestWeaponFold theorems) is the in-repo pattern to mirror for
the fold proofs. If a permutation-invariance proof for `gearTargetPick`
is cheap with the strict-total-order structure, add it
(`gearTargetPick_perm`); if it balloons, the membership + none_iff +
Python's insertion-order unit tests are the accepted Phase-2 bar (note the
deferral in the module docstring).

- [ ] **Step 2: Register the module + build**

Add the import line where sibling Formal modules are registered (grep
`BankExpansionTiming` in `formal/` to find the aggregator), then:

Run: `cd formal && lake build 2>&1 | grep -E "error|warning: .*sorry" ; echo exit=$?`
Expected: exit=0, no errors, no sorry warnings.

- [ ] **Step 3: Axiom hygiene**

Run: `cd formal && grep -rn "axiom" Formal/ProgressionTree.lean`
Expected: no output (no new axioms).

- [ ] **Step 4: Commit**

```bash
git add formal/Formal/ProgressionTree.lean formal/Formal.lean
git commit -m "feat(formal): ProgressionTree.lean — milestone/branch/argmax/weights proven"
```

---

### Task 3: Assembly — `decide_tree()` in `progression_tree.py`

**Files:**
- Create: `src/artifactsmmo_cli/ai/tiers/progression_tree.py`
- Test: `tests/test_ai/test_progression_tree.py`

**Interfaces:**
- Consumes: Task 1 cores; existing helpers — `CharacterObjective.near_term_gear(state) -> dict[slot, code]`, `CharacterObjective.utility_potion_targets(state) -> dict[slot, code]`, `CharacterObjective._item_value(code|None) -> int`, `equip_value(stats) -> int` (tiers.equip_value), `actionable_step(root, state, game_data) -> MetaGoal|None` (tiers.strategy), `StrategyDecision`/`RootScore` (tiers.strategy), `ObtainItem`/`ReachCharLevel` (tiers.meta_goal), `equipped_potion_qty` (ai.equipped_potion).
- Produces: `decide_tree(state: WorldState, game_data: GameData, objective: CharacterObjective) -> StrategyDecision` — used by Phase 3's shadow wiring and this task's tests.

Semantics (BINDING):
1. Trunk: `trunk = ReachCharLevel(level=milestone_pure(state.level))`.
2. Gear candidates:
   - Structural slots: for each `(slot, code)` in `objective.near_term_gear(state)`: `gain = Fraction(equip_value(game_data.item_stats(code)) - objective._item_value(state.equipment.get(slot)))`; include only `gain > 0`; `level = item_stats(code).level`; weight 1 (no scaling).
   - Utility slots: for each `(slot, code)` in `objective.utility_potion_targets(state)`: SKIP when already provisioned (`equipped_potion_qty(state, code) > 0` — the slot holds stock; refill churn is the flat-ranking disease this replaces; finer provisioning quantities stay the guard's job). Else `gain = potion_type_weight("hp_restore") * Fraction(equip_value(game_data.item_stats(code)))` — Phase-2 maps every `utility_potion_targets` entry to the `hp_restore` family (that helper only produces heals today; other families join when the tree drives boost/resist targets in a later tuning pass — document this in the code).
3. `gear_target_exists = candidates != []`; `band_adequate = candidates == []` for Phase 2 (adequacy refined with the E-tower signal in Phase 3 — the 2-arg proven core stays general; document).
4. `branch = branch_pick_pure(band_adequate, gear_target_exists)`.
5. GEAR: `chosen_root = ObtainItem(code=pick.code, quantity=1, slot=pick.slot)`; `chosen_step = actionable_step(chosen_root, state, game_data) or chosen_root`. XP: `chosen_root = trunk`; `chosen_step = trunk`.
6. `fallback_steps`/`fallback_roots`: the OTHER branch's root+step (gear pick if xp chosen and candidates existed — impossible by rule; xp trunk if gear chosen), plus remaining gear candidates in pick order (each as its own ObtainItem root/step pair) — gives the arbiter alternates exactly like today's `fallback_steps` contract.
7. `ranking`: descent rendered as `RootScore` rows for display parity — trunk row (category `"char_level"`, contribution/score `Fraction(1)`), then each gear candidate (category `"gear"`, score = its gain, `step_repr` = its actionable step repr). Cost field: 0. `desired_state`: `{}` (display-only in this path; the arbiter derives real desired state from goals).
8. `interrupt = None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ai/test_progression_tree.py
"""decide_tree(): the Phase-2 tree assembly over Phase-1 scenarios.

Drives the module DIRECTLY (not wired into StrategyEngine — Phase 3).
Expectations are computed from the tree's own binding semantics."""

import json
from pathlib import Path

from artifactsmmo_cli.ai.player import GamePlayer  # noqa: F401  (scenario seam parity)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.progression_tree import decide_tree

BUNDLE = (Path(__file__).parent / "scenarios" / "fixtures"
          / "gamedata_bundle.json")


def _decide(name: str):
    gd = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
    state = scenario_state(SCENARIOS[name])
    return decide_tree(state, gd, CharacterObjective.from_game_data(gd)), state


def test_weapon_upgrade_scenario_picks_gear_branch():
    d, _ = _decide("l10_weapon_upgrade")
    assert isinstance(d.chosen_root, ObtainItem)
    assert d.chosen_root.slot == "weapon_slot"


def test_low_hp_scenario_still_produces_a_decision():
    """Guards preempt at the ARBITER, not here — the tree always answers."""
    d, _ = _decide("l3_low_hp")
    assert d.chosen_root is not None and d.chosen_step is not None


def test_xp_branch_when_no_gear_candidates():
    """A maximally-geared synthetic state falls to the trunk."""
    d, state = _decide("l10_copper_adequate")
    # Whichever branch fires, the DECISION is total and the trunk is the
    # milestone: for the xp case, root == step == ReachCharLevel(20).
    if isinstance(d.chosen_root, ReachCharLevel):
        assert d.chosen_root.level == 20
        assert d.chosen_step == d.chosen_root


def test_trunk_milestone_matches_core():
    d, state = _decide("l1_fresh")
    trunk_rows = [r for r in d.ranking if r.category == "char_level"]
    assert trunk_rows and "10" in trunk_rows[0].root_repr


def test_ranking_renders_the_descent():
    d, _ = _decide("l10_weapon_upgrade")
    assert d.ranking, "descent must be rendered for display parity"
    assert all(r.score >= 0 for r in d.ranking)


def test_fallbacks_offer_the_other_branch():
    d, _ = _decide("l10_weapon_upgrade")
    assert any(isinstance(s, ReachCharLevel) for s in d.fallback_steps), (
        "gear decision must carry the xp trunk as an arbiter fallback")
```

NOTE: `l10_copper_adequate`'s live outcome depends on the catalog (empty
utility slots may yield a potion candidate → GEAR). The test above is
branch-agnostic where the catalog decides, and exact where the tree's rule
is deterministic. After implementing, ADD one exact assertion per scenario
recording the actual branch/target under the committed bundle (like the
CURRENT_TODAY pins) with a comment deriving WHY from the semantics — these
are the tree's own behavior pins for Phase 3.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_progression_tree.py -q --no-cov`
Expected: FAIL — `ModuleNotFoundError: ...progression_tree`

- [ ] **Step 3: Implement `progression_tree.py` per the BINDING semantics above**

Module skeleton (fill per semantics 1-8; keep under ~150 lines):

```python
# src/artifactsmmo_cli/ai/tiers/progression_tree.py
"""The progression-tree selector (spec 2026-07-06): trunk -> branch -> target.

Phase 2: standalone assembly, NOT wired into StrategyEngine.decide (Phase 3
shadows it there). Consumes the same helpers the flat ranking uses, so the
cutover swaps the decision procedure, not the data sources."""
```

with `decide_tree(state, game_data, objective) -> StrategyDecision` composing
Task-1 cores exactly as the BINDING semantics dictate. Every branch of the
assembly must be reachable by at least one test (coverage gate).

- [ ] **Step 4: Run tests, add the per-scenario behavior pins (see NOTE), re-run**

Run: `uv run pytest tests/test_ai/test_progression_tree.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Full suite, commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/progression_tree.py tests/test_ai/test_progression_tree.py
git commit -m "feat(tree): decide_tree assembly — trunk/branch/target over existing helpers"
```

---

### Task 4: Mutation binding — `PROGRESSION_TREE_MUTATIONS`

**Files:**
- Modify: `formal/diff/mutate.py` (new group + `run_group` registration; follow the `OBJECTIVE_NOW_MUTATIONS` unit-bound precedent — group bound to `tests/test_ai/test_progression_tree_core.py`)

**Interfaces:** none new.

- [ ] **Step 1: Add the group (source strings must match `progression_tree_core.py` EXACTLY — copy from the file, never retype)**

```python
PROGRESSION_TREE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "progression_tree_core.py"

# Progression-tree cores (2026-07-06): unit-killed group (OBJECTIVE_NOW
# precedent) bound to tests/test_ai/test_progression_tree_core.py.
PROGRESSION_TREE_MUTATIONS = [
    ("tree: branch pick ignores adequacy (gear whenever a target exists)",
     "    if not band_adequate and gear_target_exists:",
     "    if gear_target_exists:"),
    ("tree: milestone off-by-a-band (current band, not next)",
     "    return min(TRUNK_CAP, (level // BAND + 1) * BAND)",
     "    return min(TRUNK_CAP, (level // BAND) * BAND)"),
    ("tree: health weight demoted below boost",
     '    "hp_restore": Fraction(1),',
     '    "hp_restore": Fraction(1, 8),'),
    ("tree: unknown potion family weighs like health",
     "    return POTION_TYPE_WEIGHTS.get(family, Fraction(0))",
     "    return POTION_TYPE_WEIGHTS.get(family, Fraction(1))"),
    ("tree: argmax gain sign flipped (worst upgrade wins)",
     "    return min(candidates, key=lambda c: (-c.gain, -c.level, c.code, c.slot))",
     "    return min(candidates, key=lambda c: (c.gain, -c.level, c.code, c.slot))"),
]
```

and next to the other `run_group` calls:

```python
    run_group(PROGRESSION_TREE_SRC, PROGRESSION_TREE_MUTATIONS,
              "tests/test_ai/test_progression_tree_core.py", survivors)
```

- [ ] **Step 2: Kill-check EVERY mutant manually (apply → bound test fails → revert → green). Do NOT use `git checkout` to revert (uncommitted-work hazard); reverse the string replacement.**

For each of the 5 mutants: apply via a python one-shot string replace, run
`uv run pytest tests/test_ai/test_progression_tree_core.py -q --no-cov -x`
(expect ≥1 FAIL), reverse the replace, re-run (expect all PASS). If any
mutant SURVIVES, add the missing unit test to the core test file first,
then re-check.

- [ ] **Step 3: Commit**

```bash
git add formal/diff/mutate.py tests/test_ai/test_progression_tree_core.py
git commit -m "feat(gate): PROGRESSION_TREE_MUTATIONS — unit-killed core binding"
```

---

### Task 5: Wrap-up

- [ ] **Step 1:** Append "Phase 2 SHIPPED" (commits, decisions, deferrals — e.g. adequacy = candidates-empty until Phase 3, permutation proof status) to the spec's Phases section.
- [ ] **Step 2:** IF the bot is down (`ps aux | grep "[a]rtifactsmmo play"` empty): run `./formal/gate.sh` end-to-end (now includes the new Lean module + mutation group). If live: record the debt, stop.
- [ ] **Step 3:** Commit docs; update `project_progression_tree.md` memory (Phase 2 shipped, next = Phase 3 shadow).
