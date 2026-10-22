"""The real `gh api` calls the `GitHub` seam makes, on this repository's own merged PR (docs/design.md, §7).

The suite reads GitHub through fakes and canned answers; these read GitHub itself, so a renamed field, a jq
path that selects nothing, a ref the activity API reads another way or a time `moment` can't parse fails here.
They run in the runners CI job, with the redline job's read permissions, and are skipped without
REDLINE_REAL_GITHUB, so GitHub being down fails that job and never the gates.
"""

import os
from pathlib import Path

import pytest

from redline.approval import MAINTAINER, moment
from redline.pr import GitHub

pytestmark = pytest.mark.skipif(os.environ.get("REDLINE_REAL_GITHUB") != "1",
                                reason="the real gh api calls run in the runners CI job")

ROOT = Path(__file__).resolve().parent.parent
PR, HEAD, AUTHOR = 60, "726bf21a9d05ddd70133250a72a8b3cba763bbc3", "Yusuprozimemet"
CREATED = "2026-10-22T14:06:29Z"  # its branch's creation pushed the head; nothing pushed it again


@pytest.fixture
def github():
    return GitHub(ROOT)


def test_the_merged_pr_of_a_commit_is_read_from_github(github):
    assert github.pulls(HEAD) == [PR]


def test_the_heads_push_is_read_from_the_activity_api(github):
    assert github.pushed(PR) == (HEAD, CREATED)
    assert moment(CREATED).tzinfo is not None


def test_the_label_still_on_the_pr_is_read_with_who_applied_it_and_when(github):
    # documentation was applied and removed, enhancement applied, after the PR merged
    applied = github.labels(PR)
    assert set(applied) == {"enhancement"}, applied
    who, at = applied["enhancement"]
    assert who == AUTHOR
    assert moment(at) > moment(CREATED)


def test_a_role_is_read_from_github(github):
    assert github.role(AUTHOR) in MAINTAINER


def test_paginate_joins_every_page_line_by_line(github):
    events = f"repos/{{owner}}/{{repo}}/issues/{PR}/events"
    jq = ".[] | [.event, .created_at] | @tsv"
    whole = github.run("gh", "api", f"{events}?per_page=100", "--jq", jq)
    assert len(whole.splitlines()) >= 3, whole
    assert github.run("gh", "api", "--paginate", f"{events}?per_page=1", "--jq", jq) == whole
