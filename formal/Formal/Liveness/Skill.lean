/-! # Skill — Item 4e/5a

Per-skill XP delta enumeration. The 8 trainable skills correspond to
production's `SKILL_NAMES` in `WorldState`, which is DERIVED from the API schema
enums `CraftSkill ∪ GatheringSkill` (mining, woodcutting, fishing, alchemy,
weaponcrafting, gearcrafting, jewelrycrafting, cooking — production sorts them
alphabetically; the constructor ORDER here is irrelevant, see below). `combat`
is the implicit aggregate from `.fight` (server's `fight_xp` delta), with no
`SKILL_NAMES` counterpart.

This inductive is an INERT reference enum: nothing in the formal layer pattern-
matches on it, indexes it, or proves over it (the objective differential keys
skills by name and reduces via the permutation-invariant `Objective.gapSum` /
`targetSum`). It exists only to document the vocabulary, so neither the
production derivation's order nor a future schema-added skill forces a change
here — the objective differential, not this enum, is the live correspondence.
-/

namespace Formal.Liveness

inductive Skill where
  | mining
  | woodcutting
  | fishing
  | alchemy
  | weaponcrafting
  | gearcrafting
  | jewelrycrafting
  | cooking
  | combat
  deriving DecidableEq, Repr

end Formal.Liveness
