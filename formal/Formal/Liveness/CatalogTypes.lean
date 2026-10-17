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
Task 3's `canonicalPlan`), the production-projected player combat scalars, the
closed-form integer inputs `Formal.PredictWin.predictWin` reads (projection pin
only), and the fight-odds `Terms`/`Damage`/HP/restore the kernel decides the
row's verdict over (`WinnableGrounded.rowWinnable`). Emitted into
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
  pCritHit : Int
  pLifesteal : Int
  pAntipoison : Int
  -- The integer `predictWin` inputs + playerFirst.
  rawPlayer : Int
  monsterHp : Int
  rawMonster : Int
  mCrit : Int
  mAtkSum : Int
  mCritHit : Int
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
  -- New Season-8 abilities: default 0 so existing witness rows need no update.
  mSunShield : Int := 0
  mGreed : Int := 0
  mEnchantedMirror : Int := 0
  playerFirst : Bool
  -- The fight-odds inputs the kernel DECIDES (production `combat.fight_split`,
  -- spec 2026-10-15 fight-gates-odds §5): the `Formal.FightOutcome.Terms` ...
  tRawPlayer : Int
  tKillStep : Int
  tMonsterHp : Int
  tRecon : Int
  tDieStep : Int
  tPlayerFirst : Bool
  -- ... the `Formal.FightOdds.Damage` at the row's REAL crit chances ...
  dMonsterHp : Int
  dKillNormal : Int
  dKillCrit : Int
  dPCrit : Nat
  dDieNormal : Int
  dDieCrit : Int
  dMCrit : Nat
  dBurn : List Int
  dPHeal : Int
  dMHeal : Int
  -- ... and the fight's start HP, max HP and worn restore potion (HP, stock).
  fightHp : Int
  fightMaxHp : Int
  restore : Nat
  stock : Nat
  -- The crit-budget certificate `Formal.FightOdds.critBound` reads (the most
  -- monster crits the never-critting player survives); soundness does not
  -- depend on its value.
  critBudget : Nat
deriving Repr, DecidableEq

end Formal.Liveness
