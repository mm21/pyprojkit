"""
Project-wide configuration, declared in a project's `pyprojconf.py`.
"""

from __future__ import annotations

import glob
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Self, Sequence

from .. import _paths
from ..versions import PythonVersions, PythonVersionSet, RequiresPython
from .base import BaseConfig, BaseFormatterConfig, ConfigError
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
    "PackageSpec",
    "ResolvedPackage",
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

    packages: str | PackageSpec | Sequence[str | PackageSpec]
    """
    Packages comprising the project: import names, e.g. `"trilium_alchemy"`, or
    `PackageSpec`s to locate a package in a source path other than `source_path`. See
    `resolved_packages` for the normalized form.
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

    source_path: str = "src"
    """
    Default directory containing packages, relative to the project root; `"."` for a
    flat layout. Overridden per package by `PackageSpec.source_path`.
    """

    test_paths: Sequence[str] = ("test",)
    """
    Directories containing tests, relative to the project root; may be glob patterns.
    Propagated to pytest's `testpaths`.
    """

    extra_code_paths: Sequence[str] = ("doc", "examples", "*.py", "*.toml")
    """
    Additional directories or files containing code, relative to the project root; may
    be glob patterns. Formatted and checked by static analysis along with the package
    and test paths (see `get_code_paths()`).
    """

    tools: ToolsConfig = field(default_factory=ToolsConfig)
    """
    Tool configurations.
    """

    def __post_init__(self):
        names = [package.name for package in self.resolved_packages]
        if not names:
            raise ConfigError("At least one package must be configured")
        if duplicates := sorted({name for name in names if names.count(name) > 1}):
            raise ConfigError(f"Duplicate packages: {', '.join(duplicates)}")

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
    def resolved_packages(self) -> tuple[ResolvedPackage, ...]:
        """
        Packages normalized with their source paths resolved, in configured order.
        """
        packages = (
            [self.packages]
            if isinstance(self.packages, (str, PackageSpec))
            else self.packages
        )
        specs = (
            PackageSpec(package) if isinstance(package, str) else package
            for package in packages
        )
        return tuple(
            ResolvedPackage(
                name=spec.name,
                source_path=Path(
                    spec.source_path
                    if spec.source_path is not None
                    else self.source_path
                ),
            )
            for spec in specs
        )

    def get_test_paths(self, root: Path) -> list[Path]:
        """
        Get existing test paths, with glob patterns expanded, relative to the project
        root.
        """
        return _glob_paths(root, self.test_paths)

    def get_code_paths(self, root: Path) -> list[Path]:
        """
        Get all existing paths containing code — package directories, test paths, and
        extra code paths — with glob patterns expanded, relative to the project root.

        Paths nested within another are omitted.
        """
        paths = [
            package.path
            for package in self.resolved_packages
            if (root / package.path).is_dir()
        ]
        paths += self.get_test_paths(root)
        paths += _glob_paths(root, self.extra_code_paths)

        # dedupe, dropping paths nested within another
        result: list[Path] = []
        for path in paths:
            if path in result or any(
                path.is_relative_to(other)
                for other in paths
                if other not in (path, Path("."))
            ):
                continue
            result.append(path)
        return result


@dataclass(frozen=True)
class PackageSpec:
    """
    Package to include in the project, optionally located in a source path other than
    the project's default.
    """

    name: str
    """
    Import name of the package.
    """

    source_path: str | None = None
    """
    Directory containing the package, relative to the project root, if other than
    `ProjectConfig.source_path`.
    """


@dataclass(frozen=True, kw_only=True)
class ResolvedPackage:
    """
    Package with its source path resolved, as given by
    `ProjectConfig.resolved_packages`.
    """

    name: str
    """
    Import name of the package.
    """

    source_path: Path
    """
    Directory containing the package, relative to the project root.
    """

    @property
    def path(self) -> Path:
        """
        Path to the package directory, relative to the project root.
        """
        return self.source_path / self.name


def _glob_paths(root: Path, patterns: Sequence[str]) -> list[Path]:
    """
    Expand path patterns relative to the root, keeping those which exist, in pattern
    order (and sorted within each pattern).
    """
    paths: list[Path] = []
    for pattern in patterns:
        if glob.has_magic(pattern):
            matches = sorted(p.relative_to(root) for p in root.glob(pattern))
        else:
            matches = [Path(pattern)] if (root / pattern).exists() else []
        paths += [p for p in matches if p not in paths]
    return paths
