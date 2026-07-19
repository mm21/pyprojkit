from pathlib import Path

import pytest

from pyprojkit import ProjectConfig, PythonVersions

PYPROJECT = """\
[project]
classifiers = [
  "Development Status :: 3 - Alpha",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.11",
  "Typing :: Typed"
]
dependencies = [
  "requests>=2,<3"
]
description = "Fixture package"
name = "fixture-pkg"
requires-python = ">=3.11"
version = "0.1.0"

[build-system]
build-backend = "uv_build"
requires = ["uv_build>=0.11.6,<0.12.0"]

[tool.custom]
keep = true
"""

PYPROJCONF = """\
from pyprojkit import ProjectConfig, PythonVersions

config = ProjectConfig(package="fixture_pkg", python=PythonVersions(3, (12, 13)))
"""


@pytest.fixture
def config() -> ProjectConfig:
    return ProjectConfig(package="fixture_pkg", python=PythonVersions(3, (12, 13)))


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Minimal fixture project with pyproject.toml and pyprojconf.py; cwd is set to it.
    """
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    (tmp_path / "pyprojconf.py").write_text(PYPROJCONF)
    (tmp_path / "src" / "fixture_pkg").mkdir(parents=True)
    (tmp_path / "src" / "fixture_pkg" / "__init__.py").write_text("")
    (tmp_path / "test").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path
