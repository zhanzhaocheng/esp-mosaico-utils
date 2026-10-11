#pragma once

#include <stdbool.h>
#include "esp_err.h"
#include "esp_lcd_touch.h"
#include "vibe_view_esp.h"

/** Initialize the CO5300 panel and fill its Vibe View presentation fields. */
esp_err_t board_display_init(vv_esp_config_t *out_config);
/** A missing touch controller leaves *out_touch NULL and returns ESP_OK. */
esp_err_t board_touch_init(esp_lcd_touch_handle_t *out_touch);
/** vv_esp_touch_read_t for the handle returned by board_touch_init(). */
bool board_touch_read(void *touch, int *x, int *y);
