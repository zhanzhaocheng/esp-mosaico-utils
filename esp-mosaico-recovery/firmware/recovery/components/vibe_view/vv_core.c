// SPDX-License-Identifier: Apache-2.0
#include <stdlib.h>
#include <string.h>
#include "vv_internal.h"

#define COAST_MIN_SPEED 60   /* px/s below which coasting stops. */
#define COAST_DECAY_MS 325   /* Exponential velocity time constant. */

static void lock(vv_view_t *v) { if (v->lock) v->lock(v->lock_ctx); }
static void unlock(vv_view_t *v) { if (v->unlock) v->unlock(v->lock_ctx); }

static const vv_object_def_t *obj(const vv_view_t *v, uint16_t index) { return &v->scene->objects[index]; }

static bool in_template(const vv_object_def_t *o) { return o->tmpl != VV_NO_INDEX; }

uint16_t vv_width(const vv_view_t *view) { return view ? view->width : 0; }
uint16_t vv_height(const vv_view_t *view) { return view ? view->height : 0; }

/* ---- Invalidation ------------------------------------------------------ */

static bool overlaps(const vv_rect_t *a, const vv_rect_t *b)
{
    return a->x1 <= b->x2 && b->x1 <= a->x2 && a->y1 <= b->y2 && b->y1 <= a->y2;
}

static void merge(vv_rect_t *into, const vv_rect_t *r)
{
    if (r->x1 < into->x1) into->x1 = r->x1;
    if (r->y1 < into->y1) into->y1 = r->y1;
    if (r->x2 > into->x2) into->x2 = r->x2;
    if (r->y2 > into->y2) into->y2 = r->y2;
}

void vv_invalidate(vv_view_t *v, int x, int y, int w, int h)
{
    if (w <= 0 || h <= 0) return;
    int x2 = x + w - 1, y2 = y + h - 1;
    if (x < 0) x = 0;
    if (y < 0) y = 0;
    if (x2 >= v->width) x2 = v->width - 1;
    if (y2 >= v->height) y2 = v->height - 1;
    if (x > x2 || y > y2) return;
    vv_rect_t r = {(int16_t)x, (int16_t)y, (int16_t)x2, (int16_t)y2};
    for (uint8_t i = 0; i < v->dirty_count; ++i) {
        if (overlaps(&v->dirty[i], &r)) {
            merge(&r, &v->dirty[i]);
            v->dirty[i] = v->dirty[--v->dirty_count];
            i = (uint8_t)-1; /* Rescan: the grown rectangle may touch others. */
        }
    }
    if (v->dirty_count == VV_MAX_DIRTY) {
        for (uint8_t i = 1; i < v->dirty_count; ++i) merge(&v->dirty[0], &v->dirty[i]);
        merge(&v->dirty[0], &r);
        v->dirty_count = 1;
        return;
    }
    v->dirty[v->dirty_count++] = r;
}

void vv_invalidate_object(vv_view_t *v, uint16_t index)
{
    const vv_object_def_t *o = obj(v, index);
    if (!in_template(o)) vv_invalidate(v, o->x, o->y, o->w, o->h);
}

bool vv_object_shown(const vv_view_t *v, uint16_t index)
{
    for (int i = index; i >= 0; i = obj(v, (uint16_t)i)->parent) {
        if (!v->visible[i]) return false;
        /* Template objects are shown through their list. */
        if (obj(v, (uint16_t)i)->type == VV_OBJ_TEMPLATE) return true;
    }
    return true;
}

/* ---- Creation ---------------------------------------------------------- */

