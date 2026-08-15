-- @concept: crafting, gathering, planner @property: safety
import Formal.Extracted.SkillXpPositive
/-! # SkillXpPositive — the gather/craft skill-xp positivity gate

The server pays gathering and crafting skill xp through a `level_penalty` that
falls to ZERO once the content sits far enough below the character's SKILL level
(https://docs.artifactsmmo.com/concepts/skills). This is the GATHER/CRAFT twin of
`Formal.XpPositive`, which models the same shape for COMBAT.

The two bands are MEASURED SEPARATELY and come out EQUAL: both are
`diff >= 11 => 0`. This one is corroborated by `formal/diff/gather_xp_replay.py`
over 3231 live gather cycles — every bucket at gap ≤ 10 pays every time (gap 10:
159 pays / 0 zero) and every bucket at gap ≥ 11 pays zero times (gap 11: 0 / 310),
with no outlier anywhere; an independent 456-craft-cycle replay finds the same
split. Combat's is corroborated by `formal/diff/xp_formula_replay.py` over the
learning store's 10_883 ok-fights — diff 10: 372 pays / 0 zero, diff 11: 0 / 51.

Neither constant is derived from the other, and no shared mechanism is claimed:
two independent replays over disjoint evidence landed on the same number. This
paragraph previously asserted the two bands were deliberately DIFFERENT, citing
combat at `diff >= 10` with a "399/399" corroboration. That figure predates the
harness migration: it was produced when the replay recovered per-fight xp by
DIFFERENCING CONSECUTIVE STATE SNAPSHOTS — the same off-by-one attribution the
gather replay's own numbers were corrected for — and it observed ZERO zero-band
fights, so it never tested the boundary it was cited for.

WHY IT IS IN THE DECISION PATH: `skill_grind_selection_pure` filters grind rungs
on it and `best_gather_resource_drop` filters the gather fallback on it. Without
that filter the grind picked whichever rung's materials were already stockpiled —
systematically the greyest, cheapest tier — and ground it for zero xp
indefinitely (live Robby 2026-08-05: 288 `LevelSkill(woodcutting->20)` cycles,
`woodcutting` xp pinned at 4229 across 104 consecutive `ok` cycles).

Roles: characterization (`gate_iff` — the gate is exactly the integer band),
`gate_false_iff` (the zero-penalty band is precisely the complement for real
content), `gate_antitone` (raising the SKILL never turns a zero-xp target
positive — once grey, always grey, which is what makes the grind filter stable
under its own progress), and `gate_of_reachable` (content at or above the
character's skill always pays, so the filter can never empty a live candidate
set that contains an at-level rung).

Core-only (no Mathlib). -/

namespace Formal.SkillXpPositive

open Extracted.SkillXpPositive

/-- Characterization: the gate is the integer band, exactly. -/
theorem gate_iff (content skill : Int) :
    skill_xp_positive content skill = true ↔ 1 ≤ content ∧ skill < content + GREY_SKILL_GAP := by
  simp [skill_xp_positive]

/-- The `level_penalty = 0` band ("`GREY_SKILL_GAP`+ levels above") is EXACTLY
    the gate's complement for real content. -/
theorem gate_false_iff (content skill : Int) (hc : 1 ≤ content) :
    skill_xp_positive content skill = false ↔ content + GREY_SKILL_GAP ≤ skill := by
  rw [← Bool.not_eq_true, gate_iff]
  omega

/-- Antitone in SKILL level: leveling the skill UP never turns a zero-xp target
    positive (once out of band, always out of band). This is what makes the
    grind filter stable under its own progress — a rung the grind skipped as
    grey can never become a valid target later by grinding. -/
theorem gate_antitone (content skill skill' : Int) (h : skill ≤ skill') :
    skill_xp_positive content skill' = true → skill_xp_positive content skill = true := by
  simp only [gate_iff]
  omega

/-- Monotone in CONTENT level: at a fixed skill, harder content never pays less.
    Together with `gate_antitone` this pins the band's shape in both arguments. -/
theorem gate_monotone_content (content content' skill : Int)
    (hc : 1 ≤ content) (h : content ≤ content') :
    skill_xp_positive content skill = true → skill_xp_positive content' skill = true := by
  simp only [gate_iff]
  omega

/-- REACHABLE CONTENT ALWAYS PAYS: content at or above the character's skill
    level is never in the zero band. The grind's candidate set is filtered to
    `craft_level ≤ skill`, so this is the load-bearing liveness fact — an
    at-level rung (`craft_level = skill`) survives the xp filter, hence the
    filter cannot empty a candidate set that had a top-tier rung in it. -/
theorem gate_of_reachable (content skill : Int) (hc : 1 ≤ content) (h : skill ≤ content) :
    skill_xp_positive content skill = true := by
  rw [gate_iff]
  refine ⟨hc, ?_⟩
  unfold GREY_SKILL_GAP
  omega

end Formal.SkillXpPositive
