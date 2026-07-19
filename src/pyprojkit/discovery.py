"""
Discovery of a project's `pyprojconf.py`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from .config.base import ConfigError
from .config.project import ProjectConfig

__all__ = [
    "load_config",
]

CONF_FILENAME = "pyprojconf.py"


def load_config(root: Path | str | None = None) -> ProjectConfig:
    """
    Load `pyprojconf.py` from the given project root (defaulting to the current
    directory) and return its `config`.
    """
    root_path = Path(root) if root else Path.cwd()
    conf_path = root_path / CONF_FILENAME

    if not conf_path.is_file():
        raise ConfigError(f"'{conf_path}' not found")

    module_name = f"_pyprojconf_{abs(hash(str(conf_path.resolve())))}"
    spec = importlib.util.spec_from_file_location(module_name, conf_path)
    assert spec and spec.loader

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise ConfigError(f"Failed to import '{conf_path}': {exc}") from exc
    finally:
        sys.modules.pop(module_name, None)

    config = getattr(module, "config", None)
    if not isinstance(config, ProjectConfig):
        raise ConfigError(
            f"'{conf_path}' must define a module-level `config: ProjectConfig`"
        )

    return config
