import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Callable

import pytest
from doit.action import PythonAction
from doit.exceptions import TaskFailed
from doit.loader import load_tasks
from doit.task import Task

from pyprojkit import (
    AnalysisConfig,
    ConfigError,
    NoxConfig,
    ProjectConfig,
    TaskFactory,
    ToolsConfig,
    tasks,
)


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
        "task_preflight",
    }


def test_minimal_tasks(project: Path, config: ProjectConfig):
    minimal = replace(config, tools=ToolsConfig())
    assert set(TaskFactory(config=minimal).create_all_tasks()) == {
        "task_sync",
        "task_preflight",
    }
    with pytest.raises(ConfigError, match="tools.formatting"):
        TaskFactory(config=minimal).create_format_task()


def test_format_task(project: Path):
    factory = TaskFactory()
    task = factory.create_format_task()()
    assert task.name == "format"

    # actions in formatter order
    cmds = [_py_action(action).args[0] for action in task.actions]
    assert [cmd[0] for cmd in cmds] == [
        "autoflake",
        "isort",
        "docfmt",
        "black",
        "toml-sort",
    ]

    # docfmt returns 0 when it writes changes in-place
    assert _py_action(task.actions[2]).args[1] == {0}

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


def test_opt_in_tasks(
    project: Path, config: ProjectConfig, monkeypatch: pytest.MonkeyPatch
):
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
    cmds = _run_task(task, monkeypatch)
    assert [cmd[0] for cmd in cmds] == ["mypy", "pyright"]
    assert cmds[0][-2:] == ["src", "test"]
    assert cmds[1][-2:] == ["src", "test"]
    # top-level files are included
    assert any(arg.endswith("pyprojconf.py") for arg in cmds[1])

    # override packages location
    flat = replace(enabled, packages_dir=".")
    factory = TaskFactory(config=flat)
    task = factory.create_init_task()()
    assert _py_action(task.actions[0]).args[0][:2] == ["mkinit", "fixture_pkg"]


