# Requirements Traceability Matrix

Document ID: `ESQH-RTM-001`
Version: `0.1.0`
Baseline: `ESQH-BL-0.1.0`

The Python traceability checker treats
[`requirements/requirements.json`](../requirements/requirements.json),
[`qualification/test_procedures.json`](../qualification/test_procedures.json),
and the live C `--json` result as machine-readable authorities. It fails for an
unknown, missing, duplicate, or unmapped ID.

| Requirement | Design | Procedure | C cases | Additional evidence |
|---|---|---|---|---|
| `SRS-PLT-001` | `SSDD-CMP-001` | `QTP-001` | `TC-PLT-001` | ARM ELF header, entry, vector, symbol inspection |
| `SRS-BOOT-001` | `SSDD-CMP-003` | `QTP-002` | `TC-BOOT-001` | Controller initialization test |
| `SRS-SCH-001` | `SSDD-CMP-002` | `QTP-002` | `TC-SCH-001` | Native scheduler test |
| `SRS-STA-001` | `SSDD-CMP-003` | `QTP-003`, `QTP-005` | `TC-STA-001`, `TC-STA-002`, `TC-FLT-001`, `TC-RCV-001` | Transition-table review |
| `SRS-UART-001` | `SSDD-CMP-004` | `QTP-008` | `TC-IF-UART-001` | Complete-buffer round trip |
| `SRS-UART-002` | `SSDD-CMP-004` | `QTP-008` | `TC-IF-UART-002` | Negative-vector review |
| `SRS-SPI-001` | `SSDD-CMP-005` | `QTP-009` | `TC-IF-SPI-001` | Boundary review |
| `SRS-CAN-001` | `SSDD-CMP-006` | `QTP-009` | `TC-IF-CAN-001` | Boundary review |
| `SRS-ETH-001` | `SSDD-CMP-007` | `QTP-010` | `TC-IF-ETH-001` | Boundary review |
| `SRS-TLM-001` | `SSDD-CMP-009` | `QTP-007` | `TC-TLM-001` | Representative byte checks plus encoder-offset inspection |
| `SRS-FLT-001` | `SSDD-CMP-008` | `QTP-003`, `QTP-005` | `TC-STA-002`, `TC-FLT-001` | Fault-mask and severity review |
| `SRS-WDG-001` | `SSDD-CMP-002`, `SSDD-CMP-003`, `SSDD-CMP-008` | `QTP-004` | `TC-CMD-HB-001`, `TC-WDG-001` | 100/101 ms boundary |
| `SRS-RCV-001` | `SSDD-CMP-003`, `SSDD-CMP-008` | `QTP-005` | `TC-RCV-001` | Recovery-mask review |
| `SRS-BND-001` | `SSDD-CMP-001`–`009` | `QTP-006`, `QTP-008`, `QTP-009`, `QTP-010` | `TC-BND-001`, interface cases | Fixed queue/structure boundaries plus source inspection |
| `SRS-DET-001` | `SSDD-CMP-002`, `SSDD-CMP-003`, `SSDD-CMP-009`, `SSDD-CMP-010` | `QTP-006`, `QTP-007` | `TC-DET-001`, `TC-TLM-001` | Repeated runner-output comparison |
| `SRS-RES-001` | `SSDD-CMP-001` | `QTP-001`, `QTP-006` | `TC-PLT-001`, `TC-RES-001` | ARM size/map inspection is mandatory |
| `SRS-CFG-001` | `SSDD-CMP-001`, `SSDD-CMP-011` | `QTP-001` | `TC-CFG-001`, `TC-CFG-002` | Version/configuration-index inspection |

## Important interpretation

`TC-PLT-001` and `TC-RES-001` exercise the host-visible platform/resource
contract. They do not inspect or execute an ARM binary. `SRS-PLT-001` and the
ARM memory portion of `SRS-RES-001` pass the full acceptance gate only when the
separate ARM artifact inspection also passes.

The full verification gate separately scans firmware-linked source for dynamic
allocation and hosted I/O, checks the expected public API symbols, and rejects
unresolved ARM symbols. Those constraints support the design but do not imply
physical-target execution.

The short form `SSDD-CMP-001`–`009` in the bounded-storage row means each named
component from `SSDD-CMP-001` through `SSDD-CMP-009`; the JSON authority lists
those IDs explicitly.
