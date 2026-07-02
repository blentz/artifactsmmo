# Learned Per-Monster Potion Economy — Implementation Plan (Phase 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Learn per-monster heal-potion demand from real fights (equipped-utility-slot delta = potions expended, normalized to HP-healed) and size provisioning + crafting from it, seeded by the `predict_win` damage model until samples exist.

**Architecture:** A new `Cycle.consumables_expended_json` column captures what a fight consumed; a warmup-gated `LearningStore.hp_healed_per_fight(monster)` averages HP-healed over recent wins; `potion_provision_qty_pure` (a NEW proven core, ceil-div `hp_need/restore` clamped by held + max_stack) replaces the win-rate `marginal_potion_qty_pure`; the craft baseline scales to the active target monster's demand. Cold-start `hp_need` comes from `expected_damage_per_fight` extracted from `predict_win`.

**Tech Stack:** Python 3.13, SQLModel (LearningStore SQLite), Lean 4 + Mathlib (formal cores), pytest + Hypothesis (differential), `uv`.

## Global Constraints

- ALWAYS prefix Python commands with `uv run` (binary at `/home/blentz/.local/bin/uv` in this env).
- ONE behavioral class per file. No inline imports (imports at top, absolute). Never `if TYPE_CHECKING`. Never catch `Exception`. No multiple implementations — fix in place.
- Use only API data or fail with an error; no defaulting game data.
- Testing success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage. Tests in `tests/`. Use the real test suite (no throwaway scripts).
- Decision cores get formal lockstep: Lean model + differential (`formal/diff/`) + mutation (`formal/diff/mutate.py`), gate part (d) globs `formal/diff/`. Run `formal/sim` regen only if game-data shape changes (it does not here).
- Verification per task: `uv run pytest <targeted> --no-cov` green; full-gate at the end.

---

### Task 1: `Cycle.consumables_expended_json` column

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/models.py` (CycleBase, near `delta_skill_xp_json` ~line 61)
- Test: `tests/test_ai/test_learning_store.py`

**Interfaces:**
- Produces: `Cycle.consumables_expended_json: str` (default `"{}"`) — JSON `{item_code: qty_consumed}` for the cycle.

- [ ] **Step 1: Write the failing test**
```python
def test_cycle_consumables_expended_json_roundtrips(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "c.db"), character="hero")
    store.start_session()
    store.record_cycle(Cycle(
        ts="2026-07-02T00:00:00+00:00", session_id="s", cycle_index=0,
        character="hero", outcome="ok", action_repr="Fight(red_slime)",
        action_class="FightAction", consumables_expended_json='{"small_health_potion": 2}'))
    with Session(store._engine) as s:
        row = list(s.exec(select(Cycle).where(Cycle.action_repr == "Fight(red_slime)")))[0]
    assert row.consumables_expended_json == '{"small_health_potion": 2}'
    store.close()

def test_cycle_consumables_expended_json_defaults_empty(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "c.db"), character="hero")
    store.start_session()
    store.record_cycle(Cycle(ts="2026-07-02T00:00:01+00:00", session_id="s",
        cycle_index=1, character="hero", outcome="ok", action_repr="Rest",
        action_class="RestAction"))
    with Session(store._engine) as s:
        row = list(s.exec(select(Cycle).where(Cycle.action_repr == "Rest")))[0]
    assert row.consumables_expended_json == "{}"
    store.close()
```

- [ ] **Step 2: Run — expect FAIL** (`AttributeError`/unexpected kwarg `consumables_expended_json`)
Run: `uv run pytest tests/test_ai/test_learning_store.py -k consumables_expended -v --no-cov`

- [ ] **Step 3: Add the field** in `models.py` CycleBase, next to `delta_skill_xp_json`:
```python
    # Items consumed this cycle as JSON {item_code: qty}. Sparse — non-empty
    # only on fights that consumed equipped utility consumables. Generalizes
    # to any utility effect (Phase 2 resolves each code's effect).
    consumables_expended_json: str = Field(default="{}")
