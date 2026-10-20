from dataclasses import fields, replace

import pytest

from pyprojkit import (
    AutoflakeConfig,
    BlackConfig,
    DocfmtConfig,
    IsortConfig,
    ProjectConfig,
    PythonVersions,
    PythonVersionSet,
    RequiresPython,
    TomlSortConfig,
    ToolsConfig,
    create_kitchen_sink_tools,
)


def test_python_versions():
    versions = PythonVersionSet.from_config(PythonVersions(3, (12, 14)))

    assert versions.versions == [(3, 12), (3, 13), (3, 14)]
    assert versions.patch((3, 12)).startswith("3.12.")


def test_python_versions_invalid():
    with pytest.raises(ValueError):
        PythonVersions(3, (14, 12))


def test_pins_override_and_missing():
    python = PythonVersions(3, (12, 12), patch_overrides={(3, 12): "3.12.99"})
    assert PythonVersionSet((python,)).patch((3, 12)) == "3.12.99"

    with pytest.raises(ValueError, match="No known patch release"):
        PythonVersionSet((PythonVersions(3, (10, 10)),)).patch((3, 10))


def test_default_minimal():
    tools = ToolsConfig()
    assert all(getattr(tools, f.name) is None for f in fields(tools))


def test_kitchen_sink():
    tools = create_kitchen_sink_tools()
    assert tools.formatting is not None
    names = [type(f).__name__ for f in tools.formatting.formatters]
    assert names == [
        "AutoflakeConfig",
        "IsortConfig",
        "DocfmtConfig",
        "BlackConfig",
        "TomlSortConfig",
    ]
    assert tools.doc is not None and tools.doc.mkinit is not None
    assert tools.doc.sphinx is None
    assert all(
        getattr(tools, f.name) is not None for f in fields(tools) if f.name != "doc"
    )


def test_custom_profile():
    tools = replace(create_kitchen_sink_tools(), analysis=None)
    assert tools.analysis is None
    assert tools.test is not None


def test_to_toml_key_mapping(config: ProjectConfig):
    autoflake = AutoflakeConfig().to_toml(config)
    assert autoflake == {
        "in_place": True,
        "recursive": True,
        "remove-all-unused-imports": True,
        "remove-unused-variables": True,
    }

    black = BlackConfig().to_toml(config)
    assert black == {"quiet": True, "target-version": ["py312", "py313"]}

    tomlsort = TomlSortConfig().to_toml(config)
    assert tomlsort == {
        "sort_first": ["project", "dependency-groups", "build-system"],
        "sort_table_keys": True,
        "spaces_before_inline_comment": 2,
    }


def test_to_toml_none_omitted(config: ProjectConfig):
    isort = IsortConfig(profile=None)
    assert isort.to_toml(config) == {"quiet": True}


def test_formatter_commands():
    py, toml = ["a.py", "src"], ["pyproject.toml"]
    assert AutoflakeConfig().command(py, toml) == ["autoflake", "a.py", "src"]
    assert TomlSortConfig().command(py, toml) == ["toml-sort", "-i", "pyproject.toml"]
    assert DocfmtConfig().command(py, toml) == ["docfmt", "a.py", "src"]
    assert DocfmtConfig().expect_rc == {0}


def test_requires_python():
    assert RequiresPython((3, 12)).specifier == ">=3.12,<4.0"
    assert RequiresPython((3, 12), (3, 15)).specifier == ">=3.12,<3.15"
    assert RequiresPython((3, 12)).contains((3, 99))

    excluded = RequiresPython((3, 12), exclude=[(3, 14), (3, 13)])
    assert excluded.specifier == ">=3.12,<4.0,!=3.13.*,!=3.14.*"
    assert not excluded.contains((3, 13))
    with pytest.raises(ValueError):
        RequiresPython((3, 12), (3, 12))


def test_pinned_versions_outside_requires_python():
    with pytest.raises(ValueError):
        ProjectConfig(
            package="p",
            requires_python=RequiresPython((3, 13)),
            pinned_python=PythonVersions(3, (12, 14)),
        )


def test_python_version_set_discontiguous():
    config = ProjectConfig(
        package="p",
        requires_python=RequiresPython((2, 10), (4, 0)),
        pinned_python=[PythonVersions(2, (10, 12)), PythonVersions(3, (1, 3))],
    )
    assert config.requires_python.specifier == ">=2.10,<4.0"
    versions = config.pinned_versions
    assert versions is not None
    assert versions.versions == [(2, 10), (2, 11), (2, 12), (3, 1), (3, 2), (3, 3)]


def test_pinned_python_optional():
    config = ProjectConfig(package="p", requires_python=RequiresPython((3, 12)))
    assert config.pinned_versions is None
