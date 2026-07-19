from pathlib import Path

import nox.registry
import pytest

from pyprojkit import ConfigError, NoxFactory


@pytest.fixture(autouse=True)
def clean_registry():
    nox.registry._REGISTRY.clear()
    yield
    nox.registry._REGISTRY.clear()


def test_test_session(project: Path):
    factory = NoxFactory()
    session = factory.create_test_session()

    registry = nox.registry.get()
    assert "test" in registry
    func = registry["test"]
    assert func.python == ["3.12.13", "3.13.13"]
    assert session is not None

    # double registration guarded
    with pytest.raises(ConfigError, match="already created"):
        factory.create_test_session()


def test_envdir(project: Path):
    NoxFactory()
    assert nox.options.envdir == "__cache__/nox"