vv_err_t vv_create(const vv_config_t *config, vv_view_t **out_view)
{
    if (!config || !config->scene || !config->framebuffer || !out_view) return VV_ERR_INVALID_ARG;
    const vv_scene_t *scene = config->scene;
    vv_view_t *v = calloc(1, sizeof(*v));
    if (!v) return VV_ERR_NO_MEM;
    v->scene = scene;
    v->fb = config->framebuffer;
    v->width = scene->width;
    v->height = scene->height;
    v->lock = config->lock;
    v->unlock = config->unlock;
    v->lock_ctx = config->lock_ctx;
    vv_err_t err = vv_assets_load(v, config->assets, config->assets_size);
    if (err != VV_OK) {
        free(v);
        return err;
    }
    size_t texts = 0;
    for (uint16_t i = 0; i < scene->object_count; ++i) {
        const vv_object_def_t *o = &scene->objects[i];
        if (o->type == VV_OBJ_LABEL && o->bind != VV_NONE && !in_template(o)) ++texts;
    }
    v->visible = calloc(scene->object_count, 1);
    v->texts = calloc(scene->object_count, sizeof(char *));
    v->values = calloc(scene->bind_count ? scene->bind_count : 1, sizeof(int32_t));
    v->lists = calloc(scene->list_count ? scene->list_count : 1, sizeof(vv_list_rt_t));
    v->keyboards = calloc(scene->keyboard_count ? scene->keyboard_count : 1, sizeof(vv_keyboard_rt_t));
    v->text_arena = calloc(texts ? texts : 1, VV_TEXT_MAX);
    bool ok = v->visible && v->texts && v->values && v->lists && v->keyboards && v->text_arena;
    for (uint8_t i = 0; ok && i < scene->list_count; ++i) {
        v->lists[i].slots = calloc(scene->lists[i].slots, sizeof(vv_slot_t));
        ok = v->lists[i].slots != NULL;
        for (uint8_t s = 0; ok && s < scene->lists[i].slots; ++s) v->lists[i].slots[s].item = -1;
    }
    if (!ok) {
        vv_destroy(v);
        return VV_ERR_NO_MEM;
    }
    char *arena = v->text_arena;
    for (uint16_t i = 0; i < scene->object_count; ++i) {
        const vv_object_def_t *o = &scene->objects[i];
        v->visible[i] = !(o->flags & VV_FLAG_HIDDEN);
        if (o->type == VV_OBJ_LABEL && o->bind != VV_NONE && !in_template(o)) {
            v->texts[i] = arena;
            arena += VV_TEXT_MAX;
        }
        if (o->type == VV_OBJ_PROGRESS && o->bind != VV_NONE && o->ref != VV_NONE)
            v->values[o->bind] = o->ref;
    }
    v->press.key = -1;
    vv_invalidate(v, 0, 0, v->width, v->height);
    *out_view = v;
    return VV_OK;
}

void vv_destroy(vv_view_t *v)
{
    if (!v) return;
    for (uint8_t i = 0; v->lists && i < v->scene->list_count; ++i) free(v->lists[i].slots);
    free(v->visible);
    free(v->texts);
    free(v->values);
    free(v->lists);
    free(v->keyboards);
    free(v->text_arena);
    free(v);
}

/* ---- Bound values ------------------------------------------------------ */

static void copy_text(char *dst, size_t capacity, const char *src)
{
    size_t n = strlen(src);
    if (n >= capacity) {
        n = capacity - 1;
        while (n && ((unsigned char)src[n] & 0xC0) == 0x80) --n; /* Keep whole UTF-8 sequences. */
    }
    memcpy(dst, src, n);
    dst[n] = 0;
}

static int bound_object(const vv_view_t *v, uint16_t bind)
{
    return v && bind < v->scene->bind_count ? v->scene->bind_objects[bind] : -1;
}

vv_err_t vv_set_text(vv_view_t *v, uint16_t bind, const char *text)
{
    const int index = bound_object(v, bind);
    if (index < 0 || !v->texts[index]) return VV_ERR_INVALID_ARG;
    char next[VV_TEXT_MAX];
    copy_text(next, sizeof(next), text ? text : "");
    if (strcmp(next, v->texts[index]) == 0) return VV_OK;
    memcpy(v->texts[index], next, sizeof(next));
    vv_invalidate_object(v, (uint16_t)index);
    return VV_OK;
}

