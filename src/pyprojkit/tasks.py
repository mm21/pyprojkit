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

import os
import shutil
from pathlib import Path
from typing import Callable

from doit import task_params
from doit.task import Task
from doit.tools import create_folder

from . import _paths
from ._run import cleanup_dir, run
from .config.base import ConfigError
from .config.project import ProjectConfig
from .discovery import load_config
from .sync import sync

__all__ = [
    "TaskFactory",
]

TaskCreator = Callable[..., Task]


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
                for formatter in config.tools.formatting.formatters
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
        out_dir = Path(self._config.tools.publish.out_dir)

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
        mkinit = self._require(self._config.tools.doc.mkinit, "tools.doc.mkinit")
        package = self._config.package

        def task_init() -> Task:
            return Task(
                "init",
                actions=[
                    (run, (["mkinit", f"src/{package}", *mkinit.args],)),
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
        sphinx = self._require(self._config.tools.doc.sphinx, "tools.doc.sphinx")

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
        package = self._config.package

        def task_analysis() -> Task:
            actions = []

            if analysis.mypy:
                actions.append(
                    (
                        run,
                        (
                            [
                                "mypy",
                                "--html-report",
                                str(_paths.MYPY_HTML_PATH),
                                "--cobertura-xml-report",
                                str(_paths.MYPY_XML_PATH),
                                package,
                            ],
                        ),
                    )
                )

            if analysis.pyright:
                actions.append((run, (["pyright", package],)))

            return Task(
                "analysis",
                actions=actions,
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
            "task_format": self.create_format_task(),
            "task_publish": self.create_publish_task(),
        }

        if tools.test:
            creators["task_test"] = self.create_test_task()
            creators["task_badges"] = self.create_badges_task()

        if tools.doc.mkinit:
            creators["task_init"] = self.create_init_task()

        if tools.doc.sphinx:
            creators["task_doc"] = self.create_doc_task()

        if tools.analysis:
            creators["task_analysis"] = self.create_analysis_task()

        return creators

    def _require[T](self, value: T | None, name: str) -> T:
        if value is None:
            raise ConfigError(f"Configuration does not set `{name}`")
        return value
