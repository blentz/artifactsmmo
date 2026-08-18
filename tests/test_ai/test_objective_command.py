"""Tests for the read-only `objective` CLI command.

The command exists because the unified objective's inputs were unobservable: no
shipped tool printed `acquire_cost` / `reachable_level` / `cycles_to_fifty` / the
band, and `j_ranking` lived only in play-traces. `decided_by` is the load-bearing
part — it names the clause that settled the ranking, which is how "J never ran"
becomes a printed fact instead of an inference from a `->L26` prefix.

So the `decided_by` tests are the ones that matter here, and each pins a DIFFERENT
branch of the lexicographic key against a hand-built candidate list. Driving them
through a scenario would leave the branches at the mercy of whatever the fixture
happens to project.
"""

from unittest.mock import MagicMock, patch

import pytest
import typer

from artifactsmmo_cli.ai.tiers.progression_choice import (
    TARGET_LEVEL,
    ProgressionCandidate,
)
from artifactsmmo_cli.commands import objective as objective_cmd


def _candidate(identity: str, cost: int, reach: int, cycles: int = 0,
               failed: bool = False) -> ProgressionCandidate:
    return ProgressionCandidate(identity=identity, acquire_cost=cost,
                                reachable_level=reach, cycles_to_fifty=cycles,
                                failed=failed)


class TestBandName:
    def test_a_candidate_reaching_the_target_is_finite(self):
        assert objective_cmd.band_name(_candidate("x", 0, TARGET_LEVEL)) == "FINITE"

    def test_a_candidate_short_of_the_target_is_unreachable(self):
        assert objective_cmd.band_name(_candidate("x", 0, TARGET_LEVEL - 1)) == "UNREACHABLE"

    def test_a_failed_candidate_reports_failed_whatever_its_level(self):
        """`failed` dominates the level field (S-012), so a FAILED candidate that
        happens to carry a target-reaching level must not read as FINITE."""
        assert objective_cmd.band_name(
            _candidate("x", 0, TARGET_LEVEL, failed=True)) == "FAILED"


class TestDecidedBy:
    def test_an_empty_ranking_decides_nothing(self):
        assert "no candidates" in objective_cmd.decided_by([])

    def test_a_finite_winner_was_decided_by_J(self):
        ranked = [_candidate("trunk", 0, TARGET_LEVEL, cycles=100),
                  _candidate("gear", 40, TARGET_LEVEL, cycles=90)]
        assert objective_cmd.decided_by(ranked) == "S-005 (J) — winner J=100"

    def test_a_lone_furthest_reacher_was_decided_by_key_1(self):
        """The 18% case: one candidate — in practice a weapon — raises the
        ceiling a frozen loadout can grind to, so furthest progress separates it
        before cost is ever consulted."""
        ranked = [_candidate("weapon", 73, 19), _candidate("trunk", 0, 15)]
        verdict = objective_cmd.decided_by(ranked)
        assert "S-006 key 1" in verdict
        assert "L19" in verdict

    def test_a_tie_on_furthest_progress_falls_to_the_cost_key(self):
        """THE LIVE DEGENERACY, pinned. Measured over 10,716 trace cycles and
        reproduced offline on `l20_band_entry`/`l30_band_entry`: every candidate
        reaches the same level, so key 1 separates nothing and the trunk wins for
        costing zero. The verdict must say so, including the tie width."""
        ranked = [_candidate("trunk", 0, 26), _candidate("a", 96, 26),
                  _candidate("b", 1000001, 26)]
        verdict = objective_cmd.decided_by(ranked)
        assert "S-006 key 2" in verdict
        assert "3/3" in verdict
        assert "J never ran" in verdict

    def test_the_tie_width_counts_only_the_top_reach_not_the_whole_field(self):
        """A near-tie and a total tie must be distinguishable — 2/3 is an ordinary
        close call, 3/3 is the degeneracy. Counting every live candidate instead
        of only those sharing the top reach would report both as 3/3."""
        ranked = [_candidate("trunk", 0, 26), _candidate("a", 96, 26),
                  _candidate("b", 5, 20)]
        assert "2/3" in objective_cmd.decided_by(ranked)

    def test_failed_candidates_are_excluded_from_the_tie_count(self):
        """A FAILED candidate has no projection, so counting it among those
        'tied on furthest progress' would overstate the degeneracy."""
        ranked = [_candidate("trunk", 0, 26), _candidate("a", 96, 26),
                  _candidate("bad", 0, 99, failed=True)]
        assert "2/2" in objective_cmd.decided_by(ranked)

    def test_an_all_failed_ranking_says_no_projection_ran(self):
        ranked = [_candidate("a", 0, 0, failed=True), _candidate("b", 0, 0, failed=True)]
        verdict = objective_cmd.decided_by(ranked)
        assert "FAILED" in verdict
        assert "2/2" in verdict


class TestRows:
    def test_cycles_are_reported_only_where_the_spec_says_they_mean_something(self):
        """S-014 declares cycles-to-target void outside the finite band. Printing
        the stored 0 there would publish a meaningless number as if the objective
        had computed it."""
        rows = objective_cmd._rows([_candidate("far", 0, TARGET_LEVEL - 1, cycles=0),
                                    _candidate("near", 0, TARGET_LEVEL, cycles=77)])
        assert rows[0]["cycles_to_target"] is None
        assert rows[1]["cycles_to_target"] == 77

    def test_rank_is_the_input_position(self):
        rows = objective_cmd._rows([_candidate("a", 0, 1), _candidate("b", 0, 1)])
        assert [r["rank"] for r in rows] == [0, 1]


