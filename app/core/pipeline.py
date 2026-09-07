"""Transactional batch generation pipeline."""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib,json,shutil,tempfile
from pathlib import Path
from typing import Callable
from app.models import Project
from app.runners import SolutionRunner
from app.validators import validate_input
from .engine import GenerationEngine

class GenerationPipeline:
    """Generate, validate, deduplicate, solve, then atomically publish a batch."""
    def __init__(self,engine:GenerationEngine|None=None):self.engine=engine or GenerationEngine()
    def generate(self,project:Project,project_dir:Path,destination:Path,*,progress:Callable[[int,int],None]|None=None,cancel:Callable[[],bool]|None=None)->Path:
        groups=[]
        for g in project.test_plan: groups.extend([{"name":g.name,"profile":g.profile,"overrides":g.overrides}]*g.count)
        while len(groups)<project.test_count:groups.append({"name":"Random","profile":"random","overrides":{}})
        groups=groups[:project.test_count]; runner=SolutionRunner(project.compiler_path or None); executable:Path|None=None
        with tempfile.TemporaryDirectory(prefix="tgs-batch-") as raw:
            stage=Path(raw)/destination.name; stage.mkdir(); seen:dict[str,int]={}; manifest=[]
            solution=project_dir/project.solution_path
            if solution.exists():
                executable=Path(raw)/("solution.exe" if solution.suffix==".cpp" else solution.name)
                if solution.suffix==".cpp":runner.compile(solution,executable,project.cpp_standard)
                else:executable=solution
            for i,group in enumerate(groups,1):
                if cancel and cancel():raise RuntimeError("Generation cancelled")
                seed=project.seed+i
                custom_validator = project_dir / project.validator_path if project.validator_path else None
                for retry in range(101):
                    text,_=self.engine.generate(project,seed,index=i,group=group,base=project_dir)
                    valid,message=validate_input(text,project.to_dict(),custom_validator)
                    if not valid:raise RuntimeError(f"Validator Error at test{i:02d}: {message}")
                    digest=hashlib.sha256(text.encode()).hexdigest(); duplicate=seen.get(digest)
                    if not duplicate or project.duplicate_policy != "regenerate":
                        break
                    seed = project.seed + i + (retry + 1) * project.test_count
                else:
                    raise RuntimeError(f"Duplicate Input: could not regenerate test{i:02d} uniquely")
                if duplicate and project.duplicate_policy=="fail":raise RuntimeError(f"Duplicate Input: test{i:02d} duplicates test{duplicate:02d}")
                seen.setdefault(digest,i); folder=project.test_folder_pattern.format(index=i); test_dir=stage/folder; test_dir.mkdir()
                (test_dir/project.input_filename).write_text(text,encoding="utf-8")
                if executable:
                    result=runner.run(executable,text,project.time_limit,project.io_mode,project.input_filename,project.output_filename)
                    if result.status!="OK":raise RuntimeError(f"test{i:02d}: {result.status}\n{result.stderr}")
                    (test_dir/project.output_filename).write_text(result.stdout,encoding="utf-8")
                manifest.append({"id":f"{i:02d}","folder":folder,"seed":seed,"group":group["name"],"input_sha256":digest,"duplicate_of":duplicate})
                if progress:progress(i,len(groups))
            data={"problem":project.problem_name,"generated_at":datetime.now(timezone.utc).isoformat(),"master_seed":project.seed,"tests":manifest}
            (stage/"manifest.json").write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8")
            target=destination
            version=2
            while target.exists():target=destination.with_name(f"{destination.name}_V{version:02d}");version+=1
            shutil.copytree(stage,target);return target
