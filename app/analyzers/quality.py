"""Generic numeric coverage analyzer."""
from pathlib import Path
from statistics import mean
from typing import Any

def analyze(folder:Path)->dict[str,Any]:
    """Summarize numeric values without assuming the problem algorithm."""
    tests=list(folder.glob("test*/*.inp")); rows=[]
    for path in tests:
        try:rows.append([int(x) for x in path.read_text(encoding="utf-8").split()])
        except ValueError:continue
    values=[x for row in rows for x in row]; warnings=[]
    if values and 1 not in values:warnings.append("No value n=1 observed")
    if values and min(values)>=0:warnings.append("No negative values")
    if values and len(values)==len(set(values)):warnings.append("No duplicates")
    return {"test_count":len(tests),"scalar_min":min(values) if values else None,"scalar_max":max(values) if values else None,"scalar_mean":mean(values) if values else None,"warnings":warnings}
