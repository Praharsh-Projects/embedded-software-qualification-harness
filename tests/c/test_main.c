#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "esqh/esqh.h"

typedef bool (*test_function_t)(void);

typedef struct {
    const char *id;
    const char *name;
    test_function_t function;
} test_case_t;

static esqh_controller_t make_controller(void) {
    esqh_config_t config;
    esqh_controller_t controller;
    esqh_config_default(&config);
    esqh_controller_init(&controller, &config);
    return controller;
}

static esqh_frame_t make_frame(esqh_interface_t interface_type, uint16_t length) {
    esqh_frame_t frame = {0};
    uint16_t index;
    frame.interface_type = interface_type;
    frame.message_id = interface_type == ESQH_INTERFACE_CAN ? 0x321u : 0x1201u;
    frame.sequence = 7u;
    frame.payload_length = length;
    for (index = 0u; index < length && index < ESQH_MAX_PAYLOAD; ++index) {
        frame.payload[index] = (uint8_t)(index ^ 0x5au);
    }
    return frame;
}

static bool frames_equal(const esqh_frame_t *left, const esqh_frame_t *right) {
    return left->interface_type == right->interface_type &&
           left->message_id == right->message_id &&
           left->sequence == right->sequence &&
           left->payload_length == right->payload_length &&
           memcmp(left->payload, right->payload, left->payload_length) == 0;
}

static bool tc_cfg_001(void) {
    esqh_config_t config;
    esqh_config_default(&config);
    return esqh_config_is_valid(&config) &&
           strcmp(config.version, ESQH_VERSION) == 0 &&
           strcmp(config.baseline, ESQH_BASELINE) == 0;
}

static bool tc_cfg_002(void) {
    esqh_config_t config;
    esqh_config_default(&config);
    config.watchdog_timeout_ms = 0u;
    if (esqh_config_is_valid(&config)) {
        return false;
    }
    esqh_config_default(&config);
    config.minimum_setpoint = config.maximum_setpoint;
    return !esqh_config_is_valid(&config);
}

static bool tc_plt_001(void) {
    return sizeof(uint8_t) == 1u && sizeof(uint16_t) == 2u &&
           sizeof(uint32_t) == 4u && sizeof(esqh_controller_t) < 8192u;
}

static bool tc_boot_001(void) {
    esqh_controller_t controller = make_controller();
    return controller.state == ESQH_STATE_INIT &&
           controller.fault_bitmap == 0u &&
           controller.queue.count == 0u &&
           !controller.self_test_passed;
}

static bool tc_sch_001(void) {
    esqh_controller_t controller = make_controller();
    unsigned int index;
    for (index = 0u; index < 100u; ++index) {
        esqh_controller_tick(&controller);
    }
    return controller.task_1ms_count == 100u &&
           controller.task_10ms_count == 10u &&
           controller.task_100ms_count == 1u;
}

static bool tc_sta_001(void) {
    esqh_controller_t controller = make_controller();
    esqh_controller_mark_self_test_passed(&controller);
    if (controller.state != ESQH_STATE_INIT) {
        return false;
    }
    return esqh_controller_heartbeat(&controller, 1u) == ESQH_OK &&
           controller.state == ESQH_STATE_OPERATIONAL;
}

static bool tc_sta_002(void) {
    esqh_controller_t controller = make_controller();
    esqh_controller_latch_fault(&controller, ESQH_FAULT_INTERFACE, false);
    if (controller.state != ESQH_STATE_DEGRADED) {
        return false;
    }
    esqh_controller_latch_fault(&controller, ESQH_FAULT_CRITICAL, true);
    return controller.state == ESQH_STATE_SAFE &&
           esqh_controller_recover(&controller) == ESQH_ERR_STATE;
}

static bool tc_cmd_hb_001(void) {
    esqh_controller_t controller = make_controller();
    esqh_controller_mark_self_test_passed(&controller);
    return esqh_controller_heartbeat(&controller, 4u) == ESQH_OK &&
           esqh_controller_heartbeat(&controller, 4u) == ESQH_ERR_SEQUENCE &&
           (controller.fault_bitmap & ESQH_FAULT_SEQUENCE) != 0u;
}

