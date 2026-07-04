"""Differential (C1b): the acquirability tables match an INDEPENDENT recompute.

The generator emits `gatherableItems` / `monsterDropItems` / `acquirableCert`
/ `acquirableWitness` / `acquirableFrontier` into the fixture via a forward
fixpoint; `WitnessAcquirable.lean` kernel-verifies the cert's closure property
and the restricted sweep's winnability. This harness closes the remaining
loop with a DIFFERENT algorithm (per-code recursive descent, not the
generator's fixpoint) straight from the snapshot, and re-runs the PRODUCTION
sweep over the cert-restricted pool — pinning the emitted tables against
production behaviour, not against the generator's own code.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from formal.diff.test_winnable_across_band_diff import (
    BASE_STATS_PATH,
    SNAPSHOT_PATH,
    _game_data_from_snapshot,
    _item_stats_from_snapshot,
)
from formal.sim.winnable_witness import BAND_HI, BAND_LO, build_witness_row

FIXTURE = Path(__file__).resolve().parents[1] / "Formal/Liveness/GameDataFixture.lean"


def _lean_str_list(src: str, name: str) -> list[str]:
    m = re.search(rf"def {name} : List String :=\n  \[([^\]]*)\]", src)
    assert m, name
    return re.findall(r'"([^"]+)"', m.group(1))


def test_acquirability_tables_match_independent_recompute():
    snap = json.loads(Path(SNAPSHOT_PATH).read_text())
    src = FIXTURE.read_text()

    gather = sorted(set(snap["resource_drops"].values()))
    drops = sorted({i for lst in snap["monster_drops"].values() for i in lst})
    assert _lean_str_list(src, "gatherableItems") == gather
    assert _lean_str_list(src, "monsterDropItems") == drops

    # Independent closure: recursive descent per code (the generator uses a
    # forward fixpoint — agreement is a real cross-check, not an echo).
    recipes = snap["crafting_recipes"]
    sources = set(gather) | set(drops)

    def closable(c: str, depth: int = 0) -> bool:
        if c in sources:
            return True
        if depth > 10:
            return False
        r = recipes.get(c)
        return bool(r) and all(closable(i, depth + 1) for i in r)

    universe = set(recipes) | sources | set(snap["item_stats"])
    for ings in recipes.values():
        universe |= set(ings)
    expected_cert = sorted(c for c in universe if closable(c))
    assert _lean_str_list(src, "acquirableCert") == expected_cert

    # Production sweep over the cert-restricted pool: frontier + row identity.
    stats = _item_stats_from_snapshot(snap)
    gd = _game_data_from_snapshot(snap, stats)
    cert = set(expected_cert)
    acq_stats = {c: s for c, s in stats.items() if c in cert}
    base = json.loads(Path(BASE_STATS_PATH).read_text())["base_stats"]
    frontier: list[int] = []
    rows = []
    for level in range(BAND_LO, BAND_HI):
        base_row = base.get(str(level))
        if base_row is None:
            continue
        row = build_witness_row(level, base_row, acq_stats, gd)
        if row is None:
            frontier.append(level)
        else:
            rows.append(row)
    m = re.search(r"def acquirableFrontier : List Int :=\n  \[([^\]]*)\]", src)
    assert m
    emitted_frontier = [int(x) for x in re.findall(r"-?\d+", m.group(1))]
    assert emitted_frontier == frontier
    # Row identity: level + monster are pinned exactly (pure fold, deterministic).
    # Loadout CODES are pinned as an acquirability property (every code in the
    # kernel-verified cert), NOT as an exact sequence: C1b surfaced a real
    # production nondeterminism — pick_loadout breaks equal-score ties on
    # set-iteration order (hash seed), e.g. copper_armor vs feather_coat at
    # level 5 across processes. Exact-sequence pinning is deferred to the
    # picker-tiebreak fix (docs/PLAN_c2_composed_liveness.md, filed finding);
    # the kernel theorems are unaffected (they verify the EMITTED rows).
    emitted = re.findall(
        r"\{ level := (\d+), monsterCode := \"([^\"]+)\".*?loadoutCodes := \[([^\]]*)\]",
        src[src.index("def acquirableWitness") :],
        re.S,
    )
    cert_set = set(expected_cert)
    assert len(emitted) == len(rows)
    for (lvl, mon, codes), row in zip(emitted, rows):
        assert int(lvl) == row.level
        assert mon == row.monster_code
        emitted_codes = set(re.findall(r'"([^"]+)"', codes))
        assert emitted_codes <= cert_set, (lvl, sorted(emitted_codes - cert_set))
        assert set(row.loadout_codes) <= cert_set, (lvl, row.loadout_codes)
