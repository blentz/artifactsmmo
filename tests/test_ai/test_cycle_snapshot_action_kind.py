from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot


def _min(**kw):
    base = dict(cycle_index=0, timestamp="t", character="c", x=0, y=0, level=1,
                xp=0, max_xp=1, hp=1, max_hp=1, gold=0, selected_goal="g",
                action="Rest", outcome="ok")
    base.update(kw)
    return CycleSnapshot(**base)


def test_defaults():
    s = _min()
    assert s.action_kind == "other" and s.action_target is None


def test_set_fields():
    s = _min(action_kind="gather", action_target="copper_rocks")
    assert s.action_kind == "gather" and s.action_target == "copper_rocks"
