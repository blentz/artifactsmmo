-- @concept: maps @property: safety, dominance, totality, monotonicity
/-
Formal model of the pure Manhattan-nearest tile selector extracted from
`src/artifactsmmo_cli/ai/nearest_tile.py` (`nearest_tile`).

THE HEADLINE IS THE COUPLING, NOT BARE ARGMIN. `nearest_tile` is the SINGLE
spatial-routing primitive that every gather/fight/move action resolves its
destination against, and it is the trusted `distance` input feeding
`Formal/GatherSelection.lean`'s candidate metric. Two facts make this module load-
bearing beyond "argmin returns a minimum":

  1. DETERMINISM (closes a real divergence bug). The live `MoveTo` previously
     PLANNED its move with `min(self.destinations)` (raw tuple lex order, ignoring
     distance) but EXECUTED it with a Manhattan-`min` (no tie-break). On a distance
     tie those two picks could disagree, so the planned state and the executed state
     diverged. Re-pointing BOTH `apply` and `execute` at this one selector — which
     breaks distance ties lexicographically by `(x, y)` for a UNIQUE winner — makes
     plan-time and execute-time agree. `nearestTile_deterministic_lexmin` is the
     theorem that closes it.

  2. COST-MONOTONE. On the live movement model the action cost is
     `staticGatherCost = 6 + manhattan` (a step's fixed overhead plus the tile
     distance), monotone in distance, so the Manhattan-nearest tile IS the
     least-cost destination — which is exactly why feeding its distance into the
     gather metric is sound. `cost_monotone_in_distance` pins this.

HONEST LIMIT (single-layer, no-obstacle, single-hop). On the live model a move is
ONE hop on ONE map layer with no obstacles, so least-cost = Manhattan-nearest. This
module proves THAT model. It is NOT a cross-layer A* optimality proof; multi-layer
traversal / obstacle routing is out of scope (and `utils/pathfinding.py` is CLI-only,
deliberately NOT modeled here).

The diff oracle feeds tiles as `[origin_x, origin_y, [(x, y), ...]]` and compares the
selected tile against `nearest_tile(...)` exactly. Tiles are `Int × Int` (coordinates
can be negative — the live `WorldState` allows negative map coords); the lex key is
`(manhattan, x, y)` with `manhattan : Nat` (a non-negative distance) and the `x`, `y`
tie-break over `Int`.

Lean core only — no mathlib. The lex order is a hand-rolled strict order with a
`Decidable` instance; argmin is a `List.foldl`; `Nat`/`Int` trichotomy via core
lemmas — the same core-only convention as `Formal/GatherSelection.lean`.
-/

namespace Formal.NearestTile

/-- A map tile coordinate (the live `WorldState` permits negative coords). -/
abbrev Tile := Int × Int

/-- Manhattan distance from `(ox, oy)` to a tile, as a `Nat` (mirrors the Python
`abs(t[0]-origin_x) + abs(t[1]-origin_y)`; `Int.natAbs` is the exact `abs`). -/
def manhattan (ox oy : Int) (t : Tile) : Nat :=
  (t.1 - ox).natAbs + (t.2 - oy).natAbs

/-- Strict lexicographic order on the key `(manhattan, x, y)` — the exact tuple the
Python `min(tiles, key=lambda t: (..., t[0], t[1]))` minimizes over. `a` strictly
precedes `b` iff it is strictly nearer, or ties on distance and has a strictly smaller
`x`, or ties on both and has a strictly smaller `y`. -/
def keyLt (ox oy : Int) (a b : Tile) : Prop :=
  manhattan ox oy a < manhattan ox oy b
  ∨ (manhattan ox oy a = manhattan ox oy b ∧ a.1 < b.1)
  ∨ (manhattan ox oy a = manhattan ox oy b ∧ a.1 = b.1 ∧ a.2 < b.2)

instance (ox oy : Int) (a b : Tile) : Decidable (keyLt ox oy a b) := by
  unfold keyLt; infer_instance

/-- The two tiles tie on the FULL key `(manhattan, x, y)`. -/
def keyEq (ox oy : Int) (a b : Tile) : Prop :=
  manhattan ox oy a = manhattan ox oy b ∧ a.1 = b.1 ∧ a.2 = b.2

