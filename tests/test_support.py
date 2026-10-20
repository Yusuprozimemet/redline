import pytest

from redline.config import load_config
from test_check_break import holds  # noqa: F401 (a fixture)
from test_lock import check_lock, lock
from test_start import change  # noqa: F401 (a fixture)
from test_timing import REACHED, critical  # noqa: F401 (critical is a fixture)

SUPPORTED = """import pytest
import helpers
from helpers import wait as wait_for
from support.fixtures import ready
from greet import placeholder

@pytest.mark.spec("GREET.H1")
def test_h1(ready):
    assert wait_for() and helpers.POLLS
    assert placeholder() is None

@pytest.mark.spec("GREET.H2")
def test_h2():
    assert True

@pytest.mark.spec("GREET.H3")
def test_h3():
    assert placeholder() is None
"""
SUPPORT = {
    "test_hold.py": SUPPORTED,
    "helpers.py": "from support.timing import TIMEOUT\n\nPOLLS = 50\n\ndef wait():\n    return TIMEOUT\n\ndef unrelated():\n    return 1\n",
    "support/__init__.py": "",
    "support/timing.py": "TIMEOUT = 5\nSTEP = 0.1\n",
    "support/fixtures.py": "import pytest\nfrom .timing import STEP\n\n@pytest.fixture\ndef ready():\n    return STEP\n",
}
CONFIG = 'support:\n  - "helpers.py"\n  - "support/*.py"\n'


@pytest.fixture
def supported(critical):
    critical.commit("support files", {**SUPPORT, "redline/config.yaml": CONFIG})
    return critical


@pytest.mark.parametrize("path, old, new", [
    ("helpers.py", "return TIMEOUT", "return TIMEOUT * 2"),  # a helper imported under another name
    ("helpers.py", "POLLS = 50", "POLLS = 500"),  # `import helpers`, then helpers.POLLS
    ("support/timing.py", "TIMEOUT = 5", "TIMEOUT = 50"),  # a support file's own import
    ("support/timing.py", "STEP = 0.1", "STEP = 1"),  # a relative import
    ("support/fixtures.py", "return STEP", "return STEP * 10"),  # a fixture imported into the test's file
])
def test_a_critical_reach_follows_imports_into_support_files(supported, capsys, path, old, new):
    lock(supported, capsys)
    supported.commit("wait longer", {path: SUPPORT[path].replace(old, new)})
    assert REACHED in check_lock(supported, capsys)[1].splitlines()


def test_an_import_from_a_file_support_doesnt_name_isnt_followed(supported, capsys):
    lock(supported, capsys)
    supported.commit("elsewhere", {
        "greet.py": "def placeholder():\n    return None\n",  # the code under test
        "helpers.py": SUPPORT["helpers.py"].replace("return 1", "return 2"),  # a support name nothing reads
    })
    assert check_lock(supported, capsys) == (0, "ok: 3 locked test(s) match the code\n")


def test_without_support_files_the_reach_is_what_it_was_and_naming_one_changes_it(critical, capsys):
    critical.commit("support files", SUPPORT)
    lock(critical, capsys)
    critical.commit("wait longer", {"helpers.py": SUPPORT["helpers.py"].replace("POLLS = 50", "POLLS = 500")})
    assert check_lock(critical, capsys) == (0, "ok: 3 locked test(s) match the code\n")
    critical.commit("name the support files", {"redline/config.yaml": CONFIG})
    assert REACHED in check_lock(critical, capsys)[1].splitlines()


def test_support_globs_are_read_from_the_config(supported):
    assert load_config(supported.path).support == ["helpers.py", "support/*.py"]
