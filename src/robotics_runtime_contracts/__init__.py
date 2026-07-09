from __future__ import annotations

from importlib.resources import files
from pathlib import Path


def schema_dir() -> Path:
    return Path(str(files("robotics_runtime_contracts").joinpath("schemas")))


def schema_path(name: str) -> Path:
    path = schema_dir() / name
    if not path.is_file():
        raise FileNotFoundError(path)
    return path
