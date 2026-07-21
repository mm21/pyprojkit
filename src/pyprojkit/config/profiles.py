"""
Profile registries: named factories for pre-canned configurations.

A tools profile encompasses all tool categories; a formatting profile covers
just the formatter chain. Third parties can register their own profiles and
reuse them across projects:

```python
from pyprojkit import register_tools_profile

register_tools_profile("mycompany", lambda: ToolsConfig(...))
```
"""

from __future__ import annotations

from typing import Callable

from .base import ConfigError
from .project import FormattingConfig, ToolsConfig
from .tools import (
    AutoflakeConfig,
    BlackConfig,
    DocfmtConfig,
    IsortConfig,
    TomlSortConfig,
)

__all__ = [
    "get_formatting_profile",
    "get_tools_profile",
    "register_formatting_profile",
    "register_tools_profile",
]


def _default_formatting() -> FormattingConfig:
    return FormattingConfig(
        formatters=(
            AutoflakeConfig(),
            IsortConfig(),
            DocfmtConfig(),
            BlackConfig(),
            TomlSortConfig(),
        )
    )


_FORMATTING_PROFILES: dict[str, Callable[[], FormattingConfig]] = {
    "default": _default_formatting,
}

# the zero-arg ToolsConfig constructor is itself the default profile, as its
# field defaults resolve to the default sub-configs
_TOOLS_PROFILES: dict[str, Callable[[], ToolsConfig]] = {
    "default": ToolsConfig,
}


def get_formatting_profile(name: str) -> FormattingConfig:
    """
    Get a new instance of the given formatting profile.
    """
    try:
        factory = _FORMATTING_PROFILES[name]
    except KeyError:
        raise ConfigError(
            f"Unknown formatting profile '{name}'; have {sorted(_FORMATTING_PROFILES)}"
        ) from None
    return factory()


def get_tools_profile(name: str) -> ToolsConfig:
    """
    Get a new instance of the given tools profile.
    """
    try:
        factory = _TOOLS_PROFILES[name]
    except KeyError:
        raise ConfigError(
            f"Unknown tools profile '{name}'; have {sorted(_TOOLS_PROFILES)}"
        ) from None
    return factory()


def register_formatting_profile(name: str, factory: Callable[[], FormattingConfig]):
    """
    Register a named formatting profile.
    """
    _FORMATTING_PROFILES[name] = factory


def register_tools_profile(name: str, factory: Callable[[], ToolsConfig]):
    """
    Register a named tools profile.
    """
    _TOOLS_PROFILES[name] = factory
