"""
Sync engine: writes managed parts of `pyproject.toml` (and the generated agent skill)
from a project's `pyprojconf.py`.

Managed content:

- A header comment at the top of `pyproject.toml` noting it is managed (in part) by
  pyprojkit
- `project.requires-python`
- Python version classifiers (`Programming Language :: Python :: 3[.X]`) and, if the
  project is typed, `Typing :: Typed`; managed classifiers are marked with an inline
  `# pyprojkit-managed` comment and removed when dropped from the configuration. Other
  classifiers are left untouched, as are comments in the list
- An empty `py.typed` file in each package directory, if the project is typed; created
  if missing, but never removed
- A `.python-version` file at the project root pinning the newest pinned version's exact
  patch release (as used for nox), if enabled; overwritten when out of date, but never removed
- `build-system.build-backend` and `build-system.requires`, if enabled; updated to the
  installed uv's build backend only when it's newer than the required range
- Individual key/value pairs within tool tables, marked with an inline
  `# pyprojkit-managed` comment; the marker doubles as bookkeeping — a marked field
  dropped from the configuration is deleted on the next sync, and a table emptied
  that way is pruned. All other keys and comments in those tables belong to the
  project and are preserved.

Fields which are only updated when out of date, such as those of the uv build backend,
are instead marked with an inline `# pyprojkit-tracked` comment; when dropped from the
configuration, the marker is stripped and the field is kept. (All `# pyprojkit-*`
comments are reserved: don't put them on your own fields.)
- The generated `pyprojkit-python` agent skill under
  `<skills_dir>/pyprojkit-python/SKILL.md`, overwritten on every sync and removed when
  dropped from the configuration

On every non-check sync, the lock file is refreshed via the configured workflow tool
(`uv lock` or `poetry lock`), so manual edits to `pyproject.toml` are picked up too.
Skipped when no workflow tool is configured.

Everything else (dependencies, build-system unless enabled as above, urls, unmanaged
fields and tables, etc.) is preserved. Output is normalized with toml-sort (as a
library, using the same settings as the managed `[tool.tomlsort]` table), so a
subsequent `toml-sort` run in the format task is a no-op.

Files synced by pyprojkit < 0.4 (whole-table ownership with a `[tool.pyprojkit]`
bookkeeping table and "managed by pyprojkit" comments) are migrated in one sync.
"""

from __future__ import annotations

import contextlib
import difflib
import re
import subprocess
from pathlib import Path
from typing import Any, Iterator

import tomlkit
from tomlkit import TOMLDocument
from tomlkit.items import AoT, Null, Table

from ._run import run
from .config.base import BaseToolConfig, ConfigError
from .config.project import ProjectConfig, SkillConfig
from .config.tools import TomlSortConfig
from .skill import SKILL_NAME, render_skill

__all__ = [
    "compute_managed_fields",
    "render",
    "sync",
]

_CLASSIFIER_RE = re.compile(r"^Programming Language :: Python :: \d+(\.\d+)?$")
_TYPED_CLASSIFIER = "Typing :: Typed"

_MARKER = "pyprojkit-managed"
_TRACKED_MARKER = "pyprojkit-tracked"
_LEGACY_MARKER = "managed by pyprojkit"

_UV_BUILD = "uv_build"
_UV_BUILD_REQ_RE = re.compile(r"^\s*uv[_-]build\s*(?P<spec>[^;]*)", re.IGNORECASE)
_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")

_HEADER_LINK = "https://github.com/mm21/pyprojkit"
_HEADER_COMMENT = f"# managed (in part) by pyprojkit: {_HEADER_LINK}"


def compute_managed_fields(config: ProjectConfig) -> dict[str, dict[str, Any]]:
    """
    Compute all managed fields, keyed by dotted table path then key.
    """
    tool_configs: list[BaseToolConfig] = []
    tools = config.tools

    if tools.formatting:
        tool_configs += tools.formatting.formatters

    if test := tools.test:
        tool_configs += [test.pytest, test.coverage_run, test.coverage_report]

    tool_configs += [t for t in (tools.doit, tools.nox) if t]

    if analysis := tools.analysis:
        tool_configs += [t for t in (analysis.mypy, analysis.pyright) if t]

    return {t.table_path: t.to_toml(config) for t in tool_configs}


