# Fight Odds (part A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The fight loop's XP rate is priced by a fight's exact win probability over crit rolls, so a risky fight carries a potion.

**Architecture:** A new pure core (`ai/fight_odds_core.py`) walks every crit outcome and returns the fight's endings with exact `Fraction` probabilities; a Lean model (`formal/Formal/FightOdds.lean`, an unmerged tree) is its specification, bound by a differential test. `combat.fight_split` supplies the per-round normal and crit damage from the same integers `fight_numbers` resolves. `loop_rate` prices the expected loop (renewal-reward), including a loss's recovery and the walk back from the respawn tile. Every fight records its P(win) for calibration.

**Tech Stack:** Python 3.13 (`uv run`), `fractions.Fraction`, pytest + hypothesis, Lean 4.30 core (`Rat`, no Mathlib outside `Formal/Liveness/`), SQLModel/SQLite.

**Spec:** `docs/superpowers/specs/2026-10-15-fight-odds-design.md`

## Global Constraints

- Use `uv run` for every Python command.
- No inline imports. Never catch `Exception`. No `if TYPE_CHECKING`. One behavioural class per file (pure dataclasses may share a module).
- Success = 0 errors, 0 warnings, 0 skipped, 100% coverage; full `bash formal/gate.sh` green before push (read its rc file in its own call).
- Lean outside `Formal/Liveness/` is core-only: no `import Mathlib`; axioms ⊆ {propext, Classical.choice, Quot.sound}. Theorem statements in this plan are fixed; tactics are the implementer's.
- Mutation anchors for every new branch, refreshed in the SAME commit as the edit; `uv run python formal/diff/mutate.py --check-anchors` must pass.
- Exact arithmetic only: probabilities are `Fraction` (Python) / `Rat` (Lean). No floats in decisions.
- `fight_odds` is memoised on value inputs only (frozen dataclasses and ints), bounded `maxsize`.
- `predict_win`, `combat_margin`, `is_winnable`, `fight_outcome` and their proofs are unchanged (part B owns them).
- `RESPAWN_TILE = (0, 0)` cited to learning.db (every R2D2 owlbear loss row ends there, `hp = 1`).
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never `--no-verify`, never `git stash`, never `git checkout <path>`. Chain git with `&&`.
- Worktree commits use `ARTIFACTSMMO_TOKEN=dummy` (the hook's CLI help test only). Never copy the real `TOKEN` file.

## Review Focus

1. A fight whose NORMAL hit is net non-positive (a monster heal larger than the bare hit) while its mean is positive: the walk must still terminate (turn cap) and its probabilities still sum to 1. → Task 1, `test_heal_larger_than_normal_hit_terminates`.
2. A crit chance of exactly 0 or 100: no zero-probability branch is created, and 100% crit is a single deterministic walk at the crit amount. → Task 1, `test_certain_crit_is_one_walk`.
3. A loadout whose potion is drunk only in losing endings: its consumed price still counts (a loss drinks too). → Task 4, `test_a_loss_still_pays_its_drinks`.
4. A chosen potion loadout whose expected drinks are below 1: `used` must not round to 0, or `potion_carry` stocks nothing. → Task 4, `test_expected_drinks_round_up`.
5. A monster with no known spawn tile reaching `loop_rate`: fail loudly, never price the walk back as free. → Task 4, `test_no_spawn_tile_raises`.

---

### Task 1: `fight_odds_core` — the exact ending distribution (Python)

**Files:**
- Create: `src/artifactsmmo_cli/ai/fight_odds_core.py`
- Test: `tests/test_ai/test_fight_odds_core.py`
- Modify: `formal/diff/mutate.py` (new `FIGHT_ODDS_CORE_SRC`, `FIGHT_ODDS_MUTATIONS`, `run_group`, `_ALL_SRCS`)

**Interfaces:**
- Consumes: `fight_terms_core.FightTerms`, `FightExit`, `SCALE`, `MAX_TURNS`, `effective_player_hp`; `fight_outcome_core.drink`.
- Produces:
  - `RoundDamage(monster_hp: int, kill_normal: int, kill_crit: int, p_crit: int, die_normal: int, die_crit: int, m_crit: int)` — frozen dataclass; `monster_hp` whole HP (barrier included), the four amounts ×10000 per round (everything the round charges), crits in percent 0..100.
  - `Ending(prob: Fraction, win: bool, turns: int, hp_end: int, used: int)` — frozen dataclass, `hp_end` ×10000 (0 on a loss).
  - `fight_odds(terms: FightTerms, damage: RoundDamage, hp_start: int, max_hp: int, restore: int, stock: int) -> tuple[Ending, ...]`
  - `win_probability(endings: Sequence[Ending]) -> Fraction`

- [ ] **Step 1: Write the failing tests**

```python
"""The exact ending distribution of a fight over crit rolls
(spec 2026-10-15 fight-odds §1)."""

from fractions import Fraction

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.fight_odds_core import Ending, RoundDamage, fight_odds, win_probability
from artifactsmmo_cli.ai.fight_outcome_core import fight_outcome
from artifactsmmo_cli.ai.fight_terms_core import MAX_TURNS, SCALE, fight_terms

# R2D2 v owlbear, 2026-10-15 server logs: 141/212 a turn at 45% crit; the owlbear
# 83/125 at 5%, moving first; R2D2 785 HP, owlbear 1450 HP.
_R2D2_TERMS = fight_terms(141, 50 * 141 * 245, 1450, 0, 50 * 83 * 205, 785, 785, False)
_R2D2 = RoundDamage(1450, 141 * SCALE, 212 * SCALE, 45, 83 * SCALE, 125 * SCALE, 5)


def _no_crit(kill: int, die: int, mhp: int) -> RoundDamage:
    return RoundDamage(mhp, kill, kill, 0, die, die, 0)


class TestR2D2Replay:
    def test_bare_odds_match_the_exact_value(self):
        p = win_probability(fight_odds(_R2D2_TERMS, _R2D2, 785, 785, 0, 0))
        assert round(float(p), 4) == 0.6308

    def test_a_minor_health_potion_makes_it_certain(self):
        p = win_probability(fight_odds(_R2D2_TERMS, _R2D2, 785, 785, 70, 100))
        assert round(float(p), 4) == 1.0

    def test_losses_end_between_the_seventh_and_tenth_monster_hit(self):
        # 6 hits deal at most 750 < 785; 10 hits at least 830 > 785.
        losses = {e.turns for e in fight_odds(_R2D2_TERMS, _R2D2, 785, 785, 0, 0) if not e.win}
        assert losses == {7, 8, 9, 10}


class TestDistribution:
    def test_probabilities_sum_to_one(self):
        assert sum(e.prob for e in fight_odds(_R2D2_TERMS, _R2D2, 785, 785, 70, 3)) == 1

    def test_endings_are_merged(self):
        endings = fight_odds(_R2D2_TERMS, _R2D2, 785, 785, 0, 0)
        keys = [(e.win, e.turns, e.hp_end, e.used) for e in endings]
        assert len(keys) == len(set(keys))

    def test_certain_crit_is_one_walk(self):
        damage = RoundDamage(1450, 141 * SCALE, 212 * SCALE, 100, 83 * SCALE, 125 * SCALE, 0)
        endings = fight_odds(_R2D2_TERMS, damage, 785, 785, 0, 0)
        assert len(endings) == 1 and endings[0].prob == 1 and endings[0].win

    def test_heal_larger_than_normal_hit_terminates(self):
        # The normal hit heals the monster (net -1), the crit kills: mean positive.
        terms = fight_terms(10, 5000, 50, 0, 20_000, 1000, 1000, True)
        damage = RoundDamage(50, -10_000, 600_000, 50, 20_000, 20_000, 0)
        endings = fight_odds(terms, damage, 1000, 1000, 0, 0)
        assert sum(e.prob for e in endings) == 1
        assert max(e.turns for e in endings) <= MAX_TURNS


class TestExits:
    @pytest.mark.parametrize("terms", [
        fight_terms(0, 1, 100, 0, 1, 100, 100, True),        # NO_DAMAGE
        fight_terms(5, 0, 100, 0, 1, 100, 100, True),        # UNKILLABLE
        fight_terms(5, 1, 10_000, 0, 1, 100, 100, True),     # OVER_CAP
        fight_terms(5, 10_000, 100, 3, 1, 100, 100, True),   # RECONSTITUTED
    ])
    def test_a_losing_exit_is_one_certain_loss(self, terms):
        assert fight_odds(terms, _no_crit(10_000, 1, 100), 100, 100, 0, 0) == (
            Ending(Fraction(1), False, 0, 0, 0),)

    def test_out_sustain_is_one_certain_win(self):
        terms = fight_terms(5, 50_000, 100, 0, 0, 100, 100, True)
        assert fight_odds(terms, _no_crit(50_000, 0, 100), 100, 100, 0, 0) == (
            Ending(Fraction(1), True, 20, 100 * SCALE, 0),)  # ceil(100 × 10000 / 50000)

    def test_a_dead_start_is_one_certain_loss(self):
        terms = fight_terms(5, 50_000, 100, 0, 10, 0, 100, True)
        assert fight_odds(terms, _no_crit(50_000, 10, 100), 0, 100, 0, 0) == (
            Ending(Fraction(1), False, 0, 0, 0),)

    def test_negative_restore_or_stock_raises(self):
        with pytest.raises(ValueError):
            fight_odds(_R2D2_TERMS, _R2D2, 785, 785, -1, 0)
        with pytest.raises(ValueError):
            fight_odds(_R2D2_TERMS, _R2D2, 785, 785, 0, -1)


_walked = st.tuples(
    st.integers(min_value=1, max_value=60),               # raw player
    st.integers(min_value=10_000, max_value=600_000),     # kill step
    st.integers(min_value=1, max_value=600),              # monster hp
    st.integers(min_value=10_000, max_value=900_000),     # die step
    st.booleans(),                                        # player first
    st.integers(min_value=1, max_value=2000),             # hp
    st.integers(min_value=0, max_value=400),              # restore
    st.integers(min_value=0, max_value=8),                # stock
)


@settings(max_examples=300, deadline=None)
@given(case=_walked)
def test_no_crit_equals_the_expected_value_walk(case):
    raw, ks, mhp, ds, pf, hp, restore, stock = case
    terms = fight_terms(raw, ks, mhp, 0, ds, hp, hp, pf)
    o = fight_outcome(terms, hp, hp, restore, stock)
    assert fight_odds(terms, _no_crit(ks, ds, mhp), hp, hp, restore, stock) == (
        Ending(Fraction(1), o.win, o.turns, o.hp_end, o.used),)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_fight_odds_core.py -q --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.fight_odds_core'`.

- [ ] **Step 3: Write the implementation**

```python
"""Pure core: a fight's exact ending distribution over crit rolls (spec
2026-10-15 fight-odds §1; proved model `formal/Formal/FightOdds.lean`,
differential `formal/diff/test_fight_odds_diff.py`).

`fight_outcome_core.fight_outcome` races the EXPECTED rounds: crit is its mean.
The server rolls one crit per turn per side (2026-10-15 fight logs: both of a
character's elements crit together), so a fight one round ahead on the mean can
be a coin flip: R2D2 v owlbear is margin 1 round and P(win) = 0.6308. This walk
branches on both rolls every round and merges identical states, so a round
holds at most `(r + 1)²` pool pairs per stock value.

THE ROUND. `RoundDamage` holds what one round charges, ×10000: `kill_normal` /
`kill_crit` to the monster, `die_normal` / `die_crit` to the player, each the
bare hit plus every term today's expected step charges beyond it (healing,
poison, greed, mean lifesteal, ... — `combat.fight_split`). Only crits branch.
A player turn first applies `drink` (start of turn, below half, one per turn
while stock lasts), then hits; `player_first` orders the two turns, exactly as
`fight_outcome`. A monster pool at or below 0 is a win, a player pool at or
below 0 a loss, and any state unresolved after `MAX_TURNS` rounds a loss in
round `MAX_TURNS`. Pools are not capped: a negative amount (a mean-modelled
heal larger than the bare hit) only raises a pool, as the mean model allows.

THE EXITS. The closed form's guard ladder decides first, with probability 1:
the out-sustain exit is one win in `rounds_to_kill` at the starting pool; every
other exit and a dead start is one loss in round 0 (spec ruling: the exits
stay deterministic). With both crit chances 0 the walk equals `fight_outcome`
(`Formal.FightOdds.fightOdds_noCrit`)."""

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache

from artifactsmmo_cli.ai.fight_outcome_core import drink
from artifactsmmo_cli.ai.fight_terms_core import MAX_TURNS, SCALE, FightExit, FightTerms, effective_player_hp

FIGHT_ODDS_CACHE = 4096
"""Distinct fights `fight_odds` keeps (value keys: frozen dataclasses and ints)."""


@dataclass(frozen=True)
class RoundDamage:
    """One round's charges, ×10000, and the crit chances in percent."""

    monster_hp: int
    kill_normal: int
    kill_crit: int
    p_crit: int
    die_normal: int
    die_crit: int
    m_crit: int


@dataclass(frozen=True)
class Ending:
    """One way the fight ends, with its probability (`hp_end` ×10000)."""

    prob: Fraction
    win: bool
    turns: int
    hp_end: int
    used: int


State = tuple[int, int, int]
"""`(monster pool, player pool, stock left)`."""


def _roll(pct: int, normal: int, crit: int) -> tuple[tuple[Fraction, int], ...]:
    """The two outcomes of one crit roll, without a zero-probability branch."""
    branches = ((Fraction(100 - pct, 100), normal), (Fraction(pct, 100), crit))
    return tuple(b for b in branches if b[0] != 0)


def _add(into: dict, key: object, prob: Fraction) -> None:
    into[key] = into.get(key, Fraction(0)) + prob


@lru_cache(maxsize=FIGHT_ODDS_CACHE)
def fight_odds(terms: FightTerms, damage: RoundDamage, hp_start: int, max_hp: int,
               restore: int, stock: int) -> tuple[Ending, ...]:
    """Every ending of the fight from `hp_start` with `stock` restore potions of
    `restore` HP (see the module doc), merged, in a fixed order."""
    if restore < 0 or stock < 0:
        raise ValueError(f"restore {restore} and stock {stock} must be non-negative")
    pool = effective_player_hp(hp_start, max_hp) * SCALE
    if terms.exit is FightExit.OUT_SUSTAIN:
        return (Ending(Fraction(1), True, terms.rounds_to_kill, pool, 0),)
    if terms.exit not in (FightExit.NONE, FightExit.DEAD) or pool <= 0:
        return (Ending(Fraction(1), False, 0, 0, 0),)
    max_pool, restore_pool = max_hp * SCALE, restore * SCALE
    kills = _roll(damage.p_crit, damage.kill_normal, damage.kill_crit)
    hits = _roll(damage.m_crit, damage.die_normal, damage.die_crit)
    ended: dict[tuple[bool, int, int, int], Fraction] = {}
    states: dict[State, Fraction] = {(damage.monster_hp * SCALE, pool, stock): Fraction(1)}
    for round_no in range(1, MAX_TURNS + 1):
        after: dict[State, Fraction] = {}
        for (monster, player, left), prob in states.items():
            if terms.player_first:
                _player_then_monster(round_no, monster, player, left, prob, stock,
                                     max_pool, restore_pool, kills, hits, ended, after)
            else:
                _monster_then_player(round_no, monster, player, left, prob, stock,
                                     max_pool, restore_pool, kills, hits, ended, after)
        states = after
        if not states:
            break
    for (_, _, left), prob in states.items():
        _add(ended, (False, MAX_TURNS, 0, stock - left), prob)
    return tuple(Ending(p, win, turns, hp_end, used)
                 for (win, turns, hp_end, used), p in sorted(ended.items()))


def _player_then_monster(round_no: int, monster: int, player: int, left: int, prob: Fraction,
                         stock: int, max_pool: int, restore_pool: int,
                         kills: tuple[tuple[Fraction, int], ...], hits: tuple[tuple[Fraction, int], ...],
                         ended: dict, after: dict) -> None:
    player, left = drink(player, max_pool, restore_pool, left)
    for pk, kill in kills:
        if monster - kill <= 0:
            _add(ended, (True, round_no, player, stock - left), prob * pk)
            continue
        for ph, hit in hits:
            if player - hit <= 0:
                _add(ended, (False, round_no, 0, stock - left), prob * pk * ph)
            else:
                _add(after, (monster - kill, player - hit, left), prob * pk * ph)


def _monster_then_player(round_no: int, monster: int, player: int, left: int, prob: Fraction,
                         stock: int, max_pool: int, restore_pool: int,
                         kills: tuple[tuple[Fraction, int], ...], hits: tuple[tuple[Fraction, int], ...],
                         ended: dict, after: dict) -> None:
    for ph, hit in hits:
        if player - hit <= 0:
            _add(ended, (False, round_no, 0, stock - left), prob * ph)
            continue
        drunk, rest = drink(player - hit, max_pool, restore_pool, left)
        for pk, kill in kills:
            if monster - kill <= 0:
                _add(ended, (True, round_no, drunk, stock - rest), prob * ph * pk)
            else:
                _add(after, (monster - kill, drunk, rest), prob * ph * pk)


def win_probability(endings: Sequence[Ending]) -> Fraction:
    """P(win): the summed probability of the winning endings."""
    return sum((e.prob for e in endings if e.win), Fraction(0))
```

Give `ended` / `after` precise types (`dict[tuple[bool, int, int, int], Fraction]` and `dict[State, Fraction]`) so `mypy --strict` passes; `_add` takes `dict[Any, Fraction]` only if strict typing requires it — prefer two typed helpers over `Any`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_fight_odds_core.py -q --cov=artifactsmmo_cli.ai.fight_odds_core --cov-report=term-missing`
Expected: all PASS, `fight_odds_core.py` 100%.

- [ ] **Step 5: Add mutants**

In `formal/diff/mutate.py` add `FIGHT_ODDS_CORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "fight_odds_core.py"`, append it to `_ALL_SRCS`, and a group `FIGHT_ODDS_MUTATIONS` with one entry per branch, each anchored on exactly one source line:
- "fight_odds: a zero-probability branch is kept" (`return tuple(b for b in branches if b[0] != 0)` → `return branches`);
- "fight_odds: crit and normal swapped" (`(Fraction(100 - pct, 100), normal), (Fraction(pct, 100), crit)` → `(Fraction(100 - pct, 100), crit), (Fraction(pct, 100), normal)`);
- "fight_odds: a kill at exactly 0 HP is not a kill" (both `if monster - kill <= 0:` → `if monster - kill < 0:`, one mutant per function — make each anchor unique by including the following line);
- "fight_odds: the player survives at exactly 0 HP" (both `if player - hit <= 0:` → `< 0`, one per function);
- "fight_odds: first-mover order inverted" (`if terms.player_first:` → `if not terms.player_first:`);
- "fight_odds: unresolved states dropped at the cap" (the final `for (_, _, left), prob in states.items():` loop body → `pass`);
- "fight_odds: no drink before the player's hit" (`player, left = drink(player, max_pool, restore_pool, left)` → `pass`).
Register `run_group(FIGHT_ODDS_CORE_SRC, FIGHT_ODDS_MUTATIONS, "tests/test_ai/test_fight_odds_core.py", survivors)` beside the `FIGHT_OUTCOME_MUTATIONS` call.

Run: `uv run python formal/diff/mutate.py --check-anchors && uv run python formal/diff/mutate.py --only src/artifactsmmo_cli/ai/fight_odds_core.py`
Expected: anchors OK; every `FIGHT_ODDS_MUTATIONS` mutant killed. A survivor means a missing test: add it to Step 1's file, not a weaker mutant.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/fight_odds_core.py tests/test_ai/test_fight_odds_core.py formal/diff/mutate.py && ARTIFACTSMMO_TOKEN=dummy git commit -m "feat(combat): fight_odds walks every crit outcome of a fight

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Lean model `FightOdds.lean`, oracle runner and differential

**Files:**
- Create: `formal/Formal/FightOdds.lean`
- Create: `formal/diff/test_fight_odds_diff.py`
- Modify: `formal/Formal.lean` (import), `formal/Oracle.lean` (`runFightOdds`, dispatch `"fight_odds"`), `formal/Formal/Contracts.lean`, `formal/Formal/Manifest.lean`, `formal/Formal/Audit.lean`, `formal/diff/mutate.py` (point `FIGHT_ODDS_MUTATIONS`' run_group ALSO at the diff: add a second `run_group(FIGHT_ODDS_CORE_SRC, FIGHT_ODDS_MUTATIONS, "formal/diff/test_fight_odds_diff.py", survivors)` only if the unit run leaves survivors the diff kills; otherwise leave it)

**Interfaces:**
- Consumes: Task 1's `fight_odds`, `RoundDamage`, `Ending`; `Formal.FightOutcome` (`Terms`, `scale`, `gate`, `roundsToKill`, `effHp`, `drink`, `fightOutcome`, `coupled`, `drink_coupled`, `mul_lt_iff_lt_ceilDiv`), `Formal.PredictWin.maxTurns`.
- Produces: `Formal.FightOdds.fightOdds`, `winProb`, theorems below; oracle kind `"fight_odds"`.

The Lean model is the SPECIFICATION: an unmerged tree of endings (`List (Rat × Ending)`), not the merged walk. The differential groups Lean's list by ending and compares it with Python's merged tuple.

- [ ] **Step 1: Write the model**

```lean
/-
Fight odds (spec docs/superpowers/specs/2026-10-15-fight-odds-design.md §1).
The exact ending distribution of a fight over per-turn crit rolls, as an
UNMERGED tree; `ai/fight_odds_core.fight_odds` merges identical states.
Lean core only — no Mathlib.
-/
import Formal.FightOutcome

namespace Formal.FightOdds

open Formal.FightOutcome (Terms scale gate roundsToKill effHp drink fightOutcome Exit)
open Formal.PredictWin (maxTurns)

/-- One round's charges ×10000 and the crit chances in percent. -/
structure Damage where
  monsterHp : Int
  killNormal : Int
  killCrit : Int
  pCrit : Nat
  dieNormal : Int
  dieCrit : Int
  mCrit : Nat

structure Ending where
  win : Bool
  turns : Int
  hpEnd : Int
  used : Nat
  deriving DecidableEq, Repr

/-- The outcomes of one crit roll: `(probability, amount)`, no zero branch. -/
def roll (pct : Nat) (normal crit : Int) : List (Rat × Int) :=
  [(((100 - pct : Nat) : Rat) / 100, normal), (((pct : Nat) : Rat) / 100, crit)].filter
    (fun b => b.1 ≠ 0)

/-- Scale every probability of a list. -/
def scaleBy (w : Rat) (xs : List (Rat × Ending)) : List (Rat × Ending) :=
  xs.map fun e => (w * e.1, e.2)

/-- The tree from round `r` with `fuel` rounds left. -/
def tree (d : Damage) (pf : Bool) (maxPool rPool : Int) (stock : Nat) :
    Nat → Int → Int → Int → Nat → List (Rat × Ending)
  | 0, r, _, _, k => [(1, ⟨false, r - 1, 0, stock - k⟩)]
  | fuel + 1, r, m, p, k =>
    if pf then
      let (p', k') := drink p maxPool rPool k
      (roll d.pCrit d.killNormal d.killCrit).flatMap fun (wk, kill) =>
        if m - kill ≤ 0 then [(wk, ⟨true, r, p', stock - k'⟩)]
        else scaleBy wk ((roll d.mCrit d.dieNormal d.dieCrit).flatMap fun (wh, hit) =>
          if p' - hit ≤ 0 then [(wh, ⟨false, r, 0, stock - k'⟩)]
          else scaleBy wh (tree d pf maxPool rPool stock fuel (r + 1) (m - kill) (p' - hit) k'))
    else
      (roll d.mCrit d.dieNormal d.dieCrit).flatMap fun (wh, hit) =>
        if p - hit ≤ 0 then [(wh, ⟨false, r, 0, stock - k⟩)]
        else
          let (p', k') := drink (p - hit) maxPool rPool k
          scaleBy wh ((roll d.pCrit d.killNormal d.killCrit).flatMap fun (wk, kill) =>
            if m - kill ≤ 0 then [(wk, ⟨true, r, p', stock - k'⟩)]
            else scaleBy wk (tree d pf maxPool rPool stock fuel (r + 1) (m - kill) p' k'))

