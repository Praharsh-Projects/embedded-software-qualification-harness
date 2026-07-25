#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-all}"
HOST_BUILD="${ESQH_HOST_BUILD:-${ROOT}/build/host}"
ARM_BUILD="${ESQH_ARM_BUILD:-${ROOT}/build/arm}"
QUALIFICATION_OUTPUT="${ROOT}/build/qualification"
QUALIFICATION_BINARY="${ESQH_QUALIFICATION_BINARY:-${HOST_BUILD}/esqh_qualification}"
C_RESULTS="${QUALIFICATION_OUTPUT}/c_results.json"
ARM_ELF="${ESQH_ARM_ELF:-${ARM_BUILD}/esqh_firmware.elf}"
ARM_BIN="${ESQH_ARM_BIN:-${ARM_BUILD}/esqh_firmware.bin}"
ARM_MAP="${ESQH_ARM_MAP:-${ARM_BUILD}/esqh_firmware.map}"

export PYTHONDONTWRITEBYTECODE=1

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

verify_firmware_source_constraints() {
  local forbidden_calls
  local grep_status
  local matches
  forbidden_calls='(^|[^[:alnum:]_])(malloc|calloc|realloc|free|abort|exit|printf|fprintf|sprintf|snprintf|puts|putchar|fopen|fclose|fread|fwrite|system|popen)[[:space:]]*\('
  set +e
  matches="$(
    grep -R -n -E --include='*.c' "${forbidden_calls}" \
      "${ROOT}/src" "${ROOT}/firmware"
  )"
  grep_status=$?
  set -e
  if ((grep_status == 0)); then
    die "firmware-linked source contains dynamic-allocation or hosted-I/O calls: ${matches}"
  fi
  ((grep_status == 1)) || die "firmware source-constraint scan failed"
}

verify_host() {
  require_command cmake
  require_command python3

  cmake --fresh -S "${ROOT}" -B "${HOST_BUILD}" \
    -DCMAKE_BUILD_TYPE=Debug \
    -DESQH_ENABLE_SANITIZERS=ON
  cmake --build "${HOST_BUILD}" --parallel
  ctest --test-dir "${HOST_BUILD}" --output-on-failure
  python3 -m unittest discover -s "${ROOT}/tests/python" -v

  if [[ ! -x "${QUALIFICATION_BINARY}" ]]; then
    die "qualification binary not found or not executable: ${QUALIFICATION_BINARY}"
  fi

  mkdir -p "${QUALIFICATION_OUTPUT}"
  set +e
  "${QUALIFICATION_BINARY}" --json > "${C_RESULTS}"
  qualification_exit_code=$?
  set -e

  python3 "${ROOT}/tools/qualification_runner.py" \
    --c-results "${C_RESULTS}" \
    --binary-exit-code "${qualification_exit_code}" \
    --requirements "${ROOT}/requirements/requirements.json" \
    --procedures "${ROOT}/qualification/test_procedures.json" \
    --json-output "${QUALIFICATION_OUTPUT}/qualification_report.json" \
    --markdown-output "${QUALIFICATION_OUTPUT}/qualification_report.md"

  python3 "${ROOT}/tools/traceability_check.py" \
    --requirements "${ROOT}/requirements/requirements.json" \
    --procedures "${ROOT}/qualification/test_procedures.json" \
    --c-results "${C_RESULTS}"

  echo "PASS: host verification and qualification"
}

