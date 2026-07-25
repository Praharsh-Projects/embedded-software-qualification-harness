# Software Requirements Specification

Document ID: `ESQH-SRS-001`
Version: `0.1.0`
Baseline: `ESQH-BL-0.1.0`
Status: Portfolio project baseline

## 1. Purpose

This SRS defines verifiable requirements for a small embedded-software
qualification harness. The deliverable is a freestanding C11 artifact for a
generic Cortex-M0+ target together with native host simulations and automated
verification. It is not a physical-device or industry-certification claim.

The machine-readable authority for requirement IDs and statements is
[`requirements/requirements.json`](../requirements/requirements.json).

## 2. System context

The controller receives framed commands, maintains a bounded operating state,
samples a virtual SPI register model, exchanges simulated classic CAN frames,
and emits bounded Ethernet-style datagrams and telemetry. All interfaces are
in-memory software models. The host executable supplies a deterministic clock
and scenario inputs. The cross-compiled artifact proves that the portable code
can be linked without an operating system or hosted C library for the generic
instruction target.

## 3. States

- `INIT`: startup and self-test have not completed.
- `OPERATIONAL`: self-test passed and a valid heartbeat is current.
- `DEGRADED`: a recoverable interface fault is latched.
- `SAFE`: a control timeout or nonrecoverable condition prevents operation.

Only transitions documented in `SSDD.md` are permitted.

## 4. Requirements

### 4.1 Platform and initialization

- **SRS-PLT-001 — Freestanding Cortex-M0+ artifact.** The build shall produce
  a little-endian ARM EABI freestanding ELF targeting the generic Cortex-M0+
  instruction set with `Reset_Handler` as its entry point.
- **SRS-BOOT-001 — Controlled initialization.** Controller initialization with
  a valid configuration shall clear runtime state and enter the `INIT` state.
- **SRS-SCH-001 — Cooperative period accounting.** The application shall count
  fixed 1 ms, 10 ms, and 100 ms cooperative release periods using bounded
  counters; it does not execute task bodies.
- **SRS-STA-001 — Controller states.** The controller shall implement the
  `INIT`, `OPERATIONAL`, `DEGRADED`, and `SAFE` states and shall change state
  only through the documented self-test, heartbeat, fault, and recovery rules.

### 4.2 Interface behavior

- **SRS-UART-001 — Valid UART frame handling.** The UART protocol component
  shall, for each decode call supplied one complete bounded UART frame with a
  valid marker, UART interface field, supported payload length, and CRC, return
  `ESQH_OK` and populate the caller-provided destination with that frame.
- **SRS-UART-002 — Invalid UART frame rejection.** The UART protocol component
  shall reject truncated buffers, invalid-CRC buffers, marker/interface-
  mismatched buffers, and structurally complete valid-CRC buffers with payloads
  greater than 64 bytes while leaving the destination frame unchanged; encode
  rejection shall leave the output buffer and written count unchanged.
- **SRS-SPI-001 — Bounded SPI model.** The SPI model shall provide deterministic
  reads and writes over sixteen virtual registers and shall reject invalid
  addresses and transfer lengths.
- **SRS-CAN-001 — Bounded classic CAN model.** The CAN model shall accept only
  eleven-bit identifiers and payload lengths from zero through eight bytes and
  shall reject out-of-range input.
- **SRS-ETH-001 — Bounded Ethernet-style datagram model.** The Ethernet model
  shall accept payloads from zero through 256 bytes and shall reject oversized
  input.
- **SRS-TLM-001 — Deterministic telemetry content.** The 24-byte telemetry
  record shall contain sequence, controller state, fault bitmap, setpoint, SPI
  register zero, five interface counters, and CRC-16 in a deterministic field
  order.

### 4.3 Fault and recovery behavior

- **SRS-FLT-001 — Fault latching and severity.** The fault handler shall latch
  supplied fault bits, drive recoverable faults to `DEGRADED`, and drive
  critical or nonrecoverable faults to `SAFE`.
- **SRS-WDG-001 — Control heartbeat timeout.** More than 100 simulated
  milliseconds without a valid control heartbeat shall force the controller
  into `SAFE`.
- **SRS-RCV-001 — Controlled recovery.** A recovery command shall clear only
  recoverable faults and shall require successful self-test and a fresh
  heartbeat before the controller returns to `OPERATIONAL`.

### 4.4 Quality and configuration constraints

- **SRS-BND-001 — Bounded storage.** Runtime state and interface queues shall
  use fixed-size storage with explicit compile-time bounds.
- **SRS-DET-001 — Repeatable behavior.** Identical initial state and input
  traces shall produce byte-identical telemetry and normalized result output.
- **SRS-RES-001 — Static resource budget.** The linked artifact shall use less
  than 64 KiB of flash and less than 8 KiB of statically allocated RAM.
- **SRS-CFG-001 — Configuration identity.** The build and qualification outputs
  shall expose the repository version and configuration baseline identifier.

## 5. Verification

Each requirement maps to at least one design component and verification case
in `TRACEABILITY.md`. Interface and behavior requirements are verified through
host tests. Target-specific requirements are verified through ELF/map
inspection. Startup source inspection confirms data/BSS initialization
separately from the host controller-initialization case. No test result
represents physical-target execution.

The build additionally enforces a project design constraint against dynamic
allocation and hosted I/O in firmware-linked source, links local freestanding
memory primitives, and rejects unresolved ARM symbols. That build gate is
supporting evidence, not a broader claim than `SRS-BND-001`.
