"""redline/config.yaml, read from the repository root. A missing file means defaults."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

PATH = Path("redline") / "config.yaml"


@dataclass
class Config:
    generated: list[str] = field(default_factory=list)  # globs for lockfiles and generated files


def load_config(repo: Path) -> Config:
    path = repo / PATH
    data = yaml.safe_load(path.read_text()) if path.is_file() else None
    return Config(generated=list((data or {}).get("generated") or []))
