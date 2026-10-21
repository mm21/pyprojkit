"""
Development workflow toolkit for Python projects.

Declare configuration once in `pyprojconf.py`; pyprojkit keeps `pyproject.toml` in sync
and provides `doit` task and `nox` session factories.
"""

__submodules__ = [
    "config",
    "versions",
    "discovery",
    "skill",
    "sync",
    "tasks",
    "sessions",
]

# isort: off
# <AUTOGEN_INIT>
from .config import (
    ConfigError,
    BaseToolConfig,
    BaseFormatterConfig,
    AutoflakeConfig,
    IsortConfig,
    BlackConfig,
    DocfmtConfig,
    TomlSortConfig,
    PytestConfig,
    CoverageRunConfig,
    CoverageReportConfig,
    DoitConfig,
    NoxConfig,
    MypyConfig,
    ProjectConfig,
    ToolsConfig,
    FormattingConfig,
    TestConfig,
    DocConfig,
    MkinitConfig,
    SphinxConfig,
    AnalysisConfig,
    PublishConfig,
    SkillConfig,
    create_kitchen_sink_tools,
)
from .versions import (
    DEFAULT_PATCH_VERSIONS,
    PythonVersions,
    PythonVersionSet,
    RequiresPython,
)
from .discovery import (
    load_config,
)
from .skill import (
    render_skill,
)
from .sync import (
    compute_managed_fields,
    render,
    sync,
)
from .tasks import (
    TaskFactory,
)
from .sessions import (
    NoxFactory,
)

__all__ = [
    "sync",
    "ConfigError",
    "BaseToolConfig",
    "BaseFormatterConfig",
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
    "create_kitchen_sink_tools",
    "DEFAULT_PATCH_VERSIONS",
    "PythonVersions",
    "PythonVersionSet",
    "RequiresPython",
    "load_config",
    "render_skill",
    "compute_managed_fields",
    "render",
    "TaskFactory",
    "NoxFactory",
]
# </AUTOGEN_INIT>
