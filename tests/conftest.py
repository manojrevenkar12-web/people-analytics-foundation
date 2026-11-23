import pytest

from paf.lab import simulate


@pytest.fixture(scope="session")
def W():  # type: ignore[no-untyped-def]
    return simulate.world("dev", 21)


@pytest.fixture(scope="session")
def cfg() -> dict:
    return simulate.load("platform")