vv_err_t vv_set_value(vv_view_t *v, uint16_t bind, int32_t value)
{
    const int index = bound_object(v, bind);
    if (index < 0 || obj(v, (uint16_t)index)->type != VV_OBJ_PROGRESS) return VV_ERR_INVALID_ARG;
    if (value < 0) value = 0;
    if (value > 100) value = 100;
    if (v->values[bind] != value) {
        v->values[bind] = value;
        vv_invalidate_object(v, (uint16_t)index);
    }
    return VV_OK;
}

vv_err_t vv_set_visible(vv_view_t *v, uint16_t bind, bool visible)
{
    const int index = bound_object(v, bind);
    if (index < 0 || in_template(obj(v, (uint16_t)index))) return VV_ERR_INVALID_ARG;
    if (v->visible[index] != visible) {
        v->visible[index] = visible;
        vv_invalidate_object(v, (uint16_t)index);
        /* A page that hides under a press must not deliver its click. */
        v->press.cancelled = v->press.down;
    }
    return VV_OK;
}

vv_err_t vv_keyboard_set_mode(vv_view_t *v, uint16_t object, vv_keyboard_mode_t mode)
{
    if (!v || mode > VV_KEYBOARD_SYMBOLS_MORE) return VV_ERR_INVALID_ARG;
    for (uint8_t k = 0; k < v->scene->keyboard_count; ++k) {
        if (v->scene->keyboards[k].object != object) continue;
        if (v->keyboards[k].mode != mode) {
            v->keyboards[k].mode = (uint8_t)mode;
            vv_invalidate_object(v, object);
        }
        return VV_OK;
    }
    return VV_ERR_NOT_FOUND;
}

/* ---- Lists ------------------------------------------------------------- */

int32_t vv_list_max_scroll(const vv_view_t *v, uint8_t list)
{
    const vv_list_def_t *def = &v->scene->lists[list];
    const int32_t content = (int32_t)v->lists[list].total * def->item_height;
    const int32_t visible = obj(v, def->object)->h;
    return content > visible ? content - visible : 0;
}

static void list_invalidate(vv_view_t *v, uint8_t list, bool rebind)
{
    if (rebind) {
        for (uint8_t s = 0; s < v->scene->lists[list].slots; ++s) v->lists[list].slots[s].item = -1;
    }
    vv_invalidate_object(v, v->scene->lists[list].object);
}

vv_list_t vv_list_bind(vv_view_t *v, uint16_t object, vv_row_cb_t callback, void *ctx)
{
    if (!v || !callback) return VV_LIST_NONE;
    for (uint8_t i = 0; i < v->scene->list_count; ++i) {
        if (v->scene->lists[i].object != object) continue;
        v->lists[i].callback = callback;
        v->lists[i].ctx = ctx;
        list_invalidate(v, i, true);
        return i;
    }
    return VV_LIST_NONE;
}

vv_err_t vv_list_set_total(vv_view_t *v, vv_list_t list, uint32_t total)
{
    if (!v || list >= v->scene->list_count) return VV_ERR_INVALID_ARG;
    vv_list_rt_t *rt = &v->lists[list];
    if (rt->total == total) return VV_OK;
    rt->total = total;
    const int32_t max = vv_list_max_scroll(v, (uint8_t)list);
    if (rt->scroll > max) rt->scroll = max;
    list_invalidate(v, (uint8_t)list, true);
    return VV_OK;
}

vv_err_t vv_list_refresh(vv_view_t *v, vv_list_t list)
{
    if (!v || list >= v->scene->list_count) return VV_ERR_INVALID_ARG;
    list_invalidate(v, (uint8_t)list, true);
    return VV_OK;
}

