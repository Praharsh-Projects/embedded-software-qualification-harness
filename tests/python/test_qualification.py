from __future__ import annotations

import json
import io
import stat
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.qualification import (
    EXIT_INPUT_ERROR,
    EXIT_OK,
    EXIT_QUALIFICATION_FAILED,
    InputValidationError,
    check_traceability,
    run_qualification,
)
from tools.qualification_runner import parse_args


class QualificationRunnerTests(unittest.TestCase):
    METADATA = {
        "project": "qualification-runner-tests",
        "version": "9.8.7",
        "baseline": "TEST-BL-9.8.7",
    }

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.requirements = self.root / "requirements.json"
        self.procedures = self.root / "procedures.json"
        self.binary = self.root / "stub_c_tests"
        self.json_report = self.root / "qualification.json"
        self.markdown_report = self.root / "qualification.md"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_json(self, path: Path, value: object) -> None:
        path.write_text(json.dumps(value), encoding="utf-8")

    def write_requirements(self, identifiers: tuple[str, ...] = ("SWR-001", "SWR-002")) -> None:
        self.write_json(
            self.requirements,
            {
                "schema_version": 1,
                **self.METADATA,
                "requirements": [
                    {
                        "id": identifier,
                        "title": f"Requirement {identifier}",
                        "statement": "The software shall behave deterministically.",
                        "verification_methods": ["test", "analysis", "inspection"],
                    }
                    for identifier in identifiers
                ],
            },
        )

    def write_procedures(
        self,
        procedures: list[dict[str, object]] | None = None,
    ) -> None:
        self.write_json(
            self.procedures,
            {
                "schema_version": 1,
                **self.METADATA,
                "test_procedures": procedures
                if procedures is not None
                else [
                    {
                        "id": "QTP-001",
                        "verification_method": "automated_test",
                        "requirement_ids": ["SWR-001"],
                        "c_test_cases": ["C-001"],
                    },
                    {
                        "id": "QTP-002",
                        "verification_method": "test",
                        "requirement_ids": ["SWR-002"],
                        "c_test_cases": ["C-002"],
                    },
                ],
            },
        )

    def write_stub_binary(
        self,
        result: object,
        exit_code: int = 0,
        *,
        include_metadata: bool = True,
    ) -> None:
        if include_metadata and isinstance(result, dict):
            result = {**self.METADATA, **result}
        payload = json.dumps(result)
        script = textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import json
            import sys

            if sys.argv[1:] != ["--json"]:
                raise SystemExit(64)
            print({payload!r})
            raise SystemExit({exit_code})
            """
        )
        self.binary.write_text(script, encoding="utf-8")
        self.binary.chmod(self.binary.stat().st_mode | stat.S_IXUSR)

    def run_subject(self) -> tuple[int, dict[str, object]]:
        return run_qualification(
            binary=self.binary,
            requirements_path=self.requirements,
            procedures_path=self.procedures,
            json_output=self.json_report,
            markdown_output=self.markdown_report,
        )

    def test_success_writes_deterministic_json_and_markdown(self) -> None:
        self.write_requirements()
        self.write_procedures()
        self.write_stub_binary(
            {
                "test_cases": [
                    {"id": "C-002", "passed": True, "name": "upper boundary"},
                    {"id": "C-001", "status": "passed", "name": "nominal"},
                ]
            }
        )

        exit_code, report = self.run_subject()
        first_json = self.json_report.read_bytes()
        first_markdown = self.markdown_report.read_bytes()
        second_exit_code, second_report = self.run_subject()

        self.assertEqual(exit_code, EXIT_OK)
        self.assertEqual(second_exit_code, EXIT_OK)
        self.assertEqual(report, second_report)
        self.assertEqual(first_json, self.json_report.read_bytes())
        self.assertEqual(first_markdown, self.markdown_report.read_bytes())
        self.assertEqual(report["result"], "HOST_PASS")
        self.assertEqual(
            report["evidence_scope"],
            "host-executable qualification cases",
        )
        self.assertEqual(
            report["external_gates"]["arm_inspection"],
            {
                "note": (
                    "ARM inspection remains required for SRS-PLT-001 and the "
                    "ARM portion of SRS-RES-001."
                ),
                "requirement_ids": ["SRS-PLT-001", "SRS-RES-001"],
                "status": "REQUIRED",
            },
        )
        self.assertEqual(
            {key: report[key] for key in ("project", "version", "baseline")},
            self.METADATA,
        )
        self.assertEqual(report["binary_exit_code"], 0)
        markdown = first_markdown.decode("utf-8")
        self.assertIn("# Host-Executable Qualification Report", markdown)
        self.assertIn("**Host-only result:** HOST_PASS", markdown)
        self.assertIn(
            "**Evidence scope:** host-executable qualification cases",
            markdown,
        )
        self.assertIn("- Baseline: TEST-BL-9.8.7", markdown)
        self.assertIn(
            "ARM inspection remains required for SRS-PLT-001 and the ARM "
            "portion of SRS-RES-001.",
            markdown,
        )
        self.assertEqual(report["summary"]["c_cases_passed"], 2)
        self.assertEqual(
            [case["id"] for case in report["c_cases"]],
            ["C-001", "C-002"],
        )

    def test_duplicate_requirement_is_an_input_error(self) -> None:
        self.write_json(
            self.requirements,
            {
                **self.METADATA,
                "requirements": [
                    {"id": "SWR-001"},
                    {"id": "SWR-001"},
                ]
            },
        )
        self.write_procedures(
            [
                {
                    "id": "QTP-001",
                    "method": "test",
                    "requirement_id": "SWR-001",
                    "case_id": "C-001",
                }
            ]
        )
        self.write_stub_binary({"cases": [{"id": "C-001", "status": "PASS"}]})

        exit_code, report = self.run_subject()

        self.assertEqual(exit_code, EXIT_INPUT_ERROR)
        self.assertEqual(report["result"], "FAIL")
        self.assertEqual(report["issues"][0]["code"], "DUPLICATE_REQUIREMENT_ID")
        self.assertTrue(self.json_report.exists())
        self.assertTrue(self.markdown_report.exists())

    def test_unmapped_requirement_fails_traceability(self) -> None:
        self.write_requirements()
        self.write_procedures(
            [
                {
                    "id": "QTP-001",
                    "verification_method": "test",
                    "requirement_ids": ["SWR-001"],
                    "case_ids": ["C-001"],
                }
            ]
        )
        self.write_stub_binary({"cases": [{"id": "C-001", "status": "PASS"}]})

        exit_code, report = self.run_subject()

        self.assertEqual(exit_code, EXIT_QUALIFICATION_FAILED)
        self.assertIn(
            "UNMAPPED_REQUIREMENT",
            {issue["code"] for issue in report["issues"]},
        )

    def test_failed_c_case_and_nonzero_binary_fail_qualification(self) -> None:
        self.write_requirements(("SWR-001",))
        self.write_procedures(
            [
                {
                    "id": "QTP-001",
                    "method": "test",
                    "requirement_id": "SWR-001",
                    "test_case_id": "C-001",
                }
            ]
        )
        self.write_stub_binary(
            {
                "cases": [
                    {
                        "id": "C-001",
                        "status": "failed",
                        "message": "expected SAFE, received FAULT",
                    }
                ]
            },
            exit_code=1,
        )

        exit_code, report = self.run_subject()

        self.assertEqual(exit_code, EXIT_QUALIFICATION_FAILED)
        self.assertEqual(report["traceability"][0]["status"], "FAIL")
        self.assertEqual(
            {issue["code"] for issue in report["issues"]},
            {"BINARY_EXIT_NONZERO", "CASE_FAILED"},
        )

    def test_missing_and_unknown_c_cases_are_both_rejected(self) -> None:
        self.write_requirements(("SWR-001",))
        self.write_procedures(
            [
                {
                    "id": "QTP-001",
                    "method": "test",
                    "requirement_id": "SWR-001",
                    "case_ids": ["C-MISSING"],
                }
            ]
        )
        self.write_stub_binary({"cases": [{"id": "C-UNKNOWN", "status": "PASS"}]})

        exit_code, report = self.run_subject()

        self.assertEqual(exit_code, EXIT_QUALIFICATION_FAILED)
        self.assertEqual(
            {issue["code"] for issue in report["issues"]},
            {"MISSING_C_CASE", "UNKNOWN_C_CASE"},
        )

    def test_unsupported_verification_method_is_an_input_error(self) -> None:
        self.write_requirements(("SWR-001",))
        self.write_procedures(
            [
                {
                    "id": "QTP-001",
                    "method": "wishful_thinking",
                    "requirement_id": "SWR-001",
                    "case_id": "C-001",
                }
            ]
        )
        self.write_stub_binary({"cases": [{"id": "C-001", "status": "PASS"}]})

        exit_code, report = self.run_subject()

        self.assertEqual(exit_code, EXIT_INPUT_ERROR)
        self.assertEqual(report["issues"][0]["code"], "UNSUPPORTED_VERIFICATION_METHOD")

    def test_malformed_c_json_is_an_input_error(self) -> None:
        self.write_requirements(("SWR-001",))
        self.write_procedures(
            [
                {
                    "id": "QTP-001",
                    "method": "test",
                    "requirement_id": "SWR-001",
                    "case_id": "C-001",
                }
            ]
        )
        self.binary.write_text(
            "#!/bin/sh\nprintf 'not-json\\n'\n",
            encoding="utf-8",
        )
        self.binary.chmod(self.binary.stat().st_mode | stat.S_IXUSR)

        exit_code, report = self.run_subject()

        self.assertEqual(exit_code, EXIT_INPUT_ERROR)
        self.assertEqual(report["issues"][0]["code"], "INVALID_C_JSON")

    def test_missing_c_result_metadata_fails_safely(self) -> None:
        self.write_requirements(("SWR-001",))
        self.write_procedures(
            [
                {
                    "id": "QTP-001",
                    "method": "test",
                    "requirement_id": "SWR-001",
                    "case_id": "C-001",
                }
            ]
        )
        self.write_stub_binary(
            {"cases": [{"id": "C-001", "status": "PASS"}]},
            include_metadata=False,
        )

        exit_code, report = self.run_subject()

        self.assertEqual(exit_code, EXIT_INPUT_ERROR)
        self.assertEqual(
            {issue["code"] for issue in report["issues"]},
            {"INVALID_METADATA"},
        )
        self.assertEqual(report["project"], self.METADATA["project"])
        self.assertEqual(report["summary"]["c_cases_total"], 0)

    def test_metadata_mismatch_fails_safely(self) -> None:
        self.write_requirements(("SWR-001",))
        self.write_procedures(
            [
                {
                    "id": "QTP-001",
                    "method": "test",
                    "requirement_id": "SWR-001",
                    "case_id": "C-001",
                }
            ]
        )
        procedures = json.loads(self.procedures.read_text(encoding="utf-8"))
        procedures["baseline"] = "TEST-BL-WRONG"
        self.write_json(self.procedures, procedures)
        self.write_stub_binary({"cases": [{"id": "C-001", "status": "PASS"}]})

        exit_code, report = self.run_subject()

        self.assertEqual(exit_code, EXIT_INPUT_ERROR)
        self.assertIn(
            "METADATA_MISMATCH",
            {issue["code"] for issue in report["issues"]},
        )
        self.assertEqual(report["baseline"], self.METADATA["baseline"])

    def test_captured_results_preserve_nonzero_binary_exit_code(self) -> None:
        self.write_requirements(("SWR-001",))
        self.write_procedures(
            [
                {
                    "id": "QTP-001",
                    "method": "test",
                    "requirement_id": "SWR-001",
                    "case_id": "C-001",
                }
            ]
        )
        c_results = self.root / "c-results.json"
        self.write_json(
            c_results,
            {
                **self.METADATA,
                "cases": [{"id": "C-001", "status": "PASS"}],
            },
        )

        exit_code, report = run_qualification(
            c_results_path=c_results,
            binary_exit_code=7,
            requirements_path=self.requirements,
            procedures_path=self.procedures,
            json_output=self.json_report,
            markdown_output=self.markdown_report,
        )

        self.assertEqual(exit_code, EXIT_QUALIFICATION_FAILED)
        self.assertEqual(report["result"], "FAIL")
        self.assertEqual(report["binary_exit_code"], 7)
        self.assertEqual(
            {issue["code"] for issue in report["issues"]},
            {"BINARY_EXIT_NONZERO"},
        )

    def test_runner_cli_requires_one_result_source(self) -> None:
        parsed = parse_args(["--c-results", "captured.json"])
        self.assertEqual(parsed.c_results, Path("captured.json"))
        self.assertEqual(parsed.binary_exit_code, 0)
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parse_args(["--binary", "suite", "--c-results", "captured.json"])
            with self.assertRaises(SystemExit):
                parse_args(["--binary", "suite", "--binary-exit-code", "1"])

    def test_standalone_traceability_check_accepts_complete_mapping(self) -> None:
        self.write_requirements(("SWR-001",))
        self.write_procedures(
            [
                {
                    "id": "QTP-001",
                    "method": "test",
                    "requirement_id": "SWR-001",
                    "case_id": "C-001",
                }
            ]
        )
        c_results = self.root / "c-results.json"
        self.write_json(
            c_results,
            {
                **self.METADATA,
                "cases": [{"id": "C-001", "status": "PASS"}],
            },
        )

        self.assertEqual(
            check_traceability(
                requirements_path=self.requirements,
                procedures_path=self.procedures,
                c_results_path=c_results,
            ),
            (),
        )

    def test_standalone_traceability_check_rejects_duplicate_c_ids(self) -> None:
        self.write_requirements(("SWR-001",))
        self.write_procedures(
            [
                {
                    "id": "QTP-001",
                    "method": "test",
                    "requirement_id": "SWR-001",
                    "case_id": "C-001",
                }
            ]
        )
        c_results = self.root / "c-results.json"
        self.write_json(
            c_results,
            {
                **self.METADATA,
                "cases": [
                    {"id": "C-001", "status": "PASS"},
                    {"id": "C-001", "status": "PASS"},
                ]
            },
        )

        with self.assertRaises(InputValidationError) as context:
            check_traceability(
                requirements_path=self.requirements,
                procedures_path=self.procedures,
                c_results_path=c_results,
            )
        self.assertEqual(context.exception.issues[0].code, "DUPLICATE_C_CASE_ID")


if __name__ == "__main__":
    unittest.main()
