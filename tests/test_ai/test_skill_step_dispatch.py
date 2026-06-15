"""Unit tests for the pure skill-step dispatch core (proved in
formal/Formal/Extracted/SkillStepDispatch.lean)."""

from artifactsmmo_cli.ai.tiers.skill_step_dispatch import (
    DispatchCandidate,
    DispatchDecision,
    FlagInputs,
    cannibalize_pure,
    combine_dispatch_pure,
    dispatch_candidate_flags,
    skill_step_dispatch_pure,
)


def _fi(code="x", recipe=("copper_bar",), level=1, obtainable=True,
        is_target=False, owned=False):
    return FlagInputs(code=code, recipe_mats=tuple(recipe), craft_level=level,
                      obtainable=obtainable, is_target=is_target, owned=owned)


def test_flags_unowned_target_is_exempt():
    """An unowned, in-level target is exempt: both reserved flags false even
    though its recipe input is reserved."""
    c = _fi(recipe=("copper_bar",), is_target=True, owned=False)
    assert dispatch_candidate_flags(
        c, 1, frozenset({"copper_bar"}), frozenset({"copper_bar"}), False) == (False, False)


def test_flags_owned_target_not_exempt():
    """An OWNED target is not exempt — its reserved mats block it (no over-craft)."""
    c = _fi(recipe=("copper_bar",), is_target=True, owned=True)
    assert dispatch_candidate_flags(
        c, 1, frozenset({"copper_bar"}), frozenset({"copper_bar"}), False) == (True, True)


def test_flags_nontarget_reserved():
    """A non-target throwaway is reservation-blocked by its mats."""
    c = _fi(recipe=("copper_bar",), is_target=False)
    assert dispatch_candidate_flags(
        c, 1, frozenset({"copper_bar"}), frozenset({"copper_bar"}), False) == (True, True)


def test_flags_cannibalize_frees_relaxed():
    """Under cannibalization the relaxed flag is false (full still reserved)."""
    c = _fi(recipe=("copper_bar",), is_target=False)
    assert dispatch_candidate_flags(
        c, 1, frozenset({"copper_bar"}), frozenset({"copper_bar"}), True) == (True, False)


def test_cannibalize_true_when_all_feasible_owned():
    cands = [_fi(code="a", owned=True), _fi(code="b", owned=True)]
    assert cannibalize_pure(1, cands) is True


def test_cannibalize_false_when_unowned_feasible_exists():
    cands = [_fi(code="a", owned=True), _fi(code="b", owned=False)]
    assert cannibalize_pure(1, cands) is False


def test_cannibalize_false_when_no_feasible():
    cands = [_fi(code="a", owned=True, level=10)]  # out of level -> not feasible
    assert cannibalize_pure(1, cands) is False


def _c(code, level=1, missing=0, obtainable=True, full=False, relaxed=False):
    """A same-skill (gearcrafting) candidate. `full`/`relaxed` = uses a material
    in the full / relaxed reserved set."""
    return DispatchCandidate(
        code=code, craft_skill="gearcrafting", craft_level=level,
        mats_missing=missing, obtainable=obtainable,
        uses_reserved_full=full, uses_reserved_relaxed=relaxed,
    )


def test_suppress_when_committed_same_skill_craftable_now():
    """Committed item is same-skill and craftable at current level -> SUPPRESS
    (its own root crafts it; no throwaway grind)."""
    d = skill_step_dispatch_pure("gearcrafting", 1, "gearcrafting", 1, [_c("copper_helmet")])
    assert d.kind == "suppress"
    assert d.code == ""


def test_no_suppress_when_committed_skill_gated():
    """Committed item gated ABOVE current level -> not suppressed; the grind is
    its legitimate bootstrap."""
    d = skill_step_dispatch_pure("gearcrafting", 1, "gearcrafting", 5, [_c("copper_helmet")])
    assert d.kind == "grind"
    assert d.code == "copper_helmet"


def test_grind_full_respects_reservation():
    """A full-reservation-respecting candidate is grinded; the reserved one is
    skipped even if it has fewer missing materials."""
    d = skill_step_dispatch_pure(
        "gearcrafting", 1, "", 0,
        [_c("copper_helmet", missing=0, full=True, relaxed=True),
         _c("wooden_shield", missing=3, full=False, relaxed=False)],
    )
    assert d.kind == "grind"
    assert d.code == "wooden_shield"


def test_relaxed_retry_when_full_starves():
    """Robby 2026-06-14 192617: the ONLY candidate uses a material reserved by a
    skill-gated objective (full) but freed under relaxation -> relaxed retry
    grinds it instead of falling to NO_GRIND."""
    d = skill_step_dispatch_pure(
        "gearcrafting", 1, "", 0,
        [_c("copper_helmet", full=True, relaxed=False)],
    )
    assert d.kind == "grind"
    assert d.code == "copper_helmet"


def test_full_preference_over_relaxed():
    """When BOTH a full-ok and a relaxed-only candidate exist, the full-ok one
    wins (we only relax when the full pass found nothing)."""
    d = skill_step_dispatch_pure(
        "gearcrafting", 1, "", 0,
        [_c("copper_helmet", missing=0, full=True, relaxed=False),
         _c("wooden_shield", missing=9, full=False, relaxed=False)],
    )
    assert d.kind == "grind"
    assert d.code == "wooden_shield"


def test_no_grind_when_no_feasible_candidate():
    """No same-skill in-level obtainable candidate -> NO_GRIND (caller returns
    None; arbiter advances)."""
    d = skill_step_dispatch_pure("gearcrafting", 1, "", 0,
                                 [_c("iron_helm", level=10)])  # out of level
    assert d.kind == "no_grind"
    assert d.code == ""


def test_no_grind_when_all_reserved_even_relaxed():
    """Every candidate uses a relaxed-reserved material -> nothing to grind."""
    d = skill_step_dispatch_pure("gearcrafting", 1, "", 0,
                                 [_c("copper_helmet", full=True, relaxed=True)])
    assert d.kind == "no_grind"


def test_grind_never_picks_unobtainable():
    """An un-obtainable candidate is never grinded (inherited selection role)."""
    d = skill_step_dispatch_pure("gearcrafting", 1, "", 0,
                                 [_c("wooden_staff", obtainable=False)])
    assert d.kind == "no_grind"


# --- combine_dispatch_pure (the extracted/proved core) -----------------------

def test_combine_suppress():
    assert combine_dispatch_pure("gearcrafting", 1, "gearcrafting", 1,
                                 "copper_helmet", "") == ("suppress", "")


def test_combine_prefers_full_pick():
    assert combine_dispatch_pure("gearcrafting", 1, "", 0,
                                 "wooden_shield", "copper_helmet") == ("grind", "wooden_shield")


def test_combine_falls_back_to_relaxed_pick():
    assert combine_dispatch_pure("gearcrafting", 1, "", 0,
                                 "", "copper_helmet") == ("grind", "copper_helmet")


def test_combine_no_grind_when_both_empty():
    assert combine_dispatch_pure("gearcrafting", 1, "", 0, "", "") == ("no_grind", "")


def test_combine_not_suppressed_when_committed_gated():
    """committed_level above current -> not suppressed; relaxed pick used."""
    assert combine_dispatch_pure("gearcrafting", 1, "gearcrafting", 5,
                                 "", "copper_helmet") == ("grind", "copper_helmet")
