"""Built-in and custom validation."""
from __future__ import annotations
import importlib.util
from pathlib import Path
from typing import Any

def validate_input(text:str, params:dict[str,Any], custom:Path|None=None)->tuple[bool,str]:
    """Perform basic text checks and optionally call validator.py."""
    if not text.strip(): return False,"Input is empty"
    if "\x00" in text: return False,"Input contains NUL"
    if custom and custom.is_file():
        try:
            spec=importlib.util.spec_from_file_location("tgs_validator",custom); module=importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            assert spec and spec.loader; spec.loader.exec_module(module); result=module.validate(text,params)
            return (bool(result[0]),str(result[1]))
        except Exception as exc: return False,f"Validator Error: {exc}"
    return True,""