/-- The argmin step: keep `x` over `best` iff `x` has a strictly smaller key. -/
def minStep (ox oy : Int) (best x : Tile) : Tile := if keyLt ox oy x best then x else best

/-- Lex-argmin over the list: fold the tail from the head, keeping the strictly-smaller
key at each step (first-wins on ties, mirroring Python `min`'s stability). `none` on the
empty list (mirrors `if not tiles: return None`). -/
def nearestTile (ox oy : Int) : List Tile → Option Tile
  | [] => none
  | c :: cs => some (cs.foldl (minStep ox oy) c)

/-- The static per-step move/gather cost on the live single-hop model: a fixed `6`
overhead plus the Manhattan distance. Monotone in distance, so least-cost ⇔
Manhattan-nearest (the coupling that justifies feeding this distance into the gather
metric). -/
def staticGatherCost (ox oy : Int) (t : Tile) : Nat := 6 + manhattan ox oy t

/-! ### Key lex-order facts (over `Nat` distance + `Int` x/y). -/

/-- `keyLt` is irreflexive: nothing strictly precedes itself. -/
theorem keyLt_irrefl (ox oy : Int) (a : Tile) : ¬ keyLt ox oy a a := by
  unfold keyLt
  rintro (h | ⟨_, h⟩ | ⟨_, _, h⟩)
  · exact Nat.lt_irrefl _ h
  · exact Int.lt_irrefl _ h
  · exact Int.lt_irrefl _ h

/-- `keyLt` transitivity. -/
theorem keyLt_trans {ox oy : Int} {a b c : Tile}
    (hab : keyLt ox oy a b) (hbc : keyLt ox oy b c) : keyLt ox oy a c := by
  unfold keyLt at *
  rcases hab with (h1 | ⟨e1, h1⟩ | ⟨e1, d1, h1⟩)
  · rcases hbc with (h2 | ⟨e2, h2⟩ | ⟨e2, h2⟩)
    · exact Or.inl (Nat.lt_trans h1 h2)
    · exact Or.inl (e2 ▸ h1)
    · exact Or.inl (e2 ▸ h1)
  · rcases hbc with (h2 | ⟨e2, h2⟩ | ⟨e2, d2, h2⟩)
    · exact Or.inl (e1 ▸ h2)
    · exact Or.inr (Or.inl ⟨e1.trans e2, Int.lt_trans h1 h2⟩)
    · exact Or.inr (Or.inl ⟨e1.trans e2, d2 ▸ h1⟩)
  · rcases hbc with (h2 | ⟨e2, h2⟩ | ⟨e2, d2, h2⟩)
    · exact Or.inl (e1 ▸ h2)
    · exact Or.inr (Or.inl ⟨e1.trans e2, d1 ▸ h2⟩)
    · exact Or.inr (Or.inr ⟨e1.trans e2, d1.trans d2, Int.lt_trans h1 h2⟩)

/-- `keyLt` is asymmetric: `a < b` excludes `b < a`. -/
theorem keyLt_asymm {ox oy : Int} {a b : Tile} (h : keyLt ox oy a b) : ¬ keyLt ox oy b a :=
  fun h2 => keyLt_irrefl ox oy a (keyLt_trans h h2)

/-- TOTALITY of the key order (trichotomy): for any two tiles, exactly one of
`keyLt a b`, full key tie, or `keyLt b a` holds. -/
theorem keyLt_total (ox oy : Int) (a b : Tile) :
    keyLt ox oy a b ∨ keyEq ox oy a b ∨ keyLt ox oy b a := by
  unfold keyLt keyEq
  rcases Nat.lt_trichotomy (manhattan ox oy a) (manhattan ox oy b) with he | he | he
  · exact Or.inl (Or.inl he)
  · rcases Int.lt_trichotomy a.1 b.1 with hx | hx | hx
    · exact Or.inl (Or.inr (Or.inl ⟨he, hx⟩))
    · rcases Int.lt_trichotomy a.2 b.2 with hy | hy | hy
      · exact Or.inl (Or.inr (Or.inr ⟨he, hx, hy⟩))
      · exact Or.inr (Or.inl ⟨he, hx, hy⟩)
      · exact Or.inr (Or.inr (Or.inr (Or.inr ⟨he.symm, hx.symm, hy⟩)))
    · exact Or.inr (Or.inr (Or.inr (Or.inl ⟨he.symm, hx⟩)))
  · exact Or.inr (Or.inr (Or.inl he))

/-- A full key tie composes on the left of `keyLt`. -/
theorem keyEq_keyLt {ox oy : Int} {a b c : Tile}
    (he : keyEq ox oy a b) (h : keyLt ox oy b c) : keyLt ox oy a c := by
  obtain ⟨e, dx, dy⟩ := he
  unfold keyLt at h ⊢
  rcases h with (h | ⟨e', h⟩ | ⟨e', d', h⟩)
  · exact Or.inl (e ▸ h)
  · exact Or.inr (Or.inl ⟨e ▸ e', dx ▸ h⟩)
  · exact Or.inr (Or.inr ⟨e ▸ e', dx ▸ d', dy ▸ h⟩)

/-- A full key tie composes on the right of `keyLt`. -/
theorem keyLt_keyEq {ox oy : Int} {a b c : Tile}
    (h : keyLt ox oy a b) (he : keyEq ox oy b c) : keyLt ox oy a c := by
  obtain ⟨e, dx, dy⟩ := he
  unfold keyLt at h ⊢
  rcases h with (h | ⟨e', h⟩ | ⟨e', d', h⟩)
  · exact Or.inl (e ▸ h)
  · exact Or.inr (Or.inl ⟨e' ▸ e, dx ▸ h⟩)
  · exact Or.inr (Or.inr ⟨e' ▸ e, dx ▸ d', dy ▸ h⟩)

/-- A full key tie is incompatible with `keyLt` (it has no strict component). -/
theorem keyEq_not_keyLt {ox oy : Int} {a b : Tile} (he : keyEq ox oy a b) :
    ¬ keyLt ox oy a b := by
  obtain ⟨e, dx, dy⟩ := he
  unfold keyLt
  rintro (h | ⟨_, h⟩ | ⟨_, _, h⟩)
  · exact (Nat.ne_of_lt h) e
  · exact (Int.ne_of_lt h) dx
  · exact (Int.ne_of_lt h) dy

/-- ORDER-CONNECTION: if `y` does not beat `m` and `m` does not beat `v`, then `y`
does not beat `v` (the key order is total, so `v ≤ m ≤ y ⇒ v ≤ y`). -/
theorem keyLt_not_of_chain {ox oy : Int} {m v y : Tile}
    (hy_not_m : ¬ keyLt ox oy y m) (hm_not_v : ¬ keyLt ox oy m v) : ¬ keyLt ox oy y v := by
  have hv_le_m : keyLt ox oy v m ∨ keyEq ox oy v m := by
    rcases keyLt_total ox oy v m with h | h | h
    · exact Or.inl h
    · exact Or.inr h
    · exact absurd h hm_not_v
  have hm_le_y : keyLt ox oy m y ∨ keyEq ox oy m y := by
    rcases keyLt_total ox oy m y with h | h | h
    · exact Or.inl h
    · exact Or.inr h
    · exact absurd h hy_not_m
  intro hyv
  have hv_le_y : keyLt ox oy v y ∨ keyEq ox oy v y := by
    rcases hv_le_m with hvm | hvm
    · rcases hm_le_y with hmy | hmy
      · exact Or.inl (keyLt_trans hvm hmy)
      · exact Or.inl (keyLt_keyEq hvm hmy)
    · rcases hm_le_y with hmy | hmy
      · exact Or.inl (keyEq_keyLt hvm hmy)
      · exact Or.inr ⟨hvm.1.trans hmy.1, hvm.2.1.trans hmy.2.1, hvm.2.2.trans hmy.2.2⟩
  rcases hv_le_y with hvy | hvy
  · exact keyLt_asymm hvy hyv
  · exact keyEq_not_keyLt (⟨hvy.1.symm, hvy.2.1.symm, hvy.2.2.symm⟩ : keyEq ox oy y v) hyv

/-! ### `minStep` characterization + `foldl` argmin invariant. -/

/-- The step result is one of its two arguments. -/
theorem minStep_eq (ox oy : Int) (best x : Tile) :
    minStep ox oy best x = best ∨ minStep ox oy best x = x := by
  unfold minStep; by_cases hf : keyLt ox oy x best
  · exact Or.inr (if_pos hf)
  · exact Or.inl (if_neg hf)

/-- The step result is never strictly beaten by the running best. -/
theorem minStep_not_lt_best (ox oy : Int) (best x : Tile) :
    ¬ keyLt ox oy best (minStep ox oy best x) := by
  unfold minStep; by_cases hf : keyLt ox oy x best
  · rw [if_pos hf]; exact keyLt_asymm hf
  · rw [if_neg hf]; exact keyLt_irrefl ox oy best

/-- The step result is never strictly beaten by the incoming element. -/
theorem minStep_not_lt_elem (ox oy : Int) (best x : Tile) :
    ¬ keyLt ox oy x (minStep ox oy best x) := by
  unfold minStep; by_cases hf : keyLt ox oy x best
  · rw [if_pos hf]; exact keyLt_irrefl ox oy x
  · rw [if_neg hf]; exact hf

/-- The fold accumulator is always either the initial seed or one of the folded
elements. -/
theorem foldl_minStep_mem (ox oy : Int) :
    ∀ (cs : List Tile) (init : Tile),
      cs.foldl (minStep ox oy) init = init ∨ cs.foldl (minStep ox oy) init ∈ cs := by
  intro cs
  induction cs with
  | nil => intro init; exact Or.inl rfl
  | cons d ds ih =>
    intro init
    rw [List.foldl_cons]
    rcases ih (minStep ox oy init d) with h | h
    · rcases minStep_eq ox oy init d with hs | hs
      · exact Or.inl (h.trans hs)
      · refine Or.inr ?_
        rw [h.trans hs]
        exact List.mem_cons_self
    · exact Or.inr (List.mem_cons_of_mem d h)

/-- HEADLINE INVARIANT: the fold result's key is `≤` both the seed and every folded
element (no tile strictly beats it). -/
theorem foldl_minStep_dominates (ox oy : Int) :
    ∀ (cs : List Tile) (init : Tile),
      (¬ keyLt ox oy init (cs.foldl (minStep ox oy) init)) ∧
      (∀ y ∈ cs, ¬ keyLt ox oy y (cs.foldl (minStep ox oy) init)) := by
  intro cs
  induction cs with
  | nil => intro init; exact ⟨keyLt_irrefl ox oy init, by intro y hy; cases hy⟩
  | cons d ds ih =>
    intro init
    rw [List.foldl_cons]
    obtain ⟨ihinit, ihmem⟩ := ih (minStep ox oy init d)
    have seed_not_beats : ¬ keyLt ox oy init (ds.foldl (minStep ox oy) (minStep ox oy init d)) :=
      keyLt_not_of_chain (minStep_not_lt_best ox oy init d) ihinit
    refine ⟨seed_not_beats, ?_⟩
    intro y hy
    rcases List.mem_cons.mp hy with rfl | hmem
    · exact keyLt_not_of_chain (minStep_not_lt_elem ox oy init y) ihinit
    · exact ihmem y hmem

/-! ### Role theorems. -/

/-- TOTALITY: `nearestTile = none` IFF the tile list is empty. A non-empty tile set
always yields a winner (movement never deadlocks resolving a destination). -/
theorem nearestTile_nil (ox oy : Int) (cs : List Tile) :
    nearestTile ox oy cs = none ↔ cs = [] := by
  cases cs with
  | nil => simp [nearestTile]
  | cons c cs => simp [nearestTile]

/-- TOTALITY (positive form): a non-empty tile list always selects SOME tile. -/
theorem nearestTile_total (ox oy : Int) {cs : List Tile} (h : cs ≠ []) :
    (nearestTile ox oy cs).isSome := by
  cases cs with
  | nil => exact absurd rfl h
  | cons c cs => simp [nearestTile]

/-- SAFETY: the selected tile is a REAL element of the list (never invented). -/
theorem nearestTile_mem {ox oy : Int} {cs : List Tile} {t : Tile}
    (h : nearestTile ox oy cs = some t) : t ∈ cs := by
  cases cs with
  | nil => simp [nearestTile] at h
  | cons d ds =>
    simp only [nearestTile, Option.some.injEq] at h
    subst h
    rcases foldl_minStep_mem ox oy ds d with hm | hm
    · rw [hm]; exact List.mem_cons_self
    · exact List.mem_cons_of_mem d hm

/-- DOMINANCE: no tile strictly beats the winner on the lex key (the winner is the
lex-minimum, so nothing is strictly nearer-or-tie-smaller). -/
theorem nearestTile_lexmin {ox oy : Int} {cs : List Tile} {t : Tile}
    (h : nearestTile ox oy cs = some t) : ∀ u ∈ cs, ¬ keyLt ox oy u t := by
  cases cs with
  | nil => simp [nearestTile] at h
  | cons d ds =>
    simp only [nearestTile, Option.some.injEq] at h
    subst h
    obtain ⟨hseed, hmem⟩ := foldl_minStep_dominates ox oy ds d
    intro u hu
    rcases List.mem_cons.mp hu with rfl | humem
    · exact hseed
    · exact hmem u humem

/-- DOMINANCE (distance form): the winner's Manhattan distance is `≤` every tile's.
Derived from the lex-min dominance — no tile is strictly nearer. -/
theorem nearestTile_min {ox oy : Int} {cs : List Tile} {t : Tile}
    (h : nearestTile ox oy cs = some t) :
    ∀ u ∈ cs, manhattan ox oy t ≤ manhattan ox oy u := by
  intro u hu
  have hnot : ¬ keyLt ox oy u t := nearestTile_lexmin h u hu
  rcases Nat.lt_or_ge (manhattan ox oy u) (manhattan ox oy t) with hlt | hge
  · exact absurd (Or.inl hlt) hnot
  · exact hge

/-- DETERMINISM / lex-min on ties (CLOSES the apply/execute divergence): on a distance
tie the winner is the lexicographically smallest `(x, y)`. Concretely, any OTHER tile
`u` in the list with the SAME distance as the winner is NOT lex-before it — so the
unique winner is fixed regardless of list order, and the PLANNED (apply) and EXECUTED
(execute) picks, both this selector, coincide. -/
theorem nearestTile_deterministic_lexmin {ox oy : Int} {cs : List Tile} {t : Tile}
    (h : nearestTile ox oy cs = some t) :
    ∀ u ∈ cs, manhattan ox oy u = manhattan ox oy t →
      (t.1 < u.1 ∨ (t.1 = u.1 ∧ t.2 ≤ u.2)) := by
  intro u hu hdist
  have hnot : ¬ keyLt ox oy u t := nearestTile_lexmin h u hu
  -- `u` does not lex-beat `t`, and distances tie, so `t.x < u.x`, or `t.x = u.x ∧ t.y ≤ u.y`.
  rcases Int.lt_trichotomy u.1 t.1 with hx | hx | hx
  · exact absurd (Or.inr (Or.inl ⟨hdist, hx⟩)) hnot
  · refine Or.inr ⟨hx.symm, ?_⟩
    rcases Int.lt_trichotomy u.2 t.2 with hy | hy | hy
    · exact absurd (Or.inr (Or.inr ⟨hdist, hx, hy⟩)) hnot
    · exact Int.le_of_eq hy.symm
    · exact Int.le_of_lt hy
  · exact Or.inl hx

/-- COST-MONOTONE in distance (the coupling that justifies the gather metric):
`staticGatherCost = 6 + manhattan` is monotone in Manhattan distance, so a strictly
nearer tile is strictly cheaper and the Manhattan-nearest tile IS the least-cost
destination. -/
theorem cost_monotone_in_distance (ox oy : Int) (a b : Tile)
    (h : manhattan ox oy a ≤ manhattan ox oy b) :
    staticGatherCost ox oy a ≤ staticGatherCost ox oy b := by
  unfold staticGatherCost
  exact Nat.add_le_add_left h 6

/-- COST corollary: the SELECTED tile is the least-cost destination over the list
(combines `nearestTile_min` with cost-monotonicity). -/
theorem nearestTile_least_cost {ox oy : Int} {cs : List Tile} {t : Tile}
    (h : nearestTile ox oy cs = some t) :
    ∀ u ∈ cs, staticGatherCost ox oy t ≤ staticGatherCost ox oy u := by
  intro u hu
  exact cost_monotone_in_distance ox oy t u (nearestTile_min h u hu)

end Formal.NearestTile
