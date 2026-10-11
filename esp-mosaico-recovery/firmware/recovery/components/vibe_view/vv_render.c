// SPDX-License-Identifier: Apache-2.0
#include <string.h>
#include "vv_internal.h"

/* Half-open painting bounds. */
typedef struct {
    int x1, y1, x2, y2;
} box_t;

static const uint8_t s_alpha4[16] = {0, 2, 4, 6, 9, 11, 13, 15, 17, 19, 21, 23, 26, 28, 30, 32};

static inline uint16_t blend(uint16_t dst, uint16_t src, unsigned alpha32)
{
    if (alpha32 >= 32) return src;
    if (!alpha32) return dst;
    uint32_t d = (dst | ((uint32_t)dst << 16)) & 0x07E0F81Fu;
    const uint32_t s = (src | ((uint32_t)src << 16)) & 0x07E0F81Fu;
    d += ((s - d) * alpha32) >> 5;
    d &= 0x07E0F81Fu;
    return (uint16_t)(d | (d >> 16));
}

static uint16_t lighten(uint16_t color) { return blend(color, 0xFFFF, 6); }

static box_t intersect(box_t a, int x, int y, int w, int h)
{
    if (x > a.x1) a.x1 = x;
    if (y > a.y1) a.y1 = y;
    if (x + w < a.x2) a.x2 = x + w;
    if (y + h < a.y2) a.y2 = y + h;
    return a;
}

static bool empty(box_t b) { return b.x1 >= b.x2 || b.y1 >= b.y2; }

static void fill(vv_view_t *v, box_t b, uint16_t color)
{
    for (int y = b.y1; y < b.y2; ++y) {
        uint16_t *row = v->fb + (size_t)y * v->width;
        for (int x = b.x1; x < b.x2; ++x) row[x] = color;
    }
}

/* Coverage of a corner pixel, 0..32, from 4x4 samples against the arc whose
 * centre is radius pixels inside both outer edges. */
static unsigned corner_coverage(int dx, int dy, int radius)
{
    const int c = radius * 8, limit = c * c;
    unsigned inside = 0;
    for (int sy = 0; sy < 4; ++sy) {
        const int ddy = c - (dy * 8 + sy * 2 + 1);
        for (int sx = 0; sx < 4; ++sx) {
            const int ddx = c - (dx * 8 + sx * 2 + 1);
            if (ddx * ddx + ddy * ddy <= limit) ++inside;
        }
    }
    return inside * 2;
}

static void fill_round(vv_view_t *v, box_t clip, int x, int y, int w, int h, int radius, uint16_t color)
{
    box_t b = intersect(clip, x, y, w, h);
    if (empty(b)) return;
    if (radius > w / 2) radius = w / 2;
    if (radius > h / 2) radius = h / 2;
    for (int yy = b.y1; yy < b.y2; ++yy) {
        uint16_t *row = v->fb + (size_t)yy * v->width;
        int dy = -1;
        if (yy < y + radius) dy = yy - y;
        else if (yy >= y + h - radius) dy = y + h - 1 - yy;
        for (int xx = b.x1; xx < b.x2; ++xx) {
            int dx = -1;
            if (dy >= 0) {
                if (xx < x + radius) dx = xx - x;
                else if (xx >= x + w - radius) dx = x + w - 1 - xx;
            }
            row[xx] = dx < 0 ? color : blend(row[xx], color, corner_coverage(dx, dy, radius));
        }
    }
}

/* ---- Text -------------------------------------------------------------- */

static uint32_t utf8_next(const char **cursor, const char *end)
{
    const unsigned char *s = (const unsigned char *)*cursor;
    uint32_t cp = *s++;
    int extra = cp >= 0xF0 ? 3 : cp >= 0xE0 ? 2 : cp >= 0xC0 ? 1 : 0;
    if (extra) cp &= 0x3Fu >> extra;
    while (extra-- && (const char *)s < end && (*s & 0xC0) == 0x80) cp = (cp << 6) | (*s++ & 0x3F);
    *cursor = (const char *)s;
    return cp;
}

