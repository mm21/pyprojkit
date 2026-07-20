"""
Project-wide configuration, declared in a project's `pyprojconf.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from .. import _paths
from ..versions import PythonVersions
from .base import BaseFormatterConfig
from .tools import (
    CoverageReportConfig,
    CoverageRunConfig,
    DoitConfig,
    MypyConfig,
    NoxConfig,
    PytestConfig,
)

__all__ = [
    "ProjectConfig",
    "ToolsConfig",
    "FormattingConfig",
    "TestConfig",
    "DocConfig",
    "MkinitConfig",
    "SphinxConfig",
    "AnalysisConfig",
    "PublishConfig",
]


@dataclass(kw_only=True)
class FormattingConfig:
    """
    Formatting configuration: which formatters run (in order) and their settings.
    """

    formatters: tuple[BaseFormatterConfig, ...]
    """
    Formatters in run order.
    """

    @classmethod
    def default(cls) -> FormattingConfig:
        """
        Get the default formatting profile.
        """
        from .profiles import get_formatting_profile

        return get_formatting_profile("default")


@dataclass(kw_only=True)
class TestConfig:
    """
    Testing configuration (pytest + coverage).
    """

    pytest: PytestConfig = field(default_factory=PytestConfig)
    coverage_run: CoverageRunConfig = field(default_factory=CoverageRunConfig)
    coverage_report: CoverageReportConfig = field(default_factory=CoverageReportConfig)


@dataclass(kw_only=True)
class MkinitConfig:
    """
    Configuration for generating `__init__.py` files using mkinit.
    """

    args: tuple[str, ...] = (
        "--recursive",
        "--nomods",
        "--relative",
        "-i",
        "--source-order",
    )
    """
    Arguments passed to mkinit.
    """


@dataclass(kw_only=True)
class SphinxConfig:
    """
    Configuration for building documentation using sphinx.
    """

    source_dir: str = "doc"
    """
    Directory containing sphinx sources.
    """

    copy_env_var: str | None = None
    """
    Name of environment variable (or `.env` entry) giving a directory to which to copy
    built documentation when the doc task is run with `--copy`.
    """


@dataclass(kw_only=True)
class DocConfig:
    """
    Documentation tool configurations.
    """

    mkinit: MkinitConfig | None = field(default_factory=MkinitConfig)
    """
    Enables the `init` task; enabled by default.
    """

    sphinx: SphinxConfig | None = None
    """
    Enables the `doc` task; opt-in.
    """


@dataclass(kw_only=True)
class AnalysisConfig:
    """
    Static analysis configuration.
    """

    mypy: MypyConfig | None = field(default_factory=MypyConfig)
    pyright: bool = True


@dataclass(kw_only=True)
class PublishConfig:
    """
    Configuration for building and publishing via uv.
    """

    out_dir: str = str(_paths.UV_PATH)
    """
    Directory for build artifacts; cleaned before each build so stale artifacts are
    never published.
    """


@dataclass(kw_only=True)
class ToolsConfig:
    """
    Development tool configurations, grouped by broad tool category.

    A "tools profile" is simply a pre-canned `ToolsConfig` factory; see
    `pyprojkit.config.profiles`. The default instance corresponds to the default
    profile.
    """

    formatting: FormattingConfig = field(default_factory=FormattingConfig.default)
    test: TestConfig | None = field(default_factory=TestConfig)
    doit: DoitConfig = field(default_factory=DoitConfig)
    nox: NoxConfig = field(default_factory=NoxConfig)
    doc: DocConfig = field(default_factory=DocConfig)
    analysis: AnalysisConfig | None = None
    publish: PublishConfig = field(default_factory=PublishConfig)

    tool_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    """
    Escape hatch: extra entries merged last into managed tables, keyed by table path,
    e.g. `{"tool.pytest.ini_options": {"addopts": "..."}}`.

    A key not otherwise managed creates a new managed table.
    """

    @classmethod
    def default(cls) -> ToolsConfig:
        """
        Get the default tools profile.
        """
        from .profiles import get_tools_profile

        return get_tools_profile("default")


@dataclass(kw_only=True)
class ProjectConfig:
    """
    Top-level project configuration.

    A project's `pyprojconf.py` must define a module-level instance named `config`.
    """

    package: str
    """
    Import name of the package, e.g. `"trilium_alchemy"`.
    """

    python: PythonVersions
    """
    Supported Python versions.
    """

    packages_dir: str = "src"
    """
    Directory containing packages, relative to the project root.
    """

    format_paths: Sequence[str] = ("src", "test", "doc", "examples")
    """
    Directories to format (those which exist), in addition to `*.py` and `*.toml` files
    at the project root.
    """

    tools: ToolsConfig = field(default_factory=ToolsConfig.default)
    """
    Tool configurations.
    """

    @property
    def package_path(self) -> Path:
        """
        Path to the package directory, relative to the project root.
        """
        return Path(self.packages_dir) / self.package
