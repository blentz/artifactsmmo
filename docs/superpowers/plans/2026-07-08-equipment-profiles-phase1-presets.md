# Equipment Profiles — Phase 1: Profile Presets + Calibration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define the two equipment-profile weight presets (COMBAT, UTILITY) over the already-parameterized `strategic_value` scorer, plus a `score_for_profile` wrapper and the load-bearing COMBAT-calibration pins that prove the flat-parity bug is closed — all pure, proven, and UNWIRED (no consumer changes). Spec: `docs/superpowers/specs/2026-07-08-equipment-profiles-design.md`.

**Architecture:** `strategic_value(stats, weights, ...)` already accepts a weights tuple `(combat, wisdom, prospecting, inventory, haste)` in `1/STRATEGIC_SCALE` fixed-point units — no parameterization work needed. Phase 1 adds a new pure module holding `ProfileKind`, the `PROFILE_WEIGHTS` presets, a `profile_weights(kind)` accessor, and a `score_for_profile(stats, kind)` wrapper, with tests pinning the calibration (COMBAT ranks by combat only; UTILITY gives efficiency stats real weight).

**Tech Stack:** Python 3.13 (`uv`), pytest, Lean 4 (a nonneg-weights witness only — `strategic_value_pure` is already proven parametric over weights).

## Global Constraints (spec + repo rules)

- UNWIRED phase: no existing consumer changes; `equip_value`, the tree, `pick_loadout` all untouched. Adding a new module + tests only.
- `strategic_value` weights are `(combat, wisdom, prospecting, inventory_space, haste)` in `1/STRATEGIC_SCALE=1000` fixed-point units; `combat_weight = STRATEGIC_SCALE` is the dominant/floor weight (from `tiers/strategic_value.py`).
- COMBAT preset MUST rank by combat content only (utility stats weight 0) — this is the bug-fix: a pure-combat item strictly outranks a pure-utility item, and combat items order by `combat_raw`.
- UTILITY preset keeps `combat_weight = STRATEGIC_SCALE` (the FLOOR — combat still dominates shared slots structurally) and gives the efficiency stats their own nonzero weights so efficiency-slot gear gets ordered/pursued. Do NOT inherit `DEFAULT_STRATEGIC_WEIGHTS`' deferred inventory/haste parity (`STRATEGIC_SCALE`) — that would weight inventory_space as strongly as combat; set them explicitly small (spec risk item).
- Exact integer arithmetic; no floats in the score path; no inline imports; never catch Exception; TDD; 100% coverage; mypy strict.
- Never run gate.sh/mutate.py while the bot is running (`ps aux | grep "[a]rtifactsmmo play"` must be empty).

---

### Task 1: `ProfileKind` + `PROFILE_WEIGHTS` presets + accessor

**Files:**
- Create: `src/artifactsmmo_cli/ai/tiers/equipment_profile.py`
- Test: `tests/test_ai/test_equipment_profile.py`

**Interfaces:**
- Produces (later phases + Task 2 consume):
  - `class ProfileKind(Enum): COMBAT = "combat"; UTILITY = "utility"`
  - `PROFILE_WEIGHTS: dict[ProfileKind, tuple[int, int, int, int, int]]` — weights in `(combat, wisdom, prospecting, inventory_space, haste)` `1/STRATEGIC_SCALE` units, matching `strategic_value`'s tuple order.
  - `profile_weights(kind: ProfileKind) -> tuple[int, int, int, int, int]` — accessor; a `ProfileKind` not in the table is a programming error, so index directly (no `.get` default — fail loud per repo rule).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_equipment_profile.py
"""Equipment-profile weight presets (spec 2026-07-08). Phase 1: presets +
accessor, pure and unwired."""

from artifactsmmo_cli.ai.tiers.equipment_profile import (
    PROFILE_WEIGHTS,
    ProfileKind,
    profile_weights,
)
from artifactsmmo_cli.ai.tiers.strategic_value import STRATEGIC_SCALE


