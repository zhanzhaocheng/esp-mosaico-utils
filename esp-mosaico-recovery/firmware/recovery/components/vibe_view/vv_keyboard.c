// SPDX-License-Identifier: Apache-2.0
#include <string.h>
#include "vv_internal.h"

/* Four rows inside the keyboard's authored rectangle. Letters follow QWERTY;
 * the two symbol pages together cover every printable ASCII character that
 * Wi-Fi passphrases may contain. */
static const char *const s_rows[4][3] = {
    {"qwertyuiop", "asdfghjkl", "zxcvbnm"},
    {"QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"},
    {"1234567890", "-/:;()$&@\"", ".,?!'#%"},
    {"[]{}^*+=<>", "_\\|~`#%$&@", ".,?!'\"-"},
};

#define ROW_TOP 4
#define ROW_PITCH 58
#define KEY_H 50
#define KEY_W 44
#define KEY_GAP 4
#define EDGE 2

static void row_of_chars(vv_key_t *keys, size_t *n, size_t capacity, const char *chars, int x, int y)
{
    for (const char *c = chars; *c && *n < capacity; ++c, x += KEY_W + KEY_GAP)
        keys[(*n)++] = (vv_key_t){(int16_t)x, (int16_t)y, KEY_W, KEY_H, VV_KEY_CHAR, *c};
}

static void add(vv_key_t *keys, size_t *n, size_t capacity, int x, int y, int w, uint8_t kind)
{
    if (*n < capacity) keys[(*n)++] = (vv_key_t){(int16_t)x, (int16_t)y, (int16_t)w, KEY_H, kind, 0};
}

size_t vv_keyboard_layout(const vv_view_t *view, uint8_t keyboard, vv_key_t *keys, size_t capacity)
{
    const vv_object_def_t *o = &view->scene->objects[view->scene->keyboards[keyboard].object];
    const uint8_t mode = view->keyboards[keyboard].mode;
    const char *const *rows = s_rows[mode < 4 ? mode : 0];
    size_t n = 0;
    int y = o->y + ROW_TOP;
    for (int r = 0; r < 2; ++r, y += ROW_PITCH) {
        const int count = (int)strlen(rows[r]);
        const int width = count * KEY_W + (count - 1) * KEY_GAP;
        row_of_chars(keys, &n, capacity, rows[r], o->x + (o->w - width) / 2, y);
    }
    const int side = (o->w - 2 * EDGE - 7 * KEY_W - 8 * KEY_GAP) / 2;
    add(keys, &n, capacity, o->x + EDGE, y, side, mode >= VV_KEYBOARD_SYMBOLS ? VV_KEY_MORE : VV_KEY_SHIFT);
    row_of_chars(keys, &n, capacity, rows[2], o->x + EDGE + side + KEY_GAP, y);
    add(keys, &n, capacity, o->x + o->w - EDGE - side, y, side, VV_KEY_DELETE);
    y += ROW_PITCH;
    const int mode_w = 90, ok_w = 120;
    add(keys, &n, capacity, o->x + EDGE, y, mode_w, VV_KEY_MODE);
    add(keys, &n, capacity, o->x + EDGE + mode_w + KEY_GAP, y,
        o->w - 2 * EDGE - mode_w - ok_w - 2 * KEY_GAP, VV_KEY_SPACE);
    add(keys, &n, capacity, o->x + o->w - EDGE - ok_w, y, ok_w, VV_KEY_OK);
    return n;
}

int vv_keyboard_hit(const vv_view_t *view, uint8_t keyboard, int x, int y)
{
    vv_key_t keys[VV_KEY_COUNT_MAX];
    const size_t n = vv_keyboard_layout(view, keyboard, keys, VV_KEY_COUNT_MAX);
    /* Gaps between keys belong to the nearest key, as on a phone keyboard. */
    const int slop = (ROW_PITCH - KEY_H + 1) / 2;
    for (size_t i = 0; i < n; ++i) {
        const vv_key_t *k = &keys[i];
        if (x >= k->x - KEY_GAP / 2 && x < k->x + k->w + KEY_GAP / 2 &&
            y >= k->y - slop && y < k->y + k->h + slop)
            return (int)i;
    }
    return -1;
}

const char *vv_keyboard_label(const vv_view_t *view, uint8_t keyboard, const vv_key_t *key, char *buffer)
{
    const vv_keyboard_def_t *def = &view->scene->keyboards[keyboard];
    const char *const *strings = view->scene->strings;
    switch (key->kind) {
    case VV_KEY_CHAR: buffer[0] = key->ch; buffer[1] = 0; return buffer;
    case VV_KEY_SHIFT: return strings[def->shift_label];
    case VV_KEY_DELETE: return strings[def->delete_label];
    case VV_KEY_MODE:
        return strings[view->keyboards[keyboard].mode >= VV_KEYBOARD_SYMBOLS ?
            def->letters_label : def->symbols_label];
    case VV_KEY_SPACE: return strings[def->space_label];
    case VV_KEY_OK: return strings[def->ok_label];
    case VV_KEY_MORE:
        return view->keyboards[keyboard].mode == VV_KEYBOARD_SYMBOLS ? "#+=" : "123";
    default: return "";
    }
}
