import pathlib
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

@pytest.fixture
def repo_root():
    return REPO_ROOT

@pytest.fixture
def fixtures_dir():
    return pathlib.Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def _no_nominatim(monkeypatch):
    """The suite never asks the real Nominatim (CI is meant to need no network, and the
    service allows one request a second). A test that reaches it unmocked fails here,
    naming the query -- v1.2.1 added a country-code request, and a fixture that missed
    it went online silently. A test that mocks requests.get replaces this guard."""
    import requests
    real = requests.get

    def guarded(url, *a, **kw):
        if "nominatim" in str(url):
            raise AssertionError(f"unmocked Nominatim request in a test: {kw.get('params')}")
        return real(url, *a, **kw)
    monkeypatch.setattr(requests, "get", guarded)
