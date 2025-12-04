#include "pico/stdlib.h"
#include "hardware/uart.h"
#include "hardware/gpio.h"
#include "hardware/pwm.h"
#include <stdio.h>  
#include <math.h>
#include <string.h> // Required for memcpy

// --- Configuration ---
#define PACKET_SIZE    9      // Size of command: [c, f, f] = 9 bytes
#define HEADER_CHAR    'A'    // Expected command header from PC

#define UART_ID        uart0
#define UART_TX_PIN    28
#define UART_RX_PIN    29
#define UART_BAUD      9600

#define R_DIR_PIN      10
#define L_DIR_PIN      11
#define R_PWM_PIN      14
#define L_PWM_PIN      15

// coefficients for left motor
float l_coeff_a = 1.37f;
float l_coeff_b = -100.5f;
float r_coeff_a = 1.37f;
float r_coeff_b = -100.0f;

inline float speed_to_pwm(float speed, float a, float b){
    return a * speed + b;
}

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
    gpio_put(L_DIR_PIN, l_pct<=0);
    gpio_put(R_DIR_PIN, r_pct<=0);
    uint16_t top = pwm_hw->slice[slice7].top;
    uint16_t ll = (uint16_t)(top * (l_pct>=0 ? l_pct : -l_pct) / 100);
    uint16_t rl = (uint16_t)(top * (r_pct>=0 ? r_pct : -r_pct) / 100);
    pwm_set_chan_level(pwm_gpio_to_slice_num(L_PWM_PIN), pwm_gpio_to_channel(L_PWM_PIN), ll);
    pwm_set_chan_level(pwm_gpio_to_slice_num(R_PWM_PIN), pwm_gpio_to_channel(R_PWM_PIN), rl);
}


// --- FSM Definitions ---
typedef enum {
    STATE_WAIT_FOR_HEADER,
    STATE_READ_FLOAT_PAYLOAD,
    STATE_PROCESS_COMMAND
} command_state_t;

static command_state_t current_state = STATE_WAIT_FOR_HEADER;
static uint8_t packet_buffer[PACKET_SIZE];
static uint8_t byte_count = 0;

static void parse_uart_fsm(uint8_t rx_byte) {
    
    switch (current_state) {

        case STATE_WAIT_FOR_HEADER:
            byte_count = 0; // Always reset counter
            if (rx_byte == HEADER_CHAR) {
                packet_buffer[byte_count++] = rx_byte; // Store header byte
                current_state = STATE_READ_FLOAT_PAYLOAD;
            } else {
                // Ignore noise or stay in this state
                // printf("FSM: Waiting for '%c', received 0x%02X\n", HEADER_CHAR, rx_byte);
            }
            break;

        case STATE_READ_FLOAT_PAYLOAD:
            // Read the remaining 8 bytes (the two floats)
            packet_buffer[byte_count++] = rx_byte;
            if (byte_count == PACKET_SIZE) {
                current_state = STATE_PROCESS_COMMAND;
            }
            break;

        case STATE_PROCESS_COMMAND:
            // Should be handled by the main loop immediately after state change.
            // If a byte arrives here, it's likely the start of the NEXT packet.
            // Go back to WAITING for the header. The main loop will process the command.
            current_state = STATE_WAIT_FOR_HEADER;
            byte_count = 0;
            break;
    }
}


static void process_complete_command(void) {
    // Buffer indices: [0:Header][1-4:L_float][5-8:R_float]
    float l_rads_cmd;
    float r_rads_cmd;

    // 1. Unpack the floats (Safe via memcpy)
    memcpy(&l_rads_cmd, packet_buffer + 1, sizeof(float)); 
    memcpy(&r_rads_cmd, packet_buffer + 1 + sizeof(float), sizeof(float)); 

    // 2. Separate Direction from Speed
    // Remember the requested direction
    bool l_is_reverse = (l_rads_cmd < 0);
    bool r_is_reverse = (r_rads_cmd < 0);

    // Work only with positive magnitudes for the formula
    float l_speed_mag = fabsf(l_rads_cmd);
    float r_speed_mag = fabsf(r_rads_cmd);

    // 3. Apply your coefficients
    // Example: If speed is 0 -> (1.37 * 0) - 100 = -100.
    float l_pwm_calc = speed_to_pwm(l_speed_mag, l_coeff_a, l_coeff_b);
    float r_pwm_calc = speed_to_pwm(r_speed_mag, r_coeff_a, r_coeff_b);

    // 4. CRITICAL FIX: Clamp negative results to 0
    // If the linear fit result is negative (e.g. -100), it means "Don't Move", 
    // NOT "Move Fast in Reverse".
    if (l_pwm_calc < 0) l_pwm_calc = 0;
    if (r_pwm_calc < 0) r_pwm_calc = 0;

    // 5. Re-apply the direction sign for set_motor_speed
    // We cast to int because set_motor_speed expects integer % (-100 to 100)
    int l_pct = (int)l_pwm_calc;
    int r_pct = (int)r_pwm_calc;

    if (l_is_reverse) l_pct = -l_pct;
    if (r_is_reverse) r_pct = -r_pct;

    // 6. Execute
    set_motor_speed(l_pct, r_pct);
    
    // Reset FSM
    current_state = STATE_WAIT_FOR_HEADER;
    byte_count = 0;
}

int main(void){
    stdio_init_all();     // initialize USB serial (if CMake open USB stdio)
    //printf("Ready for commands\n");  // debug hint

    gpio_init(R_DIR_PIN); gpio_set_dir(R_DIR_PIN, GPIO_OUT); gpio_put(R_DIR_PIN, 0);
    gpio_init(L_DIR_PIN); gpio_set_dir(L_DIR_PIN, GPIO_OUT); gpio_put(L_DIR_PIN, 0);

    pwm_init_20k_on_pin(R_PWM_PIN);
    pwm_init_20k_on_pin(L_PWM_PIN);
    set_motor_speed(0, 0);

    current_state = STATE_WAIT_FOR_HEADER;
    byte_count = 0;

    uart_init(UART_ID, UART_BAUD);
    gpio_set_function(UART_TX_PIN, GPIO_FUNC_UART);
    gpio_set_function(UART_RX_PIN, GPIO_FUNC_UART);
    uart_set_format(UART_ID, 8, 1, UART_PARITY_NONE);
    uart_set_fifo_enabled(UART_ID, true);

    //printf("FSM Ready: Waiting for '%c' header byte (9-byte packet).\n", HEADER_CHAR);

    while (true){
        // 1. Check for incoming data
        if (uart_is_readable(UART_ID)){
            uint8_t c = uart_getc(UART_ID);
            parse_uart_fsm(c);
        }

        // 2. Process complete command outside the FSM function
        if (current_state == STATE_PROCESS_COMMAND){
            process_complete_command();
        }
        
        tight_loop_contents();
    }
}