"""redline/config.yaml, read from the repository root. A missing file means defaults."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PATH = Path("redline") / "config.yaml"
LEVELS = ("lite", "standard", "critical")
RIGOR = re.compile(r"^Rigor:\s*(\S+)\s*$", re.MULTILINE)


@dataclass
class Config:
    generated: list[str] = field(default_factory=list)  # globs for lockfiles and generated files
    rigor: str = "standard"  # the level of a change whose proposal declares none
    rules: dict[str, list[str]] = field(default_factory=dict)  # cause -> lines every brief prints (§10)


def load_config(repo: Path) -> Config:
    path = repo / PATH
    data = (yaml.safe_load(path.read_text()) if path.is_file() else None) or {}
    rules = {str(cause): [str(r) for r in lines or []] for cause, lines in (data.get("rules") or {}).items()}
    return Config(generated=list(data.get("generated") or []), rigor=str(data.get("rigor") or "standard"),
                  rules=rules)


def rigor(repo: Path, change: str) -> str:
    """The change's level: its proposal's `Rigor:` line, else the config's `rigor:`. See §4, §8."""
    proposal = repo / "redline" / "changes" / change / "proposal.md"
    found = RIGOR.search(proposal.read_text(encoding="utf-8")) if proposal.is_file() else None
    level = found[1] if found else load_config(repo).rigor
    if level not in LEVELS:
        raise RuntimeError(f"{change}: unknown rigor level `{level}`")
    return level
