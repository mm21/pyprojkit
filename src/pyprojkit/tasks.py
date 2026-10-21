"""
`doit` task factories.

Usage in a project's `dodo.py`:

```python
from pyprojkit import TaskFactory

factory = TaskFactory()  # auto-loads ./pyprojconf.py

task_sync = factory.create_sync_task()
task_format = factory.create_format_task()
task_test = factory.create_test_task()
task_badges = factory.create_badges_task()
task_publish = factory.create_publish_task()
```

or equivalently: `globals().update(factory.create_all_tasks())`.
"""

from __future__ import annotations

import contextlib
import difflib
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from doit import task_params
from doit.action import PythonAction
from doit.exceptions import BaseFail, TaskFailed
from doit.task import Task
from doit.tools import create_folder

from . import _paths
from ._run import cleanup_dir, run
from .config.base import ConfigError
from .config.project import ProjectConfig, SkillConfig
from .discovery import load_config
from .skill import SKILL_NAME
from .sync import sync

__all__ = [
    "TaskFactory",
]

type TaskCreator = Callable[..., Task]

type _Action = tuple[Callable[..., Any], Sequence[Any], dict[str, Any]]


def _run_all(commands: list[list[str]]) -> TaskFailed | None:
    """
    Run every command even if an earlier one fails, failing if any did.
    """
    failures: list[str] = []
    for cmd in commands:
        try:
            run(cmd)
        except SystemExit as e:
            failures.append(str(e.code))

    if failures:
        return TaskFailed("\n".join(failures))
    return None


def _run_actions(actions: list[_Action]) -> str | None:
    """
    Run actions in order with doit's semantics, stopping at the first failure.

    :return: Error message upon failure
    """
    for func, args, kwargs in actions:
        try:
            result = func(*args, **kwargs)
        except SystemExit as e:
            return str(e.code)
        except Exception as e:
            return f"{type(e).__name__}: {e}"

        if result is False:
            return "action returned False"
        if isinstance(result, BaseFail):
            return result.message

    return None


def _task_actions(creator: TaskCreator) -> list[_Action]:
    """
    Get the actions of the task created by the given creator.
    """
    return [
        (action.py_callable, action.args, action.kwargs)
        for action in creator().actions
        if isinstance(action, PythonAction)
    ]


def _in_ci() -> bool:
    """
    Check whether running in CI, per the `CI` environment variable set by most CI
    providers.
    """
    return os.environ.get("CI", "").lower() not in ("", "0", "false", "no")


def _populate_sandbox(config: ProjectConfig, root: Path, sandbox: Path):
    """
    Copy the files which preflight steps may edit into the sandbox: root files, format
    paths, the package, badges, and generated skills.
    """
    for path in root.iterdir():
        if path.is_file():
            shutil.copy2(path, sandbox / path.name)

    skills_dirs = {SkillConfig().skills_dir}
    if skill := config.tools.skill:
        skills_dirs.add(skill.skills_dir)

    dirs = [
        *(Path(p) for p in config.format_paths),
        config.package_path,
        _paths.BADGES_PATH,
        *(Path(d) / SKILL_NAME for d in skills_dirs),
    ]

    # sorted so parents come first and nested dirs are skipped
    copied: list[Path] = []
    for rel in sorted(dirs):
        if any(rel.is_relative_to(c) for c in copied) or not (root / rel).is_dir():
            continue
        shutil.copytree(
            root / rel, sandbox / rel, ignore=shutil.ignore_patterns("__pycache__")
        )
        copied.append(rel)


def _snapshot(root: Path) -> dict[str, bytes]:
    """
    Get the contents of all files under the given root, keyed by relative path,
    excluding caches and outputs.
    """
    excluded = {_paths.CACHE_PATH, _paths.OUT_PATH}
    return {
        rel.as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and "__pycache__" not in (rel := path.relative_to(root)).parts
        and Path(rel.parts[0]) not in excluded
    }


def _compare(old: dict[str, bytes], new: dict[str, bytes]) -> list[str]:
    """
    Print a diff of each changed file, returning their paths.
    """
    changed = sorted(p for p in old.keys() | new.keys() if old.get(p) != new.get(p))
    for path in changed:
        diff = difflib.unified_diff(
            old.get(path, b"").decode(errors="replace").splitlines(keepends=True),
            new.get(path, b"").decode(errors="replace").splitlines(keepends=True),
            fromfile=f"{path} (on disk)",
            tofile=f"{path} (edited)",
        )
        # terminate lines lacking a newline (at end of file) so they don't run together
        print("".join(line.rstrip("\n") + "\n" for line in diff), end="", flush=True)
    return changed


