import hashlib,json,random,zipfile
from pathlib import Path
import pytest
from app.core.constraints import ConstraintError,evaluate
from app.core.engine import GenerationEngine
from app.core.pipeline import GenerationPipeline
from app.exporters import export_zip
from app.generators.blocks import array,graph,query_list,tree
from app.generators.queries import generate_queries
from app.models import Project, TestGroup as PlanGroup
from app.core.stress import StressTester, normalize_output
from app.core.planning import audit_plan
from app.validators import validate_subtasks

def test_constraint_engine():
    assert evaluate("n*(n-1)/2",{"n":5})==10
    with pytest.raises(ConstraintError):evaluate("__import__('os')",{})

@pytest.mark.parametrize("pattern",["random","all_equal","strict_increasing","decreasing","many_duplicates","binary","mountain"])
def test_array_generator(pattern):
    result=array({"length":10,"min":0,"max":20,"pattern":pattern},{},random.Random(2))
    assert len(result)==10 and all(0<=x<=20 for x in result)

def test_graph_simple_connected():
    edges=graph({"n":8,"m":12,"connected":True,"simple":True},{},random.Random(3))
    assert len(edges)==len({tuple(sorted(e)) for e in edges})==12
    reached={1}
    while True:
        old=len(reached);reached|={v for u,v in edges if u in reached}|{u for u,v in edges if v in reached}
        if len(reached)==old:break
    assert len(reached)==8

@pytest.mark.parametrize("pattern",["random_tree","path","star","balanced_binary_tree","broom","caterpillar"])
def test_tree_generator(pattern):
    edges=tree({"n":20,"pattern":pattern},{},random.Random(1));assert len(edges)==19
    assert all(1<=u<=20 and 1<=v<=20 for u,v in edges)

def test_query_ranges():
    for mode in ["random_range","single_point","whole_range","prefix","suffix","nested"]:
        assert all(1<=l<=r<=30 for l,r in query_list({"count":50,"n":30,"pattern":mode},{},random.Random(9)))

def test_seed_reproducibility():
    p=Project(schema=[{"type":"integer","name":"n","min":5,"max":5,"layout":"same_line"},{"type":"array","name":"a","length":"n","min":-5,"max":5}])
    one=GenerationEngine().generate(p,123)[0];two=GenerationEngine().generate(p,123)[0]
    assert one==two and hashlib.sha256(one.encode()).digest()==hashlib.sha256(two.encode()).digest()

def test_duplicate_detection_and_folder_export(tmp_path:Path):
    p=Project(problem_name="X",input_filename="X.inp",output_filename="X.out",test_count=2,duplicate_policy="warn",schema=[{"type":"integer","name":"n","min":1,"max":1}])
    target=GenerationPipeline().generate(p,tmp_path,tmp_path/"generated"/"X")
    manifest=json.loads((target/"manifest.json").read_text());assert manifest["tests"][1]["duplicate_of"]==1
    archive=export_zip(target,tmp_path/"X.zip")
    with zipfile.ZipFile(archive) as z: assert "X/test01/X.inp" in z.namelist()

def test_output_normalization():
    assert normalize_output("  1  2\n3\n") == "1 2 3"

def test_schema_driven_range_query_dependencies():
    spec = {
        "count": 100,
        "pattern": "random_range",
        "query_types": [{
            "name": "Range", "weight": 100,
            "fields": [
                {"name": "l", "type": "integer", "min": 1, "max": "n"},
                {"name": "r", "type": "integer", "min": "l", "max": "n"},
            ],
        }],
    }
    rows = generate_queries(spec, {"n": 20}, random.Random(22))
    assert len(rows) == 100
    assert all(1 <= left <= right <= 20 for left, right in rows)

