#include "esqh/esqh.h"

static esqh_controller_t controller;
static esqh_config_t link_contract_config;
static esqh_frame_t link_contract_frame;
static uint8_t link_contract_wire[ESQH_MAX_PAYLOAD + 16u];
static uint8_t link_contract_telemetry[ESQH_TELEMETRY_SIZE];
static uint8_t link_contract_spi_value;
static size_t link_contract_written;
static volatile uint32_t link_contract_gate;
static volatile uint32_t link_contract_sink;

void *memcpy(void *destination, const void *source, size_t length) {
    uint8_t *destination_bytes = (uint8_t *)destination;
    const uint8_t *source_bytes = (const uint8_t *)source;
    size_t index;
    for (index = 0u; index < length; ++index) {
        destination_bytes[index] = source_bytes[index];
    }
    return destination;
}

void *memset(void *destination, int value, size_t length) {
    uint8_t *destination_bytes = (uint8_t *)destination;
    size_t index;
    for (index = 0u; index < length; ++index) {
        destination_bytes[index] = (uint8_t)value;
    }
    return destination;
}

static void retain_public_api_link_contract(void) {
    esqh_config_default(&link_contract_config);
    link_contract_sink ^= (uint32_t)esqh_config_is_valid(&link_contract_config);
    esqh_controller_init(&controller, &link_contract_config);

    esqh_queue_init(&controller.queue);
    link_contract_frame.interface_type = ESQH_INTERFACE_UART;
    link_contract_frame.message_id = 1u;
    link_contract_frame.sequence = 1u;
    link_contract_frame.payload_length = 0u;

    link_contract_sink ^= (uint32_t)esqh_crc16(link_contract_frame.payload, 0u);
    link_contract_sink ^= (uint32_t)esqh_queue_push(&controller.queue, &link_contract_frame);
    link_contract_sink ^= (uint32_t)esqh_queue_pop(&controller.queue, &link_contract_frame);
    link_contract_sink ^= (uint32_t)esqh_wire_size(&link_contract_frame);
    link_contract_sink ^= (uint32_t)esqh_frame_encode(
        &link_contract_frame,
        link_contract_wire,
        sizeof(link_contract_wire),
        &link_contract_written
    );
    link_contract_sink ^= (uint32_t)esqh_frame_decode(
        ESQH_INTERFACE_UART,
        link_contract_wire,
        link_contract_written,
        &link_contract_frame
    );

    link_contract_sink ^= (uint32_t)esqh_spi_write(&controller, 0u, 0u);
    link_contract_sink ^= (uint32_t)esqh_spi_read(
        &controller,
        0u,
        &link_contract_spi_value
    );
    esqh_controller_mark_self_test_passed(&controller);
    link_contract_sink ^= (uint32_t)esqh_controller_heartbeat(&controller, 1u);
    link_contract_sink ^= (uint32_t)esqh_controller_setpoint(&controller, 2u, 0);
    esqh_controller_latch_fault(&controller, ESQH_FAULT_INTERFACE, false);
    link_contract_sink ^= (uint32_t)esqh_controller_recover(&controller);
    esqh_controller_tick(&controller);
    link_contract_sink ^= (uint32_t)esqh_controller_receive(
        &controller,
        &link_contract_frame
    );
    link_contract_sink ^= (uint32_t)esqh_controller_telemetry(
        &controller,
        link_contract_telemetry
    );
}

void firmware_main(void) {
    esqh_config_t config;
    if (link_contract_gate != 0u) {
        retain_public_api_link_contract();
    }
    esqh_config_default(&config);
    esqh_controller_init(&controller, &config);
    esqh_controller_mark_self_test_passed(&controller);

    for (;;) {
        esqh_controller_tick(&controller);
    }
}