class TestCommand:
    def test_it_refuses_while_a_mutation_run_holds_the_lock(self, capsys):
        with patch.object(objective_cmd, "check_mutation_lock",
                          return_value=MagicMock(state="active", pid=7)):
            with pytest.raises(typer.Exit):
                objective_cmd.objective(character="hero")
        assert "mutation run in progress" in capsys.readouterr().out

    def test_it_requires_a_subject(self, capsys):
        with patch.object(objective_cmd, "check_mutation_lock",
                          return_value=MagicMock(state="clear")):
            with pytest.raises(typer.Exit):
                objective_cmd.objective(character=None, scenario=None)
        assert "give a CHARACTER name or --scenario" in capsys.readouterr().out

    def test_an_unknown_scenario_exits_before_touching_a_store(self, capsys):
        with patch.object(objective_cmd, "check_mutation_lock",
                          return_value=MagicMock(state="clear")):
            with pytest.raises(typer.Exit):
                objective_cmd.objective(character=None, scenario="nope")
        assert "unknown scenario" in capsys.readouterr().out

    def test_a_scenario_ranks_offline_and_names_the_deciding_key(self, capsys):
        """No API client, no Config, no token — the whole point of the scenario
        path. The DECIDED BY line must be present whatever the fixture projects,
        because it is the reason this command exists."""
        with patch.object(objective_cmd, "check_mutation_lock",
                          return_value=MagicMock(state="clear")):
            objective_cmd.objective(character=None, scenario="l1_fresh")
        out = capsys.readouterr().out
        assert "DECIDED BY:" in out
        assert "WINNER:" in out
        assert "milestone=10" in out
        assert "ephemeral :memory: (cold)" in out
        assert "timing:" in out

    def test_a_scenario_emits_machine_readable_json(self, capsys):
        with patch.object(objective_cmd, "check_mutation_lock",
                          return_value=MagicMock(state="clear")):
            objective_cmd.objective(character=None, scenario="l1_fresh", json_out=True)
        import json as json_mod
        payload = json_mod.loads(capsys.readouterr().out)
        assert payload["subject"] == "l1_fresh"
        assert payload["milestone"] == 10
        assert payload["target"] == TARGET_LEVEL
        assert "decided_by" in payload
        assert isinstance(payload["candidates"], list)

    def test_a_scenario_accepts_an_explicit_bundle(self, capsys):
        with patch.object(objective_cmd, "check_mutation_lock",
                          return_value=MagicMock(state="clear")):
            objective_cmd.objective(character=None, scenario="l1_fresh",
                                    bundle=str(objective_cmd._DEFAULT_BUNDLE))
        assert "DECIDED BY:" in capsys.readouterr().out

    def test_learn_reads_the_persistent_db_path(self):
        """`--learn` must open the real learning DB, not an in-memory one — a
        ranking against a cold store is a different ranking, and the header says
        which was used precisely because the two disagree."""
        seen: dict[str, str] = {}

        class _Store:
            def __init__(self, db_path: str, character: str) -> None:
                seen["db_path"] = db_path

            def start_session(self) -> None:
                pass

            def end_session(self, exit_reason: str) -> None:
                pass

            def close(self) -> None:
                pass

        with patch.object(objective_cmd, "check_mutation_lock",
                          return_value=MagicMock(state="clear")):
            with patch.object(objective_cmd, "LearningStore", _Store):
                with patch.object(objective_cmd, "Config") as config:
                    config.from_token_file.return_value = MagicMock(
                        game_data_ttl_minutes=60)
                    with patch.object(objective_cmd, "ClientManager"):
                        with patch.object(objective_cmd, "GamePlayer") as player:
                            player.return_value._initialize.side_effect = RuntimeError("stop")
                            with pytest.raises(RuntimeError):
                                objective_cmd.objective(character="hero", learn=True)
        assert seen["db_path"].endswith("learning.db")

    def test_without_learn_the_store_is_ephemeral(self):
        seen: dict[str, str] = {}

        class _Store:
            def __init__(self, db_path: str, character: str) -> None:
                seen["db_path"] = db_path

            def start_session(self) -> None:
                pass

            def end_session(self, exit_reason: str) -> None:
                pass

            def close(self) -> None:
                pass

        with patch.object(objective_cmd, "check_mutation_lock",
                          return_value=MagicMock(state="clear")):
            with patch.object(objective_cmd, "LearningStore", _Store):
                with patch.object(objective_cmd, "Config") as config:
                    config.from_token_file.return_value = MagicMock(
                        game_data_ttl_minutes=60)
                    with patch.object(objective_cmd, "ClientManager"):
                        with patch.object(objective_cmd, "GamePlayer") as player:
                            player.return_value._initialize.side_effect = RuntimeError("stop")
                            with pytest.raises(RuntimeError):
                                objective_cmd.objective(character="hero", learn=False)
        assert seen["db_path"] == ":memory:"
