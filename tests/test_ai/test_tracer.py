"""Tests for Tracer / NullTracer / FileTracer."""

import json
import os
import tempfile

from artifactsmmo_cli.ai.tracing import FileTracer, NullTracer, Tracer


class TestNullTracer:
    def test_write_is_no_op(self):
        t = NullTracer()
        t.write_cycle({"any": "data"})  # no exception
        t.close()


class TestFileTracer:
    def test_writes_jsonl_records(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            t = FileTracer(path)
            t.write_cycle({"cycle": 1, "action": "Fight"})
            t.write_cycle({"cycle": 2, "action": "Rest"})
            t.close()

            with open(path) as f:
                lines = f.readlines()
            assert len(lines) == 2
            assert json.loads(lines[0]) == {"cycle": 1, "action": "Fight"}
            assert json.loads(lines[1]) == {"cycle": 2, "action": "Rest"}
        finally:
            os.unlink(path)

    def test_close_is_idempotent(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            t = FileTracer(path)
            t.close()
            t.close()  # no exception
        finally:
            os.unlink(path)
