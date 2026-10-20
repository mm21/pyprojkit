from pyprojkit import ProjectConfig, PythonVersions, RequiresPython

config = ProjectConfig(
    package="pyprojkit",
    requires_python=RequiresPython((3, 12)),
    pinned_python=PythonVersions(3, (12, 14)),
)
