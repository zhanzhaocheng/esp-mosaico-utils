// SPDX-License-Identifier: Apache-2.0
#include <string.h>
#include "vibe_view_esp.h"
#include "vv_scene_def.h"
#include "driver/gpio.h"
#include "esp_attr.h"
#include "esp_check.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

#define MAX_RECTS 4
#define TX_ALIGN_PIXELS 32  /* 64-byte cache lines for PSRAM DMA. */
#define TE_TIMEOUT_MS 40
#define TX_TIMEOUT_MS 250
#define IDLE_PERIOD_MS 20
#define ACTIVE_PERIOD_MS 10

static const char *TAG = "vibe_view";

typedef struct {
    vv_view_t *view;
    vv_esp_config_t config;
    uint16_t width, height;
    uint16_t *fb;  /* Rendered frame, native endian; also the screen mirror source. */
    uint16_t *tx;  /* Panel-order copy of changed areas while DMA reads them. */
    size_t tx_pixels;
    SemaphoreHandle_t fb_lock, state_lock, tx_done, te, first_frame;
    unsigned pending;
    volatile bool presented;
    bool touching;
    int touch_x, touch_y; /* Last pressed point; releases are reported there. */
} port_t;

static port_t s_port;

static void state_lock(void *ctx) { xSemaphoreTake(((port_t *)ctx)->state_lock, portMAX_DELAY); }
static void state_unlock(void *ctx) { xSemaphoreGive(((port_t *)ctx)->state_lock); }

static bool IRAM_ATTR on_color_done(esp_lcd_panel_io_handle_t io, esp_lcd_panel_io_event_data_t *event,
                                    void *ctx)
{
    (void)io;
    (void)event;
    BaseType_t woken = pdFALSE;
    xSemaphoreGiveFromISR(((port_t *)ctx)->tx_done, &woken);
    return woken == pdTRUE;
}

static void IRAM_ATTR on_te(void *ctx)
{
    BaseType_t woken = pdFALSE;
    xSemaphoreGiveFromISR(((port_t *)ctx)->te, &woken);
    portYIELD_FROM_ISR(woken);
}

static void wait_transfers(port_t *p)
{
    while (p->pending) {
        if (xSemaphoreTake(p->tx_done, pdMS_TO_TICKS(TX_TIMEOUT_MS)) != pdTRUE) {
            ESP_LOGW(TAG, "panel transfer did not complete; continuing");
            p->pending = 0;
            break;
        }
        --p->pending;
    }
}

static void align_rect(const port_t *p, vv_rect_t *r)
{
    const int mask = p->config.x_align - 1;
    r->x1 = (int16_t)(r->x1 & ~mask);
    r->x2 = (int16_t)(r->x2 | mask);
    if (r->x2 >= p->width) r->x2 = (int16_t)(p->width - 1);
}

static size_t rect_pixels(const vv_rect_t *r)
{
    return (size_t)(r->x2 - r->x1 + 1) * (size_t)(r->y2 - r->y1 + 1);
}

