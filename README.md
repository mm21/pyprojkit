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
    - [Tools](#tools)
  - [Syncing `pyproject.toml`](#syncing-pyprojecttoml)
    - [Managed content](#managed-content)
    - [Agent skill](#agent-skill)
    - [Check mode](#check-mode)
  - [doit tasks](#doit-tasks)
  - [nox sessions](#nox-sessions)
  - [Path conventions](#path-conventions)
  - [Sharing configuration](#sharing-configuration)

## Motivation

Every Python project accumulates the same development workflow boilerplate: formatter settings in `pyproject.toml`, supported Python versions repeated across classifiers, `requires-python`, black's `target-version`, and the testing matrix, plus a `dodo.py` and `noxfile.py` that look nearly identical from project to project. Keeping all of it consistent — and keeping it up to date as tools and Python versions evolve — is tedious and error-prone.

PyProjKit centralizes all of this. Each project declares its configuration exactly once in a `pyprojconf.py` at the project root; PyProjKit then:

1. **Syncs `pyproject.toml`**: writes the managed parts (version classifiers, `requires-python`, individual `[tool.*]` fields marked with `# pyprojkit-managed` comments) while preserving everything else, with a `--check` mode for CI.
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
from pyprojkit import ProjectConfig, PythonVersions, RequiresPython

config = ProjectConfig(
    package="my_package",
    requires_python=RequiresPython((3, 12)),
    pinned_python=PythonVersions(3, (12, 14)),
)
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

or run everything at once with `doit preflight`.

## Declaring configuration: `pyprojconf.py`

`pyprojconf.py` must define a module-level `config: ProjectConfig`. `TaskFactory`, `NoxFactory`, and the `pyprojkit` CLI load it automatically from the current directory.

### Python versions

Two separate concepts are configured:

- `requires_python` (required) is the minimum and optional exclusive maximum of interpreters the package can be installed on. It's independent of what you test: if the maximum is omitted it's derived from the minimum as the next major version, so downstream dependency resolution stays future-proof.
- `pinned_python` (optional) is the specific versions you test and target. `PythonVersions` takes the major version and an inclusive range of minor versions; pass a sequence for discontiguous ranges, e.g. `[PythonVersions(3, (8, 9)), PythonVersions(3, (11, 12))]`. Every pinned version must satisfy `requires_python`.

To exclude known-broken minor versions, use `RequiresPython((3, 12), exclude=[(3, 13)])`, which adds `!=3.13.*`.

```python
requires_python = RequiresPython((3, 12))  # requires-python = ">=3.12,<4.0"
pinned_python = PythonVersions(3, (12, 14))
```

`requires_python` drives `requires-python`. `pinned_python` drives:

- Trove classifiers (`Programming Language :: Python :: 3.12`, ...)
- black's `target-version` (`["py312", "py313", "py314"]`)
- mypy's `python_version` (`3.12`, the lowest pinned version)
- nox interpreter pins (`3.12.13`, `3.13.13`, `3.14.6`)

If `pinned_python` is omitted, classifiers, black's `target-version` and mypy's `python_version` are left unmanaged, and creating the nox test session raises a `ConfigError`.

The exact patch releases used for nox come from a mapping bundled with PyProjKit, updated with each release — so updating PyProjKit refreshes the pins across all your projects. Individual projects can override:

```python
pinned_python = PythonVersions(3, (12, 14), patch_overrides={(3, 14): "3.14.7"})
```

### Tools

Tool configurations are grouped by category under `ToolsConfig`. Every category defaults to `None`, so the default configuration is minimal: no tools are managed and only the `sync` task exists. Set a category to enable it:

- `workflow_tool`: `"uv"` or `"poetry"`, the tool managing the project environment; commands in the agent skill are run through it, e.g. `uv run doit test`
- `formatting`: ordered chain of formatters, e.g. autoflake &rarr; isort &rarr; docfmt &rarr; black &rarr; toml-sort
- `test`: pytest + coverage settings
- `doit`, `nox`: cache locations and backends
- `doc`: documentation tools — mkinit and sphinx (each opt-in within)
- `analysis`: mypy + pyright
- `publish`: build/publish output directory
- `skill`: a `pyprojkit-python` [agent skill](https://agentskills.io) generated from the configuration

`create_kitchen_sink_tools()` returns a `ToolsConfig` with everything enabled (except sphinx, which needs project-specific settings). Customize it with `dataclasses.replace`:

```python
from dataclasses import replace

from pyprojkit import (
    AnalysisConfig,
    DocConfig,
    ProjectConfig,
    PythonVersions,
    RequiresPython,
    SphinxConfig,
    create_kitchen_sink_tools,
)

config = ProjectConfig(
    package="my_package",
    requires_python=RequiresPython((3, 12)),
    pinned_python=PythonVersions(3, (12, 14)),
    tools=replace(
        create_kitchen_sink_tools(),
        doc=DocConfig(sphinx=SphinxConfig(copy_env_var="MY_PACKAGE_DOCS_DIR")),
        analysis=None,
    ),
)
```

To tweak a managed value, replace it in the tool's config:

```python
tools=replace(
    create_kitchen_sink_tools(),
    test=TestConfig(pytest=PytestConfig(addopts="-x")),
)
```

Anything PyProjKit doesn't manage — extra keys in managed tables, whole unmanaged tables — is simply edited directly in `pyproject.toml` and left untouched by the sync.

## Syncing `pyproject.toml`

Formatters and other tools read their settings from `pyproject.toml`, so PyProjKit writes them there — `pyproject.toml` remains the single source of truth for the tools themselves, while `pyprojconf.py` is the single source of truth for you.

### Managed content

The sync engine owns:

- A header comment at the top of `pyproject.toml` noting the file is managed (in part) by PyProjKit
- `project.requires-python`
- Python version classifiers (other classifiers are untouched)
- Individual key/value pairs within tool tables, each marked with an inline `# pyprojkit-managed` comment

The marker comment doubles as bookkeeping: a marked field dropped from your configuration is deleted on the next sync, and a table emptied that way is pruned. (The marker is reserved — don't put it on your own fields.)

Everything else — dependencies, `[tool.uv.sources]`, build system, unmanaged fields inside managed tables, whole unmanaged tables, comments — is preserved. Output is normalized with toml-sort using the same settings as the managed `[tool.tomlsort]` table, so syncing and formatting never fight.

Files synced by PyProjKit < 0.4 (whole-table ownership with a `[tool.pyprojkit]` bookkeeping table) are migrated automatically in a single sync.

### Agent skill

PyProjKit generates a `pyprojkit-python` skill in the [Agent Skills](https://agentskills.io) format, usable by any agent which supports it (Claude Code, Codex, Cursor, etc). Its content is derived from your configuration: the Python versions to target, conventions such as placing internal (`_`-prefixed) symbols after public ones of the same kind, and, when `doit` is enabled, a checklist of the workflow tasks you've enabled to run before finishing a task — `doit init` with mkinit, `doit format` with formatting, `doit analysis` with analysis, `doit test` with testing Commands are prefixed with `<workflow_tool> run` when a workflow tool is configured.

```python
tools=replace(ToolsConfig(), skill=SkillConfig())
```

The skill is written to `.claude/skills/pyprojkit-python/SKILL.md` by default; set `SkillConfig.skills_dir` to write it elsewhere, e.g. `skills_dir=".agents/skills"` for agents reading the cross-agent location.

The generated skill file is overwritten on every sync (so it tracks both your configuration and PyProjKit updates) and removed when dropped from the configuration; disable entirely with `skill=None`. The `pyprojkit-` prefix namespaces the skill, so it never collides with your own skills.

### Check mode

Verify a project is in sync without writing (e.g. in CI):

```bash
pyprojkit sync --check
```

Prints a diff and exits nonzero if `pyproject.toml` or the generated skill is out of date.

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
| `init` | Generate `__init__.py` files via mkinit |
| `doc` | Build documentation via sphinx; `--copy` deploys to a directory given by an env var (opt-in) |
| `analysis` | Run mypy (with HTML/cobertura reports) and pyright (opt-in) |
| `preflight` | Run every enabled step (see below) |

The `preflight` task runs every enabled step in order — sync, init, format, analysis, test, badges, nox — continuing past failures, then fails once listing the failed steps. It's meant to be used by developers and CI alike:

```bash
doit preflight             # edit files in place (sync, init, format, badges)
doit preflight --no-test   # skip test, badges and nox
doit preflight --check     # fail if any file would be edited, printing diffs
```

In check mode, the editing steps run on a temporary copy of the project, which is then compared with the original, so the check is exactly "would an edit run change anything" — including interactions between tools, like formatters rewriting files generated by mkinit. Badges are generated from the test results and compared too, so committed badges must be up to date. Check mode is the default when the `CI` environment variable is set, as it is by most CI providers.

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

## Sharing configuration

There is no profile registry: a shared configuration is just a function or global in a module you control, which each project imports.

```python
# in your shared module, e.g. mycompany_config.py
from dataclasses import replace

from pyprojkit import AnalysisConfig, ToolsConfig, create_kitchen_sink_tools


def create_mycompany_tools() -> ToolsConfig:
    return replace(create_kitchen_sink_tools(), analysis=AnalysisConfig())
```

```python
# in each project's pyprojconf.py
from mycompany_config import create_mycompany_tools

from pyprojkit import ProjectConfig, PythonVersions, RequiresPython

config = ProjectConfig(
    package="my_package",
    requires_python=RequiresPython((3, 12)),
    pinned_python=PythonVersions(3, (12, 14)),
    tools=create_mycompany_tools(),
)
```

New formatters are equally pluggable: subclass `BaseFormatterConfig` (declaring the tool's `[tool.X]` table and command line) and include it in a `FormattingConfig` — the sync engine and format task pick it up automatically.
