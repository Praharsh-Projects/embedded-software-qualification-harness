# Software Qualification Test Plan

Document ID: `ESQH-SQTP-001`
Version: `0.1.0`
Baseline: `ESQH-BL-0.1.0`

## 1. Objective

Verify the seventeen requirements in `SRS.md` using native unit/integration
tests, ten host-driven qualification procedures, and structural analysis of
the generic Cortex-M0+ artifact. The activity is project-internal
qualification, not regulatory, safety, customer, or physical-device
qualification.

## 2. Test levels

| Level | Purpose | Environment |
|---|---|---|
| Unit | Boundary and state behavior of one C component | Native host process |
| Integration | Controller behavior across multiple portable components | Native host process |
| Qualification | Requirement-oriented cases reconciled by the Python runner | Native host process |
| Artifact inspection | Architecture, entry point, symbols, and memory budget | ARM cross-build output |

## 3. Test items

- portable application/controller modules;
- deterministic UART, SPI, classic CAN, and datagram models;
- state, fault, heartbeat, recovery, and telemetry behavior;
- native C qualification executable and its JSON contract;
- Python schema, execution, reconciliation, and report generation;
- generic Cortex-M0+ ELF/map output.

## 4. Environment

Host verification runs on current GitHub-hosted Ubuntu and macOS runners and may
also run locally on macOS/Linux. The ARM job uses `arm-none-eabi-gcc` and
binutils. All host interface behavior is simulated in memory. No physical
device or laboratory equipment is part of the environment.

## 5. Entry criteria

- requirement and procedure JSON parse successfully;
- all requirement, procedure, and C case IDs are unique;
- native build completes with warnings treated as errors;
- the qualification executable supports `--json`;
- the source revision, project, version, and configuration baseline are known.

## 6. Execution strategy

1. Configure and build the native targets.
2. Run native CTest unit and integration tests.
3. Run Python automation tests.
4. Execute the C qualification binary once and save its complete result
   document and exit status.
5. Reconcile that same result document through the Python runner and standalone
   traceability checker.
6. Reject project/version/baseline mismatches and missing, unknown, duplicate,
   failed, or incomplete C cases.
7. Verify complete requirement-to-procedure-to-case traceability.
8. Cross-compile the generic Cortex-M0+ artifact.
9. Inspect architecture, entry point, vector section, retained public APIs,
   undefined symbols, and
   resource limits.
10. Save machine-readable and human-readable evidence.

## 7. Pass/fail criteria

The baseline passes only when:

- every native unit and integration test passes;
- every committed C qualification case returns `PASS`;
- all ten qualification procedures resolve to `PASS`;
- all seventeen requirements map to at least one procedure and returned case;
- no returned case is unmapped;
- result, requirement, and procedure metadata identify the same project,
  version, and baseline;
- the runner reports no schema, execution, or traceability finding;
- every public core API expected by the link contract is present in the ARM ELF;
- the ARM artifact links with no unresolved symbol;
- flash use is below 64 KiB and static RAM use is below 8 KiB.

Any unmet condition fails the run. Tests are not waived automatically. A
deviation must be recorded explicitly and cannot be reported as a pass.

## 8. Independence and confidence limits

The project author may write both implementation and tests. CI supplies
repeatable execution but not organizational test independence. Host simulation
cannot reveal board startup, peripheral, concurrency, electrical, or
real-time-timing defects. Artifact inspection cannot prove behavior on a
physical MCU.

## 9. Deliverables

- CTest output;
- qualification JSON and Markdown reports;
- traceability result;
- ARM ELF/map/bin and SHA-256 values;
- artifact-inspection output;
- CI run status tied to a commit.
