"""
Base classes for tool configurations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, fields
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from .project import ProjectConfig

__all__ = [
    "ConfigError",
    "BaseToolConfig",
    "BaseFormatterConfig",
]


class ConfigError(Exception):
    """
    Raised for invalid or missing configuration.
    """


@dataclass(kw_only=True)
class BaseToolConfig(ABC):
    """
    Configuration for a tool which reads its settings from a table in `pyproject.toml`,
    e.g. `[tool.black]`.

    Dataclass fields map to table entries; a field whose name differs from its TOML key
    declares the key via `field(metadata={"toml": "some-key"})`. Fields set to `None`
    are omitted. Values derived from project-wide config (e.g. black's `target-version`)
    are contributed by `extra_toml()`.
    """

    table_path: ClassVar[str]
    """
    Dotted path of the tool's table, e.g. `"tool.pytest.ini_options"`.
    """

    def to_toml(self, project: ProjectConfig) -> dict[str, Any]:
        """
        Get this tool's table contents.
        """
        config: dict[str, Any] = {}
        for field_ in fields(self):
            value = getattr(self, field_.name)
            if value is None:
                continue
            key = field_.metadata.get("toml", field_.name)
            config[key] = list(value) if isinstance(value, tuple) else value
        config.update(self.extra_toml(project))
        return config

    def extra_toml(self, project: ProjectConfig) -> dict[str, Any]:
        """
        Get extra table entries derived from project-wide config.
        """
        return {}


@dataclass(kw_only=True)
class BaseFormatterConfig(BaseToolConfig):
    """
    Configuration for a tool which additionally runs as part of the `format` task.

    Adds the command line to invoke and the expected return codes; the order of
    formatters in `FormattingConfig` is the run order.
    """

    expect_rc: ClassVar[frozenset[int]] = frozenset({0})
    """
    Return codes indicating success.
    """

    @abstractmethod
    def command(self, py_paths: list[str], toml_paths: list[str]) -> list[str]:
        """
        Get the command line to run, given python and toml paths to format.
        """
        ...