def test_mixed_weighted_query_types_and_fixed_prefixes():
    spec = {
        "count": 200,
        "query_types": [
            {"name": "Update", "weight": 40, "prefix": 1, "fields": [
                {"name": "i", "type": "integer", "min": 1, "max": "n"},
                {"name": "x", "type": "integer", "min": -10**9, "max": 10**9},
            ]},
            {"name": "Range", "weight": 60, "prefix": 2, "fields": [
                {"name": "l", "type": "integer", "min": 1, "max": "n"},
                {"name": "r", "type": "integer", "min": "l", "max": "n"},
            ]},
        ],
    }
    rows = generate_queries(spec, {"n": 30}, random.Random(7))
    assert {row[0] for row in rows} == {1, 2}
    assert all(len(row) == 3 for row in rows)
    assert all(row[0] != 2 or 1 <= row[1] <= row[2] <= 30 for row in rows)

def test_query_output_layout_is_not_implicit():
    base = {
        "type": "query_list", "name": "queries", "count": 2,
        "pattern": "whole_range",
        "query_types": [{"name": "Range", "weight": 100, "fields": [
            {"name": "l", "type": "integer", "min": 1, "max": "n"},
            {"name": "r", "type": "integer", "min": "l", "max": "n"},
        ]}],
    }
    multiline = Project(schema=[{"type": "integer", "name": "n", "min": 5, "max": 5, "newline": True}, {**base, "one_query_per_line": True}])
    singleline = Project(schema=[{"type": "integer", "name": "n", "min": 5, "max": 5, "newline": True}, {**base, "one_query_per_line": False, "layout": "same_line"}])
    assert GenerationEngine().generate(multiline, 1)[0].splitlines() == ["5", "1 5", "1 5"]
    assert GenerationEngine().generate(singleline, 1)[0].splitlines() == ["5", "1 5 1 5"]

@pytest.mark.parametrize("pattern", ["random_range", "single_point", "whole_range", "prefix", "suffix", "short_range", "long_range", "nested", "overlapping", "repeated"])
def test_query_patterns_respect_schema(pattern):
    spec = {
        "count": 12, "pattern": pattern,
        "query_types": [{"name": "Range", "weight": 100, "fields": [
            {"name": "l", "type": "integer", "min": 1, "max": "n"},
            {"name": "r", "type": "integer", "min": "l", "max": "n"},
        ]}],
    }
    rows = generate_queries(spec, {"n": 20}, random.Random(19))
    assert all(1 <= left <= right <= 20 for left, right in rows)
    if pattern == "single_point": assert all(left == right for left, right in rows)
    if pattern == "whole_range": assert all((left, right) == (1, 20) for left, right in rows)
    if pattern == "prefix": assert all(left == 1 for left, _ in rows)
    if pattern == "suffix": assert all(right == 20 for _, right in rows)

def test_query_duplicate_avoid_and_sorted_order():
    spec = {
        "count": 5, "duplicate_policy": "avoid", "query_order": "sorted",
        "query_types": [{"name": "Point", "weight": 100, "fields": [
            {"name": "x", "type": "integer", "min": 1, "max": 20},
        ]}],
    }
    rows = generate_queries(spec, {}, random.Random(31))
    assert len(rows) == len(set(rows)) == 5
    assert rows == sorted(rows, key=lambda row: tuple(str(value) for value in row))

def test_subtask_constraints_validate_scalar_and_array_context():
    subtasks = [{
        "name": "Small", "start": 1, "end": 5,
        "constraints": {
            "n": {"min": 1, "max": 10},
            "a": {"length": "n", "min": -5, "max": 5},
        },
    }]
    assert validate_subtasks(2, {"n": 3, "a": [-5, 0, 5]}, subtasks) == (True, "")
    valid, reason = validate_subtasks(2, {"n": 3, "a": [-6, 0, 5]}, subtasks)
    assert not valid and "below -5" in reason
    assert validate_subtasks(8, {"n": 100, "a": []}, subtasks) == (True, "")

