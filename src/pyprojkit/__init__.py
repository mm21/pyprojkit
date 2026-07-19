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
from .versions import (
    DEFAULT_PATCH_VERSIONS,
    PythonVersions,
)
from .config import (
    ConfigError,
    BaseToolConfig,
    BaseFormatterConfig,
    AutoflakeConfig,
    IsortConfig,
    BlackConfig,
    DocformatterConfig,
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
    get_formatting_profile,
    get_tools_profile,
    register_formatting_profile,
    register_tools_profile,
)
from .discovery import (
    load_config,
)
from .sync import (
    compute_managed_tables,
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
    "DEFAULT_PATCH_VERSIONS",
    "PythonVersions",
    "ConfigError",
    "BaseToolConfig",
    "BaseFormatterConfig",
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
    "ProjectConfig",
    "ToolsConfig",
    "FormattingConfig",
    "TestConfig",
    "DocConfig",
    "MkinitConfig",
    "SphinxConfig",
    "AnalysisConfig",
    "PublishConfig",
    "get_formatting_profile",
    "get_tools_profile",
    "register_formatting_profile",
    "register_tools_profile",
    "load_config",
    "compute_managed_tables",
    "render",
    "TaskFactory",
    "NoxFactory",
]
# </AUTOGEN_INIT>
