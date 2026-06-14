# Per-Slot Gear Roots (Dual-Ring Equip) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make gear roots slot-aware so the objective can target and equip the same item in more than one slot (two `copper_ring`s in `ring1_slot` + `ring2_slot`).

**Architecture:** `ObtainItem` gains an optional `slot`; a slot-tagged root is satisfied only when that slot holds the code (slot=None keeps today's membership/owned-count semantics). `target_gear`/`near_term_gear` duplicate-fill ring slots; gear roots are emitted per `(slot, code)`; the equip step and scoring use `root.slot`. Backward-compatible — every existing slot-less `ObtainItem` is unchanged.

**Tech Stack:** Python 3.13, `uv`, pytest (`-W error`, 100% coverage on `src/`), mypy `--strict`.

**Spec:** `docs/superpowers/specs/2026-06-14-per-slot-gear-roots-dual-ring-design.md`

**Conventions (CLAUDE.md):** Prefix commands with `uv run`. Imports top only; no inline/`...`/`TYPE_CHECKING`; never catch `Exception`. mypy strict (parameterize generics). Tests in `tests/`; 0 errors/warnings/skips, 100% coverage on `src/`.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `src/artifactsmmo_cli/ai/tiers/meta_goal.py` | `ObtainItem.slot` + slot-aware `is_satisfied` + custom `__repr__` | T1 |
| `src/artifactsmmo_cli/ai/tiers/objective.py` | rings duplicate-fill via shared `_slot_assignments` (target_gear + near_term_gear) | T2 |
| `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py` | per-`(slot, code)` gear-root emission | T3 |
| `src/artifactsmmo_cli/ai/strategy_driver.py` | equip step uses `step.slot`/`root.slot` | T4 |
| `src/artifactsmmo_cli/ai/tiers/strategy.py` | scoring uses `root.slot` (`_base_prior`, `_marginal`) | T4 |

---

## Task 1: `ObtainItem` slot-aware

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/meta_goal.py`
- Test: `tests/test_ai/test_meta_goal.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ai/test_meta_goal.py` (create the file with the imports below if it does not exist):

```python
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from tests.test_ai.fixtures import make_state


def _ring_gd() -> GameData:
    gd = GameData()
    gd._item_stats = {"copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                               attack={"fire": 2})}
    return gd


def test_slot_tagged_obtainitem_satisfied_only_when_that_slot_holds_code():
    gd = _ring_gd()
    root = ObtainItem("copper_ring", slot="ring2_slot")
    # ring1 holds it, ring2 empty -> the ring2 root is NOT satisfied.
    s1 = make_state(equipment={"ring1_slot": "copper_ring"})
    assert root.is_satisfied(s1, gd) is False
    # ring2 holds it -> satisfied.
    s2 = make_state(equipment={"ring1_slot": "copper_ring", "ring2_slot": "copper_ring"})
    assert root.is_satisfied(s2, gd) is True


def test_slotless_equippable_unchanged_membership():
    gd = _ring_gd()
    root = ObtainItem("copper_ring")  # slot=None -> today's membership semantics
    assert root.is_satisfied(make_state(equipment={"ring1_slot": "copper_ring"}), gd) is True
    assert root.is_satisfied(make_state(equipment={}), gd) is False


def test_repr_omits_slot_when_none_and_shows_it_when_set():
    assert repr(ObtainItem("copper_boots")) == "ObtainItem(code='copper_boots', quantity=1)"
    assert repr(ObtainItem("copper_ring", slot="ring2_slot")) == (
        "ObtainItem(code='copper_ring', quantity=1, slot='ring2_slot')")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_meta_goal.py -v`
Expected: FAIL — `ObtainItem` has no `slot` (TypeError) / repr mismatch.

- [ ] **Step 3: Add `slot` + slot-aware `is_satisfied` + custom repr**

In `src/artifactsmmo_cli/ai/tiers/meta_goal.py`, replace the `ObtainItem` class. Note `@dataclass(..., repr=False)` so the custom `__repr__` is used (the auto-repr would append `slot=None` and break existing repr assertions across the suite):

```python
@dataclass(frozen=True, repr=False)
class ObtainItem:
    code: str
    quantity: int = 1
    slot: str | None = None

    def __repr__(self) -> str:
        if self.slot is not None:
            return (f"ObtainItem(code={self.code!r}, quantity={self.quantity}, "
                    f"slot={self.slot!r})")
        return f"ObtainItem(code={self.code!r}, quantity={self.quantity})"

    def is_satisfied(self, state: WorldState, game_data: GameData) -> bool:
        # Per-slot gear root: satisfied iff THIS slot holds the code, so the
        # objective can target the same item in multiple slots (two copper_rings
        # in ring1_slot + ring2_slot). slot=None keeps the legacy semantics below.
        if self.slot is not None:
            return state.equipment.get(self.slot) == self.code
        # Equippable items: owning isn't the end-state — the meta-objective
        # is to WEAR them. Trace 2026-06-05T03:37: Robby crafted wooden_shield
        # but never equipped it; root dropped from candidates because owned >=
        # 1, the UpgradeEquipmentGoal never re-fired, and the shield sat
        # in inventory forever. Require occupancy of an equipment slot.
        # EXCEPT TOOLS (subtype='tool', e.g. copper_pickaxe, copper_axe,
        # fishing_net): owning is the goal because tools ROTATE through
        # weapon_slot per the active gathering task (OptimizeLoadout swaps
        # the right tool in per-fight / per-gather). Recipe-input codes
        # (ash_plank, copper_bar, ash_wood) stay on the owned-count rule —
        # they're consumed by crafts and never enter equipment.
        stats = game_data.item_stats(self.code)
        if stats is not None and ITEM_TYPE_TO_SLOTS.get(stats.type_):
            if stats.subtype == "tool":
                return owned_count(state, self.code) >= self.quantity
            return self.code in state.equipment.values()
        return owned_count(state, self.code) >= self.quantity
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_ai/test_meta_goal.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/meta_goal.py tests/test_ai/test_meta_goal.py
git commit -m "feat(ai): ObtainItem.slot — per-slot gear-root satisfaction"
```

---

## Task 2: Rings duplicate-fill (`target_gear` + `near_term_gear`)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/objective.py`
- Test: `tests/test_ai/test_tiers_objective.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ai/test_tiers_objective.py`:

```python
def test_ring_slots_duplicate_fill_when_one_attainable():
    """Only copper_ring attainable -> BOTH ring slots target it (you can wear
    two identical rings) instead of leaving ring2_slot untargeted."""
    gd = GameData()
    gd._item_stats = {
        "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring", attack={"fire": 2}),
        "iron_sword": ItemStats(code="iron_sword", level=1, type_="weapon", attack={"fire": 5}),
    }
    gd._crafting_recipes = {"copper_ring": {"bar": 1}, "iron_sword": {"bar": 1}}
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    obj = CharacterObjective.from_game_data(gd)
    assert obj.target_gear["ring1_slot"] == "copper_ring"
    assert obj.target_gear["ring2_slot"] == "copper_ring"


def test_artifact_slots_not_duplicate_filled():
    """Artifacts are unique (game rejects duplicates): one attainable artifact
    fills only artifact1_slot — duplicate-fill is rings-only."""
    gd = GameData()
    gd._item_stats = {"ancient_relic": ItemStats(code="ancient_relic", level=1,
                                                  type_="artifact", attack={"fire": 3})}
    gd._crafting_recipes = {"ancient_relic": {"bar": 1}}
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    obj = CharacterObjective.from_game_data(gd)
    assert obj.target_gear["artifact1_slot"] == "ancient_relic"
    assert "artifact2_slot" not in obj.target_gear
    assert "artifact3_slot" not in obj.target_gear


def test_near_term_gear_duplicate_fills_empty_second_ring():
    """near_term_gear: ring1 already holds copper_ring, ring2 empty, only
    copper_ring attainable-now -> ring2_slot also targets copper_ring."""
    gd = GameData()
    gd._item_stats = {"copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                               attack={"fire": 2})}
    gd._crafting_recipes = {"copper_ring": {"bar": 1}}
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    obj = CharacterObjective.from_game_data(gd)
    state = make_state(level=5, equipment={"ring1_slot": "copper_ring"})
    nt = obj.near_term_gear(state)
    assert nt.get("ring2_slot") == "copper_ring"  # empty 2nd ring slot still targeted
```

(The existing `test_paired_ring_slots_get_top_two_distinct` — 2+ distinct attainable rings → ring1=gold, ring2=ruby — must stay green: duplicate-fill only triggers when fewer distinct attainable than slots.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_tiers_objective.py -k "duplicate_fill or near_term_gear_duplicate" -v`
Expected: FAIL — `ring2_slot`/duplicate keys absent.

- [ ] **Step 3: Add the shared `_slot_assignments` helper + use it in both methods**

In `src/artifactsmmo_cli/ai/tiers/objective.py`, add the module constant + helper (after the imports, near `is_attainable`):

```python
_DUPLICATE_FILL_TYPES = frozenset({"ring"})
"""Multi-slot equip types whose empty slots are filled by repeating the best
attainable item. Rings only: the game lets you wear two identical rings, so when
fewer distinct rings are attainable than ring slots, double up the best.
Artifacts are unique (the game rejects duplicates) and utility consumables stay
distinct, so their remaining slots are left untargeted."""


def _slot_assignments(type_: str, slots: list[str],
                      attainable: list[tuple[int, str]]) -> list[tuple[str, int, str]]:
    """(slot, value, code) for each slot: ranked attainable assigned in order,
    then for rings any remaining slots filled by repeating the best attainable."""
    out: list[tuple[str, int, str]] = []
    for i, slot in enumerate(slots):
        if i < len(attainable):
            value, code = attainable[i]
        elif type_ in _DUPLICATE_FILL_TYPES and attainable:
            value, code = attainable[0]
        else:
            continue
        out.append((slot, value, code))
    return out
```

Replace the `from_game_data` ring/zip loop:

```python
            for slot, _value, code in _slot_assignments(type_, slots, attainable):
                target_gear[slot] = code
```

Replace the `near_term_gear` ring/zip loop (preserving its "beats equipped" gate):

```python
            for slot, value, code in _slot_assignments(type_, slots, attainable):
                if value > self._item_value(state.equipment.get(slot)):
                    targets[slot] = code
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_ai/test_tiers_objective.py -v`
Expected: PASS (new tests + the preserved top-2-distinct test).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/objective.py tests/test_ai/test_tiers_objective.py
git commit -m "feat(ai): rings duplicate-fill empty slots in target/near-term gear"
```

---

## Task 3: Per-slot gear-root emission

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py`
- Test: `tests/test_ai/test_tiers_prerequisite_graph.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ai/test_tiers_prerequisite_graph.py` (uses the file's existing `objective_roots`, `ObtainItem`, `CharacterObjective`, `GameData`, `ItemStats`, `make_state` imports — add any missing import at the top):

```python
def test_gear_roots_are_slot_tagged_and_distinct_per_ring_slot():
    """Two ring slots both wanting copper_ring -> two DISTINCT slot-tagged
    gear roots (so ring2 isn't deduped/satisfied off ring1)."""
    gd = GameData()
    gd._item_stats = {"copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                               attack={"fire": 2})}
    gd._crafting_recipes = {"copper_ring": {"bar": 1}}
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    obj = CharacterObjective.from_game_data(gd)
    roots = objective_roots(obj)
    ring_roots = [r for r in roots
                  if isinstance(r, ObtainItem) and r.code == "copper_ring"]
    assert ObtainItem("copper_ring", slot="ring1_slot") in ring_roots
    assert ObtainItem("copper_ring", slot="ring2_slot") in ring_roots
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_tiers_prerequisite_graph.py::test_gear_roots_are_slot_tagged_and_distinct_per_ring_slot -v`
Expected: FAIL — roots are slot-less `ObtainItem("copper_ring")`.

- [ ] **Step 3: Emit per `(slot, code)`**

In `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py`, change the two gear-root emission lines (near 157-161). Replace:

```python
        roots.extend(ObtainItem(code)
                     for code in objective.near_term_gear(state).values())
```
with:
```python
        roots.extend(ObtainItem(code, slot=slot)
                     for slot, code in objective.near_term_gear(state).items())
```

and replace:
```python
    roots.extend(ObtainItem(code) for code in objective.target_gear.values())
```
with:
```python
    roots.extend(ObtainItem(code, slot=slot) for slot, code in objective.target_gear.items())
```

(Leave the `target_tools` line unchanged — tools are slot-less, they rotate through weapon_slot.)

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_ai/test_tiers_prerequisite_graph.py -v`
Expected: PASS. Some existing tests asserting slot-less gear roots from `target_gear` may now see slot-tagged roots — update those assertions to the `slot=`-tagged form (e.g. `ObtainItem("copper_boots", slot="boots_slot")`). Curate any that fail in this step.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py tests/test_ai/test_tiers_prerequisite_graph.py
git commit -m "feat(ai): emit per-slot gear roots from target/near-term gear"
```

---

## Task 4: Slot-aware equip + scoring

**Files:**
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` (`objective_step_goal`)
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py` (`_base_prior`, `_marginal`)
- Test: `tests/test_ai/test_strategy_driver.py`, `tests/test_ai/test_tiers_strategy.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ai/test_strategy_driver.py`:

```python
def test_equip_step_uses_root_slot_for_second_ring():
    """A slot-tagged ring2 gear root equips copper_ring into ring2_slot (not the
    type's first slot), so a 2nd copper_ring fills the empty second ring slot."""
    gd = GameData()
    gd._item_stats = {"copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                               attack={"fire": 2})}
    gd._crafting_recipes = {"copper_ring": {"bar": 1}}
    gd._resource_drops = {"rocks": "bar"}
    # ring1 already worn; a spare copper_ring in inventory to equip into ring2.
    state = make_state(level=5, inventory={"copper_ring": 1},
                       equipment={"ring1_slot": "copper_ring"})
    step = ObtainItem("copper_ring", slot="ring2_slot")
    g = objective_step_goal(step, state, gd, _ctx(), root=step)
    assert isinstance(g, UpgradeEquipmentGoal)
    assert g._committed_target == ("copper_ring", "ring2_slot")
```

Append to `tests/test_ai/test_tiers_strategy.py`:

```python
def test_second_ring_root_scored_against_its_own_empty_slot():
    """With ring1 filled and ring2 empty, the ring1 root is satisfied while the
    slot-tagged ring2 root scores its OWN empty slot (positive marginal) so it's
    pursued — not read as satisfied off ring1."""
    gd = GameData()
    gd._item_stats = {"copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                               attack={"fire": 6})}
    gd._crafting_recipes = {"copper_ring": {"bar": 1}}
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
    state = make_state(level=5, equipment={"ring1_slot": "copper_ring"})
    ring2 = ObtainItem("copper_ring", slot="ring2_slot")
    assert not ring2.is_satisfied(state, gd)
    assert eng._marginal(ring2, state, gd) > 0
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py::test_equip_step_uses_root_slot_for_second_ring tests/test_ai/test_tiers_strategy.py::test_second_ring_root_scored_against_its_own_empty_slot -v`
Expected: FAIL — equip targets `slots[0]` (ring1); marginal computed off ring1 (already filled → 0 gain).

- [ ] **Step 3: Use the slot in the equip step (`strategy_driver.py`)**

In `objective_step_goal`, the `isinstance(step, ObtainItem)` gear branch currently does:

```python
        slots = ITEM_TYPE_TO_SLOTS.get(stats.type_) if stats is not None else None
        if slots:
            return _equippable_goal(step.code, slots[0], state, game_data)
```

Change the destination slot to honor the step's slot:

```python
        slots = ITEM_TYPE_TO_SLOTS.get(stats.type_) if stats is not None else None
        if slots:
            dest_slot = step.slot if step.slot is not None else slots[0]
            return _equippable_goal(step.code, dest_slot, state, game_data)
```

And in the intermediate-step branch that targets the root, change `root_slots[0]` to honor `root.slot`:

```python
            if root_slots:
                dest_slot = root.slot if root.slot is not None else root_slots[0]
                upgrade = UpgradeEquipmentGoal(initial_equipment=state.equipment,
                                               committed_target=(root.code, dest_slot))
```

- [ ] **Step 4: Use the slot in scoring (`strategy.py`)**

Add a helper on `StrategyEngine` (next to `_gear_slot`):

```python
    def _root_slot(self, root: MetaGoal, state: WorldState,
                   game_data: GameData) -> str | None:
        """The slot a gear root scores against: the root's explicit slot when it
        carries one (per-slot gear roots), else the code's target_gear slot."""
        if isinstance(root, ObtainItem) and root.slot is not None:
            return root.slot
        code = root.code if isinstance(root, ObtainItem) else ""
        return self._gear_slot(code, state, game_data)
```

In `_base_prior`, the `ObtainItem` branch — replace `slot = self._gear_slot(root.code, state, game_data)` with `slot = self._root_slot(root, state, game_data)`.

In `_marginal`, the `ObtainItem` gear branch — replace its `slot = self._gear_slot(root.code, ...)` line with `slot = self._root_slot(root, state, game_data)` so the equipped-current-value and empty-slot urgency are computed for the root's OWN slot.

- [ ] **Step 5: Run tests to verify pass**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py tests/test_ai/test_tiers_strategy.py -v`
Expected: PASS — new tests plus all pre-existing (slot-less roots take the `root.slot is None` path → unchanged scoring/equip).

- [ ] **Step 6: Integration regression + full gate, then commit**

Add to `tests/test_ai/test_strategy_driver.py` an end-to-end check that the arbiter equips the second ring:

```python
def test_arbiter_equips_second_ring_into_empty_slot():
    """Reported 2026-06-14: copper_ring worn in ring1, spare in inventory, ring2
    empty -> the arbiter's chosen goal equips the spare into ring2_slot."""
    gd = GameData()
    gd._item_stats = {"copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                               attack={"fire": 6})}
    gd._crafting_recipes = {"copper_ring": {"bar": 1}}
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    obj = CharacterObjective.from_game_data(gd)
    state = make_state(level=5, inventory={"copper_ring": 1},
                       equipment={"ring1_slot": "copper_ring"})
    eng = StrategyEngine(obj, BalancedPersonality())
    d = eng.decide(state, gd)
    # ring2 root is the live gear target; its step is the equip into ring2_slot.
    assert d.chosen_root == ObtainItem("copper_ring", slot="ring2_slot")
```

Run: `uv run pytest && uv run mypy src/`
Expected: 0 fail, 0 warn, 0 skip, 100% coverage; mypy clean.

```bash
git add src/artifactsmmo_cli/ai/strategy_driver.py src/artifactsmmo_cli/ai/tiers/strategy.py tests/test_ai/test_strategy_driver.py tests/test_ai/test_tiers_strategy.py
git commit -m "feat(ai): slot-aware equip + scoring so the 2nd ring slot is filled"
```

---

## Final verification

- [ ] `uv run pytest` → 0 errors, 0 warnings, 0 skipped, 100% coverage on `src/`.
- [ ] `uv run mypy src/` → clean.
- [ ] Manual: run watch mode with a character holding spare rings → it equips a 2nd ring into ring2_slot.

## Notes

- **Backward compatibility is the invariant:** every existing slot-less `ObtainItem` runs the `slot is None` path — same `is_satisfied`, equality, and repr. The equippable-goal formal/test semantics are exercised by those slot-less roots and must stay green; if any go red it means a path lost the `slot is None` branch.
- **Curate, don't defer:** Tasks 3 and 4 will turn some existing gear-root/scoring assertions slot-tagged — update them in the same task (the spec's ripple list).
- **No engine/combat changes**; equip_value / ranking magnitudes are unchanged — this only adds slot identity to gear roots + the rings dup-fill.
```
