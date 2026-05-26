----------------------------- MODULE LoadoutProjection -----------------------------
EXTENDS Integers, FiniteSets, TLC

\* Mirrors src/artifactsmmo_cli/ai/equipment/projection.py:30 project_loadout_stats.
\* The server reports only TOTAL stats (base + equipped gear), so a loadout's
\* projected stats = current totals + Σ over CHANGED slots of (new - old). For
\* each slot, if new_code == old_code the slot is skipped (zero contribution);
\* otherwise the picked item's contribution is added and the equipped item's
\* contribution subtracted, per element (attack/resistance) and per scalar
\* (dmg, dmg_elements, critical_strike, initiative, hp_bonus).
\*
\* This spec covers the attack/resistance ELEMENT maps + max_hp + initiative.
\* dmg, dmg_elements, and critical_strike follow the IDENTICAL additive
\* new-minus-old, skip-when-equal pattern (projection.py:58-59, 52-54) and are
\* verified by that structural identity; modeling them adds no new control flow.

Slots == {"weapon_slot", "body_slot"}
Field == {"fire", "earth"}   \* element keys for attack/resistance

Items == {"none", "w1", "w2", "b1", "b2"}
IAtk  == [ none |-> [fire |-> 0, earth |-> 0], w1 |-> [fire |-> 5, earth |-> 0],
           w2 |-> [fire |-> 9, earth |-> 1], b1 |-> [fire |-> 0, earth |-> 0], b2 |-> [fire |-> 0, earth |-> 0] ]
IResist == [ none |-> [fire |-> 0, earth |-> 0], w1 |-> [fire |-> 0, earth |-> 0],
             w2 |-> [fire |-> 0, earth |-> 0], b1 |-> [fire |-> 4, earth |-> 2], b2 |-> [fire |-> 10, earth |-> 6] ]
IHp   == [ none |-> 0, w1 |-> 0, w2 |-> 0, b1 |-> 12, b2 |-> 30 ]
IInit == [ none |-> 0, w1 |-> 2, w2 |-> 5, b1 |-> 0, b2 |-> 0 ]

\* algorithm model: project = current + sum over CHANGED slots of (new - old).
ChangedW(st, lo) == lo["weapon_slot"] # st.equip["weapon_slot"]
ChangedB(st, lo) == lo["body_slot"]   # st.equip["body_slot"]
ProjAtk(st, lo, e) == st.atk[e]
  + (IF ChangedW(st, lo) THEN IAtk[lo["weapon_slot"]][e] - IAtk[st.equip["weapon_slot"]][e] ELSE 0)
  + (IF ChangedB(st, lo) THEN IAtk[lo["body_slot"]][e]   - IAtk[st.equip["body_slot"]][e]   ELSE 0)
ProjRes(st, lo, e) == st.res[e]
  + (IF ChangedW(st, lo) THEN IResist[lo["weapon_slot"]][e] - IResist[st.equip["weapon_slot"]][e] ELSE 0)
  + (IF ChangedB(st, lo) THEN IResist[lo["body_slot"]][e]   - IResist[st.equip["body_slot"]][e]   ELSE 0)
ProjHp(st, lo) == st.maxhp
  + (IF ChangedW(st, lo) THEN IHp[lo["weapon_slot"]] - IHp[st.equip["weapon_slot"]] ELSE 0)
  + (IF ChangedB(st, lo) THEN IHp[lo["body_slot"]]   - IHp[st.equip["body_slot"]]   ELSE 0)
ProjInit(st, lo) == st.init
  + (IF ChangedW(st, lo) THEN IInit[lo["weapon_slot"]] - IInit[st.equip["weapon_slot"]] ELSE 0)
  + (IF ChangedB(st, lo) THEN IInit[lo["body_slot"]]   - IInit[st.equip["body_slot"]]   ELSE 0)

\* INDEPENDENT oracle: unconditional all-slot (new - old). new==old contributes 0,
\* so summing over all slots equals summing over changed slots — proves the
\* ChangedSlots guard is sound. No guard here (structurally distinct from Proj*).
OAtk(st, lo, e) == st.atk[e] + (IAtk[lo["weapon_slot"]][e] - IAtk[st.equip["weapon_slot"]][e])
                             + (IAtk[lo["body_slot"]][e]   - IAtk[st.equip["body_slot"]][e])
ORes(st, lo, e) == st.res[e] + (IResist[lo["weapon_slot"]][e] - IResist[st.equip["weapon_slot"]][e])
                             + (IResist[lo["body_slot"]][e]   - IResist[st.equip["body_slot"]][e])
OHp(st, lo)  == st.maxhp + (IHp[lo["weapon_slot"]] - IHp[st.equip["weapon_slot"]])
                         + (IHp[lo["body_slot"]]   - IHp[st.equip["body_slot"]])
OInit(st, lo) == st.init + (IInit[lo["weapon_slot"]] - IInit[st.equip["weapon_slot"]])
                         + (IInit[lo["body_slot"]]   - IInit[st.equip["body_slot"]])

Correct(c) ==
  LET st == c.st IN
  LET lo == c.lo IN
  /\ \A e \in Field : ProjAtk(st, lo, e) = OAtk(st, lo, e)
  /\ \A e \in Field : ProjRes(st, lo, e) = ORes(st, lo, e)
  /\ ProjHp(st, lo) = OHp(st, lo)
  /\ ProjInit(st, lo) = OInit(st, lo)
  /\ (lo = st.equip =>
        /\ \A e \in Field : ProjAtk(st, lo, e) = st.atk[e]
        /\ ProjHp(st, lo) = st.maxhp)

BaseEquip == [weapon_slot |-> "w1", body_slot |-> "b1"]
BaseState == [atk |-> [fire |-> 5, earth |-> 0], res |-> [fire |-> 4, earth |-> 2],
              maxhp |-> 112, init |-> 2, equip |-> BaseEquip]
EmptyState == [atk |-> [fire |-> 0, earth |-> 0], res |-> [fire |-> 0, earth |-> 0],
               maxhp |-> 100, init |-> 0, equip |-> [weapon_slot |-> "none", body_slot |-> "none"]]
Loadouts == { [weapon_slot |-> w, body_slot |-> b] : w \in {"none","w1","w2"}, b \in {"none","b1","b2"} }
Cases == { [st |-> BaseState, lo |-> lo] : lo \in Loadouts }
           \cup { [st |-> EmptyState, lo |-> lo] : lo \in Loadouts }

VARIABLE todo
Init == todo = Cases
Next == /\ todo # {}
        /\ \E c \in todo :
              /\ Assert(Correct(c), <<"LoadoutProjection FAIL", c>>)
              /\ todo' = todo \ {c}
================================================================================
