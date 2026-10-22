"""
Configurations for all supported tools.

Formatters are tools which additionally run as part of the `format` task. Every field
defaults to `None` (unset); each tool's opinionated settings are provided by its
`create_recommended()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Self

from .. import _paths
from .base import BaseFormatterConfig, BaseToolConfig

if TYPE_CHECKING:
    from .project import ProjectConfig

__all__ = [
    "AutoflakeConfig",
    "IsortConfig",
    "BlackConfig",
    "DocfmtConfig",
    "TomlSortConfig",
    "PytestConfig",
    "CoverageRunConfig",
    "CoverageReportConfig",
    "DoitConfig",
    "NoxConfig",
    "MypyConfig",
    "PyrightConfig",
]


# --- formatters (run order defined by FormattingConfig) ---


@dataclass(kw_only=True)
class AutoflakeConfig(BaseFormatterConfig):
    table_path: ClassVar[str] = "tool.autoflake"

    in_place: bool | None = None
    recursive: bool | None = None
    remove_all_unused_imports: bool | None = field(
        default=None, metadata={"toml": "remove-all-unused-imports"}
    )
    remove_unused_variables: bool | None = field(
        default=None, metadata={"toml": "remove-unused-variables"}
    )

    @classmethod
    def create_recommended(cls) -> Self:
        return cls(
            in_place=True,
            recursive=True,
            remove_all_unused_imports=True,
            remove_unused_variables=True,
        )

    def command(self, py_paths: list[str], toml_paths: list[str]) -> list[str]:
        return ["autoflake"] + py_paths


@dataclass(kw_only=True)
class IsortConfig(BaseFormatterConfig):
    table_path: ClassVar[str] = "tool.isort"

    profile: str | None = None
    quiet: bool | None = None

    @classmethod
    def create_recommended(cls) -> Self:
        return cls(profile="black", quiet=True)

    def command(self, py_paths: list[str], toml_paths: list[str]) -> list[str]:
        return ["isort"] + py_paths


@dataclass(kw_only=True)
class BlackConfig(BaseFormatterConfig):
    table_path: ClassVar[str] = "tool.black"

    quiet: bool | None = None

    @classmethod
    def create_recommended(cls) -> Self:
        return cls(quiet=True)

    def extra_toml(self, project: ProjectConfig) -> dict[str, Any]:
        versions = project.pinned_versions
        if versions is None:
            return {}
        return {"target-version": [f"py{maj}{min}" for maj, min in versions.versions]}

    def command(self, py_paths: list[str], toml_paths: list[str]) -> list[str]:
        return ["black"] + py_paths


@dataclass(kw_only=True)
class DocfmtConfig(BaseFormatterConfig):
    table_path: ClassVar[str] = "tool.docfmt"

    # docfmt returns 0 when it writes changes in-place; 1 means "would change"
    # in check mode and 2 is an error, so only 0 is expected here
    expect_rc: ClassVar[frozenset[int]] = frozenset({0})

    # line length is left unset: docfmt picks it up from `[tool.black]`
    in_place: bool | None = field(default=None, metadata={"toml": "in-place"})
    recursive: bool | None = None
    summary_on_own_line: bool | None = field(
        default=None, metadata={"toml": "summary-on-own-line"}
    )
    force_reflow: bool | None = field(default=None, metadata={"toml": "force-reflow"})

    @classmethod
    def create_recommended(cls) -> Self:
        return cls(
            in_place=True, recursive=True, summary_on_own_line=True, force_reflow=True
        )

    def command(self, py_paths: list[str], toml_paths: list[str]) -> list[str]:
        return ["docfmt"] + py_paths


@dataclass(kw_only=True)
class TomlSortConfig(BaseFormatterConfig):
    table_path: ClassVar[str] = "tool.tomlsort"

    sort_first: tuple[str, ...] | None = None
    sort_table_keys: bool | None = None

    # the toml-sort CLI and library defaults disagree; when unset, the sync engine's
    # normalization falls back to the CLI default so it agrees with the format task
    spaces_before_inline_comment: int | None = None

    @classmethod
    def create_recommended(cls) -> Self:
        return cls(
            sort_first=("project", "dependency-groups", "build-system"),
            sort_table_keys=True,
            spaces_before_inline_comment=2,
        )

    def command(self, py_paths: list[str], toml_paths: list[str]) -> list[str]:
        return ["toml-sort", "-i"] + toml_paths


# --- non-formatter tools ---


@dataclass(kw_only=True)
class PytestConfig(BaseToolConfig):
    table_path: ClassVar[str] = "tool.pytest.ini_options"

    addopts: str | None = None
    cache_dir: str | None = None
    testpaths: str | None = None

    @classmethod
    def create_recommended(cls) -> Self:
        return cls(
            addopts="--import-mode=importlib -s -v -rA",
            cache_dir=str(_paths.PYTEST_CACHE_PATH),
            testpaths="test",
        )


@dataclass(kw_only=True)
class CoverageRunConfig(BaseToolConfig):
    table_path: ClassVar[str] = "tool.coverage.run"

    data_file: str | None = None

    @classmethod
    def create_recommended(cls) -> Self:
        return cls(data_file=str(_paths.COVERAGE_DATA_PATH))


@dataclass(kw_only=True)
class CoverageReportConfig(BaseToolConfig):
    table_path: ClassVar[str] = "tool.coverage.report"

    exclude_lines: tuple[str, ...] | None = None

    @classmethod
    def create_recommended(cls) -> Self:
        return cls(exclude_lines=("if TYPE_CHECKING:", "\\.\\.\\.$"))


@dataclass(kw_only=True)
class DoitConfig(BaseToolConfig):
    table_path: ClassVar[str] = "tool.doit"

    dep_file: str | None = None
    verbosity: int | None = None

    @classmethod
    def create_recommended(cls) -> Self:
        return cls(dep_file=str(_paths.DOIT_DB_PATH), verbosity=2)


@dataclass(kw_only=True)
class NoxConfig(BaseToolConfig):
    table_path: ClassVar[str] = "tool.nox"

    default_venv_backend: str | None = None
    envdir: str | None = None

    @classmethod
    def create_recommended(cls) -> Self:
        return cls(default_venv_backend="uv", envdir=str(_paths.NOX_ENVDIR_PATH))


@dataclass(kw_only=True)
class MypyConfig(BaseToolConfig):
    table_path: ClassVar[str] = "tool.mypy"

    check_untyped_defs: bool | None = None

    @classmethod
    def create_recommended(cls) -> Self:
        return cls(check_untyped_defs=True)

    def extra_toml(self, project: ProjectConfig) -> dict[str, Any]:
        versions = project.pinned_versions
        if versions is None:
            return {}
        maj, min = versions.versions[0]
        return {"python_version": f"{maj}.{min}"}


@dataclass(kw_only=True)
class PyrightConfig(BaseToolConfig):
    table_path: ClassVar[str] = "tool.pyright"

    @classmethod
    def create_recommended(cls) -> Self:
        return cls()

    def extra_toml(self, project: ProjectConfig) -> dict[str, Any]:
        versions = project.pinned_versions
        if versions is None:
            return {}
        maj, min = versions.versions[0]
        return {"pythonVersion": f"{maj}.{min}"}