verify_arm() {
  require_command cmake
  require_command arm-none-eabi-gcc
  require_command arm-none-eabi-readelf
  require_command arm-none-eabi-nm
  require_command arm-none-eabi-size
  verify_firmware_source_constraints

  cmake --fresh -S "${ROOT}" -B "${ARM_BUILD}" \
    -DCMAKE_BUILD_TYPE=MinSizeRel \
    -DCMAKE_TOOLCHAIN_FILE="${ROOT}/cmake/toolchains/arm-none-eabi-gcc.cmake"
  cmake --build "${ARM_BUILD}" --parallel

  [[ -f "${ARM_ELF}" ]] || die "ARM ELF not found: ${ARM_ELF}"
  [[ -f "${ARM_BIN}" ]] || die "ARM binary not found: ${ARM_BIN}"
  [[ -f "${ARM_MAP}" ]] || die "ARM map not found: ${ARM_MAP}"

  elf_header="$(arm-none-eabi-readelf -h "${ARM_ELF}")"
  elf_sections="$(arm-none-eabi-readelf -S "${ARM_ELF}")"
  elf_attributes="$(arm-none-eabi-readelf -A "${ARM_ELF}")"
  elf_symbols="$(arm-none-eabi-nm "${ARM_ELF}")"
  [[ "${elf_header}" =~ Machine:[[:space:]]+ARM ]] || die "ELF machine is not ARM"
  [[ "${elf_header}" =~ Data:[[:space:]]+2.s[[:space:]]complement,[[:space:]]little[[:space:]]endian ]] \
    || die "ELF is not little-endian"
  [[ "${elf_header}" =~ Flags:.*EABI ]] || die "ELF does not declare an ARM EABI"
  [[ "${elf_sections}" =~ \.isr_vector ]] || die "ELF has no .isr_vector section"
  [[ "${elf_attributes}" =~ Tag_CPU_arch:[[:space:]]+v6S-M ]] \
    || die "ELF attributes do not identify the ARMv6-M profile"
  [[ "${elf_attributes}" =~ Tag_CPU_arch_profile:[[:space:]]+Microcontroller ]] \
    || die "ELF attributes do not identify the microcontroller profile"
  [[ "${elf_attributes}" =~ Tag_THUMB_ISA_use:[[:space:]]+Thumb-1 ]] \
    || die "ELF attributes do not identify the Thumb-1 instruction set"
  [[ "${elf_symbols}" =~ [[:space:]]T[[:space:]]+Reset_Handler ]] \
    || die "ELF has no text symbol Reset_Handler"

  entry_address="$(
    arm-none-eabi-readelf -h "${ARM_ELF}" |
      awk '/Entry point address:/ {print $4}'
  )"
  reset_address="0x$(
    arm-none-eabi-nm "${ARM_ELF}" |
      awk '$3 == "Reset_Handler" {print $1; exit}'
  )"
  entry_value=$((entry_address))
  reset_value=$((reset_address))
  (( (entry_value & ~1) == (reset_value & ~1) && (entry_value & 1) == 1 )) \
    || die "ELF Thumb entry ${entry_address} does not resolve to Reset_Handler ${reset_address}"

  undefined_symbols="$(arm-none-eabi-nm -u "${ARM_ELF}")"
  [[ -z "${undefined_symbols}" ]] || die "ELF has undefined symbols: ${undefined_symbols}"

  expected_symbols=(
    esqh_crc16
    esqh_config_default
    esqh_config_is_valid
    esqh_queue_init
    esqh_queue_push
    esqh_queue_pop
    esqh_wire_size
    esqh_frame_encode
    esqh_frame_decode
    esqh_spi_write
    esqh_spi_read
    esqh_controller_init
    esqh_controller_mark_self_test_passed
    esqh_controller_heartbeat
    esqh_controller_setpoint
    esqh_controller_latch_fault
    esqh_controller_recover
    esqh_controller_tick
    esqh_controller_receive
    esqh_controller_telemetry
  )
  for expected_symbol in "${expected_symbols[@]}"; do
    grep -q -E "[[:space:]][Tt][[:space:]]+${expected_symbol}$" <<<"${elf_symbols}" \
      || die "ELF does not retain public API symbol: ${expected_symbol}"
  done

  read -r text_bytes data_bytes bss_bytes _ < <(
    arm-none-eabi-size "${ARM_ELF}" | tail -n 1
  )
  [[ "${text_bytes}" =~ ^[0-9]+$ ]] || die "could not read ELF text size"
  [[ "${data_bytes}" =~ ^[0-9]+$ ]] || die "could not read ELF data size"
  [[ "${bss_bytes}" =~ ^[0-9]+$ ]] || die "could not read ELF bss size"

  flash_bytes=$((text_bytes + data_bytes))
  ram_bytes=$((data_bytes + bss_bytes))
  ((flash_bytes < 65536)) || die "flash budget exceeded: ${flash_bytes} bytes"
  ((ram_bytes < 8192)) || die "static RAM budget exceeded: ${ram_bytes} bytes"

  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${ARM_ELF}" "${ARM_BIN}" "${ARM_MAP}"
  else
    shasum -a 256 "${ARM_ELF}" "${ARM_BIN}" "${ARM_MAP}"
  fi
  arm-none-eabi-size "${ARM_ELF}"
  echo "PASS: generic Cortex-M0+ artifact inspection"
  echo "NOTE: artifact was compiled and inspected; it was not run on hardware"
}

case "${MODE}" in
  host)
    verify_host
    ;;
  arm)
    verify_arm
    ;;
  all)
    verify_host
    verify_arm
    ;;
  *)
    die "usage: $0 [host|arm|all]"
    ;;
esac
