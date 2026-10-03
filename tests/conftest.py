import pathlib
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

@pytest.fixture
def repo_root():
    return REPO_ROOT

@pytest.fixture
def fixtures_dir():
    return pathlib.Path(__file__).resolve().parent / "fixtures"
