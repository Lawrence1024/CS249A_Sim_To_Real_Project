cmake_minimum_required(VERSION 3.13)

# must import SDK before project()
include(${PICO_SDK_PATH}/external/pico_sdk_import.cmake)

project(pololu C CXX ASM)

pico_sdk_init()

add_executable(pololu
    bluetooth_pololu.c
)

target_link_libraries(pololu
    pico_stdlib
    hardware_uart
    hardware_pwm
    hardware_gpio
)
pico_enable_stdio_usb(pololu 1)
pico_enable_stdio_uart(pololu 0)
# if need USB CDC print, uncomment:
# pico_enable_stdio_usb(pololu 1)
# pico_enable_stdio_uart(pololu 0)

pico_add_extra_outputs(pololu)  # generate .uf2
