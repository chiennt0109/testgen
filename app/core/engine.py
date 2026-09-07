"""Schema orchestration independent from the GUI."""
from __future__ import annotations
import importlib.util
import random
import traceback
from pathlib import Path
from typing import Any
from app.generators import generate_block
from app.models import Project


class GenerationEngine:
    """Generate formatted input from a project schema or custom module."""
    def generate(self, project: Project, seed: int, *, index: int = 1, group: dict[str, Any] | None = None, base: Path | None = None) -> tuple[str, dict[str, Any]]:
        if project.generator_path:
            path=(base or Path.cwd())/project.generator_path
            try:
                spec=importlib.util.spec_from_file_location(f"tgs_custom_{seed}",path); module=importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
                assert spec and spec.loader; spec.loader.exec_module(module)
                text=module.generate(seed,{**project.to_dict(),"test_index":index,"group":group or {}})
                if not isinstance(text,str): raise TypeError("generate() must return str")
                return text,text and {} or {}
            except Exception as exc: raise RuntimeError(f"Generator Error: {exc}\n{traceback.format_exc()}") from exc
        rng=random.Random(seed); ctx:dict[str,Any]={}; lines:list[str]=[]; current:list[str]=[]
        for block in project.schema:
            merged=dict(block); merged.update((group or {}).get("overrides",{}).get(block.get("name",""),{}))
            value=generate_block(merged,ctx,rng); name=merged.get("name")
            if name: ctx[name]=value
            layout=merged.get("layout","line")
            if isinstance(value,list):
                if current: lines.append(" ".join(current)); current=[]
                if value and isinstance(value[0],tuple):
                    one_per_line = merged.get("one_query_per_line", layout != "same_line")
                    rendered = [" ".join(map(str,row)) for row in value]
                    if one_per_line:
                        lines.extend(rendered)
                    else:
                        lines.append(" ".join(rendered))
                else: lines.append(" ".join(map(str,value)))
            elif "\n" in str(value):
                if current: lines.append(" ".join(current)); current=[]
                lines.extend(str(value).splitlines())
            elif layout=="same_line": current.append(str(value))
            else:
                current.append(str(value))
                if merged.get("newline",False): lines.append(" ".join(current)); current=[]
        if current: lines.append(" ".join(current))
        return "\n".join(lines)+"\n",ctx
