"""
Sync engine: writes managed parts of `pyproject.toml` from a project's `pyprojconf.py`.

Managed content:

- A header comment at the top of `pyproject.toml` noting it is managed (in part) by
  pyprojkit
- `project.requires-python`
- Python version classifiers (`Programming Language :: Python :: 3[.X]`);
  other classifiers are left untouched, as are comments in the list
- Individual key/value pairs within tool tables, marked with an inline
  `# pyprojkit-managed` comment; the marker doubles as bookkeeping — a marked field
  dropped from the configuration is deleted on the next sync, and a table emptied
  that way is pruned. All other keys and comments in those tables belong to the
  project and are preserved. (The marker comment is reserved: don't put it on your
  own fields.)

Everything else (dependencies, build-system, urls, unmanaged fields and tables, etc.) is
preserved. Output is normalized with toml-sort (as a library, using the same settings as
the managed `[tool.tomlsort]` table), so a subsequent `toml-sort` run in the format task
is a no-op.

Files synced by pyprojkit < 0.4 (whole-table ownership with a `[tool.pyprojkit]`
bookkeeping table and "managed by pyprojkit" comments) are migrated in one sync.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Any, Iterator

import tomlkit
from tomlkit import TOMLDocument
from tomlkit.items import AoT, Null, Table

from .config.base import ConfigError
from .config.project import ProjectConfig
from .config.tools import TomlSortConfig

__all__ = [
    "compute_managed_fields",
    "render",
    "sync",
]

_CLASSIFIER_RE = re.compile(r"^Programming Language :: Python :: \d+(\.\d+)?$")

_MARKER = "pyprojkit-managed"
_LEGACY_MARKER = "managed by pyprojkit"

_HEADER_LINK = "https://github.com/mm21/pyprojkit"
_HEADER_COMMENT = f"# managed (in part) by pyprojkit: {_HEADER_LINK}"


def compute_managed_fields(config: ProjectConfig) -> dict[str, dict[str, Any]]:
    """
    Compute all managed fields, keyed by dotted table path then key.
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

    return tables


