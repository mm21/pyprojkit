"""
`nox` session factories.

Usage in a project's `noxfile.py`:

```python
from pyprojkit import NoxFactory

test = NoxFactory().create_test_session()
```
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import nox
from nox import Session

from .config.base import ConfigError
from .config.project import ProjectConfig
from .discovery import load_config

__all__ = [
    "NoxFactory",
]


class NoxFactory:
    """
    Factory for `nox` sessions, configured by the project's `pyprojconf.py`.

    Sessions are registered with nox upon creation, so `create_*_session()` must be
    called at `noxfile.py` import time.
    """

    _config: ProjectConfig
    _registered: set[str]

    def __init__(
        self,
        config: ProjectConfig | None = None,
        root: Path | str | None = None,
    ):
        self._config = config or load_config(root)
        self._registered = set()
        nox.options.envdir = self._config.tools.nox.envdir

    def create_test_session(self, *, group: str = "dev") -> Callable[[Session], None]:
        """
        Create and register `test` session which runs pytest over all supported Python
        versions, installing dependencies from the given dependency group via uv.
        """
        if "test" in self._registered:
            raise ConfigError("Session 'test' already created")
        self._registered.add("test")

        @nox.session(python=self._config.python.pins, name="test")
        def test(session: Session):
            session.run_install(
                "uv",
                "sync",
                f"--group={group}",
                "--frozen",
                f"--python={session.python}",  # explicitly pin the version
                env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
            )
            session.run("pytest", *session.posargs)

        return test
