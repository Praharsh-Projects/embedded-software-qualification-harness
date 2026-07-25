# Software Qualification Test Report

Document ID: `ESQH-SQTR-001`
Version: `0.1.0`
Baseline: `ESQH-BL-0.1.0`
Execution date: `2026-07-26`
Status: **PASS — local pre-publication baseline**

## 1. Result summary

| Verification item | Result |
|---|---|
| Native CTest target | PASS, 1/1 executable |
| Live C cases inside `esqh_qualification --json` | PASS, 20/20 |
| Python qualification automation tests | PASS, 13/13 |
| Qualification reconciliation | PASS, 17 requirements / 10 procedures / 20 C cases, 0 findings |
| Qualification identity | PASS, project / version / baseline agree across all three authorities |
| Evidence source | PASS, one captured C result drives report and traceability |
| ARM Cortex-M0+ cross-build | PASS |
| ARM ELF structure and entry | PASS |
| Public core APIs retained in ARM ELF | PASS, 20/20 |
| Undefined ARM symbols | PASS, none |
| Flash budget | PASS, 2,808 bytes used of 65,536-byte acceptance limit |
| Static RAM budget | PASS, 2,848 bytes used of 8,192-byte acceptance limit |

The CTest entry executes the native `esqh_qualification` binary. Its JSON mode
reports twenty named C cases with project/version/baseline identity. The Python
suite separately tests schema validation, metadata mismatch, captured exit
status, deterministic reporting, failure handling, and traceability behavior.

## 2. Identified environment

- Host: macOS 26.5.2, Apple Silicon (`arm64`)
- Native compiler: Apple clang 21.0.0
- CMake: 4.1.1
- Python: 3.14.6
- ARM compiler: `arm-none-eabi-gcc` 16.1.0
- Repository version: 0.1.0
- Configuration baseline: `ESQH-BL-0.1.0`
- Source identity: local working tree before the initial repository commit

The absence of an immutable commit SHA is a recorded pre-publication deviation.
This local result must be repeated in CI after the initial commit; it is not a
substitute for that CI result.

## 3. ARM artifact evidence

| Property | Observed value |
|---|---|
| ELF class | ELF32 |
| Data encoding | little-endian |
| Machine | ARM |
| Entry point | `0x08000045` (Thumb-state bit set) |
| Entry symbol | `Reset_Handler` at `0x08000044` |
| Text | 2,808 bytes |
| Data | 0 bytes |
| BSS | 2,848 bytes |
| Undefined symbols | none |
| Expected public API symbols | 20/20 present |

Artifact SHA-256 values:

```text
bc4adc76b76f482d538bc996f81d6b8ad673e0075ba1f586c9c3a26eba2f4b91  esqh_firmware.elf
23d06a089947939253f83be5d7b695f588b53ec008197f57efd2ad49fae57786  esqh_firmware.bin
dd82f1031c6ea7e0089bf487394ae0cbe882f1ce631e85bd51ca403374237a31  esqh_firmware.map
```

These hashes identify the local artifacts produced by this execution. A commit
or toolchain change is expected to produce different artifacts and requires a
new report.

## 4. Evidence boundary

Behavioral tests run as native host simulations. ARM verification is structural
inspection of a cross-compiled artifact. No test in this report runs on
physical hardware, uses a real UART/SPI/CAN/Ethernet peripheral, establishes
real-time timing, or demonstrates external certification.

The host executable verifies the portable fixed-width and structure contracts.
The ARM build verifies instruction target, freestanding link, entry/vector,
retention of every expected public core API, undefined-symbol state, and
linked-size budgets. Neither proves correct
electrical, peripheral, interrupt, or real-time behavior on an MCU.

## 5. Deviations and follow-up

- No physical-target execution or hardware-in-the-loop activity was planned or
  performed.
- No organizationally independent verifier reviewed this baseline.
- The run predates the initial commit, so it has no immutable source SHA.
- Re-run `./scripts/verify.sh all` and the GitHub Actions workflow after the
  initial commit. Record the passing commit and CI URL before using CI status as
  public evidence.
