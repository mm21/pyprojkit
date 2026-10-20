"""
Configuration model for pyprojkit.
"""

__submodules__ = [
    "base",
    "tools",
    "project",
    "profiles",
]

# isort: off
# <AUTOGEN_INIT>
from .base import (
    ConfigError,
    BaseToolConfig,
    BaseFormatterConfig,
)
from .tools import (
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
)
from .project import (
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
)
from .profiles import (
    create_kitchen_sink_tools,
)

__all__ = [
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
]
# </AUTOGEN_INIT>
