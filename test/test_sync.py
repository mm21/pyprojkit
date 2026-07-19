from dataclasses import replace
from pathlib import Path

import pytest
import tomlkit

from pyprojkit import FormattingConfig, ProjectConfig, sync
from pyprojkit.cli import main
from pyprojkit.config.tools import BlackConfig, TomlSortConfig
from pyprojkit.sync import render


def test_render_managed_content(project: Path, config: ProjectConfig):
    text = (project / "pyproject.toml").read_text()
    new = render(config, text)
    doc = tomlkit.parse(new)

    # requires-python and classifiers
    assert doc["project"]["requires-python"] == ">=3.12,<3.14"
    classifiers = list(doc["project"]["classifiers"])
    assert "Programming Language :: Python :: 3.12" in classifiers
    assert "Programming Language :: Python :: 3.13" in classifiers
    assert "Programming Language :: Python :: 3.11" not in classifiers
    # non-version classifiers preserved
    assert "Development Status :: 3 - Alpha" in classifiers
    assert "Typing :: Typed" in classifiers

    # managed tool tables
    tool = doc["tool"]
    assert tool["black"]["target-version"] == ["py312", "py313"]
    assert tool["pytest"]["ini_options"]["testpaths"] == "test"
    assert tool["coverage"]["run"]["data_file"] == "__cache__/.coverage"
    assert tool["doit"]["dep_file"] == "__cache__/.doit.db"
    assert tool["nox"]["default_venv_backend"] == "uv"

    # bookkeeping
    assert "tool.black" in tool["pyprojkit"]["managed"]

    # foreign content preserved
    assert tool["custom"]["keep"] is True
    assert list(doc["project"]["dependencies"]) == ["requests>=2,<3"]


def test_managed_comments(project: Path, config: ProjectConfig):
    sync(config, project)
    text = (project / "pyproject.toml").read_text()

    # managed tables, requires-python, and version classifiers are marked
    assert "[tool.black]  # managed by pyprojkit" in text
    assert "[tool.pyprojkit]  # managed by pyprojkit" in text
    assert 'requires-python = ">=3.12,<3.14"  # managed by pyprojkit' in text
    assert '"Programming Language :: Python :: 3.12",  # managed by pyprojkit' in text

    # unmanaged content is not marked
    for line in text.splitlines():
        if "Development Status" in line or "[tool.custom]" in line:
            assert "managed by pyprojkit" not in line


def test_idempotent(project: Path, config: ProjectConfig):
    text = (project / "pyproject.toml").read_text()
    once = render(config, text)
    twice = render(config, once)
    assert once == twice


def test_sync_write_and_check(project: Path, config: ProjectConfig):
    # out of sync initially
    assert sync(config, project, check=True) is False

    # write, then in sync
    assert sync(config, project) is True
    assert sync(config, project, check=True) is True


def test_purge_dropped_tool(project: Path, config: ProjectConfig):
    sync(config, project)
    doc = tomlkit.parse((project / "pyproject.toml").read_text())
    assert "docformatter" in doc["tool"]

    # drop all formatters except black and toml-sort
    slim = replace(
        config,
        tools=replace(
            config.tools,
            formatting=FormattingConfig(formatters=(BlackConfig(), TomlSortConfig())),
        ),
    )
    sync(slim, project)

    doc = tomlkit.parse((project / "pyproject.toml").read_text())
    assert "docformatter" not in doc["tool"]
    assert "autoflake" not in doc["tool"]
    assert "isort" not in doc["tool"]
    assert "black" in doc["tool"]
    # foreign table survives purge
    assert doc["tool"]["custom"]["keep"] is True


def test_purge_prunes_empty_parents(project: Path, config: ProjectConfig):
    sync(config, project)

    # disable testing -> pytest/coverage tables removed entirely
    no_test = replace(config, tools=replace(config.tools, test=None))
    sync(no_test, project)

    doc = tomlkit.parse((project / "pyproject.toml").read_text())
    assert "pytest" not in doc["tool"]
    assert "coverage" not in doc["tool"]


def test_tool_overrides(project: Path, config: ProjectConfig):
    tweaked = replace(
        config,
        tools=replace(
            config.tools,
            tool_overrides={
                "tool.pytest.ini_options": {"addopts": "-x"},
                "tool.pyright": {"typeCheckingMode": "strict"},
            },
        ),
    )
    sync(tweaked, project)

    doc = tomlkit.parse((project / "pyproject.toml").read_text())
    assert doc["tool"]["pytest"]["ini_options"]["addopts"] == "-x"
    assert doc["tool"]["pyright"]["typeCheckingMode"] == "strict"
    assert "tool.pyright" in doc["tool"]["pyprojkit"]["managed"]


def test_cli(project: Path):
    assert main(["sync", "--check"]) == 1
    assert main(["sync"]) == 0
    assert main(["sync", "--check"]) == 0


def test_cli_no_conf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    assert main(["sync"]) == 2
