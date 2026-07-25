#include "esqh/esqh.h"

static void esqh_copy_text(char *destination, size_t capacity, const char *source) {
    size_t index = 0u;

    if (destination == NULL || capacity == 0u) {
        return;
    }
    while (source[index] != '\0' && index + 1u < capacity) {
        destination[index] = source[index];
        ++index;
    }
    while (index < capacity) {
        destination[index] = '\0';
        ++index;
    }
}

static bool esqh_text_equal(const char *left, const char *right, size_t capacity) {
    size_t index;

    for (index = 0u; index < capacity; ++index) {
        if (left[index] != right[index]) {
            return false;
        }
        if (left[index] == '\0') {
            return true;
        }
    }
    return true;
}

void esqh_config_default(esqh_config_t *config) {
    if (config == NULL) {
        return;
    }
    config->watchdog_timeout_ms = ESQH_WATCHDOG_DEFAULT_MS;
    config->minimum_setpoint = -1000;
    config->maximum_setpoint = 1000;
    config->enabled_interface_mask = 0x0fu;
    esqh_copy_text(config->version, sizeof(config->version), ESQH_VERSION);
    esqh_copy_text(config->baseline, sizeof(config->baseline), ESQH_BASELINE);
}

bool esqh_config_is_valid(const esqh_config_t *config) {
    if (config == NULL) {
        return false;
    }
    if (config->watchdog_timeout_ms == 0u ||
        config->watchdog_timeout_ms > 1000u) {
        return false;
    }
    if (config->minimum_setpoint >= config->maximum_setpoint) {
        return false;
    }
    if ((config->enabled_interface_mask & 0x0fu) == 0u ||
        (config->enabled_interface_mask & ~0x0fu) != 0u) {
        return false;
    }
    return esqh_text_equal(
               config->version,
               ESQH_VERSION,
               sizeof(config->version)
           ) &&
           esqh_text_equal(
               config->baseline,
               ESQH_BASELINE,
               sizeof(config->baseline)
           );
}
