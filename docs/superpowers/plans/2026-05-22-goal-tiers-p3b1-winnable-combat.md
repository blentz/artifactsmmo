# Goal Tiers — P3b.1 Winnable Combat Target Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gate the strategy's combat target by a documented-formula combat-outcome prediction (player vs monster stats) plus a learned-win-rate veto, so the bot only fights monsters it can actually win.

**Architecture:** Add player combat stats to `WorldState` and monster crit/initiative to `GameData`; a new pure `ai/combat.py:predict_win` implements the documented per-element damage + crit + initiative + 100-turn formula; `player.py` combines that prediction with the existing win-rate veto in `_is_winnable`, reworks `_pick_winnable_monster` to filter by it, and gates `farm_target` in `_build_goals`.

**Tech Stack:** Python 3.13, `uv run` (pytest, ruff, mypy --strict), pydantic/dataclasses. Source spec: `docs/superpowers/specs/2026-05-22-goal-tiers-p3b1-winnable-combat-design.md`.

---

## File Structure

- `src/artifactsmmo_cli/ai/world_state.py` — MODIFY: add `attack`, `dmg`, `dmg_elements`, `resistance`, `critical_strike`, `initiative` frozen fields + populate them in `from_character_schema`.
- `src/artifactsmmo_cli/ai/game_data.py` — MODIFY: store monster `critical_strike`/`initiative` in `_load_monsters`; add `monster_hp`, `monster_critical_strike`, `monster_initiative` getters.
- `src/artifactsmmo_cli/ai/combat.py` — CREATE: pure `predict_win(state, game_data, monster_code) -> bool` + helpers.
- `src/artifactsmmo_cli/ai/player.py` — MODIFY: module constants `WIN_RATE_THRESHOLD`/`MIN_WIN_SAMPLES`, new `_is_winnable`, reworked `_pick_winnable_monster`, `_build_goals` `farm_target` gate.
- Tests: `tests/test_ai/test_world_state.py`, `tests/test_ai/test_game_data.py`, `tests/test_ai/test_combat.py` (new), `tests/test_ai/test_player.py`.

Note on conventions: always `uv run`. `ELEMENTS = ("fire", "earth", "water", "air")`. Existing `WorldState` test helper is `tests/test_ai/fixtures.py:make_state`. The `field` import and `from dataclasses import dataclass, field` are already present in both `world_state.py` and `game_data.py`.

---

### Task 1: WorldState combat-stat fields

**Files:**
- Modify: `src/artifactsmmo_cli/ai/world_state.py`
- Test: `tests/test_ai/test_world_state.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ai/test_world_state.py` (it already imports `WorldState` and constructs `CharacterSchema` fixtures — match the existing fixture style in that file; the snippet below shows the assertions, attach them to a character built the same way the other tests in the file build one):

```python
def test_from_character_schema_populates_combat_stats():
    # Build `char` the same way the other tests in this file do (CharacterSchema
    # with attack_*, dmg, dmg_*, res_*, critical_strike, initiative set).
    char = _make_character_schema(
        attack_fire=10, attack_earth=0, attack_water=5, attack_air=0,
        dmg=8, dmg_fire=4, dmg_earth=0, dmg_water=0, dmg_air=0,
        res_fire=0, res_earth=12, res_water=0, res_air=0,
        critical_strike=15, initiative=30,
    )
    state = WorldState.from_character_schema(char)
    assert state.attack == {"fire": 10, "water": 5}        # zeros dropped
    assert state.dmg == 8
    assert state.dmg_elements == {"fire": 4}                # zeros dropped
    assert state.resistance == {"earth": 12}                # zeros dropped
    assert state.critical_strike == 15
    assert state.initiative == 30


def test_combat_stats_default_empty_when_not_supplied():
    state = make_state()  # tests/test_ai/fixtures.py helper
    assert state.attack == {}
    assert state.dmg == 0
    assert state.dmg_elements == {}
    assert state.resistance == {}
    assert state.critical_strike == 0
    assert state.initiative == 0
```

If `test_world_state.py` has no local CharacterSchema builder, reuse whatever the existing tests in that file use to construct a `CharacterSchema` (search the file for `CharacterSchema(`) and add the new attack/dmg/res/crit/initiative kwargs to that call. `make_state` is imported in the file's other tests via `from tests.test_ai.fixtures import make_state`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_world_state.py::test_from_character_schema_populates_combat_stats tests/test_ai/test_world_state.py::test_combat_stats_default_empty_when_not_supplied -v`
Expected: FAIL — `AttributeError: 'WorldState' object has no attribute 'attack'` (and the others).

