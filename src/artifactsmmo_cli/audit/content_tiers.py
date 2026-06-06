"""Cluster level-gated game content into capability-unlock tiers — the journey
axis of the behavioral-completeness audit. Pure: inputs are (code -> level) maps
extracted from GameData; no I/O. A tier is a band of `band` levels holding the
items/monsters/resources unlocked within it."""

from dataclasses import dataclass, field


@dataclass
class ContentTier:
    index: int
    name: str
    min_level: int
    max_level: int
    items: list[str] = field(default_factory=list)
    monsters: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)


def _band_index(level: int, band: int) -> int:
    return level // band


def derive_content_tiers(
    items: dict[str, int],
    monsters: dict[str, int],
    resources: dict[str, int],
    band: int = 10,
) -> list[ContentTier]:
    """Group content into `band`-wide level tiers. Returns tiers sorted by level,
    each listing the (sorted) codes unlocked in that band. Bands with no content
    in ANY category are omitted."""
    buckets: dict[int, ContentTier] = {}

    def _tier(level: int) -> ContentTier:
        bi = _band_index(level, band)
        if bi not in buckets:
            lo = bi * band + 1
            hi = lo + band - 1
            buckets[bi] = ContentTier(index=bi, name=f"T{bi + 1} (levels {lo}-{hi})",
                                      min_level=lo, max_level=hi)
        return buckets[bi]

    for code, lvl in items.items():
        _tier(lvl).items.append(code)
    for code, lvl in monsters.items():
        _tier(lvl).monsters.append(code)
    for code, lvl in resources.items():
        _tier(lvl).resources.append(code)
    for t in buckets.values():
        t.items.sort(); t.monsters.sort(); t.resources.sort()
    return [buckets[k] for k in sorted(buckets)]
