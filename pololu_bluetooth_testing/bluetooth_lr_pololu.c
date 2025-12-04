#include "pico/stdlib.h"
#include "hardware/uart.h"
#include "hardware/gpio.h"
#include "hardware/pwm.h"
#include <stdio.h>
#include <math.h>
#include <string.h> // Required for memcpy

// --- Configuration ---
#define UART_ID        uart0
#define UART_TX_PIN    28
#define UART_RX_PIN    29
#define UART_BAUD      115200 
#define PACKET_SIZE    9      // Size of command: [c, f, f] = 9 bytes
#define HEADER_CHAR    'A'    // Expected command header from PC

// ... (Pin definitions R_DIR_PIN, L_DIR_PIN, R_PWM_PIN, L_PWM_PIN remain the same) ...
// ... (PWM Configuration and LUTs remain the same) ...

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

// --- Look-Up Table Interpolation (rads_to_pwm remains the same) ---
// ... (rads_to_pwm and set_motor_pwm_level function codes go here) ...


static void process_complete_command(void) {
    // Buffer indices: [0:Header][1-4:L_float][5-8:R_float]
    float l_rads_cmd;
    float r_rads_cmd;

    // Read Left float (4 bytes starting immediately after the 1-byte header at index 1)
    memcpy(&l_rads_cmd, packet_buffer + 1, sizeof(float)); 
    // Read Right float (4 bytes starting at index 5)
    memcpy(&r_rads_cmd, packet_buffer + 1 + sizeof(float), sizeof(float)); 

    // Determine direction and absolute speed
    bool l_dir = (l_rads_cmd >= 0.0f);
    bool r_dir = (r_rads_cmd >= 0.0f);
    float l_speed = fabsf(l_rads_cmd);
    float r_speed = fabsf(r_rads_cmd);

    // Convert rad/s to PWM level using LUTs and apply control
    int16_t l_level = (int16_t)rads_to_pwm(l_speed, LEFT_SPEED_RADS, LEFT_PWM_DUTY);
    int16_t r_level = (int16_t)rads_to_pwm(r_speed, RIGHT_SPEED_RADS, RIGHT_PWM_DUTY);

    set_motor_pwm_level(l_level, l_dir, r_level, r_dir);
    
    // Reset state after processing
    current_state = STATE_WAIT_FOR_HEADER;
    byte_count = 0;
    
    // Optional debug output:
    // printf("Processed: L(%.2f), R(%.2f)\n", l_rads_cmd, r_rads_cmd);
}

int main(void){
    // ... (All initialization code: stdio, GPIO, PWM, UART setup) ...

    printf("FSM Ready: Waiting for '%c' header byte (9-byte packet).\n", HEADER_CHAR);

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