- [ ] **Step 3: Add the fields**

In `src/artifactsmmo_cli/ai/world_state.py`, add a module-level constant near `SKILL_NAMES` (after line 37):

```python
ELEMENTS = ("fire", "earth", "water", "air")
```

Then add these fields to the `WorldState` dataclass, immediately after the `crafting_target` field (after line 82, keeping them with the other defaulted fields):

```python
    attack: dict[str, int] = field(default_factory=dict)
    """element -> attack value (server-computed total, base + gear). Empty by
    default so non-schema constructions keep working. From attack_{el}."""
    dmg: int = 0
    """Global damage % bonus. Applies to every element. From `dmg`."""
    dmg_elements: dict[str, int] = field(default_factory=dict)
    """element -> per-element damage % bonus. From dmg_{el}."""
    resistance: dict[str, int] = field(default_factory=dict)
    """element -> resistance %. From res_{el}."""
    critical_strike: int = 0
    """Critical-strike chance %. From `critical_strike`."""
    initiative: int = 0
    """Turn-order stat (higher acts first). From `initiative`."""
```

- [ ] **Step 4: Populate them in `from_character_schema`**

In `from_character_schema`, after the `skills`/`skill_xp` loop (after line 126) and before the `cooldown_expires` block, add:

```python
        attack: dict[str, int] = {}
        dmg_elements: dict[str, int] = {}
        resistance: dict[str, int] = {}
        for elem in ELEMENTS:
            atk = getattr(char, f"attack_{elem}", 0)
            if atk:
                attack[elem] = atk
            de = getattr(char, f"dmg_{elem}", 0)
            if de:
                dmg_elements[elem] = de
            res = getattr(char, f"res_{elem}", 0)
            if res:
                resistance[elem] = res
```

Then add these to the `return cls(...)` call (after the `active_events=active_events or {},` line):

```python
            attack=attack,
            dmg=getattr(char, "dmg", 0),
            dmg_elements=dmg_elements,
            resistance=resistance,
            critical_strike=getattr(char, "critical_strike", 0),
            initiative=getattr(char, "initiative", 0),
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_world_state.py -v`
Expected: PASS (all tests in the file, including the two new ones).

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/world_state.py tests/test_ai/test_world_state.py
git commit -m "feat(ai): add player combat stats to WorldState

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Monster crit/initiative + getters in GameData

**Files:**
- Modify: `src/artifactsmmo_cli/ai/game_data.py`
- Test: `tests/test_ai/test_game_data.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ai/test_game_data.py`:

```python
def test_monster_combat_getters_return_stored_values():
    gd = GameData()
    gd._monster_hp = {"chicken": 60}
    gd._monster_critical_strike = {"chicken": 5}
    gd._monster_initiative = {"chicken": 100}
    assert gd.monster_hp("chicken") == 60
    assert gd.monster_critical_strike("chicken") == 5
    assert gd.monster_initiative("chicken") == 100


def test_monster_combat_getters_default_zero_when_unknown():
    gd = GameData()
    assert gd.monster_hp("missing") == 0
    assert gd.monster_critical_strike("missing") == 0
    assert gd.monster_initiative("missing") == 0
```

`GameData` is already imported at the top of `test_game_data.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_game_data.py::test_monster_combat_getters_return_stored_values tests/test_ai/test_game_data.py::test_monster_combat_getters_default_zero_when_unknown -v`
Expected: FAIL — `AttributeError: 'GameData' object has no attribute '_monster_critical_strike'` / `no attribute 'monster_critical_strike'`.

- [ ] **Step 3: Add the dict fields**

In `src/artifactsmmo_cli/ai/game_data.py`, after the `_monster_resistance` field (line 55), add:

```python
    _monster_critical_strike: dict[str, int] = field(default_factory=dict)  # code -> crit %
    _monster_initiative: dict[str, int] = field(default_factory=dict)  # code -> initiative
```

- [ ] **Step 4: Add the getters**

After the existing `monster_resistance` method (after line 224), add:

