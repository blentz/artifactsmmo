"""Tests for Phase G-B projections module."""

import json
import math

import pytest
from sqlalchemy.exc import OperationalError
from sqlmodel import Session

import artifactsmmo_cli.ai.learning.projections as proj
from artifactsmmo_cli.ai.equipment.equip_actions_core import EQUIP_SECONDS_PER_ITEM
from artifactsmmo_cli.ai.expected_damage import expected_damage_per_fight
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.learning.fight_loop_cost import TYPICAL_FIGHT_COOLDOWN_SECONDS
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.models import Session as SessionModel
from artifactsmmo_cli.ai.learning.projections import (
    TASKS_COIN_CODE,
    WARMUP_MIN_SAMPLES,
    Yield,
    _best_alternative_repr,
    cheapest_path_to_level,
    cycles_for_progress,
    expected_yield_per_cycle,
    low_yield_cancel_fires,
    project_task_completion,
)
from artifactsmmo_cli.ai.learning.rung_state_core import HP_PER_LEVEL
from artifactsmmo_cli.ai.learning.store import LearningStore
from tests.test_ai.fixtures import make_state


def _harmless(gd: GameData) -> GameData:
    """Give every monster already in `gd` empty attack/resistance and zero crit.

    `cheapest_path_to_level` charges each kill the Rest its damage forces
    (`fight_loop_cost.cycles_per_kill`), so it now reads the monster's combat
    stats. Zero damage means a divisor of exactly 1.0, which keeps the cases
    below pinning xp-per-kill arithmetic and monster SELECTION alone — the damage
    term has its own tests rather than perturbing every existing expectation."""
    codes = list(gd.monster_levels)
    gd._monster_attack = {code: {} for code in codes}
    gd._monster_resistance = {code: {} for code in codes}
    gd._monster_critical_strike = dict.fromkeys(codes, 0)
    # HP only where a case has not already set its own — several pin xp-per-kill,
    # which reads it. The value is irrelevant to the damage term (empty attack
    # already forces 0), it just has to exist.
    existing = dict(getattr(gd.monsters, "hp", None) or {})
    gd._monster_hp = {code: existing.get(code, 1) for code in codes}
    return gd


def _make_cycle(
    cycle_index: int,
    selected_goal: str,
    *,
    delta_xp: int = 0,
    delta_gold: int = 0,
    task_progress: int = 0,
    cycles_to_satisfy: int | None = None,
    delta_skill_xp_json: str = "{}",
    drops_json: str | None = None,
    level: int | None = 1,
) -> dict:
    """Kwargs for Cycle(...) — keep a single template so all tests stay consistent.

    `level` defaults to 1 because that is the level the cases below put the
    character at, and a learned XP rate is only interpretable against the level its
    samples were taken at (`Yield.char_xp_level`). A row with no level makes
    `cheapest_path_to_level` DECLINE the learned branch and answer from the
    published formula instead — so leaving it unset here silently converted every
    observed-branch case into a formula case, and the ones whose two arms happened
    to agree went vacuous rather than red.
    """
    return dict(
        ts=f"2026-05-18T00:{cycle_index:02d}:00Z",
        session_id="s1",
        cycle_index=cycle_index,
        character="hero",
        selected_goal=selected_goal,
        action_repr="X",
        action_class="X",
        outcome="ok",
        level=level,
        delta_xp=delta_xp,
        delta_gold=delta_gold,
        delta_hp=0,
        delta_inv_used=0,
        task_progress=task_progress,
        task_total=10,
        delta_skill_xp_json=delta_skill_xp_json,
        drops_json=drops_json,
        cycles_to_satisfy=cycles_to_satisfy,
    )


def _populate(store: LearningStore, cycles: list[dict]) -> None:
    """Insert raw Cycle rows directly (bypassing _ensure_session_row dance)."""
    store.start_session()
    with Session(store._engine) as s:
        # Force the session row to exist for FK-ish referential clarity.
        if not s.get(SessionModel, store._session_id):
            s.add(SessionModel(
                session_id=store._session_id,
                started_at="2026-05-18T00:00:00Z",
                character="hero",
            ))
        for kw in cycles:
            kw_with_session = dict(kw)
            kw_with_session["session_id"] = store._session_id
            s.add(Cycle(**kw_with_session))
        s.commit()


class TestParseHelpers:
    """Coverage for _parse_skill_xp and _parse_drops error/non-dict paths."""

    def test_non_dict_skill_xp_json_yields_empty(self, tmp_path):
        """Lines 79: valid JSON but non-dict (e.g. list) → returns {}."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(i, "PursueTask(x)", delta_skill_xp_json="[1, 2]") for i in range(3)
        ])
        y = expected_yield_per_cycle("PursueTask(x)", store)
        store.close()
        assert y.skill_xp == {}

    def test_malformed_skill_xp_json_yields_empty(self, tmp_path):
        """Lines 81-82: invalid JSON in delta_skill_xp_json → swallowed → empty."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(i, "PursueTask(x)", delta_skill_xp_json="{broken") for i in range(3)
        ])
        y = expected_yield_per_cycle("PursueTask(x)", store)
        store.close()
        assert y.skill_xp == {}

    def test_non_dict_drops_json_yields_zero_coins(self, tmp_path):
        """Line 93: valid JSON but non-dict drops_json → zero tasks_coins."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(i, "CompleteTask", drops_json='["item"]') for i in range(3)
        ])
        y = expected_yield_per_cycle("CompleteTask", store)
        store.close()
        assert y.tasks_coins == 0.0

    def test_malformed_drops_json_yields_zero_coins(self, tmp_path):
        """Lines 95-96: invalid JSON in drops_json → swallowed → zero coins."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(i, "CompleteTask", drops_json="{broken") for i in range(3)
        ])
        y = expected_yield_per_cycle("CompleteTask", store)
        store.close()
        assert y.tasks_coins == 0.0


class TestYieldType:
    def test_default_empty_yield(self):
        y = Yield()
        assert y.char_xp == 0.0
        assert y.skill_xp == {}
        assert y.gold == 0.0
        assert y.tasks_coins == 0.0
        assert y.sample_count == 0


class TestExpectedYieldPerCycle:
    def test_empty_store_returns_empty_yield(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        y = expected_yield_per_cycle("PursueTask(x)", store)
        store.close()
        assert y.sample_count == 0
        assert y.char_xp == 0.0

    def test_aggregates_char_xp_and_gold(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(i, "PursueTask(x)", delta_xp=10, delta_gold=2) for i in range(5)
        ])
        y = expected_yield_per_cycle("PursueTask(x)", store)
        store.close()
        assert y.sample_count == 5
        assert y.char_xp == 10.0
        assert y.gold == 2.0

    def test_aggregates_skill_xp_from_json(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(i, "PursueTask(x)",
                        delta_skill_xp_json=json.dumps({"woodcutting": 4}))
            for i in range(4)
        ])
        y = expected_yield_per_cycle("PursueTask(x)", store)
        store.close()
        assert y.skill_xp == {"woodcutting": 4.0}

    def test_parses_tasks_coin_from_drops_json(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        # 2 cycles drop 3 coins, 2 drop none → avg = 1.5
        rows = [
            _make_cycle(0, "CompleteTask", drops_json=json.dumps({TASKS_COIN_CODE: 3})),
            _make_cycle(1, "CompleteTask", drops_json=json.dumps({TASKS_COIN_CODE: 3})),
            _make_cycle(2, "CompleteTask"),
            _make_cycle(3, "CompleteTask"),
        ]
        _populate(store, rows)
        y = expected_yield_per_cycle("CompleteTask", store)
        store.close()
        assert y.tasks_coins == 1.5

    def test_ignores_other_goals(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(0, "PursueTask(x)", delta_xp=10),
            _make_cycle(1, "FarmMonster", delta_xp=100),
            _make_cycle(2, "PursueTask(x)", delta_xp=10),
        ])
        y = expected_yield_per_cycle("PursueTask(x)", store)
        store.close()
        assert y.sample_count == 2
        assert y.char_xp == 10.0


