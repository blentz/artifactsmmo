from artifactsmmo_cli.audit.proof_tags import (
    IndexRow,
    manifest_audit_names,
    manifest_open_lines,
    render_audit_lean,
    render_index_markdown,
)

_MANIFEST_SAMPLE = """import Formal
open Formal.CalculatePath Formal.TaskBatch
-- a comment mentioning #check @Formal.NotReal.ignored is still a check line
#check @pathFrom_valid         -- bare, resolved by the open above
#check @Formal.GearPolicy.armor_dominates
#check @InventoryRoom.hasRoom_false_of_no_slot
#check @Formal.GearPolicy.armor_dominates
"""


def test_manifest_audit_names_dedupes_and_keeps_file_order():
    assert manifest_audit_names(_MANIFEST_SAMPLE) == [
        "pathFrom_valid",
        "Formal.GearPolicy.armor_dominates",
        "InventoryRoom.hasRoom_false_of_no_slot",
    ]


def test_manifest_audit_names_ignores_checks_inside_comments():
    """A retired row or a `#check @…` quoted in prose must NOT become an audited
    declaration: it may name something that no longer exists, and the generated
    audit file would stop compiling."""
    assert "Formal.NotReal.ignored" not in manifest_audit_names(_MANIFEST_SAMPLE)


def test_manifest_open_lines_are_carried_over():
    """Manifest abbreviates some checks to bare names, so the generated audit file
    must reproduce the same `open` context or those names will not resolve."""
    assert manifest_open_lines(_MANIFEST_SAMPLE) == [
        "open Formal.CalculatePath Formal.TaskBatch"
    ]


def test_render_audit_lean_prints_axioms_for_every_name_under_the_opens():
    out = render_audit_lean(["pathFrom_valid", "Formal.GearPolicy.armor_dominates"],
                            ["open Formal.CalculatePath"])
    assert "DO NOT EDIT" in out
    assert "import Formal\n" in out
    # the open must precede the bare name it resolves
    assert out.index("open Formal.CalculatePath") < out.index("#print axioms pathFrom_valid")
    assert "#print axioms Formal.GearPolicy.armor_dominates\n" in out


def test_render_audit_lean_is_the_manifest_surface_exactly():
    """The audited surface IS the traceability surface — that equality is the
    whole point of deriving one file from the other."""
    names = manifest_audit_names(_MANIFEST_SAMPLE)
    out = render_audit_lean(names, manifest_open_lines(_MANIFEST_SAMPLE))
    printed = [ln.removeprefix("#print axioms ")
               for ln in out.splitlines() if ln.startswith("#print axioms ")]
    assert printed == names


def test_render_index_lists_modules_concepts_properties():
    rows = [IndexRow("PlannerDepthBound", ["planner", "core"], ["safety", "reachability"])]
    md = render_index_markdown(rows)
    assert "| Module | Concepts | Properties |" in md
    assert "PlannerDepthBound" in md
    assert "planner, core" in md
    assert "safety, reachability" in md
