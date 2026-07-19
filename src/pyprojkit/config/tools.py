"""
Configurations for all supported tools.

Formatters are tools which additionally run as part of the `format` task.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from .. import _paths
from .base import BaseFormatterConfig, BaseToolConfig

if TYPE_CHECKING:
    from .project import ProjectConfig

__all__ = [
    "AutoflakeConfig",
    "IsortConfig",
    "BlackConfig",
    "DocformatterConfig",
    "TomlSortConfig",
    "PytestConfig",
    "CoverageRunConfig",
    "CoverageReportConfig",
    "DoitConfig",
    "NoxConfig",
    "MypyConfig",
]


# --- formatters (run order defined by FormattingConfig) ---


@dataclass(kw_only=True)
class AutoflakeConfig(BaseFormatterConfig):
    table_path: ClassVar[str] = "tool.autoflake"

    in_place: bool | None = True
    recursive: bool | None = True
    remove_all_unused_imports: bool | None = field(
        default=True, metadata={"toml": "remove-all-unused-imports"}
    )
    remove_unused_variables: bool | None = field(
        default=True, metadata={"toml": "remove-unused-variables"}
    )

    def command(self, py_paths: list[str], toml_paths: list[str]) -> list[str]:
        return ["autoflake"] + py_paths


@dataclass(kw_only=True)
class IsortConfig(BaseFormatterConfig):
    table_path: ClassVar[str] = "tool.isort"

    profile: str | None = "black"
    quiet: bool | None = True

    def command(self, py_paths: list[str], toml_paths: list[str]) -> list[str]:
        return ["isort"] + py_paths


@dataclass(kw_only=True)
class BlackConfig(BaseFormatterConfig):
    table_path: ClassVar[str] = "tool.black"

    quiet: bool | None = True

    def extra_toml(self, project: ProjectConfig) -> dict[str, Any]:
        return {"target-version": project.python.black_targets}

    def command(self, py_paths: list[str], toml_paths: list[str]) -> list[str]:
        return ["black"] + py_paths


@dataclass(kw_only=True)
class DocformatterConfig(BaseFormatterConfig):
    table_path: ClassVar[str] = "tool.docformatter"

    # docformatter returns 3 when files were changed
    expect_rc: ClassVar[frozenset[int]] = frozenset({0, 3})

    black: bool | None = True
    in_place: bool | None = field(default=True, metadata={"toml": "in-place"})
    make_summary_multi_line: bool | None = field(
        default=True, metadata={"toml": "make-summary-multi-line"}
    )
    non_strict: bool | None = field(default=True, metadata={"toml": "non-strict"})
    pre_summary_newline: bool | None = field(
        default=True, metadata={"toml": "pre-summary-newline"}
    )
    recursive: bool | None = True

    def command(self, py_paths: list[str], toml_paths: list[str]) -> list[str]:
        return ["docformatter"] + py_paths


@dataclass(kw_only=True)
class TomlSortConfig(BaseFormatterConfig):
    table_path: ClassVar[str] = "tool.tomlsort"

    sort_first: tuple[str, ...] | None = (
        "project",
        "dependency-groups",
        "build-system",
    )
    sort_table_keys: bool | None = True

    def command(self, py_paths: list[str], toml_paths: list[str]) -> list[str]:
        return ["toml-sort", "-i"] + toml_paths


# --- non-formatter tools ---


@dataclass(kw_only=True)
class PytestConfig(BaseToolConfig):
    table_path: ClassVar[str] = "tool.pytest.ini_options"

    addopts: str | None = "--import-mode=importlib -s -v -rA"
    cache_dir: str | None = str(_paths.PYTEST_CACHE_PATH)
    testpaths: str | None = "test"


@dataclass(kw_only=True)
class CoverageRunConfig(BaseToolConfig):
    table_path: ClassVar[str] = "tool.coverage.run"

    data_file: str | None = str(_paths.COVERAGE_DATA_PATH)


@dataclass(kw_only=True)
class CoverageReportConfig(BaseToolConfig):
    table_path: ClassVar[str] = "tool.coverage.report"

    exclude_lines: tuple[str, ...] | None = (
        "if TYPE_CHECKING:",
        "\\.\\.\\.$",
    )


@dataclass(kw_only=True)
class DoitConfig(BaseToolConfig):
    table_path: ClassVar[str] = "tool.doit"

    dep_file: str | None = str(_paths.DOIT_DB_PATH)
    verbosity: int | None = 2


@dataclass(kw_only=True)
class NoxConfig(BaseToolConfig):
    table_path: ClassVar[str] = "tool.nox"

    default_venv_backend: str | None = "uv"
    envdir: str | None = str(_paths.NOX_ENVDIR_PATH)


@dataclass(kw_only=True)
class MypyConfig(BaseToolConfig):
    table_path: ClassVar[str] = "tool.mypy"

    ignore_missing_imports: bool | None = True

    def extra_toml(self, project: ProjectConfig) -> dict[str, Any]:
        return {"python_version": project.python.mypy_version}