static int advance(const vv_font_rt_t *font, uint32_t cp)
{
    const vv_glyph_t *g = vv_glyph(font, cp);
    if (!g) g = vv_glyph(font, ' ');
    return g ? g->advance : 0;
}

static int text_width(const vv_font_rt_t *font, const char *s, const char *end)
{
    int width = 0;
    while (s < end) width += advance(font, utf8_next(&s, end));
    return width;
}

static void draw_glyph(vv_view_t *v, box_t clip, const vv_font_rt_t *font, const vv_glyph_t *g,
                       int pen, int baseline, uint16_t color)
{
    const int x0 = pen + g->x_offset, y0 = baseline + g->y_offset;
    const box_t b = intersect(clip, x0, y0, g->width, g->height);
    if (empty(b)) return;
    const uint8_t *bits = font->bitmap + g->bitmap;
    const int stride = (g->width + 1) / 2;
    for (int y = b.y1; y < b.y2; ++y) {
        const uint8_t *src = bits + (size_t)(y - y0) * stride;
        uint16_t *row = v->fb + (size_t)y * v->width;
        for (int x = b.x1; x < b.x2; ++x) {
            const int gx = x - x0;
            const unsigned a = (src[gx >> 1] >> ((gx & 1) ? 0 : 4)) & 0x0F;
            if (a) row[x] = blend(row[x], color, s_alpha4[a]);
        }
    }
}

static int draw_run(vv_view_t *v, box_t clip, const vv_font_rt_t *font, const char *s, const char *end,
                    int pen, int baseline, uint16_t color)
{
    while (s < end) {
        const uint32_t cp = utf8_next(&s, end);
        const vv_glyph_t *g = vv_glyph(font, cp);
        if (g) draw_glyph(v, clip, font, g, pen, baseline, color);
        pen += g ? g->advance : advance(font, ' ');
    }
    return pen;
}

static void draw_text(vv_view_t *v, box_t clip, int x, int y, int w, int h, uint8_t font_index,
                      uint8_t align, uint16_t color, const char *text)
{
    if (!text || !*text || font_index >= v->font_count) return;
    clip = intersect(clip, x, y, w, h);
    if (empty(clip)) return;
    const vv_font_rt_t *font = &v->fonts[font_index];
    int lines = 1;
    for (const char *c = text; *c; ++c) lines += *c == '\n';
    const int line_height = font->header->line_height;
    int baseline = y + (h - lines * line_height) / 2 + font->header->ascent;
    static const char dots[] = "...";
    const int dots_width = text_width(font, dots, dots + 3);
    for (const char *line = text; line; baseline += line_height) {
        const char *end = strchr(line, '\n');
        const char *next = end ? end + 1 : NULL;
        if (!end) end = line + strlen(line);
        int width = text_width(font, line, end);
        bool ellipsis = false;
        if (width > w && vv_glyph(font, '.')) {
            /* Keep whole code points that fit before the ellipsis. */
            const char *cut = line;
            width = 0;
            for (const char *c = line; c < end;) {
                const int a = advance(font, utf8_next(&c, end));
                if (width + a + dots_width > w) break;
                width += a;
                cut = c;
            }
            end = cut;
            width += dots_width;
            ellipsis = true;
        }
        int pen = x;
        if (align == VV_ALIGN_CENTER) pen = x + (w - width) / 2;
        else if (align == VV_ALIGN_RIGHT) pen = x + w - width;
        pen = draw_run(v, clip, font, line, end, pen, baseline, color);
        if (ellipsis) (void)draw_run(v, clip, font, dots, dots + 3, pen, baseline, color);
        line = next;
    }
}

/* ---- Images, progress and keyboard ------------------------------------- */

