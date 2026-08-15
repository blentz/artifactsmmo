"""The GATHER/CRAFT skill-xp positivity gate (server level_penalty band).

The server pays gathering and crafting skill xp per a level_penalty that falls
to ZERO once the content sits far enough below the character's SKILL level
(documented: https://docs.artifactsmmo.com/concepts/skills — "resources/items
10+ levels below your skill level: 0"):

    XP = Round((XP_base + (content_level / skill_level) * k)
               * level_penalty * wisdom_bonus)

This mirrors `ai/xp_positive`'s COMBAT gate (`monster_catalog.xp_per_kill`,
`char_level - monster_level >= 11 => 0`) for the other two xp sources. Until
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

Hence the paying band is `gap <= 10`, i.e. `skill_level < content_level + 11`.

COMBAT'S BAND IS THE SAME NUMBER — measured separately, and equal. This
paragraph used to say the two were deliberately NOT shared, on the grounds that
combat's was `>= 10`, doc-cited AND "corroborated 399/399" in
`xp_formula_replay.py`, while this one was `>= 11`, and that nothing in the game
tied them together. The first half of that has been withdrawn. The 399/399
figure was produced when that replay recovered per-fight xp by DIFFERENCING
CONSECUTIVE STATE SNAPSHOTS — the same attribution bug that manufactured this
file's own retracted below-band payers — and it observed ZERO zero-band fights,
so it never tested the boundary at all. Re-run against the learning store, with
each fight read from its OWN `delta_xp`, combat's boundary is 11 too:

    diff = char_level - monster_level     pays / zero
      9                                   2101 /   0
     10                                    372 /   0
     11                                      0 /  51     <-- band starts here

10_750 paying fights, all at diff <= 10; 107 zero-xp fights, all at diff >= 11.
Those 10_857 are the CLASSIFIABLE subset of 10_883 ok-fights; the other 26 are
level-reset rows whose own `delta_xp` is negative, counted and excluded rather
than read as zeros.

The two constants are still NOT shared in code, and no common mechanism is
claimed — the game documents two separate curves, and this file's `>= 11` rests
on 3231 gathers while `monster_catalog`'s rests on 10_883 ok-fights. They are
equal because both were measured and both came out 11, not because either was
derived from the other.
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
