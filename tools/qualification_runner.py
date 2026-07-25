#!/usr/bin/env python3
"""Command-line entry point for the deterministic qualification runner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.qualification import run_qualification


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconcile one C qualification result source and write reports."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--binary", type=Path, help="Execute this C test executable once")
    source.add_argument(
        "--c-results",
        type=Path,
        help="Read an already captured C result JSON document",
    )
    parser.add_argument(
        "--binary-exit-code",
        type=int,
        default=None,
        help="Captured binary exit status for --c-results (default: 0)",
    )
    parser.add_argument(
        "--requirements",
        type=Path,
        default=Path("requirements/requirements.json"),
    )
    parser.add_argument(
        "--procedures",
        type=Path,
        default=Path("qualification/test_procedures.json"),
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("reports/qualification_report.json"),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path("reports/qualification_report.md"),
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    if args.binary is not None and args.binary_exit_code is not None:
        parser.error("--binary-exit-code is valid only with --c-results")
    if args.binary_exit_code is not None and args.binary_exit_code < 0:
        parser.error("--binary-exit-code must be a non-negative integer")
    if args.binary_exit_code is None:
        args.binary_exit_code = 0
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    exit_code, report = run_qualification(
        binary=args.binary,
        c_results_path=args.c_results,
        binary_exit_code=args.binary_exit_code,
        requirements_path=args.requirements,
        procedures_path=args.procedures,
        json_output=args.json_output,
        markdown_output=args.markdown_output,
        timeout_seconds=args.timeout,
    )
    print(
        f"{report['result']}: "
        f"{report['summary']['c_cases_passed']}/{report['summary']['c_cases_total']} "
        f"C cases passed; {report['summary']['issues']} findings"
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
