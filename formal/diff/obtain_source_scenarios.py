"""Shared scenario builder for the SIX-source obtain-model differentials.

Given a "featured" kind, build ``(recipes, owned, bank, sources, target, qty)``
that FORCES that kind to be emitted, so the craft-plan / next-craft differentials
provably exercise all six kinds -- a differential that only ever sees three
kinds agrees VACUOUSLY. Every scenario is a valid input to BOTH the Python cores
(`next_craft_target_pure` / `craft_plan_full` with a real `sources` map) and the
Lean oracle (`next_craft` / `craft_plan` with the 7th `sources` arg); the callers
assert Python and Lean agree step-for-step.
"""

import math
import random

from artifactsmmo_cli.ai.obtain_sources import Source, SourceKind

# The six declared obtain kinds (the emitted `NextAction.kind` strings).
SIX_KINDS = ["gather", "craft", "withdraw", "recycle", "buy", "drop"]

_UNBOUNDED = 10**9


def sources_to_json(sources: dict[str, list[Source]]) -> dict:
    """Encode ``{item: [Source, ...]}`` as the oracle's JSON source map:
    ``{item: [[kindStr, code, yield_per, capacity], ...]}`` (list order = the
    declared priority order the descent scans)."""
    return {
        item: [[s.kind.value, s.code, s.yield_per, s.capacity] for s in lst]
        for item, lst in sources.items()
    }


def scenario(
    rng: random.Random, featured: str
) -> tuple[dict[str, dict[str, int]], dict[str, int], dict[str, int], dict[str, list[Source]], str, int]:
    """Build a scenario forcing ``featured`` to be the emitted kind.

    Returns ``(recipes, owned, bank, sources, target, qty)``. Parameters
    (qty, capacities, recycle copies) are drawn from ``rng`` so successive
    trials of the same kind differ -- including the recycle live-bound
    exhaustion (partial-recovery MIXED plan) whenever ``copies*yield < qty``.
    """
    qty = rng.randint(1, 5)
    target = "top"
    if featured == "gather":
        # Raw target, no recipe, no source -> gather the shortfall.
        return {}, {}, {}, {}, target, qty
    if featured == "craft":
        # Craftable with every input on hand -> craft.
        return {"top": {"leaf": 1}}, {"leaf": rng.randint(qty, qty + 5)}, {}, {}, target, qty
    if featured == "withdraw":
        # A WITHDRAW source (a banked copy) preempts the craft; capacity >= qty
        # so it is a single withdraw of the whole deficit.
        cap = rng.randint(qty, qty + 3)
        return {}, {}, {}, {"top": [Source(SourceKind.WITHDRAW, "top", 1, cap)]}, target, qty
    if featured == "recycle":
        if rng.random() < 0.5:
            # CEIL-PINNING mixed recycle (Finding 2b). `capacity` binds the FIRST
            # recycle at a NON-MULTIPLE of `yp` that is strictly below both the
            # deficit and the live bound (owned*yp), so the debit ⌈cap/yp⌉ leaves
            # a surplus count that a truncating ⌊cap/yp⌋ would NOT. `copies` is
            # exactly ⌈cap/yp⌉ so the ceil debit EXHAUSTS the source on the
            # revisit (→ craft descent) while a floor debit would leave one copy
            # (→ a second recycle). The revisit thus emits a DIFFERENT plan under
            # ceil vs floor — the differential goes red on a floored Lean debit.
            yp = rng.randint(2, 3)
            cap = yp * rng.randint(1, 2) + 1  # non-multiple of yp; ⌈cap/yp⌉ != ⌊cap/yp⌋
            copies = math.ceil(cap / yp)  # ceil-debit exhausts, floor-debit does not
            qty = cap + rng.randint(1, 3)  # deficit exceeds cap → a revisit occurs
            sources = {"top": [Source(SourceKind.RECYCLE, "surplus", yp, cap)]}
            return {"top": {"leaf": 1}}, {"surplus": copies}, {}, sources, target, qty
        # A RECYCLE source: destroy `surplus`, yield `yp` per copy, `copies`
        # owned. When copies*yp < qty the plan mixes recycle + craft descent.
        yp = rng.randint(1, 3)
        copies = rng.randint(1, 6)
        sources = {"top": [Source(SourceKind.RECYCLE, "surplus", yp, copies * yp)]}
        return {"top": {"leaf": 1}}, {"surplus": copies}, {}, sources, target, qty
    if featured == "buy":
        return {}, {}, {}, {"top": [Source(SourceKind.BUY, "npc", 1, _UNBOUNDED)]}, target, qty
    if featured == "drop":
        return {}, {}, {}, {"top": [Source(SourceKind.DROP, "mon", 1, _UNBOUNDED)]}, target, qty
    raise ValueError(f"unknown featured kind {featured!r}")
