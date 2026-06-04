/-! # Skill — Item 4e/5a

Per-skill XP delta enumeration. Mirrors production's
`SKILL_NAMES` in `WorldState`:
mining, woodcutting, fishing, alchemy, weaponcrafting, gearcrafting,
jewelrycrafting, cooking, combat.

`combat` is the implicit aggregate from `.fight` (server's `fight_xp`
delta). Other 8 are direct production-side skills.
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