/-- `fight_odds_core.fight_odds`, unmerged. -/
def fightOdds (t : Terms) (d : Damage) (hp maxHp : Int) (restore stock : Nat) :
    List (Rat × Ending) :=
  match gate t with
  | .outSustain => [(1, ⟨true, roundsToKill t, effHp hp maxHp * scale, 0⟩)]
  | .none =>
    if effHp hp maxHp * scale ≤ 0 then [(1, ⟨false, 0, 0, 0⟩)]
    else tree d t.playerFirst (maxHp * scale) ((restore : Int) * scale) stock
      maxTurns.toNat 1 (d.monsterHp * scale) (effHp hp maxHp * scale) stock
  | _ => [(1, ⟨false, 0, 0, 0⟩)]

/-- P(win). -/
def winProb (xs : List (Rat × Ending)) : Rat :=
  (xs.filter (·.2.win)).foldr (fun e acc => e.1 + acc) 0

end Formal.FightOdds
```

Check the Python walk matches this tree branch for branch (drink placement, turn numbering, cap ending `turns = MAX_TURNS`, `used = stock − left`). If they differ, the Python is wrong: fix Task 1's code and tests in this task's commit, and say so in the report.

- [ ] **Step 2: Prove the theorems (statements fixed)**

```lean
theorem fightOdds_sum_one (t : Terms) (d : Damage) (hp maxHp : Int) (restore stock : Nat)
    (hp' : d.pCrit ≤ 100) (hm : d.mCrit ≤ 100) :
    ((fightOdds t d hp maxHp restore stock).map (·.1)).foldr (· + ·) 0 = 1

theorem fightOdds_noCrit (t : Terms) (d : Damage) (hp maxHp : Int) (restore stock : Nat)
    (hp0 : d.pCrit = 0) (hm0 : d.mCrit = 0)
    (hk : d.killNormal = t.killStep) (hd : d.dieNormal = t.dieStep)
    (hmhp : d.monsterHp = t.monsterHp) :
    fightOdds t d hp maxHp restore stock =
      [(1, ⟨(fightOutcome t hp maxHp restore stock).win,
            (fightOutcome t hp maxHp restore stock).turns,
            (fightOutcome t hp maxHp restore stock).hpEnd,
            (fightOutcome t hp maxHp restore stock).used⟩)]

theorem fightOdds_win_mono_stock (t : Terms) (d : Damage) (hp maxHp : Int) (restore s s' : Nat)
    (hs : s ≤ s') (hp' : d.pCrit ≤ 100) (hm : d.mCrit ≤ 100) :
    winProb (fightOdds t d hp maxHp restore s) ≤ winProb (fightOdds t d hp maxHp restore s')

theorem fightOdds_win_mono_hp (t : Terms) (d : Damage) (hp hp' maxHp : Int) (restore stock : Nat)
    (hh : hp ≤ hp') (hp1 : d.pCrit ≤ 100) (hm : d.mCrit ≤ 100) :
    winProb (fightOdds t d hp maxHp restore stock) ≤ winProb (fightOdds t d hp' maxHp restore stock)
```

Proof route: induction on `fuel` for `tree`, generalising pools and stock. `sum_one`: each `roll` sums to 1 under `pct ≤ 100`, `scaleBy` multiplies a list's sum. `noCrit`: with `pct = 0`, `roll` is `[(1, normal)]`, so `tree` is one path; relate it to `FightOutcome.walk` via the monster pool after `n` rounds (`m − n × killStep ≤ 0 ↔ n ≥ roundsToKill`, from `mul_lt_iff_lt_ceilDiv`). `mono_*`: couple the trees state by state with `FightOutcome.coupled` / `drink_coupled` (the deterministic `walk_mono` / `stock_mono` proofs are the pattern). `fightOdds_win_mono_hp` crosses the `effHp ≤ 0` branch: the lower start is a certain loss (winProb 0) there.

If a statement is FALSE (a counterexample exists), stop and report BLOCKED with the counterexample: do not weaken it.

- [ ] **Step 3: Oracle runner**

In `formal/Oracle.lean`, beside `runFightOutcome`:

```lean
/-- A fight's ending distribution (`Formal.FightOdds.fightOdds`), grouped by
ending with summed probabilities. Args: `[rawPlayer, killStep, monsterHp, recon,
dieStep, playerFirst, hp, maxHp, restore, stock, dMonsterHp, killNormal,
killCrit, pCrit, dieNormal, dieCrit, mCrit]`, playerFirst as 0/1. -/
def runFightOdds (args : Array Json) : Json :=
  let i : Nat → Int := fun k => intArg args k
  let t : Formal.FightOutcome.Terms := ⟨i 0, i 1, i 2, i 3, i 4, i 5 != 0⟩
  let d : Formal.FightOdds.Damage := ⟨i 10, i 11, i 12, (i 13).toNat, i 14, i 15, (i 16).toNat⟩
  let xs := Formal.FightOdds.fightOdds t d (i 6) (i 7) (i 8).toNat (i 9).toNat
  let grouped := xs.foldl (fun (acc : List (Formal.FightOdds.Ending × Rat)) e =>
    match acc.find? (·.1 == e.2) with
    | some _ => acc.map fun a => if a.1 == e.2 then (a.1, a.2 + e.1) else a
    | none => acc ++ [(e.2, e.1)]) []
  Json.arr (grouped.map fun (en, p) => Json.mkObj [
    ("win", Json.bool en.win), ("turns", Json.num en.turns), ("hp_end", Json.num en.hpEnd),
    ("used", Json.num (Int.ofNat en.used)),
    ("prob_num", Json.num p.num), ("prob_den", Json.num (Int.ofNat p.den))]).toArray
```

Add `else if kind == "fight_odds" then runFightOdds args` beside `"fight_outcome"` in the dispatch.

- [ ] **Step 4: Differential test**

```python
"""Differential: `ai/fight_odds_core.fight_odds` (merged walk) against the proved
tree `Formal.FightOdds.fightOdds` (spec 2026-10-15 fight-odds §1). Fights are kept
to at most 6 rounds so the unmerged Lean tree (4^rounds paths) stays small."""

from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.fight_odds_core import RoundDamage, fight_odds
from artifactsmmo_cli.ai.fight_terms_core import SCALE, fight_terms
from formal.diff.oracle_client import run_oracle

_case = st.tuples(
    st.integers(min_value=1, max_value=60),                 # monster hp
    st.integers(min_value=10, max_value=60),                # kill normal (whole HP)
    st.integers(min_value=0, max_value=60),                 # kill crit extra
    st.integers(min_value=0, max_value=100),                # p crit
    st.integers(min_value=5, max_value=80),                 # die normal (whole HP)
    st.integers(min_value=0, max_value=80),                 # die crit extra
    st.integers(min_value=0, max_value=100),                # m crit
    st.booleans(),                                          # player first
    st.integers(min_value=-5, max_value=300),               # hp
    st.integers(min_value=1, max_value=300),                # max hp
    st.integers(min_value=0, max_value=120),                # restore
    st.integers(min_value=0, max_value=4),                  # stock
)


@settings(max_examples=200, deadline=None)
@given(cases=st.lists(_case, min_size=1, max_size=10))
def test_fight_odds_matches_lean(cases):
    args, ours = [], []
    for mhp, kn, kx, pc, dn, dx, mc, pf, hp, max_hp, restore, stock in cases:
        kill, die = kn * SCALE, dn * SCALE
        mean_kill = kill + (kx * SCALE * pc) // 100
        mean_die = die + (dx * SCALE * mc) // 100
        terms = fight_terms(1, mean_kill, mhp, 0, mean_die, hp, max_hp, pf)
        damage = RoundDamage(mhp, kill, kill + kx * SCALE, pc, die, die + dx * SCALE, mc)
        args.append([1, mean_kill, mhp, 0, mean_die, 1 if pf else 0, hp, max_hp, restore, stock,
                     mhp, kill, kill + kx * SCALE, pc, die, die + dx * SCALE, mc])
        ours.append(fight_odds(terms, damage, hp, max_hp, restore, stock))
    for mine, row in zip(ours, run_oracle("fight_odds", args), strict=True):
        lean = {(r["win"], r["turns"], r["hp_end"], r["used"]): Fraction(r["prob_num"], r["prob_den"])
                for r in row}
        assert {(e.win, e.turns, e.hp_end, e.used): e.prob for e in mine} == lean
```

(`mhp ≤ 60` against a normal hit ≥ 10 keeps fights within 6 rounds.)

- [ ] **Step 5: Contracts / Manifest / Audit**

Add `import Formal.FightOdds` to `formal/Formal.lean`; in `Contracts.lean` a "FightOdds role contracts" block restating the four theorems as `example`s over the model (follow the PredictWin block at :329-380); `#check` the four theorems in `Manifest.lean`; `#print axioms` them in `Audit.lean`.

- [ ] **Step 6: Build and run**

Run: `cd formal && lake build Formal oracle 2>&1 | tail -5` then `uv run pytest formal/diff/test_fight_odds_diff.py -q --no-cov`
Expected: build succeeds with no `sorry`; diff PASS. `bash formal/gate/check_axioms_safety.sh` passes.

- [ ] **Step 7: Commit**

```bash
git add formal/Formal/FightOdds.lean formal/Formal.lean formal/Oracle.lean formal/Formal/Contracts.lean formal/Formal/Manifest.lean formal/Formal/Audit.lean formal/diff/test_fight_odds_diff.py formal/diff/mutate.py && ARTIFACTSMMO_TOKEN=dummy git commit -m "formal(combat): the fight-odds tree, its sum, no-crit and monotone theorems

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `combat.fight_split` and `combat.win_probability`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/combat.py` (`fight_numbers` builds the split; new `fight_split`, `win_probability`, `_crit_hit`)
- Modify: `src/artifactsmmo_cli/ai/fight_walk.py` (new `odds_walk`)
- Test: `tests/test_ai/test_fight_split.py` (create)
- Modify: `formal/diff/mutate.py` (`FIGHT_SPLIT_MUTATIONS` over `COMBAT_SRC`, and `FIGHT_WALK_SRC` if not present)

**Interfaces:**
- Consumes: Task 1's `RoundDamage`, `fight_odds`, `win_probability`, `Ending`.
- Produces:
  - `FightNumbers.damage: RoundDamage` (new field, last).
  - `combat.fight_split(state, game_data, monster_code) -> tuple[FightTerms, RoundDamage]` — `fight_numbers`' terms and damage.
  - `combat.win_probability(state, game_data, monster_code) -> Fraction` — P(win) from `state.hp` wearing the current utility slots (the equipped restore potion and its `utilityN_slot_quantity`), in the same on-hand loadout `predict_win` reads.
  - `fight_walk.odds_walk(state, game_data, monster, loadout) -> tuple[tuple[Ending, ...], int, str | None]` — like `fight_walk`, from full HP: the endings, the projected max HP, the restore potion code.

- [ ] **Step 1: Write the failing tests**

```python
"""The crit split of a fight's round (spec 2026-10-15 fight-odds §1)."""

from fractions import Fraction

from artifactsmmo_cli.ai.combat import combat_terms, fight_split, win_probability
from artifactsmmo_cli.ai.fight_odds_core import fight_odds
from artifactsmmo_cli.ai.fight_outcome_core import fight_outcome
from artifactsmmo_cli.ai.fight_terms_core import SCALE
from artifactsmmo_cli.ai.fight_walk import fight_walk, odds_walk
```

Build the fixture the way `tests/test_ai/test_combat.py` builds a state and a monster (read it first; reuse its helpers and `tests/test_ai/_monster_fixture.fill_monster_stat_defaults`): a monster `owl` with 1450 HP, attack `{"water": 83}`, no resistance, crit 5, initiative 250; a player with attack `{"earth": 77, "fire": 64}`, no damage bonus, crit 45, initiative 200, 785 HP, no resistance. Then:

- `test_the_crit_hit_rounds_half_up_per_element`: `fight_split(...)[1]` has `kill_normal == 141 * SCALE`, `kill_crit == 212 * SCALE` (96 + 116), `die_normal == 83 * SCALE`, `die_crit == 125 * SCALE`, `p_crit == 45`, `m_crit == 5`, `monster_hp == 1450`.
- `test_the_split_agrees_with_the_terms`: `fight_split(...)[0] == combat_terms(...)`.
- `test_a_heal_lands_in_both_amounts`: give the monster `healing` (read `GameData.monster_healing`'s fixture field); `kill_normal` and `kill_crit` each drop by exactly `terms.kill_step`'s healing term, so `kill_crit - kill_normal` is unchanged.
- `test_win_probability_reads_current_hp_and_the_worn_potion`: at full HP the fixture's P(win) is 0.6308 to four places; at `hp=1` it is 0; wearing a restore potion (70 HP, `utility1_slot_quantity=100`) it is 1.
- `test_odds_walk_with_no_crit_is_the_walk`: with both crits 0, `odds_walk` returns one ending equal to `fight_walk`'s outcome.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_fight_split.py -q --no-cov`
Expected: FAIL with `ImportError: cannot import name 'fight_split'`.

- [ ] **Step 3: Implement**

In `combat.py`:

```python
def _crit_hit(attack: dict[str, int], dmg_global: int, dmg_elements: dict[str, int],
              resist: dict[str, int]) -> int:
    """One CRITICAL turn's damage: each element's net hit ×1.5, rounded half up
    per element — the server's rule (2026-10-15 fight logs: 77 → 116, 83 → 125,
    64 → 96). `(3 × d + 1) // 2` is ⌊1.5 × d + ½⌋ exactly."""
    return sum(
        (3 * _element_damage(attack.get(e, 0), dmg_global + dmg_elements.get(e, 0), resist.get(e, 0)) + 1) // 2
        for e in ELEMENTS
    )
```

In `fight_numbers`, after `kill_step`, `die_step` and `raw_monster` exist:

```python
    crit_player = _crit_hit(p.attack, p.dmg, p.dmg_elements, m_resist)
    crit_monster = _crit_hit(m_attack, 0, {}, p.resistance)
    # Everything a round charges beyond the bare hit (spec 2026-10-15 §1): the
    # expected step less its hit term, applied to both crit outcomes.
    kill_rest = kill_step - raw_player * SCALE - 50 * raw_player * p.critical_strike
    die_rest = die_step - raw_monster * SCALE - 50 * raw_monster * m_crit
    damage = RoundDamage(
        effective_monster_hp,
        raw_player * SCALE + kill_rest, crit_player * SCALE + kill_rest, p.critical_strike,
        raw_monster * SCALE + die_rest, crit_monster * SCALE + die_rest, m_crit,
    )
```

and `return FightNumbers(terms, raw_player, hit, p.max_hp, threat, damage)`. Add `damage: RoundDamage` as the last `FightNumbers` field and update every `FightNumbers(` construction (`grep -rn "FightNumbers(" src tests`).

```python
def fight_split(state: WorldState, game_data: GameData, monster_code: str) -> tuple[FightTerms, RoundDamage]:
    """`fight_numbers`' terms and the round's crit split, from the same integers."""
    n = fight_numbers(state, game_data, monster_code)
    return n.terms, n.damage


def win_probability(state: WorldState, game_data: GameData, monster_code: str) -> Fraction:
    """P(win) of fighting now: from `state.hp`, in the on-hand loadout
    `predict_win` reads, drinking the worn restore potion (spec §4)."""
    terms, damage = fight_split(state, game_data, monster_code)
    restore, stock = worn_restore(state, game_data)
    return odds_win(fight_odds(terms, damage, state.hp,
                               fight_max_hp(state, game_data, monster_code), restore, stock))
```

`worn_restore(state, game_data) -> tuple[int, int]` reads `utility1_slot` / `utility2_slot` with their `_quantity`: the first worn utility with `hp_restore > 0` and no `SPLASH_RESTORE` effect gives `(hp_restore, quantity)`, else `(0, 0)`. Put it in `fight_walk.py` beside `_restore_of` (import `SPLASH_RESTORE` there) and import it into `combat.py` only if that creates no cycle; otherwise place it in `combat.py`. Import `fight_odds_core.win_probability` as `odds_win` to avoid the name clash.

In `fight_walk.py`:

```python
def odds_walk(state: WorldState, game_data: GameData, monster: str,
              loadout: Sequence[tuple[str, int]]) -> tuple[tuple[Ending, ...], int, str | None]:
    """`fight_walk`'s fight as its exact ending distribution (spec §1)."""
    projected, restore_code, restore_hp, restore_stock = wear(state, game_data, loadout)
    max_hp = fight_max_hp(projected, game_data, monster)
    terms, damage = fight_split(projected, game_data, monster)
    return fight_odds(terms, damage, max_hp, max_hp, restore_hp, restore_stock), max_hp, restore_code
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_ai/test_fight_split.py tests/test_ai/test_combat.py tests/test_ai/test_fight_walk.py tests/test_ai/test_party_terms.py -q --cov=artifactsmmo_cli.ai.combat --cov=artifactsmmo_cli.ai.fight_walk --cov-report=term-missing`
Expected: PASS; both modules 100%. Then `uv run pytest formal/diff/test_predict_win_diff.py formal/diff/test_combat_margin_diff.py formal/diff/test_fight_outcome_diff.py -q --no-cov` still PASS (the terms are unchanged).

- [ ] **Step 5: Mutants**

`FIGHT_SPLIT_MUTATIONS` over `COMBAT_SRC` against `tests/test_ai/test_fight_split.py`: crit rounds down (`(3 * _element_damage(...) + 1) // 2` → `(3 * _element_damage(...)) // 2`); `kill_rest` drops the crit term (`- 50 * raw_player * p.critical_strike` removed); `die_rest` drops it likewise; the monster crit hit reads the player's damage bonus (`_crit_hit(m_attack, 0, {}, p.resistance)` → `_crit_hit(m_attack, p.dmg, {}, p.resistance)`); `win_probability` reads max HP instead of current (`state.hp,` → `fight_max_hp(state, game_data, monster_code),`). Run `--check-anchors` and `--only src/artifactsmmo_cli/ai/combat.py`; all killed.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/combat.py src/artifactsmmo_cli/ai/fight_walk.py tests/test_ai/test_fight_split.py formal/diff/mutate.py && ARTIFACTSMMO_TOKEN=dummy git commit -m "feat(combat): a fight's round splits into its normal and crit damage

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

(Also `git add` any test file whose `FightNumbers(` construction you updated.)

---

### Task 4: `loop_rate` prices the expected loop

**Files:**
- Modify: `src/artifactsmmo_cli/ai/loop_rate_core.py` (`expected_xp_per_second`)
- Modify: `src/artifactsmmo_cli/ai/loop_rate.py` (`RESPAWN_TILE`, `LOSS_HP`, `p_win`, expected pricing)
- Modify: `src/artifactsmmo_cli/ai/party_loop.py` (pass `p_win=Fraction(1)`)
- Modify: `formal/Formal/LoopRate.lean` (`expectedXpRate`, `expectedXpRate_sure_win`), `formal/Oracle.lean` (`"expected_xp_rate"`), `formal/diff/test_loop_rate_diff.py`, `Contracts.lean`, `Manifest.lean`, `Audit.lean`
- Test: `tests/test_ai/test_loop_rate.py`, `tests/test_ai/test_loop_rate_core.py`, `tests/test_ai/test_best_loadout.py`
- Modify: `formal/diff/mutate.py` (`LOOP_RATE_READER_MUTATIONS`, `LOOP_RATE_CORE_MUTATIONS`)

**Interfaces:**
- Consumes: Task 3's `odds_walk`; Task 1's `Ending`, `win_probability`; `cost_core.travel_seconds`; `game_data.monster_locations`.
- Produces:
  - `loop_rate_core.expected_xp_per_second(xp_per_kill: int, p_win: Fraction, fight_seconds: Fraction, extra_seconds: Fraction) -> Fraction` = `p_win × xp_per_kill / (fight_seconds + extra_seconds)`.
  - `LoopRate.p_win: Fraction` (new field, after `win`). `LoopRate.win` keeps `fight_outcome`'s yes/no.
  - `loop_rate.RESPAWN_TILE = (0, 0)`, `loop_rate.LOSS_HP = 1`.

**The pricing** (spec §2), in `loop_rate`:

```python
    outcome, max_hp, restore_code = fight_walk(state, game_data, monster, loadout)
    endings, _, _ = odds_walk(state, game_data, monster, loadout)
    p_win = odds_win(endings)
    menu = [(f.restore, f.price, f.held) for f in food]
    extra = (1 - p_win) * travel_seconds(RESPAWN_TILE, _monster_tile(game_data, monster))
    used_mean = {code: Fraction(0) for code, _ in loadout}
    eaten_mean = [Fraction(0)] * len(food)
    recovery_mean = consumed_mean = hp_end_mean = Fraction(0)
    for e in endings:
        used = tuple((code, e.used if code == restore_code else 1) for code, _ in loadout)
        consumed = consumed_seconds([(n, prices[code], held_count(code, state)) for code, n in used])
        if consumed is None:
            return None
        hp_end = e.hp_end // SCALE if e.win else LOSS_HP
        recovery, counts = recovery_choice(max_hp - hp_end, max_hp, menu, EAT_SECONDS)
        recovery_mean += e.prob * recovery
        consumed_mean += e.prob * consumed
        hp_end_mean += e.prob * hp_end
        for code, n in used:
            used_mean[code] += e.prob * n
        for i, k in enumerate(counts):
            eaten_mean[i] += e.prob * k
    extra += recovery_mean + consumed_mean
    xp = game_data.xp_per_kill(monster, state.level, state.wisdom)
    rate = expected_xp_per_second(xp, p_win, FIGHT_SECONDS, extra)
    used_units = tuple((code, math.ceil(used_mean[code])) for code, _ in loadout)
    eaten = tuple((f.code, math.ceil(k)) for f, k in zip(food, eaten_mean, strict=True) if k > 0)
    return LoopRate(rate, xp if p_win > 0 else 0, outcome.win, p_win, FIGHT_SECONDS, recovery_mean,
                    consumed_mean, max_hp, math.floor(hp_end_mean), used_units, eaten)
```

with

```python
RESPAWN_TILE = (0, 0)
"""Where the server puts a character that lost a fight (learning.db 2026-10-15:
every R2D2 owlbear `error:fight_lost` row ends at (0, 0) with hp = 1). Observed
server behaviour, not API data (spec 2026-10-15 fight-odds §2 ruling)."""

LOSS_HP = 1
"""The HP a lost fight leaves (`learning/fight_loop_cost.loss_cost`, live 2026-10-08)."""


def _monster_tile(game_data: GameData, monster: str) -> tuple[int, int]:
    """The monster's spawn tile nearest the respawn tile: where a loss walks back to."""
    tiles = game_data.monster_locations(monster)
    if not tiles:
        raise ValueError(f"{monster} has no spawn tile: a loss's walk back cannot be priced")
    return min(tiles, key=lambda tile: (travel_seconds(RESPAWN_TILE, tile), tile))
```

Rounding rulings (record in the report): `used` and `eaten` round UP (a chosen potion drunk in fewer than every ending must still be carried: `potion_carry` reads `used`); `hp_end` rounds down. The spec's §2 said "rounded down" for both fields; this plan corrects `used`/`eaten` to round up, and Task 6 amends the spec. The `(travel, tile)` key orders ties by the tile tuple — a coordinate, a semantic key, not an alphabetical one.

- [ ] **Step 1: Write the failing tests** in `tests/test_ai/test_loop_rate.py` (reuse its `_gd()` ogre fixture; add a monster location `gd._monster_locations = {"ogre": [(3, 4)]}` or whatever field `GameData.monster_locations` reads — check `game_data.py:668`, and set the ogre's crit through `fill_monster_stat_defaults`' field):
- `test_a_sure_win_prices_as_before`: crits 0, potion loadout that wins → `xp_per_second` equals `xp_per_second(xp, FIGHT_SECONDS, recovery, consumed)` from `loop_rate_core`, `p_win == 1`.
- `test_a_risky_fight_pays_its_losses`: give the player crit so the bare fight is a near-coin-flip (compute P(win) with `odds_walk` in the test); assert `rate.xp_per_second == p * xp / (FIGHT_SECONDS + E[recovery + consumed] + (1 - p) * travel_seconds((0, 0), (3, 4)))` with the expectation built from `odds_walk`'s endings in the test.
- `test_a_loss_still_pays_its_drinks`: a loadout whose drinks happen only in losing endings (stock 1, a fight lost outright) → `rate.consumed_seconds > 0`.
- `test_expected_drinks_round_up`: a chosen restore loadout whose expected drinks is strictly between 0 and 1 → its `used` entry is 1.
- `test_no_spawn_tile_raises`: `gd._monster_locations = {}` → `pytest.raises(ValueError, match="no spawn tile")`.
In `tests/test_ai/test_best_loadout.py`:
- `test_a_restore_potion_beats_a_risky_bare_fight`: R2D2-shaped numbers (bare P(win) ≈ 0.63, a held 70-HP restore potion with a price) → `best_loadout(...).potions` contains the restore potion.
In `tests/test_ai/test_loop_rate_core.py`:
- `test_expected_rate_of_a_sure_win_is_the_rate`: `expected_xp_per_second(30, Fraction(1), F, E) == xp_per_second(30, F, E, Fraction(0))`.
- `test_expected_rate_scales_with_p`: halving `p_win` halves the rate.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_loop_rate.py tests/test_ai/test_loop_rate_core.py tests/test_ai/test_best_loadout.py -q --no-cov`
Expected: FAIL (`expected_xp_per_second` / `p_win` missing).

- [ ] **Step 3: Implement** the core function, the `loop_rate` body above, `LoopRate.p_win`, and `party_loop.py:84`'s `LoopRate(...)` call gains `Fraction(1)` after its `True` (a party rate is priced by `group_outcome`, unchanged in A). Imports at the top: `math`, `travel_seconds` from `artifactsmmo_cli.ai.actions.cost_core`, `odds_walk` from `fight_walk`, `win_probability as odds_win` from `fight_odds_core`, `expected_xp_per_second` from `loop_rate_core`.

```python
def expected_xp_per_second(xp_per_kill: int, p_win: Fraction, fight_seconds: Fraction,
                           extra_seconds: Fraction) -> Fraction:
    """XP per second of a loop whose fight wins with probability `p_win`
    (renewal-reward: expected XP over expected seconds; spec 2026-10-15 §2).
    `extra_seconds` is the expected recovery, consumed price and walk back."""
    if fight_seconds <= 0:
        raise ValueError(f"fight_seconds {fight_seconds} must be positive")
    if xp_per_kill < 0 or extra_seconds < 0 or not 0 <= p_win <= 1:
        raise ValueError(f"xp {xp_per_kill}, extra {extra_seconds}, p_win {p_win} out of range")
    return p_win * xp_per_kill / (fight_seconds + extra_seconds)
```

- [ ] **Step 4: Lean.** In `LoopRate.lean`:

```lean
/-- Expected XP per second of a loop winning with probability `p` (renewal-reward). -/
def expectedXpRate (p : Rat) (xp : Nat) (fight extra : Rat) : Rat :=
  p * (xp : Rat) / (fight + extra)

theorem expectedXpRate_sure_win (xp : Nat) (fight extra : Rat) :
    expectedXpRate 1 xp fight extra = (xp : Rat) / (fight + extra)

theorem expectedXpRate_mono_p (p p' : Rat) (xp : Nat) (fight extra : Rat)
    (hp : p ≤ p') (hd : 0 < fight + extra) :
    expectedXpRate p xp fight extra ≤ expectedXpRate p' xp fight extra
```

Oracle `"expected_xp_rate"`: args `[p_num, p_den, xp, fight_num, fight_den, extra_num, extra_den]` (use `ratArg`), emits `rate_num` / `rate_den`. Extend `formal/diff/test_loop_rate_diff.py` with a hypothesis test comparing `expected_xp_per_second` to it on random rationals (`p` in [0, 1], positive fight, non-negative extra). Contracts/Manifest/Audit as in Task 2 Step 5.

- [ ] **Step 5: Run**

Run: `uv run pytest tests/test_ai/test_loop_rate.py tests/test_ai/test_loop_rate_core.py tests/test_ai/test_best_loadout.py tests/test_ai/test_party_loop.py formal/diff/test_loop_rate_diff.py formal/diff/test_best_loadout_diff.py -q --cov=artifactsmmo_cli.ai.loop_rate --cov=artifactsmmo_cli.ai.loop_rate_core --cov-report=term-missing` (after `cd formal && lake build Formal oracle`)
Expected: PASS, both 100%. Then the whole AI suite: `uv run pytest tests/test_ai -q -x --no-cov -n auto` — fix any test that asserted the old certain-win rate against a fixture with crit > 0 by building its expectation from `odds_walk` (not by zeroing the fixture's crit); list each such test in the report.

- [ ] **Step 6: Mutants** — `LOOP_RATE_READER_MUTATIONS` gains: a loss walks back for free (`extra = (1 - p_win) * travel_seconds(...)` → `extra = Fraction(0)`); a loss recovers from its own pool (`hp_end = e.hp_end // SCALE if e.win else LOSS_HP` → `hp_end = e.hp_end // SCALE`); drinks round down (`math.ceil(used_mean[code])` → `math.floor(used_mean[code])`); the rate ignores the odds (`expected_xp_per_second(xp, p_win, ...)` → `expected_xp_per_second(xp, Fraction(1), ...)`); the farthest spawn tile (`min(tiles, ...)` → `max(tiles, ...)`). `LOOP_RATE_CORE_MUTATIONS` gains: `p_win *` dropped. `--check-anchors`, `--only` both files; all killed.

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/loop_rate.py src/artifactsmmo_cli/ai/loop_rate_core.py src/artifactsmmo_cli/ai/party_loop.py tests/test_ai/test_loop_rate.py tests/test_ai/test_loop_rate_core.py tests/test_ai/test_best_loadout.py formal/Formal/LoopRate.lean formal/Oracle.lean formal/Formal/Contracts.lean formal/Formal/Manifest.lean formal/Formal/Audit.lean formal/diff/test_loop_rate_diff.py formal/diff/mutate.py && ARTIFACTSMMO_TOKEN=dummy git commit -m "feat(combat): the fight loop's XP rate is priced by its win odds

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

(Add every other test file you changed in Step 5.)

---

### Task 5: Calibration record and report

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/models.py:783` (`CombatLoadoutOutcome.p_win: float | None = None`)
- Modify: `src/artifactsmmo_cli/ai/learning/store.py` (migration beside the `level` one at ~:250; `record_combat_outcome(..., p_win: Fraction | None = None)`; `CombatLoadoutOutcomeRow.p_win: float | None`; `combat_loadout_outcomes` fills it)
- Modify: `src/artifactsmmo_cli/ai/player.py:4317` (`_record_combat_outcome` passes `win_probability(...)` for a solo fight; a party fight passes None)
- Modify: `src/artifactsmmo_cli/commands/combat_loadout_report.py:24` (fill `p_win`), `src/artifactsmmo_cli/ai/macro/loadout_calibration.py` (bucket table)
- Test: `tests/test_ai/test_learning_store.py`, `tests/test_ai/test_player*.py` (the file testing `_record_combat_outcome`: `grep -rln "_record_combat_outcome\|record_combat_outcome" tests`), `tests/test_ai/test_loadout_calibration.py` or wherever `loadout_calibration_report` is tested, `tests/test_commands/test_combat_loadout_report.py`

**Interfaces:**
- Consumes: Task 3's `combat.win_probability`.
- Produces: column `combat_loadout_outcome.p_win REAL` (nullable); `CombatLoadoutOutcomeRow.p_win`; report section "P(win) calibration".

The column is a float because it is a stored diagnostic, never a decision input (`float(p)` at write). Rows written before it are NULL and are left out of the buckets.

- [ ] **Step 1: Failing tests**
- store: `record_combat_outcome("combat:owl", {}, True, False, 34, p_win=Fraction(63, 100))` then `combat_loadout_outcomes()[0].p_win == 0.63`; omitting it stores None.
- migration: a DB created with the old table (create it with raw SQL lacking `p_win`) gains the column on `LearningStore(...)` open, and its old row reads `p_win is None`.
- player: a resolved solo fight records `p_win == float(win_probability(prev_state, gd, monster))` (monkeypatch `player.win_probability` to return `Fraction(1, 2)` and assert 0.5); a party fight records None.
- report: rows with p_win 0.05, 0.63, 0.66, 0.97 and actual wins F, T, F, T give a table with buckets `0.0-0.1`, `0.6-0.7`, `0.9-1.0`: fights 1/2/1, mean predicted 5%/64.5%/97%, observed 0%/50%/100%. Rows with `p_win=None` are not counted; with no `p_win` rows the section says "No P(win) recorded yet."

- [ ] **Step 2: Run to verify failure** — `uv run pytest <the files above> -q --no-cov`; FAIL on the missing field.

- [ ] **Step 3: Implement.** Migration:

```python
            if "p_win" not in clo_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE combat_loadout_outcome ADD COLUMN p_win REAL")
```

Report: a `_p_win_buckets(rows)` helper in `loadout_calibration.py` (bucket = `min(int(p * 10), 9)`), appended as a `## P(win) calibration` markdown table `| bucket | fights | mean predicted | observed |` after the existing per-task table.

- [ ] **Step 4: Run** the same files with `--cov` on the four modules; 100%.

- [ ] **Step 5: Mutants** — over `STORE_SRC`/the report module (find their names in `mutate.py`): the migration skipped (`if "p_win" not in clo_cols:` → `if False:`); the bucket of p = 1.0 overflows (`min(int(p * 10), 9)` → `int(p * 10)`); a party fight records the solo odds. `--check-anchors`; all killed.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/models.py src/artifactsmmo_cli/ai/learning/store.py src/artifactsmmo_cli/ai/player.py src/artifactsmmo_cli/commands/combat_loadout_report.py src/artifactsmmo_cli/ai/macro/loadout_calibration.py formal/diff/mutate.py <test files> && ARTIFACTSMMO_TOKEN=dummy git commit -m "feat(learning): every fight records its win odds; the report buckets them

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Cost check, spec amendment, merge, live probe (controller)

- [ ] **Step 1: Cost.** In the worktree and in main (base), time `best_loadout` over every character's live state and its band monsters with a scratch script (no TOKEN in the worktree: run it from the main checkout against `PYTHONPATH` of the worktree's `src`). Budget: worktree time < 2 × base time per character. Over budget: report, do not merge; the fix is a cache or state bound, decided then.
- [ ] **Step 2: Spec amendment.** In the spec's §2 `LoopRate` paragraph, record that `used` and `eaten` round UP (Task 4 ruling) and why. Commit.
- [ ] **Step 3: Gate and merge.** From main: `git merge --ff-only feat/fight-odds`; `bash formal/gate.sh > <scratch>/gate.log 2>&1; echo $? > <scratch>/gate.rc`; read the rc in its own call; push only on 0: `git push origin HEAD:main`. Remove the worktree and branch.
- [ ] **Step 4: Probe.** `uv run artifactsmmo plan R2D2 --learn` plus a scratch probe printing `best_loadout(...)` for owlbear: expect `p_win` ≈ 0.63 bare and a restore potion chosen if R2D2 has a route to one; else owlbear's rate below the band's best. `uv run artifactsmmo plan <each char> --learn` runs without error (the no-spawn-tile raise must not fire live).
- [ ] **Step 5: Report** to the user: commits, rulings, the probe result, and "restart the fleet". Live checks after restart are the spec's Live verification section.