static void flush(port_t *p, vv_rect_t *rects, size_t count)
{
    size_t total = 0;
    for (size_t i = 0; i < count; ++i) {
        align_rect(p, &rects[i]);
        total += (rect_pixels(&rects[i]) + TX_ALIGN_PIXELS - 1) & ~(size_t)(TX_ALIGN_PIXELS - 1);
    }
    if (total > p->tx_pixels) {
        /* Overlapping aligned areas: send their union instead. */
        for (size_t i = 1; i < count; ++i) {
            if (rects[i].x1 < rects[0].x1) rects[0].x1 = rects[i].x1;
            if (rects[i].y1 < rects[0].y1) rects[0].y1 = rects[i].y1;
            if (rects[i].x2 > rects[0].x2) rects[0].x2 = rects[i].x2;
            if (rects[i].y2 > rects[0].y2) rects[0].y2 = rects[i].y2;
        }
        count = 1;
    }
    wait_transfers(p);
    size_t offsets[MAX_RECTS], offset = 0;
    xSemaphoreTake(p->fb_lock, portMAX_DELAY);
    for (size_t i = 0; i < count; ++i) {
        const vv_rect_t *r = &rects[i];
        const size_t width = (size_t)(r->x2 - r->x1 + 1);
        offsets[i] = offset;
        uint16_t *dst = p->tx + offset;
        for (int y = r->y1; y <= r->y2; ++y) {
            const uint16_t *src = p->fb + (size_t)y * p->width + r->x1;
            if (p->config.swap_bytes) {
                for (size_t x = 0; x < width; ++x) dst[x] = __builtin_bswap16(src[x]);
            } else {
                memcpy(dst, src, width * sizeof(uint16_t));
            }
            dst += width;
        }
        offset += (rect_pixels(r) + TX_ALIGN_PIXELS - 1) & ~(size_t)(TX_ALIGN_PIXELS - 1);
    }
    xSemaphoreGive(p->fb_lock);
    if (p->te) {
        /* Start right after the panel leaves the visible scan. */
        (void)xSemaphoreTake(p->te, 0);
        (void)xSemaphoreTake(p->te, pdMS_TO_TICKS(TE_TIMEOUT_MS));
    }
    for (size_t i = 0; i < count; ++i) {
        const vv_rect_t *r = &rects[i];
        const esp_err_t err = esp_lcd_panel_draw_bitmap(p->config.panel, r->x1, r->y1, r->x2 + 1, r->y2 + 1,
                                                        p->tx + offsets[i]);
        if (err == ESP_OK) ++p->pending;
        else ESP_LOGW(TAG, "draw (%d,%d)-(%d,%d) failed: %s", r->x1, r->y1, r->x2, r->y2, esp_err_to_name(err));
    }
    if (!p->presented) {
        wait_transfers(p);
        p->presented = true;
        xSemaphoreGive(p->first_frame);
    }
}

static void read_touch(port_t *p)
{
    if (!p->config.touch_read) return;
    int x = p->touch_x, y = p->touch_y;
    const bool pressed = p->config.touch_read(p->config.touch_ctx, &x, &y);
    if (pressed) {
        p->touch_x = x;
        p->touch_y = y;
    }
    if (pressed || p->touching) vv_touch_sample(p->view, pressed, p->touch_x, p->touch_y);
    p->touching = pressed;
}

static void ui_task(void *arg)
{
    port_t *p = arg;
    vv_rect_t rects[MAX_RECTS];
    for (;;) {
        read_touch(p);
        vv_process(p->view, (uint32_t)(esp_timer_get_time() / 1000));
        xSemaphoreTake(p->fb_lock, portMAX_DELAY);
        const size_t count = vv_render(p->view, rects, MAX_RECTS);
        xSemaphoreGive(p->fb_lock);
        if (count) flush(p, rects, count);
        vTaskDelay(pdMS_TO_TICKS(vv_is_animating(p->view) || p->touching ? ACTIVE_PERIOD_MS : IDLE_PERIOD_MS));
    }
}

static void release(port_t *p)
{
    if (p->view) vv_destroy(p->view);
    heap_caps_free(p->fb);
    heap_caps_free(p->tx);
    SemaphoreHandle_t handles[] = {p->fb_lock, p->state_lock, p->tx_done, p->te, p->first_frame};
    for (size_t i = 0; i < sizeof(handles) / sizeof(handles[0]); ++i) {
        if (handles[i]) vSemaphoreDelete(handles[i]);
    }
    memset(p, 0, sizeof(*p));
}

static esp_err_t start_te(port_t *p)
{
    const gpio_config_t te = {
        .pin_bit_mask = 1ULL << p->config.te_gpio,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_POSEDGE,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&te), TAG, "TE GPIO");
    const esp_err_t err = gpio_install_isr_service(0);
    ESP_RETURN_ON_FALSE(err == ESP_OK || err == ESP_ERR_INVALID_STATE, err, TAG, "GPIO ISR service");
    return gpio_isr_handler_add(p->config.te_gpio, on_te, p);
}

