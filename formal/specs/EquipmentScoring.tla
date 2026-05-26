----------------------------- MODULE EquipmentScoring -----------------------------
EXTENDS Integers, FiniteSets, TLC

\* Mirrors src/artifactsmmo_cli/ai/equipment/scoring.py
\*   weapon_score (line 9), armor_score (line 23), _candidates_for_slot (line 33),
\*   pick_loadout (line 55).
\*
\* FLOATS -> INTEGERS. pick_loadout consumes the scores only inside `max()` and a
\* strict `>` comparison, so only the ORDERING of scores matters. The real scores
\* are:
\*   weapon_score = Sum_e atk[e] * max(0, 1 - res[e]/100)   (clamped at 0)
\*   armor_score  = Sum_e mon_atk[e] * armor_res[e] / 100   (no clamp)
\* Integer surrogates multiply each by 100:
\*   WScore = Sum_e atk[e] * max(0, 100 - res[e])   (max(0,...) matches weapon_score's
\*                                                   max(0.0, 1 - res/100) clamp)
\*   AScore = Sum_e mon_atk[e] * armor_res[e]        (no clamp, like armor_score)
\* Multiplying every score by the SAME positive constant preserves both max() and
\* the strict `>`, so the surrogate has IDENTICAL ordering to the real score. The
\* spec verifies the properties pick_loadout relies on (score-optimal per slot,
\* no-downgrade, feasibility) through the surrogate.

Elements == {"fire", "earth"}
Max(a, b) == IF a > b THEN a ELSE b

\* mirrors ITEM_TYPE_TO_SLOTS from ai/actions/equip.py
SlotsOfType == [ weapon |-> {"weapon_slot"}, body |-> {"body_slot"}, helmet |-> {"helmet_slot"} ]
AllSlots == {"weapon_slot", "body_slot", "helmet_slot"}

Items == {"none", "wood_sword", "iron_sword", "leather", "plate", "cap"}
Type   == [ none |-> "none", wood_sword |-> "weapon", iron_sword |-> "weapon",
            leather |-> "body", plate |-> "body", cap |-> "helmet" ]
Level  == [ none |-> 0, wood_sword |-> 1, iron_sword |-> 5, leather |-> 1, plate |-> 8, cap |-> 1 ]
Attack == [ none |-> [fire |-> 0, earth |-> 0], wood_sword |-> [fire |-> 6, earth |-> 0],
            iron_sword |-> [fire |-> 10, earth |-> 0], leather |-> [fire |-> 0, earth |-> 0],
            plate |-> [fire |-> 0, earth |-> 0], cap |-> [fire |-> 0, earth |-> 0] ]
Resist == [ none |-> [fire |-> 0, earth |-> 0], wood_sword |-> [fire |-> 0, earth |-> 0],
            iron_sword |-> [fire |-> 0, earth |-> 0], leather |-> [fire |-> 5, earth |-> 2],
            plate |-> [fire |-> 20, earth |-> 10], cap |-> [fire |-> 3, earth |-> 0] ]

WScore(item, monRes) == LET S(e) == Attack[item][e] * Max(0, 100 - monRes[e])
                        IN S("fire") + S("earth")
AScore(item, monAtk) == LET S(e) == monAtk[e] * Resist[item][e]
                        IN S("fire") + S("earth")
ScoreOf(item, slot, monAtk, monRes) ==
  IF slot = "weapon_slot" THEN WScore(item, monRes) ELSE AScore(item, monAtk)

\* "none" is the empty-slot sentinel; Owned may include it, Feasible filters it out
Owned(st) == { c \in DOMAIN st.inv : st.inv[c] > 0 } \cup { st.equip[s] : s \in AllSlots }
Feasible(st, c) == c # "none" /\ st.level >= Level[c]
Candidates(st, slot) == { c \in Owned(st) : Feasible(st, c) /\ slot \in SlotsOfType[Type[c]] }

PickSlot(st, slot, monAtk, monRes) ==
  LET cands == Candidates(st, slot)
      cur   == st.equip[slot]
  IN IF cands = {} THEN cur
     ELSE LET best == CHOOSE b \in cands :
                        \A o \in cands : ScoreOf(b, slot, monAtk, monRes) >= ScoreOf(o, slot, monAtk, monRes)
          IN IF cur = best THEN cur
             ELSE IF cur = "none" THEN best
             ELSE IF ScoreOf(best, slot, monAtk, monRes) > ScoreOf(cur, slot, monAtk, monRes)
                  THEN best ELSE cur

