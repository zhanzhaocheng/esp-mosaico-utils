// SPDX-License-Identifier: Apache-2.0
#pragma once

/* ESP-IDF port of Vibe View: one UI task renders into a PSRAM framebuffer and
 * sends changed areas to an esp_lcd panel, optionally after the panel's TE
 * pulse. Touch is read through a caller-provided function so the component
 * does not depend on a particular touch driver. */

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "vibe_view.h"

#ifdef __cplusplus
extern "C" {
#endif

/** Return true while touched and write the panel coordinate. */
typedef bool (*vv_esp_touch_read_t)(void *ctx, int *x, int *y);

typedef struct {
    esp_lcd_panel_handle_t panel;
    esp_lcd_panel_io_handle_t io;
    int te_gpio;            /* Tearing-effect output, -1 when unused. */
    bool swap_bytes;        /* Send RGB565 most-significant byte first. */
    uint8_t x_align;        /* Column alignment required by the panel, power of two. */
    vv_esp_touch_read_t touch_read;
    void *touch_ctx;
    uint32_t task_stack;    /* Internal RAM: callbacks may write NVS. */
    unsigned task_priority;
    int task_core;
} vv_esp_config_t;

/** Create the view and start its UI task. Scene and assets must stay valid. */
esp_err_t vv_esp_start(const vv_esp_config_t *config, const vv_scene_t *scene,
                       const void *assets, size_t assets_size, vv_view_t **out_view);

/** Native-endian RGB565 frame. Read it only between lock and unlock. */
const uint16_t *vv_esp_framebuffer(vv_view_t *view);
bool vv_esp_lock(vv_view_t *view, uint32_t timeout_ms);
void vv_esp_unlock(vv_view_t *view);

/** Wait until the first complete frame has been painted and sent. */
bool vv_esp_wait_first_frame(vv_view_t *view, uint32_t timeout_ms);

#ifdef __cplusplus
}
#endif
