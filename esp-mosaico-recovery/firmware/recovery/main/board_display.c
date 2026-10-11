// SPDX-License-Identifier: Apache-2.0

#include "board_display.h"

#include "bsp/esp_mosaico.h"
#include "esp_attr.h"
#include "esp_check.h"
#include "esp_log.h"
#include "sdkconfig.h"

static const char *TAG = "vibe_board";
static volatile bool s_touch_irq;
static bool s_touch_irq_enabled, s_touching;

esp_err_t board_display_init(vv_esp_config_t *out_config)
{
    ESP_RETURN_ON_FALSE(out_config != NULL, ESP_ERR_INVALID_ARG, TAG,
                        "display output is null");

    const bsp_display_config_t config = BSP_DISPLAY_DEFAULT_CONFIG();
    esp_lcd_panel_handle_t panel = NULL;
    ESP_RETURN_ON_ERROR(bsp_display_new(&config, &panel), TAG,
                        "initialize CO5300");
    ESP_RETURN_ON_FALSE(panel != NULL && bsp_display_get_panel_io() != NULL,
                        ESP_ERR_INVALID_STATE, TAG, "panel/io missing");

    *out_config = (vv_esp_config_t) {
        .panel = panel,
        .io = bsp_display_get_panel_io(),
#if CONFIG_BSP_CO5300_ENABLE_TE
        .te_gpio = BSP_LCD_TE,
#else
        .te_gpio = -1,
#endif
        /* CO5300 takes big-endian RGB565 over QSPI and 4-column windows. */
        .swap_bytes = true,
        .x_align = 4,
        /* Internal RAM: UI callbacks save and erase Wi-Fi credentials in NVS. */
        .task_stack = 8192,
        .task_priority = 5,
        .task_core = -1,
    };
    ESP_LOGI(TAG, "Vibe View target %dx%d RGB565 TE=%s GPIO=%d",
             BSP_LCD_H_RES, BSP_LCD_V_RES,
             out_config->te_gpio >= 0 ? "on" : "off", out_config->te_gpio);
    return ESP_OK;
}

static void IRAM_ATTR touch_interrupt(esp_lcd_touch_handle_t touch)
{
    (void)touch;
    s_touch_irq = true;
}

esp_err_t board_touch_init(esp_lcd_touch_handle_t *out_touch)
{
    ESP_RETURN_ON_FALSE(out_touch != NULL, ESP_ERR_INVALID_ARG, TAG,
                        "touch output is null");
    const esp_err_t err = bsp_touch_new(BSP_LCD_ROTATION_DEFAULT, out_touch);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "touch unavailable (%s); continuing without it",
                 esp_err_to_name(err));
        *out_touch = NULL;
        return ESP_OK;
    }
    /* Read the controller only after it signals a touch, then until release. */
    const esp_err_t irq = esp_lcd_touch_register_interrupt_callback(*out_touch, touch_interrupt);
    s_touch_irq_enabled = irq == ESP_OK;
    if (!s_touch_irq_enabled) {
        ESP_LOGW(TAG, "touch interrupt unavailable (%s); using polling", esp_err_to_name(irq));
    }
    return ESP_OK;
}

bool board_touch_read(void *touch, int *x, int *y)
{
    if (touch == NULL) return false;
    if (s_touch_irq_enabled && !s_touch_irq && !s_touching) return false;
    s_touch_irq = false;
    esp_lcd_touch_point_data_t point = {0};
    uint8_t count = 0;
    s_touching = esp_lcd_touch_read_data(touch) == ESP_OK &&
        esp_lcd_touch_get_data(touch, &point, &count, 1) == ESP_OK && count > 0;
    if (s_touching) {
        *x = point.x;
        *y = point.y;
    }
    return s_touching;
}
