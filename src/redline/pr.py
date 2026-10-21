"""`redline pr`: run the local gates for the open step, then open its pull request.

check-lines, check-plan (with a critical initiative's plan audits), check-defects and check-relabel always run; the defect log is required at C
only, the blind relabel at C at critical only. check-premises and check-audit run at the S step, on the step's own
change. check-links
and check-order run from the R step on: at S the delta declares scenarios that have no tests yet.
check-order skips `hold` scenarios, which have no red by design. check-break runs at R only.
check-lock runs on every change the lock names at every step, and on the step's change at R and G (against main's lock at G);
at every step the whole lock is compared by test with main's (lock.check_frozen). check-track runs at G steps (track.py). check-close and check-specs run at C (close.py, specs.py).
A changed `rigor:` in the config or `Rigor:` line in a plan, a change's level lowered, a glob added to `generated:` or `support:`,
a deleted plan, or a change taken out of one, needs an approved `Redline-Rigor` claim at every step. Over 400 lines, an `Oversized:
<reason>` trailer needs a maintainer's label, as a departure does (approval.py); locally, where
the PR doesn't exist yet, `pr` only reports that CI will need it.
If every gate passes, each commit of the step gets the `Redline-Step: <change>/<step>` trailer
(once), the branch is pushed, the PR is opened with `gh`, and the step stops being open. Pushing and `gh` sit behind `GitHub`, which tests replace.
"""

import subprocess
from pathlib import Path

from redline.approval import OVERSIZED, RIGOR, Approvals, claims
from redline.audit import check_audit
from redline.breaks import check_break, holds
from redline.close import check_close
from redline.config import LEVELS, load_config, rigor
from redline.defects import check_defects
from redline.lines import LIMIT, check_lines
from redline.links import check_links
from redline.lock import check_frozen, check_lock, read_lock
from redline.order import check_order, git
from redline.plan import ROOT, check_plan, parse_plan
from redline.planaudit import check_plan_audits
from redline.premises import check_premises
from redline.relabel import check_relabel
from redline.runner import check_helpers
from redline.specs import check_specs
from redline.start import TRAILER, Refused, open_step_file, read_steps
from redline.track import check_track


class GitHub:
    """Everything that goes over the network."""

    def __init__(self, repo: Path):
        self.repo = repo

    def run(self, *command: str) -> str:
        done = subprocess.run(command, cwd=self.repo, capture_output=True, encoding="utf-8", errors="replace")
        if done.returncode:
            raise RuntimeError(f"{' '.join(command[:3])}: {done.stderr.strip()}")
        return done.stdout.strip()

    def push(self, branch: str) -> None:
        self.run("git", "push", "-u", "origin", branch)

    def create_pr(self, title: str, body: str) -> str:
        return self.run("gh", "pr", "create", "--title", title, "--body", body)

    def labels(self, number: int) -> dict[str, str]:
        """Each label on the PR, with whoever applied it last."""
        events = self.run("gh", "api", "--paginate", f"repos/{{owner}}/{{repo}}/issues/{number}/events", "--jq",
                          '.[] | select(.event == "labeled" or .event == "unlabeled") | [.event, .label.name, .actor.login] | @tsv')
        applied = {}
        for line in events.splitlines():
            event, label, who = line.split("	")
            if event == "labeled":
                applied[label] = who
            else:
                applied.pop(label, None)
        return applied

    def pulls(self, sha: str) -> list[int]:
        """The merged PRs GitHub associates with the commit."""
        found = self.run("gh", "api", f"repos/{{owner}}/{{repo}}/commits/{sha}/pulls", "--jq",
                         ".[] | select(.merged_at != null) | .number")
        return [int(number) for number in found.split()]

    def role(self, login: str) -> str:
        return self.run("gh", "api", f"repos/{{owner}}/{{repo}}/collaborators/{login}/permission", "--jq", ".role_name")


def size(repo: Path, approvals: Approvals) -> list[str]:
    """check-lines, where more than 400 lines needs an approved `Oversized` claim."""
    count = check_lines(repo)
    if count.total <= LIMIT:
        return []
    over = f"check-lines: {count.total} changed lines, over the limit of {LIMIT}"
    if not claims(repo, count.base, "Oversized"):
        return [over]
    why = approvals.approve(OVERSIZED, over)
    return [why] if why else []


def rigor_claim(repo: Path, approvals: Approvals) -> list[str]:
    """A changed `rigor:` in the config or `Rigor:` line in a plan, a change's level lowered, a glob added to
    the config's `generated:` or `support:`, a deleted plan, or a change taken out of one, needs an approved
    `Redline-Rigor` claim. An unknown level fails whatever the trailer."""
    fork = git(repo, "merge-base", "main", "HEAD").stdout.strip()
    old, new = load_config(repo, fork), load_config(repo)
    changed = [] if old.rigor == new.rigor else [
        f"rigor: `rigor:` in redline/config.yaml changed from {old.rigor} to {new.rigor}"]
    for key in ("generated", "support"):  # each gate reads them at the fork, but they hold for every later PR
        changed += [f"rigor: `{glob}` was added to `{key}:` in redline/config.yaml"
                    for glob in getattr(new, key) if glob not in getattr(old, key)]
    listed = git(repo, "ls-tree", "-r", "--name-only", fork, "--", ROOT).stdout.split()
    for path in (p for p in listed if p.endswith("/plan.md") and p.count("/") == 3):  # a new plan isn't a change
        before = parse_plan("", git(repo, "show", f"{fork}:{path}").stdout)
        now = parse_plan("", (repo / path).read_text(encoding="utf-8")) if (repo / path).is_file() else None
        if before.rigor != (level := now.rigor if now else ""):
            changed.append(f"rigor: the `Rigor:` line of {path} changed from {before.rigor or 'none'} to {level or 'none'}")
        had = [c for phase in before.phases for c in phase.changes]
        if now is None:
            changed.append(f"rigor: {path} was deleted, taking {', '.join(had) or 'no changes'} out of its initiative")
        else:
            kept = {c for phase in now.phases for c in phase.changes}
            changed += [f"rigor: {c} was taken out of {path}" for c in had if c not in kept]
    bad = []
    proposals = git(repo, "ls-tree", "-r", "--name-only", fork, "--", "redline/changes").stdout.split()
    for change in (p.split("/")[2] for p in proposals if p.endswith("/proposal.md") and p.count("/") == 3):
        try:  # a new proposal declares its level; a raise asks more of every gate (§8)
            before, level = rigor(repo, change, fork), rigor(repo, change)
        except RuntimeError as error:
            bad.append(f"rigor: {error}")
            continue
        if LEVELS.index(level) < LEVELS.index(before):
            changed.append(f"rigor: {change}'s level was lowered from {before} to {level}")
    if changed and not claims(repo, fork, "Redline-Rigor"):
        return bad + [f"{what}, with no Redline-Rigor trailer" for what in changed]
    return bad + [why for what in changed if (why := approvals.approve(RIGOR, what))]


