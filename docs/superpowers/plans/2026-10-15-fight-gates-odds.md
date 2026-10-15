# Fight gates read the odds (part B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every yes/no fight gate decides on the exact win probability against a per-character, per-monster threshold derived from loss cost, and a fight below 75% routes the character to gear first.

**Architecture:** `combat.predict_win` becomes `win_probability >= win_threshold(state, monster)`. θ lives on `WorldState.win_thresholds` (filled each cycle from learning.db, default 4/5), so every caller, with or without a history, reads one verdict. A second predicate, `secure_win` (P ≥ max(θ, 3/4)), drives the gear arm (`has_combat_deficit`, `combat_deficit`, `SelectionContext.combat_risky`). The closed form stays for the exits and gear ranking, with burn charged off the monster's attack. Lean liveness re-grounds its 49 witness rows on a worst-case-race theorem.

**Tech Stack:** Python 3.13 (uv), SQLModel/sqlite learning.db, Lean 4 (`formal/`), pytest, `formal/diff` differential harnesses, `formal/diff/mutate.py`.

**Spec:** `docs/superpowers/specs/2026-10-15-fight-gates-odds-design.md`

## Global Constraints

- `uv run` for every Python command.
- No inline imports; no `except Exception`; no `if TYPE_CHECKING`; one behavioural class per file; no `...` relative imports.
- Success = 0 errors, 0 warnings, 0 skipped, 100% coverage (`formal/gate.sh`).
- `DEFAULT_WIN_THRESHOLD = Fraction(4, 5)`; `SECURE_WIN = Fraction(3, 4)`; sample bar `MIN_WIN_SAMPLES` (5) wins **and** 5 losses per (character, monster); θ window = last 14 days of `cycles`.
- θ = t_loss / (t_win + t_loss), exact `Fraction` over integer second totals (`Fraction(loss_total * n_win, win_total * n_loss + loss_total * n_win)`).
- A fight's cost = its `actual_cooldown_seconds` + every `RestAction` and `MoveAction` cooldown of the same character after it and before that character's next `FightAction`. Win = outcome `ok`; loss = `error:fight_lost`; other outcomes skipped; a fight with no later fight skipped.
- Lean: no `sorry`, no new axiom. The only accepted warning is the pre-existing one at `PredictWin.lean:705`.
- Work in worktree `.worktrees/fight-gates` on branch `fight-gates`. Setup: symlink `artifactsmmo-api-client` → `/home/blentz/git/artifactsmmo/artifactsmmo-api-client`, `uv sync`; in `formal/.lake` symlink `packages` → main checkout's `formal/.lake/packages` and `cp -a --reflink=auto` its `build` and `config`.
- Commits in the worktree use `ARTIFACTSMMO_TOKEN=dummy`. Never copy the real `TOKEN` file. Never `--no-verify`, `git stash`, or `git checkout <path>`; chain git commands with `&&`.
- Mutation anchors are refreshed in the SAME commit as the edit they anchor (`uv run python formal/diff/mutate.py --check-anchors`).
- The gate regenerates `docs/behavioral_completeness/DROP_WALL_MATRIX.md` with a pre-existing one-cell drift: restore it with `git show HEAD:<path> > <path>`, never commit it.

## Review Focus

1. A character with a θ entry fights monster A at P 0.6 while another without data refuses it. Expect `predict_win` to read the entry for the monster asked about only. Test: Task 3 step 1, `test_threshold_entry_changes_only_its_monster`.
2. A cycle log where two characters interleave, or a Rest belongs to a later craft (Fight, Craft, Rest, Fight). Expect the Rest still counted (window is fight-to-fight, Rest/Move only), the Craft not. Test: Task 2, `test_window_counts_rest_and_move_only` and `test_interleaved_characters`.
3. A monster with exit `OUT_SUSTAIN` or `UNKILLABLE`. Expect P exactly 1 or 0, so the verdict is unchanged from the closed form whatever θ is. Test: Task 4, `test_exits_decide_regardless_of_threshold`.
4. A state at low current HP. `predict_win` must still read `state.hp` (rest guard compares current against max), and the deficit walk reads max HP. Test: Task 4, `test_predict_win_reads_current_hp`.
5. The risky target with no gear to buy. Expect the walk to still return the grind (`ReachCharLevel`), never `None`. Test: Task 5, `test_risky_target_without_gear_still_grinds`.