```

- [ ] **Step 4: Run — expect PASS.** Run: `uv run pytest tests/test_ai/test_learning_store.py -k consumables_expended -v --no-cov`

- [ ] **Step 5: Commit**
```bash
git add src/artifactsmmo_cli/ai/learning/models.py tests/test_ai/test_learning_store.py
git commit -m "feat(learning): Cycle.consumables_expended_json column"
```

---

### Task 2: Player records equipped-utility delta on fight cycles

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` — `_record_learning_cycle` (~1843–1910); add a `_compute_consumables_expended` helper next to `_compute_drops`.
- Test: `tests/test_ai/test_player_learning.py`

**Interfaces:**
- Consumes: `WorldState.equipment` (dict slot→code), `WorldState.utility1_slot_quantity`, `WorldState.utility2_slot_quantity`.
- Produces: `_compute_consumables_expended(prev, new) -> dict[str, int]`; `_record_learning_cycle` persists it into `consumables_expended_json`.

- [ ] **Step 1: Write the failing test** (helper is pure — test it directly)
```python
def test_compute_consumables_expended_counts_utility_drop():
    player = GamePlayer(character="hero")
    prev = make_state(equipment={"utility1_slot": "small_health_potion"})
    prev = dataclasses.replace(prev, utility1_slot_quantity=5, utility2_slot_quantity=0)
    new = dataclasses.replace(prev, utility1_slot_quantity=2)
    assert player._compute_consumables_expended(prev, new) == {"small_health_potion": 2}

def test_compute_consumables_expended_empty_when_no_drop():
    player = GamePlayer(character="hero")
    prev = make_state(equipment={"utility1_slot": "small_health_potion"})
    prev = dataclasses.replace(prev, utility1_slot_quantity=5)
    assert player._compute_consumables_expended(prev, prev) == {}
```

- [ ] **Step 2: Run — expect FAIL** (`_compute_consumables_expended` missing).
Run: `uv run pytest tests/test_ai/test_player_learning.py -k compute_consumables -v --no-cov`

- [ ] **Step 3: Implement the helper + wire it** in `player.py`:
```python
    @staticmethod
    def _compute_consumables_expended(prev: WorldState, new: WorldState) -> dict[str, int]:
        """Utility consumables auto-consumed this cycle: per utility slot, the
        drop in that slot's equipped quantity (only positive drops; an equip
        raises the quantity and is not an expenditure)."""
        expended: dict[str, int] = {}
        for slot, prev_qty, new_qty in (
            ("utility1_slot", prev.utility1_slot_quantity, new.utility1_slot_quantity),
            ("utility2_slot", prev.utility2_slot_quantity, new.utility2_slot_quantity),
        ):
            code = prev.equipment.get(slot)
            drop = prev_qty - new_qty
            if code is not None and drop > 0:
                expended[code] = expended.get(code, 0) + drop
        return expended
```
Then in `_record_learning_cycle`, before building `cycle`:
```python
        consumables = self._compute_consumables_expended(prev_state, new_state)
```
and add to the `Cycle(...)` kwargs:
```python
            consumables_expended_json=json.dumps(consumables, ensure_ascii=False, sort_keys=True),
```

- [ ] **Step 4: Run — expect PASS.** Run: `uv run pytest tests/test_ai/test_player_learning.py -k compute_consumables -v --no-cov`

- [ ] **Step 5: Commit**
```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player_learning.py
git commit -m "feat(learning): record equipped-utility expenditure per cycle"
```

---

### Task 3: `LearningStore.hp_healed_per_fight` accessor

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/store.py` (mirror `success_rate` / `_action_class_cost_median`, ~294–316).
- Test: `tests/test_ai/test_learning_store.py`

**Interfaces:**
- Consumes: `Cycle.action_repr == f"Fight({monster})"`, `Cycle.outcome == "ok"`, `Cycle.consumables_expended_json`.
- Produces: `hp_healed_per_fight(self, monster_code: str, restore_of: Callable[[str], int], window: int = WINDOW_ACTION) -> float | None` — mean HP-healed over the last-`window` winning `Fight(monster)` cycles; `None` below `WARMUP_MIN_SAMPLES`. Zero-consumption wins count as 0 healed (so easy fights pull the mean DOWN — no over-provisioning).

- [ ] **Step 1: Write the failing test**
```python
def _restore_of(code: str) -> int:
    return {"small_health_potion": 30}.get(code, 0)