vv_err_t vv_row_set_text(vv_view_t *v, vv_row_t row, uint16_t bind, const char *text)
{
    const uint8_t list = (uint8_t)(row >> 8), slot = (uint8_t)row;
    if (!v || list >= v->scene->list_count || slot >= v->scene->lists[list].slots) return VV_ERR_INVALID_ARG;
    const vv_template_def_t *t = &v->scene->templates[v->scene->lists[list].tmpl];
    for (uint8_t b = 0; b < t->bind_count; ++b) {
        if (t->binds[b] != bind) continue;
        char *dst = v->lists[list].slots[slot].text[b];
        char next[VV_ROW_TEXT_MAX];
        copy_text(next, sizeof(next), text ? text : "");
        if (strcmp(dst, next) != 0) {
            memcpy(dst, next, sizeof(next));
            list_invalidate(v, list, false);
        }
        return VV_OK;
    }
    return VV_ERR_INVALID_ARG;
}

void vv_list_bind_rows(vv_view_t *v, uint8_t list)
{
    const vv_list_def_t *def = &v->scene->lists[list];
    vv_list_rt_t *rt = &v->lists[list];
    if (!rt->callback || !vv_object_shown(v, def->object)) return;
    const int32_t first = rt->scroll / def->item_height;
    const int32_t last = (rt->scroll + obj(v, def->object)->h - 1) / def->item_height;
    for (int32_t item = first; item <= last && item < (int32_t)rt->total; ++item) {
        vv_slot_t *slot = &rt->slots[item % def->slots];
        if (slot->item == item) continue;
        memset(slot->text, 0, sizeof(slot->text));
        slot->item = item;
        (void)rt->callback(v, (vv_row_t)((list << 8) | (item % def->slots)), (uint32_t)item, rt->ctx);
    }
}

/* ---- Events, timers and input ----------------------------------------- */

vv_err_t vv_on_event(vv_view_t *v, vv_event_cb_t callback, void *ctx)
{
    if (!v) return VV_ERR_INVALID_ARG;
    v->event_cb = callback;
    v->event_ctx = ctx;
    return VV_OK;
}

static void emit(vv_view_t *v, uint16_t action, vv_list_t list, uint32_t item, uint32_t arg)
{
    if (!v->event_cb || action == VV_NONE) return;
    const vv_event_t event = {action, list, item, arg};
    v->event_cb(v, &event, v->event_ctx);
}

void *vv_timer_create(vv_view_t *v, uint32_t period_ms, vv_timer_cb_t callback, void *ctx)
{
    if (!v || !callback || !period_ms) return NULL;
    void *handle = NULL;
    lock(v);
    for (int i = 0; i < VV_MAX_TIMERS; ++i) {
        vv_timer_t *t = &v->timers[i];
        if (t->active) continue;
        t->period = period_ms;
        t->due = v->now + period_ms;
        t->callback = callback;
        t->ctx = ctx;
        t->active = true;
        handle = t;
        break;
    }
    unlock(v);
    return handle;
}

vv_err_t vv_timer_delete(vv_view_t *v, void *timer)
{
    if (!v || !timer) return VV_ERR_INVALID_ARG;
    vv_err_t err = VV_ERR_NOT_FOUND;
    lock(v);
    for (int i = 0; i < VV_MAX_TIMERS; ++i) {
        if (&v->timers[i] == timer && v->timers[i].active) {
            v->timers[i].active = false;
            err = VV_OK;
        }
    }
    unlock(v);
    return err;
}

vv_err_t vv_inject_touch(vv_view_t *v, int x, int y, bool pressed)
{
    if (!v || x < 0 || y < 0 || x >= v->width || y >= v->height) return VV_ERR_INVALID_ARG;
    vv_err_t err = VV_OK;
    lock(v);
    if (v->queue_count == VV_INPUT_QUEUE) {
        err = VV_ERR_NO_MEM;
    } else {
        v->queue[(v->queue_head + v->queue_count) % VV_INPUT_QUEUE] = (vv_input_t){(int16_t)x, (int16_t)y, pressed};
        ++v->queue_count;
    }
    unlock(v);
    return err;
}

static bool contains(const vv_object_def_t *o, int x, int y)
{
    return x >= o->x && y >= o->y && x < o->x + o->w && y < o->y + o->h;
}

