# Scope, Assumptions, and Limitations

## Evidence boundary

This repository demonstrates a project-scoped embedded-software lifecycle using
a freestanding C11 build and executable host simulations. It is not a
production system, a hardware-in-the-loop environment, or evidence of
qualification to any external standard.

## What is implemented

- A cross-compiled ELF artifact for the generic ARM Cortex-M0+ instruction set.
- Portable application logic using fixed-size storage and no operating system.
- Deterministic, in-memory models of UART, SPI, classic CAN, and bounded
  Ethernet-style datagrams.
- Host-executable unit, integration, and qualification tests.
- Project-style requirements, design, interface, test, configuration, and
  traceability records.

## What is not implemented or claimed

- No firmware has been flashed to or executed on physical hardware.
- There are no MCU-specific clocks, pin multiplexing, peripheral registers,
  DMA channels, interrupt priorities, board-support package, or electrical
  drivers.
- The interface models do not reproduce voltage levels, baud-rate tolerances,
  SPI setup/hold timing, CAN arbitration or bit timing, Ethernet PHY/MAC
  behavior, packet loss, or real network stacks.
- No oscilloscope, logic analyzer, CAN adapter, or other laboratory instrument
  was used.
- No RTOS is used. The scheduler is a deterministic cooperative software
  component, not an RTOS kernel.
- No DOORS or SVN workflow is represented.
- The documents resemble common lifecycle artifacts but do not establish
  compliance with IEC 61508, ISO 26262, DO-178C, EN 50128, IEC 62304, or any
  other industry standard.
- "Qualification" means verification against the requirements defined in this
  repository. It is not third-party, regulatory, safety, or customer
  qualification.
- Host tests execute native code against simulated interfaces. The ARM artifact
  is verified by compilation and structural inspection, not target execution.

## Generic target assumptions

The linker model assumes 64 KiB of flash beginning at `0x08000000` and 8 KiB
of RAM beginning at `0x20000000`. These values describe a synthetic target used
to make the artifact inspectable; they are not the memory map of a named board.
Porting to hardware would require a board-specific linker description, clock
and peripheral initialization, interrupt integration, device drivers, and
physical validation.

## Reproducibility boundary

CI results are evidence only for the commit and tool versions shown in that CI
run. A committed test report is a snapshot, not a guarantee that later commits
pass. Run the local verification commands or inspect the current CI status
before relying on a result.