```python
    def monster_hp(self, code: str) -> int:
        """Max HP of a monster, or 0 when unknown."""
        return self._monster_hp.get(code, 0)

    def monster_critical_strike(self, code: str) -> int:
        """Critical-strike chance % of a monster, or 0 when unknown."""
        return self._monster_critical_strike.get(code, 0)

    def monster_initiative(self, code: str) -> int:
        """Initiative (turn-order) stat of a monster, or 0 when unknown."""
        return self._monster_initiative.get(code, 0)
```

- [ ] **Step 5: Populate them in `_load_monsters`**

In `_load_monsters`, inside the `for mon in result.data:` loop, after the `_monster_resistance[mon.code] = {...}` assignment (after line 526), add:

```python
                self._monster_critical_strike[mon.code] = getattr(mon, "critical_strike", 0)
                self._monster_initiative[mon.code] = getattr(mon, "initiative", 0)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_game_data.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/game_data.py tests/test_ai/test_game_data.py
git commit -m "feat(ai): load monster crit/initiative + add combat getters

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Combat-outcome estimator (`combat.py`)

**Files:**
- Create: `src/artifactsmmo_cli/ai/combat.py`
- Test: `tests/test_ai/test_combat.py` (new)

This is the documented formula (https://docs.artifactsmmo.com/concepts/stats_and_fights):
per element `output = attack + Round(attack × dmg%/100)`, `blocked = Round(output × res%/100)`, net `= max(0, output − blocked)`; `.5` rounds up; crit modelled as expected multiplier `(1 + crit%/100 × 0.5)` (1.5× on a crit% chance); elements summed independently; `dmg%` = global `dmg` + per-element `dmg_el`; monsters have no damage% bonus; `rounds_to_kill = ceil(hp / expected_hit)`; lose if `rounds_to_kill > 100`; initiative decides turn order (player-first ties win on `<=`, else `<`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_combat.py`:

```python
"""Tests for the documented combat-outcome estimator."""

from artifactsmmo_cli.ai.combat import (
    _element_damage,
    _expected_hit,
    _round_half_up,
    predict_win,
)
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state


def _gd(hp, attack=None, resist=None, crit=0, initiative=0, code="mob"):
    gd = GameData()
    gd._monster_hp = {code: hp}
    gd._monster_attack = {code: attack or {}}
    gd._monster_resistance = {code: resist or {}}
    gd._monster_critical_strike = {code: crit}
    gd._monster_initiative = {code: initiative}
    return gd


def test_round_half_up_rounds_half_upward():
    assert _round_half_up(2.5) == 3
    assert _round_half_up(2.4999) == 2
    assert _round_half_up(3.0) == 3


def test_element_damage_applies_bonus_then_resistance():
    # 100 attack + 30% damage = 130 output; 30% resistance blocks Round(130*0.3)=39
    assert _element_damage(100, 30, 30) == 130 - 39


def test_element_damage_clamps_to_zero():
    # full resistance blocks everything (never negative)
    assert _element_damage(10, 0, 100) == 0


def test_expected_hit_sums_elements_and_applies_crit():
    # fire 10 (no bonus/res), water 5 (no bonus/res) = 15 raw; crit 20% -> *1.10
    raw = _expected_hit({"fire": 10, "water": 5}, 0, {}, {}, 20)
    assert raw == 15 * 1.10


def test_predict_win_true_when_player_kills_first():
    state = make_state(max_hp=100, attack={"fire": 30}, initiative=50)
    gd = _gd(hp=30, attack={"fire": 5}, initiative=10)   # player one-shots
    assert predict_win(state, gd, "mob") is True


def test_predict_win_false_when_monster_kills_first():
    state = make_state(max_hp=10, attack={"fire": 1}, initiative=0)
    gd = _gd(hp=1000, attack={"fire": 50}, initiative=100)
    assert predict_win(state, gd, "mob") is False


def test_predict_win_false_when_player_cannot_damage():
    state = make_state(max_hp=100, attack={}, initiative=50)
    gd = _gd(hp=30, attack={"fire": 5})
    assert predict_win(state, gd, "mob") is False


def test_predict_win_true_when_monster_cannot_damage():
    state = make_state(max_hp=100, attack={"fire": 10}, initiative=0)
    gd = _gd(hp=30, attack={}, initiative=100)
    assert predict_win(state, gd, "mob") is True


def test_predict_win_false_when_kill_exceeds_turn_cap():
    state = make_state(max_hp=10000, attack={"fire": 1}, initiative=100)
    gd = _gd(hp=10000, attack={"fire": 1})   # rounds_to_kill = 10000 > 100
    assert predict_win(state, gd, "mob") is False


def test_predict_win_resistance_lets_defender_survive_longer():
    # Monster with high resistance survives more rounds -> can flip a win to a loss.
    state = make_state(max_hp=20, attack={"fire": 20}, initiative=0)
    weak = _gd(hp=40, attack={"fire": 15}, initiative=100)
    armored = _gd(hp=40, attack={"fire": 15}, resist={"fire": 75}, initiative=100, code="mob")
    assert predict_win(state, weak, "mob") is True
    assert predict_win(state, armored, "mob") is False


def test_predict_win_initiative_tie_favors_player():
    # Both kill in the same number of rounds; equal initiative -> player wins.
    state = make_state(max_hp=20, attack={"fire": 20}, initiative=50)
    gd = _gd(hp=20, attack={"fire": 20}, initiative=50)
    assert predict_win(state, gd, "mob") is True
```