def test_hp_healed_per_fight_none_below_warmup(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "h.db"), character="hero")
    store.start_session()
    for i in range(4):  # < WARMUP_MIN_SAMPLES
        store.record_cycle(Cycle(ts=f"2026-07-02T00:00:0{i}+00:00", session_id="s",
            cycle_index=i, character="hero", outcome="ok", action_repr="Fight(red_slime)",
            action_class="FightAction", consumables_expended_json='{"small_health_potion": 2}'))
    assert store.hp_healed_per_fight("red_slime", _restore_of) is None
    store.close()

def test_hp_healed_per_fight_means_over_wins(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "h.db"), character="hero")
    store.start_session()
    # 5 wins: three consumed 2 potions (60 HP), two consumed 0 (0 HP) -> mean 36.0
    exps = ['{"small_health_potion": 2}'] * 3 + ["{}"] * 2
    for i, e in enumerate(exps):
        store.record_cycle(Cycle(ts=f"2026-07-02T00:00:1{i}+00:00", session_id="s",
            cycle_index=i, character="hero", outcome="ok", action_repr="Fight(red_slime)",
            action_class="FightAction", consumables_expended_json=e))
    # a loss must be ignored
    store.record_cycle(Cycle(ts="2026-07-02T00:00:20+00:00", session_id="s",
        cycle_index=9, character="hero", outcome="error:fight_lost",
        action_repr="Fight(red_slime)", action_class="FightAction",
        consumables_expended_json='{"small_health_potion": 5}'))
    assert store.hp_healed_per_fight("red_slime", _restore_of) == 36.0
    store.close()
```

- [ ] **Step 2: Run — expect FAIL** (`hp_healed_per_fight` missing).
Run: `uv run pytest tests/test_ai/test_learning_store.py -k hp_healed_per_fight -v --no-cov`

- [ ] **Step 3: Implement** in `store.py` (uses `json`, `Callable`, `warmup_gated_median`/`WARMUP_MIN_SAMPLES` — add imports if absent; a mean helper is fine inline):
```python
    def hp_healed_per_fight(self, monster_code: str,
                            restore_of: Callable[[str], int],
                            window: int = WINDOW_ACTION) -> float | None:
        """Mean HP-healed per WON Fight(monster) over the last `window`; None below
        WARMUP_MIN_SAMPLES. hp_healed per row = sum(qty * restore_of(code)) over the
        cycle's consumables_expended_json (empty -> 0). `restore_of` supplies the
        per-code restore so the store stays GameData-free."""
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle.consumables_expended_json)
                    .where(
                        Cycle.character == self._character,
                        Cycle.action_repr == f"Fight({monster_code})",
                        Cycle.outcome == "ok",
                    )
                    .order_by(col(Cycle.ts).desc())
                    .limit(window)
                )
                rows = list(s.exec(stmt))
        except SQLAlchemyError:
            return None
        if len(rows) < WARMUP_MIN_SAMPLES:
            return None
        healed: list[float] = []
        for raw in rows:
            consumed = json.loads(raw) if raw else {}
            healed.append(float(sum(qty * restore_of(code) for code, qty in consumed.items())))
        return sum(healed) / len(healed)
