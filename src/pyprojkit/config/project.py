"""
Project-wide configuration, declared in a project's `pyprojconf.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Self, Sequence

from .. import _paths
from ..versions import PythonVersions, PythonVersionSet, RequiresPython
from .base import BaseConfig, BaseFormatterConfig
from .tools import (
    AutoflakeConfig,
    BlackConfig,
    CoverageReportConfig,
    CoverageRunConfig,
    DocfmtConfig,
    DoitConfig,
    IsortConfig,
    MypyConfig,
    NoxConfig,
    PyrightConfig,
    PytestConfig,
    TomlSortConfig,
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
    "SkillConfig",
]


@dataclass(kw_only=True)
class FormattingConfig(BaseConfig):
    """
    Formatting configuration: which formatters run (in order) and their settings.
    """

    formatters: tuple[BaseFormatterConfig, ...] = ()
    """
    Formatters in run order.
    """

    @classmethod
    def create_recommended(cls) -> Self:
        return cls(
            formatters=(
                AutoflakeConfig.create_recommended(),
                IsortConfig.create_recommended(),
                DocfmtConfig.create_recommended(),
                BlackConfig.create_recommended(),
                TomlSortConfig.create_recommended(),
            )
        )


@dataclass(kw_only=True)
class TestConfig(BaseConfig):
    """
    Testing configuration (pytest + coverage).
    """

    pytest: PytestConfig = field(default_factory=PytestConfig)
    coverage_run: CoverageRunConfig = field(default_factory=CoverageRunConfig)
    coverage_report: CoverageReportConfig = field(default_factory=CoverageReportConfig)

    @classmethod
    def create_recommended(cls) -> Self:
        return cls(
            pytest=PytestConfig.create_recommended(),
            coverage_run=CoverageRunConfig.create_recommended(),
            coverage_report=CoverageReportConfig.create_recommended(),
        )


@dataclass(kw_only=True)
class MkinitConfig(BaseConfig):
    """
    Configuration for generating `__init__.py` files using mkinit.
    """

    args: tuple[str, ...] = ()
    """
    Arguments passed to mkinit.
    """

    @classmethod
    def create_recommended(cls) -> Self:
        return cls(
            args=("--recursive", "--nomods", "--relative", "-i", "--source-order")
        )


@dataclass(kw_only=True)
class SphinxConfig(BaseConfig):
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

    @classmethod
    def create_recommended(cls) -> Self:
        return cls()


@dataclass(kw_only=True)
class DocConfig(BaseConfig):
    """
    Documentation tool configurations.
    """

    mkinit: MkinitConfig | None = None
    """
    Enables the `init` task.
    """

    sphinx: SphinxConfig | None = None
    """
    Enables the `doc` task.
    """

    @classmethod
    def create_recommended(cls) -> Self:
        """
        Enables mkinit; sphinx is left disabled since it needs project-specific
        settings.
        """
        return cls(mkinit=MkinitConfig.create_recommended())


@dataclass(kw_only=True)
class AnalysisConfig(BaseConfig):
    """
    Static analysis configuration.
    """

    mypy: MypyConfig | None = None
    pyright: PyrightConfig | None = None

    @classmethod
    def create_recommended(cls) -> Self:
        return cls(
            mypy=MypyConfig.create_recommended(),
            pyright=PyrightConfig.create_recommended(),
        )


@dataclass(kw_only=True)
class PublishConfig(BaseConfig):
    """
    Configuration for building and publishing via uv.
    """

    out_dir: str | None = None
    """
    Directory for build artifacts, defaulting to uv's `dist`; cleaned before each build
    so stale artifacts are never published.
    """

    @classmethod
    def create_recommended(cls) -> Self:
        return cls(out_dir=str(_paths.UV_PATH))


@dataclass(kw_only=True)
class SkillConfig(BaseConfig):
    """
    Agent skill integration: a `pyprojkit-python` skill in the
    [Agent Skills](https://agentskills.io) format, generated from the project's
    configuration so it instructs agents to run the workflow tasks which are enabled
    (formatting, analysis, testing, etc).
    """

    skills_dir: str = ".claude/skills"
    """
    Skills directory, relative to the project root, to write the skill to as
    `<skills_dir>/pyprojkit-python/SKILL.md`.
    """

    @classmethod
    def create_recommended(cls) -> Self:
        return cls()


@dataclass(kw_only=True)
class ToolsConfig(BaseConfig):
    """
    Development tool configurations, grouped by broad tool category.

    Every category is opt-in: `None` (the default) means the tool is neither managed nor
    given a task. For a pre-canned set of everything, see `create_recommended()` (also
    available as `create_recommended_tools()`); to share a configuration across
    projects, define your own factory function or global.
    """

    workflow_tool: Literal["uv", "poetry"] | None = None
    """
    Development workflow tool which manages the project's environment; when set,
    commands given to agents are run through it, e.g. `uv run doit test`.
    """

    formatting: FormattingConfig | None = None
    test: TestConfig | None = None
    doit: DoitConfig | None = None
    nox: NoxConfig | None = None
    doc: DocConfig | None = None
    analysis: AnalysisConfig | None = None
    publish: PublishConfig | None = None
    skill: SkillConfig | None = None
    """
    Agent skill integration. When `None`, managed skill files are removed on the next
    sync.
    """

    @classmethod
    def create_recommended(cls) -> Self:
        """
        Enables every tool category, each with its opinionated settings: uv as the
        workflow tool, formatting, testing, doit, nox, mkinit, static analysis,
        publishing and the agent skill. Sphinx is left disabled since it needs
        project-specific settings.
        """
        return cls(
            workflow_tool="uv",
            formatting=FormattingConfig.create_recommended(),
            test=TestConfig.create_recommended(),
            doit=DoitConfig.create_recommended(),
            nox=NoxConfig.create_recommended(),
            doc=DocConfig.create_recommended(),
            analysis=AnalysisConfig.create_recommended(),
            publish=PublishConfig.create_recommended(),
            skill=SkillConfig.create_recommended(),
        )


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

    code_paths: Sequence[str] = ("src", "test", "doc", "examples")
    """
    Directories containing Python code (those which exist), relative to the project
    root. These are formatted (in addition to `*.py` and `*.toml` files at the project
    root) and checked by static analysis.
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
