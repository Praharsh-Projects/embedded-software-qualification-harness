# Embedded Software Qualification Harness

[![Verification](https://github.com/Praharsh-Projects/embedded-software-qualification-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/Praharsh-Projects/embedded-software-qualification-harness/actions/workflows/ci.yml)

A bounded portfolio project demonstrating a small embedded-software lifecycle:
requirements, design, interface contracts, freestanding C11, host-executable
verification, configuration control, and traceable qualification evidence.

The project cross-compiles a generic ARM Cortex-M0+ artifact and exercises the
portable logic against deterministic in-memory models of UART, SPI, classic
CAN, and bounded Ethernet-style datagrams.

> **Evidence boundary:** no firmware was run on physical hardware. The
> interfaces are software simulations, not peripheral drivers. There is no
> RTOS, oscilloscope/logic-analyzer evidence, external safety certification, or
> claim of compliance with an industry standard. See
> [Scope, Assumptions, and Limitations](docs/LIMITATIONS.md).

## What this repository demonstrates

- Freestanding C11 design with fixed-size storage and explicit fault handling.
- A generic Cortex-M0+ ELF/linker artifact that can be inspected in CI.
- Deterministic state, heartbeat, watchdog, recovery, and telemetry behavior.
- Host models of UART framing, a virtual SPI register device, classic CAN
  frames, and bounded Ethernet-style datagrams.
- Twenty live C cases reconciled into ten qualification procedures.
- Seventeen requirements linked to design components, procedures, cases, and
  result evidence.
- A Python runner that rejects malformed, missing, duplicate, unknown, failed,
  incomplete, unmapped, or baseline-mismatched evidence.
- One captured C result document drives both qualification reporting and the
  standalone traceability gate in the full verification script.
- SRS, SSDD, ICD, SQTP, procedures, report, configuration index, and
  traceability records.

## Architecture

```text
requirements + procedures
          |
          v
Python qualification runner
          |
          v
native C qualification target --json
          |
          v
portable application/controller
   |        |        |        |
 UART      SPI      CAN    datagram
 model    model    model     model

ARM cross-build: startup/vector/linker + complete portable core
                 (retained, compiled, and inspected; not run)
```

## Prerequisites

Host verification:

- CMake
- a C11 compiler
- Python 3.10 or newer

ARM artifact verification additionally requires an
`arm-none-eabi-gcc`/binutils toolchain. CI installs it on Ubuntu. The full
verification command intentionally fails rather than silently skipping the ARM
gate when that toolchain is unavailable.

## Verification

Host build, CTest, Python tests, qualification, and traceability:

```bash
./scripts/verify.sh host
```

ARM cross-build and structural inspection:

```bash
./scripts/verify.sh arm
```

All gates:

```bash
./scripts/verify.sh all
```

The host path writes generated evidence below `build/qualification/`. The ARM
path writes the ELF/map/bin and inspection output below `build/arm/`. These
outputs are tied to the current source state and are not committed.

To inspect the C case contract directly after a host build:

```bash
build/host/esqh_qualification --json
```

To invoke the Python runner explicitly:

```bash
python3 tools/qualification_runner.py \
  --binary build/host/esqh_qualification \
  --requirements requirements/requirements.json \
  --procedures qualification/test_procedures.json \
  --json-output build/qualification/qualification_report.json \
  --markdown-output build/qualification/qualification_report.md
```

The runner also accepts an already captured result with `--c-results`; the
full verification script uses that mode so reporting and traceability consume
the same execution.

## Lifecycle records

| Record | Purpose |
|---|---|
| [SRS](docs/SRS.md) | Seventeen uniquely identified requirements |
| [SSDD](docs/SSDD.md) | Architecture, modules, state, bounds, and error strategy |
| [ICD](docs/ICD.md) | Software-model frame and transaction contracts |
| [SQTP](docs/SQTP.md) | Test strategy, gates, and confidence limits |
| [Test procedures](docs/TEST_PROCEDURES.md) | Ten repeatable qualification procedures |
| [Test report](docs/TEST_REPORT.md) | Snapshot of an identified completed run |
| [Configuration index](docs/CONFIGURATION_INDEX.md) | Controlled and generated configuration items |
| [Traceability](docs/TRACEABILITY.md) | Requirement-to-design-to-test mapping |
| [Limitations](docs/LIMITATIONS.md) | Explicit exclusions and claim boundaries |

Machine-readable authorities:

- `requirements/requirements.json`
- `qualification/test_procedures.json`
- `config/configuration_items.json`
- the live C `--json` output

## Safe interpretation

Successful verification supports saying that this repository:

- builds a freestanding C11 artifact targeting generic Cortex-M0+;
- runs deterministic host simulations and tests of bounded interface contracts;
- automates project-scoped qualification and traceability reporting; and
- maintains project-style lifecycle and configuration documentation.

It does not support saying that the author deployed to an MCU, used physical
lab equipment, implemented real peripheral drivers, worked with an RTOS,
qualified production or mission-critical software, or complied with an
external standard.

## License

[MIT](LICENSE)
