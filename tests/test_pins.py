"""What CI runs is pinned: actions by commit, Python and Node by version, pip from constraints.txt (docs/design.md, section 7)."""
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
CONSTRAINTS = ROOT / "constraints.txt"
USES = re.compile(r"^\s*(?:- )?uses: ([\w.-]+/[\w.-]+)@([0-9a-f]{40})  # (v\d+\.\d+\.\d+)$")


def name(spec: str) -> str:
    """A distribution's name as pip compares it: lower case, runs of `-`, `_` and `.` as one `-`."""
    return re.sub(r"[-_.]+", "-", re.match(r"[A-Za-z0-9._-]+", spec).group()).lower()


def pins() -> dict[str, str]:
    lines = [line.strip() for line in CONSTRAINTS.read_text(encoding="utf-8").splitlines()]
    specs = [line for line in lines if line and not line.startswith("#")]
    assert all(re.fullmatch(r"[A-Za-z0-9._-]+==[\w.]+", spec) for spec in specs), specs
    return {name(spec): spec.partition("==")[2] for spec in specs}


def steps() -> list[dict]:
    flow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return [step for job in flow["jobs"].values() for step in job["steps"]]


def test_every_action_is_pinned_to_a_commit_with_its_tag_in_a_comment():
    lines = [line for line in WORKFLOW.read_text(encoding="utf-8").splitlines() if re.match(r"^\s*(- )?uses:", line)]
    assert len(lines) == sum("uses" in step for step in steps()) >= 4
    used = {}
    for line in lines:
        match = USES.match(line)
        assert match, line
        used.setdefault(match[1], set()).add(match.group(2, 3))
    assert all(len(shas) == 1 for shas in used.values()), used


def test_python_and_node_are_exact_versions():
    versions = [str(v) for step in steps() for k, v in step.get("with", {}).items() if k in ("python-version", "node-version")]
    assert len(versions) == 4 and all(re.fullmatch(r"\d+\.\d+\.\d+", v) for v in versions), versions


def test_every_pip_install_takes_the_constraints_and_pins_nothing_itself():
    installs = [line for step in steps() for line in step.get("run", "").splitlines() if "pip install" in line]
    assert len(installs) == 3
    assert all("-c constraints.txt" in line and "==" not in line for line in installs), installs


def test_the_constraints_pin_every_dependency_and_extra_and_xdist_and_the_build_backend_is_exact():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    needed = project["project"]["dependencies"] + sum(project["project"]["optional-dependencies"].values(), [])
    assert {name(spec) for spec in needed} | {"pytest-xdist"} <= set(pins()), pins()
    assert [re.fullmatch(r"setuptools==[\d.]+", spec) is not None for spec in project["build-system"]["requires"]] == [True]


def pulled_in() -> dict[str, str]:
    """Each installed distribution the pip lines pull in, by name, at its version: Redline's requirements, its `mutation`
    extra and pytest-xdist where installed, and theirs in turn. A runner image's own tools, such as Windows' pipx, aren't."""
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
    pinned, pulled = pins(), pulled_in()
    assert {"redline", "pytest"} <= set(pulled), pulled
    assert {n: v for n, v in pulled.items() if n != "redline" and pinned.get(n) != v} == {}, pinned