---

### Task 1: Closed-form burn charged off the monster's attack

**Files:**
- Modify: `src/artifactsmmo_cli/ai/combat.py` (`_die_step` ~:131-153, its 2 calls in `fight_numbers`, the `flat_burn` line and the burn comment ~:330-345, :385-392)
- Modify: `formal/Formal/PredictWin.lean` (`dieStep`, `predictWin`, docstring ~:128-170) and every caller of `dieStep` (`grep -rn "dieStep" formal/Formal`)
- Modify: `formal/Oracle.lean` if it passes `pAtkSum` into `dieStep` for burn
- Modify: `formal/diff/test_winnable_witness_diff.py:_kernel_predict_win`, `formal/diff/test_predict_win_diff.py`, `formal/diff/test_combat_margin_diff.py` (whatever builds the die step)
- Modify: `formal/diff/mutate.py` (anchors on the burn term)
- Test: `tests/test_ai/test_combat.py`

**Interfaces:**
- Produces: `_die_step(raw_monster, m_crit, p_crit, player_lifesteal, p_atk_sum, monster_poison, monster_burn, p_max_hp, void_drain, berserk, frenzy, antipoison, raw_player, greed, mirror, m_atk_sum)`. `m_atk_sum` is a NEW last parameter used only by the burn term (`monster_burn * m_atk_sum * 100`).

- [ ] **Step 1: Write the failing test** (in `tests/test_ai/test_combat.py`, beside the existing `_die_step` tests)

```python
def test_burn_is_charged_off_the_monsters_attack_not_the_players() -> None:
    # imp: burn 15%, attack 45; a player with attack 80. Server: first tick
    # round(15% x 45) = 7, so the closed form charges 15 * 45 * 100 per round.
    base = _die_step(0, 0, 0, 0, 80, 0, 0, 500, 0, 0, 0, 0, 0, 0, 0, 45)
    burned = _die_step(0, 0, 0, 0, 80, 0, 15, 500, 0, 0, 0, 0, 0, 0, 0, 45)
    assert burned - base == 15 * 45 * 100
```

- [ ] **Step 2: Run it, expect FAIL** (`TypeError: _die_step() takes 15 positional arguments but 16 were given`)

Run: `uv run pytest tests/test_ai/test_combat.py -k burn_is_charged_off -q`

- [ ] **Step 3: Implement**
  - Add `m_atk_sum: int` as the last parameter of `_die_step`; the burn term becomes `+ monster_burn * m_atk_sum * 100`.
  - In `fight_numbers`, pass `m_atk_sum` to both `_die_step` calls (the `hit` call keeps `monster_burn=0`, so its value there is irrelevant; pass `m_atk_sum` anyway).
  - `flat_burn = game_data.monster_burn(monster_code) * m_atk_sum * 100`.
  - Rewrite the burn comment: the closed form charges the first tick's unrounded value every round; the ticks decay, so this bounds each round's tick; the odds walk charges the exact ticks.
  - Lean `dieStep`: rename the burn factor from `pAtkSum` to a new `mAtkSum` argument (append it last, same order as Python); `predictWin` passes its existing `mAtkSum`. Update the docstring. Fix every other `dieStep` caller (`grep -rn "dieStep" formal/`).
  - Python mirrors (`_kernel_predict_win` and any harness that rebuilds the die step) use `row.m_atk_sum` / the monster's attack sum.
- [ ] **Step 4: Run tests and the Lean build**

Run: `uv run pytest tests/test_ai/test_combat.py -q` → PASS
Run: `cd formal && lake build 2>&1 | grep -E "error|sorry" ; cd ..` → no output
Run: `uv run pytest formal/diff/test_predict_win_diff.py formal/diff/test_combat_margin_diff.py formal/diff/test_winnable_witness_diff.py -q` → PASS
- [ ] **Step 5: Refresh anchors, commit**

```bash
uv run python formal/diff/mutate.py --check-anchors
git add -A src formal tests && ARTIFACTSMMO_TOKEN=dummy git commit -m "fix(combat): the closed form charges burn off the monster's attack"
```

---

### Task 2: θ from loss cost (pure core + store query)