static void draw_image(vv_view_t *v, box_t clip, uint16_t index, int x, int y, uint16_t tint)
{
    if (index >= v->image_count) return;
    const vv_image_rt_t *image = &v->images[index];
    const box_t b = intersect(clip, x, y, image->header->width, image->header->height);
    if (empty(b)) return;
    const bool l1 = image->header->format == VV_IMAGE_L1;
    const size_t stride = l1 ? (image->header->width + 7u) / 8u : image->header->width;
    for (int yy = b.y1; yy < b.y2; ++yy) {
        const uint8_t *src = image->data + (size_t)(yy - y) * stride;
        uint16_t *row = v->fb + (size_t)yy * v->width;
        for (int xx = b.x1; xx < b.x2; ++xx) {
            const int ix = xx - x;
            if (l1) row[xx] = (src[ix >> 3] & (0x80u >> (ix & 7))) ? 0xFFFF : 0x0000;
            else row[xx] = blend(row[xx], tint, (src[ix] * 32u + 127u) / 255u);
        }
    }
}

static void draw_progress(vv_view_t *v, box_t clip, const vv_object_def_t *o, int32_t value)
{
    fill_round(v, clip, o->x, o->y, o->w, o->h, o->radius, o->bg);
    const int width = (int)((int64_t)o->w * value / 100);
    if (width <= 0) return;
    /* A short fill keeps its rounded start and a straight leading edge. */
    const box_t b = intersect(clip, o->x, o->y, width, o->h);
    const int drawn = width < 2 * o->radius ? 2 * o->radius : width;
    fill_round(v, b, o->x, o->y, drawn, o->h, o->radius, o->fg);
}

static void draw_keyboard(vv_view_t *v, box_t clip, uint16_t index, const vv_object_def_t *o)
{
    const uint8_t k = (uint8_t)o->ref;
    const vv_keyboard_def_t *def = &v->scene->keyboards[k];
    const box_t b = intersect(clip, o->x, o->y, o->w, o->h);
    if (empty(b)) return;
    fill(v, b, def->bg);
    vv_key_t keys[VV_KEY_COUNT_MAX];
    const size_t n = vv_keyboard_layout(v, k, keys, VV_KEY_COUNT_MAX);
    const vv_press_t *p = &v->press;
    const bool upper = v->keyboards[k].mode == VV_KEYBOARD_UPPER;
    for (size_t i = 0; i < n; ++i) {
        const vv_key_t *key = &keys[i];
        uint16_t color = def->function, text = def->function_text;
        uint8_t font = def->function_font, icon = VV_NO_INDEX;
        switch (key->kind) {
        case VV_KEY_CHAR: color = def->key; text = def->key_text; font = def->font; break;
        case VV_KEY_SHIFT: if (upper) color = def->key; icon = def->shift_icon; break;
        case VV_KEY_DELETE: color = def->del; text = def->del_text; icon = def->delete_icon; break;
        case VV_KEY_SPACE: color = def->space; text = def->space_text; break;
        case VV_KEY_OK: color = def->ok; text = def->ok_text; break;
        default: break;
        }
        if (p->down && !p->cancelled && p->kind == VV_PRESS_KEY && p->object == index && p->key == (int)i)
            color = lighten(color);
        fill_round(v, b, key->x, key->y, key->w, key->h, def->radius, color);
        if (icon != VV_NO_INDEX && icon < v->image_count) {
            const vv_image_t *h = v->images[icon].header;
            draw_image(v, b, icon, key->x + (key->w - h->width) / 2, key->y + (key->h - h->height) / 2, text);
        } else {
            char buffer[2];
            draw_text(v, b, key->x, key->y, key->w, key->h, font, VV_ALIGN_CENTER, text,
                      vv_keyboard_label(v, k, key, buffer));
        }
    }
}

/* ---- Objects ----------------------------------------------------------- */

static const char *template_text(const vv_view_t *v, const vv_object_def_t *o, const vv_slot_t *slot)
{
    const char *authored = o->text != VV_NONE ? v->scene->strings[o->text] : "";
    if (!slot || o->bind == VV_NONE) return authored;
    const vv_template_def_t *t = &v->scene->templates[o->tmpl];
    for (uint8_t b = 0; b < t->bind_count; ++b) {
        if (t->binds[b] == o->bind) return slot->text[b][0] ? slot->text[b] : authored;
    }
    return authored;
}

static void draw_object(vv_view_t *v, box_t clip, uint16_t index, int x, int y,
                        const vv_slot_t *slot, bool pressed);

