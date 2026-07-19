"""
Shared path conventions for caches, artifacts, and badges.

These are used by config defaults, doit task factories, and nox session factories alike,
so they must not be coupled to any one tool.
"""

from pathlib import Path

# caches
CACHE_PATH = Path("__cache__")
DOIT_DB_PATH = CACHE_PATH / ".doit.db"
COVERAGE_DATA_PATH = CACHE_PATH / ".coverage"
PYTEST_CACHE_PATH = CACHE_PATH / "pytest"
NOX_ENVDIR_PATH = CACHE_PATH / "nox"

# artifact output
OUT_PATH = Path("__out__")

# test coverage results
TESTS_PATH = OUT_PATH / "test"
JUNIT_PATH = TESTS_PATH / "junit.xml"
COV_PATH = TESTS_PATH / "cov"
COV_HTML_PATH = COV_PATH / "html"
COV_XML_PATH = COV_PATH / "coverage.xml"

# documentation
DOC_PATH = OUT_PATH / "doc"
DOC_HTML_PATH = DOC_PATH / "html"

# static analysis results
ANALYSIS_PATH = OUT_PATH / "analysis"
MYPY_PATH = ANALYSIS_PATH / "mypy"
MYPY_HTML_PATH = MYPY_PATH / "html"
MYPY_XML_PATH = MYPY_PATH / "xml"

# build/publish artifacts
UV_PATH = OUT_PATH / "uv"

# badges output
BADGES_PATH = Path("badges")
PYTEST_BADGE_PATH = BADGES_PATH / "tests.svg"
COV_BADGE_PATH = BADGES_PATH / "cov.svg"
