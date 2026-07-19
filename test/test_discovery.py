from pathlib import Path

import pytest

from pyprojkit import ConfigError, load_config


def test_load(project: Path):
    config = load_config()
    assert config.package == "fixture_pkg"
    assert config.python.versions == [(3, 12), (3, 13)]


def test_load_explicit_root(project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir("/")
    config = load_config(project)
    assert config.package == "fixture_pkg"


def test_missing_file(tmp_path: Path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path)


def test_missing_config_attr(tmp_path: Path):
    (tmp_path / "pyprojconf.py").write_text("x = 1\n")
    with pytest.raises(ConfigError, match="module-level"):
        load_config(tmp_path)


def test_import_error(tmp_path: Path):
    (tmp_path / "pyprojconf.py").write_text("raise RuntimeError('boom')\n")
    with pytest.raises(ConfigError, match="Failed to import"):
        load_config(tmp_path)
