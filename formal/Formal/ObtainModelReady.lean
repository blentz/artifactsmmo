-- formal/Formal/ObtainModelReady.lean
-- @concept: core, planner @property: validity, sufficiency, safety
/-
The route selection of the unified obtain model, mirroring
`src/artifactsmmo_cli/ai/obtain_model/ready_core.py::ready_routes` and
`src/artifactsmmo_cli/ai/obtain_model/policy.py::Policy`.

Phase 1 of docs/PLAN_decision_architecture_redesign.md. The obtain model
enumerates every route to an item with every gate evaluated, and a `Policy`
decides which gates count. `readyRoutes` keeps the routes that are ready
under the policy, in input (priority) order, and keeps only the FIRST ready
SELL route per item sold (buyers arrive highest price first).

Proved over ALL route lists and policies:
- soundness: every returned route is in the input and ready under the policy;
- order: the result is a sublist of the input (priority order preserved);
- completeness: every ready non-SELL route is returned;
- SELL: returned SELL routes have distinct `via`, every sold item with a ready
  buyer is covered, and the covering route is the first ready one;
- policy: the three switchable gates behave as named, and every other gate
  is always enforced.

`via` is abstracted to `Nat` (the Python side uses item/NPC code strings;
the differential harness interns them) — only equality of `via` is ever used.

Lean core only — no mathlib.
-/

namespace Formal.ObtainModelReady

/-- `ai/source_kind.py::SourceKind`. -/
inductive SrcKind
  | withdraw | recycle | craft | gather | buy | geFill | drop | sell
  deriving DecidableEq, Repr

/-- `ai/obtain_model/gate.py::GateKind`. -/
inductive GateKind
  | bankAccessible | craftSkill | gatherSkill | workshopKnown | spawnLive | winnable
  | vendorLocated | vendorPermanent | vendorTradeable | geLocated | licensed
  deriving DecidableEq, Repr

/-- One evaluated gate (`Gate.kind`, `Gate.satisfied`). -/
structure Gate where
  kind : GateKind
  sat : Bool
  deriving DecidableEq, Repr

/-- The fields of `Route` that selection reads. -/
structure Route where
  kind : SrcKind
  via : Nat
  primary : Bool
  gates : List Gate
  deriving DecidableEq, Repr

/-- `Policy`'s three switches. -/
structure Policy where
  allGather : Bool
  gatherSkill : Bool
  eventVendors : Bool
  deriving DecidableEq, Repr

/-- `Policy.LEGACY`: exactly what `obtain_sources` answered. -/
def legacy : Policy := ⟨false, false, false⟩

/-- `Policy.admits`: a non-primary GATHER route needs `allGather`. -/
def admits (p : Policy) (r : Route) : Bool :=
  r.kind != .gather || p.allGather || r.primary

/-- `Policy.enforces`. -/
def enforces (p : Policy) (r : Route) (g : Gate) : Bool :=
  match g.kind with
  | .gatherSkill => p.gatherSkill
  | .vendorPermanent => if r.kind = .buy then !p.eventVendors else true
  | .vendorTradeable => if r.kind = .buy then p.eventVendors else true
  | _ => true

/-- `Policy.ready`: admitted, and every enforced gate is satisfied. -/
def routeReady (p : Policy) (r : Route) : Bool :=
  admits p r && r.gates.all (fun g => !enforces p r g || g.sat)

/-- The selection loop, with `sold` the items already covered by a SELL route. -/
def readyAux (p : Policy) : List Nat → List Route → List Route
  | _, [] => []
  | sold, r :: rs =>
    if routeReady p r then
      if r.kind = .sell then
        if r.via ∈ sold then readyAux p sold rs
        else r :: readyAux p (r.via :: sold) rs
      else r :: readyAux p sold rs
    else readyAux p sold rs

/-- `ready_core.ready_routes`. -/
def readyRoutes (p : Policy) (rs : List Route) : List Route := readyAux p [] rs

/-! ### Soundness and order -/

theorem readyAux_sublist (p : Policy) (sold : List Nat) (rs : List Route) :
    (readyAux p sold rs).Sublist rs := by
  induction rs generalizing sold with
  | nil => simp [readyAux]
  | cons r rs ih =>
    simp only [readyAux]
    split
    · split
      · split
        · exact (ih sold).cons r
        · exact (ih (r.via :: sold)).cons_cons r
      · exact (ih sold).cons_cons r
    · exact (ih sold).cons r

/-- **ORDER.** The result is a sublist of the input: routes keep their
priority order and nothing is invented. -/
theorem readyRoutes_sublist (p : Policy) (rs : List Route) :
    (readyRoutes p rs).Sublist rs :=
  readyAux_sublist p [] rs

