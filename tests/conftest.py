import pytest
from os.path import join, dirname


@pytest.fixture(scope="session")
def examples_dir():
    return join(dirname(__file__), 'example-recipes')
