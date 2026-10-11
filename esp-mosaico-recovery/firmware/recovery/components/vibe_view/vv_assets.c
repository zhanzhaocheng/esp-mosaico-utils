// SPDX-License-Identifier: Apache-2.0
#include <string.h>
#include "vv_internal.h"

uint32_t vv_crc32(const uint8_t *data, size_t size)
{
    static const uint32_t nibble[16] = {
        0x00000000, 0x1DB71064, 0x3B6E20C8, 0x26D930AC, 0x76DC4190, 0x6B6B51F4, 0x4DB26158, 0x5005713C,
        0xEDB88320, 0xF00F9344, 0xD6D6A3E8, 0xCB61B38C, 0x9B64C2B0, 0x86D3D2D4, 0xA00AE278, 0xBDBDF21C,
    };
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < size; ++i) {
        crc ^= data[i];
        crc = (crc >> 4) ^ nibble[crc & 15];
        crc = (crc >> 4) ^ nibble[crc & 15];
    }
    return ~crc;
}

static bool in_blob(uint32_t offset, size_t length, size_t size)
{
    return offset <= size && length <= size - offset && (offset & 3) == 0;
}

vv_err_t vv_assets_load(vv_view_t *view, const void *assets, size_t size)
{
    const uint8_t *blob = assets;
    const vv_assets_header_t *header = assets;
    if (!blob || ((uintptr_t)blob & 3) || size < sizeof(*header) ||
        memcmp(header->magic, VV_ASSETS_MAGIC, 4) != 0 || header->version != VV_ASSETS_VERSION ||
        header->total_size > size || header->font_count > VV_MAX_FONTS ||
        header->image_count > VV_MAX_IMAGES)
        return VV_ERR_INVALID_ARG;
    size = header->total_size;
    if (vv_crc32(blob + sizeof(*header), size - sizeof(*header)) != header->crc32 ||
        header->crc32 != view->scene->assets_crc32 ||
        !in_blob(header->fonts_offset, 4u * header->font_count, size) ||
        !in_blob(header->images_offset, 4u * header->image_count, size))
        return VV_ERR_INVALID_ARG;
    const uint32_t *font_offsets = (const uint32_t *)(blob + header->fonts_offset);
    for (uint16_t i = 0; i < header->font_count; ++i) {
        if (!in_blob(font_offsets[i], sizeof(vv_font_t), size)) return VV_ERR_INVALID_ARG;
        const vv_font_t *font = (const vv_font_t *)(blob + font_offsets[i]);
        if (!in_blob(font->glyphs_offset, (size_t)font->glyph_count * sizeof(vv_glyph_t), size) ||
            font->bitmap_offset > size)
            return VV_ERR_INVALID_ARG;
        const vv_glyph_t *glyphs = (const vv_glyph_t *)(blob + font->glyphs_offset);
        for (uint16_t g = 0; g < font->glyph_count; ++g) {
            const size_t bytes = (size_t)(glyphs[g].width + 1) / 2 * glyphs[g].height;
            if (glyphs[g].bitmap > size - font->bitmap_offset ||
                bytes > size - font->bitmap_offset - glyphs[g].bitmap ||
                (g && glyphs[g].codepoint <= glyphs[g - 1].codepoint))
                return VV_ERR_INVALID_ARG;
        }
        view->fonts[i] = (vv_font_rt_t){font, glyphs, blob + font->bitmap_offset};
    }
    const uint32_t *image_offsets = (const uint32_t *)(blob + header->images_offset);
    for (uint16_t i = 0; i < header->image_count; ++i) {
        if (!in_blob(image_offsets[i], sizeof(vv_image_t), size)) return VV_ERR_INVALID_ARG;
        const vv_image_t *image = (const vv_image_t *)(blob + image_offsets[i]);
        const size_t row = image->format == VV_IMAGE_L1 ? (image->width + 7u) / 8u : image->width;
        if ((image->format != VV_IMAGE_L1 && image->format != VV_IMAGE_A8) ||
            image->data_offset > size || image->data_size > size - image->data_offset ||
            row * image->height > image->data_size)
            return VV_ERR_INVALID_ARG;
        view->images[i] = (vv_image_rt_t){image, blob + image->data_offset};
    }
    view->font_count = (uint8_t)header->font_count;
    view->image_count = (uint8_t)header->image_count;
    view->assets = blob;
    return VV_OK;
}

const vv_glyph_t *vv_glyph(const vv_font_rt_t *font, uint32_t codepoint)
{
    size_t low = 0, high = font->header->glyph_count;
    while (low < high) {
        const size_t mid = (low + high) / 2;
        const uint32_t value = font->glyphs[mid].codepoint;
        if (value == codepoint) return &font->glyphs[mid];
        if (value < codepoint) low = mid + 1;
        else high = mid;
    }
    return NULL;
}