def render(config: ProjectConfig, text: str) -> str:
    """
    Render the synced `pyproject.toml` contents from existing contents.
    """
    doc = tomlkit.parse(_ensure_header(text))

    project = doc.get("project")
    if project is None:
        raise ConfigError("pyproject.toml has no [project] table")

    _update_classifiers(project, config)

    tracked: set[tuple[str, str]] = set()
    if config.uv_build_backend:
        _update_build_system(doc, _get_uv_version())
        tracked |= {("build-system", "build-backend"), ("build-system", "requires")}
    _update_tracked_markers(doc, tracked)

    fields = compute_managed_fields(config)
    fields["project"] = {"requires-python": config.requires_python.specifier}

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
    Sync `pyproject.toml` and the generated agent skill under the given project root
    (defaulting to the current directory).

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

    for marker_path in _iter_missing_typed_markers(config, root_path):
        rel = marker_path.relative_to(root_path)
        if check:
            print(f"would create {rel}")
            in_sync = False
        else:
            marker_path.touch()

    if (version_file := _python_version_file(config, root_path)) is not None:
        version_path, version = version_file
        current = version_path.read_text() if version_path.is_file() else None
        if current != version:
            if check:
                _print_diff(version_path.name, current or "", version)
                in_sync = False
            else:
                version_path.write_text(version)

    for skill_path, desired in _iter_skill_files(config, root_path):
        current = skill_path.read_text() if skill_path.is_file() else None
        if current == desired:
            continue
        rel = skill_path.relative_to(root_path)
        if check:
            if desired is None:
                print(f"would remove {rel}")
            else:
                _print_diff(str(rel), current or "", desired)
            in_sync = False
        elif desired is None:
            skill_path.unlink()
            _prune_dirs(skill_path.parent, stop=root_path)
        else:
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            skill_path.write_text(desired)

    if not check:
        _lock(config, root_path)

    return in_sync if check else True


def _lock(config: ProjectConfig, root: Path):
    """
    Refresh the lock file using the configured workflow tool, if any.
    """
    if tool := config.tools.workflow_tool:
        with contextlib.chdir(root):
            run([tool, "lock"])


def _print_diff(name: str, old: str, new: str):
    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"{name} (on disk)",
        tofile=f"{name} (synced)",
    )
    print("".join(diff), end="")


def _iter_missing_typed_markers(config: ProjectConfig, root: Path) -> Iterator[Path]:
    """
    Yield the path of each missing `py.typed` file, if the project is typed; packages
    whose directory doesn't exist are skipped.
    """
    if not config.typed:
        return
    for package in config.resolved_packages:
        package_dir = root / package.path
        if package_dir.is_dir() and not (package_dir / "py.typed").exists():
            yield package_dir / "py.typed"


def _python_version_file(config: ProjectConfig, root: Path) -> tuple[Path, str] | None:
    """
    Get `(path, desired_content)` for the `.python-version` file, if enabled.
    """
    if not config.python_version_file or (versions := config.pinned_versions) is None:
        return None
    return root / ".python-version", f"{versions.patch(versions.versions[-1])}\n"


