import pytest

FAILING = "def test_it():\n    assert 1 + 1 == 3\n"
PASSING = "def test_it():\n    assert 1 + 1 == 2\n"


def write(pytester: pytest.Pytester, marker: str, body: str) -> None:
    pytester.makepyfile(f"import pytest\n\n@pytest.mark.{marker}\n{body}")


def test_new_scenario_that_fails_is_an_expected_failure(pytester):
    write(pytester, 'spec("TOY.S1", new=True)', FAILING)
    result = pytester.runpytest("--strict-markers")
    result.assert_outcomes(xfailed=1)
    assert result.ret == 0


def test_new_scenario_that_already_passes_fails_the_run(pytester):
    write(pytester, 'spec("TOY.S1", new=True)', PASSING)
    result = pytester.runpytest("--strict-markers")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*XPASS(strict)*TOY.S1*"])


def test_strictness_does_not_depend_on_ini(pytester):
    pytester.makeini("[pytest]\nxfail_strict = false\n")
    write(pytester, 'spec("TOY.S1", new=True)', PASSING)
    pytester.runpytest().assert_outcomes(failed=1)


@pytest.mark.parametrize(("body", "outcome"), [(PASSING, "passed"), (FAILING, "failed")])
def test_green_scenario_runs_as_a_normal_test(pytester, body, outcome):
    write(pytester, 'spec("TOY.S1")', body)
    pytester.runpytest("--strict-markers").assert_outcomes(**{outcome: 1})


@pytest.mark.parametrize("marker", ["spec", "spec()", 'spec("A", "B")', "spec(1)", 'spec("A", hold=True)'])
def test_malformed_marker_is_a_usage_error(pytester, marker):
    write(pytester, marker, PASSING)
    result = pytester.runpytest("--strict-markers")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*spec*ID*"])
