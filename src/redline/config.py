"""redline/config.yaml, read from the repository root. A missing file means defaults."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from redline.order import shown

PATH = Path("redline") / "config.yaml"
LEVELS = ("lite", "standard", "critical")
RIGOR = re.compile(r"^Rigor:\s*(\S+)\s*$", re.MULTILINE)


@dataclass
class Config:
    generated: list[str] = field(default_factory=list)  # globs for lockfiles and generated files
    rigor: str = "standard"  # the level of a change whose proposal declares none
    rules: dict[str, list[str]] = field(default_factory=dict)  # cause -> lines every brief prints (§10)
    support: list[str] = field(default_factory=list)  # globs for test-support files a critical reach follows (§4)


def load_config(repo: Path, rev: str | None = None) -> Config:
    """The config in the working tree, or at `rev`."""
    path = repo / PATH
    text = shown(repo, PATH.as_posix(), rev) if rev else path.read_text() if path.is_file() else None
    data = (yaml.safe_load(text) if text is not None else None) or {}
    rules = {str(cause): [str(r) for r in lines or []] for cause, lines in (data.get("rules") or {}).items()}
    return Config(list(data.get("generated") or []), str(data.get("rigor") or "standard"), rules,
                  list(data.get("support") or []))


def rigor(repo: Path, change: str, rev: str | None = None) -> str:
    """The change's level: its proposal's `Rigor:` line, else the config's `rigor:`, read at `rev`, else the
    working tree. See §4, §8."""
    proposal = shown(repo, f"redline/changes/{change}/proposal.md", rev)
    found = RIGOR.search(proposal) if proposal is not None else None
    level = found[1] if found else load_config(repo, rev).rigor
    if level not in LEVELS:
        raise RuntimeError(f"{change}: unknown rigor level `{level}`")
    return level
