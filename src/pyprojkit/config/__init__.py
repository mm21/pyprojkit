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
    BaseConfig,
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
    PyrightConfig,
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
    SkillConfig,
)
from .profiles import (
    create_kitchen_sink_tools,
)

__all__ = [
    "ConfigError",
    "BaseConfig",
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
    "PyrightConfig",
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
]
# </AUTOGEN_INIT>