theorem readyAux_ready (p : Policy) (sold : List Nat) (rs : List Route) :
    ∀ r ∈ readyAux p sold rs, routeReady p r = true := by
  induction rs generalizing sold with
  | nil => simp [readyAux]
  | cons q rs ih =>
    intro r hr
    simp only [readyAux] at hr
    split at hr
    · rename_i hq
      split at hr
      · split at hr
        · exact ih sold r hr
        · rcases List.mem_cons.mp hr with h | h
          · exact h ▸ hq
          · exact ih _ r h
      · rcases List.mem_cons.mp hr with h | h
        · exact h ▸ hq
        · exact ih sold r h
    · exact ih sold r hr

/-- **SOUNDNESS.** Every returned route is an input route that is ready
under the policy. -/
theorem readyRoutes_sound (p : Policy) (rs : List Route) (r : Route)
    (h : r ∈ readyRoutes p rs) : r ∈ rs ∧ routeReady p r = true :=
  ⟨(readyRoutes_sublist p rs).subset h, readyAux_ready p [] rs r h⟩

/-! ### Completeness -/

theorem readyAux_complete_nonsell (p : Policy) (sold : List Nat) (rs : List Route)
    (r : Route) (hmem : r ∈ rs) (hready : routeReady p r = true)
    (hkind : r.kind ≠ .sell) : r ∈ readyAux p sold rs := by
  induction rs generalizing sold with
  | nil => simp at hmem
  | cons q rs ih =>
    simp only [readyAux]
    rcases List.mem_cons.mp hmem with h | h
    · subst h
      simp [hready, hkind]
    · split
      · split
        · split
          · exact ih sold h
          · exact List.mem_cons_of_mem _ (ih _ h)
        · exact List.mem_cons_of_mem _ (ih sold h)
      · exact ih sold h

/-- **COMPLETENESS.** Every ready non-SELL route is returned. -/
theorem readyRoutes_complete_nonsell (p : Policy) (rs : List Route) (r : Route)
    (hmem : r ∈ rs) (hready : routeReady p r = true) (hkind : r.kind ≠ .sell) :
    r ∈ readyRoutes p rs :=
  readyAux_complete_nonsell p [] rs r hmem hready hkind

/-! ### SELL: one route per item sold, and it is the first ready buyer -/

/-- The `via`s of the SELL routes in a list. -/
def sellVias (rs : List Route) : List Nat :=
  (rs.filter (fun r => r.kind = .sell)).map (·.via)

theorem readyAux_sell_fresh (p : Policy) (sold : List Nat) (rs : List Route) :
    ∀ v ∈ sellVias (readyAux p sold rs), v ∉ sold := by
  induction rs generalizing sold with
  | nil => simp [readyAux, sellVias]
  | cons q rs ih =>
    intro v hv
    simp only [readyAux] at hv
    split at hv
    · split at hv
      · rename_i hsell
        split at hv
        · exact ih sold v hv
        · rename_i hnot
          simp only [sellVias, List.filter_cons, hsell, decide_true, if_true,
            List.map_cons, List.mem_cons] at hv
          rcases hv with h | h
          · exact h ▸ hnot
          · have := ih (q.via :: sold) v h
            exact fun hs => this (List.mem_cons_of_mem _ hs)
      · rename_i hsell
        have : sellVias (q :: readyAux p sold rs) = sellVias (readyAux p sold rs) := by
          simp [sellVias, hsell]
        rw [this] at hv
        exact ih sold v hv
    · exact ih sold v hv

theorem readyAux_sell_nodup (p : Policy) (sold : List Nat) (rs : List Route) :
    (sellVias (readyAux p sold rs)).Nodup := by
  induction rs generalizing sold with
  | nil => simp [readyAux, sellVias]
  | cons q rs ih =>
    simp only [readyAux]
    split
    · split
      · rename_i hsell
        split
        · exact ih sold
        · have hfresh := readyAux_sell_fresh p (q.via :: sold) rs
          simp only [sellVias, List.filter_cons, hsell, decide_true, if_true, List.map_cons]
          refine List.nodup_cons.mpr ⟨?_, ih _⟩
          intro hin
          exact hfresh q.via hin (List.mem_cons_self)
      · rename_i hsell
        have : sellVias (q :: readyAux p sold rs) = sellVias (readyAux p sold rs) := by
          simp [sellVias, hsell]
        rw [this]
        exact ih sold
    · exact ih sold

/-- **SELL UNIQUENESS.** At most one SELL route per item sold is returned. -/
theorem readyRoutes_sell_nodup (p : Policy) (rs : List Route) :
    (sellVias (readyRoutes p rs)).Nodup :=
  readyAux_sell_nodup p [] rs