`make_state` must accept `attack`, `max_hp`, `initiative` (and the other combat kwargs) and forward them to `WorldState`. If `tests/test_ai/fixtures.py:make_state` does not yet pass these through, extend it to forward `attack`, `dmg`, `dmg_elements`, `resistance`, `critical_strike`, `initiative`, `max_hp` (defaulting to the `WorldState` defaults). Make that fixture change in this step.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_combat.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.combat'`.

- [ ] **Step 3: Implement `combat.py`**

Create `src/artifactsmmo_cli/ai/combat.py`:

```python
"""Combat-outcome estimator implementing the documented artifactsmmo fight
formula (https://docs.artifactsmmo.com/concepts/stats_and_fights).

Pure functions over WorldState + GameData; no API, no RNG. Critical strikes are
modelled as their expected contribution (deterministic) since the planner needs
a stable verdict, not a sampled fight."""

import math

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import ELEMENTS, WorldState

MAX_TURNS = 100
"""A fight unresolved by turn 100 is a loss (documented combat cap)."""


def _round_half_up(value: float) -> int:
    """Round to nearest integer; exact halves round up (documented rule)."""
    return math.floor(value + 0.5)


def _element_damage(attack: int, dmg_pct: int, resist_pct: int) -> int:
    """Net damage for one element: apply the damage % bonus, then subtract the
    defender's resistance %. Never negative."""
    output = attack + _round_half_up(attack * dmg_pct / 100)
    blocked = _round_half_up(output * resist_pct / 100)
    return max(0, output - blocked)


def _expected_hit(
    attack: dict[str, int],
    dmg_global: int,
    dmg_elements: dict[str, int],
    resist: dict[str, int],
    crit: int,
) -> float:
    """Expected per-turn damage across all elements, including the expected
    critical-strike contribution (crit% chance of a 1.5x hit)."""
    raw = sum(
        _element_damage(attack.get(e, 0), dmg_global + dmg_elements.get(e, 0), resist.get(e, 0))
        for e in ELEMENTS
    )
    return raw * (1 + (crit / 100) * 0.5)


def predict_win(state: WorldState, game_data: GameData, monster_code: str) -> bool:
    """True if the documented formula says the player beats the monster.

    Player wins when it reduces the monster to 0 HP no later than the monster
    reduces it to 0 (player-first on an initiative tie). Loses if the kill would
    take more than MAX_TURNS turns."""
    player_hit = _expected_hit(
        state.attack, state.dmg, state.dmg_elements,
        game_data.monster_resistance(monster_code), state.critical_strike,
    )
    if player_hit <= 0:
        return False
    rounds_to_kill = math.ceil(game_data.monster_hp(monster_code) / player_hit)
    if rounds_to_kill > MAX_TURNS:
        return False
    monster_hit = _expected_hit(
        game_data.monster_attack(monster_code), 0, {},
        state.resistance, game_data.monster_critical_strike(monster_code),
    )
    if monster_hit <= 0:
        return True
    rounds_to_die = math.ceil(state.max_hp / monster_hit)
    player_first = state.initiative >= game_data.monster_initiative(monster_code)
    return rounds_to_kill <= rounds_to_die if player_first else rounds_to_kill < rounds_to_die
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_combat.py -v`
Expected: PASS (all listed tests).

- [ ] **Step 5: Lint + type-check the new module**

