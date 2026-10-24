"""
Python version handling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

__all__ = [
    "DEFAULT_PATCH_VERSIONS",
    "PythonVersions",
    "PythonVersionSet",
    "RequiresPython",
]

DEFAULT_PATCH_VERSIONS: dict[tuple[int, int], str] = {
    (3, 12): "3.12.15",
    (3, 13): "3.13.17",
    (3, 14): "3.14.9",
    (3, 15): "3.15.1",
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

    Used for the versions which are pinned, i.e. tested and targeted by tools.
    """

    major: int
    """
    Major version, e.g. `3`.
    """

    minors: tuple[int, int]
    """
    Minor version range as (min, max), both inclusive, e.g. `(12, 14)`.
    """

    patch_overrides: Mapping[tuple[int, int], str] = field(default_factory=dict)
    """
    Overrides for patch releases used to pin nox sessions, keyed by (major, minor).
    """

    def __post_init__(self):
        if self.minors[0] > self.minors[1]:
            raise ValueError(f"Invalid minor version range: {self.minors}")

    @property
    def versions(self) -> list[tuple[int, int]]:
        """
        All supported (major, minor) versions.
        """
        return [
            (self.major, minor) for minor in range(self.minors[0], self.minors[1] + 1)
        ]


@dataclass(frozen=True)
class RequiresPython:
    """
    Interpreter versions the package declares it can be installed on, i.e.
    `requires-python`. Independent of the versions that are tested.

    Leaving the upper bound open keeps dependency resolution for downstream packages
    future-proof.
    """

    min: tuple[int, int]
    """
    Minimum supported version as (major, minor), e.g. `(3, 12)`.
    """

    max: tuple[int, int] | None = None
    """
    Exclusive upper bound as (major, minor). If not specified, defaults to the next
    major version after the minimum, e.g. `<4.0` for a minimum of 3.12.
    """

    exclude: Sequence[tuple[int, int]] = ()
    """
    Minor versions to exclude, as (major, minor), e.g. `[(3, 13)]` for `!=3.13.*`.
    """

    def __post_init__(self):
        if self.max is not None and self.max <= self.min:
            raise ValueError(f"Invalid requires-python range: {self.min}, {self.max}")

    @property
    def upper(self) -> tuple[int, int]:
        """
        Exclusive upper bound, derived from the minimum if not specified.
        """
        return self.max or (self.min[0] + 1, 0)

    @property
    def specifier(self) -> str:
        """
        Version specifier for `requires-python`.
        """
        spec = f">={self.min[0]}.{self.min[1]},<{self.upper[0]}.{self.upper[1]}"
        for maj, min in sorted(set(self.exclude)):
            spec += f",!={maj}.{min}.*"
        return spec

    def contains(self, version: tuple[int, int]) -> bool:
        """
        Whether a (major, minor) version satisfies the specifier.
        """
        return self.min <= version < self.upper and version not in self.exclude


@dataclass(frozen=True)
class PythonVersionSet:
    """
    One or more `PythonVersions` ranges, allowing discontiguous support such as 3.8-3.9
    and 3.11-3.12, or ranges spanning major versions such as 2.10-2.12 and 3.1-3.5.

    Exposes the same derived values as `PythonVersions`, aggregated over all ranges.
    """

    ranges: tuple[PythonVersions, ...]
    """
    Supported ranges, in the order given.
    """

    def __post_init__(self):
        if not self.ranges:
            raise ValueError("At least one Python version range is required")

    @classmethod
    def from_config(
        cls, python: PythonVersions | Sequence[PythonVersions]
    ) -> PythonVersionSet:
        """
        Normalize the value of `ProjectConfig.python`.
        """
        if isinstance(python, PythonVersions):
            return cls((python,))
        return cls(tuple(python))

    @property
    def versions(self) -> list[tuple[int, int]]:
        """
        All supported (major, minor) versions, sorted and deduplicated.
        """
        return sorted({v for r in self.ranges for v in r.versions})

    def patch(self, version: tuple[int, int]) -> str:
        """
        Exact patch release for a (major, minor) version, taking overrides from the
        ranges into account.
        """
        for r in self.ranges:
            if version in r.patch_overrides:
                return r.patch_overrides[version]
        patch = DEFAULT_PATCH_VERSIONS.get(version)
        if patch is None:
            raise ValueError(
                f"No known patch release for Python {version[0]}.{version[1]}; "
                f"pass patch_overrides={{{version}: '<release>'}} or update pyprojkit"
            )
        return patch