def _get_uv_version() -> tuple[int, int, int]:
    """
    Get the installed uv version as (major, minor, patch).
    """
    try:
        output = subprocess.run(
            ["uv", "--version"], capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        raise ConfigError(f"Failed to get uv version: {e}") from e
    if (match := _VERSION_RE.search(output)) is None:
        raise ConfigError(f"Failed to parse uv version: {output!r}")
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def _update_build_system(doc: TOMLDocument, uv_version: tuple[int, int, int]):
    """
    Point `[build-system]` at the uv build backend for the given uv version, unless it
    already uses a `uv_build` requirement whose range the version doesn't exceed (an
    older uv never downgrades it).

    Other requirements are kept if the backend is already `uv_build`, else replaced.
    """
    build_system = doc.get("build-system")
    if build_system is None:
        build_system = tomlkit.table()
        doc["build-system"] = build_system

    requires = build_system.get("requires", [])
    index = next(
        (i for i, r in enumerate(requires) if _UV_BUILD_REQ_RE.match(str(r))), None
    )
    is_uv_build = build_system.get("build-backend") == _UV_BUILD and index is not None

    if is_uv_build:
        match = _UV_BUILD_REQ_RE.match(str(requires[index]))
        assert match is not None
        upper = _parse_upper_bound(match["spec"])
        if upper is None or uv_version < upper:
            return

    major, minor, patch = uv_version
    upper_bound = f"{major}.{minor + 1}.0" if major == 0 else f"{major + 1}.0.0"
    requirement = f"{_UV_BUILD}>={major}.{minor}.{patch},<{upper_bound}"

    build_system["build-backend"] = _UV_BUILD
    if is_uv_build:
        requires[index] = requirement
    else:
        build_system["requires"] = [requirement]


def _update_tracked_markers(doc: TOMLDocument, tracked: set[tuple[str, str]]):
    """
    Mark the given `(table_path, key)` fields as tracked, and strip the marker from any
    other fields carrying it (keeping the fields themselves).
    """
    for path, table in _walk_tables(doc):
        for key, item in table.value.body:
            if key is None or isinstance(item, (Table, AoT)):
                continue
            if (path, key.key) in tracked:
                item.comment(_TRACKED_MARKER)
            elif _TRACKED_MARKER in item.trivia.comment:
                item.trivia.comment = ""
                item.trivia.comment_ws = ""


def _parse_upper_bound(spec: str) -> tuple[int, ...] | None:
    """
    Get the exclusive upper bound (`<X.Y[.Z]`) from a version specifier, if any, padded
    to (major, minor, patch).
    """
    for clause in spec.split(","):
        clause = clause.strip()
        if clause.startswith("<") and not clause.startswith("<="):
            parts = tuple(int(p) for p in re.findall(r"\d+", clause)[:3])
            return parts + (0,) * (3 - len(parts))
    return None


def _iter_skill_files(
    config: ProjectConfig, root: Path
) -> Iterator[tuple[Path, str | None]]:
    """
    Yield `(path, desired_content)` for each managed skill file; `None` content means
    the file should not exist.

    The skill name is namespaced (`pyprojkit-*`), so it's owned by pyprojkit: the
    generated skill in the default skills directory is pruned when no longer configured
    (including via `skill=None`).
    """
    desired: Path | None = None
    if skill := config.tools.skill:
        desired = _skill_path(root, skill.skills_dir)
        yield desired, render_skill(config)

    default = _skill_path(root, SkillConfig().skills_dir)
    if default != desired and default.is_file():
        yield default, None


def _skill_path(root: Path, skills_dir: str) -> Path:
    return root / skills_dir / SKILL_NAME / "SKILL.md"


def _prune_dirs(path: Path, stop: Path):
    """
    Remove `path` and its parents up to (excluding) `stop`, as long as they are empty.
    """
    while path != stop and path.is_dir() and not any(path.iterdir()):
        path.rmdir()
        path = path.parent


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
    Replace managed classifiers with those derived from the configuration, preserving
    all others; result is sorted, with managed entries marked by an inline comment.

    Stale entries are those previously marked as managed, plus python version
    classifiers if versions are pinned (so they're replaced wholesale). Left untouched
    if there are neither managed nor stale entries.

    Comments in the existing list are preserved: an inline comment stays with its entry,
    and a standalone comment stays with the entry it precedes (or is emitted at the end
    of the list if it precedes none).
    """
    versions = config.pinned_versions
    managed = _managed_classifiers(config)
    existing = project.get("classifiers", [])
    marked = _marked_classifiers(existing)
    kept = [
        str(c)
        for c in existing
        if str(c) not in marked
        and not (versions is not None and _CLASSIFIER_RE.match(str(c)))
    ]
    if not managed and len(kept) == len(existing):
        return

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


def _managed_classifiers(config: ProjectConfig) -> set[str]:
    """
    Get classifiers derived from the configuration.
    """
    managed: set[str] = set()
    if (versions := config.pinned_versions) is not None:
        prefix = "Programming Language :: Python :: "
        managed |= {f"{prefix}{maj}" for maj, _ in versions.versions}
        managed |= {f"{prefix}{maj}.{min}" for maj, min in versions.versions}
    if config.typed:
        managed.add(_TYPED_CLASSIFIER)
    return managed


def _marked_classifiers(array: Any) -> set[str]:
    """
    Get entries of an existing classifiers array carrying a managed marker comment.
    """
    return {
        str(group.value)
        for group in getattr(array, "_value", [])
        if group.value is not None
        and not isinstance(group.value, Null)
        and _comment_text(group) in (_MARKER, _LEGACY_MARKER)
    }


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
        legacy_paths = list(doc["tool"]["pyprojkit"]["managed"])  # type: ignore[index,arg-type]
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
            for f in (
                config.tools.formatting.formatters if config.tools.formatting else ()
            )
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
