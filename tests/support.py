from pathlib import Path
from typing import Any

import yaml


def load_fixture(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))
