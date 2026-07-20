# PyProjKit

Development workflow toolkit for Python projects

[![Python versions](https://img.shields.io/pypi/pyversions/pyprojkit.svg)](https://pypi.org/project/pyprojkit)
[![PyPI](https://img.shields.io/pypi/v/pyprojkit?color=%2334D058&label=pypi%20package)](https://pypi.org/project/pyprojkit)
[![Tests](./badges/tests.svg?dummy=8484744)]()
[![Coverage](./badges/cov.svg?dummy=8484744)]()
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

- [PyProjKit](#pyprojkit)
  - [Motivation](#motivation)
  - [Getting started](#getting-started)
  - [Declaring configuration: `pyprojconf.py`](#declaring-configuration-pyprojconfpy)
    - [Python versions](#python-versions)
    - [Tools and profiles](#tools-and-profiles)
  - [Syncing `pyproject.toml`](#syncing-pyprojecttoml)
    - [Managed content](#managed-content)
    - [Check mode](#check-mode)
  - [doit tasks](#doit-tasks)
  - [nox sessions](#nox-sessions)
  - [Path conventions](#path-conventions)
  - [Custom profiles](#custom-profiles)

## Motivation

Every Python project accumulates the same development workflow boilerplate: formatter settings in `pyproject.toml`, supported Python versions repeated across classifiers, `requires-python`, black's `target-version`, and the testing matrix, plus a `dodo.py` and `noxfile.py` that look nearly identical from project to project. Keeping all of it consistent — and keeping it up to date as tools and Python versions evolve — is tedious and error-prone.

PyProjKit centralizes all of this. Each project declares its configuration exactly once in a `pyprojconf.py` at the project root; PyProjKit then:

1. **Syncs `pyproject.toml`**: writes the managed parts (version classifiers, `requires-python`, `[tool.*]` tables) while preserving everything else, with a `--check` mode for CI.
2. **Provides `doit` task factories**: format, test, badges, publish, and more, pre-wired to sensible conventions.
3. **Provides `nox` session factories**: a test session across all supported Python versions, pinned to exact patch releases.

Supported Python versions are declared once and drive everything: classifiers, `requires-python`, black's `target-version`, mypy's `python_version`, and the nox interpreter matrix.

## Getting started

Install from PyPI:

```bash
pip install pyprojkit
```

Or add it to your project's dev dependencies (formatter, test, and analysis tools are available as extras):

```toml
[dependency-groups]
dev = [
  "pyprojkit[all]"
]
```

Then drop three small files into your project root.

`pyprojconf.py`:

```python
from pyprojkit import ProjectConfig, PythonVersions

config = ProjectConfig(package="my_package", python=PythonVersions(3, (12, 14)))
```

`dodo.py`:

```python
from pyprojkit import TaskFactory

globals().update(TaskFactory().create_all_tasks())
```

`noxfile.py`:

```python
from pyprojkit import NoxFactory

test = NoxFactory().create_test_session()
```

Then sync your `pyproject.toml` and run your workflow:

```bash
doit sync    # or: pyprojkit sync
doit format
doit test
doit badges
nox
```

## Declaring configuration: `pyprojconf.py`

`pyprojconf.py` must define a module-level `config: ProjectConfig`. `TaskFactory`, `NoxFactory`, and the `pyprojkit` CLI load it automatically from the current directory.

### Python versions

`PythonVersions` takes the major version and an inclusive range of minor versions — only versions you explicitly support (i.e. test against):

```python
python = PythonVersions(3, (12, 14))
```

This single declaration drives:

- `requires-python` (`>=3.12,<3.15`)
- Trove classifiers (`Programming Language :: Python :: 3.12`, ...)
- black's `target-version` (`["py312", "py313", "py314"]`)
- mypy's `python_version` (`3.12`)
- nox interpreter pins (`3.12.13`, `3.13.13`, `3.14.6`)

The exact patch releases used for nox come from a mapping bundled with PyProjKit, updated with each release — so updating PyProjKit refreshes the pins across all your projects. Individual projects can override:

```python
python = PythonVersions(3, (12, 14), patch_overrides={(3, 14): "3.14.7"})
```

### Tools and profiles

Tool configurations are grouped by category under `ToolsConfig`, whose defaults constitute the default *profile*:

- `formatting`: ordered chain of formatters; by default autoflake &rarr; isort &rarr; black &rarr; docformatter &rarr; toml-sort
- `test`: pytest + coverage settings
- `doit`, `nox`: cache locations and backends
- `doc`: documentation tools — mkinit (enabled by default) and sphinx (opt-in)
- `analysis`: mypy + pyright (opt-in)
- `publish`: build/publish output directory

Customize with `dataclasses.replace`:

```python
from dataclasses import replace

from pyprojkit import (
    AnalysisConfig,
    DocConfig,
    ProjectConfig,
    PythonVersions,
    SphinxConfig,
    ToolsConfig,
)

config = ProjectConfig(
    package="my_package",
    python=PythonVersions(3, (12, 14)),
    tools=replace(
        ToolsConfig.default(),
        doc=DocConfig(sphinx=SphinxConfig(copy_env_var="MY_PACKAGE_DOCS_DIR")),
        analysis=AnalysisConfig(),
    ),
)
```

For one-off tweaks to managed tables there's an escape hatch, merged last into the synced output:

```python
tools=replace(
    ToolsConfig.default(),
    tool_overrides={"tool.pytest.ini_options": {"addopts": "-x"}},
)
```

## Syncing `pyproject.toml`

Formatters and other tools read their settings from `pyproject.toml`, so PyProjKit writes them there — `pyproject.toml` remains the single source of truth for the tools themselves, while `pyprojconf.py` is the single source of truth for you.

### Managed content

The sync engine owns:

- `project.requires-python`
- Python version classifiers (other classifiers are untouched)
- One `[tool.X]` table per enabled tool (fully owned; hand edits inside are overwritten)
- `[tool.pyprojkit].managed`: bookkeeping list of owned tables, so a tool dropped from your configuration gets its table cleanly removed on the next sync

Everything else — dependencies, `[tool.uv.sources]`, build system, unmanaged tool tables — is preserved. Output is normalized with toml-sort using the same settings as the managed `[tool.tomlsort]` table, so syncing and formatting never fight.

### Check mode

Verify a project is in sync without writing (e.g. in CI):

```bash
pyprojkit sync --check
```

Prints a diff and exits nonzero if `pyproject.toml` is out of date.

## doit tasks

`TaskFactory` creates `doit` tasks pre-wired to the configuration. Create them selectively:

```python
from pyprojkit import TaskFactory

factory = TaskFactory()

task_sync = factory.create_sync_task()
task_format = factory.create_format_task()
task_test = factory.create_test_task()
task_badges = factory.create_badges_task()
task_publish = factory.create_publish_task()
```

or all at once: `globals().update(factory.create_all_tasks())`, which creates every task enabled by the configuration.

| Task | Description |
| --- | --- |
| `sync` | Update `pyproject.toml` from `pyprojconf.py` |
| `format` | Run the configured formatter chain over the project |
| `test` | Run pytest with coverage (HTML + XML) and JUnit output |
| `badges` | Generate test/coverage badges via genbadge |
| `publish` | Build and publish via uv (output dir is cleaned first, so stale artifacts are never published) |
| `init` | Generate `__init__.py` files via mkinit (enabled by default) |
| `doc` | Build documentation via sphinx; `--copy` deploys to a directory given by an env var (opt-in) |
| `analysis` | Run mypy (with HTML/cobertura reports) and pyright (opt-in) |

The `format` task passes an explicit list of paths to each formatter — root `*.py`/`*.toml` files plus the configured `format_paths` directories that exist (`src`, `test`, `doc`, `examples` by default) — so formatters never wander into `.venv` or other unrelated trees.

## nox sessions

`NoxFactory.create_test_session()` registers a `test` session which, for each pinned interpreter, syncs the project's dev dependency group via uv into the session environment and runs pytest:

```bash
$ nox -l
* test-3.12.13
* test-3.13.13
* test-3.14.6
```

Extra arguments pass through to pytest: `nox -s test-3.12.13 -- -k my_test`.

## Path conventions

All tasks share the same layout:

- `__cache__/`: caches (doit db, pytest cache, coverage data, nox envs)
- `__out__/`: generated artifacts (`test/` coverage + JUnit results, `doc/html`, `analysis/`, `uv/` build artifacts)
- `badges/`: generated badge SVGs
- `src/<package>`: package sources consumed by the `init` and `analysis` tasks; the containing directory is configurable via `ProjectConfig.packages_dir` (default `"src"`)

## Custom profiles

A profile is a named factory for a pre-canned configuration, at two levels: the overall tools profile and the formatting profile it contains. The `"default"` profiles ship with PyProjKit; register your own once and reuse it across projects:

```python
# in your shared module, e.g. mycompany_profiles.py
from dataclasses import replace

from pyprojkit import AnalysisConfig, ToolsConfig, register_tools_profile

register_tools_profile(
    "mycompany",
    lambda: replace(ToolsConfig.default(), analysis=AnalysisConfig()),
)
```

```python
# in each project's pyprojconf.py
import mycompany_profiles  # noqa: F401 -- registers the profile

from pyprojkit import ProjectConfig, PythonVersions, get_tools_profile

config = ProjectConfig(
    package="my_package",
    python=PythonVersions(3, (12, 14)),
    tools=get_tools_profile("mycompany"),
)
```

New formatters are equally pluggable: subclass `BaseFormatterConfig` (declaring the tool's `[tool.X]` table and command line) and include it in a `FormattingConfig` — the sync engine and format task pick it up automatically.
