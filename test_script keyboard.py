import asyncio
from mocap.mocap_estimator import *
from pololu_bluetooth_testing.pololu_ble import *
from pynput import keyboard # Library for non-blocking keyboard input

# --- Global Control State ---
# These are updated by the keyboard thread and read by the main async loop
current_left_speed = 0.0
current_right_speed = 0.0

# Define your speed intensity
SPEED_VAL = 100.0 

def on_press(key):
    global current_left_speed, current_right_speed
    try:
        # Check for specific characters
        if hasattr(key, 'char'):
            if key.char == 'w': # Forward
                current_left_speed = SPEED_VAL
                current_right_speed = SPEED_VAL
            elif key.char == 's': # Backward
                current_left_speed = -SPEED_VAL
                current_right_speed = -SPEED_VAL
            elif key.char == 'a': # Turn Left (Pivot)
                current_left_speed = -SPEED_VAL
                current_right_speed = SPEED_VAL
            elif key.char == 'd': # Turn Right (Pivot)
                current_left_speed = SPEED_VAL
                current_right_speed = -SPEED_VAL
    except AttributeError:
        pass

def on_release(key):
    global current_left_speed, current_right_speed
    # Stop the robot when the key is released
    # (Optional: remove this if you want it to keep moving until 's' is pressed)
    if hasattr(key, 'char') and key.char in ['w', 'a', 's', 'd']:
        current_left_speed = 0.0
        current_right_speed = 0.0
    
    # Allow exiting the script nicely with ESC
    if key == keyboard.Key.esc:
        return False

async def main():
    global current_left_speed, current_right_speed

    # 1. Start the Keyboard Listener (Non-blocking)
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    
    # 2. Setup Estimator and BLE
    estimator = MocapEstimator(target_id=15)
    ble_sender = PololuBLE()
    
    print("Connecting to BLE...")
    if await ble_sender.connect() == False:
        print("Failed to connect to Pololu BLE device.")
        exit(1)
    
    print("Connected! Controls: W (Fwd), S (Back), A (Left), D (Right). ESC to exit.")

    while True:
        try:
            # Get pose (keeping this for telemetry/printing)
            pose = estimator.get_pose()

            # --- SEND COMMAND ---
            # We simply send whatever the global variables are set to
            await ble_sender.send_wheel_speed_command(current_left_speed, current_right_speed)
    
            # Print status
            # \r allows printing on the same line to avoid flooding the terminal
            print(f"Pose: {pose} | Cmd: L={current_left_speed} R={current_right_speed}", end='\r')
            
            await asyncio.sleep(0.01) # 100Hz loop
            
            # Check if listener is still alive (stops if ESC pressed)
            if not listener.is_running():
                print("\nExiting...")
                break

        except KeyboardInterrupt:
            print("\nShutting down test script...")
            break
        except Exception as e:
            print(f"\nError: {e}")
            break

if __name__ == "__main__":
    asyncio.run(main())