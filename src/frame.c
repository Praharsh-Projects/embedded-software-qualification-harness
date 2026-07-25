#include "internal.h"

#define ESQH_UART_MARKER 0xA5u
#define ESQH_SPI_MARKER 0x5Au
#define ESQH_ETH_MARKER_HIGH 0x45u
#define ESQH_ETH_MARKER_LOW 0x53u

void esqh_internal_copy_bytes(
    uint8_t *destination,
    const uint8_t *source,
    size_t length
) {
    size_t index;

    for (index = 0u; index < length; ++index) {
        destination[index] = source[index];
    }
}

uint16_t esqh_internal_read_u16(const uint8_t *bytes) {
    return (uint16_t)(
        ((uint16_t)bytes[0] << 8u) |
        (uint16_t)bytes[1]
    );
}

void esqh_internal_write_u16(uint8_t *bytes, uint16_t value) {
    bytes[0] = (uint8_t)(value >> 8u);
    bytes[1] = (uint8_t)(value & 0xffu);
}

void esqh_internal_write_u32(uint8_t *bytes, uint32_t value) {
    bytes[0] = (uint8_t)(value >> 24u);
    bytes[1] = (uint8_t)(value >> 16u);
    bytes[2] = (uint8_t)(value >> 8u);
    bytes[3] = (uint8_t)value;
}

uint16_t esqh_internal_payload_limit(esqh_interface_t interface_type) {
    switch (interface_type) {
        case ESQH_INTERFACE_UART:
            return 64u;
        case ESQH_INTERFACE_SPI:
            return 32u;
        case ESQH_INTERFACE_CAN:
            return 8u;
        case ESQH_INTERFACE_ETHERNET:
            return ESQH_MAX_PAYLOAD;
        default:
            return 0u;
    }
}

size_t esqh_wire_size(const esqh_frame_t *frame) {
    if (frame == NULL ||
        frame->payload_length >
            esqh_internal_payload_limit(frame->interface_type)) {
        return 0u;
    }
    if (frame->interface_type == ESQH_INTERFACE_CAN) {
        return (size_t)frame->payload_length + 7u;
    }
    return (size_t)frame->payload_length + 10u;
}

esqh_status_t esqh_frame_encode(
    const esqh_frame_t *frame,
    uint8_t *output,
    size_t output_capacity,
    size_t *written
) {
    size_t required;
    uint16_t crc;
    size_t crc_offset;

    if (frame == NULL || output == NULL || written == NULL) {
        return ESQH_ERR_ARGUMENT;
    }
    if (frame->payload_length >
        esqh_internal_payload_limit(frame->interface_type)) {
        return ESQH_ERR_LENGTH;
    }
    if (frame->interface_type == ESQH_INTERFACE_CAN &&
        frame->message_id > 0x07ffu) {
        return ESQH_ERR_RANGE;
    }
    required = esqh_wire_size(frame);
    if (required == 0u || output_capacity < required) {
        return ESQH_ERR_LENGTH;
    }

    if (frame->interface_type == ESQH_INTERFACE_CAN) {
        esqh_internal_write_u16(output, frame->message_id);
        esqh_internal_write_u16(output + 2u, frame->sequence);
        output[4] = (uint8_t)frame->payload_length;
        esqh_internal_copy_bytes(
            output + 5u,
            frame->payload,
            frame->payload_length
        );
        crc_offset = 5u + frame->payload_length;
    } else {
        if (frame->interface_type == ESQH_INTERFACE_UART) {
            output[0] = ESQH_UART_MARKER;
            output[1] = (uint8_t)frame->interface_type;
        } else if (frame->interface_type == ESQH_INTERFACE_SPI) {
            output[0] = ESQH_SPI_MARKER;
            output[1] = (uint8_t)frame->interface_type;
        } else if (frame->interface_type == ESQH_INTERFACE_ETHERNET) {
            output[0] = ESQH_ETH_MARKER_HIGH;
            output[1] = ESQH_ETH_MARKER_LOW;
        } else {
            return ESQH_ERR_RANGE;
        }
        esqh_internal_write_u16(output + 2u, frame->message_id);
        esqh_internal_write_u16(output + 4u, frame->sequence);
        esqh_internal_write_u16(output + 6u, frame->payload_length);
        esqh_internal_copy_bytes(
            output + 8u,
            frame->payload,
            frame->payload_length
        );
        crc_offset = 8u + frame->payload_length;
    }
    crc = esqh_crc16(output, crc_offset);
    esqh_internal_write_u16(output + crc_offset, crc);
    *written = required;
    return ESQH_OK;
}

esqh_status_t esqh_frame_decode(
    esqh_interface_t interface_type,
    const uint8_t *input,
    size_t input_length,
    esqh_frame_t *frame
) {
    esqh_frame_t decoded = {0};
    uint16_t payload_length;
    uint16_t received_crc;
    uint16_t expected_crc;
    size_t header_length;
    size_t crc_offset;

    if (input == NULL || frame == NULL) {
        return ESQH_ERR_ARGUMENT;
    }
    if (interface_type < ESQH_INTERFACE_UART ||
        interface_type > ESQH_INTERFACE_ETHERNET) {
        return ESQH_ERR_RANGE;
    }
    if (interface_type == ESQH_INTERFACE_CAN) {
        if (input_length < 7u) {
            return ESQH_ERR_LENGTH;
        }
        payload_length = input[4];
        header_length = 5u;
        decoded.message_id = esqh_internal_read_u16(input);
        decoded.sequence = esqh_internal_read_u16(input + 2u);
        if (decoded.message_id > 0x07ffu || payload_length > 8u) {
            return ESQH_ERR_RANGE;
        }
    } else {
        if (input_length < 10u) {
            return ESQH_ERR_LENGTH;
        }
        if ((interface_type == ESQH_INTERFACE_UART &&
             (input[0] != ESQH_UART_MARKER ||
              input[1] != (uint8_t)interface_type)) ||
            (interface_type == ESQH_INTERFACE_SPI &&
             (input[0] != ESQH_SPI_MARKER ||
              input[1] != (uint8_t)interface_type)) ||
            (interface_type == ESQH_INTERFACE_ETHERNET &&
             (input[0] != ESQH_ETH_MARKER_HIGH ||
              input[1] != ESQH_ETH_MARKER_LOW))) {
            return ESQH_ERR_RANGE;
        }
        payload_length = esqh_internal_read_u16(input + 6u);
        header_length = 8u;
        decoded.message_id = esqh_internal_read_u16(input + 2u);
        decoded.sequence = esqh_internal_read_u16(input + 4u);
        if (payload_length > esqh_internal_payload_limit(interface_type)) {
            return ESQH_ERR_LENGTH;
        }
    }
    crc_offset = header_length + payload_length;
    if (input_length != crc_offset + 2u) {
        return ESQH_ERR_LENGTH;
    }
    received_crc = esqh_internal_read_u16(input + crc_offset);
    expected_crc = esqh_crc16(input, crc_offset);
    if (received_crc != expected_crc) {
        return ESQH_ERR_CHECKSUM;
    }
    decoded.interface_type = interface_type;
    decoded.payload_length = payload_length;
    esqh_internal_copy_bytes(
        decoded.payload,
        input + header_length,
        payload_length
    );
    *frame = decoded;
    return ESQH_OK;
}
