#include "esqh/esqh.h"

uint16_t esqh_crc16(const uint8_t *data, size_t length) {
    uint16_t crc = 0xffffu;
    size_t index;
    uint8_t bit;

    if (data == NULL && length != 0u) {
        return 0u;
    }
    for (index = 0u; index < length; ++index) {
        crc ^= (uint16_t)((uint16_t)data[index] << 8u);
        for (bit = 0u; bit < 8u; ++bit) {
            if ((crc & 0x8000u) != 0u) {
                crc = (uint16_t)((crc << 1u) ^ 0x1021u);
            } else {
                crc = (uint16_t)(crc << 1u);
            }
        }
    }
    return crc;
}