static void hit_test(vv_view_t *v, int x, int y)
{
    vv_press_t *p = &v->press;
    p->kind = VV_PRESS_NONE;
    const vv_scene_t *s = v->scene;
    /* The last visible interactive object in draw order is on top. */
    for (uint16_t i = 0; i < s->draw_count;) {
        const uint16_t index = s->draw_order[i];
        const vv_object_def_t *o = obj(v, index);
        if (!v->visible[index]) {
            i = o->subtree_end;
            continue;
        }
        ++i;
        if (!contains(o, x, y)) continue;
        if (o->type == VV_OBJ_BUTTON && o->action != VV_NONE) {
            p->kind = VV_PRESS_BUTTON;
            p->object = index;
        } else if (o->type == VV_OBJ_LIST && o->ref != VV_NONE) {
            const uint8_t list = (uint8_t)o->ref;
            const vv_list_def_t *def = &s->lists[list];
            const int32_t item = (y - o->y + v->lists[list].scroll) / def->item_height;
            const vv_object_def_t *root = obj(v, s->templates[def->tmpl].root);
            const int32_t within = (y - o->y + v->lists[list].scroll) % def->item_height;
            p->kind = VV_PRESS_LIST;
            p->object = index;
            p->list = list;
            p->item = -1;
            if (item < (int32_t)v->lists[list].total && within < root->h && x - o->x < root->w) {
                p->kind = VV_PRESS_ROW;
                p->item = item;
            }
            p->start_scroll = v->lists[list].scroll;
            v->lists[list].coasting = false;
        } else if (o->type == VV_OBJ_KEYBOARD && o->ref != VV_NONE) {
            const int key = vv_keyboard_hit(v, (uint8_t)o->ref, x, y);
            p->kind = key >= 0 ? VV_PRESS_KEY : VV_PRESS_NONE;
            p->object = index;
            p->key = (int8_t)key;
        }
    }
}

static void invalidate_press(vv_view_t *v)
{
    const vv_press_t *p = &v->press;
    if (p->kind == VV_PRESS_BUTTON || p->kind == VV_PRESS_KEY) vv_invalidate_object(v, p->object);
    if (p->kind == VV_PRESS_ROW || p->kind == VV_PRESS_LIST) vv_invalidate_object(v, v->scene->lists[p->list].object);
}

static void press_keyboard_key(vv_view_t *v, uint16_t object)
{
    const vv_object_def_t *o = obj(v, object);
    const uint8_t k = (uint8_t)o->ref;
    vv_key_t keys[VV_KEY_COUNT_MAX];
    const size_t n = vv_keyboard_layout(v, k, keys, VV_KEY_COUNT_MAX);
    if (v->press.key < 0 || (size_t)v->press.key >= n) return;
    const vv_key_t *key = &keys[v->press.key];
    vv_keyboard_rt_t *rt = &v->keyboards[k];
    const uint16_t action = v->scene->keyboards[k].action;
    switch (key->kind) {
    case VV_KEY_CHAR: emit(v, action, VV_LIST_NONE, 0, (uint8_t)key->ch); break;
    case VV_KEY_SPACE: emit(v, action, VV_LIST_NONE, 0, ' '); break;
    case VV_KEY_DELETE: emit(v, action, VV_LIST_NONE, 0, 8); break;
    case VV_KEY_OK: emit(v, action, VV_LIST_NONE, 0, 13); break;
    case VV_KEY_SHIFT:
        rt->mode = rt->mode == VV_KEYBOARD_LOWER ? VV_KEYBOARD_UPPER : VV_KEYBOARD_LOWER;
        break;
    case VV_KEY_MODE:
        rt->mode = rt->mode >= VV_KEYBOARD_SYMBOLS ? VV_KEYBOARD_LOWER : VV_KEYBOARD_SYMBOLS;
        break;
    case VV_KEY_MORE:
        rt->mode = rt->mode == VV_KEYBOARD_SYMBOLS ? VV_KEYBOARD_SYMBOLS_MORE : VV_KEYBOARD_SYMBOLS;
        break;
    default: break;
    }
    vv_invalidate_object(v, object);
}