static bool tc_wdg_001(void) {
    esqh_controller_t no_heartbeat = make_controller();
    esqh_controller_t controller = make_controller();
    unsigned int index;
    esqh_controller_mark_self_test_passed(&no_heartbeat);
    for (index = 0u; index <= ESQH_WATCHDOG_DEFAULT_MS; ++index) {
        esqh_controller_tick(&no_heartbeat);
    }
    if (no_heartbeat.state != ESQH_STATE_SAFE ||
        (no_heartbeat.fault_bitmap & ESQH_FAULT_WATCHDOG) == 0u) {
        return false;
    }
    esqh_controller_mark_self_test_passed(&controller);
    if (esqh_controller_heartbeat(&controller, 1u) != ESQH_OK) {
        return false;
    }
    for (index = 0u; index < ESQH_WATCHDOG_DEFAULT_MS; ++index) {
        esqh_controller_tick(&controller);
    }
    if (controller.state != ESQH_STATE_OPERATIONAL) {
        return false;
    }
    esqh_controller_tick(&controller);
    return controller.state == ESQH_STATE_SAFE &&
           (controller.fault_bitmap & ESQH_FAULT_WATCHDOG) != 0u;
}

static bool tc_flt_001(void) {
    esqh_controller_t controller = make_controller();
    esqh_frame_t frame = make_frame((esqh_interface_t)99, 1u);
    return esqh_controller_receive(&controller, &frame) == ESQH_ERR_RANGE &&
           controller.state == ESQH_STATE_DEGRADED &&
           (controller.fault_bitmap & ESQH_FAULT_INTERFACE) != 0u;
}

static bool tc_rcv_001(void) {
    esqh_controller_t controller = make_controller();
    esqh_controller_mark_self_test_passed(&controller);
    if (esqh_controller_heartbeat(&controller, 1u) != ESQH_OK ||
        controller.state != ESQH_STATE_OPERATIONAL ||
        esqh_controller_recover(&controller) != ESQH_ERR_STATE) {
        return false;
    }
    esqh_controller_latch_fault(&controller, ESQH_FAULT_INTERFACE, false);
    if (esqh_controller_recover(&controller) != ESQH_OK ||
        controller.state != ESQH_STATE_INIT ||
        controller.self_test_passed ||
        controller.heartbeat_seen) {
        return false;
    }
    esqh_controller_mark_self_test_passed(&controller);
    return esqh_controller_heartbeat(&controller, 2u) == ESQH_OK &&
           controller.state == ESQH_STATE_OPERATIONAL;
}

static bool tc_res_001(void) {
    return sizeof(esqh_controller_t) < 8192u &&
           sizeof(esqh_frame_queue_t) <=
               (ESQH_FRAME_QUEUE_CAPACITY * sizeof(esqh_frame_t) + 8u);
}

static bool tc_bnd_001(void) {
    esqh_frame_queue_t queue;
    esqh_frame_t input = make_frame(ESQH_INTERFACE_CAN, 1u);
    esqh_frame_t output;
    unsigned int index;
    esqh_queue_init(&queue);
    for (index = 0u; index < ESQH_FRAME_QUEUE_CAPACITY; ++index) {
        input.sequence = (uint16_t)(index + 1u);
        if (esqh_queue_push(&queue, &input) != ESQH_OK) {
            return false;
        }
    }
    if (esqh_queue_push(&queue, &input) != ESQH_ERR_FULL) {
        return false;
    }
    for (index = 0u; index < ESQH_FRAME_QUEUE_CAPACITY; ++index) {
        if (esqh_queue_pop(&queue, &output) != ESQH_OK ||
            output.sequence != (uint16_t)(index + 1u)) {
            return false;
        }
    }
    return esqh_queue_pop(&queue, &output) == ESQH_ERR_EMPTY;
}

static bool tc_det_001(void) {
    esqh_controller_t left = make_controller();
    esqh_controller_t right = make_controller();
    uint8_t left_output[ESQH_TELEMETRY_SIZE];
    uint8_t right_output[ESQH_TELEMETRY_SIZE];
    esqh_controller_mark_self_test_passed(&left);
    esqh_controller_mark_self_test_passed(&right);
    if (esqh_controller_heartbeat(&left, 1u) != ESQH_OK ||
        esqh_controller_heartbeat(&right, 1u) != ESQH_OK ||
        esqh_controller_setpoint(&left, 2u, 123) != ESQH_OK ||
        esqh_controller_setpoint(&right, 2u, 123) != ESQH_OK) {
        return false;
    }
    esqh_controller_telemetry(&left, left_output);
    esqh_controller_telemetry(&right, right_output);
    return memcmp(left_output, right_output, sizeof(left_output)) == 0;
}

