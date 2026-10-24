"""Redline's own checkout passes check-links and check-order, as every step from R on runs them. check-order
reads the whole history, so the tests are skipped in a shallow clone. See specs/, §5 and O-SELF5."""

import subprocess
from pathlib import Path

import pytest

from redline import order
from redline.breaks import holds
from redline.links import check_links
from redline.order import check_order, git

ROOT = Path(__file__).parent.parent
TOY = "tests/toys/jest/src/adult.test.js"


def shallow() -> bool:
    return git(ROOT, "rev-parse", "--is-shallow-repository").stdout.strip() != "false"


@pytest.mark.skipif(shallow(), reason="check-order reads the whole history, which a shallow clone lacks")
def test_redlines_own_checkout_passes_check_links_and_check_order():
    assert check_links(ROOT).gaps == []
    assert order.failed(check_order(ROOT), set(holds(ROOT))) == []


def test_the_toys_test_file_is_written_by_its_tests_not_committed():
    assert git(ROOT, "ls-files", "--", TOY).stdout == ""
    ignored = subprocess.run(["git", "check-ignore", "-q", "--no-index", TOY], cwd=ROOT)
    assert ignored.returncode == 0, f"{TOY} isn't ignored, so check-links would read it when a test writes it"
