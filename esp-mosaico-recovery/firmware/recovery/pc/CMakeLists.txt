cmake_minimum_required(VERSION 3.16)
project(vibe_sim LANGUAGES C)

# Native simulator for the production Vibe Mode scene and controller. It needs
# only a C compiler: the scene tables and asset blob are committed outputs of
# tools/gen_vibe_view.py.
set(RECOVERY "${CMAKE_CURRENT_LIST_DIR}/..")
set(VIEW "${RECOVERY}/components/vibe_view")
set(GENERATED "${RECOVERY}/ui/generated")

set(assets "${GENERATED}/vibe_assets.bin")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${assets}")
file(READ "${assets}" assets_hex HEX)
file(SIZE "${assets}" assets_size)
string(REGEX REPLACE "([0-9a-f][0-9a-f])" "0x\\1," assets_bytes "${assets_hex}")
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/vibe_assets_data.c"
    "/* Generated from ui/generated/vibe_assets.bin by pc/CMakeLists.txt. */\n"
    "#include <stddef.h>\n"
    "const size_t vibe_assets_data_size = ${assets_size};\n"
    "const unsigned char vibe_assets_data[] = {${assets_bytes}};\n")

add_executable(vibe_sim
    sim_main.c
    platform_pc.c
    "${RECOVERY}/main/vibe_ui.c"
    "${RECOVERY}/main/vibe_transfer.c"
    "${VIEW}/vv_assets.c"
    "${VIEW}/vv_core.c"
    "${VIEW}/vv_keyboard.c"
    "${VIEW}/vv_render.c"
    "${GENERATED}/vibe_scene.c"
    "${CMAKE_CURRENT_BINARY_DIR}/vibe_assets_data.c")
target_include_directories(vibe_sim PRIVATE
    "${CMAKE_CURRENT_LIST_DIR}" "${RECOVERY}/main" "${VIEW}/include" "${VIEW}" "${GENERATED}")
target_compile_definitions(vibe_sim PRIVATE VIBE_UI_TRACE=1)
set_target_properties(vibe_sim PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED ON)
if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(vibe_sim PRIVATE -Wall -Wextra -Werror -Wno-unused-parameter)
endif()