**Files:**
- Create: `src/artifactsmmo_cli/ai/win_threshold_core.py`
- Modify: `src/artifactsmmo_cli/ai/learning/store.py` (new method after `lost_task_keys`)
- Test: `tests/test_ai/test_win_threshold_core.py`, `tests/test_ai/test_learning_store.py` (or the store test file that covers `combat_record`)

**Interfaces:**
- Produces:
  - `FightCostRow = tuple[str, str, str, int]`: `(action_class, action_repr, outcome, seconds)` in id order, one character.
  - `win_thresholds_from_rows(rows: Sequence[FightCostRow]) -> dict[str, Fraction]`: monster code → θ, only for pairs with ≥ `MIN_WIN_SAMPLES` wins and ≥ `MIN_WIN_SAMPLES` losses.
  - `LearningStore.fight_cost_rows(since_iso: str) -> list[FightCostRow]`: this character's `FightAction`, `RestAction`, `MoveAction` cycles with `ts >= since_iso`, ordered by `id`; `[]` on `SQLAlchemyError`.
  - `THRESHOLD_WINDOW_DAYS = 14` in `win_threshold_core`.

- [ ] **Step 1: Write the failing tests** (`tests/test_ai/test_win_threshold_core.py`)

```python
from fractions import Fraction

from artifactsmmo_cli.ai.win_threshold_core import win_thresholds_from_rows

def _fight(monster: str, won: bool, secs: int) -> tuple[str, str, str, int]:
    return ("FightAction", f"Fight({monster})", "ok" if won else "error:fight_lost", secs)

def _rest(secs: int) -> tuple[str, str, str, int]:
    return ("RestAction", "Rest", "ok", secs)

def _move(secs: int) -> tuple[str, str, str, int]:
    return ("MoveAction", "Move(0,0)", "ok", secs)

def _loop(won: list[bool]) -> list[tuple[str, str, str, int]]:
    rows = []
    for w in won:
        rows += [_fight("cyclops", w, 10), _rest(50 if w else 90)]
        if not w:
            rows.append(_move(20))
    return rows + [_fight("cyclops", True, 10)]  # closes the last window

def test_theta_is_loss_cost_share() -> None:
    # wins cost 10+50=60, losses 10+90+20=120: theta = 120/(60+120) = 2/3
    assert win_thresholds_from_rows(_loop([True] * 5 + [False] * 5)) == {"cyclops": Fraction(2, 3)}

def test_fewer_than_five_losses_gives_no_entry() -> None:
    assert win_thresholds_from_rows(_loop([True] * 9 + [False] * 4)) == {}

def test_fewer_than_five_wins_gives_no_entry() -> None:
    assert win_thresholds_from_rows(_loop([True] * 3 + [False] * 9)) == {}

def test_window_counts_rest_and_move_only() -> None:
    rows = _loop([True] * 5 + [False] * 5)
    rows.insert(1, ("CraftAction", "Craft(x)", "ok", 999))
    assert win_thresholds_from_rows(rows) == {"cyclops": Fraction(2, 3)}

def test_other_fight_outcomes_are_skipped_and_end_the_window() -> None:
    rows = _loop([True] * 5 + [False] * 5)
    rows.insert(0, ("FightAction", "Fight(cyclops)", "error:cooldown", 0))
    assert win_thresholds_from_rows(rows) == {"cyclops": Fraction(2, 3)}

def test_trailing_open_window_is_skipped() -> None:
    rows = _loop([True] * 5 + [False] * 5) + [_fight("cyclops", False, 10), _rest(5000)]
    assert win_thresholds_from_rows(rows) == {"cyclops": Fraction(2, 3)}

def test_monsters_are_kept_apart() -> None:
    a = _loop([True] * 5 + [False] * 5)
    b = [("FightAction", "Fight(imp)", r[2], r[3]) if r[0] == "FightAction" else r for r in a]
    assert set(win_thresholds_from_rows(a + b)) == {"cyclops", "imp"}
```

A store test (in the file covering `combat_record`): two characters' cycles interleaved by id; `fight_cost_rows` returns only its own character's Fight/Rest/Move rows in id order, and rows older than `since_iso` are absent (`test_interleaved_characters`).

- [ ] **Step 2: Run, expect FAIL** (`ModuleNotFoundError: artifactsmmo_cli.ai.win_threshold_core`)

Run: `uv run pytest tests/test_ai/test_win_threshold_core.py -q`

