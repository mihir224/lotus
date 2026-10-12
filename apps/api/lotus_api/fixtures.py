import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import get_settings


@lru_cache
def load_fixture(name: str) -> list[dict[str, Any]]:
    path: Path = get_settings().fixture_dir / name
    return json.loads(path.read_text(encoding="utf-8"))