static void track_velocity(vv_press_t *p, int y, uint32_t now)
{
    if (p->samples == 4) {
        memmove(p->sample_y, p->sample_y + 1, 3 * sizeof(p->sample_y[0]));
        memmove(p->sample_ms, p->sample_ms + 1, 3 * sizeof(p->sample_ms[0]));
        p->samples = 3;
    }
    p->sample_y[p->samples] = (int16_t)y;
    p->sample_ms[p->samples] = now;
    ++p->samples;
}

static void pointer(vv_view_t *v, bool pressed, int x, int y)
{
    vv_press_t *p = &v->press;
    if (pressed && !p->down) {
        memset(p, 0, sizeof(*p));
        p->down = true;
        p->key = -1;
        p->x = p->start_x = (int16_t)x;
        p->y = p->start_y = (int16_t)y;
        hit_test(v, x, y);
        track_velocity(p, y, v->now);
        invalidate_press(v);
        return;
    }
    if (!p->down) return;
    p->x = (int16_t)x;
    p->y = (int16_t)y;
    if (pressed) {
        track_velocity(p, y, v->now);
        const int dy = y - p->start_y, dx = x - p->start_x;
        if ((p->kind == VV_PRESS_ROW || p->kind == VV_PRESS_LIST) && !p->dragging &&
            (dy > VV_DRAG_START_PX || dy < -VV_DRAG_START_PX)) {
            p->dragging = true;
        }
        if (p->dragging) {
            vv_list_rt_t *rt = &v->lists[p->list];
            int32_t scroll = p->start_scroll - dy;
            const int32_t max = vv_list_max_scroll(v, p->list);
            scroll = scroll < 0 ? 0 : scroll > max ? max : scroll;
            if (scroll != rt->scroll) rt->scroll = scroll;
            invalidate_press(v);
        } else if (p->kind == VV_PRESS_BUTTON || p->kind == VV_PRESS_KEY) {
            const vv_object_def_t *o = obj(v, p->object);
            const bool inside = p->kind == VV_PRESS_KEY ?
                vv_keyboard_hit(v, (uint8_t)o->ref, x, y) == p->key : contains(o, x, y);
            if (!inside && !p->cancelled) {
                p->cancelled = true;
                invalidate_press(v);
            }
        } else if (p->kind == VV_PRESS_ROW && (dx > VV_DRAG_START_PX || dx < -VV_DRAG_START_PX)) {
            p->cancelled = true;
            invalidate_press(v);
        }
        return;
    }
    /* Release. */
    p->down = false;
    invalidate_press(v);
    if (p->dragging) {
        vv_list_rt_t *rt = &v->lists[p->list];
        int32_t velocity = 0;
        if (p->samples >= 2) {
            const uint32_t span = p->sample_ms[p->samples - 1] - p->sample_ms[0];
            if (span > 0 && span < 200)
                velocity = (int32_t)(p->sample_y[0] - p->sample_y[p->samples - 1]) * 1000 / (int32_t)span;
        }
        if (velocity > COAST_MIN_SPEED || velocity < -COAST_MIN_SPEED) {
            rt->velocity = velocity;
            rt->coast_ms = v->now;
            rt->coasting = true;
        }
        return;
    }
    if (p->cancelled) return;
    switch (p->kind) {
    case VV_PRESS_BUTTON: emit(v, obj(v, p->object)->action, VV_LIST_NONE, 0, 0); break;
    case VV_PRESS_ROW: {
        const vv_template_def_t *t = &v->scene->templates[v->scene->lists[p->list].tmpl];
        emit(v, t->action, p->list, (uint32_t)p->item, 0);
        break;
    }
    case VV_PRESS_KEY: press_keyboard_key(v, p->object); break;
    default: break;
    }
}

void vv_touch_sample(vv_view_t *v, bool pressed, int x, int y)
{
    if (v && x >= 0 && y >= 0 && x < v->width && y < v->height) pointer(v, pressed, x, y);
    else if (v && !pressed) pointer(v, false, v->press.x, v->press.y);
}

