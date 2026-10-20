"""
Built-in tool configurations.

Configurations are plain `ToolsConfig` values: define your own factory function or
global in a module shared across projects, optionally building on
`create_kitchen_sink_tools()`:

```python
from dataclasses import replace

from pyprojkit import AnalysisConfig, ToolsConfig, create_kitchen_sink_tools


def create_mycompany_tools() -> ToolsConfig:
    return replace(create_kitchen_sink_tools(), analysis=AnalysisConfig())
```
"""

from __future__ import annotations

from .project import (
    AnalysisConfig,
    ClaudeConfig,
    DocConfig,
    FormattingConfig,
    PublishConfig,
    TestConfig,
    ToolsConfig,
)
from .tools import (
    AutoflakeConfig,
    BlackConfig,
    DocfmtConfig,
    DoitConfig,
    IsortConfig,
    NoxConfig,
    TomlSortConfig,
)

__all__ = [
    "create_kitchen_sink_tools",
]


def create_kitchen_sink_tools() -> ToolsConfig:
    """
    Get a new instance of the configuration which enables every tool: formatting,
    testing, doit, nox, mkinit, static analysis, publishing and Claude skills. Sphinx is
    left disabled since it needs project-specific settings.
    """
    return ToolsConfig(
        formatting=FormattingConfig(
            formatters=(
                AutoflakeConfig(),
                IsortConfig(),
                DocfmtConfig(),
                BlackConfig(),
                TomlSortConfig(),
            )
        ),
        test=TestConfig(),
        doit=DoitConfig(),
        nox=NoxConfig(),
        doc=DocConfig(),
        analysis=AnalysisConfig(),
        publish=PublishConfig(),
        claude=ClaudeConfig(),
    )