class TestCyclesForProgress:
    def test_returns_none_below_warmup(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(0, "PursueTask(x)", task_progress=0),
            _make_cycle(1, "PursueTask(x)", task_progress=1),
        ])
        assert cycles_for_progress("PursueTask(x)", store) is None
        store.close()

    def test_median_progress_interval(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        # Need at least WARMUP_MIN_SAMPLES intervals between progress events.
        # Bumping progress every 5 cycles gives one interval per 5 cycles, so
        # use ~5 * (WARMUP_MIN_SAMPLES + 2) cycles to get enough intervals.
        cycles = []
        for i in range((WARMUP_MIN_SAMPLES + 2) * 5):
            tp = i // 5
            cycles.append(_make_cycle(i, "PursueTask(x)", task_progress=tp))
        _populate(store, cycles)
        result = cycles_for_progress("PursueTask(x)", store)
        store.close()
        assert result is not None
        assert 4.0 <= result <= 6.0


class TestProjectTaskCompletion:
    @staticmethod
    def _gd_rewards(task_code: str, *, gold: int, coin: int) -> GameData:
        """GameData whose completion payout for `task_code` is the given API
        gold/tasks_coin amounts (so the projection reads them, never a literal)."""
        gd = GameData()
        gd._task_gold_rewards = {task_code: gold}
        gd._task_coin_rewards = {task_code: coin}
        return gd

    def test_no_task_returns_none(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        state = make_state(task_code=None, task_total=0, task_progress=0)
        assert project_task_completion(state, GameData(), store) is None
        store.close()

    def test_satisfied_task_returns_none(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        state = make_state(task_code="x", task_total=10, task_progress=10)
        assert project_task_completion(state, GameData(), store) is None
        store.close()

    def test_reward_projection_uses_api_task_rewards(self, tmp_path):
        """With no yield history the payout is exactly the API completion reward —
        gold from `task_gold_reward`, coins from `task_coin_reward` — not a
        hardcoded 150/3."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        state = make_state(task_code="gudgeon", task_type="items",
                           task_total=20, task_progress=5)
        gd = self._gd_rewards("gudgeon", gold=140, coin=5)
        proj = project_task_completion(state, gd, store)
        store.close()
        assert proj is not None
        # 15 remaining * 15 cycles/progress = 225 cycles
        assert proj.cycles_remaining == 225.0
        # No yield data → expected_char_xp = 0
        assert proj.expected_char_xp == 0.0
        # No yield data → expected_gold = 0 + API gold(140)
        assert proj.expected_gold == 140.0
        # No yield data → expected_tasks_coins = 0 + API coin(5)
        assert proj.expected_tasks_coins == 5.0
        # No history → confidence = 0
        assert proj.confidence == 0.0

    def test_confidence_scales_with_sample_count(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        # 15 cycles → confidence = 15 / (10*3) = 0.5
        _populate(store, [
            _make_cycle(i, "PursueTask(x)", delta_xp=5, delta_gold=1, task_progress=i)
            for i in range(15)
        ])
        state = make_state(task_code="x", task_type="items",
                           task_total=20, task_progress=5)
        gd = self._gd_rewards("x", gold=150, coin=3)
        proj = project_task_completion(state, gd, store)
        store.close()
        assert proj is not None
        assert 0.4 < proj.confidence < 0.6


class TestCheapestPathToLevel:
    def _gd_with_monsters(self, monsters: dict[str, int]) -> GameData:
        """Monsters that deal NO damage, so `cycles_per_kill` is exactly 1.0 and
        these cases keep pinning xp-per-kill arithmetic alone. Damage is given
        its own tests below (`test_bloodier_monster_loses_the_argmax`)."""
        gd = GameData()
        gd._monster_level = monsters
        return _harmless(gd)

    def test_returns_empty_path_when_already_at_target(self, monkeypatch, tmp_path):
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        state = make_state(level=10)
        plan = cheapest_path_to_level(10, state, store, self._gd_with_monsters({}))
        store.close()
        assert plan.total_cycles == 0.0
        assert plan.segments == []
        assert plan.blocked is False

    def test_uses_documented_xp_formula_when_no_observations(self, monkeypatch, tmp_path):
        """No store data → use game_data.xp_per_kill (documented formula)
        instead of magic constants."""
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd_with_monsters({"chicken": 1})
        gd._monster_hp = {"chicken": 60}
        gd._monster_type = {"chicken": "normal"}
        state = make_state(level=1, xp=0, max_xp=100)
        plan = cheapest_path_to_level(2, state, store, gd)
        store.close()
        # xp_per_kill(chicken, L1) = 22 per documented formula, and ONE KILL IS
        # ONE CYCLE, so xp_per_cycle = 22 and gaining 100 XP costs ceil(100/22)
        # ≈ 4.5 cycles.
        #
        # This test used to assert 100 < total_cycles < 200, pinning the old
        # `xp_per_kill / DEFAULT_FIGHT_CYCLES` where the divisor was a 30-SECOND
        # cooldown masquerading as a cycle count. Those bounds were the bug's
        # own arithmetic written down as an expectation, which is why the suite
        # stayed green while the projection ran ~80x high (2026-08-07).
        assert not plan.blocked
        assert plan.segments[0].monster_code == "chicken"
        assert plan.segments[0].xp_per_cycle == 22
        assert plan.segments[0].cycles_per_kill == 1.0
        assert 4 < plan.total_cycles < 6

    def test_total_cycles_is_denominated_in_kills_not_seconds(self, monkeypatch, tmp_path):
        """THE UNIT, pinned directly. A projected cycle is one executed action,
        so the projected cost of a level is the NUMBER OF KILLS it takes — never
        that number scaled by a cooldown duration.

        Stated as an identity rather than a range so no future divisor can slip
        back in unnoticed: whatever the xp arithmetic, total_cycles must equal
        xp_needed / xp_per_kill."""
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd_with_monsters({"chicken": 1})
        gd._monster_hp = {"chicken": 60}
        gd._monster_type = {"chicken": "normal"}
        state = make_state(level=1, xp=0, max_xp=100)
        plan = cheapest_path_to_level(2, state, store, gd)
        store.close()

        xp_per_kill = gd.xp_per_kill("chicken", 1, wisdom=state.wisdom)
        assert plan.total_cycles == pytest.approx(100 / xp_per_kill)
        # ...and emphatically NOT the seconds-scaled figure the old code gave.
        assert plan.total_cycles < 100 / xp_per_kill * 2

    def _bloody(self, gd: GameData, code: str, attack: dict[str, int]) -> GameData:
        """Give one monster real attack, so it forces a Rest per kill."""
        gd._monster_attack = {**dict(gd.monsters.attack), code: attack}
        return gd

    def test_bloodier_monster_loses_the_argmax(self, monkeypatch, tmp_path):
        """THE PER-MONSTER DIVISOR, pinned where the differential cannot see it.

        `cheapest_path_to_level` charged every kill exactly one cycle until
        2026-08-07, so a monster that costs a Rest every kill ranked identically
        to one that costs none. Measured that day, every character ran ~1 Rest per
        Fight, i.e. the fight action was only ~51% of the loop.

        A UNIFORM divisor could never change this argmax, which is why
        `formal/diff/test_cheapest_path_diff.py` (structural, and deliberately
        built with harmless monsters) cannot pin it. This one is per-monster: the
        bloody monster here has a STRICTLY HIGHER xp-per-kill and must still lose,
        because it only delivers that xp every two cycles."""
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd_with_monsters({"bruiser": 4, "pushover": 3})
        gd._monster_hp = {"bruiser": 120, "pushover": 60}
        gd._monster_type = {"bruiser": "normal", "pushover": "normal"}
        state = make_state(level=3, xp=0, max_xp=100, attack={"earth": 40})
        self._bloody(gd, "bruiser", {"earth": 500})

        # 31 xp/kill against 22 — but the bruiser only delivers its 31 every TWO
        # cycles (15.5/cycle), so the gentler monster wins on throughput. Pinned
        # as an assertion so a catalogue change that closes the per-kill gap
        # breaks this loudly instead of making it vacuous.
        assert (gd.xp_per_kill("bruiser", 3, wisdom=state.wisdom)
                > gd.xp_per_kill("pushover", 3, wisdom=state.wisdom)), (
            "fixture drift: the bloody monster must be the better one PER KILL, "
            "or this proves nothing about the divisor"
        )
        plan = cheapest_path_to_level(4, state, store, gd)
        store.close()
        assert plan.segments[0].monster_code == "pushover"
        assert plan.segments[0].cycles_per_kill == 1.0

    def test_a_forced_full_bar_rest_costs_more_than_three_fights(
            self, monkeypatch, tmp_path):
        """The magnitude, not just the ordering.

        This monster takes the character's whole bar, so recovery is a 100-second
        Rest — 3.33 fights' worth of elapsed time against a ~30s Fight. The level
        therefore costs 4.33x the bare fight count, not the 2.0x the superseded
        flat-one-action-per-rest model reported. Pinning 2.0 here was pinning the
        cap that shut the defensive-gear channel."""
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd_with_monsters({"chicken": 1})
        gd._monster_hp = {"chicken": 60}
        gd._monster_type = {"chicken": "normal"}
        state = make_state(level=1, xp=0, max_xp=100, attack={"earth": 40})
        self._bloody(gd, "chicken", {"earth": 500})
        plan = cheapest_path_to_level(2, state, store, gd)
        store.close()

        xp_per_kill = gd.xp_per_kill("chicken", 1, wisdom=state.wisdom)
        # Premise: the damage really does take the whole bar, or the rest term
        # is not at its ceiling and this measures some milder regime instead.
        assert expected_damage_per_fight(state, gd, "chicken") >= state.max_hp
        expected = 1.0 + 100 / TYPICAL_FIGHT_COOLDOWN_SECONDS
        assert plan.segments[0].cycles_per_kill == pytest.approx(expected)
        assert plan.total_cycles == pytest.approx(100 / xp_per_kill * expected)

    def test_the_total_is_finite_exactly_when_the_last_rung_reaches_target(
            self, monkeypatch, tmp_path):
        """S-003's invariant, added after the contradiction hunt found S-003 and
        S-012 prescribing DIFFERENT TOTALS for the same call.

        S-003 said the total IS the sum of the rungs; S-012 said a stopped walk
        reports a not-finite total. Both were reachable and they disagree outright --
        a walk crossing rungs of 2.5 and 1.25 and then stopping owes 3.75 under one
        and +inf under the other. The repair is this invariant, so the total and the
        rungs can never tell different stories about whether the target was reached.
        """
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "inv.db"), character="hero")
        gd = self._gd_with_monsters({"chicken": 1})
        gd._monster_hp = {"chicken": 60}
        gd._monster_type = {"chicken": "normal"}
        state = make_state(level=1, xp=0, max_xp=100, attack={"earth": 40})
        for target in (2, 5, 50):
            plan = cheapest_path_to_level(target, state, store, gd)
            reached = (plan.segments[-1].to_level if plan.segments else state.level)
            assert math.isfinite(plan.total_cycles) == (reached >= target), (
                target, reached, plan.total_cycles)
        store.close()

    def test_a_zero_rung_walk_is_completed_not_stopped(self, tmp_path):
        """Ratified after the grid's last two open cells. A character already at or
        above the target crosses NO rungs -- and that is a COMPLETED walk, so the
        total is 0 (the sum over nothing) and not the not-finite sentinel a walk that
        fell short reports. Reporting an already-satisfied target as unreachable is
        the one reading that is plainly wrong, and S-003's finite-iff-reached
        invariant holds vacuously rather than by special case."""
        store = LearningStore(db_path=str(tmp_path / "z.db"), character="hero")
        gd = self._gd_with_monsters({"chicken": 1})
        state = make_state(level=7, xp=0, max_xp=100)
        for target in (7, 3):
            plan = cheapest_path_to_level(target, state, store, gd)
            assert plan.segments == []
            assert plan.total_cycles == 0.0
            assert math.isfinite(plan.total_cycles)
        store.close()

    def test_the_rung_sequence_is_strictly_increasing(self, monkeypatch, tmp_path):
        """No level appears twice and each entry advances exactly one level. S-003
        promises the highest level reached is recoverable FROM THE RUNGS ALONE, and
        that is only true if the sequence cannot double back -- which the text
        implied and never required."""
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "s.db"), character="hero")
        gd = self._gd_with_monsters({"chicken": 1})
        gd._monster_hp = {"chicken": 60}
        gd._monster_type = {"chicken": "normal"}
        state = make_state(level=1, xp=0, max_xp=100, attack={"earth": 40})
        plan = cheapest_path_to_level(6, state, store, gd)
        froms = [s.from_level for s in plan.segments]
        assert froms == sorted(set(froms)), froms
        assert all(s.to_level == s.from_level + 1 for s in plan.segments)
        assert froms == list(range(state.level, state.level + len(froms)))
        store.close()

    def test_observed_and_formula_branches_share_one_unit(self, monkeypatch, tmp_path):
        """Both arms of the per-monster loop must yield xp per CYCLE.

        They did not: the observed arm returned `expected_yield_per_cycle`
        (per-cycle, correct) while the formula arm divided by a cooldown in
        seconds, so the two were compared across a ~29x unit gap and any monster
        with observations beat any monster without, regardless of merit. Here the
        observed monster is genuinely WORSE per kill, and must lose."""
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        # chicken is OBSERVED but feeble: 2 char-xp per cycle.
        _populate(store, [
            _make_cycle(i, "GrindCharacterXP(chicken)", delta_xp=2) for i in range(5)
        ])
        gd = self._gd_with_monsters({"chicken": 1, "cow": 1})
        gd._monster_hp = {"chicken": 60, "cow": 60}
        gd._monster_type = {"chicken": "normal", "cow": "normal"}
        state = make_state(level=1, xp=0, max_xp=100)
        plan = cheapest_path_to_level(2, state, store, gd)
        store.close()

        # cow has no observations, so it is costed by the formula (22 xp/kill).
        # 22 per cycle beats the observed 2 per cycle, and would NOT have under
        # the old mixed units (2 vs 22/30 = 0.73).
        assert plan.segments[0].monster_code == "cow"
        assert plan.segments[0].xp_per_cycle == 22

    def test_uses_observed_xp_when_available(self, monkeypatch, tmp_path):
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        # Seed 5 FarmMonster(chicken) cycles at 20 char-xp each
        _populate(store, [
            _make_cycle(i, "GrindCharacterXP(chicken)", delta_xp=20) for i in range(5)
        ])
        gd = self._gd_with_monsters({"chicken": 1})
        # HP 60 so the FORMULA answer is 22, not 20. With `_harmless`'s default HP
        # of 1 the formula also returns 20, and this case passed whether or not the
        # observed branch was taken — it could not distinguish the thing it is
        # named for. Found when adding the level-scoping fix, which flipped the
        # branch this exercises without turning it red.
        gd._monster_hp = {"chicken": 60}
        state = make_state(level=1, xp=0, max_xp=100)
        plan = cheapest_path_to_level(2, state, store, gd)
        store.close()
        assert gd.xp_per_kill("chicken", 1) == 22, "premise: the two arms differ"
        # 100 xp at the OBSERVED 20/cycle = 5 cycles (the formula would give 22).
        assert plan.segments[0].xp_per_cycle == 20.0
        assert plan.total_cycles == 5.0

    def test_blocked_when_no_beatable_monster(self, monkeypatch, tmp_path):
        # Level-gate blocks these high-level monsters (ogre L50 > L1+1, dragon L80
        # similarly), so is_winnable is never reached for them — monkeypatch is still
        # correct for completeness but the level gate fires first.
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd_with_monsters({"ogre": 50, "dragon": 80})
        state = make_state(level=1, xp=0, max_xp=100)
        plan = cheapest_path_to_level(50, state, store, gd)
        store.close()
        assert plan.blocked
        assert plan.total_cycles == float("inf")

    def test_picks_highest_xp_monster(self, monkeypatch, tmp_path):
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, (
            [_make_cycle(i, "GrindCharacterXP(chicken)", delta_xp=2) for i in range(5)] +
            [_make_cycle(5 + i, "GrindCharacterXP(yellow_slime)", delta_xp=15) for i in range(5)]
        ))
        gd = self._gd_with_monsters({"chicken": 1, "yellow_slime": 2})
        state = make_state(level=1, xp=0, max_xp=100)
        plan = cheapest_path_to_level(2, state, store, gd)
        store.close()
        # yellow_slime (lvl 2, char L1) is beatable due to +1 margin, gives 15xp/cyc
        assert plan.segments[0].monster_code == "yellow_slime"

    def test_extends_across_levels(self, monkeypatch, tmp_path):
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd_with_monsters({"chicken": 1, "wolf": 5})
        state = make_state(level=1, xp=0, max_xp=100)
        plan = cheapest_path_to_level(3, state, store, gd)
        store.close()
        # Should have 2 segments (level 1→2, level 2→3)
        assert len(plan.segments) == 2

    def test_next_action_monster_property(self, monkeypatch, tmp_path):
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd_with_monsters({"chicken": 1})
        state = make_state(level=1, xp=0, max_xp=100)
        plan = cheapest_path_to_level(2, state, store, gd)
        store.close()
        assert plan.next_action_monster == "chicken"
        # Empty path → None
        empty = cheapest_path_to_level(1, make_state(level=1), store, gd)
        assert empty.next_action_monster is None

    def test_blocked_when_all_beatable_yield_zero_xp(self, monkeypatch, tmp_path):
        """Line 253: beatable is non-empty but all candidates produce 0 XP per cycle.
        Char L20 vs L1 monster: diff=19 >= 10 → penalty=0.0 → xp_per_kill=0
        → xp_per_cycle=0 → best_code stays None → blocked."""
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd_with_monsters({"chicken": 1})
        gd._monster_hp = {"chicken": 0}
        gd._monster_type = {"chicken": "normal"}
        state = make_state(level=20, xp=0, max_xp=100)
        plan = cheapest_path_to_level(21, state, store, gd)
        store.close()
        assert plan.blocked is True
        assert plan.total_cycles == float("inf")


class TestPathSuccessRateFilter:
    """G-I post-fix: monsters with observed low win-rate excluded from path.

    The old bespoke win-rate filter is now replaced by is_winnable (the single
    combat-beatability verdict shared with the runtime). is_winnable's learned-loss
    veto (>= MIN_WIN_SAMPLES fights at < WIN_RATE_THRESHOLD) subsumes the old
    MIN_PATH_SUCCESS_RATE / MIN_PATH_SAMPLES filter. We monkeypatch is_winnable
    to model the verdict directly, since the test's intent is that a monster
    is_winnable deems unwinnable is excluded from the path.
    """

    def test_low_win_rate_monster_skipped(self, monkeypatch, tmp_path):
        # is_winnable returns False for yellow_slime (learned-loss veto fired),
        # True for chicken — identical to what the old MIN_PATH_SUCCESS_RATE
        # filter produced, but now routed through the shared runtime verdict.
        monkeypatch.setattr(proj, "is_winnable",
                            lambda s, g, code, h: code == "chicken")
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")

        gd = GameData()
        gd._monster_level = {"chicken": 1, "yellow_slime": 2}
        _harmless(gd)
        state = make_state(level=1, xp=0, max_xp=100)

        plan = cheapest_path_to_level(2, state, store, gd)
        store.close()
        # yellow_slime excluded by is_winnable; chicken is the only option.
        assert plan.segments[0].monster_code == "chicken"


class TestIsWinnableFilter:
    """Task-1: cheapest_path uses is_winnable to filter candidates."""

    def test_unwinnable_high_xp_monster_excluded(self, monkeypatch, tmp_path):
        # cow: level 8 (==char), high XP; green_slime: level 4, lower XP. is_winnable
        # says only green_slime is winnable → path picks green_slime despite cow's XP.
        gd = GameData()
        gd._monster_level = {"cow": 8, "green_slime": 4}
        _harmless(gd)
        monkeypatch.setattr(proj, "is_winnable",
                            lambda s, g, code, h: code == "green_slime")
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="r")
        state = make_state(level=8, xp=0, max_xp=100)
        plan = cheapest_path_to_level(9, state, store, gd)
        store.close()
        assert plan.next_action_monster == "green_slime"
        assert plan.blocked is False

    def test_blocked_when_nothing_winnable(self, monkeypatch, tmp_path):
        gd = GameData()
        gd._monster_level = {"cow": 8}
        _harmless(gd)
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: False)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="r")
        state = make_state(level=8, xp=0, max_xp=100)
        plan = cheapest_path_to_level(9, state, store, gd)
        store.close()
        assert plan.blocked is True

    def test_beatability_projected_at_full_hp(self, monkeypatch, tmp_path):
        # The projection rests to max_hp before is_winnable, identical to the
        # runtime `_is_winnable`. A monster winnable WHEN RESTED must stay on the
        # path even from a mid-damage state — else the plan screen would show a
        # lower monster than the bot (which rests first) actually grinds.
        gd = GameData()
        gd._monster_level = {"green_slime": 4}
        _harmless(gd)
        # winnable ONLY at full hp — proves the projection passes the rested state.
        monkeypatch.setattr(proj, "is_winnable",
                            lambda s, g, code, h: s.hp == s.max_hp)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="r")
        damaged = make_state(level=8, xp=0, max_xp=100, hp=10, max_hp=200)
        plan = cheapest_path_to_level(9, damaged, store, gd)
        store.close()
        assert plan.next_action_monster == "green_slime"
        assert plan.blocked is False

    def test_next_monster_is_always_winnable(self, monkeypatch, tmp_path):
        # Regression lock: the projection's emitted next monster MUST pass
        # is_winnable, so the runtime cascade returns the SAME monster.
        gd = GameData()
        gd._monster_level = {"cow": 8, "green_slime": 4}
        _harmless(gd)
        monkeypatch.setattr(proj, "is_winnable",
                            lambda s, g, code, h: code == "green_slime")
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="r")
        state = make_state(level=8, xp=0, max_xp=100)
        nxt = cheapest_path_to_level(9, state, store, gd).next_action_monster
        store.close()
        assert nxt is not None
        assert proj.is_winnable(state, gd, nxt, store) is True


class TestTaskPursuitYield:
    """The `FarmItems` replacement: task-pursuit yield pooled by taskmaster."""

    def _gd(self) -> GameData:
        gd = GameData()
        gd._item_stats = {
            "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource",
                                   crafting_skill="woodcutting", crafting_level=1),
            "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
            "wolf_hair": ItemStats(code="wolf_hair", level=1, type_="resource"),
        }
        gd._crafting_recipes = {"ash_plank": {"ash_wood": 1}}
        gd._resource_drops = {"ash_tree": "ash_wood"}
        gd._resource_drops_full = {"ash_tree": [("ash_wood", 100, 1, 1)]}
        gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
        return gd

    def test_pools_every_task_in_the_same_taskmaster(self, tmp_path):
        """Two different item tasks pool into one rate, weighted by their own
        sample counts — a mean over the union, NOT a mean of means, or a 1-cycle
        task would outvote a 9-cycle one."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, (
            [_make_cycle(i, "PursueTask(ash_plank)", delta_xp=10) for i in range(9)]
            + [_make_cycle(20, "PursueTask(ash_wood)", delta_xp=0)]
        ))
        y = proj.task_pursuit_yield("ash_plank", self._gd(), store)
        store.close()
        assert y.sample_count == 10
        assert y.char_xp == pytest.approx(90 / 10)

    def test_excludes_the_other_taskmaster(self, tmp_path):
        """A drop-only task belongs to the MONSTERS master and must not dilute
        the items rate."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, (
            [_make_cycle(i, "PursueTask(ash_plank)", delta_xp=10) for i in range(5)]
            + [_make_cycle(10 + i, "PursueTask(wolf_hair)", delta_xp=100) for i in range(5)]
        ))
        gd = self._gd()
        items = proj.task_pursuit_yield("ash_plank", gd, store)
        monsters = proj.task_pursuit_yield("wolf_hair", gd, store)
        store.close()
        assert items.sample_count == 5
        assert items.char_xp == pytest.approx(10)
        assert monsters.sample_count == 5
        assert monsters.char_xp == pytest.approx(100)

    def test_pools_skill_xp_too(self, tmp_path):
        """Skill XP is pooled on the same weighted basis as char XP."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [
            _make_cycle(i, "PursueTask(ash_plank)", delta_xp=1,
                        delta_skill_xp_json=json.dumps({"woodcutting": 6}))
            for i in range(4)
        ])
        y = proj.task_pursuit_yield("ash_plank", self._gd(), store)
        store.close()
        assert y.skill_xp == {"woodcutting": pytest.approx(6.0)}

    def test_no_task_history_is_a_cold_start(self, tmp_path):
        """Every live character today: 0 task-goal cycles. The guard must read
        this as 'no comparison possible', not as a zero rate."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        _populate(store, [_make_cycle(i, "GrindCharacterXP(chicken)", delta_xp=5)
                          for i in range(5)])
        y = proj.task_pursuit_yield("ash_plank", self._gd(), store)
        store.close()
        assert y.sample_count == 0


class TestLowYieldCancelFires:
    """Unit tests for the shared low_yield_cancel_fires predicate.

    Every state that is meant to reach a DOWNSTREAM condition carries a pocket
    `tasks_coin`. Since 2026-08-25 the predicate asks for one first — cancelling
    spends a coin (`TaskCancelAction.is_applicable`, HTTP 478 without it), so a
    firing verdict with no coin could only produce an empty plan. A fixture
    without the coin therefore tests the coin gate, not the margin/confidence
    logic it was written for."""

    @staticmethod
    def _gd() -> GameData:
        """GameData carrying API completion rewards for the task codes these
        tests use, so the projection reads real payouts (never a literal)."""
        gd = GameData()
        gd._task_gold_rewards = {"x": 150, "gudgeon": 150}
        gd._task_coin_rewards = {"x": 3, "gudgeon": 3}
        return gd

    def _seed(self, store: LearningStore, cycles: list[dict]) -> None:
        store.start_session()
        with Session(store._engine) as s:
            if not s.get(SessionModel, store._session_id):
                s.add(SessionModel(
                    session_id=store._session_id,
                    started_at="2026-05-18T00:00:00Z",
                    character="hero",
                ))
            for kw in cycles:
                kw_with = dict(kw)
                kw_with["session_id"] = store._session_id
                s.add(Cycle(**kw_with))
            s.commit()

    def _cycle(self, idx: int, goal: str, *, delta_xp: int = 0,
               task_progress: int = 0) -> dict:
        return dict(
            ts=f"2026-05-18T00:{idx:02d}:00Z",
            cycle_index=idx,
            character="hero",
            selected_goal=goal,
            action_repr="X",
            action_class="X",
            outcome="ok",
            delta_xp=delta_xp,
            delta_gold=0,
            delta_hp=0,
            delta_inv_used=0,
            task_progress=task_progress,
            task_total=10,
        )

    def test_returns_false_when_no_history(self):
        state = make_state(task_code="x", task_total=10, task_progress=5)
        assert low_yield_cancel_fires(state, self._gd(), None) is False

    def test_returns_false_when_no_task(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        state = make_state(task_code=None, task_total=0)
        assert low_yield_cancel_fires(state, self._gd(), store) is False
        store.close()

    def test_returns_false_when_task_total_zero(self, tmp_path):
        """task_total == 0 is treated as no active task (fixes means.py bug)."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        state = make_state(task_code="gudgeon", task_total=0, task_progress=0)
        assert low_yield_cancel_fires(state, self._gd(), store) is False
        store.close()

    def test_zero_char_xp_fires_immediately(self, tmp_path):
        """FarmItems 0 xp/cycle + FarmMonster positive → fires without confidence gate."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        cycles = [self._cycle(i, "PursueTask(x)", delta_xp=0, task_progress=i) for i in range(5)]
        cycles += [self._cycle(5 + i, "GrindCharacterXP(slime)", delta_xp=15) for i in range(3)]
        self._seed(store, cycles)
        state = make_state(task_code="gudgeon", task_total=347, task_progress=5,
                           inventory={"tasks_coin": 1})
        assert low_yield_cancel_fires(state, self._gd(), store) is True
        store.close()

    def test_no_fire_when_no_farmitems_history(self, tmp_path):
        """FarmMonster data but no FarmItems samples → cannot determine current rate."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        cycles = [self._cycle(i, "GrindCharacterXP(slime)", delta_xp=15) for i in range(5)]
        self._seed(store, cycles)
        state = make_state(task_code="gudgeon", task_total=50, task_progress=5,
                           inventory={"tasks_coin": 1})
        assert low_yield_cancel_fires(state, self._gd(), store) is False
        store.close()

    def test_no_fire_when_no_alternative_history(self, tmp_path):
        """FarmItems data but no FarmMonster cycles → no alternative repr."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        cycles = [self._cycle(i, "PursueTask(x)", delta_xp=1, task_progress=i) for i in range(35)]
        self._seed(store, cycles)
        state = make_state(task_code="x", task_total=50, task_progress=10,
                           inventory={"tasks_coin": 1})
        assert low_yield_cancel_fires(state, self._gd(), store) is False
        store.close()

    def test_positive_path_fires_above_margin_and_confidence(self, tmp_path):
        """FarmItems 1 xp, FarmMonster 5 xp → 5x margin, sufficient confidence → fires."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        cycles = (
            [self._cycle(i, "PursueTask(x)", delta_xp=1, task_progress=i) for i in range(35)] +
            [self._cycle(35 + i, "GrindCharacterXP(chicken)", delta_xp=5) for i in range(35)]
        )
        self._seed(store, cycles)
        state = make_state(task_code="x", task_total=50, task_progress=10,
                           inventory={"tasks_coin": 1})
        assert low_yield_cancel_fires(state, self._gd(), store) is True
        store.close()

    def test_no_fire_below_confidence_threshold(self, tmp_path):
        """3 FarmItems samples → confidence 0.1 < 0.5 → no fire on positive path."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        cycles = (
            [self._cycle(i, "PursueTask(x)", delta_xp=1, task_progress=i) for i in range(3)] +
            [self._cycle(3 + i, "GrindCharacterXP(chicken)", delta_xp=5) for i in range(3)]
        )
        self._seed(store, cycles)
        state = make_state(task_code="x", task_total=50, task_progress=3,
                           inventory={"tasks_coin": 1})
        assert low_yield_cancel_fires(state, self._gd(), store) is False
        store.close()

    def test_no_fire_below_margin(self, tmp_path):
        """Alt 1.2x better but below 1.5 margin → no fire."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        cycles = (
            [self._cycle(i, "PursueTask(x)", delta_xp=1, task_progress=i) for i in range(30)] +
            [self._cycle(30 + i, "GrindCharacterXP(chicken)", delta_xp=1) for i in range(30)] +
            [self._cycle(60 + i, "GrindCharacterXP(chicken)", delta_xp=2) for i in range(6)]
        )
        self._seed(store, cycles)
        state = make_state(task_code="x", task_total=50, task_progress=10,
                           inventory={"tasks_coin": 1})
        assert low_yield_cancel_fires(state, self._gd(), store) is False
        store.close()

    def test_no_fire_when_alt_yield_has_zero_samples(self, monkeypatch, tmp_path):
        """Line 378: _best_alternative_repr returns a repr but expected_yield_per_cycle
        finds zero samples for it → returns False without firing."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        cycles = [self._cycle(i, "PursueTask(x)", delta_xp=1, task_progress=i) for i in range(5)]
        self._seed(store, cycles)
        # Return a repr that has no cycles in the store for this character.
        monkeypatch.setattr(proj, "_best_alternative_repr",
                            lambda h: "GrindCharacterXP(ghost_that_does_not_exist)")
        state = make_state(task_code="x", task_total=50, task_progress=5,
                           inventory={"tasks_coin": 1})
        assert low_yield_cancel_fires(state, self._gd(), store) is False
        store.close()


class TestBestAlternativeReprEdgeCases:
    """Coverage for _best_alternative_repr error/empty-counts paths."""

    def test_returns_none_on_sqlalchemy_error(self, monkeypatch, tmp_path):
        """Lines 337-338: SQLAlchemy error → returns None gracefully."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        store.start_session()

        def _raise(self, stmt):
            raise OperationalError("stmt", {}, Exception("closed"))

        monkeypatch.setattr(Session, "exec", _raise)
        result = _best_alternative_repr(store)
        assert result is None
        store.close()

    def test_returns_none_when_all_rows_none(self, monkeypatch, tmp_path):
        """Line 346: rows non-empty but all entries are None → counts empty → None."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        store.start_session()
        monkeypatch.setattr(Session, "exec", lambda self, stmt: iter([None]))
        result = _best_alternative_repr(store)
        assert result is None
        store.close()


class TestLearnedRateIsLevelScoped:
    """A learned XP rate belongs to the level it was measured at.

    THE DEFECT, measured live on 2026-08-09 and written up in
    `docs/FINDING_learned_rate_launders_grey_penalty.md`. The learned branch of
    `cheapest_path_to_level` reused one rate at every rung of a walk that climbs up
    to 38 levels. The game's XP award is a function of the gap between character
    and monster and goes to ZERO eleven or more levels above it, so reusing the rate
    deleted that rule from every projection that had any observation at all.

    C3P0 thereby projected reaching level 50 — the terminal objective — by farming
    a LEVEL 4 slime at a flat 7.0 XP per cycle from rung 12 to rung 49. A trunk
    that reaches 50 at acquisition cost zero is unbeatable in `J`, so four of five
    live characters sat on that projection. R2D2, whose only observation was
    negative and therefore declined, fell through to the formula branch and
    correctly reported a wall — it was the only honest character in the account.
    """

    def _seed_grind(self, store: LearningStore, monster: str, *,
                    at_level: int | None, xp_per_cycle: int, n: int = 20) -> None:
        store.start_session()
        with Session(store._engine) as s:
            if not s.get(SessionModel, store._session_id):
                s.add(SessionModel(session_id=store._session_id,
                                   started_at="2026-08-09T00:00:00Z",
                                   character="hero"))
            for i in range(n):
                s.add(Cycle(
                    ts=f"2026-08-09T00:{i:02d}:00Z",
                    session_id=store._session_id,
                    cycle_index=i,
                    character="hero",
                    selected_goal=f"GrindCharacterXP({monster})",
                    action_repr="Fight",
                    action_class="FightAction",
                    outcome="ok",
                    level=at_level,
                    delta_xp=xp_per_cycle,
                ))
            s.commit()

    def _gd(self, monsters: dict[str, int]) -> GameData:
        gd = GameData()
        gd._monster_level = monsters
        gd._monster_type = dict.fromkeys(monsters, "normal")
        return _harmless(gd)

    def test_a_low_level_monsters_rate_does_not_survive_the_grey_boundary(
            self, monkeypatch, tmp_path):
        """C3P0's case, reduced. A rate measured against a level-4 monster while
        the character was level 12 must not still be earning XP at rung 30.

        Before the fix every rung reported the seeded rate unchanged and the walk
        completed; now the rate decays and the walk reports itself blocked."""
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        self._seed_grind(store, "green_slime", at_level=12, xp_per_cycle=7)
        gd = self._gd({"green_slime": 4})
        state = make_state(level=12, xp=0, max_xp=100)

        plan = cheapest_path_to_level(30, state, store, gd)
        store.close()

        assert plan.blocked is True, (
            "a level-4 monster carried the walk past the grey boundary — the "
            "learned rate is being reused unscaled again")
        reached = state.level + len(plan.segments)
        assert 12 < reached < 30
        rates = [s.xp_per_cycle for s in plan.segments]
        assert rates == sorted(rates, reverse=True), (
            f"the rate must decay as the gap widens, got {rates}")
        assert rates[0] > rates[-1], (
            f"a FLAT rate across rungs is the defect itself, got {rates}")

    def test_the_walk_switches_to_a_richer_monster_as_the_gap_widens(
            self, monkeypatch, tmp_path):
        """The correction is not just a dampener — it changes the ARGMAX.

        Observed live: once green_slime's rate decayed, C3P0's walk moved to
        blue_slime and then red_slime. With a stale flat rate the low-level
        monster looked best forever and the higher one was never chosen, so this
        pins SELECTION rather than arithmetic."""
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        # A rich measured rate, so the observed monster genuinely wins at first and
        # the switch below is caused by the DECAY, not by it never having led.
        self._seed_grind(store, "green_slime", at_level=12, xp_per_cycle=30)
        # `peer_slime` is level 13, so it is admissible from rung 12 (the walk
        # allows monster_level <= rung + 1). A level-20 monster would be gated out
        # of every rung the walk reaches and could never win, which would have made
        # this case unfalsifiable rather than informative.
        gd = self._gd({"green_slime": 4, "peer_slime": 13})
        gd._monster_hp = {"green_slime": 60, "peer_slime": 60}
        state = make_state(level=12, xp=0, max_xp=100)

        plan = cheapest_path_to_level(30, state, store, gd)
        store.close()

        chosen = [s.monster_code for s in plan.segments]
        assert chosen[0] == "green_slime", (
            "the measured rate should still win at the level it was measured at")
        assert "peer_slime" in chosen, (
            f"never switched off the decaying monster: {chosen}")
        assert chosen[-1] == "peer_slime"

    def test_an_observation_with_no_recorded_level_falls_through_to_the_formula(
            self, monkeypatch, tmp_path):
        """`level` is nullable on the cycle row. A rate whose samples carry no
        level cannot be restated for another one, so the learned branch declines
        and the published formula answers instead — never the unscaled rate."""
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        self._seed_grind(store, "green_slime", at_level=None, xp_per_cycle=7)
        gd = self._gd({"green_slime": 4})
        gd._monster_hp = {"green_slime": 60}
        state = make_state(level=4, xp=0, max_xp=100)

        plan = cheapest_path_to_level(5, state, store, gd)
        store.close()

        assert plan.segments
        assert plan.segments[0].xp_per_cycle == gd.xp_per_kill("green_slime", 4)

    def test_yield_carries_the_level_its_samples_came_from(self, tmp_path):
        """The field the fix rests on. Without it the rate is uninterpretable away
        from where it was measured."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        self._seed_grind(store, "green_slime", at_level=12, xp_per_cycle=7)
        y = expected_yield_per_cycle("GrindCharacterXP(green_slime)", store)
        store.close()
        assert y.char_xp == 7.0
        assert y.char_xp_level == 12

    def test_the_level_is_the_mean_over_the_window(self, tmp_path):
        """Samples span a level-up. The rate is an average over those cycles, so
        the level it is attributed to is the average too — one number, from the
        same rows, in the same pass."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        self._seed_grind(store, "green_slime", at_level=10, xp_per_cycle=7, n=10)
        with Session(store._engine) as s:
            for i in range(10, 20):
                s.add(Cycle(
                    ts=f"2026-08-09T01:{i:02d}:00Z", session_id=store._session_id,
                    cycle_index=i, character="hero",
                    selected_goal="GrindCharacterXP(green_slime)",
                    action_repr="Fight", action_class="FightAction", outcome="ok",
                    level=14, delta_xp=7))
            s.commit()
        y = expected_yield_per_cycle("GrindCharacterXP(green_slime)", store)
        store.close()
        assert y.char_xp_level == 12

    def test_no_samples_leaves_the_level_unset(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        y = expected_yield_per_cycle("GrindCharacterXP(nobody)", store)
        store.close()
        assert y.sample_count == 0
        assert y.char_xp_level is None


class TestTheWalkCarriesAGrowingBody:
    """S-015: the projected state grows as the walk climbs.

    The walk used to advance `sim_level` and nothing else, so the beatability
    verdict at rung 40 was asked of the character's rung-12 body. The published
    rules grant +5 max HP per level unconditionally, so that growth is arithmetic
    the server will perform, not speculation about gear.

    Ratified as W-001 after ten of twenty-two blind adversaries found it
    independently. It is NOT the cause of the live level-17 wall — measured, twice:
    C3P0 and R2D2 are attack-bound and growing their HP moves neither. So these
    cases carry the whole burden of proof, and each is checked against a reverted
    fix rather than assumed.

    The beatability predicate is BACKGROUND in the spec ("clauses constrain when
    and with what arguments the oracle consults it, never how it decides"), so
    these substitute a predicate that reads exactly one argument — the state's
    max_hp. That is precisely the axis S-015 changes, and it keeps the cases from
    depending on combat arithmetic that has its own tests.
    """

    def _gd(self, monsters: dict[str, int]) -> GameData:
        gd = GameData()
        gd._monster_level = monsters
        gd._monster_type = dict.fromkeys(monsters, "normal")
        return _harmless(gd)

    def _hp_gated(self, monkeypatch, gates: dict[str, int]) -> list:
        """Beatable iff the state handed to the predicate has enough max HP.
        Records every max_hp the walk consulted, so a case can assert on the
        ARGUMENT rather than only on the outcome."""
        seen: list[int] = []

        def predicate(s, g, code, h):
            seen.append(s.max_hp)
            return s.max_hp >= gates[code]

        monkeypatch.setattr(proj, "is_winnable", predicate)
        return seen

    def test_the_consult_sees_the_grown_body_not_the_one_handed_in(
            self, monkeypatch, tmp_path):
        """THE ARGUMENT ITSELF. A character at level 5 with 100 max HP that climbs
        four rungs must be presented to the predicate with 120 max HP by rung 9
        (100 + 5x4), never with 100 throughout."""
        seen = self._hp_gated(monkeypatch, {"wolf": 0})
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd({"wolf": 6})
        gd._monster_hp = {"wolf": 200}
        state = make_state(level=5, xp=0, max_xp=100, max_hp=100)

        cheapest_path_to_level(9, state, store, gd)
        store.close()

        assert seen, "the predicate was never consulted"
        assert min(seen) == 100, "the first rung must use the body as handed in"
        assert max(seen) == 100 + HP_PER_LEVEL * 3, (
            f"the walk never grew the body it consulted: saw {sorted(set(seen))}")

    def test_growth_flips_a_walk_from_blocked_to_complete(self, monkeypatch, tmp_path):
        """W-001's exhibit, reduced. The troll is gated above the starting body and
        below the grown one, so it is unreachable with a frozen state and reachable
        with a growing one — and the wolf goes grey before the target, so the walk
        cannot finish without switching to the troll."""
        self._hp_gated(monkeypatch, {"wolf": 0, "troll": 120})
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd({"wolf": 6, "troll": 12})
        gd._monster_hp = {"wolf": 200, "troll": 3000}
        state = make_state(level=5, xp=0, max_xp=100, max_hp=100)

        plan = cheapest_path_to_level(20, state, store, gd)
        store.close()

        assert plan.blocked is False, (
            "the walk stalled — the troll never became beatable, so the body it "
            "consulted was never grown")
        assert state.level + len(plan.segments) == 20
        assert "troll" in [s.monster_code for s in plan.segments], (
            "never switched to the monster the growth unlocked")

    def test_the_kill_cost_divides_by_the_grown_pool(self, monkeypatch, tmp_path):
        """S-005's recovery term divides damage by the HP pool, and that pool grows
        too. A bigger pool absorbs more fights before a rest, so the same monster
        costs strictly fewer cycles per kill at a later rung."""
        self._hp_gated(monkeypatch, {"wolf": 0})
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        # Built WITHOUT `_harmless`, which zeroes every monster's attack — with no
        # damage there is no forced recovery, the divisor is a constant 1.0, and
        # this case would pass or fail for reasons unrelated to the HP pool.
        gd = GameData()
        gd._monster_level = {"wolf": 6}
        gd._monster_type = {"wolf": "normal"}
        gd._monster_hp = {"wolf": 200}
        # Damage tuned to sit just ABOVE the rest threshold at the starting body and
        # just below it once grown. `rest_cycles_per_fight` saturates at one rest
        # per fight — one Rest refills everything — so a monster that bleeds the
        # character far past the threshold prices identically at every pool size,
        # and the growth would be invisible for a correct reason.
        gd._monster_attack = {"wolf": {"earth": 6}}
        gd._monster_resistance = {"wolf": {}}
        gd._monster_critical_strike = {"wolf": 0}
        state = make_state(level=5, xp=0, max_xp=100, max_hp=100,
                           attack={"earth": 40})

        plan = cheapest_path_to_level(12, state, store, gd)
        store.close()

        per_kill = [s.cycles_per_kill for s in plan.segments]
        assert per_kill[0] > 1.0, (
            "premise: this monster must force recovery, or the divisor is constant")
        assert per_kill[0] > per_kill[-1], (
            f"cost per kill never fell as the HP pool grew: {per_kill}")

    def test_a_walk_that_is_already_done_grows_nothing(self, monkeypatch, tmp_path):
        """S-006 still short-circuits ahead of any of this."""
        seen = self._hp_gated(monkeypatch, {"wolf": 0})
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        plan = cheapest_path_to_level(5, make_state(level=5, max_hp=100),
                                      store, self._gd({"wolf": 6}))
        store.close()
        assert plan.segments == []
        assert seen == []


class TestProgressCarriesAcrossRungs:
    """S-019, which the continuous formulation already satisfies — pinned so it
    cannot be lost.

    W-005 posed the gap as integral kills per rung: `ceil(100/31)` charges a whole
    fourth kill and throws away its surplus, and over thirty-odd rungs that
    over-prices a full climb by roughly one kill per rung. This walk never rounds a
    rung: `estimated_cycles` is a continuous quotient and the total is one sum,
    rounded once by the caller. That is exactly equivalent to carrying the overshoot
    forward, so the clause holds today.

    It held by construction rather than by intent, and nothing stopped a future
    change from taking integral kills "for realism" and reintroducing the discarded
    surplus. These are that stop.
    """

    def _gd(self, monsters: dict[str, int]) -> GameData:
        gd = GameData()
        gd._monster_level = monsters
        gd._monster_type = dict.fromkeys(monsters, "normal")
        return _harmless(gd)

    def test_a_rung_is_not_charged_a_whole_extra_kill(self, monkeypatch, tmp_path):
        """The requirement must NOT divide evenly by the rate, so rounding up would
        be visible. 100 XP at 22 per cycle is 4.545..., never 5."""
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd({"chicken": 1})
        gd._monster_hp = {"chicken": 60}
        state = make_state(level=1, xp=0, max_xp=100)

        plan = cheapest_path_to_level(2, state, store, gd)
        store.close()

        rate = plan.segments[0].xp_per_cycle
        assert 100 % rate != 0, "premise: the rate must not divide the requirement"
        assert plan.segments[0].estimated_cycles == pytest.approx(100 / rate)
        assert plan.segments[0].estimated_cycles != math.ceil(100 / rate)

    def test_the_total_is_the_exact_sum_not_a_sum_of_rounded_rungs(
            self, monkeypatch, tmp_path):
        """Where the surplus goes. Rounding each rung and summing exceeds the exact
        sum by nearly one action per rung; this pins the exact sum."""
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd({"chicken": 1})
        gd._monster_hp = {"chicken": 60}
        state = make_state(level=1, xp=0, max_xp=100)

        plan = cheapest_path_to_level(6, state, store, gd)
        store.close()

        exact = sum(s.estimated_cycles for s in plan.segments)
        rounded = sum(math.ceil(s.estimated_cycles) for s in plan.segments)
        assert plan.total_cycles == pytest.approx(exact)
        assert rounded > exact, (
            "premise: with no fractional rungs this case proves nothing")

    def test_only_the_first_rung_starts_from_the_characters_own_progress(
            self, monkeypatch, tmp_path):
        """S-019's other half. A character already most of the way up its current
        level pays less for THAT rung and a full level's worth for the next."""
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd({"chicken": 1})
        gd._monster_hp = {"chicken": 60}
        state = make_state(level=1, xp=90, max_xp=100)

        plan = cheapest_path_to_level(3, state, store, gd)
        store.close()

        # Each rung has its OWN rate — `xp_per_kill` reads the simulated level, so
        # the same monster pays less as the character out-levels it. Reusing rung
        # 0's rate here compared 100/22 against 100/12 and said nothing about
        # carry-over.
        first, second = plan.segments[0], plan.segments[1]
        assert first.estimated_cycles == pytest.approx(10 / first.xp_per_cycle), (
            "the first rung must need only the 10 XP actually remaining")
        assert second.estimated_cycles == pytest.approx(100 / second.xp_per_cycle), (
            "every later rung needs a whole level's worth")
        assert first.xp_per_cycle != second.xp_per_cycle, (
            "premise: the rates differ, so the two assertions above are distinct")


class TestTheEquipIsCharged:
    """S-020: beatability is judged with the best CARRIED loadout, and putting it
    on is an executed action the rung must pay for.

    The carried-gear reading is deliberate and load-bearing — the gear branch
    projects a candidate by placing the item in INVENTORY, so an oracle that looked
    only at worn gear would make every gear candidate project byte-identically to
    the trunk. W-006 recommended exactly that; it would have re-broken the gear
    branch. Charging the action closes the same hole from the other side.
    """

    def _gd_with_weapon(self) -> GameData:
        gd = GameData()
        gd._monster_level = {"chicken": 1}
        gd._monster_type = {"chicken": "normal"}
        gd._item_stats = {
            "iron_sword": ItemStats(code="iron_sword", level=1, type_="weapon",
                                    attack={"earth": 20}),
        }
        return _harmless(gd)

    def test_carried_gear_costs_one_movement_at_the_rung_that_wears_it(
            self, monkeypatch, tmp_path):
        """One item movement, charged once. The character carries a weapon and
        wears nothing, so the first rung pays for putting it on and no later rung
        pays again — `worn` advances rather than being re-compared to the bare
        start.

        The charge is the published three seconds, not a whole Fight: an empty
        slot takes one movement, and one movement is a tenth of the unit."""
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd_with_weapon()
        bare = make_state(level=1, xp=0, max_xp=100)
        armed = make_state(level=1, xp=0, max_xp=100,
                           inventory={"iron_sword": 1})

        bare_plan = cheapest_path_to_level(4, bare, store, gd)
        armed_plan = cheapest_path_to_level(4, armed, store, gd)
        store.close()

        bare_first, armed_first = (bare_plan.segments[0].estimated_cycles,
                                   armed_plan.segments[0].estimated_cycles)
        one_movement = EQUIP_SECONDS_PER_ITEM / TYPICAL_FIGHT_COOLDOWN_SECONDS
        assert armed_first == pytest.approx(bare_first + one_movement), (
            "the first rung must carry exactly one item movement")
        # Premise: the charge is genuinely below a whole action, or this passes
        # equally well against the superseded one-action-per-slot pricing.
        assert 0 < one_movement < 1
        for i in range(1, len(armed_plan.segments)):
            assert (armed_plan.segments[i].estimated_cycles
                    == pytest.approx(bare_plan.segments[i].estimated_cycles)), (
                f"rung {i} was charged for the equip again — `worn` is not advancing")

    def test_wearing_nothing_and_carrying_nothing_costs_nothing(
            self, monkeypatch, tmp_path):
        """The sixteen empty slots of a bare character must not read as sixteen
        equip actions. `WorldState.equipment` spells them as None and a picked
        loadout may omit them entirely; if those two spellings disagreed, every
        walk would open with a phantom loadout change."""
        monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: True)
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = self._gd_with_weapon()
        state = make_state(level=1, xp=0, max_xp=100)

        plan = cheapest_path_to_level(2, state, store, gd)
        store.close()

        rate = plan.segments[0].xp_per_cycle
        assert plan.segments[0].estimated_cycles == pytest.approx(100 / rate), (
            "a bare character was charged for equipping nothing")