- [ ] **Step 3: Implement**

```python
"""Pure core: the win threshold a fight's loss cost implies (spec 2026-10-15
fight-gates-odds §2). Expected seconds per kill is t_win + (1-p)/p * t_loss; the
rule "loss overhead per kill <= one won fight" gives p >= t_loss/(t_win+t_loss)."""

from collections.abc import Sequence
from fractions import Fraction

from artifactsmmo_cli.ai.combat_constants import MIN_WIN_SAMPLES

THRESHOLD_WINDOW_DAYS = 14
"""Days of `cycles` the threshold reads (spec §2 ruling)."""

FightCostRow = tuple[str, str, str, int]
"""`(action_class, action_repr, outcome, seconds)`, one character, id order."""

_WIN, _LOSS = "ok", "error:fight_lost"
_UPKEEP = frozenset({"RestAction", "MoveAction"})


def _monster(action_repr: str) -> str:
    return action_repr[len("Fight("):-1]


def win_thresholds_from_rows(rows: Sequence[FightCostRow]) -> dict[str, Fraction]:
    """Monster -> θ for every monster with at least MIN_WIN_SAMPLES wins and
    MIN_WIN_SAMPLES losses; a fight's cost runs to the next FightAction."""
    totals: dict[tuple[str, bool], list[int]] = {}
    open_fight: tuple[str, bool] | None = None
    cost = 0
    for action_class, action_repr, outcome, seconds in rows:
        if action_class == "FightAction":
            if open_fight is not None:
                bucket = totals.setdefault(open_fight, [0, 0])
                bucket[0] += cost
                bucket[1] += 1
            open_fight = ((_monster(action_repr), outcome == _WIN)
                          if outcome in (_WIN, _LOSS) else None)
            cost = seconds
        elif action_class in _UPKEEP:
            cost += seconds
    out: dict[str, Fraction] = {}
    for monster in {m for m, _ in totals}:
        win_total, wins = totals.get((monster, True), [0, 0])
        loss_total, losses = totals.get((monster, False), [0, 0])
        if wins >= MIN_WIN_SAMPLES and losses >= MIN_WIN_SAMPLES:
            out[monster] = Fraction(loss_total * wins, win_total * losses + loss_total * wins)
    return out
```

  - `MIN_WIN_SAMPLES` lives in `combat.py` today; `combat.py` will import this core in Task 3, so importing `combat` here would be a cycle. Move `MIN_WIN_SAMPLES` (and its docstring) to a new constants module `src/artifactsmmo_cli/ai/combat_constants.py` and re-export it from `combat.py` with `from artifactsmmo_cli.ai.combat_constants import MIN_WIN_SAMPLES as MIN_WIN_SAMPLES` so existing imports keep working. If `win_total * losses + loss_total * wins == 0` (all zero-second fights), skip the monster: that is no evidence.
  - Store method:

```python
    def fight_cost_rows(self, since_iso: str) -> list[FightCostRow]:
        """This character's Fight, Rest and Move cycles since `since_iso`, in id
        order: the loss-cost evidence (`win_threshold_core`). [] on a DB error."""
        try:
            with SqlSession(self._engine) as s:
                rows = s.exec(
                    select(Cycle.action_class, Cycle.action_repr, Cycle.outcome,
                           Cycle.actual_cooldown_seconds)
                    .where(Cycle.character == self._character, Cycle.ts >= since_iso,
                           col(Cycle.action_class).in_(("FightAction", "RestAction", "MoveAction")))
                    .order_by(Cycle.id))
                return [(c, r, o, int(s_ or 0)) for c, r, o, s_ in rows]
        except SQLAlchemyError:
            return []
```

  (Check `Cycle.ts`'s column type and `actual_cooldown_seconds`'s nullability in `learning/models.py` first; match the comparison to the stored format.)
- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/test_ai/test_win_threshold_core.py tests/test_ai/test_learning_store.py -q`
- [ ] **Step 5: Commit**

```bash
git add -A src tests && ARTIFACTSMMO_TOKEN=dummy git commit -m "feat(learning): a fight's win threshold from its measured loss cost"
```

---

### Task 3: `WorldState.win_thresholds`, filled every cycle

**Files:**
- Modify: `src/artifactsmmo_cli/ai/world_state.py` (field after `lost_fights`, ~:138)
- Modify: `src/artifactsmmo_cli/ai/combat.py` (constants + `win_threshold`)
- Modify: `src/artifactsmmo_cli/ai/player.py` (`_refresh_lost_fights` ~:3579 and its 2 call sites :1001, :1095)
- Test: `tests/test_ai/test_combat.py`, `tests/test_ai/test_player.py`

**Interfaces:**
- Consumes: `win_thresholds_from_rows`, `LearningStore.fight_cost_rows`, `THRESHOLD_WINDOW_DAYS` (Task 2).
- Produces:
  - `WorldState.win_thresholds: Mapping[str, Fraction]` (default `MappingProxyType({})` or an empty `frozendict`-style default that keeps the dataclass hashable; follow how other mapping fields default in `WorldState`).
  - `combat.DEFAULT_WIN_THRESHOLD = Fraction(4, 5)`, `combat.SECURE_WIN = Fraction(3, 4)`.
  - `combat.win_threshold(state: WorldState, monster_code: str) -> Fraction`.

- [ ] **Step 1: Write the failing tests**

```python
def test_win_threshold_defaults_to_four_fifths() -> None:
    assert win_threshold(_state(), "cyclops") == Fraction(4, 5)

def test_threshold_entry_changes_only_its_monster() -> None:
    state = replace(_state(), win_thresholds={"cyclops": Fraction(1, 2)})
    assert win_threshold(state, "cyclops") == Fraction(1, 2)
    assert win_threshold(state, "imp") == Fraction(4, 5)
```

  In `test_player.py`: a player whose history returns rows giving `{"cyclops": Fraction(2, 3)}` from `fight_cost_rows` has `state.win_thresholds == {"cyclops": Fraction(2, 3)}` after the refresh; with `history=None` it is empty. Use the existing fake-history pattern in that file.
- [ ] **Step 2: Run, expect FAIL** (`ImportError: cannot import name 'win_threshold'`)
- [ ] **Step 3: Implement**
  - `world_state.py`: the field with a docstring in the style of `lost_fights` ("θ per monster from this character's measured loss cost (`win_threshold_core`); a monster absent reads `combat.DEFAULT_WIN_THRESHOLD`. Empty by default; production fills it every cycle beside `lost_fights`.").
  - `combat.py`: the two constants with docstrings quoting the USER rulings, and

```python
def win_threshold(state: WorldState, monster_code: str) -> Fraction:
    """θ for a fight against `monster_code`: this character's loss-cost
    threshold, or DEFAULT_WIN_THRESHOLD before there is evidence (spec §1)."""
    return state.win_thresholds.get(monster_code, DEFAULT_WIN_THRESHOLD)
```

  - `player.py`: rename `_refresh_lost_fights` to `_refresh_fight_record` (update both call sites) and set both fields in one `replace`:

```python
        since = (datetime.now(UTC) - timedelta(days=THRESHOLD_WINDOW_DAYS)).isoformat()
        thresholds = (win_thresholds_from_rows(self.history.fight_cost_rows(since))
                      if self.history is not None else {})
        self.state = replace(self.state, lost_fights=lost, win_thresholds=thresholds)
