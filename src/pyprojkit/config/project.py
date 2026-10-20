"""
Project-wide configuration, declared in a project's `pyprojconf.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from .. import _paths
from ..versions import PythonVersions, PythonVersionSet, RequiresPython
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
    "ClaudeConfig",
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
class ClaudeConfig:
    """
    Claude Code integration: managed skills written to `.claude/skills/`.
    """

    skills: tuple[str, ...] = ("modern-python",)
    """
    Built-in skills to sync into the project; each is written to
    `.claude/skills/<name>/SKILL.md` and overwritten on every sync.
    """


@dataclass(kw_only=True)
class ToolsConfig:
    """
    Development tool configurations, grouped by broad tool category.

    Every category is opt-in: `None` (the default) means the tool is neither managed nor
    given a task. For a pre-canned set of everything, see `create_kitchen_sink_tools()`;
    to share a configuration across projects, define your own factory function or
    global.
    """

    formatting: FormattingConfig | None = None
    test: TestConfig | None = None
    doit: DoitConfig | None = None
    nox: NoxConfig | None = None
    doc: DocConfig | None = None
    analysis: AnalysisConfig | None = None
    publish: PublishConfig | None = None
    claude: ClaudeConfig | None = None
    """
    Claude Code integration. When `None`, managed skill files are removed on the next
    sync.
    """


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

    requires_python: RequiresPython
    """
    Interpreter versions the package can be installed on (`requires-python`).
    Independent of the pinned versions: leave the upper bound open for future-proof
    dependency resolution.
    """

    pinned_python: PythonVersions | Sequence[PythonVersions] | None = None
    """
    Specific Python versions which are tested and targeted by tools (classifiers, black,
    mypy, nox): a single range, or a sequence of ranges for discontiguous support, e.g.
    3.8-3.9 and 3.11-3.12. Must all satisfy `requires_python`. Optional, but required by
    tools which need specific versions.
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

    tools: ToolsConfig = field(default_factory=ToolsConfig)
    """
    Tool configurations.
    """

    def __post_init__(self):
        if self.pinned_versions is None:
            return
        for version in self.pinned_versions.versions:
            if not self.requires_python.contains(version):
                raise ValueError(
                    f"Pinned Python {version[0]}.{version[1]} is outside of "
                    f"requires-python ({self.requires_python.specifier})"
                )

    @property
    def pinned_versions(self) -> PythonVersionSet | None:
        """
        Pinned Python versions normalized across all configured ranges, if any.
        """
        if self.pinned_python is None:
            return None
        return PythonVersionSet.from_config(self.pinned_python)

    @property
    def package_path(self) -> Path:
        """
        Path to the package directory, relative to the project root.
        """
        return Path(self.packages_dir) / self.package