def render(config: ProjectConfig, text: str) -> str:
    """
    Render the synced `pyproject.toml` contents from existing contents.
    """
    doc = tomlkit.parse(_ensure_header(text))

    project = doc.get("project")
    if project is None:
        raise ConfigError("pyproject.toml has no [project] table")

    _update_classifiers(project, config)

    fields = compute_managed_fields(config)
    fields["project"] = {"requires-python": config.python.requires_python}

    # marked fields, plus every field of tables listed in the legacy
    # [tool.pyprojkit].managed bookkeeping (those tables were fully owned)
    marked = _scan_marked_fields(doc) | _scan_legacy_fields(doc)

    for path, key in sorted(marked):
        if key not in fields.get(path, {}):
            _delete_field(doc, path, key)

    _delete_table(doc, "tool.pyprojkit")

    for path, content in fields.items():
        for key, value in content.items():
            _set_field(doc, path, key, value)

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
    In write mode, returns `True` (having updated files as needed).
    """
    root_path = Path(root) if root else Path.cwd()
    path = root_path / "pyproject.toml"
    if not path.is_file():
        raise ConfigError(f"'{path}' not found")

    in_sync = True

    old = path.read_text()
    new = render(config, old)
    if old != new:
        if check:
            _print_diff("pyproject.toml", old, new)
            in_sync = False
        else:
            path.write_text(new)

    return in_sync if check else True


def _print_diff(name: str, old: str, new: str):
    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"{name} (on disk)",
        tofile=f"{name} (synced)",
    )
    print("".join(diff), end="")


def _ensure_header(text: str) -> str:
    """
    Prepend the managed-by header comment if no leading comment already carries it.
    """
    for line in text.splitlines():
        if not line.startswith("#"):
            break
        if _HEADER_LINK in line:
            return text
    return f"{_HEADER_COMMENT}\n\n{text}"


def _update_classifiers(project: Table, config: ProjectConfig):
    """
    Replace python version classifiers with those derived from config, preserving all
    others; result is sorted, with managed entries marked by an inline comment.

    Comments in the existing list are preserved: an inline comment stays with its entry,
    and a standalone comment stays with the entry it precedes (or is emitted at the end
    of the list if it precedes none).
    """
    managed = set(config.python.classifiers)
    existing = project.get("classifiers", [])
    kept = [str(c) for c in existing if not _CLASSIFIER_RE.match(str(c))]
    leading, inline, trailing = _collect_classifier_comments(
        existing, set(kept) | managed
    )

    array = tomlkit.array()
    for entry in sorted(set(kept) | managed):
        for comment in leading.get(entry, []):
            array.add_line(comment=comment, indent="  ")
        array.add_line(
            entry,
            indent="  ",
            comment=_MARKER if entry in managed else inline.get(entry),
        )
    for comment in trailing:
        array.add_line(comment=comment, indent="  ")
    array.add_line(indent="")
    project["classifiers"] = array


def _collect_classifier_comments(
    array: Any, surviving: set[str]
) -> tuple[dict[str, list[str]], dict[str, str], list[str]]:
    """
    Extract comments from an existing classifiers array, anchored to the entries they
    accompany. Comments attached to entries which don't survive the sync are carried
    forward to the next surviving entry.
    """
    leading: dict[str, list[str]] = {}
    inline: dict[str, str] = {}
    pending: list[str] = []

    for group in getattr(array, "_value", []):
        comment = _comment_text(group)
        if comment in (_MARKER, _LEGACY_MARKER):
            comment = None
        if group.value is None or isinstance(group.value, Null):
            # standalone comment line
            if comment:
                pending.append(comment)
            continue

        entry = str(group.value)
        if entry in surviving:
            if pending:
                leading.setdefault(entry, []).extend(pending)
                pending = []
            if comment:
                inline[entry] = comment
        elif comment:
            # entry is going away; keep its comment as a standalone one
            pending.append(comment)

    return leading, inline, pending


def _comment_text(group: Any) -> str | None:
    comment = getattr(group, "comment", None)
    if comment is None:
        return None
    return comment.trivia.comment.lstrip("#").strip() or None


def _walk_tables(doc: TOMLDocument) -> Iterator[tuple[str, Table]]:
    """
    Yield `(dotted_path, table)` for every physical table in the document, including
    out-of-order ones (never yields proxies).
    """

    def walk(container: Any, prefix: str) -> Iterator[tuple[str, Table]]:
        for key, item in container.body:
            if key is None or isinstance(item, AoT):
                continue
            if isinstance(item, Table):
                path = f"{prefix}{key.key}"
                yield path, item
                yield from walk(item.value, f"{path}.")

    yield from walk(doc, "")


def _scan_marked_fields(doc: TOMLDocument) -> set[tuple[str, str]]:
    """
    Find all `(table_path, key)` fields carrying the managed marker comment, and strip
    legacy whole-table marker comments from table headers along the way.
    """
    marked: set[tuple[str, str]] = set()
    for path, table in _walk_tables(doc):
        if _LEGACY_MARKER in table.trivia.comment:
            table.trivia.comment = ""
            table.trivia.comment_ws = ""
        for key, item in table.value.body:
            if key is None or isinstance(item, (Table, AoT)):
                continue
            comment = item.trivia.comment
            if _MARKER in comment or _LEGACY_MARKER in comment:
                marked.add((path, key.key))
    return marked


def _scan_legacy_fields(doc: TOMLDocument) -> set[tuple[str, str]]:
    """
    Treat every field of tables listed in the legacy `[tool.pyprojkit].managed`
    bookkeeping as managed; those tables were fully owned by pyprojkit < 0.4.
    """
    try:
        legacy_paths = list(doc["tool"]["pyprojkit"]["managed"])  # type: ignore[index]
    except (KeyError, TypeError):
        return set()

    tables = {path: table for path, table in _walk_tables(doc)}
    marked: set[tuple[str, str]] = set()
    for path in legacy_paths:
        if path == "tool.pyprojkit" or (table := tables.get(path)) is None:
            continue
        for key, item in table.value.body:
            if key is not None and not isinstance(item, (Table, AoT)):
                marked.add((path, key.key))
    return marked


def _find_table(doc: TOMLDocument, path: str, key: str | None = None) -> Table | None:
    """
    Find the physical table at the given dotted path; with several candidates (split
    super tables), prefer one containing `key`, else the last.
    """
    found: Table | None = None
    for table_path, table in _walk_tables(doc):
        if table_path == path:
            if key is not None and key in table:
                return table
            # prefer a real table over a headerless super table
            if found is None or found.is_super_table():
                found = table
    return found


def _set_field(doc: TOMLDocument, path: str, key: str, value: Any):
    leaf = _find_table(doc, path, key)
    if leaf is None:
        parts = path.split(".")
        container: Any = doc
        for i, part in enumerate(parts):
            if part in container:
                container = container[part]
            else:
                table = tomlkit.table(is_super_table=i < len(parts) - 1)
                container[part] = table
                container = table
        leaf = _find_table(doc, path, key)
        assert leaf is not None

    leaf[key] = _to_item(value)
    leaf.value.item(key).comment(_MARKER)


def _delete_field(doc: TOMLDocument, path: str, key: str):
    table = _find_table(doc, path, key)
    if table is None or key not in table:
        return
    del table[key]
    if len(table) == 0:
        _delete_table(doc, path)


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
