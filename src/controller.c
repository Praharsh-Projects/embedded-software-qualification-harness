#include "internal.h"

esqh_status_t esqh_spi_write(
    esqh_controller_t *controller,
    uint8_t address,
    uint8_t value
) {
    if (controller == NULL) {
        return ESQH_ERR_ARGUMENT;
    }
    if (address >= ESQH_SPI_REGISTER_COUNT) {
        esqh_controller_latch_fault(
            controller,
            ESQH_FAULT_INTERFACE,
            false
        );
        return ESQH_ERR_RANGE;
    }
    controller->spi_registers[address] = value;
    controller->counters.spi_accepted++;
    return ESQH_OK;
}

esqh_status_t esqh_spi_read(
    const esqh_controller_t *controller,
    uint8_t address,
    uint8_t *value
) {
    if (controller == NULL || value == NULL) {
        return ESQH_ERR_ARGUMENT;
    }
    if (address >= ESQH_SPI_REGISTER_COUNT) {
        return ESQH_ERR_RANGE;
    }
    *value = controller->spi_registers[address];
    return ESQH_OK;
}

void esqh_controller_init(
    esqh_controller_t *controller,
    const esqh_config_t *config
) {
    size_t index;

    if (controller == NULL || !esqh_config_is_valid(config)) {
        return;
    }
    controller->config = *config;
    controller->state = ESQH_STATE_INIT;
    esqh_queue_init(&controller->queue);
    controller->counters.uart_accepted = 0u;
    controller->counters.spi_accepted = 0u;
    controller->counters.can_accepted = 0u;
    controller->counters.ethernet_accepted = 0u;
    controller->counters.rejected = 0u;
    controller->elapsed_ms = 0u;
    controller->last_heartbeat_ms = 0u;
    controller->fault_bitmap = 0u;
    controller->task_1ms_count = 0u;
    controller->task_10ms_count = 0u;
    controller->task_100ms_count = 0u;
    controller->last_command_sequence = 0u;
    controller->telemetry_sequence = 0u;
    controller->setpoint = 0;
    controller->scheduler_10ms = 10u;
    controller->scheduler_100ms = 100u;
    controller->self_test_passed = false;
    controller->heartbeat_seen = false;
    for (index = 0u; index < ESQH_SPI_REGISTER_COUNT; ++index) {
        controller->spi_registers[index] = 0u;
    }
}

void esqh_controller_mark_self_test_passed(esqh_controller_t *controller) {
    if (controller != NULL && controller->state != ESQH_STATE_SAFE) {
        controller->self_test_passed = true;
        if (controller->heartbeat_seen && controller->fault_bitmap == 0u) {
            controller->state = ESQH_STATE_OPERATIONAL;
        }
    }
}

static esqh_status_t esqh_controller_accept_sequence(
    esqh_controller_t *controller,
    uint16_t sequence
) {
    if (sequence == 0u || sequence <= controller->last_command_sequence) {
        esqh_controller_latch_fault(
            controller,
            ESQH_FAULT_SEQUENCE,
            false
        );
        return ESQH_ERR_SEQUENCE;
    }
    controller->last_command_sequence = sequence;
    return ESQH_OK;
}

esqh_status_t esqh_controller_heartbeat(
    esqh_controller_t *controller,
    uint16_t sequence
) {
    esqh_status_t status;

    if (controller == NULL) {
        return ESQH_ERR_ARGUMENT;
    }
    status = esqh_controller_accept_sequence(controller, sequence);
    if (status != ESQH_OK) {
        return status;
    }
    controller->heartbeat_seen = true;
    controller->last_heartbeat_ms = controller->elapsed_ms;
    if (controller->state != ESQH_STATE_SAFE &&
        controller->self_test_passed &&
        controller->fault_bitmap == 0u) {
        controller->state = ESQH_STATE_OPERATIONAL;
    }
    return ESQH_OK;
}

esqh_status_t esqh_controller_setpoint(
    esqh_controller_t *controller,
    uint16_t sequence,
    int16_t setpoint
) {
    esqh_status_t status;

    if (controller == NULL) {
        return ESQH_ERR_ARGUMENT;
    }
    if (controller->state != ESQH_STATE_OPERATIONAL) {
        return ESQH_ERR_STATE;
    }
    status = esqh_controller_accept_sequence(controller, sequence);
    if (status != ESQH_OK) {
        return status;
    }
    if (setpoint < controller->config.minimum_setpoint ||
        setpoint > controller->config.maximum_setpoint) {
        esqh_controller_latch_fault(
            controller,
            ESQH_FAULT_COMMAND_RANGE,
            false
        );
        return ESQH_ERR_RANGE;
    }
    controller->setpoint = setpoint;
    return ESQH_OK;
}

void esqh_controller_latch_fault(
    esqh_controller_t *controller,
    uint32_t fault,
    bool critical
) {
    if (controller == NULL) {
        return;
    }
    controller->fault_bitmap |= fault;
    if (critical || (fault & ~ESQH_RECOVERABLE_FAULTS) != 0u) {
        controller->state = ESQH_STATE_SAFE;
    } else if (controller->state != ESQH_STATE_SAFE) {
        controller->state = ESQH_STATE_DEGRADED;
    }
}

