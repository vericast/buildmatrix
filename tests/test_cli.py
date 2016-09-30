from buildmatrix import cli
import pytest
from contextlib import contextmanager
import copy
from os.path import join, sep, dirname
import sys


@pytest.fixture(scope="session")
def argv():
    return [
        '--python',
        '2.7',
        '3.4',
        '3.5',
        '--numpy',
        '1.10',
        '1.11',
        '-c',
        'anaconda',
    ]


@contextmanager
def temp_argv(new_argv):
    orig = copy.copy(sys.argv)
    sys.argv = ['buildmatrix'] + new_argv
    yield
    sys.argv = orig


def test_numpy_xx_dry_run(argv):
    recipe = join(
        dirname(__file__),
        'example-recipes',
        'compiles-against-numpy')
    with temp_argv(argv + ['--dry-run', recipe]):
        with pytest.raises(SystemExit) as se:
            cli.cli()
    assert se.value.code == 0


def test_numpy_xx(argv):
    recipe = join(
        dirname(__file__),
        'example-recipes',
        'compiles-against-numpy')
    with temp_argv(argv + [recipe]):
        cli.cli()

