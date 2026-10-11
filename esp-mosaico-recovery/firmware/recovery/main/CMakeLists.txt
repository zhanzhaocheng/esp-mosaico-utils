idf_component_register(
    SRCS
        "main.c"
        "factory_bridge.c"
        "factory_recovery_control.c"
        "factory_nand_update.c"
        "factory_network.c"
        "factory_system_inventory.c"
        "factory_system_metadata.c"
        "factory_system_update.c"
        "factory_ui.c"
        "factory_ui_dispatch.c"
        "vibe_ui.c"
        "vibe_transfer.c"
        "vibe_bundle.c"
        "board_display.c"
        "factory_ui_input.c"
        "recovery_ota_support.c"
        "iris_screen_mirror.c"
        "../ui/generated/vibe_scene.c"
    INCLUDE_DIRS "." "../ui/generated" "../../../include"
    REQUIRES
        app_update
        bootloader_support
        esp_app_format
        esp_event
        esp_http_client
        esp_iris
        esp_mosaico_boot
        iris_bridge
        esp-mosaico-bsp
        esp_netif
        esp_partition
        esp_wifi
        freertos
        espressif__cjson
        lwip
        mdns
        mbedtls
        vibe_view
        esp_lcd
        esp_lcd_touch
        esp_timer
        nvs_flash
        spi_flash
)

# Recovery is self-contained: the scene tables and subset glyphs live in
# factory.bin. tools/gen_vibe_view.py writes ui/generated from ui/main.json;
# the build only compresses the committed asset blob, losslessly.
set(vibe_assets "${CMAKE_CURRENT_LIST_DIR}/../ui/generated/vibe_assets.bin")
idf_build_get_property(vibe_python PYTHON)
set(vibe_packed "${CMAKE_CURRENT_BINARY_DIR}/vibe_bundle_data.c")
add_custom_command(OUTPUT "${vibe_packed}"
    COMMAND "${vibe_python}" "${CMAKE_CURRENT_LIST_DIR}/../tools/pack_vibe_bundle.py"
        "${vibe_assets}" "${vibe_packed}"
    DEPENDS "${vibe_assets}"
        "${CMAKE_CURRENT_LIST_DIR}/../tools/pack_vibe_bundle.py"
    VERBATIM)
target_sources(${COMPONENT_LIB} PRIVATE "${vibe_packed}")
