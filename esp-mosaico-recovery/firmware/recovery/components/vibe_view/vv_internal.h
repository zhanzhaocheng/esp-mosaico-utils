// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "vibe_view.h"
#include "vv_scene_def.h"

#define VV_TEXT_MAX 192
#define VV_ROW_TEXT_MAX 96
#define VV_MAX_TIMERS 8
#define VV_MAX_DIRTY 8
#define VV_INPUT_QUEUE 32
#define VV_MAX_FONTS 8
#define VV_MAX_IMAGES 8
#define VV_DRAG_START_PX 16
#define VV_KEY_COUNT_MAX 40

typedef struct {
    int16_t x, y;
    bool pressed;
} vv_input_t;

typedef struct {
    uint32_t period, due;
    vv_timer_cb_t callback;
    void *ctx;
    bool active;
} vv_timer_t;

typedef struct {
    int32_t item; /* Bound item, -1 when the slot needs a callback. */
    char text[VV_TEMPLATE_MAX_BINDS][VV_ROW_TEXT_MAX];
} vv_slot_t;

typedef struct {
    vv_row_cb_t callback;
    void *ctx;
    uint32_t total;
    int32_t scroll;
    int32_t velocity; /* px/s while coasting after a drag. */
    uint32_t coast_ms;
    bool coasting;
    vv_slot_t *slots;
} vv_list_rt_t;

enum {
    VV_KEY_CHAR,
    VV_KEY_SHIFT,
    VV_KEY_DELETE,
    VV_KEY_MODE,
    VV_KEY_SPACE,
    VV_KEY_OK,
    VV_KEY_MORE,
};

typedef struct {
    int16_t x, y, w, h;
    uint8_t kind;
    char ch;
} vv_key_t;

typedef struct {
    uint8_t mode;
} vv_keyboard_rt_t;

enum { VV_PRESS_NONE, VV_PRESS_BUTTON, VV_PRESS_ROW, VV_PRESS_KEY, VV_PRESS_LIST };

typedef struct {
    bool down, dragging, cancelled;
    uint8_t kind;
    uint16_t object;
    uint8_t list;
    int32_t item;
    int8_t key;
    int16_t x, y, start_x, start_y;
    int32_t start_scroll;
    int16_t sample_y[4];
    uint32_t sample_ms[4];
    uint8_t samples;
} vv_press_t;

typedef struct {
    const vv_font_t *header;
    const vv_glyph_t *glyphs;
    const uint8_t *bitmap;
} vv_font_rt_t;

typedef struct {
    const vv_image_t *header;
    const uint8_t *data;
} vv_image_rt_t;

struct vv_view {
    const vv_scene_t *scene;
    const uint8_t *assets;
    vv_font_rt_t fonts[VV_MAX_FONTS];
    uint8_t font_count;
    vv_image_rt_t images[VV_MAX_IMAGES];
    uint8_t image_count;
    uint16_t *fb;
    uint16_t width, height;

    uint8_t *visible;     /* Per object. */
    char **texts;         /* Per object: runtime text, or NULL for authored only. */
    int32_t *values;      /* Per bind. */
    vv_list_rt_t *lists;
    vv_keyboard_rt_t *keyboards;
    char *text_arena;

    vv_event_cb_t event_cb;
    void *event_ctx;

    void (*lock)(void *ctx);
    void (*unlock)(void *ctx);
    void *lock_ctx;
    vv_timer_t timers[VV_MAX_TIMERS];
    vv_input_t queue[VV_INPUT_QUEUE];
    uint8_t queue_head, queue_count;

    vv_press_t press;
    uint32_t now;
    bool time_valid;

    vv_rect_t dirty[VV_MAX_DIRTY];
    uint8_t dirty_count;
};

/* Assets. */
uint32_t vv_crc32(const uint8_t *data, size_t size);
vv_err_t vv_assets_load(vv_view_t *view, const void *assets, size_t size);
const vv_glyph_t *vv_glyph(const vv_font_rt_t *font, uint32_t codepoint);

/* Geometry and invalidation. */
void vv_invalidate(vv_view_t *view, int x, int y, int w, int h);
void vv_invalidate_object(vv_view_t *view, uint16_t object);
bool vv_object_shown(const vv_view_t *view, uint16_t object);

/* Lists. */
int32_t vv_list_max_scroll(const vv_view_t *view, uint8_t list);
void vv_list_bind_rows(vv_view_t *view, uint8_t list);

/* Keyboard layout shared by painting and hit testing. */
size_t vv_keyboard_layout(const vv_view_t *view, uint8_t keyboard, vv_key_t *keys, size_t capacity);
int vv_keyboard_hit(const vv_view_t *view, uint8_t keyboard, int x, int y);
const char *vv_keyboard_label(const vv_view_t *view, uint8_t keyboard, const vv_key_t *key, char *buffer);

/* Painting. */
void vv_paint(vv_view_t *view, const vv_rect_t *clip);
