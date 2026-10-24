"""What CI runs is pinned: actions by commit, Python, Node and the runner images by version, every package pip installs by
version and hash (specs/, section 7)."""
import os
import re
import tomllib
from importlib.metadata import distributions
from pathlib import Path

import pytest
import yaml
from packaging.requirements import Requirement

ROOT = Path(__file__).parent.parent
WORKFLOW = ROOT / ".github/workflows/redline.yml"
REQUIREMENTS = ROOT / "requirements.txt"
PIP = ROOT / "requirements-pip.txt"
USES = re.compile(r"^\s*(?:- )?uses: ([\w.-]+/[\w.-]+)@([0-9a-f]{40})  # (v\d+\.\d+\.\d+)$")
PIN = re.compile(r"([A-Za-z0-9._-]+)==([\w.]+)(?: ; (.+?))?((?: --hash=sha256:[0-9a-f]{64})+)")
INSTALLS = [
    "python -m pip install --require-hashes --force-reinstall -r requirements-pip.txt",
    "python -m pip install --require-hashes --force-reinstall -r requirements.txt",
    "python -m pip install --no-deps --no-build-isolation --check-build-dependencies --no-index -e .",
]
GATE = [  # the merge-base's Redline on a PR, with its venv's Python and not editable (O-SELF3)
    line.replace("python -m pip", '"$RUNNER_TEMP/gate/bin/python" -m pip').replace(" -e .", " .") for line in INSTALLS
]


def name(spec: str) -> str:
    """A distribution's name as pip compares it: lower case, runs of `-`, `_` and `.` as one `-`."""
    return re.sub(r"[-_.]+", "-", re.match(r"[A-Za-z0-9._-]+", spec).group()).lower()


def pinned(path: Path = REQUIREMENTS) -> dict[str, tuple[str, str | None, int]]:
    """Each pin of a requirements file by name: its version, its marker and how many hashes it has. A line that is
    neither a comment nor an `==` pin with at least one sha256 fails."""
    text = re.sub(r" ?\\\n\s*", " ", path.read_text(encoding="utf-8"))
    found = {}
    for line in text.splitlines():
        if line.strip() and not line.startswith("#"):
            match = PIN.fullmatch(line.strip())
            assert match, line
            found[name(match[1])] = (match[2], match[3], match[4].count("--hash="))
    return found


def jobs() -> dict[str, dict]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]


def steps() -> list[dict]:
    return [step for job in jobs().values() for step in job["steps"]]


def test_every_action_is_pinned_to_a_commit_with_its_tag_in_a_comment():
    lines = [line for line in WORKFLOW.read_text(encoding="utf-8").splitlines() if re.match(r"^\s*(- )?uses:", line)]
    assert len(lines) == sum("uses" in step for step in steps()) >= 4
    used = {}
    for line in lines:
        match = USES.match(line)
        assert match, line
        used.setdefault(match[1], set()).add(match.group(2, 3))
    assert all(len(shas) == 1 for shas in used.values()), used


@pytest.mark.spec("CI.APART.S4", new=True)  # O5: the suite job's setup-python is the fifth
def test_python_and_node_are_exact_versions():
    versions = [str(v) for step in steps() for k, v in step.get("with", {}).items() if k in ("python-version", "node-version")]
    assert len(versions) == 5 and all(re.fullmatch(r"\d+\.\d+\.\d+", v) for v in versions), versions


@pytest.mark.spec("CI.APART.S4", new=True)  # O5: five jobs, the suite job among them
def test_every_runner_image_is_named_by_its_version_never_latest():
    images = {job: spec["runs-on"] for job, spec in jobs().items()}
    assert len(images) == 5 and not any("latest" in image for image in images.values()), images
    assert all(re.fullmatch(r"ubuntu-\d+\.\d+|windows-\d{4}-vs\d{4}", image) for image in images.values()), images


@pytest.mark.spec("CI.APART.S4", new=True)  # O5: the suite job installs as the redline job does
def test_every_job_that_runs_pip_runs_the_hashed_lines_in_order_and_no_other():
    installs = {job: [line.strip() for step in spec["steps"] for line in step.get("run", "").splitlines() if "pip" in line]
                for job, spec in jobs().items()}
    assert {job: lines for job, lines in installs.items() if lines} == {
        "redline": GATE + INSTALLS, "suite": GATE + INSTALLS, "runners": INSTALLS, "windows": INSTALLS}


def test_every_pin_has_its_hashes_and_pip_is_pinned_and_setuptools_is_the_build_backend():
    assert list(pinned(PIP)) == ["pip"]
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["build-system"]["requires"] == [f"setuptools=={pinned()['setuptools'][0]}"]


def test_the_requirements_pin_every_dependency_and_extra_and_xdist_and_keep_mutmut_off_windows():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    needed = project["project"]["dependencies"] + sum(project["project"]["optional-dependencies"].values(), [])
    assert {name(spec) for spec in needed} | {"pytest-xdist"} <= set(pinned()), pinned()
    assert pinned()["mutmut"][1] == 'sys_platform != "win32"'


def pulled_in() -> dict[str, str]:
    """Each installed distribution the jobs' pip lines pull in, by name, at its version: Redline's requirements, its
    `mutation` extra and pytest-xdist where installed, and theirs in turn. A runner image's own tools, such as Windows'
    pipx, aren't."""
    installed = {name(d.metadata["Name"]): d for d in distributions()}
    found, todo = {}, [("redline", ("", "mutation")), ("pytest-xdist", ("",))]
    while todo:
        wanted, extras = todo.pop(0)
        dist = installed.get(wanted)
        if dist is None or name(dist.metadata["Name"]) in found:
            continue
        found[name(dist.metadata["Name"])] = dist.version
        for spec in dist.requires or []:
            requirement = Requirement(spec)
            if not requirement.marker or any(requirement.marker.evaluate({"extra": extra}) for extra in extras):
                todo.append((name(requirement.name), ("", *requirement.extras)))
    return found


@pytest.mark.skipif(os.environ.get("GITHUB_ACTIONS") != "true", reason="a job's environment is its pip lines' in CI")
def test_every_package_the_pip_lines_pull_in_is_pinned_at_its_version():
    pins, pulled = pinned(), pulled_in()
    assert {"redline", "pytest"} <= set(pulled), pulled
    assert {n: v for n, v in pulled.items() if n != "redline" and pins.get(n, ("",))[0] != v} == {}, pins
