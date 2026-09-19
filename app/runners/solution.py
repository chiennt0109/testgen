"""Compile and execute C++, Python, or native solutions."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import shutil, subprocess, sys, tempfile

@dataclass(slots=True)
class RunResult:
    status:str; stdout:str=""; stderr:str=""; returncode:int|None=None

class SolutionRunner:
    """One compilation per batch and isolated execution with timeout."""
    def __init__(self,gpp:str|None=None): self.gpp=gpp or shutil.which("g++") or ""
    def compiler_status(self)->tuple[bool,str]:
        if not self.gpp:return False,"g++ not found"
        result=subprocess.run([self.gpp,"--version"],capture_output=True,text=True,encoding="utf-8",errors="replace"); return result.returncode==0,result.stdout.splitlines()[0]
    def compile(self,source:Path,output:Path,standard:str="c++17")->Path:
        if not self.gpp: raise RuntimeError("Compile Error: g++ not found")
        result=subprocess.run([self.gpp,str(source),f"-std={standard}","-O2","-pipe","-o",str(output)],capture_output=True,text=True,encoding="utf-8",errors="replace")
        if result.returncode: raise RuntimeError(f"Compile Error:\n{result.stderr}")
        return output
    def run(self,program:Path,input_text:str,timeout:float=2.0,io_mode:str="stdio",input_name:str="input.txt",output_name:str="output.txt")->RunResult:
        program = program.resolve()
        command=[sys.executable,str(program)] if program.suffix.lower()==".py" else [str(program)]
        try:
            with tempfile.TemporaryDirectory(prefix="tgs-run-") as raw:
                cwd=Path(raw)
                if io_mode=="file": (cwd/input_name).write_text(input_text,encoding="utf-8")
                result=subprocess.run(command,input=None if io_mode=="file" else input_text,cwd=cwd,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=timeout)
                if result.returncode:return RunResult("RUNTIME ERROR",result.stdout,result.stderr,result.returncode)
                if io_mode=="file":
                    path=cwd/output_name
                    if not path.exists():return RunResult("OUTPUT MISSING",stderr=result.stderr)
                    return RunResult("OK",path.read_text(encoding="utf-8"),result.stderr,0)
                return RunResult("OK",result.stdout,result.stderr,0)
        except subprocess.TimeoutExpired as exc:return RunResult("TIMEOUT",exc.stdout or "",exc.stderr or "")
