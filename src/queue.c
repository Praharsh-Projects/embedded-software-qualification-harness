#include "esqh/esqh.h"

void esqh_queue_init(esqh_frame_queue_t *queue) {
    if (queue == NULL) {
        return;
    }
    queue->head = 0u;
    queue->tail = 0u;
    queue->count = 0u;
}

esqh_status_t esqh_queue_push(
    esqh_frame_queue_t *queue,
    const esqh_frame_t *frame
) {
    if (queue == NULL || frame == NULL) {
        return ESQH_ERR_ARGUMENT;
    }
    if (queue->count >= ESQH_FRAME_QUEUE_CAPACITY) {
        return ESQH_ERR_FULL;
    }
    queue->entries[queue->tail] = *frame;
    queue->tail++;
    if (queue->tail == ESQH_FRAME_QUEUE_CAPACITY) {
        queue->tail = 0u;
    }
    queue->count++;
    return ESQH_OK;
}

esqh_status_t esqh_queue_pop(
    esqh_frame_queue_t *queue,
    esqh_frame_t *frame
) {
    if (queue == NULL || frame == NULL) {
        return ESQH_ERR_ARGUMENT;
    }
    if (queue->count == 0u) {
        return ESQH_ERR_EMPTY;
    }
    *frame = queue->entries[queue->head];
    queue->head++;
    if (queue->head == ESQH_FRAME_QUEUE_CAPACITY) {
        queue->head = 0u;
    }
    queue->count--;
    return ESQH_OK;
}
