// SPDX-License-Identifier: Apache-2.0
/* Native Vibe View simulator: the production scene, renderer and controller
 * driven by line commands on stdin with simulated time. Every command answers
 * one line on stdout; diagnostics go to stderr.
 *
 *   wait N                 advance N frames of 16 ms
 *   tap X Y                press and release at X,Y
 *   press X Y | move X Y | release
 *   screenshot ppm|png PATH
 *   state                  scenario state as JSON
 *   text BIND              current text of a bound label, as displayed
 *   control COMMAND...     scenario control, e.g. "control open-bridge"
 *   quit
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "platform_pc.h"
#include "vibe_scene.h"
#include "vv_internal.h"

#define FRAME_MS 16u

extern const unsigned char vibe_assets_data[];
extern const size_t vibe_assets_data_size;

static uint16_t s_framebuffer[480 * 480];
static vv_view_t *s_view;
static uint32_t s_now = 1000;
static unsigned long s_frames;
static int s_last_x, s_last_y;

static void frame(void)
{
    s_now += FRAME_MS;
    vv_process(s_view, s_now);
    vv_rect_t rects[4];
    (void)vv_render(s_view, rects, 4);
    ++s_frames;
}

static void rgb888(uint16_t c, unsigned char out[3])
{
    const unsigned r = c >> 11, g = (c >> 5) & 0x3F, b = c & 0x1F;
    out[0] = (unsigned char)((r << 3) | (r >> 2));
    out[1] = (unsigned char)((g << 2) | (g >> 4));
    out[2] = (unsigned char)((b << 3) | (b >> 2));
}

static void put_be32(FILE *f, uint32_t v)
{
    const unsigned char b[4] = {(unsigned char)(v >> 24), (unsigned char)(v >> 16),
                                (unsigned char)(v >> 8), (unsigned char)v};
    fwrite(b, 1, 4, f);
}

static void chunk(FILE *f, const char *type, const unsigned char *data, size_t size)
{
    unsigned char *buffer = malloc(size + 4);
    if (!buffer) return;
    memcpy(buffer, type, 4);
    if (size) memcpy(buffer + 4, data, size);
    put_be32(f, (uint32_t)size);
    fwrite(buffer, 1, size + 4, f);
    put_be32(f, vv_crc32(buffer, size + 4));
    free(buffer);
}

/* Uncompressed (stored) Deflate keeps the encoder trivial and exact. */
static int write_png(const char *path, const unsigned char *rgb, unsigned w, unsigned h)
{
    const size_t raw_size = (size_t)(w * 3 + 1) * h;
    const size_t blocks = (raw_size + 65534) / 65535;
    unsigned char *z = malloc(2 + raw_size + blocks * 5 + 4), *raw = malloc(raw_size);
    FILE *f = fopen(path, "wb");
    if (!z || !raw || !f) {
        free(z); free(raw);
        if (f) fclose(f);
        return -1;
    }
    for (unsigned y = 0; y < h; ++y) {
        raw[y * (w * 3 + 1)] = 0;
        memcpy(raw + y * (w * 3 + 1) + 1, rgb + (size_t)y * w * 3, w * 3);
    }
    size_t n = 0;
    z[n++] = 0x78;
    z[n++] = 0x01;
    uint32_t a = 1, b = 0;
    for (size_t offset = 0; offset < raw_size;) {
        const size_t len = raw_size - offset > 65535 ? 65535 : raw_size - offset;
        z[n++] = offset + len == raw_size;
        z[n++] = (unsigned char)len;
        z[n++] = (unsigned char)(len >> 8);
        z[n++] = (unsigned char)~len;
        z[n++] = (unsigned char)(~len >> 8);
        memcpy(z + n, raw + offset, len);
        for (size_t i = 0; i < len; ++i) {
            a = (a + raw[offset + i]) % 65521;
            b = (b + a) % 65521;
        }
        n += len;
        offset += len;
    }
    const uint32_t adler = (b << 16) | a;
    z[n++] = (unsigned char)(adler >> 24);
    z[n++] = (unsigned char)(adler >> 16);
    z[n++] = (unsigned char)(adler >> 8);
    z[n++] = (unsigned char)adler;
    static const unsigned char signature[8] = {137, 80, 78, 71, 13, 10, 26, 10};
    unsigned char ihdr[13] = {0};
    ihdr[0] = (unsigned char)(w >> 24); ihdr[1] = (unsigned char)(w >> 16);
    ihdr[2] = (unsigned char)(w >> 8); ihdr[3] = (unsigned char)w;
    ihdr[4] = (unsigned char)(h >> 24); ihdr[5] = (unsigned char)(h >> 16);
    ihdr[6] = (unsigned char)(h >> 8); ihdr[7] = (unsigned char)h;
    ihdr[8] = 8; /* Bit depth. */
    ihdr[9] = 2; /* RGB. */
    fwrite(signature, 1, sizeof(signature), f);
    chunk(f, "IHDR", ihdr, sizeof(ihdr));
    chunk(f, "IDAT", z, n);
    chunk(f, "IEND", NULL, 0);
    const int err = ferror(f);
    fclose(f);
    free(z);
    free(raw);
    return err ? -1 : 0;
}