def _normalize_svg(path: Path | str):
    """
    Rewrite SVG with attributes sorted, as genbadge doesn't order them
    deterministically.
    """
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    tree = ET.parse(path)
    for elem in tree.iter():
        attrib = sorted(elem.attrib.items())
        elem.attrib.clear()
        elem.attrib.update(attrib)
    tree.write(path, encoding="unicode")


class TaskFactory:
    """
    Factory for `doit` tasks, configured by the project's `pyprojconf.py`.
    """

    _config: ProjectConfig
    _root: Path

    def __init__(
        self,
        config: ProjectConfig | None = None,
        root: Path | str | None = None,
    ):
        self._root = Path(root) if root else Path.cwd()
        self._config = config or load_config(self._root)
        _paths.CACHE_PATH.mkdir(parents=True, exist_ok=True)

    def create_sync_task(self) -> TaskCreator:
        """
        Create `sync` task which updates `pyproject.toml` from `pyprojconf.py`.
        """
        config, root = self._config, self._root

        def task_sync() -> Task:
            return Task(
                "sync",
                actions=[(sync, (config, root))],
                targets=[],
                file_dep=[],
                doc="Sync pyproject.toml from pyprojconf.py",
            )

        return task_sync

    def create_format_task(self) -> TaskCreator:
        """
        Create `format` task which runs the configured formatters.
        """
        config, root = self._config, self._root
        formatting = self._require(config.tools.formatting, "tools.formatting")

        def task_format() -> Task:
            # aggregate files to format
            py_paths = [str(p) for p in sorted(root.glob("*.py"))] + [
                path for path in config.format_paths if (root / path).is_dir()
            ]
            toml_paths = [str(p) for p in sorted(root.glob("*.toml"))]

            actions = [
                (
                    run,
                    (formatter.command(py_paths, toml_paths), set(formatter.expect_rc)),
                )
                for formatter in formatting.formatters
            ]

            return Task(
                "format",
                actions=actions,
                targets=[],
                file_dep=[],
                doc="Run formatters",
            )

        return task_format

    def create_test_task(self) -> TaskCreator:
        """
        Create `test` task which runs pytest and generates coverage reports.
        """
        self._require(self._config.tools.test, "tools.test")

        def task_test() -> Task:
            args = [
                "pytest",
                f"--cov={self._config.package}",
                f"--cov-report=html:{_paths.COV_HTML_PATH}",
                f"--cov-report=xml:{_paths.COV_XML_PATH}",
                f"--junitxml={_paths.JUNIT_PATH}",
            ]

            return Task(
                "test",
                actions=[
                    (create_folder, [_paths.COV_PATH]),
                    (run, (args,)),
                ],
                targets=[
                    f"{_paths.COV_HTML_PATH}/index.html",
                    str(_paths.COV_XML_PATH),
                    str(_paths.JUNIT_PATH),
                ],
                file_dep=[],
                clean=[(cleanup_dir, [_paths.TESTS_PATH])],
                doc="Run pytest and generate coverage reports",
            )

        return task_test

    def create_badges_task(self) -> TaskCreator:
        """
        Create `badges` task which generates badges from test results.
        """
        self._require(self._config.tools.test, "tools.test")

        def task_badges() -> Task:
            tests_args = [
                "genbadge",
                "tests",
                "-i",
                str(_paths.JUNIT_PATH),
                "-o",
                str(_paths.PYTEST_BADGE_PATH),
            ]

            cov_args = [
                "genbadge",
                "coverage",
                "-i",
                str(_paths.COV_XML_PATH),
                "-o",
                str(_paths.COV_BADGE_PATH),
            ]

            return Task(
                "badges",
                actions=[
                    (create_folder, [_paths.BADGES_PATH]),
                    (run, (tests_args,)),
                    (run, (cov_args,)),
                    (_normalize_svg, [_paths.PYTEST_BADGE_PATH]),
                    (_normalize_svg, [_paths.COV_BADGE_PATH]),
                ],
                targets=[
                    str(_paths.PYTEST_BADGE_PATH),
                    str(_paths.COV_BADGE_PATH),
                ],
                file_dep=[
                    str(_paths.JUNIT_PATH),
                    str(_paths.COV_XML_PATH),
                ],
                doc="Generate badges from test results",
            )

        return task_badges

    def create_publish_task(self) -> TaskCreator:
        """
        Create `publish` task which builds and publishes the package via uv.
        """
        publish = self._require(self._config.tools.publish, "tools.publish")
        out_dir = Path(publish.out_dir)

        def _publish():
            artifacts = [str(p) for p in sorted(out_dir.iterdir())]
            assert artifacts, f"No build artifacts in {out_dir}"
            run(["uv", "publish", *artifacts])

        def task_publish() -> Task:
            return Task(
                "publish",
                actions=[
                    # clean first so stale artifacts are never published
                    (cleanup_dir, [out_dir]),
                    (run, (["uv", "build", "--out-dir", str(out_dir)],)),
                    (_publish,),
                ],
                targets=[],
                file_dep=[],
                doc="Build and publish package via uv",
            )

        return task_publish

    def create_init_task(self) -> TaskCreator:
        """
        Create `init` task which generates `__init__.py` files using mkinit.
        """
        mkinit = self._require(
            self._config.tools.doc and self._config.tools.doc.mkinit, "tools.doc.mkinit"
        )
        package_path = self._config.package_path

        def task_init() -> Task:
            return Task(
                "init",
                actions=[
                    (run, (["mkinit", str(package_path), *mkinit.args],)),
                ],
                targets=[],
                file_dep=[],
                doc="Generate __init__.py files using mkinit",
            )

        return task_init

    def create_doc_task(self) -> TaskCreator:
        """
        Create `doc` task which builds documentation using sphinx.
        """
        sphinx = self._require(
            self._config.tools.doc and self._config.tools.doc.sphinx, "tools.doc.sphinx"
        )

        def _do_copy(copy: bool):
            if not copy:
                return

            from dotenv import load_dotenv

            load_dotenv()

            assert sphinx.copy_env_var, "No copy_env_var configured"
            dest = os.environ.get(sphinx.copy_env_var)
            assert dest, f"Environment variable {sphinx.copy_env_var} not set"

            dest_path = Path(dest)
            assert dest_path.is_dir()

            # clean destination
            for path in dest_path.iterdir():
                if path.is_file():
                    path.unlink()
                else:
                    shutil.rmtree(path)

            shutil.copytree(_paths.DOC_HTML_PATH, dest, dirs_exist_ok=True)

            print(f"\nCopied: {_paths.DOC_HTML_PATH} -> {dest}")

        @task_params(
            [
                {
                    "name": "copy",
                    "long": "copy",
                    "type": bool,
                    "default": False,
                    "help": "Copy to output folder after build",
                }
            ]
        )
        def task_doc(copy: bool) -> Task:
            args = [
                "sphinx-build",
                "-T",  # show full traceback upon error
                sphinx.source_dir,
                str(_paths.DOC_HTML_PATH),
            ]

            return Task(
                "doc",
                actions=[
                    (create_folder, [_paths.DOC_HTML_PATH]),
                    (run, (args,)),
                    (_do_copy, (copy,)),
                ],
                targets=[
                    f"{_paths.DOC_HTML_PATH}/index.html",
                ],
                file_dep=[],
                clean=[(cleanup_dir, [_paths.DOC_HTML_PATH])],
                doc="Generate documentation",
            )

        return task_doc

    def create_analysis_task(self) -> TaskCreator:
        """
        Create `analysis` task which runs static analysis tools.
        """
        analysis = self._require(self._config.tools.analysis, "tools.analysis")
        package_path = self._config.package_path

        commands: list[list[str]] = []

        if analysis.mypy:
            commands.append(
                [
                    "mypy",
                    "--html-report",
                    str(_paths.MYPY_HTML_PATH),
                    "--cobertura-xml-report",
                    str(_paths.MYPY_XML_PATH),
                    str(package_path),
                ]
            )

        if analysis.pyright:
            commands.append(["pyright", str(package_path)])

        def task_analysis() -> Task:
            return Task(
                "analysis",
                actions=[(_run_all, (commands,))],
                targets=[],
                file_dep=[],
                doc="Run static analysis tools",
            )

        return task_analysis

    def create_all_tasks(self) -> dict[str, TaskCreator]:
        """
        Create all tasks enabled by the configuration, keyed by `task_<name>` suitable
        for `globals().update(...)` in `dodo.py`.
        """
        tools = self._config.tools

        creators: dict[str, TaskCreator] = {
            "task_sync": self.create_sync_task(),
        }

        if tools.formatting:
            creators["task_format"] = self.create_format_task()

        if tools.publish:
            creators["task_publish"] = self.create_publish_task()

        if tools.test:
            creators["task_test"] = self.create_test_task()
            creators["task_badges"] = self.create_badges_task()

        if tools.doc and tools.doc.mkinit:
            creators["task_init"] = self.create_init_task()

        if tools.doc and tools.doc.sphinx:
            creators["task_doc"] = self.create_doc_task()

        if tools.analysis:
            creators["task_analysis"] = self.create_analysis_task()

        creators["task_preflight"] = self.create_preflight_task()

        return creators

    def create_preflight_task(self) -> TaskCreator:
        """
        Create `preflight` task which runs every enabled step: sync, init, format,
        analysis, test, badges, and nox.

        All steps run even if earlier ones fail; the task then fails once, listing the
        failed steps. Pass `--no-test` to skip the test steps (test, badges, nox).

        By default, steps which edit files (sync, init, format, badges) do so in place.
        Pass `--check` (the default when the `CI` environment variable is set) to
        instead run them on a temporary copy of the project and fail if any file would
        change.
        """
        config, tools = self._config, self._config.tools

        # in run order; actions are created lazily so each step sees the effects of
        # previous ones, e.g. files generated by init
        steps: list[_Step] = [
            _Step("sync", lambda f: _task_actions(f.create_sync_task()), edits=True),
        ]

        if tools.doc and tools.doc.mkinit:
            steps.append(
                _Step("init", lambda f: _task_actions(f.create_init_task()), edits=True)
            )

        if tools.formatting:
            steps.append(
                _Step(
                    "format",
                    lambda f: _task_actions(f.create_format_task()),
                    edits=True,
                )
            )

        if tools.analysis:
            steps.append(
                _Step("analysis", lambda f: _task_actions(f.create_analysis_task()))
            )

        if tools.test:
            steps.append(
                _Step("test", lambda f: _task_actions(f.create_test_task()), test=True)
            )
            steps.append(
                _Step(
                    "badges",
                    lambda f: _task_actions(f.create_badges_task()),
                    edits=True,
                    test=True,
                    inputs=(_paths.JUNIT_PATH, _paths.COV_XML_PATH),
                )
            )

            if tools.nox and config.pinned_versions is not None:
                steps.append(_Step("nox", lambda _: [(run, (["nox"],), {})], test=True))

        def _preflight(check: bool, no_test: bool) -> TaskFailed | None:
            if check:
                with tempfile.TemporaryDirectory() as tmp:
                    return self._run_preflight(steps, no_test, Path(tmp))
            return self._run_preflight(steps, no_test, None)

        @task_params(
            [
                {
                    "name": "check",
                    "long": "check",
                    "type": bool,
                    "default": _in_ci(),
                    "help": "Fail if any file would be edited, instead of editing it "
                    "(default when CI is set)",
                },
                {
                    "name": "no_test",
                    "long": "no-test",
                    "type": bool,
                    "default": False,
                    "help": "Skip test steps (test, badges, nox)",
                },
            ]
        )
        def task_preflight(check: bool = False, no_test: bool = False) -> Task:
            return Task(
                "preflight",
                actions=[(_preflight, (check, no_test))],
                targets=[],
                file_dep=[],
                verbosity=2,
                doc="Run all development workflow steps, reporting failures at the end",
            )

        return task_preflight

    def _run_preflight(
        self, steps: list[_Step], no_test: bool, sandbox: Path | None
    ) -> TaskFailed | None:
        """
        Run preflight steps, editing files in the given sandbox (check mode) if any.
        """
        failures: list[str] = []

        def record(name: str, error: str):
            print(f"##### Failed: {name}: {error}", flush=True)
            failures.append(f"{name}: {error}")

        # in check mode, edits are made in the sandbox and compared once all steps have
        # run, as a later step may undo an earlier one's changes (e.g. format reformats
        # files generated by init)
        sandbox_factory: TaskFactory | None = None
        original: dict[str, bytes] = {}
        if sandbox is not None:
            _populate_sandbox(self._config, self._root, sandbox)
            sandbox_factory = TaskFactory(config=self._config, root=sandbox)
            original = _snapshot(sandbox)

        for step in steps:
            if no_test and step.test:
                print(f"##### Skipping: {step.name}", flush=True)
                continue

            print(f"##### Step: {step.name}", flush=True)
            if sandbox_factory is not None and step.edits:
                assert sandbox is not None
                for path in step.inputs:
                    if (self._root / path).is_file():
                        (sandbox / path).parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(self._root / path, sandbox / path)
                with contextlib.chdir(sandbox):
                    error = _run_actions(step.get_actions(sandbox_factory))
            else:
                error = _run_actions(step.get_actions(self))

            if error is not None:
                record(step.name, error)

        if sandbox is not None:
            print("##### Check: comparing edits", flush=True)
            if changed := _compare(original, _snapshot(sandbox)):
                record("check", "would change " + ", ".join(changed))

        print()
        if failures:
            return TaskFailed("Failed steps:\n" + "\n".join(f"- {f}" for f in failures))

        print("##### All steps passed")
        return None

    def _require[T](self, value: T | None, name: str) -> T:
        if value is None:
            raise ConfigError(f"Configuration does not set `{name}`")
        return value


@dataclass(frozen=True)
class _Step:
    """
    Step of the `preflight` task.
    """

    name: str

    get_actions: Callable[[TaskFactory], list[_Action]]
    """
    Get the step's actions from a factory, which is rooted at the sandbox for steps
    which edit files in check mode.
    """

    edits: bool = False
    """
    Whether the step edits files.
    """

    test: bool = False
    """
    Whether the step is skipped with `--no-test`.
    """

    inputs: tuple[Path, ...] = ()
    """
    Files the step reads which earlier steps write to the project, copied into the
    sandbox in check mode.
    """
