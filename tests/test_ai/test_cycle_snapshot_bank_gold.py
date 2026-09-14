"""The TUI cannot show a number that never crosses the boundary.

`CycleSnapshot` carried `gold` (the character's pocket) and `bank_items`, and no
bank gold at all — so the three render sites were not omitting the figure, they
had nothing to omit. Gold is per-character and the bank is the account-wide pool
(`openapi.json`: "The numbers of gold on this character" vs "Quantity of gold in
your bank"), so these are two different facts and both have to travel.
"""

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot


def _snap(**overrides) -> CycleSnapshot:
    """Mirrors the `_snap` helper the three tui test modules already use."""
    base = dict(
        cycle_index=1, timestamp="2026-05-21T12:00:00Z", character="hero",
        x=0, y=0, level=5, xp=50, max_xp=500, hp=100, max_hp=100, gold=8_016,
        selected_goal="g", action="a", outcome="ok",
    )
    base.update(overrides)
    return CycleSnapshot(**base)


def test_bank_gold_travels_on_the_snapshot():
    assert _snap(bank_gold=20_000).bank_gold == 20_000


def test_bank_gold_defaults_to_none_for_snapshots_that_predate_it():
    """Unknown, not zero. A snapshot serialized before this field existed must
    still validate, the rule `path_blocked` and the region field already rely on."""
    assert _snap().bank_gold is None


def test_pocket_gold_and_bank_gold_are_separate_fields():
    """A single `gold` field would make the two indistinguishable downstream."""
    snap = _snap(gold=8_016, bank_gold=20_000)
    assert (snap.gold, snap.bank_gold) == (8_016, 20_000)
