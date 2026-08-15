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
`Gather` cycle across 155 committed play-traces (`formal/diff/
gather_xp_replay.py`, 3231 gathers, each attributed to its OWN action against
the pre/post state pair that action actually produced) resolves it:

    gap = skill_level - resource_level     pays / zero
      8                                    293 /   0
      9                                    192 /   0
     10                                    159 /   0
     11                                      0 / 310     <-- band starts here
     16                                      0 / 314
     20                                      0 / 135

Every in-band gap bucket (0-10) pays every single time; every out-of-band
bucket (>= 11) pays zero times, with no exception anywhere in 3231 gathers —
2210 paying at gap <= 10, 1021 zero at gap >= 11. `formal/diff/
craft_xp_replay.py`'s independent 450-craft-cycle replay finds the same clean
boundary for crafting: 214 paying, all at gap <= 10, and 236 zero, all at gap
>= 11. (An earlier version of this evidence reported a handful of below-band
payers and explained them as one-cycle attribution lag; that explanation was
itself wrong — a code-review round found the replay was pairing each action
against the FOLLOWING cycle's result instead of its own, which manufactured
those apparent payers out of a neighbouring cycle's real yield. Corrected,
there is nothing left to explain: the boundary is exact.)

Hence the paying band is `gap <= 10`, i.e. `skill_level < content_level + 11` —
one wider than combat's. The two constants are deliberately NOT shared: combat's
`>= 10` is doc-cited AND corroborated 399/399 in `xp_formula_replay.py`, this
one is corroborated 3231/3231 here, and nothing in the game ties them together.
"""

GREY_SKILL_GAP = 11
"""Skill levels above the content at which gather/craft xp reaches zero.

`skill_level - content_level >= GREY_SKILL_GAP` pays NOTHING. Anchored by
`formal/diff/gather_xp_replay.py` (3231 live gathers, no exception at the
boundary) and pinned by the SKILL_XP_POSITIVE mutation group."""


def skill_xp_positive(content_level: int, skill_level: int) -> bool:
    """True iff gathering/crafting `content_level` content at `skill_level`
    still pays skill xp.

    `content_level >= 1` mirrors the combat gate's real-content guard: level 0
    means "no level on file", and a zero-level content code must never be
    reported as a paying grind target.
    """
    return content_level >= 1 and skill_level < content_level + GREY_SKILL_GAP