/-- A ready SELL route whose item is not yet covered, with no ready SELL route
for the same item before it, is kept. -/
theorem readyAux_sell_first (p : Policy) (sold : List Nat) (pre post : List Route)
    (r : Route) (hready : routeReady p r = true) (hkind : r.kind = .sell)
    (hsold : r.via ∉ sold)
    (hfirst : ∀ q ∈ pre, routeReady p q = true → q.kind = .sell → q.via ≠ r.via) :
    r ∈ readyAux p sold (pre ++ r :: post) := by
  induction pre generalizing sold with
  | nil => simp [readyAux, hready, hkind, hsold]
  | cons q pre ih =>
    have hrest : ∀ q' ∈ pre, routeReady p q' = true → q'.kind = .sell → q'.via ≠ r.via :=
      fun q' hq' => hfirst q' (List.mem_cons_of_mem _ hq')
    simp only [List.cons_append, readyAux]
    split
    · rename_i hq
      split
      · rename_i hqs
        split
        · exact ih sold hsold hrest
        · have hne : q.via ≠ r.via := hfirst q List.mem_cons_self hq hqs
          refine List.mem_cons_of_mem _ (ih (q.via :: sold) ?_ hrest)
          intro h
          rcases List.mem_cons.mp h with h | h
          · exact hne h.symm
          · exact hsold h
      · exact List.mem_cons_of_mem _ (ih sold hsold hrest)
    · exact ih sold hsold hrest

/-- **SELL FIRST BUYER.** The first ready SELL route for an item is the one
returned (with `readyRoutes_sell_nodup`, the only one). -/
theorem readyRoutes_sell_first (p : Policy) (pre post : List Route) (r : Route)
    (hready : routeReady p r = true) (hkind : r.kind = .sell)
    (hfirst : ∀ q ∈ pre, routeReady p q = true → q.kind = .sell → q.via ≠ r.via) :
    r ∈ readyRoutes p (pre ++ r :: post) :=
  readyAux_sell_first p [] pre post r hready hkind (by simp) hfirst

/-! ### Policy -/

/-- **POLICY: FIXED GATES.** Every gate other than the three switchable ones
is enforced under every policy, on every route. -/
theorem enforces_fixed (p : Policy) (r : Route) (g : Gate)
    (h1 : g.kind ≠ .gatherSkill) (h2 : g.kind ≠ .vendorPermanent)
    (h3 : g.kind ≠ .vendorTradeable) : enforces p r g = true := by
  unfold enforces
  split <;> simp_all

/-- **POLICY: GATHER SKILL.** The gathering-skill gate is enforced exactly when
the policy asks for it (D-A). -/
theorem enforces_gather_skill (p : Policy) (r : Route) (sat : Bool) :
    enforces p r ⟨.gatherSkill, sat⟩ = p.gatherSkill := rfl

/-- **POLICY: EVENT VENDORS.** On a BUY route, exactly one of permanence and
tradeability is enforced, chosen by `eventVendors` (D-F). -/
theorem enforces_vendor_buy (p : Policy) (r : Route) (s : Bool) (h : r.kind = .buy) :
    enforces p r ⟨.vendorPermanent, s⟩ = !p.eventVendors ∧
    enforces p r ⟨.vendorTradeable, s⟩ = p.eventVendors := by
  simp [enforces, h]

/-- **POLICY: GATHER ROUTES.** A GATHER route is admitted iff it is the primary
dropper or the policy offers every dropper (D-B). -/
theorem admits_gather (p : Policy) (r : Route) (h : r.kind = .gather) :
    admits p r = (p.allGather || r.primary) := by
  simp [admits, h]

/-! ### Non-vacuity witnesses -/

private def sellA : Route := ⟨.sell, 7, true, [⟨.vendorTradeable, false⟩]⟩
private def sellB : Route := ⟨.sell, 7, true, [⟨.vendorTradeable, true⟩]⟩
private def sellC : Route := ⟨.sell, 7, true, []⟩
private def gatherSecondary : Route := ⟨.gather, 1, false, []⟩
private def gatherSkilled : Route := ⟨.gather, 2, true, [⟨.gatherSkill, false⟩]⟩
private def eventBuy : Route :=
  ⟨.buy, 3, true, [⟨.vendorPermanent, false⟩, ⟨.vendorTradeable, true⟩]⟩

-- A closed first buyer yields to the next; a third buyer of the same item is dropped.
example : readyRoutes legacy [sellA, sellB, sellC] = [sellB] := by decide
-- LEGACY hides a non-primary gatherer and ignores the gather skill; the open policy flips both.
example : readyRoutes legacy [gatherSecondary, gatherSkilled] = [gatherSkilled] := by decide
example : readyRoutes ⟨true, true, false⟩ [gatherSecondary, gatherSkilled] = [gatherSecondary] := by
  decide
-- An open event vendor counts only when event vendors are enabled.
example : readyRoutes legacy [eventBuy] = [] := by decide
example : readyRoutes ⟨false, false, true⟩ [eventBuy] = [eventBuy] := by decide

end Formal.ObtainModelReady
