"""
Command-line interface: `pyprojkit sync [--check]`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config.base import ConfigError
from .discovery import load_config
from .sync import sync

__all__ = [
    "main",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pyprojkit", description="Development workflow toolkit"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser(
        "sync", help="Sync pyproject.toml from pyprojconf.py"
    )
    sync_parser.add_argument(
        "--check",
        action="store_true",
        help="Verify pyproject.toml is in sync without writing; exit 1 if not",
    )
    sync_parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Project root (default: current directory)",
    )

    args = parser.parse_args(argv)

    try:
        config = load_config(args.root)
        in_sync = sync(config, args.root, check=args.check)
    except ConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.check and not in_sync:
        print("pyproject.toml is out of sync; run `pyprojkit sync`", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