```

  (Match `since` to the `ts` format checked in Task 2.)
- [ ] **Step 4: Run, expect PASS** — `uv run pytest tests/test_ai/test_combat.py tests/test_ai/test_player.py -q`
- [ ] **Step 5: Commit** — `git add -A src tests && ARTIFACTSMMO_TOKEN=dummy git commit -m "feat(combat): each character carries its win thresholds per monster"`

---

### Task 4: The verdict reads the odds

**Files:**
- Modify: `src/artifactsmmo_cli/ai/combat.py` (`predict_win` :436, new `secure_win`, `combat_margin` docstring :443, `is_winnable` :464-502, delete `_won_at_or_above_level` :528+)
- Modify: every test the switch breaks (56 files reference the gates; expect fallout mainly in `test_combat.py`, `test_band_target.py`, `test_learning_projections.py`, `test_tier_progress.py`)
- Modify: `formal/diff/test_predict_win_diff.py`, `formal/diff/test_combat_margin_diff.py`, `formal/diff/test_fight_outcome_diff.py`, `formal/diff/test_game_data_accessors_diff.py` (repoint the closed-form comparisons to `terms_win(combat_terms(...))`)
- Modify: `formal/diff/mutate.py` (anchors on `predict_win`'s body; add mutants: `>=` → `>`, θ → `DEFAULT_WIN_THRESHOLD` ignoring the state)
- Test: `tests/test_ai/test_combat.py`

**Interfaces:**
- Consumes: `win_threshold`, `SECURE_WIN` (Task 3); `win_probability` (part A).
- Produces:
  - `predict_win(state, game_data, monster_code) -> bool` = `win_probability(...) >= win_threshold(state, monster_code)`.
  - `secure_win(state, game_data, monster_code) -> bool` = `win_probability(...) >= max(win_threshold(state, monster_code), SECURE_WIN)`.

- [ ] **Step 1: Write the failing tests** (`test_combat.py`; build the fixtures from the existing `_game_data` helpers there, with hits chosen so the exact P is known)
  - `test_coin_flip_is_not_winnable_at_default` — the R2D2-owlbear replay fixture from part A's `TestFightOdds` (P = 0.6308): `predict_win` is False with no entry, True with `win_thresholds={"owlbear": Fraction(1, 2)}`.
  - `test_predict_win_is_odds_against_threshold` — Hypothesis over the existing random-fight strategy used by the odds tests: `predict_win(s, gd, m) == (win_probability(s, gd, m) >= win_threshold(s, m))`.
  - `test_exits_decide_regardless_of_threshold` — an out-sustain monster is winnable at `win_thresholds={m: Fraction(1)}`; an unkillable one is not winnable at `win_thresholds={m: Fraction(1, 100)}`.
  - `test_predict_win_reads_current_hp` — the same fight at 10% HP is not winnable and at full HP is.
  - `test_secure_win_needs_three_quarters` — with θ = 1/2 and P 0.6308: `predict_win` True, `secure_win` False.
  - `test_higher_level_win_no_longer_makes_a_monster_winnable` — a history with a win against a higher-level monster and a stat-losing target: `is_winnable` is False (was True through the removed shortcut).
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement**

```python
def predict_win(state: WorldState, game_data: GameData, monster_code: str) -> bool:
    """The fight verdict every gate reads (spec 2026-10-15 fight-gates-odds §1):
    the exact P(win) from `state.hp` in the best on-hand loadout with the worn
    restore potion, at least this character's threshold for the monster."""
    return win_probability(state, game_data, monster_code) >= win_threshold(state, monster_code)


def secure_win(state: WorldState, game_data: GameData, monster_code: str) -> bool:
    """A fight won often enough that gear is not the better use of time (USER
    2026-10-15: below 75% "we probably need better gear"): P(win) at least
    max(θ, SECURE_WIN)."""
    return win_probability(state, game_data, monster_code) >= max(
        win_threshold(state, monster_code), SECURE_WIN)
