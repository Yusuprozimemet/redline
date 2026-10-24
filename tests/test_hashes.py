"""scripts/hashes.py writes each pin's hashes: the wheels that install on CI's Pythons only (specs/, section 7)."""
import importlib.util
from pathlib import Path

import pytest


FITS = ["a-1.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", "a-1.0-cp312-cp312-win_amd64.whl",
        "a-1.0-cp38-abi3-manylinux_2_28_x86_64.whl", "a-1.0-py3-none-any.whl", "a-1.0-cp312-cp312-manylinux1_x86_64.whl"]
MISFITS = ["a-1.0.tar.gz", "a-1.0-cp312-cp312-macosx_11_0_arm64.whl", "a-1.0-cp311-cp311-manylinux_2_17_x86_64.whl",
           "a-1.0-cp312-cp312-musllinux_1_2_x86_64.whl", "a-1.0-cp312-cp312-manylinux_2_17_aarch64.whl",
           "a-1.0-cp312-cp312-win32.whl", "a-1.0-cp312-cp312-manylinux_2_40_x86_64.whl", "a-1.0-cp313-cp313-win_amd64.whl"]


@pytest.fixture
def hashes():
    spec = importlib.util.spec_from_file_location("hashes", Path(__file__).parent.parent / "scripts/hashes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(filename: str) -> str:
    return f"{abs(hash(filename)):064d}"[-64:]


def pypi(files: list[str]):
    asked = []

    def release(name, version):
        asked.append((name, version))
        return [{"filename": f, "digests": {"sha256": digest(f)}} for f in files]
    release.asked = asked
    return release


def test_a_pin_gets_the_hash_of_each_wheel_for_cpython_3_12_on_linux_x86_64_or_windows_x64_and_nothing_else(hashes):
    release = pypi(MISFITS + FITS)
    text = hashes.rewrite("# pinned\nA==1.0 ; sys_platform != \"win32\"\n", release)
    assert release.asked == [("A", "1.0")]
    lines = [f"    --hash=sha256:{d}" for d in sorted(map(digest, FITS))]
    assert text == "# pinned\nA==1.0 ; sys_platform != \"win32\" \\\n" + " \\\n".join(lines) + "\n"


def test_rewriting_drops_the_old_hashes_and_again_changes_nothing(hashes):
    old = "a==1.0 \\\n    --hash=sha256:" + "0" * 64 + " \\\n    --hash=sha256:" + "1" * 64 + "\nb==2\n"
    text = hashes.rewrite(old, pypi(FITS[:1]))
    assert text == f"a==1.0 \\\n    --hash=sha256:{digest(FITS[0])}\nb==2 \\\n    --hash=sha256:{digest(FITS[0])}\n"
    assert hashes.rewrite(text, pypi(FITS[:1])) == text


def test_a_pin_no_wheel_fits_fails_naming_it(hashes):
    with pytest.raises(ValueError, match="no wheel for CI's Pythons: a==1.0"):
        hashes.rewrite("a==1.0\n", pypi(MISFITS))


@pytest.mark.parametrize("line", ["a>=1.0", "a", "-e .", "a==1.0 --hash=md5:00"])
def test_a_line_that_is_neither_a_pin_nor_a_comment_fails(hashes, line):
    with pytest.raises(ValueError, match="not a pin"):
        hashes.rewrite(line + "\n", pypi(FITS))
