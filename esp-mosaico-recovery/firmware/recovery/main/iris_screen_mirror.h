// SPDX-License-Identifier: Apache-2.0

#pragma once

#include "esp_err.h"
#include "vibe_view.h"

/** Register the ESP-Iris screen backend before the UI starts. */
esp_err_t iris_screen_mirror_init(void);

/** Attach the running UI. Capture waits until its first frame is on the panel. */
esp_err_t iris_screen_mirror_attach(vv_view_t *ui);
