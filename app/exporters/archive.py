"""Safe ZIP export."""
from pathlib import Path
import zipfile

def export_zip(source:Path,destination:Path)->Path:
    """Archive generated tests, excluding caches and temporary files."""
    with zipfile.ZipFile(destination,"w",zipfile.ZIP_DEFLATED) as archive:
        for path in source.rglob("*"):
            if path.is_file() and not any(p in {"__pycache__",".cache","temp"} for p in path.parts):archive.write(path,path.relative_to(source.parent))
    return destination
