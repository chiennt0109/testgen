import hashlib,json,random,zipfile
from pathlib import Path
import pytest
from app.core.constraints import ConstraintError,evaluate
from app.core.engine import GenerationEngine
from app.core.pipeline import GenerationPipeline
from app.exporters import export_zip
from app.generators.blocks import array,graph,query_list,tree
from app.models import Project

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
