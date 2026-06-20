namespace Formal.Liveness

structure CatalogMonster where
  code : String
  level : Int
  hp : Int
  attackFire : Int
  attackEarth : Int
  attackWater : Int
  attackAir : Int
  resFire : Int
  resEarth : Int
  resWater : Int
  resAir : Int
  crit : Int
deriving Repr, DecidableEq

structure BaseStatsRow where
  level : Int
  maxHp : Int
  attackFire : Int
  attackEarth : Int
  attackWater : Int
  attackAir : Int
  resFire : Int
  resEarth : Int
  resWater : Int
  resAir : Int
  crit : Int
  initiative : Int
deriving Repr, DecidableEq

structure CatalogItem where
  code : String
  level : Int
  slotType : String
  attackFire : Int
  attackEarth : Int
  attackWater : Int
  attackAir : Int
  hpBonus : Int
  resFire : Int
  resEarth : Int
  resWater : Int
  resAir : Int
  crit : Int
deriving Repr, DecidableEq

/-- One band level's verified winnability WITNESS for the kernel
`winnableAcrossBand_grounded` proof. Carries the winning monster (code + level),
the `pick_loadout` loadout codes (every item `level ≤ level`, obtainability per
Task 3's `canonicalPlan`), the production-projected player combat scalars, and
the exact integer inputs `Formal.PredictWin.predictWin` reads. Emitted into
`GameDataFixture.lean` by `formal/sim/generate_lean_fixture.py`; the projection's
fidelity to production is differential-pinned by
`formal/diff/test_winnable_witness_diff.py`. -/
structure WitnessRow where
  level : Int
  monsterCode : String
  monsterLevel : Int
  loadoutCodes : List String
  -- Player-projection scalars (pinned to `project_loadout_stats`).
  pCrit : Int
  pMaxHp : Int
  pInitiative : Int
  pAtkSum : Int
  pLifesteal : Int
  pAntipoison : Int
  -- The integer `predictWin` inputs + playerFirst.
  rawPlayer : Int
  monsterHp : Int
  rawMonster : Int
  mCrit : Int
  mAtkSum : Int
  mLifesteal : Int
  mPoison : Int
  mBarrier : Int
  mBurn : Int
  mHealing : Int
  mReconstitution : Int
  mVoidDrain : Int
  mBerserk : Int
  mFrenzy : Int
  mBubble : Int
  playerFirst : Bool
deriving Repr, DecidableEq

end Formal.Liveness
