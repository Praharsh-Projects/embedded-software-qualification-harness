# Software Qualification Test Procedures

Document ID: `ESQH-SQTPROC-001`
Version: `0.1.0`
Baseline: `ESQH-BL-0.1.0`

These procedures are executed through the host qualification target and Python
runner. The exact machine-readable mappings are in
[`qualification/test_procedures.json`](../qualification/test_procedures.json).
Unless stated otherwise, each case starts with a fresh zeroed context.

## QTP-001 — Configuration and generic target contract

Cases: `TC-CFG-001`, `TC-CFG-002`, `TC-PLT-001`

1. Build and invoke the native configuration/platform-contract cases.
2. Confirm the result, requirements, and procedures expose the same project,
   repository version, and configuration baseline; confirm invalid
   configuration is rejected.
3. Separately cross-build the ARM target.
4. Inspect the ELF header, entry point, vector section, undefined symbols, map,
   and resource limits.

Pass: all three host cases pass and the independent ARM artifact inspection
passes. `TC-PLT-001` alone is not evidence of ARM target execution.

## QTP-002 — Boot and cooperative period accounting

Cases: `TC-BOOT-001`, `TC-SCH-001`

1. Initialize the application context.
2. Confirm the initial controller state is `INIT`.
3. Advance deterministic millisecond ticks across 1 ms, 10 ms, and 100 ms
   release boundaries.
4. Compare release counts with the configured periods.

Pass: initialization and all fixed-period release counts match the expected
values. The test counts releases and does not execute task bodies.

## QTP-003 — Controller state transitions

Cases: `TC-STA-001`, `TC-STA-002`

1. Complete self-test and supply a heartbeat to exercise `INIT` to
   `OPERATIONAL`.
2. In a fresh context, latch a recoverable fault and inspect `DEGRADED`.
3. Latch a critical fault and inspect `SAFE`.
4. Attempt recovery while the critical fault remains.

Pass: each documented rule reaches the expected state and recovery is rejected
while the nonrecoverable fault remains.

## QTP-004 — Heartbeat sequence and watchdog boundary

Cases: `TC-CMD-HB-001`, `TC-WDG-001`

1. Complete simulated self-test and call the heartbeat operation with a valid
   sequence.
2. Repeat that sequence and confirm it is rejected and latched.
3. In a fresh context, complete self-test without accepting a heartbeat and
   advance simulated time to 100 ms.
4. Confirm the state is still `INIT`, then advance one additional millisecond
   and confirm `SAFE`.
5. In another fresh context, complete self-test, accept a heartbeat, and
   advance simulated time to 100 ms.
6. Confirm the state is still `OPERATIONAL`, then advance one additional
   millisecond and confirm `SAFE`.

Pass: sequence guarding and both 100/101 ms watchdog branches match the
requirements. After self-test, expiry forces `SAFE` whether no heartbeat was
ever accepted or the last accepted heartbeat became stale.

## QTP-005 — Fault latching and controlled recovery

Cases: `TC-FLT-001`, `TC-RCV-001`

1. Start from a fresh valid controller context.
2. Inject a recoverable interface fault and inspect state/bitmap.
3. Request recovery and confirm the controller returns through `INIT`.
4. Provide self-test completion and a fresh heartbeat in the documented order.

Pass: the recoverable fault, state change, clear mask, and return sequence match
the design.

## QTP-006 — Resource boundaries and deterministic replay

Cases: `TC-RES-001`, `TC-BND-001`, `TC-DET-001`

1. Check the controller and queue structure bounds.
2. Fill and drain the fixed eight-frame queue and check full/empty behavior.
3. Capture normalized output for a fixed input trace.
4. Reinitialize the context and replay the identical trace.
5. Compare both outputs byte for byte.

Pass: host structures remain within their committed bounds, fixed-queue
behavior is correct, and replay outputs match exactly. The 64 KiB/8 KiB linked
ARM budgets still require the separate artifact check.

## QTP-007 — Telemetry content and order

Case: `TC-TLM-001`

1. Load known sequence, state, fault, and setpoint values.
2. Encode one telemetry record.
3. Test the 24-byte length, sequence, state, representative fault bytes, and
   CRC placement/value.
4. Inspect the encoder offsets for setpoint, SPI register zero, four accepted
   counters, and the rejected counter.

Pass: the C case passes its representative layout/CRC checks and source
inspection confirms every remaining required field occupies the documented
stable offset.

## QTP-008 — UART protocol validity and rejection

Cases: `TC-IF-UART-001`, `TC-IF-UART-002`

1. Encode and decode one UART frame containing a 64-byte payload.
2. Compare every decoded field with the input frame.
3. Decode a complete buffer with a corrupted CRC.
4. Decode a truncated buffer.
5. Decode buffers with the wrong marker, interface byte, and interface enum.
6. Attempt to encode a 65-byte UART payload and inspect the caller-owned output
   buffer and written-count sentinel.

Pass: the valid frame round-trips unchanged; every invalid buffer returns its
documented error without publishing a decoded frame, and rejected encode/decode
operations preserve caller-owned destinations.

## QTP-009 — SPI and classic CAN model boundaries

Cases: `TC-IF-SPI-001`, `TC-IF-CAN-001`

1. Round-trip a 16-byte SPI-marked frame.
2. Attempt to encode a 33-byte SPI-marked frame.
3. Read and write virtual register `0x0F`.
4. Attempt to write register `0x10`.
5. Round-trip an eight-byte classic CAN frame.
6. Attempt to encode a nine-byte payload and an identifier above `0x7FF`.

Pass: valid modeled operations succeed; invalid SPI length/address and invalid
CAN length/identifier return their documented errors.

## QTP-010 — Ethernet-style datagram boundaries

Case: `TC-IF-ETH-001`

1. Round-trip Ethernet-style frames with zero- and 256-byte payloads.
2. Attempt to encode a 257-byte payload.

Pass: both valid boundary frames round-trip unchanged and the oversized payload
is rejected before any out-of-range copy.

## Result recording

The runner records case and procedure statuses in JSON and Markdown. A failed,
missing, unknown, duplicate, or incomplete case fails the procedure. Reports
must identify the source baseline. A host PASS must not be restated as a
physical-hardware result.