esqh_status_t esqh_controller_recover(esqh_controller_t *controller) {
    if (controller == NULL) {
        return ESQH_ERR_ARGUMENT;
    }
    if (controller->state != ESQH_STATE_DEGRADED ||
        controller->fault_bitmap == 0u) {
        return ESQH_ERR_STATE;
    }
    if ((controller->fault_bitmap & ~ESQH_RECOVERABLE_FAULTS) != 0u) {
        return ESQH_ERR_STATE;
    }
    controller->fault_bitmap &= ~ESQH_RECOVERABLE_FAULTS;
    controller->state = ESQH_STATE_INIT;
    controller->self_test_passed = false;
    controller->heartbeat_seen = false;
    return ESQH_OK;
}

void esqh_controller_tick(esqh_controller_t *controller) {
    if (controller == NULL) {
        return;
    }
    controller->elapsed_ms++;
    controller->task_1ms_count++;
    controller->scheduler_10ms--;
    controller->scheduler_100ms--;
    if (controller->scheduler_10ms == 0u) {
        controller->task_10ms_count++;
        controller->scheduler_10ms = 10u;
    }
    if (controller->scheduler_100ms == 0u) {
        controller->task_100ms_count++;
        controller->scheduler_100ms = 100u;
    }
    if (controller->self_test_passed &&
        controller->elapsed_ms - controller->last_heartbeat_ms >
            controller->config.watchdog_timeout_ms) {
        esqh_controller_latch_fault(
            controller,
            ESQH_FAULT_WATCHDOG,
            true
        );
    }
}

esqh_status_t esqh_controller_receive(
    esqh_controller_t *controller,
    const esqh_frame_t *frame
) {
    esqh_status_t status;
    uint32_t enabled_bit;

    if (controller == NULL || frame == NULL) {
        return ESQH_ERR_ARGUMENT;
    }
    if (frame->interface_type < ESQH_INTERFACE_UART ||
        frame->interface_type > ESQH_INTERFACE_ETHERNET ||
        frame->payload_length >
            esqh_internal_payload_limit(frame->interface_type)) {
        controller->counters.rejected++;
        esqh_controller_latch_fault(
            controller,
            ESQH_FAULT_INTERFACE,
            false
        );
        return ESQH_ERR_RANGE;
    }
    if (frame->interface_type == ESQH_INTERFACE_CAN &&
        frame->message_id > 0x07ffu) {
        controller->counters.rejected++;
        esqh_controller_latch_fault(
            controller,
            ESQH_FAULT_INTERFACE,
            false
        );
        return ESQH_ERR_RANGE;
    }
    enabled_bit = 1u << ((uint32_t)frame->interface_type - 1u);
    if ((controller->config.enabled_interface_mask & enabled_bit) == 0u) {
        controller->counters.rejected++;
        esqh_controller_latch_fault(
            controller,
            ESQH_FAULT_INTERFACE,
            false
        );
        return ESQH_ERR_STATE;
    }
    status = esqh_queue_push(&controller->queue, frame);
    if (status != ESQH_OK) {
        controller->counters.rejected++;
        esqh_controller_latch_fault(
            controller,
            ESQH_FAULT_QUEUE_OVERFLOW,
            false
        );
        return status;
    }
    switch (frame->interface_type) {
        case ESQH_INTERFACE_UART:
            controller->counters.uart_accepted++;
            break;
        case ESQH_INTERFACE_SPI:
            controller->counters.spi_accepted++;
            break;
        case ESQH_INTERFACE_CAN:
            controller->counters.can_accepted++;
            break;
        case ESQH_INTERFACE_ETHERNET:
            controller->counters.ethernet_accepted++;
            break;
        default:
            break;
    }
    return ESQH_OK;
}

size_t esqh_controller_telemetry(
    esqh_controller_t *controller,
    uint8_t output[ESQH_TELEMETRY_SIZE]
) {
    if (controller == NULL || output == NULL) {
        return 0u;
    }
    controller->telemetry_sequence++;
    esqh_internal_write_u16(output, controller->telemetry_sequence);
    output[2] = (uint8_t)controller->state;
    output[3] = 0u;
    esqh_internal_write_u32(output + 4u, controller->fault_bitmap);
    esqh_internal_write_u16(output + 8u, (uint16_t)controller->setpoint);
    esqh_internal_write_u16(output + 10u, controller->spi_registers[0]);
    esqh_internal_write_u16(
        output + 12u,
        (uint16_t)controller->counters.uart_accepted
    );
    esqh_internal_write_u16(
        output + 14u,
        (uint16_t)controller->counters.spi_accepted
    );
    esqh_internal_write_u16(
        output + 16u,
        (uint16_t)controller->counters.can_accepted
    );
    esqh_internal_write_u16(
        output + 18u,
        (uint16_t)controller->counters.ethernet_accepted
    );
    esqh_internal_write_u16(
        output + 20u,
        (uint16_t)controller->counters.rejected
    );
    esqh_internal_write_u16(
        output + 22u,
        esqh_crc16(output, 22u)
    );
    return ESQH_TELEMETRY_SIZE;
}
