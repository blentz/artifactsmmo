"""The reprs the yield history is keyed by.

A repr is a contract between the cycle writer and every reader that aggregates
over it, and breaking it is silent: a reader asking for a repr nobody emits gets
an empty result, indistinguishable from a cold start. `8c812fb3` broke exactly
that contract for ~2.5 months.
"""

from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.learning.yield_reprs import grind_xp_repr


class TestGrindRepr:
    def test_matches_the_goal_that_actually_writes_it(self):
        """`GrindCharacterXPGoal.__repr__` is `GrindCharacterXP(<monster>)`. If
        these ever diverge the learned-rate lookups go quiet, which is precisely
        the failure this module exists to prevent."""
        assert grind_xp_repr("red_slime") == repr(GrindCharacterXPGoal("red_slime"))
