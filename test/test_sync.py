import contextlib
import io
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import tomlkit
from tomlkit.items import Array, Table

from pyprojkit import FormattingConfig, ProjectConfig, sync
from pyprojkit.cli import main
from pyprojkit.config.tools import BlackConfig, TomlSortConfig
from pyprojkit.sync import render

HEADER = "# managed (in part) by pyprojkit: https://github.com/mm21/pyprojkit"


def test_render_managed_content(project: Path, config: ProjectConfig):
    text = (project / "pyproject.toml").read_text()
    new = render(config, text)
    doc = tomlkit.parse(new)

    # requires-python and classifiers
    project_table = _get_table(doc, "project")
    assert project_table["requires-python"] == ">=3.12,<3.14"
    classifiers_item = project_table["classifiers"]
    assert isinstance(classifiers_item, Array)
    classifiers = list(classifiers_item)
    assert "Programming Language :: Python :: 3.12" in classifiers
    assert "Programming Language :: Python :: 3.13" in classifiers
    assert "Programming Language :: Python :: 3.11" not in classifiers
    # non-version classifiers preserved
    assert "Development Status :: 3 - Alpha" in classifiers
    assert "Typing :: Typed" in classifiers

    # managed fields
    assert _get_table(doc, "tool.black")["target-version"] == ["py312", "py313"]
    assert _get_table(doc, "tool.pytest.ini_options")["testpaths"] == "test"
    assert _get_table(doc, "tool.coverage.run")["data_file"] == "__cache__/.coverage"
    assert _get_table(doc, "tool.doit")["dep_file"] == "__cache__/.doit.db"
    assert _get_table(doc, "tool.nox")["default_venv_backend"] == "uv"

    # no bookkeeping table
    assert "pyprojkit" not in _get_table(doc, "tool")

    # foreign content preserved
    assert _get_table(doc, "tool.custom")["keep"] is True
    dependencies = project_table["dependencies"]
    assert isinstance(dependencies, Array)
    assert list(dependencies) == ["requests>=2,<3"]


def test_managed_comments(project: Path, config: ProjectConfig):
    sync(config, project)
    text = (project / "pyproject.toml").read_text()

    # header comment at the top
    assert text.startswith(HEADER + "\n")

    # managed fields, requires-python, and version classifiers are marked
    assert 'requires-python = ">=3.12,<3.14"  # pyprojkit-managed' in text
    assert '"Programming Language :: Python :: 3.12",  # pyprojkit-managed' in text
    assert 'testpaths = "test"  # pyprojkit-managed' in text
    assert "quiet = true  # pyprojkit-managed" in text

    # tables are no longer marked as a whole
    assert "[tool.black]  #" not in text
    assert "managed by pyprojkit" not in text

    # unmanaged content is not marked
    for line in text.splitlines():
        if "Development Status" in line or "[tool.custom]" in line:
            assert "pyprojkit" not in line


def test_header_comment(project: Path, config: ProjectConfig):
    text = (project / "pyproject.toml").read_text()
    once = render(config, text)
    twice = render(config, once)
    assert once.count(HEADER) == 1
    assert twice.count(HEADER) == 1


def test_classifier_comments_preserved(config: ProjectConfig):
    text = """\
[project]
classifiers = [
  # Get the list of trove classifiers here: https://pypi.org/classifiers/
  "Development Status :: 3 - Alpha",
  "Programming Language :: Python :: 3.11",  # managed by pyprojkit
  # about cpython
  "Programming Language :: Python :: Implementation :: CPython",
  "Typing :: Typed"  # we ship py.typed
]
name = "fixture-pkg"
version = "0.1.0"
"""
    new = render(config, text)

    assert (
        "  # Get the list of trove classifiers here: https://pypi.org/classifiers/\n"
        '  "Development Status :: 3 - Alpha",' in new
    )
    assert (
        "  # about cpython\n"
        '  "Programming Language :: Python :: Implementation :: CPython",' in new
    )
    assert '"Typing :: Typed"  # we ship py.typed' in new

    # dropped version classifier takes its (legacy) managed marker with it
    assert "3.11" not in new
    assert "managed by pyprojkit" not in new
    assert render(config, new) == new


def test_idempotent(project: Path, config: ProjectConfig):
    text = (project / "pyproject.toml").read_text()
    once = render(config, text)
    twice = render(config, once)
    assert once == twice