```

  - `combat_margin`'s docstring: drop the `predict_win` invariant; it is the closed form's round cushion (`terms_margin`), a gear-ranking signal (`combat_deficit`), not the verdict.
  - `is_winnable`: remove gate 2 and `_won_at_or_above_level`; rewrite the docstring to two gates (learned-loss veto, then `predict_win`) and say why the shortcut went (spec §4).
  - Run the full `tests/test_ai` and fix each failure by asking: was the fixture a near-even fight that the closed form called won? Then the test's expectation follows the odds (recompute P and assert the new verdict), or the fixture's stats move clear of the boundary if the test is about something else. Never weaken an assertion to pass. Record each changed test and the reason in the commit body.
  - Repoint the differential harnesses: wherever a harness compared Lean `predictWin` against `predict_win`, compare against `terms_win(combat_terms(...))`; `test_combat_margin_diff`'s sign invariant becomes `terms_win ⇔ margin > 0`.
- [ ] **Step 4: Run** — `uv run pytest tests/test_ai -q -x -n auto` → PASS; `uv run pytest formal/diff -q -k "predict_win or combat_margin or fight_outcome or accessors"` → PASS
- [ ] **Step 5: Measure the cost** — before and after this task's commit, on live state (cwd = main checkout so `TOKEN` is read in place), time `plan_once()` for each of the 5 characters (scratchpad probe built on `probe_hal_imp.py`). Budget: after < 2× before. If over, raise `FIGHT_ODDS_CACHE` and re-measure; record both numbers in the commit body.
- [ ] **Step 6: Anchors, commit** — `uv run python formal/diff/mutate.py --check-anchors && git add -A src tests formal && ARTIFACTSMMO_TOKEN=dummy git commit -m "feat(combat): every fight gate reads the exact odds against the loss-cost threshold"`

---

### Task 5: Below 75% routes to gear

**Files:**
- Modify: `src/artifactsmmo_cli/ai/combat_deficit.py` (`has_combat_deficit` :152-169, `combat_deficit` :288 and :339, module docstring lines that say `predict_win`)
- Modify: `src/artifactsmmo_cli/ai/selection_context.py` (field after `combat_propped` :256)
- Modify: `src/artifactsmmo_cli/ai/player.py` (`_selection_context` ~:4103)
- Modify: `src/artifactsmmo_cli/ai/decisions/root.py` (`IsAFightBlockingMe.resolve` :549 and its docstring)
- Test: `tests/test_ai/test_combat_deficit.py`, `tests/test_ai/test_decisions_root.py`, `tests/test_ai/test_player.py`

**Interfaces:**
- Consumes: `secure_win`, `SECURE_WIN`, `win_probability` (Task 4).
- Produces: `SelectionContext.combat_risky: bool = False`.

- [ ] **Step 1: Write the failing tests**
  - `test_has_combat_deficit_below_secure` (`test_combat_deficit.py`): task monster at P 0.6308, θ = 1/2 → `has_combat_deficit` True; and `combat_deficit(...) is not None` agrees (the pinned equivalence).
  - `test_deficit_closes_only_at_secure`: a chain whose first item lifts P from 0.63 to ≥ 0.75 closes; one that lifts it only to 0.70 does not close at that step.
  - `test_risky_target_asks_for_gear_first` (`test_decisions_root.py`): `ctx.combat_monster="owlbear"`, `combat_risky=True`, task horizon GEAR → walk visits `WhichSlotClosesTheFight`; with `combat_risky=False` it goes to `IsMyGearBehindMyTier` directly (today's behaviour).
  - `test_risky_target_without_gear_still_grinds`: `combat_risky=True`, no task, gear sheet wants nothing → root is `ReachCharLevel` (not `None`).
  - `test_selection_context_marks_risky_target` (`test_player.py`): a grind target with P < 3/4 at max HP sets `combat_risky`; P = 1 does not.
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement**
  - `combat_deficit.py`: `has_combat_deficit` returns `not secure_win(replace(state, hp=state.max_hp), game_data, monster)`; in `combat_deficit` both `predict_win` calls become `secure_win`. Update the docstrings ("unwinnable" → "not secure: below max(θ, SECURE_WIN)").
  - `selection_context.py`: `combat_risky: bool = False` with a comment in the style of `combat_propped`: "The grind target wins below SECURE_WIN (USER 2026-10-15: below 75% we probably need better gear): like a propped target it does not hide a gear upgrade."
  - `player._selection_context`: `combat_risky=(combat_monster is not None and win_probability(replace(self.state, hp=self.state.max_hp), self.game_data, combat_monster) < SECURE_WIN)`.
  - `IsAFightBlockingMe.resolve`: `if ctx.combat_monster is not None and not ctx.combat_propped and not ctx.combat_risky:`; add a paragraph to its docstring.
- [ ] **Step 4: Run** — `uv run pytest tests/test_ai -q -n auto` → PASS
- [ ] **Step 5: Anchors (add mutants: drop `not ctx.combat_risky`; `secure_win` → `predict_win` in `has_combat_deficit`), commit** — `git add -A src tests formal && ARTIFACTSMMO_TOKEN=dummy git commit -m "feat(decisions): a fight won below 75% asks for gear first"`

---

### Task 6: Lean worst-case theorem and liveness re-grounding

**Files:**
- Modify: `formal/Formal/FightOdds.lean` (new theorem)
- Modify: `formal/Formal/Liveness/WinnableGrounded.lean` (witness rows carry `Damage` + `Terms` scalars; `winnableConcrete` becomes the odds verdict; grounding via the theorem)
- Modify: `formal/sim/winnable_witness.py` (pick rows among worst-case winners; emit the damage scalars)
- Modify: `formal/diff/test_winnable_witness_diff.py` (pin the new scalars against `fight_split`; `is_winnable` True per row; worst-case path wins)
- Modify: `formal/Formal/Contracts.lean`, `formal/Formal/Manifest.lean` (list the theorem)
- Test: the diff harness above; `lake build`

**Interfaces:**
- Produces (Lean):

```lean
/-- A fight won on the worst-case path (no player crit, every monster turn a crit)
is won with probability 1. -/
theorem winProb_eq_one_of_worst (t : Terms) (d : Damage) (hp maxHp : Int) (restore stock : Nat)
    (hk : d.killNormal ≤ d.killCrit) (hd : d.dieNormal ≤ d.dieCrit)
    (hp100 : d.pCrit ≤ 100) (hm100 : d.mCrit ≤ 100)
    (hw : winProb (fightOdds t { d with pCrit := 0, mCrit := 100 } hp maxHp restore stock) = 1) :
    winProb (fightOdds t d hp maxHp restore stock) = 1
