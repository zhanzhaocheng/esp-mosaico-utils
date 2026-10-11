// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <stddef.h>
#include "vibe_view.h"

/* Scenario model selected by VIBE_SIM_SCENARIO. All calls run on the
 * simulator's single UI thread. */
vv_err_t vibe_sim_init(vv_view_t *view);
void vibe_sim_deinit(void);
void vibe_sim_control(const char *command);
int vibe_sim_state(char *out, size_t size);