def gates(repo: Path, change: str, step: str, approvals: Approvals | None = None) -> list[str]:
    approvals = approvals or Approvals()
    failures = size(repo, approvals) + rigor_claim(repo, approvals)
    failures += [f"check-plan: {bad}" for bad in check_plan(repo).bad + check_plan_audits(repo)]
    failures += [f"check-helpers: {bad}" for bad in check_helpers(repo)]
    failures += [f"check-defects: {bad}" for bad in check_defects(repo, change, step == "C").bad]
    failures += [f"check-relabel: {bad}" for bad in check_relabel(repo, change, step == "C").bad]
    if step == "S":
        failures += [f"check-premises: {bad}" for bad in check_premises(repo, change).bad]
        failures += [f"check-audit: {bad}" for bad in check_audit(repo, change).bad]
    else:
        failures += [f"check-links: {gap}" for gap in check_links(repo).gaps]
        held = set(holds(repo))  # a hold test has no red by design
        failures += [
            f"check-order: {r.scenario}: green {r.green[:7]} has no red commit among its ancestors"
            for r in check_order(repo)
            if r.status == "fail" and r.scenario not in held
        ]
    if step == "R":
        failures += [f"check-break: {sid}: {why}" for sid, why in check_break(repo, change).bad.items()]
    own = step == "R" or step.startswith("G")
    if own:  # at G its new entries need approved departures too
        base = None if step == "R" else "main"
        failures += [f"check-lock: {bad}" for bad in check_lock(repo, change, base, approvals).bad]
    if not step.startswith("G"):  # a frozen test is frozen whichever change locked it, at every step
        failures += [f"check-lock: {bad}" for bad in check_frozen(repo, "main", approvals)]
    for other in sorted(set(read_lock(repo)) - ({change} if own else set())):
        failures += [f"check-lock: {other}: {bad}" for bad in check_lock(repo, other).bad]
    if step.startswith("G"):
        failures += check_track(repo, change, step, approvals)
    if step == "C":  # earlier, a scenario a later step owns has no green yet by design
        for name, check in (("check-close", check_close), ("check-specs", lambda r, c: check_specs(r, c)[0])):
            try:
                failures += [f"{name}: {bad}" for bad in check(repo, change)]
            except RuntimeError as error:
                failures.append(f"{name}: {error}")
    return failures


def stamp(repo: Path, base: str, name: str) -> None:
    """Give every commit since `base` the step's trailer, unless they all have it already."""
    log = git(repo, "log", f"{base}..HEAD", f"--format=%(trailers:key={TRAILER},valueonly,separator=|)")
    if all(name in line.split("|") for line in log.stdout.splitlines()):
        return
    amend = f"git -c trailer.ifexists=addIfDifferent commit -q --amend --no-edit --trailer '{TRAILER}: {name}'"
    done = git(repo, "rebase", "-q", "--exec", amend, base)
    if done.returncode:
        git(repo, "rebase", "--abort")
        raise RuntimeError(f"could not add the {TRAILER} trailer: {done.stderr.strip()}")


def pr(repo: Path, body: str = "") -> tuple[str, list[str]]:
    """Open the PR for the open step; return its URL and the labels CI will need."""
    state = open_step_file(repo)
    name = state.read_text(encoding="utf-8").strip() if state.is_file() else ""
    if not name:
        raise Refused("no step is open; begin one with `redline start <change>/<step>`")
    change, _, step_name = name.partition("/")
    step = next((s for s in read_steps(repo, change) if s.name == step_name), None)
    if step is None:
        raise RuntimeError(f"no step {step_name} in redline/changes/{change}/steps.md")
    base = git(repo, "merge-base", "main", "HEAD").stdout.strip()
    if git(repo, "rev-parse", "HEAD").stdout.strip() == base:
        raise Refused("the branch has no commits of its own to put in a PR")
    if git(repo, "status", "--porcelain").stdout.strip():
        raise Refused("there are uncommitted changes; commit or stash them first")
    approvals = Approvals()
    if failures := gates(repo, change, step_name, approvals):
        raise Refused("the local gates failed:\n" + "\n".join(failures))
    stamp(repo, base, name)
    github = GitHub(repo)
    github.push(git(repo, "branch", "--show-current").stdout.strip())
    url = github.create_pr(f"{name}: {step.goal}", f"{body}\n\n{TRAILER}: {name}\n".lstrip())
    state.unlink()
    return url, approvals.pending
