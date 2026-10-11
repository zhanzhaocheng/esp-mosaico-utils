// SPDX-License-Identifier: Apache-2.0
#pragma once

/* Vibe View: the fixed-scene C renderer behind the Vibe Mode screen.
 *
 * The scene comes from ui/main.json through tools/gen_vibe_view.py, so the
 * controller addresses texts, values, pages and lists by generated IDs. Every
 * call except vv_inject_touch() and vv_timer_create()/vv_timer_delete() runs
 * on the UI task: from vv_process() callbacks or before the first frame. */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct vv_view vv_view_t;
typedef struct vv_scene vv_scene_t;

typedef enum {
    VV_OK = 0,
    VV_ERR_INVALID_ARG = 1,
    VV_ERR_NO_MEM = 2,
    VV_ERR_INVALID_STATE = 3,
    VV_ERR_NOT_FOUND = 4,
} vv_err_t;

typedef uint16_t vv_list_t;
#define VV_LIST_NONE UINT16_MAX

/** A list row slot, valid only inside a vv_row_cb_t invocation. */
typedef uint16_t vv_row_t;

typedef enum {
    VV_KEYBOARD_LOWER,
    VV_KEYBOARD_UPPER,
    VV_KEYBOARD_SYMBOLS,
    VV_KEYBOARD_SYMBOLS_MORE,
} vv_keyboard_mode_t;

/** Button clicks carry only action. List rows add list and item. Keyboard
 * keys report an ASCII code in arg: 8 is Backspace and 13 is Enter. */
typedef struct {
    uint16_t action;
    vv_list_t list;
    uint32_t item;
    uint32_t arg;
} vv_event_t;

typedef struct {
    int16_t x1, y1, x2, y2; /* Inclusive panel coordinates. */
} vv_rect_t;

typedef void (*vv_event_cb_t)(vv_view_t *view, const vv_event_t *event, void *ctx);
typedef void (*vv_timer_cb_t)(vv_view_t *view, void *ctx);
typedef vv_err_t (*vv_row_cb_t)(vv_view_t *view, vv_row_t row, uint32_t index, void *ctx);

/** Empty or NULL text restores the label's authored text. */
vv_err_t vv_set_text(vv_view_t *view, uint16_t bind, const char *text);
vv_err_t vv_set_value(vv_view_t *view, uint16_t bind, int32_t value);
vv_err_t vv_set_visible(vv_view_t *view, uint16_t bind, bool visible);

vv_list_t vv_list_bind(vv_view_t *view, uint16_t object, vv_row_cb_t callback, void *ctx);
vv_err_t vv_list_set_total(vv_view_t *view, vv_list_t list, uint32_t total);
/** Rebind every visible row through the list callback. */
vv_err_t vv_list_refresh(vv_view_t *view, vv_list_t list);
vv_err_t vv_row_set_text(vv_view_t *view, vv_row_t row, uint16_t bind, const char *text);

vv_err_t vv_keyboard_set_mode(vv_view_t *view, uint16_t object, vv_keyboard_mode_t mode);

/** One handler receives every event. NULL removes it. */
vv_err_t vv_on_event(vv_view_t *view, vv_event_cb_t callback, void *ctx);

/** Thread-safe. Callbacks run on the UI task, first after one period. */
void *vv_timer_create(vv_view_t *view, uint32_t period_ms, vv_timer_cb_t callback, void *ctx);
vv_err_t vv_timer_delete(vv_view_t *view, void *timer);

/** Thread-safe pointer input from a remote session. pressed=false releases. */
vv_err_t vv_inject_touch(vv_view_t *view, int x, int y, bool pressed);

/* ---- Runtime used by the device port and host simulator ---------------- */

typedef struct {
    const vv_scene_t *scene;
    /** Decompressed asset blob produced by gen_vibe_view.py, 4-byte aligned. */
    const void *assets;
    size_t assets_size;
    /** width*height native-endian RGB565 pixels owned by the caller. */
    uint16_t *framebuffer;
    /** Optional: guards the timer table and the injected input queue. */
    void (*lock)(void *ctx);
    void (*unlock)(void *ctx);
    void *lock_ctx;
} vv_config_t;

vv_err_t vv_create(const vv_config_t *config, vv_view_t **out_view);
void vv_destroy(vv_view_t *view);

/** Physical touch sample from the panel's controller, UI task only. */
void vv_touch_sample(vv_view_t *view, bool pressed, int x, int y);

/** Advance input, timers and scrolling to the monotonic time now_ms. */
void vv_process(vv_view_t *view, uint32_t now_ms);

/** Paint pending changes into the framebuffer and report the changed areas.
 * Returns the number of rectangles written to rects; 0 means nothing changed. */
size_t vv_render(vv_view_t *view, vv_rect_t *rects, size_t capacity);

/** True while scrolling or a press needs frequent processing. */
bool vv_is_animating(const vv_view_t *view);

uint16_t vv_width(const vv_view_t *view);
uint16_t vv_height(const vv_view_t *view);

#ifdef __cplusplus
}
#endif
