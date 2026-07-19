"""
Subprocess helpers for task actions.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], expect_rc: int | set[int] = 0):
    """
    Run command, exiting if the return code is not among the expected ones.

    The current interpreter's bin directory is prepended to `PATH` so tools from the
    active environment are found even if it isn't activated.
    """
    expect_rcs = expect_rc if isinstance(expect_rc, set) else {expect_rc}
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join(
        [str(Path(sys.executable).parent), env.get("PATH", "")]
    )
    print(f"=== Running: {cmd[0]}")
    rc = subprocess.call(cmd, env=env)
    if rc not in expect_rcs:
        sys.exit(f"{cmd[0]} failed: rc={rc}, cmd={cmd}")


def cleanup_dir(output_dir: Path | str):
    """
    Remove directory if it exists.
    """
    path = Path(output_dir)
    if path.exists():
        shutil.rmtree(path)
