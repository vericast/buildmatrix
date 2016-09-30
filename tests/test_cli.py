from buildmatrix import cli
import pytest
from contextlib import contextmanager
import copy
from os.path import join, sep, dirname
import sys


@pytest.fixture(scope="session")
def argv():
    # Fixture that returns the list of command line arguments that we are going
    # to use to fake up a command line invocation
    return [
        '--python',
        '2.7',
        '3.4',
        '3.5',
        '--numpy',
        '1.10',
        '1.11',
    ]


@contextmanager
def temp_argv(new_argv):
    # Context manager that allows us to temporarily muck with sys.argv so that
    # we can make use of the argparse bits in the cli
    orig = copy.copy(sys.argv)
    sys.argv = ['buildmatrix'] + new_argv
    yield
    sys.argv = orig


def test_numpy_xx_dry_run(argv, examples_dir):
    # Just do a dry run of the numpy package. Does not yet verify that the output
    # is correct. This is a smoke test.
    recipe = join(
        examples_dir,
        'needs-numpy-at-compilation')
    with temp_argv(argv + ['--dry-run', recipe]):
        with pytest.raises(SystemExit) as se:
            cli.cli()
    assert se.value.code == 0


def test_numpy_xx(argv, examples_dir):
    # Actually build the needs-numpy-at-compilation package. Does not verify
    # that the build is doing the right thing, just that it runs to completion.
    # Note that simply running to completion is usually a good sign that things
    # are working as expected
    recipe = join(
        examples_dir,
        'needs-numpy-at-compilation')
    with temp_argv(argv + [recipe]):
        cli.cli()

