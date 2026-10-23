"""
Built-in tool configurations.

Configurations are plain `ToolsConfig` values: define your own factory function or
global in a module shared across projects, enabling just the tools you want:

```python
from pyprojkit import (
    AnalysisConfig,
    BlackConfig,
    FormattingConfig,
    IsortConfig,
    PyrightConfig,
    PytestConfig,
    TestConfig,
    ToolsConfig,
)


def create_mycompany_tools() -> ToolsConfig:
    return ToolsConfig(
        formatting=FormattingConfig(
            formatters=(
                IsortConfig(profile="black"),
                BlackConfig(),
            )
        ),
        test=TestConfig(pytest=PytestConfig(addopts="-v")),
        analysis=AnalysisConfig(pyright=PyrightConfig()),
    )
```

Alternatively, start from `create_recommended_tools()` and override parts of it with
`dataclasses.replace()`.
"""

from __future__ import annotations

from .project import ToolsConfig

__all__ = [
    "create_recommended_tools",
]


def create_recommended_tools() -> ToolsConfig:
    """
    Get a new instance of the recommended configuration: every tool which doesn't need
    project-specific settings, with opinionated settings; equivalent to
    `ToolsConfig.create_recommended()`.
    """
    return ToolsConfig.create_recommended()