```

- [ ] **Step 4: Run — expect PASS.** Run: `uv run pytest tests/test_ai/test_learning_store.py -k hp_healed_per_fight -v --no-cov`

- [ ] **Step 5: Commit**
```bash
git add src/artifactsmmo_cli/ai/learning/store.py tests/test_ai/test_learning_store.py
git commit -m "feat(learning): hp_healed_per_fight per-monster demand accessor"
```

---

### Task 4: `expected_damage_per_fight` cold-start seed

**Files:**
- Create: `src/artifactsmmo_cli/ai/expected_damage.py` (one function; keeps `combat.py`'s proven `predict_win` untouched).
- Test: `tests/test_ai/test_expected_damage.py`

**Interfaces:**
- Consumes: `combat._element_damage`, `combat._expected_hit`, `game_data.monster_*`, `state` (player attack/resist/hp).
- Produces: `expected_damage_per_fight(state: WorldState, game_data: GameData, monster_code: str) -> int` — expected total damage taken over a fight = `round(monster_per_turn_damage) * rounds_to_kill`; `0` when unwinnable/unknown (caller won't fight). Mirrors `predict_win`'s `raw_monster` (per-turn monster damage vs player resist) and `rounds_to_kill = ceil(monster_hp / player_kill_step)` using the SAME `_element_damage`/`_expected_hit` primitives, so it cannot drift from the verdict's damage model.

- [ ] **Step 1: Write the failing test** (fixture mirrors `test_combat.py::_gd`; pick a monster where damage×rounds is a known integer)
```python
def test_expected_damage_positive_for_winnable_monster():
    gd = _gd(hp=30, attack={"fire": 10}, code="slime")  # from test_combat helpers
    state = make_state(level=5, hp=200, max_hp=200)
    dmg = expected_damage_per_fight(state, gd, "slime")
    assert dmg > 0
    # equals monster per-turn damage * rounds_to_kill (both from predict_win primitives)

def test_expected_damage_zero_when_unknown_monster():
    gd = _gd(hp=30, code="slime")
    assert expected_damage_per_fight(make_state(), gd, "ghost") == 0
```

- [ ] **Step 2: Run — expect FAIL** (module/function missing).
Run: `uv run pytest tests/test_ai/test_expected_damage.py -v --no-cov`

- [ ] **Step 3: Implement** `expected_damage.py` — recompute `raw_monster` and `rounds_to_kill` exactly as `combat.predict_win` (lines ~110–147): monster per-turn damage via `_element_damage(m_attack, 0, player_resist)` summed over `ELEMENTS`, scaled by monster crit like `_expected_hit`; `rounds_to_kill = ceil(monster_hp / player_kill_step)` where `player_kill_step` is the player's per-turn damage (`_expected_hit(player→monster)`). Return `round(raw_monster) * rounds_to_kill`; `0` on any unknown-monster `KeyError`-guarded path (guard with `game_data` presence checks, not `try/except Exception`). **On execution, read `combat.predict_win` in full and reuse its exact intermediate formulas — this is a thin reader, not a second model.**

- [ ] **Step 4: Run — expect PASS.** Run: `uv run pytest tests/test_ai/test_expected_damage.py -v --no-cov`

- [ ] **Step 5: Commit**
```bash
git add src/artifactsmmo_cli/ai/expected_damage.py tests/test_ai/test_expected_damage.py
git commit -m "feat(combat): expected_damage_per_fight cold-start seed"
```

---

### Task 5: `potion_provision_qty_pure` new proven pure core (Python)

**Files:**
- Create: `src/artifactsmmo_cli/ai/potion_provision_qty.py`
- Test: `tests/test_ai/test_potion_provision_qty.py`

**Interfaces:**
- Produces: `potion_provision_qty_pure(hp_need: int, potion_hp_restore: int, held_heal_qty: int, utility_slot_filled: bool, max_stack: int) -> int`.

- [ ] **Step 1: Write the failing tests**
```python
def test_zero_when_slot_filled():
    assert potion_provision_qty_pure(100, 30, 10, True, 100) == 0
def test_zero_when_none_held_or_zero_restore():
    assert potion_provision_qty_pure(100, 30, 0, False, 100) == 0
    assert potion_provision_qty_pure(100, 0, 10, False, 100) == 0
def test_ceil_div_sizing():
    # need 100 HP, 30/potion -> ceil(100/30)=4
    assert potion_provision_qty_pure(100, 30, 10, False, 100) == 4
def test_clamped_by_held():
    assert potion_provision_qty_pure(100, 30, 2, False, 100) == 2