static void draw_list(vv_view_t *v, box_t clip, const vv_object_def_t *o)
{
    const uint8_t list = (uint8_t)o->ref;
    const vv_list_def_t *def = &v->scene->lists[list];
    const vv_list_rt_t *rt = &v->lists[list];
    const box_t b = intersect(clip, o->x, o->y, o->w, o->h);
    if (empty(b)) return;
    if (o->flags & VV_FLAG_BG) fill(v, b, o->bg);
    const vv_template_def_t *t = &v->scene->templates[def->tmpl];
    const vv_press_t *p = &v->press;
    const int32_t first = rt->scroll / def->item_height;
    const int32_t last = (rt->scroll + o->h - 1) / def->item_height;
    for (int32_t item = first; item <= last && item < (int32_t)rt->total; ++item) {
        const vv_slot_t *slot = &rt->slots[item % def->slots];
        if (slot->item != item) continue;
        const int row_y = o->y + item * def->item_height - rt->scroll;
        const bool pressed = p->down && !p->dragging && !p->cancelled &&
            p->kind == VV_PRESS_ROW && p->list == list && p->item == item;
        for (uint16_t i = 0; i < t->draw_count; ++i) {
            const uint16_t index = v->scene->template_order[t->draw_first + i];
            const vv_object_def_t *child = &v->scene->objects[index];
            draw_object(v, b, index, o->x + child->x, row_y + child->y, slot, pressed);
        }
    }
}

static void draw_object(vv_view_t *v, box_t clip, uint16_t index, int x, int y,
                        const vv_slot_t *slot, bool pressed)
{
    const vv_object_def_t *o = &v->scene->objects[index];
    switch (o->type) {
    case VV_OBJ_LABEL: {
        const char *text = slot ? template_text(v, o, slot) :
            (v->texts[index] && v->texts[index][0]) ? v->texts[index] :
            o->text != VV_NONE ? v->scene->strings[o->text] : "";
        draw_text(v, clip, x, y, o->w, o->h, o->font, o->align, o->fg, text);
        break;
    }
    case VV_OBJ_CONTAINER:
    case VV_OBJ_TEMPLATE:
        if (o->flags & VV_FLAG_BG) fill_round(v, clip, x, y, o->w, o->h, o->radius, pressed ? lighten(o->bg) : o->bg);
        break;
    case VV_OBJ_BUTTON: {
        const vv_press_t *p = &v->press;
        const bool down = p->down && !p->cancelled && p->kind == VV_PRESS_BUTTON && p->object == index;
        if (o->flags & VV_FLAG_BG) fill_round(v, clip, x, y, o->w, o->h, o->radius, down ? lighten(o->bg) : o->bg);
        draw_text(v, clip, x, y, o->w, o->h, o->font, o->align, o->fg,
                  o->text != VV_NONE ? v->scene->strings[o->text] : "");
        break;
    }
    case VV_OBJ_LIST: draw_list(v, clip, o); break;
    case VV_OBJ_KEYBOARD: draw_keyboard(v, clip, index, o); break;
    case VV_OBJ_IMAGE: draw_image(v, clip, o->ref, x, y, o->fg); break;
    case VV_OBJ_PROGRESS: draw_progress(v, clip, o, o->bind != VV_NONE ? v->values[o->bind] : o->ref); break;
    default: break;
    }
}

void vv_paint(vv_view_t *v, const vv_rect_t *rect)
{
    const box_t clip = {rect->x1, rect->y1, rect->x2 + 1, rect->y2 + 1};
    fill(v, clip, v->scene->background);
    const vv_scene_t *s = v->scene;
    for (uint16_t i = 0; i < s->draw_count;) {
        const uint16_t index = s->draw_order[i];
        const vv_object_def_t *o = &s->objects[index];
        if (!v->visible[index]) {
            i = o->subtree_end;
            continue;
        }
        ++i;
        if (o->x < clip.x2 && o->y < clip.y2 && o->x + o->w > clip.x1 && o->y + o->h > clip.y1)
            draw_object(v, clip, index, o->x, o->y, NULL, false);
    }
}
