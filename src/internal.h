#ifndef ESQH_INTERNAL_H
#define ESQH_INTERNAL_H

#include <stddef.h>
#include <stdint.h>

#include "esqh/esqh.h"

void esqh_internal_copy_bytes(
    uint8_t *destination,
    const uint8_t *source,
    size_t length
);
uint16_t esqh_internal_read_u16(const uint8_t *bytes);
void esqh_internal_write_u16(uint8_t *bytes, uint16_t value);
void esqh_internal_write_u32(uint8_t *bytes, uint32_t value);
uint16_t esqh_internal_payload_limit(esqh_interface_t interface_type);

#endif