```

- [ ] **Step 1: Spike the proof shape** (≤ 1 h): prove a `tree` lemma by induction on fuel: if the worst path from `(r, m, p, k)` wins, then every leaf of `tree d …` wins, so `winProb = mass = 1` (`tree_mass`). Ingredients: a bigger kill only lowers `m` (monster pool monotone), a smaller hit leaves a larger pool and `drink` is monotone (`drink_ge_nonneg`, `coupled`, `tree_mono`). If the induction needs `m`-monotonicity, prove `tree_mono_monster` first. Use the `lean4:sorry-filler-deep` agent if stuck; no `sorry` may remain.
- [ ] **Step 2: Write the theorem**; `lake build` clean.
- [ ] **Step 3: Re-pick the witness rows** in `formal/sim/winnable_witness.py`: among the in-band, XP-positive, not-over-leveled monsters the builder already filters, take the highest-level one whose worst-case path wins (`fight_odds` on `replace(damage, p_crit=0, m_crit=100)` has P == 1). Emit per row the `RoundDamage` fields, the `FightTerms` fields, hp, max hp, restore and stock. Regenerate the Lean witness table the way the file's docstring says.
- [ ] **Step 4: Ground** `winnableAcrossBand_grounded` on `winProb (fightOdds …) ≥ θ` for any `θ ≤ 1`, by kernel `decide` of the worst-case single path per row and `winProb_eq_one_of_worst`. Keep `PerceptionRefresh` and `LevelingDescent` compiling unchanged in statement.
- [ ] **Step 5: Run** — `cd formal && lake build 2>&1 | grep -E "error|sorry|warning" ; cd ..` (only the PredictWin.lean:705 warning) and `uv run pytest formal/diff/test_winnable_witness_diff.py formal/diff/test_winnable_across_band_diff.py formal/diff/test_liveness_chain.py -q` → PASS
- [ ] **Step 6: Commit** — `git add -A formal && ARTIFACTSMMO_TOKEN=dummy git commit -m "proof(liveness): witness rows grounded on the worst-case fight, P(win) = 1"`

---

### Task 7: Gate, live probe, merge

- [ ] **Step 1:** `uv run python formal/diff/mutate.py --only combat,combat_deficit,win_threshold_core,root` → every new mutant killed.
- [ ] **Step 2:** `bash formal/gate.sh > <scratchpad>/gate-b.log 2>&1; echo $? > <scratchpad>/gate-b.rc` (from the worktree); read the rc file in its own call → `0`. Restore `DROP_WALL_MATRIX.md` from HEAD.
- [ ] **Step 3: Live probe** (cwd = main checkout, `PYTHONPATH` the worktree's `src`): for C3P0, R2D2, Robby print `predict_win`, `secure_win`, P and θ for cyclops, cultist_acolyte, imp, owlbear. Expect C3P0 v cyclops not winnable at θ 0.8 (or winnable but not secure at its measured θ 0.52), Robby v imp winnable.
- [ ] **Step 4:** `git fetch origin && git rebase origin/main` if needed, then `git push origin HEAD:main`; confirm `git rev-parse origin/main`. Remove the worktree and branch; `git -C /home/blentz/git/artifactsmmo pull --ff-only` on main.
- [ ] **Step 5:** Update memory `project_combat_calibration_todo.md` (part B shipped, live check pending) and tell the user to restart the fleet; the live check list is in the spec.