class TestPresets:
    def test_combat_zeroes_every_efficiency_stat(self):
        combat, wisdom, prospecting, inventory, haste = PROFILE_WEIGHTS[
            ProfileKind.COMBAT]
        assert combat == STRATEGIC_SCALE          # dominant/floor
        assert (wisdom, prospecting, inventory, haste) == (0, 0, 0, 0)

    def test_utility_keeps_combat_floor_and_lifts_efficiency(self):
        combat, wisdom, prospecting, inventory, haste = PROFILE_WEIGHTS[
            ProfileKind.UTILITY]
        assert combat == STRATEGIC_SCALE          # combat FLOOR preserved
        # every efficiency stat is nonzero and strictly below the combat
        # floor (structural combat dominance in shared slots):
        for w in (wisdom, prospecting, inventory, haste):
            assert 0 < w < STRATEGIC_SCALE

    def test_accessor_returns_the_table_row(self):
        assert profile_weights(ProfileKind.COMBAT) == PROFILE_WEIGHTS[
            ProfileKind.COMBAT]
        assert profile_weights(ProfileKind.UTILITY) == PROFILE_WEIGHTS[
            ProfileKind.UTILITY]

    def test_every_kind_has_a_preset(self):
        assert set(PROFILE_WEIGHTS) == set(ProfileKind)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_equipment_profile.py -q --no-cov`
Expected: FAIL — `ModuleNotFoundError: ...equipment_profile`

- [ ] **Step 3: Implement**

```python
# src/artifactsmmo_cli/ai/tiers/equipment_profile.py
"""Equipment profiles: named weight presets for the strategic_value scorer
(spec docs/superpowers/specs/2026-07-08-equipment-profiles-design.md).

A profile is a weight vector over strategic_value's five inputs
(combat_raw, wisdom, prospecting, inventory_space, haste) in
1/STRATEGIC_SCALE fixed-point units. COMBAT zeroes the efficiency stats so
gear ranks by combat content alone (fixing the flat-parity bug where a
prospecting artifact outranked a weapon). UTILITY keeps the combat FLOOR
(combat still dominates shared slots structurally) and gives the four
efficiency stats their own nonzero weights so efficiency-slot gear
(rings/artifacts/utility) gets ordered and pursued.

Phase 1: presets only, unwired. The UTILITY efficiency weights are the
live-tunable knob (spec Phase 5); the values here are the conservative
start, NOT the DEFAULT_STRATEGIC_WEIGHTS deferred parity (which weights
inventory_space as strongly as combat)."""

from enum import Enum

from artifactsmmo_cli.ai.tiers.strategic_value import STRATEGIC_SCALE


class ProfileKind(Enum):
    COMBAT = "combat"
    UTILITY = "utility"


# wisdom/prospecting: openapi "1% per 10 points" -> 0.001 * SCALE = 1 unit
# (same derived rate strategic_value uses). inventory_space/haste: no
# commensurated rate exists yet, so a conservative small weight (1 unit),
# NOT the SCALE-parity deferral — profiles must not weight a bag like a
# weapon. All four tunable in Phase 5.
_EFF = 1

PROFILE_WEIGHTS: dict[ProfileKind, tuple[int, int, int, int, int]] = {
    #                    (combat,          wisdom, prospecting, inventory, haste)
    ProfileKind.COMBAT: (STRATEGIC_SCALE, 0, 0, 0, 0),
    ProfileKind.UTILITY: (STRATEGIC_SCALE, _EFF, _EFF, _EFF, _EFF),
}


def profile_weights(kind: ProfileKind) -> tuple[int, int, int, int, int]:
    """The strategic_value weight tuple for `kind`. Direct index: an
    unmapped kind is a programming error, not a runtime default."""
    return PROFILE_WEIGHTS[kind]
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_equipment_profile.py -q --no-cov`
Expected: PASS

- [ ] **Step 5: Full suite, commit**

Run: `uv run pytest -q` — all pass, 100% coverage.

```bash
git add src/artifactsmmo_cli/ai/tiers/equipment_profile.py tests/test_ai/test_equipment_profile.py
git commit -m "feat(profiles): ProfileKind + COMBAT/UTILITY weight presets"
```

---

### Task 2: `score_for_profile` wrapper + calibration pins (the bug-gone proof)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/equipment_profile.py`
- Test: `tests/test_ai/test_equipment_profile.py` (extend)