static int screenshot(const char *format, const char *path)
{
    const unsigned w = vv_width(s_view), h = vv_height(s_view);
    unsigned char *rgb = malloc((size_t)w * h * 3);
    if (!rgb) return -1;
    for (size_t i = 0; i < (size_t)w * h; ++i) rgb888(s_framebuffer[i], rgb + i * 3);
    int err = -1;
    if (!strcmp(format, "png")) {
        err = write_png(path, rgb, w, h);
    } else if (!strcmp(format, "ppm")) {
        FILE *f = fopen(path, "wb");
        if (f) {
            fprintf(f, "P6\n%u %u\n255\n", w, h);
            fwrite(rgb, 1, (size_t)w * h * 3, f);
            err = ferror(f) ? -1 : 0;
            fclose(f);
        }
    }
    free(rgb);
    return err;
}

static void reply(const char *text)
{
    fputs(text, stdout);
    fputc('\n', stdout);
    fflush(stdout);
}

int main(void)
{
    /* Copy the embedded blob into aligned storage, as the device decompresses
     * it into an aligned PSRAM buffer. */
    uint32_t *assets = malloc(vibe_assets_data_size + 4);
    if (!assets) return 1;
    memcpy(assets, vibe_assets_data, vibe_assets_data_size);
    const vv_config_t config = {
        .scene = &vibe_scene,
        .assets = assets,
        .assets_size = vibe_assets_data_size,
        .framebuffer = s_framebuffer,
    };
    if (vv_create(&config, &s_view) != VV_OK) {
        fprintf(stderr, "vibe_sim: invalid scene assets\n");
        return 1;
    }
    vv_process(s_view, s_now);
    if (vibe_sim_init(s_view) != VV_OK) {
        fprintf(stderr, "vibe_sim: controller initialization failed\n");
        return 1;
    }
    frame();
    reply("ready");
    char line[512];
    while (fgets(line, sizeof(line), stdin)) {
        line[strcspn(line, "\r\n")] = 0;
        char word[16] = {0}, arg[16] = {0};
        int x = 0, y = 0, count = 0, offset = 0;
        if (sscanf(line, "%15s%n", word, &offset) != 1) continue;
        const char *rest = line + offset + (line[offset] == ' ');
        if (!strcmp(word, "wait") && sscanf(rest, "%d", &count) == 1 && count >= 0) {
            while (count--) frame();
            reply("ok");
        } else if (!strcmp(word, "tap") && sscanf(rest, "%d %d", &x, &y) == 2) {
            vv_inject_touch(s_view, x, y, true);
            vv_inject_touch(s_view, x, y, false);
            reply("ok");
        } else if ((!strcmp(word, "press") || !strcmp(word, "move")) &&
                   sscanf(rest, "%d %d", &x, &y) == 2) {
            s_last_x = x;
            s_last_y = y;
            reply(vv_inject_touch(s_view, x, y, true) == VV_OK ? "ok" : "error invalid point");
        } else if (!strcmp(word, "release")) {
            reply(vv_inject_touch(s_view, s_last_x, s_last_y, false) == VV_OK ? "ok" : "error queue full");
        } else if (!strcmp(word, "screenshot") && sscanf(rest, "%15s%n", arg, &offset) == 1) {
            const char *path = rest + offset + (rest[offset] == ' ');
            reply(*path && screenshot(arg, path) == 0 ? "ok" : "error screenshot failed");
        } else if (!strcmp(word, "state")) {
            char json[1024];
            vibe_sim_state(json, sizeof(json));
            reply(json);
        } else if (!strcmp(word, "text") && sscanf(rest, "%d", &count) == 1 &&
                   count >= 0 && count < vibe_scene.bind_count) {
            const uint16_t object = vibe_scene.bind_objects[count];
            const vv_object_def_t *o = &vibe_scene.objects[object];
            const char *text = s_view->texts[object] && s_view->texts[object][0] ? s_view->texts[object] :
                o->text != VV_NONE ? vibe_scene.strings[o->text] : "";
            reply(text);
        } else if (!strcmp(word, "control")) {
            vibe_sim_control(rest);
            reply("ok");
        } else if (!strcmp(word, "frames")) {
            char text[32];
            snprintf(text, sizeof(text), "%lu", s_frames);
            reply(text);
        } else if (!strcmp(word, "quit")) {
            reply("ok");
            break;
        } else {
            reply("error unknown command");
        }
    }
    vibe_sim_deinit();
    vv_destroy(s_view);
    free(assets);
    return 0;
}