def test_preflight_task(
    project: Path,
    config: ProjectConfig,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    # record commands instead of running them, failing format and pytest
    cmds = _fake_run(monkeypatch, fail={"isort", "pytest"})
    monkeypatch.setattr(tasks, "sync", lambda *_: None)
    monkeypatch.setattr(tasks, "_normalize_svg", lambda _: None)

    task_creator = TaskFactory(config=_enable_all(config)).create_preflight_task()
    task = task_creator(check=False, no_test=False)
    assert task.name == "preflight"

    # all steps run in order despite failures, which are reported at the end
    result = _run_preflight(task)
    assert isinstance(result, TaskFailed)
    assert result.message == (
        "Failed steps:\n- format: isort failed\n- test: pytest failed"
    )
    assert [cmd for cmd, _ in cmds] == [
        "mkinit",
        "autoflake",
        "isort",  # remaining formatters skipped
        "mypy",
        "pyright",
        "pytest",
        "genbadge",
        "genbadge",
        "nox",
    ]

    # edits made in place
    assert {cwd for _, cwd in cmds} == {project}

    # test steps skipped
    cmds.clear()
    result = _run_preflight(task_creator(check=False, no_test=True))
    assert isinstance(result, TaskFailed)
    assert result.message == "Failed steps:\n- format: isort failed"
    assert [cmd for cmd, _ in cmds] == [
        "mkinit",
        "autoflake",
        "isort",
        "mypy",
        "pyright",
    ]
    assert "Skipping: nox" in capsys.readouterr().out


def test_preflight_check(
    project: Path,
    config: ProjectConfig,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    init_path = Path("src/fixture_pkg/__init__.py")
    sync_path = Path(".claude/skills/pyprojkit-python/SKILL.md")

    def format_init(cmd: list[str]):
        init_path.write_text("x = 1\n")

    def write_results(cmd: list[str]):
        for path in (
            Path("__out__/test/junit.xml"),
            Path("__out__/test/cov/coverage.xml"),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("<results/>")

    def write_badge(cmd: list[str]):
        # reads results from the test step
        assert Path(cmd[cmd.index("-i") + 1]).is_file()
        Path(cmd[cmd.index("-o") + 1]).write_text("<svg/>")

    cmds = _fake_run(
        monkeypatch,
        effects={
            "black": format_init,
            "pytest": write_results,
            "genbadge": write_badge,
        },
    )
    monkeypatch.setattr(tasks, "_normalize_svg", lambda _: None)
    task_creator = TaskFactory(config=_enable_all(config)).create_preflight_task()
    original = _snapshot(project)

    # edits made in sandbox and compared, real sync included
    result = _run_preflight(task_creator(check=True, no_test=False))
    assert isinstance(result, TaskFailed)
    assert result.message == (
        "Failed steps:\n- check: would change "
        f"{sync_path.as_posix()}, badges/cov.svg, badges/tests.svg, pyproject.toml, "
        f"{init_path.as_posix()}"
    )
    out = capsys.readouterr().out
    assert f"+++ {init_path.as_posix()} (edited)\n" in out
    assert "\n+<svg/>\n" in out  # no trailing newline

    # project untouched besides test results; edits made elsewhere, others in project
    assert {
        p: c for p, c in _snapshot(project).items() if "__out__" not in p.parts
    } == original
    cwds = {cmd: cwd for cmd, cwd in cmds}
    assert cwds["mkinit"] != project
    assert cwds["black"] == cwds["genbadge"] == cwds["mkinit"]
    assert cwds["mypy"] == cwds["pytest"] == cwds["nox"] == project

    # passes once edits are applied
    _run_preflight(task_creator(check=False, no_test=False))
    capsys.readouterr()
    assert _run_preflight(task_creator(check=True, no_test=False)) is None
    assert "would change" not in capsys.readouterr().out


@pytest.mark.parametrize(
    ("args", "env", "params"),
    [
        (["preflight"], None, (False, False)),
        (["preflight", "--check", "--no-test"], None, (True, True)),
        (["preflight"], "true", (True, False)),
        (["preflight"], "false", (False, False)),
    ],
)
def test_preflight_params(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    args: list[str],
    env: str | None,
    params: tuple[bool, bool],
):
    """
    doit passes command-line parameters to the `preflight` task, with check mode
    defaulting to whether running in CI.
    """
    if env is None:
        monkeypatch.delenv("CI", raising=False)
    else:
        monkeypatch.setenv("CI", env)

    namespace = TaskFactory().create_all_tasks()
    loaded = {task.name: task for task in load_tasks(namespace, args=args)}
    assert _py_action(loaded["preflight"].actions[0]).args == params


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
    assert {
        "sync",
        "format",
        "test",
        "badges",
        "publish",
        "init",
        "preflight",
    } <= listed


def _enable_all(config: ProjectConfig) -> ProjectConfig:
    return replace(
        config,
        tools=replace(config.tools, analysis=AnalysisConfig(), nox=NoxConfig()),
    )


def _fake_run(
    monkeypatch: pytest.MonkeyPatch,
    fail: set[str] | None = None,
    effects: dict[str, Callable[[list[str]], None]] | None = None,
) -> list[tuple[str, Path]]:
    """
    Record commands with their working directory instead of running them, failing or
    applying effects for the given commands.
    """
    cmds: list[tuple[str, Path]] = []

    def run(cmd: list[str], expect_rc: int | set[int] = 0):
        cmds.append((cmd[0], Path.cwd()))
        if effects and cmd[0] in effects:
            effects[cmd[0]](cmd)
        if fail and cmd[0] in fail:
            sys.exit(f"{cmd[0]} failed")

    monkeypatch.setattr(tasks, "run", run)
    return cmds


def _run_preflight(task: Task) -> object:
    """
    Run task's action through doit, which replaces stdout while running it.
    """
    task.init_options()
    return _py_action(task.actions[0]).execute(out=sys.stdout)


def _snapshot(root: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _run_task(task: Task, monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """
    Run task's actions, recording commands instead of running them.
    """
    cmds: list[list[str]] = []
    monkeypatch.setattr(tasks, "run", lambda cmd, expect_rc=0: cmds.append(cmd))
    for action in task.actions:
        action = _py_action(action)
        action.py_callable(*action.args, **action.kwargs)
    return cmds


def _py_action(action: object) -> PythonAction:
    assert isinstance(action, PythonAction)
    return action