static bool tc_tlm_001(void) {
    esqh_controller_t controller = make_controller();
    uint8_t output[ESQH_TELEMETRY_SIZE];
    size_t length;
    controller.fault_bitmap = 0x01020304u;
    controller.setpoint = 0x1234;
    length = esqh_controller_telemetry(&controller, output);
    return length == ESQH_TELEMETRY_SIZE &&
           output[0] == 0u && output[1] == 1u &&
           output[2] == (uint8_t)ESQH_STATE_INIT &&
           output[4] == 1u && output[5] == 2u &&
           output[6] == 3u && output[7] == 4u &&
           esqh_crc16(output, 22u) ==
               (uint16_t)(((uint16_t)output[22] << 8u) | output[23]);
}

static bool interface_round_trip(esqh_interface_t interface_type, uint16_t length) {
    esqh_frame_t input = make_frame(interface_type, length);
    esqh_frame_t output = {0};
    uint8_t wire[ESQH_MAX_PAYLOAD + 16u];
    size_t written = 0u;
    return esqh_frame_encode(&input, wire, sizeof(wire), &written) == ESQH_OK &&
           esqh_frame_decode(interface_type, wire, written, &output) == ESQH_OK &&
           frames_equal(&input, &output);
}

static bool tc_if_uart_001(void) {
    return interface_round_trip(ESQH_INTERFACE_UART, 64u);
}

static bool tc_if_uart_002(void) {
    esqh_frame_t input = make_frame(ESQH_INTERFACE_UART, 5u);
    esqh_frame_t oversized = make_frame(ESQH_INTERFACE_UART, 65u);
    esqh_frame_t output = make_frame(ESQH_INTERFACE_CAN, 3u);
    esqh_frame_t unchanged = output;
    uint8_t wire[32];
    uint8_t protected_output[80];
    size_t written = 0u;
    size_t protected_written = 73u;
    size_t index;

    for (index = 0u; index < sizeof(protected_output); ++index) {
        protected_output[index] = 0xa7u;
    }
    if (esqh_frame_encode(
            &oversized,
            protected_output,
            sizeof(protected_output),
            &protected_written
        ) != ESQH_ERR_LENGTH ||
        protected_written != 73u) {
        return false;
    }
    for (index = 0u; index < sizeof(protected_output); ++index) {
        if (protected_output[index] != 0xa7u) {
            return false;
        }
    }

    if (esqh_frame_encode(&input, wire, sizeof(wire), &written) != ESQH_OK) {
        return false;
    }
    wire[written - 1u] ^= 0xffu;
    if (esqh_frame_decode(ESQH_INTERFACE_UART, wire, written, &output) !=
            ESQH_ERR_CHECKSUM ||
        !frames_equal(&output, &unchanged)) {
        return false;
    }
    wire[written - 1u] ^= 0xffu;
    wire[0] = 0x00u;
    if (esqh_frame_decode(ESQH_INTERFACE_UART, wire, written, &output) !=
            ESQH_ERR_RANGE ||
        !frames_equal(&output, &unchanged)) {
        return false;
    }
    wire[0] = 0xa5u;
    wire[1] = (uint8_t)ESQH_INTERFACE_SPI;
    if (esqh_frame_decode(ESQH_INTERFACE_UART, wire, written, &output) !=
            ESQH_ERR_RANGE ||
        !frames_equal(&output, &unchanged)) {
        return false;
    }
    wire[1] = (uint8_t)ESQH_INTERFACE_UART;
    return esqh_frame_decode((esqh_interface_t)99, wire, written, &output) ==
               ESQH_ERR_RANGE &&
           esqh_frame_decode(ESQH_INTERFACE_UART, wire, 4u, &output) ==
               ESQH_ERR_LENGTH &&
           frames_equal(&output, &unchanged);
}

static bool tc_if_spi_001(void) {
    esqh_controller_t controller = make_controller();
    esqh_frame_t oversized = make_frame(ESQH_INTERFACE_SPI, 33u);
    uint8_t wire[48];
    size_t written = 0u;
    uint8_t value = 0u;
    return interface_round_trip(ESQH_INTERFACE_SPI, 16u) &&
           esqh_frame_encode(&oversized, wire, sizeof(wire), &written) ==
               ESQH_ERR_LENGTH &&
           esqh_spi_write(&controller, 15u, 0x7au) == ESQH_OK &&
           esqh_spi_read(&controller, 15u, &value) == ESQH_OK &&
           value == 0x7au &&
           esqh_spi_write(&controller, 16u, 1u) == ESQH_ERR_RANGE;
}

