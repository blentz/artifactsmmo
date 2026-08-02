"""Fifth ranking factor: damp gear chains outside this character's role.

`_scaled_weights` composes gain * falloff * synergy * achievability. This adds
role alignment as a fifth multiplier on the SAME (slot, code) key, so a
role-holder prefers the chain its own skills already serve.

DAMP, never boost: an aligned candidate keeps its weight exactly (Fraction(1)),
and a misaligned one is halved. That way a character with NO role — the
single-character path, or a roster larger than the catalog — sees every
multiplier at 1 and the weight is byte-identical to the four-factor value.

An unknown producing skill reads as ALIGNED, not MISALIGNED: no signal must
never become a penalty, per "use only API data or fail with an error" — we do
not know the chain is wrong, so we do not act as if it is.
"""

from fractions import Fraction

ALIGNED = Fraction(1)
"""No signal, or the candidate's skill is one this role owns."""

MISALIGNED = Fraction(1, 2)
"""The candidate's chain belongs to another role. Halved rather than zeroed:
a role-holder must still be ABLE to pursue an off-role chain when nothing else
is available, or a jeweler with no banked bars would have no plan at all."""


def role_alignment_pure(owned_skills: frozenset[str],
                        candidate_skill: str | None) -> Fraction:
    """Multiplier for one gear candidate given the skills this role owns."""
    if not owned_skills:
        return ALIGNED
    if candidate_skill is None:
        return ALIGNED
    return ALIGNED if candidate_skill in owned_skills else MISALIGNED
