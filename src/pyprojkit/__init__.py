"""
Development workflow toolkit for Python projects.

Declare configuration once in `pyprojconf.py`; pyprojkit keeps `pyproject.toml` in sync
and provides `doit` task and `nox` session factories.
"""

__submodules__ = [
    "config",
    "versions",
    "discovery",
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
    ClaudeConfig,
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
    "ClaudeConfig",
    "create_kitchen_sink_tools",
    "DEFAULT_PATCH_VERSIONS",
    "PythonVersions",
    "PythonVersionSet",
    "RequiresPython",
    "load_config",
    "compute_managed_fields",
    "render",
    "TaskFactory",
    "NoxFactory",
]
# </AUTOGEN_INIT>
