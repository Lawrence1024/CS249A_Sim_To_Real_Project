cmake_minimum_required(VERSION 3.13)

# Pico SDK
set(PICO_SDK_PATH "${CMAKE_CURRENT_LIST_DIR}/pico-sdk")

if (DEFINED ENV{PICO_SDK_PATH})
  include("$ENV{PICO_SDK_PATH}/pico_sdk_init.cmake")
else ()
  include("${CMAKE_CURRENT_LIST_DIR}/pico-sdk/pico_sdk_init.cmake")
endif()


project(249A_project C CXX ASM)
add_compile_options(-Wall -Wextra)
pico_sdk_init()

# Optional: add Pololu library once (needed only for motor/sensor programs)
add_subdirectory(${CMAKE_CURRENT_LIST_DIR}/pololu-3pi-2040-robot/c/pololu_3pi_2040_robot)

# -------------------------
# Test Program 1: bare-metal blink
# -------------------------
add_executable(blink src/blink.c)
pico_add_extra_outputs(blink)
pico_enable_stdio_usb(blink 1)
pico_enable_stdio_uart(blink 0)
target_link_libraries(blink pico_stdlib pololu_3pi_2040_robot)

# -------------------------
# Test Program 2: test motors (needs Pololu library)
# -------------------------
add_executable(test_motors src/motors_test.c)
pico_add_extra_outputs(test_motors)
target_link_libraries(test_motors pico_stdlib pololu_3pi_2040_robot)

add_executable(test_bluetooth src/bluetooth_pololu.c)
pico_add_extra_outputs(test_bluetooth)
pico_enable_stdio_usb(test_bluetooth 1)
pico_enable_stdio_uart(test_bluetooth 0)
target_link_libraries(test_bluetooth pico_stdlib pololu_3pi_2040_robot)


