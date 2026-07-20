"""
Python version handling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

__all__ = [
    "DEFAULT_PATCH_VERSIONS",
    "PythonVersions",
]

DEFAULT_PATCH_VERSIONS: dict[tuple[int, int], str] = {
    (3, 12): "3.12.13",
    (3, 13): "3.13.13",
    (3, 14): "3.14.6",
}
"""
Mapping of minor version to latest known patch release, used to pin nox test sessions.

Updated along with pyprojkit releases; individual projects can override via
`PythonVersions.patch_overrides`.
"""


@dataclass(frozen=True)
class PythonVersions:
    """
    Python versions supported by a project, given as a major version and an inclusive
    range of minor versions. Only explicitly supported (i.e. tested) versions should be
    specified.

    Drives `requires-python`, trove classifiers, formatter target versions, and nox
    interpreter pins.
    """

    major: int
    """
    Major version, e.g. `3`.
    """

    minor: tuple[int, int]
    """
    Minor version range as (min, max), both inclusive, e.g. `(12, 14)`.
    """

    patch_overrides: Mapping[tuple[int, int], str] = field(default_factory=dict)
    """
    Overrides for patch releases used to pin nox sessions, keyed by (major, minor).
    """

    def __post_init__(self):
        if self.minor[0] > self.minor[1]:
            raise ValueError(f"Invalid minor version range: {self.minor}")

    @property
    def versions(self) -> list[tuple[int, int]]:
        """
        All supported (major, minor) versions.
        """
        return [
            (self.major, minor) for minor in range(self.minor[0], self.minor[1] + 1)
        ]

    @property
    def requires_python(self) -> str:
        """
        Version specifier for `requires-python`, spanning exactly the supported
        versions.
        """
        return f">={self.major}.{self.minor[0]},<{self.major}.{self.minor[1] + 1}"

    @property
    def classifiers(self) -> list[str]:
        """
        Trove classifiers for the supported versions.
        """
        prefix = "Programming Language :: Python :: "
        return [f"{prefix}{self.major}"] + [
            f"{prefix}{maj}.{min}" for maj, min in self.versions
        ]

    @property
    def black_targets(self) -> list[str]:
        """
        `target-version` values for black.
        """
        return [f"py{maj}{min}" for maj, min in self.versions]

    @property
    def mypy_version(self) -> str:
        """
        `python_version` value for mypy (the minimum supported version).
        """
        return f"{self.major}.{self.minor[0]}"

    @property
    def pins(self) -> list[str]:
        """
        Exact patch releases for nox interpreter pinning.
        """
        pins: list[str] = []
        for version in self.versions:
            patch = self.patch_overrides.get(
                version, DEFAULT_PATCH_VERSIONS.get(version)
            )
            if patch is None:
                raise ValueError(
                    f"No known patch release for Python {version[0]}.{version[1]}; "
                    f"pass patch_overrides={{{version}: '<release>'}} or update pyprojkit"
                )
            pins.append(patch)
        return pins