\* Independent oracle — must NOT delegate to PickSlot. Recomputes the max score
\* directly so SlotCorrect's score-optimal check is non-circular. Do NOT DRY.
MaxScore(st, slot, monAtk, monRes) ==
  LET cands == Candidates(st, slot)
  IN CHOOSE v \in { ScoreOf(c, slot, monAtk, monRes) : c \in cands } :
       \A c \in cands : v >= ScoreOf(c, slot, monAtk, monRes)

SlotCorrect(st, slot, monAtk, monRes) ==
  LET r == PickSlot(st, slot, monAtk, monRes)
      cands == Candidates(st, slot)
      cur == st.equip[slot]
  IN IF cands = {}
     THEN r = cur
     ELSE /\ ScoreOf(r, slot, monAtk, monRes) = MaxScore(st, slot, monAtk, monRes)
          /\ ScoreOf(r, slot, monAtk, monRes) >= ScoreOf(cur, slot, monAtk, monRes)
          /\ (r # "none" => Feasible(st, r) /\ slot \in SlotsOfType[Type[r]])
          /\ (r # cur => r \in cands)
          /\ (ScoreOf(cur, slot, monAtk, monRes) = MaxScore(st, slot, monAtk, monRes) => r = cur)
          \* weapon_score's max(0.0, 1-res/100) is a hard floor: a weapon's score is
          \* never negative even against res > 100. Pins WScore's Max(0, 100-res)
          \* clamp (dropping it lets fire-res 110 drive iron/wood WScore negative).
          /\ (slot = "weapon_slot" =>
                \A c \in cands : ScoreOf(c, slot, monAtk, monRes) >= 0)

MonAtk == [fire |-> 20, earth |-> 10]
MonRes == [fire |-> 0, earth |-> 0]
\* fire-res 110 > 100 forces WScore's Max(0, 100 - res) clamp to bite (clamps to 0;
\* unclamped this drives weapon scores negative, violating SlotCorrect's >= 0 floor)
MonResHi == [fire |-> 110, earth |-> 0]
States == {
  \* upgrade: iron_sword beats equipped wood_sword
  [level |-> 5, inv |-> [iron_sword |-> 1], equip |-> [weapon_slot |-> "wood_sword", body_slot |-> "none", helmet_slot |-> "none"], monAtk |-> MonAtk, monRes |-> MonRes],
  \* level-gated: iron_sword (lvl5) excluded, keep wood_sword
  [level |-> 4, inv |-> [iron_sword |-> 1], equip |-> [weapon_slot |-> "wood_sword", body_slot |-> "none", helmet_slot |-> "none"], monAtk |-> MonAtk, monRes |-> MonRes],
  \* empty-slot fill: leather into body_slot
  [level |-> 3, inv |-> [leather |-> 1], equip |-> [weapon_slot |-> "wood_sword", body_slot |-> "none", helmet_slot |-> "none"], monAtk |-> MonAtk, monRes |-> MonRes],
  \* no-downgrade: plate stays, leather not chosen
  [level |-> 8, inv |-> [leather |-> 1], equip |-> [weapon_slot |-> "none", body_slot |-> "plate", helmet_slot |-> "none"], monAtk |-> MonAtk, monRes |-> MonRes],
  \* no candidates: every slot unchanged
  [level |-> 5, inv |-> [none |-> 0], equip |-> [weapon_slot |-> "none", body_slot |-> "none", helmet_slot |-> "none"], monAtk |-> MonAtk, monRes |-> MonRes],
  \* clamp: fire-res 110 clamps both weapons' WScore to 0 -> tie -> keep equipped iron;
  \* also exercises SlotCorrect's weapon-score >= 0 floor (fails if Max(0,..) dropped)
  [level |-> 5, inv |-> [wood_sword |-> 1], equip |-> [weapon_slot |-> "iron_sword", body_slot |-> "none", helmet_slot |-> "none"], monAtk |-> MonAtk, monRes |-> MonResHi]
}

Correct(st) == \A slot \in AllSlots : SlotCorrect(st, slot, st.monAtk, st.monRes)

VARIABLE todo
Init == todo = States
Next == /\ todo # {}
        /\ \E st \in todo :
              /\ Assert(Correct(st), <<"EquipmentScoring FAIL", st>>)
              /\ todo' = todo \ {st}
================================================================================
