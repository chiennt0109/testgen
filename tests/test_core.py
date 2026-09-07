import hashlib,json,random,zipfile
from pathlib import Path
import pytest
from app.core.constraints import ConstraintError,evaluate
from app.core.engine import GenerationEngine
from app.core.pipeline import GenerationPipeline
from app.exporters import export_zip
from app.generators.blocks import array,graph,query_list,tree
from app.generators.queries import generate_queries
from app.models import Project
from app.core.stress import normalize_output

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
