// SPDX-License-Identifier: Apache-2.0
#pragma once

/* Constant scene tables emitted by tools/gen_vibe_view.py. Do not build these
 * by hand: the generator resolves coordinates, draw order and glyph sets. */

#include <stdint.h>
#include "vibe_view.h"

#ifdef __cplusplus
extern "C" {
#endif

#define VV_NONE 0xFFFFu
#define VV_NO_INDEX 0xFFu

enum {
    VV_OBJ_LAYER,
    VV_OBJ_LABEL,
    VV_OBJ_CONTAINER,
    VV_OBJ_BUTTON,
    VV_OBJ_LIST,
    VV_OBJ_KEYBOARD,
    VV_OBJ_IMAGE,
    VV_OBJ_PROGRESS,
    VV_OBJ_TEMPLATE,
};

enum { VV_ALIGN_LEFT, VV_ALIGN_CENTER, VV_ALIGN_RIGHT };

#define VV_FLAG_HIDDEN 0x01u
#define VV_FLAG_BG 0x02u

typedef struct {
    uint8_t type;
    uint8_t font;     /* Asset font index, VV_NO_INDEX without text. */
    uint8_t align;
    uint8_t flags;
    int16_t parent;   /* Object index, -1 for pages and template roots. */
    int16_t x, y, w, h; /* Absolute, or relative to the template root. */
    uint16_t fg, bg;  /* RGB565. */
    uint8_t radius;
    uint8_t tmpl;     /* Owning template, VV_NO_INDEX for scene objects. */
    uint16_t bind;    /* Text, value or visibility bind, VV_NONE. */
    uint16_t action;  /* Click or row-select action, VV_NONE. */
    uint16_t text;    /* Authored string index, VV_NONE. */
    uint16_t ref;     /* List, keyboard, image or template index; progress value. */
    uint16_t subtree_end; /* Draw-order index following this object's subtree. */
} vv_object_def_t;

typedef struct {
    uint16_t object;
    uint8_t tmpl;
    uint8_t slots;    /* Visible rows plus one partially scrolled row. */
    uint16_t item_height;
} vv_list_def_t;

#define VV_TEMPLATE_MAX_BINDS 4

typedef struct {
    uint16_t root;
    uint16_t action;     /* Row selection. */
    uint16_t draw_first; /* Range in vv_scene_t.template_order. */
    uint16_t draw_count;
    uint8_t bind_count;
    uint16_t binds[VV_TEMPLATE_MAX_BINDS];
} vv_template_def_t;

typedef struct {
    uint16_t object;
    uint16_t action;
    uint16_t bg, key, key_text, function, function_text;
    uint16_t del, del_text, space, space_text, ok, ok_text;
    uint8_t radius, font, function_font;
    uint8_t shift_icon, delete_icon; /* Image index, VV_NO_INDEX. */
    uint16_t shift_label, delete_label, ok_label, symbols_label, letters_label, space_label;
} vv_keyboard_def_t;

struct vv_scene {
    uint16_t width, height, background;
    uint16_t object_count;
    const vv_object_def_t *objects;
    uint16_t draw_count;
    const uint16_t *draw_order;      /* Scene objects outside templates. */
    const uint16_t *template_order;  /* Template objects, root first. */
    uint8_t list_count;
    const vv_list_def_t *lists;
    uint8_t template_count;
    const vv_template_def_t *templates;
    uint8_t keyboard_count;
    const vv_keyboard_def_t *keyboards;
    uint16_t string_count;
    const char *const *strings;
    uint16_t bind_count;
    const uint16_t *bind_objects;    /* Bind ID to its object index. */
    uint32_t assets_crc32;           /* Asset blob this scene was generated with. */
};

/* ---- Asset blob, little-endian, 4-byte aligned ------------------------- */

#define VV_ASSETS_MAGIC "VVA1"
#define VV_ASSETS_VERSION 1u

typedef struct {
    char magic[4];
    uint16_t version;
    uint16_t font_count;
    uint16_t image_count;
    uint16_t reserved;
    uint32_t total_size;
    uint32_t fonts_offset;  /* uint32_t offsets to vv_font_t, font_count entries. */
    uint32_t images_offset; /* uint32_t offsets to vv_image_t, image_count entries. */
    uint32_t crc32;         /* CRC-32 of every byte after this header. */
} vv_assets_header_t;

typedef struct {
    uint16_t size_px;
    uint16_t glyph_count;
    int16_t ascent;
    int16_t descent;
    uint16_t line_height;
    uint16_t reserved;
    uint32_t glyphs_offset; /* vv_glyph_t sorted by codepoint. */
    uint32_t bitmap_offset; /* 4-bit coverage, high nibble first, rows byte-padded. */
} vv_font_t;

typedef struct {
    uint32_t codepoint;
    uint32_t bitmap;   /* Offset from vv_font_t.bitmap_offset. */
    uint8_t width, height;
    int8_t x_offset;   /* Bitmap left relative to the pen. */
    int8_t y_offset;   /* Bitmap top relative to the baseline. */
    uint8_t advance;
    uint8_t reserved[3];
} vv_glyph_t;

enum {
    VV_IMAGE_L1 = 1, /* 1-bit luminance, MSB first, rows byte-padded. */
    VV_IMAGE_A8 = 2, /* 8-bit alpha tinted by the caller. */
};

typedef struct {
    uint16_t width, height;
    uint8_t format;
    uint8_t reserved[3];
    uint32_t data_offset;
    uint32_t data_size;
} vv_image_t;

#ifdef __cplusplus
}
#endif