def test_field_preservation(project: Path, config: ProjectConfig):
    sync(config, project)
    path = project / "pyproject.toml"

    # add a user-managed field with a comment inside a managed table
    text = path.read_text().replace(
        "[tool.black]",
        '[tool.black]\nextend-exclude = "generated"  # ours',
    )
    path.write_text(text)
    sync(config, project)

    text = path.read_text()
    assert 'extend-exclude = "generated"  # ours' in text
    doc = tomlkit.parse(text)
    black = _get_table(doc, "tool.black")
    assert black["quiet"] is True
    assert black["target-version"] == ["py312", "py313"]


def test_migration_legacy_format(config: ProjectConfig):
    legacy = """\
[project]
classifiers = [
  "Development Status :: 3 - Alpha",
  "Programming Language :: Python :: 3.11"  # managed by pyprojkit
]
name = "fixture-pkg"
requires-python = ">=3.11"  # managed by pyprojkit
version = "0.1.0"

[tool.black]  # managed by pyprojkit
preview = true
quiet = true
target-version = ["py311"]

[tool.custom]
keep = true

[tool.pyprojkit]  # managed by pyprojkit
managed = ["tool.black", "tool.docfmt", "tool.pyprojkit"]
"""
    new = render(config, legacy)

    assert "managed by pyprojkit" not in new
    doc = tomlkit.parse(new)
    tool = _get_table(doc, "tool")
    assert "pyprojkit" not in tool
    # legacy tables were fully owned: fields not in config are purged
    black = _get_table(doc, "tool.black")
    assert "preview" not in black
    assert black["target-version"] == ["py312", "py313"]
    assert _get_table(doc, "tool.custom")["keep"] is True

    assert render(config, new) == new


def test_out_of_order_tables(config: ProjectConfig):
    text = """\
[project]
name = "fixture-pkg"
version = "0.1.0"

[tool.black]
quiet = false

[tool.custom]
keep = true

[tool.black.extra]
foo = 1
"""
    new = render(config, text)

    assert "quiet = true  # pyprojkit-managed" in new
    doc = tomlkit.parse(new)
    assert _get_table(doc, "tool.custom")["keep"] is True
    assert _get_table(doc, "tool.black.extra")["foo"] == 1
    assert render(config, new) == new


def test_sync_write_and_check(project: Path, config: ProjectConfig):
    # out of sync initially
    with _quiet():
        assert sync(config, project, check=True) is False

    # write, then in sync
    assert sync(config, project) is True
    assert sync(config, project, check=True) is True


def test_purge_dropped_tool(project: Path, config: ProjectConfig):
    sync(config, project)
    doc = tomlkit.parse((project / "pyproject.toml").read_text())
    assert "docfmt" in _get_table(doc, "tool")

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
    tool = _get_table(doc, "tool")
    assert "docfmt" not in tool
    assert "autoflake" not in tool
    assert "isort" not in tool
    assert "black" in tool
    # foreign table survives purge
    assert _get_table(doc, "tool.custom")["keep"] is True


def test_purge_prunes_empty_parents(project: Path, config: ProjectConfig):
    sync(config, project)

    # disable testing -> pytest/coverage tables removed entirely
    no_test = replace(config, tools=replace(config.tools, test=None))
    sync(no_test, project)

    doc = tomlkit.parse((project / "pyproject.toml").read_text())
    tool = _get_table(doc, "tool")
    assert "pytest" not in tool
    assert "coverage" not in tool


def test_purge_keeps_user_fields(project: Path, config: ProjectConfig):
    sync(config, project)
    path = project / "pyproject.toml"

    # user field inside a managed table survives purge of the managed fields
    path.write_text(
        path.read_text().replace(
            "[tool.pytest.ini_options]",
            '[tool.pytest.ini_options]\nmarkers = ["slow"]',
        )
    )
    no_test = replace(config, tools=replace(config.tools, test=None))
    sync(no_test, project)

    doc = tomlkit.parse(path.read_text())
    pytest_table = _get_table(doc, "tool.pytest.ini_options")
    markers = pytest_table["markers"]
    assert isinstance(markers, Array)
    assert list(markers) == ["slow"]
    assert "addopts" not in pytest_table
    # empty foreign table is never pruned
    assert "coverage" not in _get_table(doc, "tool")


def test_cli(project: Path):
    with _quiet():
        assert main(["sync", "--check"]) == 1
    assert main(["sync"]) == 0
    assert main(["sync", "--check"]) == 0


def test_cli_no_conf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    with _quiet():
        assert main(["sync"]) == 2


@contextlib.contextmanager
def _quiet() -> Iterator[None]:
    """
    Suppress stdout/stderr since pytest runs with capture disabled (-s).
    """
    with (
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(io.StringIO()),
    ):
        yield


def _get_table(doc: tomlkit.TOMLDocument, path: str) -> Table:
    item: Any = doc
    for key in path.split("."):
        item = item[key]
    assert isinstance(item, Table)
    return item
