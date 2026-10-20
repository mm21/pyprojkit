from dataclasses import replace

from pyprojkit import (
    ProjectConfig,
    PythonVersions,
    RequiresPython,
    create_kitchen_sink_tools,
)

config = ProjectConfig(
    package="pyprojkit",
    requires_python=RequiresPython((3, 12)),
    pinned_python=PythonVersions(3, (12, 14)),
    tools=replace(create_kitchen_sink_tools(), analysis=None),
)
