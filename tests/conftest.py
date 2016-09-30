import pytest
from os.path import join, dirname


@pytest.fixture(scope="session")
def examples_dir():
    # fixture that returns the path to the folder that contains the example
    # conda recipes that are used in the test suite
    return join(dirname(__file__), 'example-recipes')
