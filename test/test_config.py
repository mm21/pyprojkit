import pytest

from pyprojkit import (
    AutoflakeConfig,
    BlackConfig,
    ConfigError,
    DocformatterConfig,
    FormattingConfig,
    IsortConfig,
    ProjectConfig,
    PythonVersions,
    TomlSortConfig,
    ToolsConfig,
    get_tools_profile,
    register_tools_profile,
)


def test_python_versions():
    python = PythonVersions(3, (12, 14))

    assert python.versions == [(3, 12), (3, 13), (3, 14)]
    assert python.requires_python == ">=3.12,<3.15"
    assert python.classifiers == [
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
    ]
    assert python.black_targets == ["py312", "py313", "py314"]
    assert python.mypy_version == "3.12"
    assert python.pins[0].startswith("3.12.")
    assert len(python.pins) == 3


def test_python_versions_single():
    python = PythonVersions(3, (13, 13))
    assert python.versions == [(3, 13)]
    assert python.requires_python == ">=3.13,<3.14"


def test_python_versions_invalid():
    with pytest.raises(ValueError):
        PythonVersions(3, (14, 12))


def test_pins_override_and_missing():
    python = PythonVersions(3, (12, 12), patch_overrides={(3, 12): "3.12.99"})
    assert python.pins == ["3.12.99"]

    with pytest.raises(ValueError, match="No known patch release"):
        _ = PythonVersions(3, (10, 10)).pins


def test_default_profile():
    tools = ToolsConfig.default()
    names = [type(f).__name__ for f in tools.formatting.formatters]
    assert names == [
        "AutoflakeConfig",
        "IsortConfig",
        "BlackConfig",
        "DocformatterConfig",
        "TomlSortConfig",
    ]
    assert tools.test is not None
    assert tools.doc.mkinit is not None  # enabled by default
    assert tools.doc.sphinx is None
    assert tools.analysis is None


def test_unknown_profile():
    with pytest.raises(ConfigError, match="Unknown tools profile"):
        get_tools_profile("nonexistent")


def test_register_profile():
    register_tools_profile(
        "custom",
        lambda: ToolsConfig(formatting=FormattingConfig(formatters=(BlackConfig(),))),
    )
    tools = get_tools_profile("custom")
    assert len(tools.formatting.formatters) == 1


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
    }


def test_to_toml_none_omitted(config: ProjectConfig):
    isort = IsortConfig(profile=None)
    assert isort.to_toml(config) == {"quiet": True}


def test_formatter_commands():
    py, toml = ["a.py", "src"], ["pyproject.toml"]
    assert AutoflakeConfig().command(py, toml) == ["autoflake", "a.py", "src"]
    assert TomlSortConfig().command(py, toml) == ["toml-sort", "-i", "pyproject.toml"]
    assert DocformatterConfig().expect_rc == {0, 3}
