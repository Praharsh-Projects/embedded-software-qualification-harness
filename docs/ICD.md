# Interface Control Description

Document ID: `ESQH-ICD-001`
Version: `0.1.0`
Baseline: `ESQH-BL-0.1.0`

## 1. Scope

This ICD specifies software-facing formats used by deterministic interface
models. It does not specify electrical characteristics, bus timing, physical
connectors, peripheral registers, or a real network stack.

## 2. Common status contract

Interface operations return one of:

| Status | Meaning |
|---|---|
| `ESQH_OK` | Operation accepted |
| `ESQH_ERR_ARGUMENT` | A required pointer is invalid |
| `ESQH_ERR_LENGTH` | Buffer or payload length is invalid |
| `ESQH_ERR_CHECKSUM` | Frame CRC does not match |
| `ESQH_ERR_RANGE` | Interface, ID, address, or value is out of range |
| `ESQH_ERR_FULL` | The shared fixed queue has no free slot |
| `ESQH_ERR_EMPTY` | No queued frame is available |
| `ESQH_ERR_SEQUENCE` | Command sequence is zero, repeated, or stale |
| `ESQH_ERR_STATE` | Current controller state/configuration forbids the action |

Rejected operations do not partially mutate the destination object.

## 3. UART model

### 3.1 Frame

```text
byte 0       start marker, 0xA5
byte 1       interface value, 0x01
bytes 2..3   message ID, big-endian
bytes 4..5   sequence, big-endian
bytes 6..7   payload length N, big-endian, 0..64
bytes 8..    N payload bytes
last 2       CRC-16/CCITT over every prior byte, big-endian
```

The decoder accepts one complete buffer per call. A bad CRC, wrong marker or
interface byte, truncation, trailing bytes, or payload length greater than 64
is rejected. There is no partial-frame retention, baud-rate behavior, UART
register, interrupt, or DMA model.

## 4. SPI model

SPI-marked frames use the same non-CAN layout as UART, with marker `0x5A`,
interface value `0x02`, and payload length from zero through 32 bytes.

The virtual device additionally contains sixteen one-byte registers addressed
`0x00` through `0x0F`. Software read/write calls operate on one register at a
time. Address `0x10` or greater is rejected before access.

The model resembles SPI Mode 0 transaction ordering for test readability but
does not reproduce chip-select timing, clock polarity/phase, setup/hold time,
full-duplex electrical behavior, or a physical sensor.

## 5. Classic CAN model

```text
bytes 0..1    unsigned 11-bit identifier encoded big-endian, 0x000..0x7FF
bytes 2..3    sequence, big-endian
byte 4        DLC, 0..8
bytes 5..     exactly DLC payload bytes
last 2        CRC-16/CCITT over every prior byte, big-endian
```

All modeled interface frames share one controller FIFO with a depth of eight.
A ninth enqueue returns `ESQH_ERR_FULL` and preserves queued frames. Invalid
identifiers return `ESQH_ERR_RANGE`; invalid DLC returns
`ESQH_ERR_LENGTH` during encoding. The model excludes extended identifiers,
remote/error frames, arbitration, acknowledgement, retransmission, bit
stuffing, and bus timing.

## 6. Ethernet-style datagram model

```text
bytes 0..1    marker, 0x45 0x53
bytes 2..3    message ID, big-endian
bytes 4..5    sequence, big-endian
bytes 6..7    payload length N, big-endian, 0..256
bytes 8..     N payload bytes
last 2        CRC-16/CCITT over every prior byte, big-endian
```

All modeled interface frames share the fixed eight-frame controller queue. A
payload length greater than 256 is rejected before copying. "Ethernet-style"
names the qualification boundary only: the model contains no Ethernet header,
MAC address, frame checksum, VLAN, IP, UDP, TCP, socket, or physical-layer
logic.

## 7. Telemetry record

Telemetry is exactly 24 bytes and uses big-endian integers:

```text
bytes 0..1    monotonically increasing 16-bit sequence
byte 2        controller state
byte 3        reserved, zero
bytes 4..7    32-bit fault bitmap
bytes 8..9    signed setpoint represented as its 16-bit bit pattern
bytes 10..11  SPI register zero
bytes 12..13  UART accepted counter, truncated to 16 bits
bytes 14..15  SPI accepted counter, truncated to 16 bits
bytes 16..17  CAN accepted counter, truncated to 16 bits
bytes 18..19  Ethernet-style accepted counter, truncated to 16 bits
bytes 20..21  rejected counter, truncated to 16 bits
bytes 22..23  CRC-16/CCITT over bytes 0..21
```

Qualification JSON is a host-reporting interface, not firmware telemetry.

## 8. Qualification executable

Invocation:

```bash
<qualification-binary> --json
```

The process emits one JSON object and no other standard output:

```json
{
  "cases": [
    {
      "id": "CASE-ID",
      "name": "Human-readable case name",
      "status": "passed",
      "message": "Bounded diagnostic"
    }
  ]
}
```

The live C executable emits `passed` or `failed`; the Python runner normalizes
accepted status spellings to `PASS`, `FAIL`, or `INCOMPLETE` in its report.
Every declared C case must appear once. Diagnostic content must not contain
source documents, credentials, memory addresses, or uncontrolled input.
