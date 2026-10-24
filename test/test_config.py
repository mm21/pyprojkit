from dataclasses import fields, replace
from pathlib import Path

import pytest

from pyprojkit import (
    AnalysisConfig,
    AutoflakeConfig,
    BlackConfig,
    ConfigError,
    DocConfig,
    DocfmtConfig,
    FormattingConfig,
    IsortConfig,
    MkinitConfig,
    PackageSpec,
    ProjectConfig,
    PublishConfig,
    PythonVersions,
    PythonVersionSet,
    RequiresPython,
    ResolvedPackage,
    TomlSortConfig,
    ToolsConfig,
    create_recommended_tools,
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
    assert AnalysisConfig() == AnalysisConfig(mypy=None, pyright=None)
    assert DocConfig() == DocConfig(mkinit=None, sphinx=None)
    assert FormattingConfig().formatters == ()
    assert MkinitConfig().args == ()
    assert PublishConfig().out_dir is None


def test_recommended():
    tools = create_recommended_tools()
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
    tools = replace(create_recommended_tools(), analysis=None)
    assert tools.analysis is None
    assert tools.test is not None


def test_to_toml_key_mapping(config: ProjectConfig):
    autoflake = AutoflakeConfig.create_recommended().to_toml(config)
    assert autoflake == {
        "in_place": True,
        "recursive": True,
        "remove-all-unused-imports": True,
        "remove-unused-variables": True,
    }

    black = BlackConfig.create_recommended().to_toml(config)
    assert black == {"quiet": True, "target-version": ["py312", "py313"]}

    tomlsort = TomlSortConfig.create_recommended().to_toml(config)
    assert tomlsort == {
        "sort_first": ["project", "dependency-groups", "build-system"],
        "sort_table_keys": True,
        "spaces_before_inline_comment": 2,
    }


def test_to_toml_none_omitted(config: ProjectConfig):
    isort = IsortConfig(quiet=True)
    assert isort.to_toml(config) == {"quiet": True}


def test_tool_defaults_empty(config: ProjectConfig):
    assert IsortConfig().to_toml(config) == {}
    assert BlackConfig().to_toml(config) == {"target-version": ["py312", "py313"]}
    tools = create_recommended_tools()
    assert tools.test is not None and tools.test.pytest.to_toml(config)


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
            packages="p",
            requires_python=RequiresPython((3, 13)),
            pinned_python=PythonVersions(3, (12, 14)),
        )


def test_python_version_set_discontiguous():
    config = ProjectConfig(
        packages="p",
        requires_python=RequiresPython((2, 10), (4, 0)),
        pinned_python=[PythonVersions(2, (10, 12)), PythonVersions(3, (1, 3))],
    )
    assert config.requires_python.specifier == ">=2.10,<4.0"
    versions = config.pinned_versions
    assert versions is not None
    assert versions.versions == [(2, 10), (2, 11), (2, 12), (3, 1), (3, 2), (3, 3)]


def test_pinned_python_optional():
    config = ProjectConfig(packages="p", requires_python=RequiresPython((3, 12)))
    assert config.pinned_versions is None


def test_packages():
    requires = RequiresPython((3, 12))

    # single str
    config = ProjectConfig(packages="pkg", requires_python=requires)
    assert config.resolved_packages == (
        ResolvedPackage(name="pkg", source_path=Path("src")),
    )
    assert config.resolved_packages[0].path == Path("src/pkg")

    # single spec, flat layout
    config = ProjectConfig(
        packages=PackageSpec("pkg"), source_path=".", requires_python=requires
    )
    assert config.resolved_packages[0].path == Path("pkg")

    # mixed sequence: spec source path overrides the default
    config = ProjectConfig(
        packages=("a", PackageSpec("b"), PackageSpec("c", "lib")),
        requires_python=requires,
    )
    assert [p.path for p in config.resolved_packages] == [
        Path("src/a"),
        Path("src/b"),
        Path("lib/c"),
    ]

    with pytest.raises(ConfigError, match="At least one package"):
        ProjectConfig(packages=(), requires_python=requires)

    with pytest.raises(ConfigError, match="Duplicate packages: a"):
        ProjectConfig(
            packages=("a", PackageSpec("a", source_path="lib")),
            requires_python=requires,
        )


def test_code_paths_glob(tmp_path: Path):
    for d in ("src/a", "lib/b", "test", "src/a/tests", "doc/sub", "examples"):
        (tmp_path / d).mkdir(parents=True)
    for f in ("dodo.py", "noxfile.py", "pyproject.toml", "README.md"):
        (tmp_path / f).write_text("")

    config = ProjectConfig(
        packages=("a", PackageSpec("b", source_path="lib"), "missing"),
        requires_python=RequiresPython((3, 12)),
        test_paths=("test", "src/*/tests"),
        extra_code_paths=("doc", "doc/sub", "*.py", "*.toml"),
    )

    assert config.get_test_paths(tmp_path) == [Path("test"), Path("src/a/tests")]
    # nested and missing paths are dropped; globs are expanded in sorted order
    assert config.get_code_paths(tmp_path) == [
        Path("src/a"),
        Path("lib/b"),
        Path("test"),
        Path("doc"),
        Path("dodo.py"),
        Path("noxfile.py"),
        Path("pyproject.toml"),
    ]


def test_code_paths_flat(tmp_path: Path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "other").mkdir()
    config = ProjectConfig(
        packages="pkg",
        requires_python=RequiresPython((3, 12)),
        source_path=".",
        test_paths=(),
        extra_code_paths=(),
    )
    # flat layout contributes only the package
    assert config.get_code_paths(tmp_path) == [Path("pkg")]


def test_python_version_file_requires_pinned():
    with pytest.raises(ConfigError, match="python_version_file requires pinned_python"):
        ProjectConfig(
            packages="p",
            requires_python=RequiresPython((3, 12)),
            python_version_file=True,
        )