def test_clamped_by_max_stack():
    assert potion_provision_qty_pure(10_000, 30, 500, False, 100) == 100
```

- [ ] **Step 2: Run — expect FAIL.** Run: `uv run pytest tests/test_ai/test_potion_provision_qty.py -v --no-cov`

- [ ] **Step 3: Implement**
```python
"""Potion-provision quantity: how many heal potions to equip for a fight,
sized to the monster's learned/seeded HP-need. Pure decision core (proved in
formal/Formal/PotionProvisionQty.lean, differential + mutation gated). Replaces
the win-rate heuristic marginal_potion_qty_pure."""


def potion_provision_qty_pure(
    hp_need: int, potion_hp_restore: int, held_heal_qty: int,
    utility_slot_filled: bool, max_stack: int,
) -> int:
    """Potions to equip = ceil(hp_need / potion_hp_restore), clamped to what is
    held and to max_stack. 0 when the slot is already filled, nothing is held, or
    the potion restores nothing (avoids divide-by-zero and a useless equip)."""
    if utility_slot_filled or held_heal_qty <= 0 or potion_hp_restore <= 0:
        return 0
    desired = (hp_need + potion_hp_restore - 1) // potion_hp_restore  # ceil
    return min(desired, held_heal_qty, max_stack)
```

- [ ] **Step 4: Run — expect PASS.** Run: `uv run pytest tests/test_ai/test_potion_provision_qty.py -v --no-cov`

- [ ] **Step 5: Commit**
```bash
git add src/artifactsmmo_cli/ai/potion_provision_qty.py tests/test_ai/test_potion_provision_qty.py
git commit -m "feat(ai): potion_provision_qty_pure decision core (ceil hp_need/restore)"
```

---

### Task 6: Lean model + differential + mutation for `potion_provision_qty` (formal-development)

**Files:**
- Create: `formal/Formal/PotionProvisionQty.lean`
- Modify: `formal/Formal.lean` (add `import Formal.PotionProvisionQty`), `formal/Oracle.lean` (add `runPotionProvisionQty` + dispatch on `"potion_provision_qty"`), `formal/diff/mutate.py` (add anchors for the new src file)
- Create: `formal/diff/test_potion_provision_qty_diff.py`

**REQUIRED SUB-SKILL:** Use `formal-development` — this is a decision core needing kernel-proved theorems + a differential harness that runs production against the Lean oracle + mutation anchors. Mirror the retiring `formal/Formal/MarginalPotionQty.lean` (namespace `Formal.MarginalPotionQty`, `ceilDiv`, theorems `qty_le_max`/`qty_le_held`) and `formal/diff/test_marginal_potion_qty_diff.py`.

**Interfaces:**
- Produces: Lean `Formal.PotionProvisionQty.potionProvisionQty (hpNeed potionRestore heldHealQty : Int) (slotFilled : Bool) (maxStack : Int) : Int`, dispatched by Oracle key `"potion_provision_qty"`.

- [ ] **Step 1: Write `PotionProvisionQty.lean`** — `def potionProvisionQty` computing `if slotFilled ∨ heldHealQty ≤ 0 ∨ potionRestore ≤ 0 then 0 else min (min (ceilDiv hpNeed potionRestore) heldHealQty) maxStack` with `ceilDiv a b := (a + b - 1) / b`. Prove: `provision_le_max : potionProvisionQty … ≤ maxStack` (when maxStack ≥ 0), `provision_le_held : potionProvisionQty … ≤ heldHealQty` (when heldHealQty ≥ 0), `provision_nonneg`. (Mirror MarginalPotionQty's proof shapes.)

- [ ] **Step 2: Register + oracle** — add the import to `Formal.lean`; add `runPotionProvisionQty (args : Array Json)` to `Oracle.lean` reading 3 Int + 1 Bool + 1 Int and returning `{"qty": …}`; add the dispatch `else if kind == "potion_provision_qty" then runPotionProvisionQty args`.

- [ ] **Step 3: Build Lean** — Run: `cd formal && lake build` (expect success; fix proof obligations until green — see formal-development).

- [ ] **Step 4: Write the differential test** `formal/diff/test_potion_provision_qty_diff.py` — Hypothesis over `(hp_need, potion_restore, held, slot_filled, max_stack)` in realistic ranges, asserting `run_oracle("potion_provision_qty", [...])["qty"] == potion_provision_qty_pure(...)`. Mirror `test_marginal_potion_qty_diff.py`.

- [ ] **Step 5: Add mutation anchors** in `formal/diff/mutate.py` — a `POTION_PROVISION_QTY_SRC` path + anchors that kill on: ceil→floor (`- 1` deletion), held-clamp deletion, max_stack-clamp deletion, slot-filled guard flip.

- [ ] **Step 6: Run differential + mutation** — Run: `cd formal && lake build oracle` then `uv run pytest formal/diff/test_potion_provision_qty_diff.py --no-cov -q` (PASS); `uv run python formal/diff/mutate.py --only potion_provision_qty` (all anchors KILLED — consult mutate.py for the exact invocation).

- [ ] **Step 7: Commit**
```bash
git add formal/Formal/PotionProvisionQty.lean formal/Formal.lean formal/Oracle.lean formal/diff/test_potion_provision_qty_diff.py formal/diff/mutate.py
git commit -m "feat(formal): PotionProvisionQty proven core + differential + mutation"
```

---

### Task 7: Wire provisioning to learned HP-need + retire `marginal_potion_qty` usage

**Files:**
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` — `_marginal_provision_goal` (~568–592); imports (drop `marginal_potion_qty_pure`, `MARGINAL_WINRATE_THRESHOLD`, `FULL_STACK_WINRATE`; keep `UTILITY_SLOT_MAX_STACK`; add `potion_provision_qty_pure`, `hp_healed_per_fight` via `history`, `expected_damage_per_fight`, `best_held_heal_restore`).
- Test: `tests/test_ai/test_strategy_driver.py` (and/or `test_provision_marginal_fight.py`)

