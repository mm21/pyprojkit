import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from doit.action import PythonAction

from pyprojkit import AnalysisConfig, ConfigError, ProjectConfig, TaskFactory


def test_create_all_tasks(project: Path):
    factory = TaskFactory()
    tasks = factory.create_all_tasks()
    assert set(tasks) == {
        "task_sync",
        "task_format",
        "task_publish",
        "task_test",
        "task_badges",
        "task_init",
    }


def test_format_task(project: Path):
    factory = TaskFactory()
    task = factory.create_format_task()()
    assert task.name == "format"

    # actions in formatter order
    cmds = [_py_action(action).args[0] for action in task.actions]
    assert [cmd[0] for cmd in cmds] == [
        "autoflake",
        "isort",
        "black",
        "docformatter",
        "toml-sort",
    ]

    # docformatter tolerates rc 3
    assert _py_action(task.actions[3]).args[1] == {0, 3}

    # existing dirs and root files aggregated
    autoflake_cmd = cmds[0]
    assert "src" in autoflake_cmd and "test" in autoflake_cmd
    assert str(project / "pyprojconf.py") in autoflake_cmd
    assert cmds[4] == ["toml-sort", "-i", str(project / "pyproject.toml")]


def test_test_task(project: Path):
    task = TaskFactory().create_test_task()()
    assert task.name == "test"
    pytest_cmd = _py_action(task.actions[1]).args[0]
    assert "--cov=fixture_pkg" in pytest_cmd
    assert str(Path("__out__/test/junit.xml")) in " ".join(pytest_cmd)


def test_badges_task(project: Path):
    task = TaskFactory().create_badges_task()()
    assert task.name == "badges"
    assert "badges/tests.svg" in task.targets
    assert "__out__/test/junit.xml" in task.file_dep


def test_publish_task(project: Path):
    task = TaskFactory().create_publish_task()()
    assert task.name == "publish"
    # first action cleans the output dir
    assert _py_action(task.actions[0]).args[0] == Path("__out__/uv")
    build_cmd = _py_action(task.actions[1]).args[0]
    assert build_cmd[:3] == ["uv", "build", "--out-dir"]


def test_opt_in_tasks(project: Path, config: ProjectConfig):
    factory = TaskFactory()

    # analysis not configured
    with pytest.raises(ConfigError, match="tools.analysis"):
        factory.create_analysis_task()

    # sphinx not configured
    with pytest.raises(ConfigError, match="tools.doc.sphinx"):
        factory.create_doc_task()

    # mkinit enabled by default
    task = factory.create_init_task()()
    assert _py_action(task.actions[0]).args[0][:2] == ["mkinit", "src/fixture_pkg"]

    # enable analysis
    enabled = replace(config, tools=replace(config.tools, analysis=AnalysisConfig()))
    task = TaskFactory(config=enabled).create_analysis_task()()
    assert [_py_action(a).args[0][0] for a in task.actions] == ["mypy", "pyright"]


def test_doit_list_smoke(project: Path):
    """
    End-to-end: doit discovers factory-created tasks in a real dodo.py.
    """
    (project / "dodo.py").write_text(
        "from pyprojkit import TaskFactory\n"
        "globals().update(TaskFactory().create_all_tasks())\n"
    )

    env = os.environ.copy()
    src = Path(__file__).parent.parent / "src"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(src), *sys.path]  # make pyprojkit + deps importable
    )

    result = subprocess.run(
        [sys.executable, "-m", "doit", "list"],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    listed = {line.split()[0] for line in result.stdout.splitlines() if line.strip()}
    assert {"sync", "format", "test", "badges", "publish", "init"} <= listed


def _py_action(action: object) -> PythonAction:
    assert isinstance(action, PythonAction)
    return action