def test_pipeline_rejects_test_outside_subtask_constraint(tmp_path:Path):
    project = Project(
        problem_name="SUBTASK", input_filename="SUBTASK.inp", test_count=1,
        schema=[{"type": "integer", "name": "n", "min": 20, "max": 20}],
        subtasks=[{"name": "n <= 10", "start": 1, "end": 1,
                  "constraints": {"n": {"max": 10}}}],
    )
    with pytest.raises(RuntimeError, match="Subtask Constraint Error"):
        GenerationPipeline().generate(project, tmp_path, tmp_path / "generated" / "SUBTASK")

def test_stress_tester_uses_profile_and_runs_repeatedly(tmp_path:Path):
    (tmp_path / "solution.py").write_text(
        "import sys\nprint(int(sys.stdin.read().strip()) * 2)\n", encoding="utf-8")
    (tmp_path / "brute.py").write_text(
        "import sys\nn=int(sys.stdin.read().strip())\nprint(n+n)\n", encoding="utf-8")
    project = Project(
        solution_path="solution.py", brute_path="brute.py", test_count=1,
        schema=[{"type": "integer", "name": "n", "min": 1, "max": 100}],
        test_plan=[PlanGroup("Tiny", 1, "small", "increment",
                             {"n": {"min": 5, "max": 5}})],
    )
    progress: list[tuple[int, int, int]] = []
    result = StressTester().run(
        project, tmp_path, 3, 1.0, profile="Small random",
        progress=lambda current, total, seed, _elapsed: progress.append((current, total, seed)))
    assert result.passed == 3 and result.failed == 0
    assert [item[0] for item in progress] == [1, 2, 3]
    assert not (tmp_path / ".tgs-build").exists()

def test_plan_audit_finds_count_mismatch_and_group_subtask_conflict():
    project = Project(
        test_count=20,
        test_plan=[
            PlanGroup("sub1", 1, "small", "increment", {"n": {"min": 1, "max": 1999}}),
            PlanGroup("sub2", 1, "large", "increment", {"n": {"min": 2000, "max": 100000}}),
        ],
        subtasks=[{"name": "Subtask 1", "start": 1, "end": 6,
                  "constraints": {"n": {"min": 1, "max": 1999}}}],
    )
    audit = audit_plan(project)
    assert any("Test Plan có 2 test" in warning for warning in audit.warnings)
    assert any("test02" in error and "xung đột" in error for error in audit.errors)

def test_pipeline_saves_runtime_error_diagnostics(tmp_path:Path):
    (tmp_path / "bad.py").write_text(
        "import sys\nsys.stderr.write('boom\\n')\nraise SystemExit(7)\n", encoding="utf-8")
    project = Project(
        problem_name="BAD", input_filename="BAD.inp", output_filename="BAD.out",
        solution_path="bad.py", test_count=1,
        schema=[{"type": "integer", "name": "n", "min": 1, "max": 1}],
    )
    with pytest.raises(RuntimeError, match="exit code: 7"):
        GenerationPipeline().generate(project, tmp_path, tmp_path / "generated" / "BAD")
    failure = tmp_path / "generation_failures" / "test01"
    assert (failure / "BAD.inp").read_text(encoding="utf-8").strip() == "1"
    assert "boom" in (failure / "stderr.txt").read_text(encoding="utf-8")
    assert json.loads((failure / "run.json").read_text(encoding="utf-8"))["returncode"] == 7

def test_generate_inputs_can_skip_broken_solution(tmp_path:Path):
    (tmp_path / "bad.py").write_text("raise SystemExit(9)\n", encoding="utf-8")
    project = Project(
        problem_name="INPUT_ONLY", input_filename="INPUT_ONLY.inp",
        output_filename="INPUT_ONLY.out", solution_path="bad.py",
        generate_outputs=False, test_count=1,
        schema=[{"type": "integer", "name": "n", "min": 3, "max": 3}],
    )
    target = GenerationPipeline().generate(
        project, tmp_path, tmp_path / "generated" / "INPUT_ONLY")
    assert (target / "test01" / "INPUT_ONLY.inp").read_text().strip() == "3"
    assert not (target / "test01" / "INPUT_ONLY.out").exists()