Run: `uv run ruff check src/artifactsmmo_cli/ai/combat.py && uv run mypy src/artifactsmmo_cli/ai/combat.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/combat.py tests/test_ai/test_combat.py tests/test_ai/fixtures.py
git commit -m "feat(ai): documented combat-outcome estimator (predict_win)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `_is_winnable` (stat prediction + win-rate veto) and reworked `_pick_winnable_monster`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py`
- Test: `tests/test_ai/test_player.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ai/test_player.py` (follow the file's existing pattern for building a `GamePlayer` with `game_data`/`state`/`history` set — mirror `_make_player` in `tests/test_ai/test_task_decision_integration.py` if no closer helper exists in this file). The `predict_win` import path to patch is `artifactsmmo_cli.ai.player.predict_win`:

```python
def test_is_winnable_true_when_predicted_and_no_losing_record(monkeypatch):
    player = _player_with(state=make_state(level=5), history=None)
    monkeypatch.setattr("artifactsmmo_cli.ai.player.predict_win", lambda s, g, c: True)
    assert player._is_winnable("chicken") is True


def test_is_winnable_false_when_prediction_says_lose(monkeypatch):
    player = _player_with(state=make_state(level=5), history=None)
    monkeypatch.setattr("artifactsmmo_cli.ai.player.predict_win", lambda s, g, c: False)
    assert player._is_winnable("chicken") is False


def test_is_winnable_vetoed_by_observed_losses(monkeypatch):
    history = _fake_history(samples=5, rate=0.2)   # >= MIN_WIN_SAMPLES, < WIN_RATE_THRESHOLD
    player = _player_with(state=make_state(level=5), history=history)
    monkeypatch.setattr("artifactsmmo_cli.ai.player.predict_win", lambda s, g, c: True)
    assert player._is_winnable("chicken") is False


def test_is_winnable_ignores_veto_below_min_samples(monkeypatch):
    history = _fake_history(samples=4, rate=0.0)   # too few samples to veto
    player = _player_with(state=make_state(level=5), history=history)
    monkeypatch.setattr("artifactsmmo_cli.ai.player.predict_win", lambda s, g, c: True)
    assert player._is_winnable("chicken") is True


def test_pick_winnable_monster_returns_highest_winnable(monkeypatch):
    gd = GameData()
    gd._monster_level = {"chicken": 1, "cow": 8, "wolf": 4}
    player = _player_with(state=make_state(level=10), history=None, game_data=gd)
    monkeypatch.setattr(player, "_is_winnable", lambda code: code in {"chicken", "wolf"})
    assert player._pick_winnable_monster() == "wolf"   # highest winnable


def test_pick_winnable_monster_none_when_no_winnable(monkeypatch):
    gd = GameData()
    gd._monster_level = {"chicken": 1, "cow": 8}
    player = _player_with(state=make_state(level=10), history=None, game_data=gd)
    monkeypatch.setattr(player, "_is_winnable", lambda code: False)
    assert player._pick_winnable_monster() is None
```

Provide local test helpers in `test_player.py` if they don't already exist:
- `_player_with(state, history, game_data=None)` — constructs `GamePlayer(character="hero", history=history)`, sets `.game_data` (a `GameData()` if not given) and `.state`.
- `_fake_history(samples, rate)` — a lightweight stand-in exposing `sample_count(repr)->samples` and `success_rate(repr)->rate` (a small local class or `unittest.mock.Mock` with those two methods). It need not be a real `LearningStore`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_player.py -k "winnable" -v`
Expected: FAIL — `AttributeError: 'GamePlayer' object has no attribute '_is_winnable'` and `_pick_winnable_monster` returning the old level-gated pick (not filtered by `_is_winnable`).

- [ ] **Step 3: Add module constants + the `predict_win` import**

In `src/artifactsmmo_cli/ai/player.py`, add the import alongside the other `ai` imports (after line 28's combat-action import is fine — keep alphabetical grouping, place near the top imports):

```python
from artifactsmmo_cli.ai.combat import predict_win
```

Add module-level constants near the top of the file (after the imports block, with the other module constants such as `_BANK_RETRY_SECONDS`):

```python
WIN_RATE_THRESHOLD = 0.5
"""Observed win rate at or above which a monster is considered beatable."""
MIN_WIN_SAMPLES = 5
"""Minimum recorded fights before an observed win rate can veto a stat
prediction (below this the sample is too noisy to trust)."""
```

- [ ] **Step 4: Add `_is_winnable` and rework `_pick_winnable_monster`**

Replace the entire `_pick_winnable_monster` method (lines 1174-1208) with:

```python
    def _is_winnable(self, monster_code: str) -> bool:
        """True when the documented combat-stat prediction says we win AND we
        have not been observed losing this monster (>= MIN_WIN_SAMPLES fights
        under WIN_RATE_THRESHOLD). The learned-loss veto overrides an optimistic
        stat prediction; a cold/absent history defers to the prediction."""
        assert self.state is not None and self.game_data is not None
        if self.history is not None:
            samples = self.history.sample_count(f"Fight({monster_code})")
            rate = self.history.success_rate(f"Fight({monster_code})")
            if samples >= MIN_WIN_SAMPLES and rate < WIN_RATE_THRESHOLD:
                return False
        return predict_win(self.state, self.game_data, monster_code)

    def _pick_winnable_monster(self) -> str | None:
        """Highest-level monster that `_is_winnable` (stat prediction not vetoed
        by observed losses). Returns None when no monster is winnable, so the
        caller can suppress combat-driving goals and let upgrade goals dominate."""
        assert self.game_data is not None
        assert self.state is not None
        best: tuple[str, int] | None = None
        for code, level in self.game_data._monster_level.items():
            if not self._is_winnable(code):
                continue
            if best is None or level > best[1]:
                best = (code, level)
        return best[0] if best is not None else None
```

Note: the old `level > self.state.level` level gate is intentionally dropped — the stat prediction is the real signal (per spec). `_is_winnable` evaluates every known monster.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_player.py -k "winnable" -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player.py
git commit -m "feat(ai): winnability = combat prediction + win-rate veto

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Gate `farm_target` by winnability in `_build_goals`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py`
- Test: `tests/test_ai/test_player.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ai/test_player.py`:

```python
def test_build_goals_keeps_winnable_path_aligned_target(monkeypatch):
    player = _build_goals_player(monkeypatch)  # see helper note below
    monkeypatch.setattr(player, "_path_aligned_monster", lambda: "wolf")
    monkeypatch.setattr(player, "_is_winnable", lambda code: code == "wolf")
    pick_calls = []
    monkeypatch.setattr(player, "_pick_winnable_monster",
                        lambda: pick_calls.append(1) or "chicken")
    goals = player._build_goals()
    # path-aligned pick is winnable -> fallback picker NOT consulted
    assert pick_calls == []
    assert any("GrindCharacterXP(wolf" in repr(g) for g in goals)


def test_build_goals_falls_back_when_path_aligned_not_winnable(monkeypatch):
    player = _build_goals_player(monkeypatch)
    monkeypatch.setattr(player, "_path_aligned_monster", lambda: "yellow_slime")
    monkeypatch.setattr(player, "_is_winnable", lambda code: code == "chicken")
    monkeypatch.setattr(player, "_pick_winnable_monster", lambda: "chicken")
    goals = player._build_goals()
    assert any("GrindCharacterXP(chicken" in repr(g) for g in goals)
    assert not any("yellow_slime" in repr(g) for g in goals)


def test_build_goals_no_grind_when_no_winnable_monster(monkeypatch):
    player = _build_goals_player(monkeypatch)
    monkeypatch.setattr(player, "_path_aligned_monster", lambda: "yellow_slime")
    monkeypatch.setattr(player, "_is_winnable", lambda code: False)
    monkeypatch.setattr(player, "_pick_winnable_monster", lambda: None)
    goals = player._build_goals()
    assert not any("GrindCharacterXP" in repr(g) for g in goals)
```

Helper note: `_build_goals_player(monkeypatch)` should construct a `GamePlayer` with `state`, `game_data`, and `_strategy` set so `_build_goals` runs end-to-end. Reuse the existing `_build_goals` test setup already in `test_player.py` (the file already has tests that call `player._build_goals()` — the `TestBuildGoals` class from the P3b cutover work; build on its fixture/`setup`). Set `_strategy` to a stub whose `.decide(state, gd)` returns an object with `chosen_step=None` (or a `ReachCharLevel`) so only the fallback grind exercises `farm_target`. Stub `_strategy` the same way the existing `TestBuildGoals` tests do.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_player.py -k "build_goals and (winnable or fall_back or no_grind or path_aligned)" -v`
Expected: FAIL — current `_build_goals` calls `_pick_winnable_monster` only when `_path_aligned_monster()` is `None`, so the non-winnable path-aligned monster (`yellow_slime`) still produces a grind goal.

- [ ] **Step 3: Add the winnability gate**

In `src/artifactsmmo_cli/ai/player.py`, replace the `farm_target` block (lines 974-976):

```python
        farm_target = self._path_aligned_monster()
        if farm_target is None:
            farm_target = self._pick_winnable_monster()
```

with:

```python
        farm_target = self._path_aligned_monster()
        if farm_target is None or not self._is_winnable(farm_target):
            farm_target = self._pick_winnable_monster()
```

The downstream code already handles `farm_target is None` (the fallback grind is only appended `if farm_target is not None`, lines 1029-1032, and `strategy_goal(..., farm_target)` returns `None` for a `ReachCharLevel` step when `combat_monster is None`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_player.py -k "build_goals and (winnable or fall_back or no_grind or path_aligned)" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player.py
git commit -m "feat(ai): gate farm_target by winnability in _build_goals

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Full suite, lint, type-check, coverage

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -q`
Expected: 0 failures, 0 errors, 0 skipped.

- [ ] **Step 2: Fix any fallout from removing the level gate / signature changes**

If existing tests asserted the OLD `_pick_winnable_monster` behavior (the `best_unobserved`/level-gate benefit-of-doubt path, or `WIN_RATE_THRESHOLD`/`MIN_SAMPLES` as locals), curate them to the new contract: `_pick_winnable_monster` now returns the highest-level monster for which `_is_winnable` is true (no separate cold-history branch — `_is_winnable` defers to `predict_win` when history is cold). Update or remove those assertions in place; do not reintroduce the local constants. Re-run `uv run pytest -q` until green.

- [ ] **Step 3: Lint**

Run: `uv run ruff check src tests`
Expected: no errors.

- [ ] **Step 4: Type-check**

Run: `uv run mypy src`
Expected: no errors. (If mypy flags `predict_win` args from `_is_winnable`, the `assert self.state is not None and self.game_data is not None` guard already narrows the types — keep it.)

- [ ] **Step 5: Coverage on changed code**

Run: `uv run pytest --cov=src/artifactsmmo_cli/ai/combat --cov=src/artifactsmmo_cli/ai/world_state --cov=src/artifactsmmo_cli/ai/game_data --cov-report=term-missing -q`
Expected: 100% on `combat.py`; the added lines in `world_state.py`/`game_data.py`/`player.py` covered. Add targeted tests for any uncovered new line.

- [ ] **Step 6: Final commit (if Step 2 changed anything)**

```bash
git add -A
git commit -m "test(ai): curate winnable-monster tests to new contract

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- WorldState combat fields + `from_character_schema` → Task 1. ✓
- Monster crit/initiative + `monster_hp`/`monster_critical_strike`/`monster_initiative` → Task 2. ✓
- `combat.py` full documented formula (`_round_half_up`, `_element_damage`, `_expected_hit`, `predict_win`, `MAX_TURNS`, initiative, crit-expected) → Task 3. ✓
- `WIN_RATE_THRESHOLD`/`MIN_WIN_SAMPLES` constants + `_is_winnable` (prediction + veto) + reworked `_pick_winnable_monster` → Task 4. ✓
- `_build_goals` `farm_target` gate → Task 5. ✓
- Error handling (history None → prediction only; empty attack → not winnable; unknown monster hp 0) → covered by Task 3/4 tests. ✓
- Testing standard (0/0/0, 100% changed code) → Task 6. ✓

**Type consistency:** `predict_win(state, game_data, monster_code)` signature identical across spec, Task 3 impl, Task 4 call. `ELEMENTS` imported from `world_state` in `combat.py`. Getter names `monster_hp`/`monster_critical_strike`/`monster_initiative` consistent Task 2 ↔ Task 3. Constants `WIN_RATE_THRESHOLD`/`MIN_WIN_SAMPLES` consistent Task 4 ↔ Task 6.

**Placeholder scan:** No TBD/TODO; every code step shows full code; test helper conventions point at concrete existing patterns (`_make_player` in `test_task_decision_integration.py`, `make_state` in `fixtures.py`, `TestBuildGoals` in `test_player.py`).
