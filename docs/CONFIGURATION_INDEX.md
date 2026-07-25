# Software Configuration Index

Document ID: `ESQH-SCI-001`
Version: `0.1.0`
Baseline: `ESQH-BL-0.1.0`
Version authority: [`VERSION`](../VERSION)

## 1. Baseline policy

A project baseline is identified by the `VERSION` value, an immutable Git
commit, and, when published, a matching signed or annotated tag. CI artifacts
must record the commit SHA. Versioning controls this repository only; it is not
a claim of customer acceptance or regulated configuration management.

## 2. Configuration items

| ID | Configuration item | Controlled paths | Verification |
|---|---|---|---|
| `CI-001` | Portable firmware/application source | `include/`, `src/`, `firmware/` | Native compile, ARM compile, tests |
| `CI-002` | Host interface simulation and qualification executable | host-linked source and C cases | Native compile, `--json` execution |
| `CI-003` | Build/toolchain configuration | `CMakeLists.txt`, `cmake/`, `Makefile` | Clean configure and build |
| `CI-004` | Unit/integration verification source | `tests/` | CTest |
| `CI-005` | Qualification definitions and automation | `qualification/`, `tools/`, `requirements/` | Python tests, runner, traceability |
| `CI-006` | Lifecycle documentation | `docs/` | ID/traceability review |
| `CI-007` | Continuous-integration workflow | `.github/workflows/` | GitHub Actions result |
| `CI-008` | Generated evidence and ARM artifacts | build/report output | Artifact inspection and SHA-256 |

The machine-readable index is
[`config/configuration_items.json`](../config/configuration_items.json).

## 3. Generated artifacts

The following are derived, not source-controlled configuration items:

- host qualification executable;
- CTest result logs;
- qualification JSON and Markdown reports;
- ARM `.elf`, `.bin`, and linker `.map`;
- ELF inspection result and SHA-256 files.

They are valid only for their recorded source commit and toolchain. CI uploads
them without treating them as independently maintained source.

## 4. Change control

1. Change requirements and design records before or with affected code.
2. Update unit/integration and qualification mappings.
3. Run the full verification script from a clean build directory.
4. Review the diff for unrelated or generated content.
5. Record user-visible changes in `CHANGELOG.md`.
6. Create a baseline tag only after CI passes.

The repository does not simulate DOORS, SVN, a commercial change-control
system, or an external Configuration Manager approval.

## 5. Toolchain record

Every report should record:

- operating system and architecture;
- native compiler and CMake versions;
- Python version;
- ARM compiler/binutils versions for the ARM job;
- Git commit and repository version.

Tool versions are evidence metadata, not configuration guarantees for future
runs.
