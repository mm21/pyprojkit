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
    DocformatterConfig,
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
)
from .profiles import (
    get_formatting_profile,
    get_tools_profile,
    register_formatting_profile,
    register_tools_profile,
)

__all__ = [
    "ConfigError",
    "BaseToolConfig",
    "BaseFormatterConfig",
    "AutoflakeConfig",
    "IsortConfig",
    "BlackConfig",
    "DocfmtConfig",
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
]
# </AUTOGEN_INIT>
