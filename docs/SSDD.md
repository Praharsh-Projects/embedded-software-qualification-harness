# Software System and Design Description

Document ID: `ESQH-SSDD-001`
Version: `0.1.0`
Baseline: `ESQH-BL-0.1.0`

## 1. Architecture

The system separates portable controller logic from target startup code and
from executable host simulations.

```text
qualification procedures
          |
          v
Python runner --> host qualification executable
                         |
                         v
             portable C11 application core
              |       |       |       |
             UART     SPI     CAN   datagram
             model   model   model    model

ARM cross-build --> startup/vector/linker + the complete portable core
```

The ARM build is structurally inspected but not executed. Behavioral evidence
comes from the host executable, which supplies deterministic time and
in-memory interface events.

## 2. Design components

### SSDD-CMP-001 — Startup, vector, and linker component

Owns the vector table, `Reset_Handler`, data/BSS initialization, stack symbol,
generic flash/RAM layout, and transfer to the firmware entry function. The
component uses no vendor SDK and performs no board/peripheral initialization.
An inert, volatile-gated link-contract path references every public core API so
linker garbage collection cannot turn full-core inspection into subset-only
evidence. The gate is zero in normal startup and the path is never behavioral
target evidence.

### SSDD-CMP-002 — Application and cooperative scheduler

Owns the application context and bounded 1 ms, 10 ms, and 100 ms counters.
Each scheduler step consumes a caller-supplied simulated tick. Counters are
decremented/reloaded without division. There is no preemption, RTOS, thread, or
dynamic task creation.

### SSDD-CMP-003 — Controller state machine

Stores one of `INIT`, `OPERATIONAL`, `DEGRADED`, or `SAFE` and accepts explicit
events. The transition policy is:

| Current state | Event | Next state |
|---|---|---|
| `INIT` | self-test passed and heartbeat current | `OPERATIONAL` |
| `INIT` | self-test failed | `SAFE` |
| `OPERATIONAL` | recoverable interface fault | `DEGRADED` |
| `OPERATIONAL` or `DEGRADED` | heartbeat expired or fatal fault | `SAFE` |
| `DEGRADED` | recovery accepted | `INIT` |
| `SAFE` | recovery requested | `SAFE` (request rejected) |

After recovery, a fresh self-test and heartbeat are required to move from
`INIT` to `OPERATIONAL`. Returning from `SAFE` requires a platform reset; the
project recovery command cannot clear a fatal or watchdog condition.
All other transitions are rejected and leave the state unchanged.

### SSDD-CMP-004 — UART protocol parser

Encodes and decodes complete bounded buffers. It checks the UART marker,
interface field, payload length, and CRC before publishing a frame. Malformed
input cannot update the output frame. The component is not a streaming UART
receiver and retains no partial frame between calls.

### SSDD-CMP-005 — SPI interface model

Represents a virtual device as sixteen byte-addressable registers and a
SPI-marked frame format with a 32-byte payload limit. Register operations check
the address before accessing the static array. The model captures functional
software transaction semantics only.

### SSDD-CMP-006 — CAN interface model

Represents classic CAN frames using an eleven-bit identifier, sequence, DLC,
and eight data bytes. Valid frames may be placed in the controller's shared
fixed eight-frame FIFO. The model excludes physical-layer and arbitration
behavior.

### SSDD-CMP-007 — Ethernet-style datagram model

Represents an application datagram as a marker, identifiers, sequence, length,
and at most 256 bytes. Valid frames may be placed in the controller's shared
fixed eight-frame FIFO. No MAC, IP, UDP, TCP, socket, or PHY implementation is
present.

### SSDD-CMP-008 — Fault manager

Stores faults in a fixed-width bitmap and maps each fault to recoverable or
fatal severity. Invalid input and queue overflow latch their assigned bits.
Recovery clears only the documented recoverable mask.

### SSDD-CMP-009 — Telemetry encoder

Serializes a 16-bit sequence, controller state, reserved byte, 32-bit fault
bitmap, setpoint, SPI register zero, four accepted counters, one rejected
counter, and CRC-16 into a 24-byte record. It does not include wall-clock time,
addresses, or nondeterministic identifiers.

### SSDD-CMP-010 — Host scenario registry and qualification target

Runs the committed C cases against fresh contexts. `--json` emits one document
containing the project, version, baseline, every case ID, name, lowercase
`passed` or `failed` status, and bounded diagnostic message. The Python runner
normalizes those statuses. A case result is independent of execution order.

### SSDD-CMP-011 — Python qualification pipeline

Validates requirements and procedure schemas, executes the C target or consumes
one explicitly captured result document, and reconciles every returned case
with its procedure mapping. It cross-checks project, version, and baseline
identity, rejects missing/unknown IDs, and emits deterministic JSON and
Markdown reports. Input or execution failures produce a nonzero exit status.

## 3. Data ownership and bounds

- The application context owns state, tick counters, faults, telemetry state,
  and all interface-model queues.
- No component returns a mutable pointer outside the owning context.
- Incoming sizes are validated before copy or queue operations.
- Storage is static or automatic with compile-time bounds; heap allocation is
  prohibited in firmware-linked sources.
- Compiler-required `memcpy` and `memset` operations resolve to the
  firmware-owned freestanding implementations; hosted I/O and dynamic
  allocation are absent, and the final ELF has no unresolved symbol.
- Host-only reporting may use the host C/Python runtime and is not linked into
  the ARM artifact.

## 4. Error strategy

Input errors return a typed status and, where required, latch a fault. Full
queues reject the new item; they do not overwrite unread data. Fatal errors and
heartbeat expiry force `SAFE`. The host runner treats malformed JSON, duplicate
IDs, missing cases, unknown cases, timeouts, or nonzero C execution as
qualification failures.

## 5. Determinism strategy

Tests create a zeroed context, inject explicit ticks and inputs, and serialize
fields in stable order. There is no wall clock, random source, concurrency, or
external I/O in the core. Replay compares normalized outputs byte for byte.

## 6. Target-port boundary

A real board port would replace the simulated interface models and complete
clock, pin, interrupt, and peripheral initialization. Those activities are
outside this baseline and cannot be inferred from the generic ELF.
