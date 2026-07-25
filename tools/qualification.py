"""Deterministic qualification reporting and traceability validation.

The module deliberately uses only the Python standard library.  It treats the
compiled C test executable as an untrusted producer of structured results:
output is decoded, validated, normalized, and reconciled with the committed
requirements and qualification procedures before a report is written.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPORT_SCHEMA_VERSION = 1
EXIT_OK = 0
EXIT_QUALIFICATION_FAILED = 1
EXIT_INPUT_ERROR = 2
HOST_EVIDENCE_SCOPE = "host-executable qualification cases"
ARM_EXTERNAL_GATE_NOTE = (
    "ARM inspection remains required for SRS-PLT-001 and the ARM portion of "
    "SRS-RES-001."
)

_PASS_STATUSES = {"pass", "passed", "success", "successful", "ok"}
_FAIL_STATUSES = {"fail", "failed", "failure", "error"}
_INCOMPLETE_STATUSES = {"skip", "skipped", "not_run", "not-run", "not run", "blocked"}

# Every accepted value maps to a reportable verification strategy. Procedures
# still reference executable case IDs; analysis and inspection cases are emitted
# by the native harness after performing their deterministic static checks.
_VERIFICATION_METHODS = {
    "test": "test",
    "automated_test": "test",
    "automated test": "test",
    "unit_test": "test",
    "unit test": "test",
    "integration_test": "test",
    "integration test": "test",
    "system_test": "test",
    "system test": "test",
    "qualification_test": "test",
    "qualification test": "test",
    "execution": "test",
    "analysis": "analysis",
    "static_analysis": "analysis",
    "static analysis": "analysis",
    "inspection": "inspection",
    "review": "inspection",
    "demonstration": "demonstration",
}


@dataclass(frozen=True)
class Issue:
    """A stable, machine-readable validation or qualification finding."""

    code: str
    message: str
    subject_id: str = ""

    def as_dict(self) -> dict[str, str]:
        value = {"code": self.code, "message": self.message}
        if self.subject_id:
            value["subject_id"] = self.subject_id
        return value


@dataclass(frozen=True)
class Requirement:
    identifier: str
    title: str
    statement: str
    verification_methods: tuple[str, ...]


@dataclass(frozen=True)
class Procedure:
    identifier: str
    title: str
    requirement_ids: tuple[str, ...]
    case_ids: tuple[str, ...]
    verification_method: str


@dataclass(frozen=True)
class CCaseResult:
    identifier: str
    name: str
    status: str
    message: str


@dataclass(frozen=True)
class QualificationMetadata:
    project: str
    version: str
    baseline: str

    def as_dict(self) -> dict[str, str]:
        return {
            "baseline": self.baseline,
            "project": self.project,
            "version": self.version,
        }


class InputValidationError(ValueError):
    """Raised when a committed input or C result violates its contract."""

    def __init__(self, issues: Sequence[Issue]):
        super().__init__("qualification input validation failed")
        self.issues = tuple(issues)


def _external_gates() -> dict[str, dict[str, Any]]:
    return {
        "arm_inspection": {
            "note": ARM_EXTERNAL_GATE_NOTE,
            "requirement_ids": ["SRS-PLT-001", "SRS-RES-001"],
            "status": "REQUIRED",
        }
    }


def _load_json(path: Path, *, kind: str) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise InputValidationError(
            [Issue("INPUT_UNREADABLE", f"Unable to read {kind} file: {error}", path.name)]
        ) from error
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise InputValidationError(
            [
                Issue(
                    "INVALID_JSON",
                    f"{kind.capitalize()} file is not valid JSON at line {error.lineno}, column {error.colno}.",
                    path.name,
                )
            ]
        ) from error


def _extract_array(
    document: Any,
    *,
    keys: Sequence[str],
    kind: str,
) -> list[Any]:
    if isinstance(document, list):
        return document
    if isinstance(document, dict):
        for key in keys:
            value = document.get(key)
            if value is not None:
                if isinstance(value, list):
                    return value
                raise InputValidationError(
                    [Issue("INVALID_SCHEMA", f"{kind.capitalize()} field '{key}' must be an array.")]
                )
    joined = "', '".join(keys)
    raise InputValidationError(
        [
            Issue(
                "INVALID_SCHEMA",
                f"{kind.capitalize()} document must be an array or contain one of: '{joined}'.",
            )
        ]
    )


def _required_string(record: Mapping[str, Any], keys: Sequence[str], *, kind: str) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    joined = "', '".join(keys)
    raise InputValidationError(
        [Issue("INVALID_SCHEMA", f"{kind.capitalize()} requires a non-empty '{joined}' field.")]
    )


def _optional_string(record: Mapping[str, Any], keys: Sequence[str], default: str = "") -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str):
            return value.strip()
    return default


def _document_metadata(document: Any, *, kind: str) -> QualificationMetadata:
    if not isinstance(document, dict):
        raise InputValidationError(
            [
                Issue(
                    "INVALID_METADATA",
                    f"{kind.capitalize()} document must be an object with project, version, and baseline metadata.",
                    kind,
                )
            ]
        )

    issues: list[Issue] = []
    values: dict[str, str] = {}
    for field in ("project", "version", "baseline"):
        value = document.get(field)
        if not isinstance(value, str) or not value.strip():
            issues.append(
                Issue(
                    "INVALID_METADATA",
                    f"{kind.capitalize()} metadata field '{field}' must be a non-empty string.",
                    kind,
                )
            )
        else:
            values[field] = value.strip()
    if issues:
        raise InputValidationError(issues)
    return QualificationMetadata(
        project=values["project"],
        version=values["version"],
        baseline=values["baseline"],
    )


def _validate_matching_metadata(
    named_metadata: Sequence[tuple[str, QualificationMetadata]],
) -> QualificationMetadata:
    if not named_metadata:
        raise InputValidationError(
            [Issue("INVALID_METADATA", "No qualification metadata was supplied.")]
        )

    reference_name, reference = named_metadata[0]
    issues: list[Issue] = []
    for source_name, candidate in named_metadata[1:]:
        for field in ("project", "version", "baseline"):
            expected = getattr(reference, field)
            actual = getattr(candidate, field)
            if actual != expected:
                issues.append(
                    Issue(
                        "METADATA_MISMATCH",
                        f"{source_name.capitalize()} metadata field '{field}' is '{actual}', "
                        f"but {reference_name} declares '{expected}'.",
                        source_name,
                    )
                )
    if issues:
        raise InputValidationError(issues)
    return reference


def _string_references(
    record: Mapping[str, Any],
    *,
    plural_keys: Sequence[str],
    singular_keys: Sequence[str],
    kind: str,
) -> tuple[str, ...]:
    value: Any = None
    selected_key = ""
    for key in plural_keys:
        if key in record:
            value = record[key]
            selected_key = key
            break
    if value is None:
        for key in singular_keys:
            if key in record:
                value = record[key]
                selected_key = key
                break

    if isinstance(value, str):
        references = [value]
    elif isinstance(value, list):
        references = value
    else:
        expected = "', '".join((*plural_keys, *singular_keys))
        raise InputValidationError(
            [
                Issue(
                    "INVALID_SCHEMA",
                    f"{kind.capitalize()} requires string references in one of: '{expected}'.",
                )
            ]
        )

    if not references or any(not isinstance(item, str) or not item.strip() for item in references):
        raise InputValidationError(
            [
                Issue(
                    "INVALID_SCHEMA",
                    f"{kind.capitalize()} field '{selected_key}' must contain non-empty string IDs.",
                )
            ]
        )
    normalized = tuple(sorted({item.strip() for item in references}))
    if len(normalized) != len(references):
        raise InputValidationError(
            [
                Issue(
                    "DUPLICATE_REFERENCE",
                    f"{kind.capitalize()} field '{selected_key}' contains duplicate IDs.",
                )
            ]
        )
    return normalized


def load_requirements(path: Path) -> tuple[Requirement, ...]:
    document = _load_json(path, kind="requirements")
    _document_metadata(document, kind="requirements")
    records = _extract_array(
        document,
        keys=("requirements",),
        kind="requirements",
    )
    requirements: list[Requirement] = []
    issues: list[Issue] = []
    seen: set[str] = set()
    for index, raw in enumerate(records):
        if not isinstance(raw, dict):
            issues.append(
                Issue("INVALID_SCHEMA", f"Requirement at index {index} must be an object.")
            )
            continue
        try:
            identifier = _required_string(
                raw, ("id", "requirement_id"), kind=f"requirement at index {index}"
            )
        except InputValidationError as error:
            issues.extend(error.issues)
            continue
        if identifier in seen:
            issues.append(
                Issue(
                    "DUPLICATE_REQUIREMENT_ID",
                    f"Requirement ID '{identifier}' is declared more than once.",
                    identifier,
                )
            )
            continue
        seen.add(identifier)
        method_values: list[str] = []
        raw_methods = raw.get("verification_methods", raw.get("verification_method"))
        if raw_methods is not None:
            if isinstance(raw_methods, str):
                method_values = [raw_methods]
            elif isinstance(raw_methods, list) and all(
                isinstance(item, str) and item.strip() for item in raw_methods
            ):
                method_values = raw_methods
            else:
                issues.append(
                    Issue(
                        "INVALID_SCHEMA",
                        f"Requirement '{identifier}' verification method must be a string or array of strings.",
                        identifier,
                    )
                )
                continue
        normalized_methods: list[str] = []
        unsupported_methods: list[str] = []
        for method_value in method_values:
            normalized_method = _normalize_method(method_value)
            if normalized_method is None:
                unsupported_methods.append(method_value)
            else:
                normalized_methods.append(normalized_method)
        if unsupported_methods:
            issues.append(
                Issue(
                    "UNSUPPORTED_VERIFICATION_METHOD",
                    f"Requirement '{identifier}' uses unsupported verification method(s): "
                    + ", ".join(sorted(unsupported_methods))
                    + ".",
                    identifier,
                )
            )
            continue
        requirements.append(
            Requirement(
                identifier=identifier,
                title=_optional_string(raw, ("title", "name"), identifier),
                statement=_optional_string(raw, ("statement", "text", "description")),
                verification_methods=tuple(sorted(set(normalized_methods))),
            )
        )
    if not records:
        issues.append(Issue("EMPTY_REQUIREMENTS", "At least one requirement is required."))
    if issues:
        raise InputValidationError(issues)
    return tuple(sorted(requirements, key=lambda item: item.identifier))


def _normalize_method(value: str) -> str | None:
    return _VERIFICATION_METHODS.get(value.strip().lower())


def load_procedures(path: Path) -> tuple[Procedure, ...]:
    document = _load_json(path, kind="test procedures")
    _document_metadata(document, kind="test procedures")
    records = _extract_array(
        document,
        keys=("procedures", "test_procedures"),
        kind="test procedures",
    )
    procedures: list[Procedure] = []
    issues: list[Issue] = []
    seen: set[str] = set()
    for index, raw in enumerate(records):
        if not isinstance(raw, dict):
            issues.append(
                Issue("INVALID_SCHEMA", f"Procedure at index {index} must be an object.")
            )
            continue
        try:
            identifier = _required_string(
                raw, ("id", "procedure_id"), kind=f"procedure at index {index}"
            )
            requirement_ids = _string_references(
                raw,
                plural_keys=("requirement_ids", "requirements"),
                singular_keys=("requirement_id",),
                kind=f"procedure '{identifier}'",
            )
            case_ids = _string_references(
                raw,
                plural_keys=("case_ids", "test_case_ids", "c_test_cases", "cases"),
                singular_keys=("case_id", "test_case_id", "c_test_case"),
                kind=f"procedure '{identifier}'",
            )
            method_value = _required_string(
                raw,
                ("verification_method", "method"),
                kind=f"procedure '{identifier}'",
            )
        except InputValidationError as error:
            issues.extend(error.issues)
            continue
        if identifier in seen:
            issues.append(
                Issue(
                    "DUPLICATE_PROCEDURE_ID",
                    f"Procedure ID '{identifier}' is declared more than once.",
                    identifier,
                )
            )
            continue
        seen.add(identifier)
        method = _normalize_method(method_value)
        if method is None:
            issues.append(
                Issue(
                    "UNSUPPORTED_VERIFICATION_METHOD",
                    f"Procedure '{identifier}' uses unsupported verification method '{method_value}'.",
                    identifier,
                )
            )
            continue
        procedures.append(
            Procedure(
                identifier=identifier,
                title=_optional_string(raw, ("title", "name", "description"), identifier),
                requirement_ids=requirement_ids,
                case_ids=case_ids,
                verification_method=method,
            )
        )
    if not records:
        issues.append(Issue("EMPTY_PROCEDURES", "At least one test procedure is required."))
    if issues:
        raise InputValidationError(issues)
    return tuple(sorted(procedures, key=lambda item: item.identifier))


def _normalize_status(raw: Any, *, case_id: str) -> str:
    if isinstance(raw, bool):
        return "PASS" if raw else "FAIL"
    if not isinstance(raw, str):
        raise InputValidationError(
            [
                Issue(
                    "INVALID_C_RESULT",
                    f"C case '{case_id}' requires a string status or boolean passed field.",
                    case_id,
                )
            ]
        )
    value = raw.strip().lower()
    if value in _PASS_STATUSES:
        return "PASS"
    if value in _FAIL_STATUSES:
        return "FAIL"
    if value in _INCOMPLETE_STATUSES:
        return "INCOMPLETE"
    raise InputValidationError(
        [
            Issue(
                "INVALID_C_STATUS",
                f"C case '{case_id}' has unsupported status '{raw}'.",
                case_id,
            )
        ]
    )


def parse_c_results(document: Any) -> tuple[CCaseResult, ...]:
    records = _extract_array(
        document,
        keys=("cases", "test_cases", "results"),
        kind="C test results",
    )
    results: list[CCaseResult] = []
    issues: list[Issue] = []
    seen: set[str] = set()
    for index, raw in enumerate(records):
        if not isinstance(raw, dict):
            issues.append(Issue("INVALID_C_RESULT", f"C result at index {index} must be an object."))
            continue
        try:
            identifier = _required_string(
                raw, ("id", "case_id", "test_case_id"), kind=f"C result at index {index}"
            )
            status_value = raw["status"] if "status" in raw else raw.get("passed")
            status = _normalize_status(status_value, case_id=identifier)
        except InputValidationError as error:
            issues.extend(error.issues)
            continue
        if identifier in seen:
            issues.append(
                Issue(
                    "DUPLICATE_C_CASE_ID",
                    f"C case ID '{identifier}' appears more than once.",
                    identifier,
                )
            )
            continue
        seen.add(identifier)
        results.append(
            CCaseResult(
                identifier=identifier,
                name=_optional_string(raw, ("name", "title"), identifier),
                status=status,
                message=_optional_string(raw, ("message", "detail", "details")),
            )
        )
    if not records:
        issues.append(Issue("EMPTY_C_RESULTS", "The C test binary returned no cases."))
    if issues:
        raise InputValidationError(issues)
    return tuple(sorted(results, key=lambda item: item.identifier))


def execute_c_binary(binary: Path, *, timeout_seconds: float = 30.0) -> tuple[Any, int]:
    try:
        completed = subprocess.run(
            [str(binary), "--json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as error:
        raise InputValidationError(
            [Issue("BINARY_NOT_FOUND", f"C test binary was not found: {binary}", binary.name)]
        ) from error
    except PermissionError as error:
        raise InputValidationError(
            [Issue("BINARY_NOT_EXECUTABLE", f"C test binary is not executable: {binary}", binary.name)]
        ) from error
    except subprocess.TimeoutExpired as error:
        raise InputValidationError(
            [
                Issue(
                    "BINARY_TIMEOUT",
                    f"C test binary exceeded the {timeout_seconds:g}-second timeout.",
                    binary.name,
                )
            ]
        ) from error
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        stderr = completed.stderr.strip()
        detail = f" Stderr: {stderr}" if stderr else ""
        raise InputValidationError(
            [
                Issue(
                    "INVALID_C_JSON",
                    "C test binary did not emit one valid JSON document on stdout." + detail,
                    binary.name,
                )
            ]
        ) from error
    return document, completed.returncode


def traceability_issues(
    requirements: Sequence[Requirement],
    procedures: Sequence[Procedure],
    c_cases: Sequence[CCaseResult],
) -> tuple[Issue, ...]:
    requirement_ids = {item.identifier for item in requirements}
    case_ids = {item.identifier for item in c_cases}
    mapped_requirements: set[str] = set()
    mapped_cases: set[str] = set()
    issues: list[Issue] = []

    for procedure in procedures:
        for requirement_id in procedure.requirement_ids:
            if requirement_id not in requirement_ids:
                issues.append(
                    Issue(
                        "UNKNOWN_REQUIREMENT",
                        f"Procedure '{procedure.identifier}' references unknown requirement '{requirement_id}'.",
                        procedure.identifier,
                    )
                )
            else:
                mapped_requirements.add(requirement_id)
                requirement = next(
                    item for item in requirements if item.identifier == requirement_id
                )
                if (
                    requirement.verification_methods
                    and procedure.verification_method not in requirement.verification_methods
                ):
                    issues.append(
                        Issue(
                            "VERIFICATION_METHOD_MISMATCH",
                            f"Procedure '{procedure.identifier}' method "
                            f"'{procedure.verification_method}' is not permitted by requirement "
                            f"'{requirement_id}'.",
                            procedure.identifier,
                        )
                    )
        for case_id in procedure.case_ids:
            if case_id not in case_ids:
                issues.append(
                    Issue(
                        "MISSING_C_CASE",
                        f"Procedure '{procedure.identifier}' references C case '{case_id}', but it was not returned.",
                        procedure.identifier,
                    )
                )
            else:
                mapped_cases.add(case_id)

    for requirement_id in sorted(requirement_ids - mapped_requirements):
        issues.append(
            Issue(
                "UNMAPPED_REQUIREMENT",
                f"Requirement '{requirement_id}' has no valid test-procedure mapping.",
                requirement_id,
            )
        )
    for case_id in sorted(case_ids - mapped_cases):
        issues.append(
            Issue(
                "UNKNOWN_C_CASE",
                f"C test binary returned case '{case_id}', but no procedure references it.",
                case_id,
            )
        )
    return tuple(sorted(issues, key=lambda item: (item.code, item.subject_id, item.message)))


def _procedure_status(
    procedure: Procedure,
    c_cases: Mapping[str, CCaseResult],
) -> str:
    statuses = [c_cases[case_id].status for case_id in procedure.case_ids if case_id in c_cases]
    if len(statuses) != len(procedure.case_ids) or any(value == "INCOMPLETE" for value in statuses):
        return "INCOMPLETE"
    if any(value == "FAIL" for value in statuses):
        return "FAIL"
    return "PASS"


def build_report(
    requirements: Sequence[Requirement],
    procedures: Sequence[Procedure],
    c_cases: Sequence[CCaseResult],
    *,
    metadata: QualificationMetadata,
    binary_exit_code: int,
    input_issues: Iterable[Issue] = (),
) -> dict[str, Any]:
    case_by_id = {item.identifier: item for item in c_cases}
    issues = list(input_issues)
    issues.extend(traceability_issues(requirements, procedures, c_cases))

    for case in c_cases:
        if case.status == "FAIL":
            issues.append(
                Issue("CASE_FAILED", f"C qualification case '{case.identifier}' failed.", case.identifier)
            )
        elif case.status == "INCOMPLETE":
            issues.append(
                Issue(
                    "CASE_INCOMPLETE",
                    f"C qualification case '{case.identifier}' did not complete.",
                    case.identifier,
                )
            )
    if binary_exit_code != 0:
        issues.append(
            Issue(
                "BINARY_EXIT_NONZERO",
                f"C test binary exited with status {binary_exit_code}.",
            )
        )

    unique_issues = {
        (issue.code, issue.message, issue.subject_id): issue
        for issue in issues
    }
    ordered_issues = sorted(
        unique_issues.values(),
        key=lambda item: (item.code, item.subject_id, item.message),
    )

    procedure_records: list[dict[str, Any]] = []
    for procedure in procedures:
        procedure_records.append(
            {
                "case_ids": list(procedure.case_ids),
                "id": procedure.identifier,
                "requirement_ids": list(procedure.requirement_ids),
                "status": _procedure_status(procedure, case_by_id),
                "title": procedure.title,
                "verification_method": procedure.verification_method,
            }
        )

    traceability_records: list[dict[str, Any]] = []
    for requirement in requirements:
        linked_procedures = [
            procedure for procedure in procedures if requirement.identifier in procedure.requirement_ids
        ]
        linked_case_ids = sorted(
            {
                case_id
                for procedure in linked_procedures
                for case_id in procedure.case_ids
            }
        )
        statuses = [
            _procedure_status(procedure, case_by_id)
            for procedure in linked_procedures
        ]
        if not statuses or any(value == "INCOMPLETE" for value in statuses):
            status = "INCOMPLETE"
        elif any(value == "FAIL" for value in statuses):
            status = "FAIL"
        else:
            status = "PASS"
        traceability_records.append(
            {
                "case_ids": linked_case_ids,
                "procedure_ids": sorted(procedure.identifier for procedure in linked_procedures),
                "requirement_id": requirement.identifier,
                "status": status,
                "title": requirement.title,
            }
        )

    passed_cases = sum(case.status == "PASS" for case in c_cases)
    failed_cases = sum(case.status == "FAIL" for case in c_cases)
    incomplete_cases = sum(case.status == "INCOMPLETE" for case in c_cases)
    result = "HOST_PASS" if not ordered_issues else "FAIL"
    return {
        "baseline": metadata.baseline,
        "binary_exit_code": binary_exit_code,
        "c_cases": [
            {
                "id": case.identifier,
                "message": case.message,
                "name": case.name,
                "status": case.status,
            }
            for case in c_cases
        ],
        "evidence_scope": HOST_EVIDENCE_SCOPE,
        "external_gates": _external_gates(),
        "issues": [issue.as_dict() for issue in ordered_issues],
        "project": metadata.project,
        "procedures": procedure_records,
        "result": result,
        "schema_version": REPORT_SCHEMA_VERSION,
        "summary": {
            "c_cases_failed": failed_cases,
            "c_cases_incomplete": incomplete_cases,
            "c_cases_passed": passed_cases,
            "c_cases_total": len(c_cases),
            "issues": len(ordered_issues),
            "procedures_total": len(procedures),
            "requirements_total": len(requirements),
        },
        "traceability": traceability_records,
        "version": metadata.version,
    }


def validation_failure_report(
    issues: Sequence[Issue],
    *,
    metadata: QualificationMetadata | None = None,
) -> dict[str, Any]:
    ordered = sorted(issues, key=lambda item: (item.code, item.subject_id, item.message))
    return {
        "baseline": metadata.baseline if metadata is not None else None,
        "binary_exit_code": None,
        "c_cases": [],
        "evidence_scope": HOST_EVIDENCE_SCOPE,
        "external_gates": _external_gates(),
        "issues": [item.as_dict() for item in ordered],
        "project": metadata.project if metadata is not None else None,
        "procedures": [],
        "result": "FAIL",
        "schema_version": REPORT_SCHEMA_VERSION,
        "summary": {
            "c_cases_failed": 0,
            "c_cases_incomplete": 0,
            "c_cases_passed": 0,
            "c_cases_total": 0,
            "issues": len(ordered),
            "procedures_total": 0,
            "requirements_total": 0,
        },
        "traceability": [],
        "version": metadata.version if metadata is not None else None,
    }


def report_exit_code(report: Mapping[str, Any], *, input_error: bool = False) -> int:
    if report.get("result") == "HOST_PASS":
        return EXIT_OK
    return EXIT_INPUT_ERROR if input_error else EXIT_QUALIFICATION_FAILED


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    arm_gate = report["external_gates"]["arm_inspection"]
    lines = [
        "# Host-Executable Qualification Report",
        "",
        f"**Host-only result:** {report['result']}",
        "",
        f"**Evidence scope:** {report['evidence_scope']}",
        "",
        "## Configuration Identity",
        "",
        f"- Project: {report.get('project') or 'Unavailable'}",
        f"- Version: {report.get('version') or 'Unavailable'}",
        f"- Baseline: {report.get('baseline') or 'Unavailable'}",
        f"- Captured binary exit code: "
        f"{report['binary_exit_code'] if report.get('binary_exit_code') is not None else 'Unavailable'}",
        "",
        "## External Gates",
        "",
        f"- **ARM inspection — {arm_gate['status']}:** {arm_gate['note']}",
        "",
        "## Summary",
        "",
        f"- Requirements: {summary['requirements_total']}",
        f"- Procedures: {summary['procedures_total']}",
        f"- C cases: {summary['c_cases_total']}",
        f"- Passed C cases: {summary['c_cases_passed']}",
        f"- Failed C cases: {summary['c_cases_failed']}",
        f"- Incomplete C cases: {summary['c_cases_incomplete']}",
        f"- Findings: {summary['issues']}",
        "",
        "## Host Case Traceability",
        "",
        "| Requirement | Procedures | C cases | Host case status |",
        "|---|---|---|---|",
    ]
    for row in report["traceability"]:
        procedures = ", ".join(row["procedure_ids"]) or "—"
        cases = ", ".join(row["case_ids"]) or "—"
        lines.append(
            f"| {row['requirement_id']} | {procedures} | {cases} | {row['status']} |"
        )
    if not report["traceability"]:
        lines.append("| — | — | — | INCOMPLETE |")

    lines.extend(
        [
            "",
            "## Host Qualification Procedures",
            "",
            "| Procedure | Verification method | Requirements | C cases | Host case status |",
            "|---|---|---|---|---|",
        ]
    )
    for procedure in report["procedures"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    procedure["id"],
                    procedure["verification_method"],
                    ", ".join(procedure["requirement_ids"]),
                    ", ".join(procedure["case_ids"]),
                    procedure["status"],
                ]
            )
            + " |"
        )
    if not report["procedures"]:
        lines.append("| — | — | — | — | INCOMPLETE |")

    lines.extend(
        [
            "",
            "## C Test Results",
            "",
            "| Case | Name | Status | Message |",
            "|---|---|---|---|",
        ]
    )
    for case in report["c_cases"]:
        safe_message = case["message"].replace("|", "\\|").replace("\n", " ")
        safe_name = case["name"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {case['id']} | {safe_name} | {case['status']} | {safe_message} |")
    if not report["c_cases"]:
        lines.append("| — | — | INCOMPLETE | No C results available |")

    lines.extend(["", "## Findings", ""])
    if report["issues"]:
        for issue in report["issues"]:
            subject = f" ({issue['subject_id']})" if issue.get("subject_id") else ""
            lines.append(f"- `{issue['code']}`{subject}: {issue['message']}")
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"


def write_reports(report: Mapping[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")


def run_qualification(
    *,
    binary: Path | None = None,
    c_results_path: Path | None = None,
    binary_exit_code: int = 0,
    requirements_path: Path,
    procedures_path: Path,
    json_output: Path,
    markdown_output: Path,
    timeout_seconds: float = 30.0,
) -> tuple[int, dict[str, Any]]:
    metadata: QualificationMetadata | None = None
    try:
        if (binary is None) == (c_results_path is None):
            raise InputValidationError(
                [
                    Issue(
                        "INVALID_RESULT_SOURCE",
                        "Exactly one C result source is required: binary or c-results.",
                    )
                ]
            )
        if not isinstance(binary_exit_code, int) or isinstance(binary_exit_code, bool) or binary_exit_code < 0:
            raise InputValidationError(
                [
                    Issue(
                        "INVALID_BINARY_EXIT_CODE",
                        "Captured binary exit code must be a non-negative integer.",
                    )
                ]
            )
        if binary is not None and binary_exit_code != 0:
            raise InputValidationError(
                [
                    Issue(
                        "INVALID_RESULT_SOURCE",
                        "A captured binary exit code is valid only with c-results.",
                    )
                ]
            )

        requirements_document = _load_json(requirements_path, kind="requirements")
        requirements_metadata = _document_metadata(
            requirements_document, kind="requirements"
        )
        metadata = requirements_metadata
        procedures_document = _load_json(procedures_path, kind="test procedures")
        procedures_metadata = _document_metadata(
            procedures_document, kind="test procedures"
        )
        metadata = _validate_matching_metadata(
            (
                ("requirements", requirements_metadata),
                ("test procedures", procedures_metadata),
            )
        )
        requirements = load_requirements(requirements_path)
        procedures = load_procedures(procedures_path)
        if binary is not None:
            c_document, observed_exit_code = execute_c_binary(
                binary, timeout_seconds=timeout_seconds
            )
        else:
            assert c_results_path is not None
            c_document = _load_json(c_results_path, kind="C test results")
            observed_exit_code = binary_exit_code
        c_metadata = _document_metadata(c_document, kind="C test results")
        metadata = _validate_matching_metadata(
            (
                ("requirements", requirements_metadata),
                ("test procedures", procedures_metadata),
                ("C test results", c_metadata),
            )
        )
        c_cases = parse_c_results(c_document)
    except InputValidationError as error:
        report = validation_failure_report(error.issues, metadata=metadata)
        write_reports(report, json_output, markdown_output)
        return EXIT_INPUT_ERROR, report

    assert metadata is not None
    report = build_report(
        requirements,
        procedures,
        c_cases,
        metadata=metadata,
        binary_exit_code=observed_exit_code,
    )
    write_reports(report, json_output, markdown_output)
    return report_exit_code(report), report


def check_traceability(
    *,
    requirements_path: Path,
    procedures_path: Path,
    c_results_path: Path,
) -> tuple[Issue, ...]:
    requirements_document = _load_json(requirements_path, kind="requirements")
    procedures_document = _load_json(procedures_path, kind="test procedures")
    c_document = _load_json(c_results_path, kind="C test results")
    _validate_matching_metadata(
        (
            (
                "requirements",
                _document_metadata(requirements_document, kind="requirements"),
            ),
            (
                "test procedures",
                _document_metadata(procedures_document, kind="test procedures"),
            ),
            (
                "C test results",
                _document_metadata(c_document, kind="C test results"),
            ),
        )
    )
    requirements = load_requirements(requirements_path)
    procedures = load_procedures(procedures_path)
    c_cases = parse_c_results(c_document)
    return traceability_issues(requirements, procedures, c_cases)
