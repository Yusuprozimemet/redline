import subprocess
from pathlib import Path

import pytest

pytest_plugins = ["pytester"]


class Repo:
    """A throwaway git repository for building toy histories."""

    def __init__(self, path: Path):
        self.path = path
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "toy@example.com")
        self.git("config", "user.name", "Toy")

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.path, check=True, capture_output=True, text=True
        ).stdout.strip()

    def commit(self, message: str, **files: str) -> str:
        """Write files (keyword name -> content, `__` for `/`) and commit them."""
        for name, content in files.items():
            target = self.path / name.replace("__", "/")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    return Repo(tmp_path / "toy")
