"""The GATHER/CRAFT skill-xp positivity gate (server level_penalty band).

The server pays gathering and crafting skill xp per a level_penalty that falls
to ZERO once the content sits far enough below the character's SKILL level
(documented: https://docs.artifactsmmo.com/concepts/skills — "resources/items
10+ levels below your skill level: 0"):

    XP = Round((XP_base + (content_level / skill_level) * k)
               * level_penalty * wisdom_bonus)

This mirrors `ai/xp_positive`'s COMBAT gate (`monster_catalog.xp_per_kill`,
`char_level - monster_level >= 10 => 0`) for the other two xp sources. Until
now only combat modelled its band: `GatherAction`/`CraftAction` carried an
UPPER skill bound (`skills[skill] >= required`) and no lower one at all, so a
skill grind could pick content that pays nothing and spin on it forever.

THE BOUNDARY IS OBSERVED, NOT ASSUMED. The doc prose "10+ levels below" is
loose about whether a gap of exactly 10 pays. It does. Replaying every
`Gather` cycle across the 53 committed play-traces (`formal/diff/
gather_xp_replay.py`, 760 gathers) resolves it:

    gap = skill_level - resource_level     pays / zero
      8                                    182 /  7
      9                                    180 / 10
     10                                    148 / 11
     11                                      0 / 312     <-- band starts here
     16                                      0 / 140
     20                                      0 / 134

The gap-10 and gap-11 buckets contain the SAME resources (`copper_rocks` lvl 1,
`ash_tree` lvl 1) at different skill levels, and gap 11 also contains a
different resource at a different level (`iron_rocks` lvl 10), so the boundary
is a property of the GAP and not of any resource. The residual zeros below the
band are the one-cycle snapshot lag that also shows up mid-band, not a signal.

Hence the paying band is `gap <= 10`, i.e. `skill_level < content_level + 11` —
one wider than combat's. The two constants are deliberately NOT shared: combat's
`>= 10` is doc-cited AND corroborated 399/399 in `xp_formula_replay.py`, this
one is corroborated 760/760 here, and nothing in the game ties them together.
"""

GREY_SKILL_GAP = 11
"""Skill levels above the content at which gather/craft xp reaches zero.

`skill_level - content_level >= GREY_SKILL_GAP` pays NOTHING. Anchored by
`formal/diff/gather_xp_replay.py` (760 live gathers, no exception at the
boundary) and pinned by the SKILL_XP_POSITIVE mutation group."""


def skill_xp_positive(content_level: int, skill_level: int) -> bool:
    """True iff gathering/crafting `content_level` content at `skill_level`
    still pays skill xp.

    `content_level >= 1` mirrors the combat gate's real-content guard: level 0
    means "no level on file", and a zero-level content code must never be
    reported as a paying grind target.
    """
    return content_level >= 1 and skill_level < content_level + GREY_SKILL_GAP
