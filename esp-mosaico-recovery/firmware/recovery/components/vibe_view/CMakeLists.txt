# Portable core plus the ESP-IDF panel port. pc/CMakeLists.txt builds the core
# natively for the simulator without this file.
idf_component_register(
    SRCS "vv_assets.c" "vv_core.c" "vv_keyboard.c" "vv_render.c" "vv_port_esp.c"
    INCLUDE_DIRS "include"
    REQUIRES esp_lcd
    PRIV_REQUIRES esp_driver_gpio esp_timer freertos heap log
)
