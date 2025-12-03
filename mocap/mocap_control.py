import asyncio
import threading
from bleak import BleakScanner, BleakClient
from PythonClient.NatNetClient import NatNetClient

# --- CONFIGURATION ---
SERVICE_UUID = "FFE0"
CHAR_UUID    = "FFE1"
TARGET_NAMES = {"HMSoft", "HM-10", "DSD TECH"}
TARGET_ID    = 15

# --- GLOBAL STATE ---
ble_client = None
main_loop = None
current_state = None  # To track what we last sent
print_counter = 0

# 1. BLE SCANNER
async def find_hm10():
    print("Scanning for HM-10...")
    devices = await BleakScanner.discover(timeout=5.0)
    for d in devices:
        if (d.name and d.name in TARGET_NAMES) or ("HM" in (d.name or "")):
            return d
    return None

# 2. HELPER TO SEND COMMAND SAFELY
def send_ble_command(cmd_bytes):
    """Schedules a BLE write on the main asyncio loop."""
    global ble_client, main_loop
    if ble_client and ble_client.is_connected and main_loop:
        try:
            # We use fire-and-forget (run_coroutine_threadsafe)
            asyncio.run_coroutine_threadsafe(
                ble_client.write_gatt_char(CHAR_UUID, cmd_bytes, response=False),
                main_loop
            )
            print(f"Sent command: {cmd_bytes}")
        except Exception as e:
            print(f"Failed to schedule write: {e}")

# 3. NATNET LISTENER (Runs at 120Hz)
def pololu_rigid_body_listener(id, pos, rot):
    global current_state
    
    if id == TARGET_ID:
        # Determine what the robot SHOULD be doing
        desired_command = b'S'
        if pos[0] > -0.9:
            desired_command = b'F'
        elif pos[0] < -1.1:
            desired_command = b'B'
        
        # --- CRITICAL FIX: STATE CHECK ---
        # Only send if the command is DIFFERENT from the last one we sent
        if desired_command != current_state:
            print(f"Position: {pos}, Desired Command: {desired_command}")
            send_ble_command(desired_command)
            current_state = desired_command

# 4. START NATNET
def start_natnet():
    streaming_client = NatNetClient()
    streaming_client.set_print_level(0)
    streaming_client.set_client_address("169.254.10.222") # Check your IP
    streaming_client.set_server_address("169.254.10.221")
    streaming_client.set_use_multicast(False)
    streaming_client.rigid_body_listener = pololu_rigid_body_listener
    
    if not streaming_client.run('d'):
        print("ERROR: NatNet failed to start.")

# 5. MAIN ASYNC LOOP
async def main():
    global ble_client, main_loop
    
    # Capture the loop so the thread can access it
    main_loop = asyncio.get_running_loop()

    # Connect to BLE
    dev = await find_hm10()
    if not dev:
        print("Device not found.")
        return

    async with BleakClient(dev) as client:
        ble_client = client
        print("BLE Connected!")
        
        # Start NatNet in a separate thread
        t = threading.Thread(target=start_natnet, daemon=True)
        t.start()
        print("NatNet started. Move robot to trigger commands.")

        # Keep the script alive forever
        while True:
            await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopping...")