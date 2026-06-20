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

end Formal.Liveness