static void coast(vv_view_t *v)
{
    for (uint8_t i = 0; i < v->scene->list_count; ++i) {
        vv_list_rt_t *rt = &v->lists[i];
        if (!rt->coasting) continue;
        uint32_t dt = v->now - rt->coast_ms;
        if (dt == 0) continue;
        if (dt > 100) dt = 100;
        rt->coast_ms = v->now;
        const int32_t max = vv_list_max_scroll(v, i);
        int32_t scroll = rt->scroll + (int32_t)((int64_t)rt->velocity * (int64_t)dt / 1000);
        rt->velocity -= (int32_t)((int64_t)rt->velocity * (int64_t)dt / COAST_DECAY_MS);
        if (scroll <= 0 || scroll >= max) {
            scroll = scroll <= 0 ? 0 : max;
            rt->coasting = false;
        }
        if (rt->velocity < COAST_MIN_SPEED && rt->velocity > -COAST_MIN_SPEED) rt->coasting = false;
        if (scroll != rt->scroll) {
            rt->scroll = scroll;
            vv_invalidate_object(v, v->scene->lists[i].object);
        }
    }
}

static void run_timers(vv_view_t *v)
{
    for (int i = 0; i < VV_MAX_TIMERS; ++i) {
        lock(v);
        vv_timer_t *t = &v->timers[i];
        const bool due = t->active && (int32_t)(v->now - t->due) >= 0;
        const vv_timer_cb_t callback = t->callback;
        void *ctx = t->ctx;
        if (due) {
            t->due += t->period;
            if ((int32_t)(v->now - t->due) >= 0) t->due = v->now + t->period; /* Do not replay a stall. */
        }
        unlock(v);
        /* A callback may delete or replace timers, including its own. */
        if (due && callback) callback(v, ctx);
    }
}

void vv_process(vv_view_t *v, uint32_t now_ms)
{
    if (!v) return;
    if (!v->time_valid) {
        /* Timers created before the first frame count from now. */
        lock(v);
        for (int i = 0; i < VV_MAX_TIMERS; ++i) {
            if (v->timers[i].active) v->timers[i].due = now_ms + v->timers[i].period;
        }
        unlock(v);
        v->time_valid = true;
    }
    v->now = now_ms;
    for (;;) {
        vv_input_t input;
        bool have = false;
        lock(v);
        if (v->queue_count) {
            input = v->queue[v->queue_head];
            v->queue_head = (uint8_t)((v->queue_head + 1) % VV_INPUT_QUEUE);
            --v->queue_count;
            have = true;
        }
        unlock(v);
        if (!have) break;
        pointer(v, input.pressed, input.x, input.y);
    }
    coast(v);
    run_timers(v);
}

bool vv_is_animating(const vv_view_t *v)
{
    if (!v) return false;
    if (v->press.down || v->queue_count) return true;
    for (uint8_t i = 0; i < v->scene->list_count; ++i) {
        if (v->lists[i].coasting) return true;
    }
    return false;
}

size_t vv_render(vv_view_t *v, vv_rect_t *rects, size_t capacity)
{
    if (!v) return 0;
    for (uint8_t i = 0; i < v->scene->list_count; ++i) vv_list_bind_rows(v, i);
    if (!v->dirty_count) return 0;
    if (rects && capacity && v->dirty_count > capacity) {
        for (uint8_t i = 1; i < v->dirty_count; ++i) merge(&v->dirty[0], &v->dirty[i]);
        v->dirty_count = 1;
    }
    const uint8_t count = v->dirty_count;
    vv_rect_t painted[VV_MAX_DIRTY];
    memcpy(painted, v->dirty, count * sizeof(painted[0]));
    v->dirty_count = 0;
    for (uint8_t i = 0; i < count; ++i) vv_paint(v, &painted[i]);
    if (rects) memcpy(rects, painted, (count < capacity ? count : capacity) * sizeof(painted[0]));
    return count;
}