esp_err_t vv_esp_start(const vv_esp_config_t *config, const vv_scene_t *scene,
                       const void *assets, size_t assets_size, vv_view_t **out_view)
{
    ESP_RETURN_ON_FALSE(config && config->panel && config->io && scene && assets && out_view &&
                        (config->x_align & (config->x_align - 1)) == 0,
                        ESP_ERR_INVALID_ARG, TAG, "invalid configuration");
    ESP_RETURN_ON_FALSE(!s_port.view, ESP_ERR_INVALID_STATE, TAG, "already started");
    port_t *p = &s_port;
    p->config = *config;
    if (!p->config.x_align) p->config.x_align = 1;
    p->width = scene->width;
    p->height = scene->height;
    const size_t pixels = (size_t)p->width * p->height;
    p->tx_pixels = pixels + MAX_RECTS * TX_ALIGN_PIXELS;
    p->fb = heap_caps_aligned_calloc(64, pixels, sizeof(uint16_t), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    p->tx = heap_caps_aligned_alloc(64, p->tx_pixels * sizeof(uint16_t), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    p->fb_lock = xSemaphoreCreateMutex();
    p->state_lock = xSemaphoreCreateMutex();
    p->tx_done = xSemaphoreCreateCounting(MAX_RECTS, 0);
    p->first_frame = xSemaphoreCreateBinary();
    if (config->te_gpio >= 0) p->te = xSemaphoreCreateBinary();
    if (!p->fb || !p->tx || !p->fb_lock || !p->state_lock || !p->tx_done || !p->first_frame ||
        (config->te_gpio >= 0 && !p->te)) {
        release(p);
        return ESP_ERR_NO_MEM;
    }
    const vv_config_t view_config = {
        .scene = scene,
        .assets = assets,
        .assets_size = assets_size,
        .framebuffer = p->fb,
        .lock = state_lock,
        .unlock = state_unlock,
        .lock_ctx = p,
    };
    const vv_err_t view_err = vv_create(&view_config, &p->view);
    if (view_err != VV_OK) {
        release(p);
        ESP_LOGE(TAG, "scene assets rejected: %d", (int)view_err);
        return view_err == VV_ERR_NO_MEM ? ESP_ERR_NO_MEM : ESP_ERR_INVALID_CRC;
    }
    const esp_lcd_panel_io_callbacks_t callbacks = {.on_color_trans_done = on_color_done};
    esp_err_t err = esp_lcd_panel_io_register_event_callbacks(config->io, &callbacks, p);
    if (err != ESP_OK) {
        release(p);
        ESP_LOGE(TAG, "panel IO callbacks: %s", esp_err_to_name(err));
        return err;
    }
    if (p->te && (err = start_te(p)) != ESP_OK) {
        /* Tearing sync is an improvement, not a requirement for maintenance. */
        ESP_LOGW(TAG, "TE sync unavailable (%s); sending without it", esp_err_to_name(err));
        vSemaphoreDelete(p->te);
        p->te = NULL;
    }
    const BaseType_t core = config->task_core < 0 ? tskNO_AFFINITY : config->task_core;
    if (xTaskCreatePinnedToCore(ui_task, "vibe_view", config->task_stack ? config->task_stack : 8192, p,
                                config->task_priority ? config->task_priority : 5, NULL, core) != pdPASS) {
        if (p->te) (void)gpio_isr_handler_remove(config->te_gpio);
        release(p);
        return ESP_ERR_NO_MEM;
    }
    ESP_LOGI(TAG, "%ux%u RGB565 view started, TE %s", p->width, p->height, p->te ? "on" : "off");
    *out_view = p->view;
    return ESP_OK;
}

const uint16_t *vv_esp_framebuffer(vv_view_t *view)
{
    return view && view == s_port.view ? s_port.fb : NULL;
}

bool vv_esp_lock(vv_view_t *view, uint32_t timeout_ms)
{
    return view && view == s_port.view &&
        xSemaphoreTake(s_port.fb_lock, pdMS_TO_TICKS(timeout_ms)) == pdTRUE;
}

void vv_esp_unlock(vv_view_t *view)
{
    if (view && view == s_port.view) xSemaphoreGive(s_port.fb_lock);
}

bool vv_esp_wait_first_frame(vv_view_t *view, uint32_t timeout_ms)
{
    if (!view || view != s_port.view) return false;
    if (s_port.presented) return true;
    if (xSemaphoreTake(s_port.first_frame, pdMS_TO_TICKS(timeout_ms)) != pdTRUE) return s_port.presented;
    xSemaphoreGive(s_port.first_frame); /* Later waiters return immediately as well. */
    return true;
}