**Interfaces:**
- Consumes: `history.hp_healed_per_fight` (Task 3), `expected_damage_per_fight` (Task 4), `potion_provision_qty_pure` (Task 5), `best_held_heal`/`best_held_heal_restore` (consumable_supply).
- Produces: unchanged `ProvisionMarginalFightGoal(target_monster, heal_code, quantity)`; quantity now HP-need-based.

- [ ] **Step 1: Write the failing tests**
```python
def test_marginal_provision_uses_learned_hp_need(...):
    # history has >=5 winning Fight(red_slime) averaging 90 HP healed;
    # best held heal restores 30 -> qty = ceil(90/30) = 3
    ...
    goal = sd._marginal_provision_goal(ctx, state, gd, store)
    assert isinstance(goal, ProvisionMarginalFightGoal)
    assert goal._quantity == 3

def test_marginal_provision_seeds_from_expected_damage_when_cold(...):
    # no history for the monster -> hp_need = expected_damage_per_fight seed
    # assert quantity == ceil(seed / restore), > 0
    ...
```
(Build fixtures from the Task-3 store helper + a `_gd` with the monster's stats; `ctx.combat_monster = "red_slime"`, utility slots empty, held heal present.)

- [ ] **Step 2: Run — expect FAIL.** Run: `uv run pytest tests/test_ai/test_strategy_driver.py -k marginal_provision -v --no-cov`

- [ ] **Step 3: Rewrite `_marginal_provision_goal`** body (keep the early guards):
```python
    heal_code = best_held_heal(state, game_data)
    if heal_code is None:
        return None
    held = state.inventory.get(heal_code, 0)
    restore = best_held_heal_restore(state, game_data)
    learned = history.hp_healed_per_fight(monster, game_data.hp_restore_of) \
        if hasattr(history, "hp_healed_per_fight") else None
    hp_need = int(learned) if learned is not None \
        else expected_damage_per_fight(state, game_data, monster)
    qty = potion_provision_qty_pure(hp_need, restore, held,
                                    utility_slot_filled=False, max_stack=UTILITY_SLOT_MAX_STACK)
    if qty <= 0:
        return None
    return ProvisionMarginalFightGoal(target_monster=monster, heal_code=heal_code, quantity=qty)
```
Add a `GameData.hp_restore_of(code) -> int` thin accessor (returns `item_stats(code).hp_restore` or 0) in `game_data.py` if not present, with its own unit test (round-trip). Update `strategy_driver` imports accordingly.

- [ ] **Step 4: Run — expect PASS** (targeted) then the strategy suite.
Run: `uv run pytest tests/test_ai/test_strategy_driver.py tests/test_ai/test_provision_marginal_fight.py --no-cov -q`

- [ ] **Step 5: Commit**
```bash
git add src/artifactsmmo_cli/ai/strategy_driver.py src/artifactsmmo_cli/ai/game_data.py tests/test_ai/
git commit -m "feat(strategy): provision potions from learned/seeded HP-need"
```

---

### Task 8: Craft baseline scales to target-monster demand

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/craft_potions.py` — `_baseline` (~63–65) and its call sites (it currently takes only `level`); thread `state`/`game_data`/`history` so it can read the target-monster demand.
- Test: `tests/test_ai/test_craft_potions.py`

**Interfaces:**
- Consumes: `potion_provision_qty_pure`, `hp_healed_per_fight`/`expected_damage_per_fight`, `ctx.combat_monster` (or the goal's known target), `target_potion` restore.
- Produces: `_baseline` returns `max(level_baseline, provision_target_for_target_monster)` clamped to `UTILITY_SLOT_MAX_STACK`; unchanged when no target monster / no data.

- [ ] **Step 1: Write the failing tests**
```python
def test_baseline_rises_for_hard_target_monster(...):
    # target monster demands ceil(hp_need/restore)=20 potions > level_baseline(10)
    # -> _baseline == 20
def test_baseline_unchanged_when_no_target(...):
    # no combat target -> _baseline == level_baseline
```

- [ ] **Step 2: Run — expect FAIL.** Run: `uv run pytest tests/test_ai/test_craft_potions.py -k baseline -v --no-cov`

- [ ] **Step 3: Implement** — compute `level_baseline = potion_baseline_pure(level, …)` as today; compute `monster_demand` = `potion_provision_qty_pure(hp_need(target), target_potion_restore, big_held, False, UTILITY_SLOT_MAX_STACK)` where `hp_need(target)` is `hp_healed_per_fight or expected_damage_per_fight`; return `min(max(level_baseline, monster_demand), UTILITY_SLOT_MAX_STACK)`. Use a large sentinel for `held_heal_qty` here (baseline is a CRAFT target, not limited by current holdings). When no target monster or no game data, return `level_baseline` unchanged. Update `_baseline` signature + its callers (`is_satisfied`, `value`, `craft_potions_fires`) to pass the needed context; keep pure-core boundaries intact.

- [ ] **Step 4: Run — expect PASS** then full craft-potions + guards suites.
Run: `uv run pytest tests/test_ai/test_craft_potions.py tests/test_ai/test_tiers_guards.py --no-cov -q`

- [ ] **Step 5: Commit**
```bash
git add src/artifactsmmo_cli/ai/goals/craft_potions.py tests/test_ai/test_craft_potions.py
git commit -m "feat(craft): scale potion baseline to active target-monster demand"
```

---

### Task 9: Retire `marginal_potion_qty` (Python + Lean + Oracle + differential + mutation)

**Files:**
- Delete: `src/artifactsmmo_cli/ai/marginal_potion_qty.py`, `formal/Formal/MarginalPotionQty.lean`, `formal/diff/test_marginal_potion_qty_diff.py`
- Modify: `formal/Formal.lean` (drop `import Formal.MarginalPotionQty`), `formal/Oracle.lean` (drop `import`, `runMarginalPotionQty`, the `"marginal_potion_qty"` dispatch), `formal/diff/mutate.py` (drop `MARGINAL_POTION_QTY_SRC` + its anchors)

**Interfaces:** none produced. Precondition: `grep -rn "marginal_potion_qty\|MarginalPotionQty" src tests formal` returns ONLY the artifacts being deleted (Task 7 removed the last live caller).

- [ ] **Step 1: Confirm no live references**
Run: `grep -rn "marginal_potion_qty\|MarginalPotionQty\|marginalPotionQty" src tests formal`
Expected: only the files listed above (no `src` consumer, no other test).

- [ ] **Step 2: Delete the Python core + its test; remove the mutate.py entry**
```bash
git rm src/artifactsmmo_cli/ai/marginal_potion_qty.py formal/diff/test_marginal_potion_qty_diff.py
```
Edit `formal/diff/mutate.py`: remove `MARGINAL_POTION_QTY_SRC` and its mutation-anchor block.

- [ ] **Step 3: Remove the Lean model + registration**
```bash
git rm formal/Formal/MarginalPotionQty.lean
```
Edit `formal/Formal.lean`: drop `import Formal.MarginalPotionQty`. Edit `formal/Oracle.lean`: drop the import, `runMarginalPotionQty`, and the `"marginal_potion_qty"` dispatch branch.

- [ ] **Step 4: Rebuild + verify no orphans**
Run: `cd formal && lake build` (PASS — no dangling import/def). Then `grep -rn "marginal_potion_qty\|MarginalPotionQty" . --include=*.py --include=*.lean` → empty.

- [ ] **Step 5: Commit**
```bash
git add -A
git commit -m "chore(formal): retire marginal_potion_qty (superseded by potion_provision_qty)"
```

---

### Task 10: Full gate

**Files:** none (verification only).

- [ ] **Step 1: Unit suite @ 100% coverage**
Run: `uv run pytest tests/ -q` — expect all pass, 100% coverage, 0 warnings/skips.

- [ ] **Step 2: mypy**
Run: `uv run mypy src/` — expect clean.

- [ ] **Step 3: Lean build**
Run: `cd formal && lake build > /tmp/lake.log 2>&1; echo EXIT=$?; grep -iE "error:|build failed|sorry" /tmp/lake.log` — expect `EXIT=0`, no errors/sorry.

- [ ] **Step 4: Differential gate**
Run: `cd formal && lake build oracle && cd .. && uv run pytest formal/diff/ -q --no-cov -n auto` — expect all pass (new `potion_provision_qty` diff present, `marginal_potion_qty` diff gone; snapshot `*_match_live` may need `reference_snapshot_regen` if live drifted again).

- [ ] **Step 5: Mutation gate for the new core**
Run: `uv run python formal/diff/mutate.py` (or scoped to `potion_provision_qty`) — expect all anchors KILLED.

- [ ] **Step 6: Merge**
```bash
git checkout main
git merge --no-ff feat/learned-potion-economy -m "Merge: learned per-monster potion economy (Phase 1)"
```

---

## Self-review notes

- **Spec coverage:** §1 recording → Tasks 1–2; §2 accessor → Task 3; §3 seed + provision core → Tasks 4–7; §4 craft hook → Task 8; formal obligations (new core + retire old) → Tasks 6, 9; L50 threading → conservative-safe, no proof task in Phase 1 (Phase 1.5 tracked separately). All covered.
- **New `GameData.hp_restore_of`** is introduced in Task 7 (used by Tasks 7–8) — a thin `item_stats(code).hp_restore or 0` accessor; add with a unit test in that task.
- **Type consistency:** `hp_healed_per_fight(monster_code, restore_of, window)` (Task 3) is the same signature consumed in Tasks 7–8; `potion_provision_qty_pure(hp_need, potion_hp_restore, held_heal_qty, utility_slot_filled, max_stack)` identical across Tasks 5, 7, 8 and the Lean core (Task 6).
- **Gate-green ordering:** the new core is added + proven (Tasks 5–6) and the last live caller migrated (Task 7) BEFORE the old core is retired (Task 9), so every commit leaves the differential gate green.