static bool tc_if_can_001(void) {
    esqh_frame_t invalid = make_frame(ESQH_INTERFACE_CAN, 9u);
    esqh_frame_t invalid_id = make_frame(ESQH_INTERFACE_CAN, 1u);
    esqh_controller_t controller = make_controller();
    uint8_t wire[32];
    size_t written = 0u;
    invalid_id.message_id = 0x0800u;
    return interface_round_trip(ESQH_INTERFACE_CAN, 8u) &&
           esqh_frame_encode(&invalid, wire, sizeof(wire), &written) ==
               ESQH_ERR_LENGTH &&
           esqh_frame_encode(&invalid_id, wire, sizeof(wire), &written) ==
               ESQH_ERR_RANGE &&
           esqh_controller_receive(&controller, &invalid_id) ==
               ESQH_ERR_RANGE;
}

static bool tc_if_eth_001(void) {
    esqh_frame_t oversized = make_frame(ESQH_INTERFACE_ETHERNET, ESQH_MAX_PAYLOAD);
    uint8_t wire[ESQH_MAX_PAYLOAD + 16u];
    size_t written = 0u;
    if (!interface_round_trip(ESQH_INTERFACE_ETHERNET, 0u) ||
        !interface_round_trip(ESQH_INTERFACE_ETHERNET, ESQH_MAX_PAYLOAD)) {
        return false;
    }
    oversized.payload_length = ESQH_MAX_PAYLOAD + 1u;
    return esqh_frame_encode(&oversized, wire, sizeof(wire), &written) ==
           ESQH_ERR_LENGTH;
}

static const test_case_t TEST_CASES[] = {
    {"TC-CFG-001", "default configuration baseline", tc_cfg_001},
    {"TC-CFG-002", "invalid configuration rejection", tc_cfg_002},
    {"TC-PLT-001", "portable fixed-width contract", tc_plt_001},
    {"TC-BOOT-001", "controlled initialization", tc_boot_001},
    {"TC-SCH-001", "cooperative scheduler periods", tc_sch_001},
    {"TC-STA-001", "allowed operational transition", tc_sta_001},
    {"TC-STA-002", "degraded and safe transitions", tc_sta_002},
    {"TC-CMD-HB-001", "heartbeat sequence guard", tc_cmd_hb_001},
    {"TC-WDG-001", "watchdog boundary", tc_wdg_001},
    {"TC-FLT-001", "fault latching", tc_flt_001},
    {"TC-RCV-001", "controlled recovery", tc_rcv_001},
    {"TC-RES-001", "static memory budget", tc_res_001},
    {"TC-BND-001", "fixed queue boundaries", tc_bnd_001},
    {"TC-DET-001", "deterministic replay", tc_det_001},
    {"TC-TLM-001", "telemetry layout and checksum", tc_tlm_001},
    {"TC-IF-UART-001", "UART frame round trip", tc_if_uart_001},
    {"TC-IF-UART-002", "UART rejection and atomicity boundaries", tc_if_uart_002},
    {"TC-IF-SPI-001", "SPI frame and register model", tc_if_spi_001},
    {"TC-IF-CAN-001", "classic CAN boundaries", tc_if_can_001},
    {"TC-IF-ETH-001", "Ethernet datagram boundaries", tc_if_eth_001}
};

int main(int argc, char **argv) {
    const bool json_output = argc == 2 && strcmp(argv[1], "--json") == 0;
    const size_t count = sizeof(TEST_CASES) / sizeof(TEST_CASES[0]);
    size_t index;
    unsigned int failures = 0u;

    if (argc != 1 && !json_output) {
        fprintf(stderr, "usage: %s [--json]\n", argv[0]);
        return 64;
    }

    if (json_output) {
        printf(
            "{\"schema_version\":1,"
            "\"project\":\"embedded-software-qualification-harness\","
            "\"version\":\"%s\","
            "\"baseline\":\"%s\","
            "\"cases\":[",
            ESQH_VERSION,
            ESQH_BASELINE
        );
    }
    for (index = 0u; index < count; ++index) {
        const bool passed = TEST_CASES[index].function();
        if (!passed) {
            failures++;
        }
        if (json_output) {
            printf(
                "%s{\"id\":\"%s\",\"name\":\"%s\",\"status\":\"%s\",\"message\":\"%s\"}",
                index == 0u ? "" : ",",
                TEST_CASES[index].id,
                TEST_CASES[index].name,
                passed ? "passed" : "failed",
                passed ? "" : "assertion failed"
            );
        } else {
            printf("%s %s - %s\n", passed ? "PASS" : "FAIL", TEST_CASES[index].id, TEST_CASES[index].name);
        }
    }
    if (json_output) {
        printf("],\"summary\":{\"total\":%zu,\"passed\":%zu,\"failed\":%u}}\n", count, count - failures, failures);
    } else {
        printf("%zu cases, %zu passed, %u failed\n", count, count - failures, failures);
    }
    return failures == 0u ? 0 : 1;
}
