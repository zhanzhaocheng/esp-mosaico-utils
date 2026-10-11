#pragma once

#include "esp_err.h"
#include "vibe_view.h"

/* Attach the Gateway's pointer RPC to the Vibe View display over USB. */
esp_err_t factory_ui_input_register(void);

/* Internal display handle shared by the input adapter. */
vv_view_t *factory_ui_handle(void);