**Interfaces:**
- Consumes: Task 1's `ProfileKind`/`profile_weights`; `strategic_value` (`tiers/strategic_value.py`); `equip_value` (`tiers/equip_value.py`) for the calibration cross-check; `ItemStats` (`ai/game_data`).
- Produces (Phase 3 pursuit wiring consumes this as the profile-aware scorer):
  - `score_for_profile(stats: ItemStats, kind: ProfileKind) -> int` — `strategic_value(stats, profile_weights(kind))` (no budget/horizon in Phase 1; those enter with the pursuit wiring if needed).

- [ ] **Step 1: Write the failing calibration tests**

```python
# append to tests/test_ai/test_equipment_profile.py
from artifactsmmo_cli.ai.tiers.equipment_profile import score_for_profile
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from tests.test_ai.fixtures import make_item_stats  # existing ItemStats builder


def _combat_item(raw: int):
    # a pure-combat item: put the whole combat_raw into `attack.fire`,
    # zero efficiency stats. (make_item_stats signature per fixtures.py —
    # attack is a per-element dict; use whatever the builder exposes.)
    return make_item_stats(attack={"fire": raw})


def _utility_item(prospecting: int):
    return make_item_stats(prospecting=prospecting)


class TestCombatCalibration:
    def test_combat_profile_ranks_weapon_over_prospecting_artifact(self):
        """THE bug-gone pin: under COMBAT, a real combat item strictly
        outranks a high-prospecting utility item (flat equip_value ranked
        the artifact higher — perfect_pearl over a weapon)."""
        weapon = _combat_item(30)
        artifact = _utility_item(201)
        assert score_for_profile(weapon, ProfileKind.COMBAT) > \
            score_for_profile(artifact, ProfileKind.COMBAT)
        # and equip_value (the OLD ruler) gets it wrong — proving the fix
        # is real, not vacuous:
        assert equip_value(artifact) > equip_value(weapon)

    def test_combat_profile_orders_combat_items_by_combat_raw(self):
        lo, hi = _combat_item(10), _combat_item(25)
        assert score_for_profile(hi, ProfileKind.COMBAT) > \
            score_for_profile(lo, ProfileKind.COMBAT)

    def test_combat_profile_ignores_efficiency_entirely(self):
        bare = _combat_item(10)
        plus_utility = make_item_stats(attack={"fire": 10}, prospecting=500)
        assert score_for_profile(bare, ProfileKind.COMBAT) == \
            score_for_profile(plus_utility, ProfileKind.COMBAT)


class TestUtilityCalibration:
    def test_utility_profile_orders_zero_combat_gear_by_efficiency(self):
        """In an efficiency slot (no combat items), UTILITY orders by the
        efficiency stats — the artifact IS pursued."""
        lo, hi = _utility_item(50), _utility_item(200)
        assert score_for_profile(hi, ProfileKind.UTILITY) > \
            score_for_profile(lo, ProfileKind.UTILITY)

    def test_utility_profile_still_floors_combat(self):
        """Even under UTILITY the combat floor dominates a shared slot: a
        combat item outranks a pure-utility item (structural dominance —
        combat_raw * SCALE beats efficiency * small weight)."""
        weapon = _combat_item(1)          # even a tiny combat signal
        artifact = _utility_item(999)
        assert score_for_profile(weapon, ProfileKind.UTILITY) > \
            score_for_profile(artifact, ProfileKind.UTILITY)
```

NOTE to implementer: verify `make_item_stats`'s real signature in
`tests/test_ai/fixtures.py` (attack may be a per-element dict, stats may
default to 0). Adjust the builders to produce genuinely pure-combat vs
pure-utility items; the ASSERTIONS are the contract, the builders are
plumbing. If `make_item_stats` doesn't exist under that name, use the
fixture the other tiers tests use for `ItemStats`.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_equipment_profile.py -q --no-cov -k Calibration`
Expected: FAIL — `score_for_profile` not defined.

- [ ] **Step 3: Implement**

```python
# add to equipment_profile.py (imports at top)
from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.tiers.strategic_value import strategic_value

def score_for_profile(stats: ItemStats, kind: ProfileKind) -> int:
    """Profile-aware strategic value of an equippable — the scorer the tree's
    gear branch consumes (Phase 3). COMBAT ranks by combat content only;
    UTILITY gives efficiency stats their weight over the combat floor."""
    return strategic_value(stats, profile_weights(kind))
