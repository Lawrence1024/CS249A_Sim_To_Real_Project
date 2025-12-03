#include "pico/stdlib.h"
#include "hardware/uart.h"
#include "hardware/gpio.h"
#include "hardware/pwm.h"
#include <stdio.h>  

#define UART_ID        uart0
#define UART_TX_PIN    28
#define UART_RX_PIN    29
#define UART_BAUD      9600

#define R_DIR_PIN      10
#define L_DIR_PIN      11
#define R_PWM_PIN      14
#define L_PWM_PIN      15

static uint slice7;

static void pwm_init_20k_on_pin(uint pin){
    gpio_set_function(pin, GPIO_FUNC_PWM);
    uint slice = pwm_gpio_to_slice_num(pin);
    pwm_config cfg = pwm_get_default_config();
    pwm_config_set_clkdiv(&cfg, 1.0f);
    pwm_config_set_wrap(&cfg, 6249);
    pwm_init(slice, &cfg, true);
    pwm_set_chan_level(slice, pwm_gpio_to_channel(pin), 0);
    slice7 = slice;
}

static inline void set_motor_speed(int l_pct, int r_pct){
    gpio_set_function(25, 0);
    if (l_pct>100) l_pct=100; if (l_pct<-100) l_pct=-100;
    if (r_pct>100) r_pct=100; if (r_pct<-100) r_pct=-100;
    gpio_put(L_DIR_PIN, l_pct>=0);
    gpio_put(R_DIR_PIN, r_pct>=0);
    uint16_t top = pwm_hw->slice[slice7].top;
    uint16_t ll = (uint16_t)(top * (l_pct>=0 ? l_pct : -l_pct) / 100);
    uint16_t rl = (uint16_t)(top * (r_pct>=0 ? r_pct : -r_pct) / 100);
    pwm_set_chan_level(pwm_gpio_to_slice_num(L_PWM_PIN), pwm_gpio_to_channel(L_PWM_PIN), ll);
    pwm_set_chan_level(pwm_gpio_to_slice_num(R_PWM_PIN), pwm_gpio_to_channel(R_PWM_PIN), rl);
}

int main(void){
    stdio_init_all();     // initialize USB serial (if CMake open USB stdio)
    printf("Ready for commands\n");  // debug hint

    gpio_init(R_DIR_PIN); gpio_set_dir(R_DIR_PIN, GPIO_OUT); gpio_put(R_DIR_PIN, 0);
    gpio_init(L_DIR_PIN); gpio_set_dir(L_DIR_PIN, GPIO_OUT); gpio_put(L_DIR_PIN, 0);

    pwm_init_20k_on_pin(R_PWM_PIN);
    pwm_init_20k_on_pin(L_PWM_PIN);
    set_motor_speed(0, 0);

    uart_init(UART_ID, UART_BAUD);
    gpio_set_function(UART_TX_PIN, GPIO_FUNC_UART);
    gpio_set_function(UART_RX_PIN, GPIO_FUNC_UART);
    uart_set_format(UART_ID, 8, 1, UART_PARITY_NONE);
    uart_set_fifo_enabled(UART_ID, true);

    while (true){
        printf("Waiting for command...\n");
        if (uart_is_readable(UART_ID)){
            printf("UART is readable\n");
            uint8_t c = uart_getc(UART_ID);
            printf("Received char: %c (0x%02X)\n", c, c);  // print received char
            switch (c){
                case 'F':
                    set_motor_speed(+20, +20);
                    printf("Command F → forward\n");
                    break;
                case 'B':
                    set_motor_speed(-20, -20);
                    printf("Command B → backward\n");
                    break;
                case 'S':
                    set_motor_speed(0, 0);
                    printf("Command S → stop\n");
                    break;
                default:
                    printf("Unknown command: 0x%02X\n", c);
                    break;
            }
            uart_putc(UART_ID, c); // echo to HM-10 (optional)
        }
        tight_loop_contents();
    }
}
