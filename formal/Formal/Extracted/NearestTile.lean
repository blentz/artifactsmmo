-- GENERATED from src/artifactsmmo_cli/ai/nearest_tile.py (sha256: 51e36b412c530835a2e9f653814f562f0fb52b066da86df4dff938342f2810af) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.NearestTile

/-- `abs` on `Int` (Python `abs`): non-negative magnitude. -/
def _intAbs (i : Int) : Int := Int.ofNat i.natAbs

/-- Strict lexicographic `<` on a 3-component Int key — the order Python's
tuple comparison gives `min(.., key=lambda t: (a, b, c))`. -/
def _lexLt3 (a b : (Int × Int × Int)) : Bool :=
  (decide (a.1 < b.1)) ||
    ((decide (a.1 = b.1)) && ((decide (a.2.1 < b.2.1)) ||
      ((decide (a.2.1 = b.2.1)) && (decide (a.2.2 < b.2.2)))))

/-- Python `min(xs, key=..)` as a first-wins left fold (Python `min` keeps the
EARLIEST minimum). Option-valued: `none` on `[]` where Python raises — callers
guard emptiness, so the two agree on every reachable input. -/
def _minByKey3 (key : (Int × Int) → (Int × Int × Int)) (xs : List (Int × Int)) :
    Option (Int × Int) :=
  match xs with
  | [] => none
  | h :: t =>
    some (List.foldl (fun best x => if _lexLt3 (key x) (key best) then x else best) h t)

/-- Extracted from `nearest_tile` (line 13). -/
def nearest_tile (origin_x : Int) (origin_y : Int) (tiles : List (Int × Int)) :
    Option (Int × Int) :=
  (if (decide ((Int.ofNat (List.length tiles)) = 0))
   then
    none
   else
    (_minByKey3 (fun t => (((_intAbs ((t.1) - origin_x)) + (_intAbs ((t.2) - origin_y))), (t.1), (t.2))) tiles))

end Extracted.NearestTile
