#!/usr/bin/env python3
"""Validate requirement/procedure/C-case traceability without running a binary."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.qualification import InputValidationError, check_traceability


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check that all requirements, procedures, and C cases map exactly."
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
    parser.add_argument("--c-results", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        issues = check_traceability(
            requirements_path=args.requirements,
            procedures_path=args.procedures,
            c_results_path=args.c_results,
        )
    except InputValidationError as error:
        issues = error.issues

    if issues:
        for issue in issues:
            subject = f" [{issue.subject_id}]" if issue.subject_id else ""
            print(f"{issue.code}{subject}: {issue.message}", file=sys.stderr)
        return 1
    print("PASS: requirements, procedures, and C cases are fully traceable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
