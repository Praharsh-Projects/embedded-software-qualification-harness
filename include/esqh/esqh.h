#ifndef ESQH_ESQH_H
#define ESQH_ESQH_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define ESQH_VERSION "0.1.0"
#define ESQH_BASELINE "ESQH-BL-0.1.0"
#define ESQH_MAX_PAYLOAD 256u
#define ESQH_FRAME_QUEUE_CAPACITY 8u
#define ESQH_SPI_REGISTER_COUNT 16u
#define ESQH_WATCHDOG_DEFAULT_MS 100u
#define ESQH_TELEMETRY_SIZE 24u

#define ESQH_FAULT_INTERFACE (1u << 0)
#define ESQH_FAULT_QUEUE_OVERFLOW (1u << 1)
#define ESQH_FAULT_SEQUENCE (1u << 2)
#define ESQH_FAULT_COMMAND_RANGE (1u << 3)
#define ESQH_FAULT_WATCHDOG (1u << 16)
#define ESQH_FAULT_CRITICAL (1u << 17)
#define ESQH_RECOVERABLE_FAULTS \
    (ESQH_FAULT_INTERFACE | ESQH_FAULT_QUEUE_OVERFLOW | ESQH_FAULT_SEQUENCE | ESQH_FAULT_COMMAND_RANGE)

typedef enum {
    ESQH_OK = 0,
    ESQH_ERR_ARGUMENT = 1,
    ESQH_ERR_LENGTH = 2,
    ESQH_ERR_CHECKSUM = 3,
    ESQH_ERR_RANGE = 4,
    ESQH_ERR_FULL = 5,
    ESQH_ERR_EMPTY = 6,
    ESQH_ERR_SEQUENCE = 7,
    ESQH_ERR_STATE = 8
} esqh_status_t;

typedef enum {
    ESQH_STATE_INIT = 0,
    ESQH_STATE_OPERATIONAL = 1,
    ESQH_STATE_DEGRADED = 2,
    ESQH_STATE_SAFE = 3
} esqh_state_t;

typedef enum {
    ESQH_INTERFACE_UART = 1,
    ESQH_INTERFACE_SPI = 2,
    ESQH_INTERFACE_CAN = 3,
    ESQH_INTERFACE_ETHERNET = 4
} esqh_interface_t;

typedef struct {
    uint16_t watchdog_timeout_ms;
    int16_t minimum_setpoint;
    int16_t maximum_setpoint;
    uint32_t enabled_interface_mask;
    char version[8];
    char baseline[20];
} esqh_config_t;

typedef struct {
    esqh_interface_t interface_type;
    uint16_t message_id;
    uint16_t sequence;
    uint16_t payload_length;
    uint8_t payload[ESQH_MAX_PAYLOAD];
} esqh_frame_t;

typedef struct {
    esqh_frame_t entries[ESQH_FRAME_QUEUE_CAPACITY];
    uint8_t head;
    uint8_t tail;
    uint8_t count;
} esqh_frame_queue_t;

typedef struct {
    uint32_t uart_accepted;
    uint32_t spi_accepted;
    uint32_t can_accepted;
    uint32_t ethernet_accepted;
    uint32_t rejected;
} esqh_interface_counters_t;

typedef struct {
    esqh_config_t config;
    esqh_state_t state;
    esqh_frame_queue_t queue;
    esqh_interface_counters_t counters;
    uint32_t elapsed_ms;
    uint32_t last_heartbeat_ms;
    uint32_t fault_bitmap;
    uint32_t task_1ms_count;
    uint32_t task_10ms_count;
    uint32_t task_100ms_count;
    uint16_t last_command_sequence;
    uint16_t telemetry_sequence;
    int16_t setpoint;
    uint8_t spi_registers[ESQH_SPI_REGISTER_COUNT];
    uint8_t scheduler_10ms;
    uint8_t scheduler_100ms;
    bool self_test_passed;
    bool heartbeat_seen;
} esqh_controller_t;

uint16_t esqh_crc16(const uint8_t *data, size_t length);

void esqh_config_default(esqh_config_t *config);
bool esqh_config_is_valid(const esqh_config_t *config);

void esqh_queue_init(esqh_frame_queue_t *queue);
esqh_status_t esqh_queue_push(esqh_frame_queue_t *queue, const esqh_frame_t *frame);
esqh_status_t esqh_queue_pop(esqh_frame_queue_t *queue, esqh_frame_t *frame);

size_t esqh_wire_size(const esqh_frame_t *frame);
esqh_status_t esqh_frame_encode(
    const esqh_frame_t *frame,
    uint8_t *output,
    size_t output_capacity,
    size_t *written
);
esqh_status_t esqh_frame_decode(
    esqh_interface_t interface_type,
    const uint8_t *input,
    size_t input_length,
    esqh_frame_t *frame
);

esqh_status_t esqh_spi_write(esqh_controller_t *controller, uint8_t address, uint8_t value);
esqh_status_t esqh_spi_read(const esqh_controller_t *controller, uint8_t address, uint8_t *value);

void esqh_controller_init(esqh_controller_t *controller, const esqh_config_t *config);
void esqh_controller_mark_self_test_passed(esqh_controller_t *controller);
esqh_status_t esqh_controller_heartbeat(esqh_controller_t *controller, uint16_t sequence);
esqh_status_t esqh_controller_setpoint(
    esqh_controller_t *controller,
    uint16_t sequence,
    int16_t setpoint
);
void esqh_controller_latch_fault(esqh_controller_t *controller, uint32_t fault, bool critical);
esqh_status_t esqh_controller_recover(esqh_controller_t *controller);
void esqh_controller_tick(esqh_controller_t *controller);
esqh_status_t esqh_controller_receive(esqh_controller_t *controller, const esqh_frame_t *frame);
size_t esqh_controller_telemetry(esqh_controller_t *controller, uint8_t output[ESQH_TELEMETRY_SIZE]);

#endif