```

- [ ] **Step 4: Run tests, then full suite**

Run: `uv run pytest tests/test_ai/test_equipment_profile.py -q --no-cov`
Expected: PASS. If `test_combat_profile_ranks_weapon_over_prospecting_artifact`'s `equip_value(artifact) > equip_value(weapon)` assertion FAILS, the flat-parity bug isn't what we think — STOP and report (the whole epic's premise needs re-checking). Otherwise the pin is valid.

Run: `uv run pytest -q` — all pass, 100% coverage.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/equipment_profile.py tests/test_ai/test_equipment_profile.py
git commit -m "feat(profiles): score_for_profile + calibration pins (combat-beats-utility bug-gone)"
```

---

### Task 3: Lean nonneg-weights witness + wrap-up

**Files:**
- Modify: whichever Lean file bounds `strategic_value_pure`'s nonneg/monotone theorems (`formal/Formal/StrategicValue.lean` — check via `grep -rn "strategicValue" formal/Formal/`) — add a witness/example that the two presets are valid weight instances (all nonneg), so the parametric nonneg proof genuinely covers them.
- Modify: the spec's Phases section — append "Phase 1 SHIPPED".

**Interfaces:** none new.

- [ ] **Step 1:** Confirm `strategic_value_pure`'s theorems are parametric over the weights (they are — the args are the weights). Add a Lean `example` pinning `PROFILE_WEIGHTS` nonnegativity in-model, e.g. `example : (0:Nat) ≤ ... := by decide` over the concrete preset tuples, so a future weight edit that introduced a negative would break the build. If the Lean model uses `Nat` weights the nonnegativity is structural — in that case add a one-line comment in `StrategicValue.lean` noting the presets are `Nat` instances and no separate witness is needed, and record that in the report (do not manufacture a vacuous theorem).
- [ ] **Step 2:** `cd formal && lake build` green (fast — only if a Lean line changed). If NO Lean change was warranted (Nat structural), skip.
- [ ] **Step 3:** IF the bot is down (`ps aux | grep "[a]rtifactsmmo play"` empty): run `./formal/gate.sh`. If live: record the debt (full suite via pre-commit is interim evidence).
- [ ] **Step 4:** Append to the spec's Phases section: `**Phase 1 SHIPPED**: ProfileKind + PROFILE_WEIGHTS (COMBAT zeroes efficiency, UTILITY floors combat + lifts efficiency) + score_for_profile + calibration pins (combat-beats-prospecting bug-gone, non-vacuous vs equip_value). Unwired.` Commit docs.

```bash
git add docs/superpowers/specs/2026-07-08-equipment-profiles-design.md formal/Formal/StrategicValue.lean 2>/dev/null
git commit -m "docs(profiles): Phase 1 shipped — presets + calibration proven"
```

---

## Later phases (outline only — planned separately after Phase 1 review)

- **Phase 2 — selector:** `profile_for(chosen_root, band_adequate)` + `is_utility_objective(root)` (reads `root_category`) in `equipment_profile.py`; pure + Lean (total + plan-gate invariant `¬band_adequate → COMBAT`); mutation arm. Unwired.
- **Phase 3 — pursuit wiring:** thread `ProfileKind` through `near_term_gear(state, profile)` / `_structural_candidates` / `_item_value` in `tiers/objective.py` + `tiers/progression_tree.py`, scoring via `score_for_profile`; **pin `has_structural_upgrade` to `ProfileKind.COMBAT` (no-circularity invariant)**; caller computes profile via `profile_for(chosen_root, band_adequate_COMBAT)`; profile scenario net (plan-gate, utility-pursuit, bug-gone regression). This is the behavior-changing phase.
- **Phase 4 — equip-gate:** winnability swap at the loadout-fielding site (`player.py` loadout resolution): field `pick_loadout(Profile(active weights))` (new `pick_loadout` purpose), swap to `pick_loadout(Combat(...))` when a fight is planned and the pick is not `is_winnable`; equip-gate scenario.
- **Phase 5 — flip + tune:** live shadow; calibrate `PROFILE_WEIGHTS[UTILITY]` (the `_EFF` values + optional budget/horizon) on real traces; ship. Hysteresis on `band_adequate` only if profile flapping is observed.
