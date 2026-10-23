import json
import re
import subprocess
from pathlib import Path

import pytest

from redline.pr import GitHub

pytest_plugins = ["pytester"]

OWN = "{owner}/{repo}"  # the checkout's own repository, as `gh api` names it
TOY = "acme/toy"  # the name GitHub gives it
NOT_FOUND = "gh: Not Found (HTTP 404)"  # gh's stderr for a run or a repository GitHub doesn't show (P13)
ASKED = re.compile(r"repos/([^/?]+/[^/?]+)(?:/actions/runs/([^/?]+)(/jobs)?)?(?:\?.*)?")


class FakeActions:
    """GitHub's Actions API, as `gh api` answers it through `GitHub.run`, for every test but tests/test_github.py.

    It answers `repos/<repo>` and `repos/<repo>/actions/runs/<id>[/jobs]`, with a run only when the test
    registered it, in that repository, and a 404 for any other; every other command goes to `run` as before.
    It gives whole JSON, as `gh api` does without `--jq`, and records the path of each answer it gives."""

    def __init__(self):
        self.runs: dict[tuple[str, str], dict] = {}
        self.jobs: dict[tuple[str, str], list[dict]] = {}
        self.errors: dict[tuple[str, str], str] = {}  # a run's stderr other than a 404, on every try
        self.asked: list[str] = []
        self.hidden = False  # GitHub doesn't show the token the checkout's repository
        self.missing = False  # no `gh` on the path

    @staticmethod
    def url(run: int | str, where: str = TOY) -> str:
        return f"https://github.com/{where}/actions/runs/{run}"

    def register(self, run: int, sha: str, jobs: dict[str, str | None] | None = None, where: str = OWN,
                 **fields: str | None) -> str:
        """A push run of redline.yml on main, on `sha`, its redline job concluded success, unless `jobs`
        and `fields` say otherwise; a field given as None is left out. Gives its URL."""
        named = TOY if where == OWN else where
        answer = {"id": run, "html_url": self.url(run, named), "event": "push", "head_sha": sha,
                  "head_branch": "main", "path": ".github/workflows/redline.yml", "status": "completed",
                  "repository": {"full_name": named}}
        answer.update(fields)
        self.runs[where, str(run)] = {key: value for key, value in answer.items() if value is not None}
        self.jobs[where, str(run)] = [{"name": name, "status": "completed", "conclusion": conclusion}
                                      for name, conclusion in ({"redline": "success"} if jobs is None else jobs).items()]
        return self.url(run, named)

    def push_run(self, commit: str, result: str = "pass", breaks: dict | None = None, url: str | None = None) -> str:
        """The push run CI notes on `commit`, its redline job failed when the note records a failure, as
        `redline ci push` writes it; gives the URL the note names: `url`, when CI was given one."""
        failed = result == "fail" or "fail" in (breaks or {}).values()
        run = int(url.rsplit("/", 1)[1]) if url else int(commit[:7], 16)
        named = self.register(run, commit, {"redline": "failure" if failed else "success"},
                              **({"html_url": url} if url else {}))
        return url or named

    def answer(self, real, github: GitHub, command: tuple[str, ...]) -> str:
        if command[0] == "gh" and self.missing:
            raise FileNotFoundError(2, "No such file or directory", "gh")
        path = next((part for part in command[2:] if not part.startswith("-")), "")
        if command[:2] != ("gh", "api") or not (asked := ASKED.fullmatch(path)):
            return real(github, *command)
        assert "--jq" not in command and "-q" not in command, "FakeActions answers whole JSON, as gh api does"
        where, run, jobs = OWN if asked[1] == TOY else asked[1], asked[2], asked[3]
        self.asked.append(f"repos/{where}" + (f"/actions/runs/{run}{jobs or ''}" if run else ""))
        failed = f"{' '.join(command[:3])}: "
        if run is None:
            if where != OWN or self.hidden:
                raise RuntimeError(failed + NOT_FOUND)
            return json.dumps({"full_name": TOY, "html_url": f"https://github.com/{TOY}"})
        if (where, run) in self.errors:
            raise RuntimeError(failed + self.errors[where, run])
        if (where, run) not in self.runs:
            raise RuntimeError(failed + NOT_FOUND)
        if jobs:
            return json.dumps({"total_count": len(self.jobs[where, run]), "jobs": self.jobs[where, run]})
        return json.dumps(self.runs[where, run])


@pytest.fixture(autouse=True)
def actions(request, monkeypatch):
    """Every test reads the Actions API through FakeActions; tests/test_github.py reads GitHub itself."""
    if request.path.name == "test_github.py":
        yield None
        return
    fake, real = FakeActions(), GitHub.run
    monkeypatch.setattr(GitHub, "run", lambda github, *command: fake.answer(real, github, command))
    monkeypatch.setattr(FakeActions, "current", fake, raising=False)  # for helpers that write a note
    yield fake


class Repo:
    """A throwaway git repository for building toy histories."""

    def __init__(self, path: Path):
        self.path = path
        path.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "toy@example.com")
        self.git("config", "user.name", "Toy")

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.path, check=True, capture_output=True, text=True
        ).stdout.strip()

    def commit(self, message: str, files: dict[str, str] | None = None) -> str:
        for name, content in (files or {}).items():
            target = self.path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    return Repo(tmp_path / "toy")
