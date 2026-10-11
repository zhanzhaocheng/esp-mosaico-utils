// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <stddef.h>
#include "esp_err.h"

/** Decompress the embedded Vibe View assets into PSRAM. The buffer stays
 * allocated for the UI lifetime; vv_create() verifies its CRC and bounds. */
esp_err_t vibe_bundle_open(const void **assets, size_t *size);
