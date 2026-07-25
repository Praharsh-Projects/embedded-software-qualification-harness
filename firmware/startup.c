#include <stdint.h>

extern uint32_t _estack;
extern uint32_t _sidata;
extern uint32_t _sdata;
extern uint32_t _edata;
extern uint32_t _sbss;
extern uint32_t _ebss;

void Reset_Handler(void);
void Default_Handler(void);
void firmware_main(void);

__attribute__((section(".isr_vector"), used))
const uintptr_t esqh_vector_table[] = {
    (uintptr_t)&_estack,
    (uintptr_t)Reset_Handler,
    (uintptr_t)Default_Handler,
    (uintptr_t)Default_Handler,
    (uintptr_t)Default_Handler,
    (uintptr_t)Default_Handler,
    (uintptr_t)Default_Handler,
    0u,
    0u,
    0u,
    0u,
    (uintptr_t)Default_Handler,
    (uintptr_t)Default_Handler,
    0u,
    (uintptr_t)Default_Handler,
    (uintptr_t)Default_Handler
};

void Reset_Handler(void) {
    uint32_t *source = &_sidata;
    uint32_t *destination = &_sdata;

    while (destination < &_edata) {
        *destination = *source;
        ++destination;
        ++source;
    }

    destination = &_sbss;
    while (destination < &_ebss) {
        *destination = 0u;
        ++destination;
    }

    firmware_main();
    for (;;) {
    }
}

void Default_Handler(void) {
    for (;;) {
    }
}
