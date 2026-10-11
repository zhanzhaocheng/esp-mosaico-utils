// SPDX-License-Identifier: Apache-2.0

#include "iris_screen_mirror.h"

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "bsp/esp_mosaico.h"
#include "esp_heap_caps.h"
#include "esp_iris.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "vibe_view_esp.h"

#define SCREEN_BYTES_PER_PIXEL 2U
#define SCREEN_STRIDE ((size_t)BSP_LCD_H_RES * SCREEN_BYTES_PER_PIXEL)
#define SCREEN_FRAME_BYTES (SCREEN_STRIDE * BSP_LCD_V_RES)
#define FULL_REPAINT_TIMEOUT_MS 2000U
#define FRAME_LOCK_TIMEOUT_MS 1000U

typedef struct {
    vv_view_t *ui;
    uint8_t *capture;
    SemaphoreHandle_t lock;
    StaticSemaphore_t lock_storage;
    bool capture_ready;
} screen_mirror_t;

static const char *TAG = "iris_screen";
static screen_mirror_t s_mirror;

static void release_frame_storage(screen_mirror_t *mirror)
{
    uint8_t *capture = NULL;
    if (mirror->lock != NULL &&
            xSemaphoreTake(mirror->lock, portMAX_DELAY) == pdTRUE) {
        capture = mirror->capture;
        mirror->capture = NULL;
        mirror->capture_ready = false;
        xSemaphoreGive(mirror->lock);
    }
    heap_caps_free(capture);
}

/* The view's framebuffer is the documented little-endian RGB565 surface;
 * byte swapping for the panel happens on a separate transfer copy. */
static esp_err_t snapshot_frame(screen_mirror_t *mirror)
{
    if (xSemaphoreTake(mirror->lock, portMAX_DELAY) != pdTRUE) {
        return ESP_ERR_TIMEOUT;
    }
    esp_err_t err = ESP_ERR_INVALID_STATE;
    const uint16_t *frame = vv_esp_framebuffer(mirror->ui);
    if (mirror->capture != NULL && frame != NULL) {
        err = ESP_ERR_TIMEOUT;
        if (vv_esp_lock(mirror->ui, FRAME_LOCK_TIMEOUT_MS)) {
            memcpy(mirror->capture, frame, SCREEN_FRAME_BYTES);
            vv_esp_unlock(mirror->ui);
            mirror->capture_ready = true;
            err = ESP_OK;
        }
    }
    xSemaphoreGive(mirror->lock);
    return err;
}

static esp_err_t screen_begin(const esp_iris_media_desc_t *requested,
                              esp_iris_media_desc_t *actual,
                              uint32_t *total_size, void *user_ctx)
{
    (void)requested;
    screen_mirror_t *mirror = user_ctx;
    if (mirror == NULL || mirror->lock == NULL || actual == NULL ||
            total_size == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    if (xSemaphoreTake(mirror->lock, portMAX_DELAY) != pdTRUE) {
        return ESP_ERR_TIMEOUT;
    }
    vv_view_t *ui = mirror->ui;
    const bool unavailable = ui == NULL || mirror->capture != NULL;
    xSemaphoreGive(mirror->lock);
    if (unavailable) {
        return ESP_ERR_INVALID_STATE;
    }

    uint8_t *capture = heap_caps_malloc(
        SCREEN_FRAME_BYTES, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (capture == NULL) {
        return ESP_ERR_NO_MEM;
    }
    if (xSemaphoreTake(mirror->lock, portMAX_DELAY) != pdTRUE) {
        heap_caps_free(capture);
        return ESP_ERR_TIMEOUT;
    }
    if (mirror->capture != NULL) {
        xSemaphoreGive(mirror->lock);
        heap_caps_free(capture);
        return ESP_ERR_INVALID_STATE;
    }
    mirror->capture = capture;
    mirror->capture_ready = false;
    xSemaphoreGive(mirror->lock);
    /* Never expose unpainted pixels during an early-boot capture. */
    if (!vv_esp_wait_first_frame(ui, FULL_REPAINT_TIMEOUT_MS)) {
        release_frame_storage(mirror);
        return ESP_ERR_TIMEOUT;
    }
    esp_err_t err = snapshot_frame(mirror);
    if (err != ESP_OK) {
        release_frame_storage(mirror);
        return err;
    }

    *actual = (esp_iris_media_desc_t) {
        .x = 0,
        .y = 0,
        .width = BSP_LCD_H_RES,
        .height = BSP_LCD_V_RES,
        .stride = SCREEN_STRIDE,
        .format = ESP_IRIS_PIXEL_FORMAT_RGB565,
        .quality = 0,
    };
    *total_size = SCREEN_FRAME_BYTES;
    return ESP_OK;
}

static esp_err_t screen_read(uint32_t offset, uint8_t *out, size_t capacity,
                             size_t *out_size, void *user_ctx)
{
    screen_mirror_t *mirror = user_ctx;
    if (mirror == NULL || mirror->capture == NULL || out == NULL ||
        out_size == NULL || capacity == 0 || offset >= SCREEN_FRAME_BYTES) {
        return ESP_ERR_INVALID_ARG;
    }

    if (offset == 0 && !mirror->capture_ready) {
        esp_err_t err = snapshot_frame(mirror);
        if (err != ESP_OK) {
            return err;
        }
    } else if (!mirror->capture_ready) {
        return ESP_ERR_INVALID_STATE;
    }

    size_t size = SCREEN_FRAME_BYTES - offset;
    if (size > capacity) {
        size = capacity;
    }
    memcpy(out, mirror->capture + offset, size);
    *out_size = size;
    if (offset + size == SCREEN_FRAME_BYTES) {
        mirror->capture_ready = false;
    }
    return ESP_OK;
}

static void screen_end(void *user_ctx)
{
    screen_mirror_t *mirror = user_ctx;
    if (mirror == NULL) {
        return;
    }
    release_frame_storage(mirror);
}

esp_err_t iris_screen_mirror_init(void)
{
    if (s_mirror.lock != NULL) {
        return ESP_ERR_INVALID_STATE;
    }
    s_mirror.lock = xSemaphoreCreateMutexStatic(&s_mirror.lock_storage);
    if (s_mirror.lock == NULL) {
        return ESP_ERR_NO_MEM;
    }
    const esp_iris_screen_backend_t backend = {
        .begin = screen_begin,
        .read = screen_read,
        .end = screen_end,
        .user_ctx = &s_mirror,
    };
    esp_err_t err = esp_iris_screen_register(&backend);
    if (err != ESP_OK) {
        vSemaphoreDelete(s_mirror.lock);
        s_mirror.lock = NULL;
        return err;
    }
    ESP_LOGI(TAG,
             "Registered %dx%d RGB565 screen backend (capture on demand)",
             BSP_LCD_H_RES, BSP_LCD_V_RES);
    return ESP_OK;
}

esp_err_t iris_screen_mirror_attach(vv_view_t *ui)
{
    if (ui == NULL || s_mirror.lock == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    if (xSemaphoreTake(s_mirror.lock, portMAX_DELAY) != pdTRUE) {
        return ESP_ERR_TIMEOUT;
    }
    if (s_mirror.capture != NULL) {
        xSemaphoreGive(s_mirror.lock);
        return ESP_ERR_INVALID_STATE;
    }
    s_mirror.ui = ui;
    xSemaphoreGive(s_mirror.lock);
    return ESP_OK;
}
