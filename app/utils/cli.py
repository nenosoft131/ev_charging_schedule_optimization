"""
Command-line interface and JSON I/O.

The CLI is the only entry point that knows how to read files, parse JSON,
configure logging, and translate results into exit codes. The actual
pipeline lives in `app.main.run` and is fully library-callable.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any



__version__ = "0.1.0"
logger = logging.getLogger("ev_scheduler")


# ---------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="schedule",
        description="Generate an EV charging schedule from a JSON forecast.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-i", "--input",
        type=Path,
        default=None,
        help="JSON input file. Reads stdin if omitted.",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="JSON output file. Writes to stdout if omitted.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable info-level logging on stderr.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


# ---------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------

def load_request(path: Path | None) -> dict[str, Any]:
    """Load a JSON request from a file or stdin, with hours pre-normalized."""
    if path is not None:
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    else:
        if sys.stdin.isatty():
            raise SystemExit(
                "No input provided. Pass --input PATH or pipe JSON via stdin. "
                "See --help for examples."
            )
        raw = json.load(sys.stdin)

    return expand_hours(raw)


def expand_hours(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert 'H:MM' hour strings in the forecast to today's ISO timestamps."""
    today = datetime.now(timezone.utc).date()
    for entry in raw.get("forecast", []):
        h = entry.get("hour")
        if isinstance(h, str) and ":" in h and "T" not in h:
            hh, mm = h.split(":")
            entry["hour"] = datetime.combine(
                today, time(int(hh), int(mm))
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
    return raw


def write_result(result: Any, path: Path | None) -> None:
    """Write a JSON result to a file or stdout."""
    text = json.dumps(result, indent=2, default=str)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        logger.info("Wrote result to %s", path)
    else:
        print(text)


def configure_logging(verbose: bool) -> None:
    """Logs go to stderr so stdout stays a clean JSON channel."""
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )



