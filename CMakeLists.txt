cmake_minimum_required(VERSION 3.24)

project(embedded_software_qualification_harness VERSION 0.1.0 LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

option(ESQH_ENABLE_SANITIZERS "Enable AddressSanitizer and UndefinedBehaviorSanitizer for host tests" ON)
if(CMAKE_CROSSCOMPILING)
  set(ESQH_BUILD_HOST_DEFAULT OFF)
  set(ESQH_BUILD_ARM_DEFAULT ON)
else()
  set(ESQH_BUILD_HOST_DEFAULT ON)
  set(ESQH_BUILD_ARM_DEFAULT OFF)
endif()
option(ESQH_BUILD_HOST "Build the native host qualification target" ${ESQH_BUILD_HOST_DEFAULT})
option(ESQH_BUILD_ARM "Build the generic Cortex-M0+ firmware artifact" ${ESQH_BUILD_ARM_DEFAULT})

set(ESQH_WARNING_FLAGS -Wall -Wextra -Wpedantic -Werror)

set(
  ESQH_CORE_SOURCES
  src/config.c
  src/controller.c
  src/crc.c
  src/frame.c
  src/queue.c
)

add_library(esqh_core STATIC ${ESQH_CORE_SOURCES})
target_include_directories(esqh_core PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/include")
target_compile_options(esqh_core PRIVATE ${ESQH_WARNING_FLAGS})

if(CMAKE_CROSSCOMPILING AND ESQH_BUILD_ARM)
  target_compile_options(
    esqh_core
    PRIVATE
      -mcpu=cortex-m0plus
      -mthumb
      -ffreestanding
      -fno-builtin
      -fno-stack-protector
      -fno-jump-tables
      -ffunction-sections
      -fdata-sections
      -Os
  )

  add_executable(esqh_firmware firmware/startup.c firmware/main.c)
  target_link_libraries(esqh_firmware PRIVATE esqh_core)
  target_include_directories(esqh_firmware PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/include")
  target_compile_options(
    esqh_firmware
    PRIVATE
      ${ESQH_WARNING_FLAGS}
      -mcpu=cortex-m0plus
      -mthumb
      -ffreestanding
      -fno-builtin
      -fno-stack-protector
      -fno-jump-tables
      -ffunction-sections
      -fdata-sections
      -Os
  )
  target_link_options(
    esqh_firmware
    PRIVATE
      -mcpu=cortex-m0plus
      -mthumb
      -nostartfiles
      -nodefaultlibs
      -nostdlib
      -Wl,--gc-sections
      -Wl,-e,Reset_Handler
      "-Wl,-Map=${CMAKE_BINARY_DIR}/esqh_firmware.map"
      "-T${CMAKE_CURRENT_SOURCE_DIR}/firmware/linker.ld"
  )
  set_target_properties(esqh_firmware PROPERTIES SUFFIX ".elf" LINK_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/firmware/linker.ld")

  add_custom_command(
    TARGET esqh_firmware
    POST_BUILD
    COMMAND "${CMAKE_OBJCOPY}" -O binary "$<TARGET_FILE:esqh_firmware>" "${CMAKE_BINARY_DIR}/esqh_firmware.bin"
    COMMAND "${CMAKE_SIZE}" "$<TARGET_FILE:esqh_firmware>"
    VERBATIM
  )
elseif(NOT CMAKE_CROSSCOMPILING AND ESQH_BUILD_HOST)
  if(ESQH_ENABLE_SANITIZERS AND CMAKE_C_COMPILER_ID MATCHES "Clang|GNU")
    target_compile_options(esqh_core PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer)
    target_link_options(esqh_core INTERFACE -fsanitize=address,undefined)
  endif()

  add_executable(esqh_qualification tests/c/test_main.c)
  target_link_libraries(esqh_qualification PRIVATE esqh_core)
  target_compile_options(esqh_qualification PRIVATE ${ESQH_WARNING_FLAGS})

  if(ESQH_ENABLE_SANITIZERS AND CMAKE_C_COMPILER_ID MATCHES "Clang|GNU")
    target_compile_options(
      esqh_qualification
      PRIVATE
        -fsanitize=address,undefined
        -fno-omit-frame-pointer
    )
  endif()

  enable_testing()
  add_test(NAME esqh_host_tests COMMAND esqh_qualification)
endif()
