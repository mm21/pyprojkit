"""
Sync engine: writes managed parts of `pyproject.toml` from a project's `pyprojconf.py`.

Managed content:

- `project.requires-python`
- Python version classifiers (`Programming Language :: Python :: 3[.X]`);
  other classifiers are left untouched
- One `[tool.X]` table per enabled tool (fully owned — any hand edits or
  comments inside are overwritten)
- `[tool.pyprojkit].managed`: bookkeeping list of owned tables, enabling safe
  removal of tables for tools dropped from the configuration

Everything else (dependencies, build-system, urls, unmanaged tool tables,
etc.) is preserved. Output is normalized with toml-sort (as a library, using
the same settings as the managed `[tool.tomlsort]` table), so a subsequent
`toml-sort` run in the format task is a no-op.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Any, cast

import tomlkit
from tomlkit import TOMLDocument
from tomlkit.items import Table

from .config.base import ConfigError
from .config.project import ProjectConfig
from .config.tools import TomlSortConfig

__all__ = [
    "compute_managed_tables",
    "render",
    "sync",
]

_CLASSIFIER_RE = re.compile(r"^Programming Language :: Python :: \d+(\.\d+)?$")

_MANAGED_COMMENT = "managed by pyprojkit"


def compute_managed_tables(config: ProjectConfig) -> dict[str, dict[str, Any]]:
    """
    Compute contents of all managed tables, keyed by dotted table path.
    """
    tables: dict[str, dict[str, Any]] = {}
    tools = config.tools

    for formatter in tools.formatting.formatters:
        tables[formatter.table_path] = formatter.to_toml(config)

    if test := tools.test:
        for tool in (test.pytest, test.coverage_run, test.coverage_report):
            tables[tool.table_path] = tool.to_toml(config)

    tables[tools.doit.table_path] = tools.doit.to_toml(config)
    tables[tools.nox.table_path] = tools.nox.to_toml(config)

    if (analysis := tools.analysis) and analysis.mypy:
        tables[analysis.mypy.table_path] = analysis.mypy.to_toml(config)

    # merge escape-hatch overrides last; unknown paths become managed tables
    for path, overrides in tools.tool_overrides.items():
        tables.setdefault(path, {}).update(overrides)

    return tables


def render(config: ProjectConfig, text: str) -> str:
    """
    Render the synced `pyproject.toml` contents from existing contents.
    """
    doc = tomlkit.parse(text)

    project = doc.get("project")
    if project is None:
        raise ConfigError("pyproject.toml has no [project] table")

    project["requires-python"] = config.python.requires_python
    project["requires-python"].comment(_MANAGED_COMMENT)
    _update_classifiers(project, config)

    tables = compute_managed_tables(config)

    prev_managed = _get_managed_list(doc)
    for path in prev_managed:
        if path not in tables:
            _delete_table(doc, path)

    for path, content in tables.items():
        _set_table(doc, path, content)

    _set_table(doc, "tool.pyprojkit", {"managed": sorted(tables)})

    return _normalize(config, tomlkit.dumps(doc))


def sync(
    config: ProjectConfig,
    root: Path | str | None = None,
    *,
    check: bool = False,
) -> bool:
    """
    Sync `pyproject.toml` under the given project root (defaulting to the current
    directory).

    In check mode, nothing is written; prints a diff and returns `False` if out of sync.
    In write mode, returns `True` (having updated the file if needed).
    """
    path = (Path(root) if root else Path.cwd()) / "pyproject.toml"
    if not path.is_file():
        raise ConfigError(f"'{path}' not found")

    old = path.read_text()
    new = render(config, old)

    if old == new:
        return True

    if check:
        diff = difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile="pyproject.toml (on disk)",
            tofile="pyproject.toml (synced)",
        )
        print("".join(diff), end="")
        return False

    path.write_text(new)
    return True


def _update_classifiers(project: Table, config: ProjectConfig):
    """
    Replace python version classifiers with those derived from config, preserving all
    others; result is sorted, with managed entries marked by an inline comment.
    """
    existing = cast(list[str], [str(c) for c in project.get("classifiers", [])])
    kept = [c for c in existing if not _CLASSIFIER_RE.match(c)]
    managed = set(config.python.classifiers)

    array = tomlkit.array()
    for entry in sorted(set(kept) | managed):
        array.add_line(
            entry,
            indent="  ",
            comment=_MANAGED_COMMENT if entry in managed else None,
        )
    array.add_line(indent="")
    project["classifiers"] = array


def _get_managed_list(doc: TOMLDocument) -> list[str]:
    try:
        return list(doc["tool"]["pyprojkit"]["managed"])  # type: ignore[index]
    except (KeyError, TypeError):
        return []


def _set_table(doc: TOMLDocument, path: str, content: dict[str, Any]):
    parts = path.split(".")
    container: Any = doc
    for part in parts[:-1]:
        if part in container:
            container = container[part]
        else:
            table = tomlkit.table(is_super_table=True)
            container[part] = table
            container = table

    leaf = tomlkit.table()
    leaf.comment(_MANAGED_COMMENT)
    for key, value in content.items():
        leaf[key] = _to_item(value)
    container[parts[-1]] = leaf


def _delete_table(doc: TOMLDocument, path: str):
    parts = path.split(".")

    # walk to leaf's parent
    containers: list[Any] = [doc]
    for part in parts[:-1]:
        container = containers[-1].get(part)
        if container is None:
            return
        containers.append(container)

    if parts[-1] not in containers[-1]:
        return
    del containers[-1][parts[-1]]

    # prune emptied parents (but never the document itself)
    for i in range(len(containers) - 1, 0, -1):
        if len(containers[i]) == 0:
            del containers[i - 1][parts[i - 1]]


def _to_item(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        array = tomlkit.array()
        array.extend(value)
        if len(array) >= 2:
            array.multiline(True)
        return array
    return value


def _normalize(config: ProjectConfig, text: str) -> str:
    """
    Normalize with toml-sort as a library, driven by the project's `TomlSortConfig`
    (skipped if toml-sort is not among the formatters).
    """
    tomlsort_config = next(
        (
            f
            for f in config.tools.formatting.formatters
            if isinstance(f, TomlSortConfig)
        ),
        None,
    )
    if tomlsort_config is None:
        return text

    from toml_sort import TomlSort
    from toml_sort.tomlsort import FormattingConfiguration, SortConfiguration

    sort_config = SortConfiguration(
        table_keys=bool(tomlsort_config.sort_table_keys),
        first=list(tomlsort_config.sort_first or []),
    )
    format_config = FormattingConfiguration(
        spaces_before_inline_comment=tomlsort_config.spaces_before_inline_comment or 1,
    )
    return TomlSort(
        input_toml=text, sort_config=sort_config, format_config=format_config
    ).sorted()
