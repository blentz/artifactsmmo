"""The oracle transport itself: does serving give the same answers as spawning,
and does it fail loudly when it should?

This tests the differential HARNESS rather than a proved component. It earns its
place in this suite because every other test here trusts the transport: if the
serving layer silently returned the wrong answers, 755 tests would keep passing
while comparing Python against the wrong questions.
"""
from __future__ import annotations

import json

import pytest

import formal.diff.test_calculate_path_diff as calculate_path_diff
from formal.diff.oracle_client import _spawn_once, run_oracle
from formal.diff.oracle_server import OracleServer, align_results

# A few kinds with distinguishable answers, so parity is a real comparison.
_CASES = [
    ("calculate_path", [[1, 2, 3, 4], [0, 0, 5, 5], [-3, 7, 2, -1]]),
    ("calculate_path", [[0, 0, 0, 0]]),
]


@pytest.mark.parametrize("kind,args", _CASES)
def test_serving_agrees_with_spawning(kind, args):
    """The two transports must be indistinguishable. `spawn` is the parity
    oracle: if these ever disagree, the serving layer is wrong, not Lean."""
    assert run_oracle(kind, args) == _spawn_once(kind, args)


def test_many_sequential_requests_stay_aligned():
    """The whole risk of a persistent pipe is positional desync. Fire a long
    sequence of DISTINGUISHABLE requests through one server and check each answer
    belongs to its own question — a shifted stream would still return well-formed
    results, just the previous request's."""
    server = OracleServer()
    try:
        for dx in range(1, 40):
            [result] = server.request("calculate_path", [[0, 0, dx, 0]])
            assert result["total_distance"] == dx, (
                f"answer for dx={dx} came back as {result['total_distance']} — "
                "requests and responses are misaligned"
            )
    finally:
        server.close()


def test_desync_is_detected_and_raises():
    """If the ids ever fail to match, the server must kill the process and raise
    rather than hand back a plausible-looking wrong answer. Simulated by moving
    the client's counter out from under an in-flight exchange."""
    server = OracleServer()
    try:
        server.request("calculate_path", [[0, 0, 1, 0]])  # start the process
        server._next_id = -999  # next request claims an id the oracle won't echo
        with pytest.raises(RuntimeError, match="desync"):
            server.request("calculate_path", [[0, 0, 1, 0]])
    finally:
        server.close()


def test_server_restarts_after_its_process_dies():
    """A crashed oracle must not wedge the rest of the run: the next request
    starts a fresh process and answers correctly."""
    server = OracleServer()
    try:
        server.request("calculate_path", [[0, 0, 1, 0]])
        server._proc.kill()
        server._proc.wait()
        [result] = server.request("calculate_path", [[0, 0, 7, 0]])
        assert result["total_distance"] == 7
    finally:
        server.close()


def test_close_is_idempotent():
    """atexit may fire after an explicit close; a second close must not raise."""
    server = OracleServer()
    server.request("calculate_path", [[0, 0, 1, 0]])
    server.close()
    server.close()


def test_results_are_matched_by_rid_not_position():
    """Scrambling the order must NOT scramble the answers. This is the property
    that makes the transport position-independent: the oracle is free to return
    a batch in any order, and the client still hands each answer back with the
    request that asked for it."""
    tagged = [{"rid": 2, "value": "c"}, {"rid": 0, "value": "a"}, {"rid": 1, "value": "b"}]
    assert align_results(3, tagged, "test") == ["a", "b", "c"]


@pytest.mark.parametrize("tagged,expected_count,match", [
    ([{"rid": 0, "value": "a"}], 2, "returned 1 results for 2 requests"),
    ([{"rid": 0, "value": "a"}, {"rid": 0, "value": "b"}], 2, "duplicate rid 0"),
    ([{"rid": 0, "value": "a"}, {"rid": 5, "value": "b"}], 2, "rid mismatch"),
    ([{"rid": 0, "value": "a"}, {"value": "b"}], 2, "missing rid/value"),
])
def test_every_batch_corruption_raises(tagged, expected_count, match):
    """Truncated, duplicated, out-of-range and malformed batches each raise.
    Before rid-tagging, all four produced well-formed but WRONG answers that a
    differential test would have compared and passed."""
    with pytest.raises(RuntimeError, match=match):
        align_results(expected_count, tagged, "test")


def test_the_differential_gate_can_fail(monkeypatch):
    """Falsifiability witness for the whole differential mechanism.

    Every other test in this suite asserts Python and Lean AGREE. None of them
    demonstrates that disagreement would be noticed — so a transport bug that
    quietly fed each test its own Python answer would leave 762 tests green and
    verifying nothing.

    Here the oracle is made to lie by exactly one unit, and a real differential
    test must fail. If this test ever passes without raising, the differential
    gate has stopped comparing anything.
    """
    truthful = calculate_path_diff.run_oracle

    def lying(kind, inputs):
        return [{**r, "total_distance": r["total_distance"] + 1}
                for r in truthful(kind, inputs)]

    monkeypatch.setattr(calculate_path_diff, "run_oracle", lying)
    with pytest.raises(AssertionError):
        calculate_path_diff.test_python_matches_lean()


def test_structured_payload_round_trips():
    """Structured (non-integer) args must survive the framing intact — the frame
    wraps the request list, it must not reshape the args."""
    server = OracleServer()
    try:
        results = server.request("calculate_path", [[1, 1, 2, 2]])
        assert json.loads(json.dumps(results)) == results
    finally:
        server.close()
