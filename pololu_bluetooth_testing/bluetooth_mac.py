# bluetooth_mac.py  (macOS + Bleak ≥ 1.0)
import asyncio
from bleak import BleakScanner, BleakClient

SERVICE_UUID = "FFE0"
CHAR_UUID    = "FFE1"

TARGET_NAMES = {"HMSoft", "HM-10", "DSD TECH"}

async def find_hm10():
    print("Scanning for HM-10...")
    devices = await BleakScanner.discover(timeout=5.0)
    for d in devices:
        if (d.name and d.name in TARGET_NAMES) or ("HM" in (d.name or "")):
            return d
    return None

async def write_cmd(client: BleakClient, cmd: bytes):
    # if client connected
    await client.write_gatt_char(CHAR_UUID, cmd, response=False)
    print("Wrote:", cmd)

async def main():
    dev = await find_hm10()
    if not dev:
        print("No HM-10-like device found. Move closer or verify with a BLE scanner.")
        return
    print("Found:", dev)
    async with BleakClient(dev) as client:
        # subscribe notification (optional)
        await client.start_notify(CHAR_UUID, lambda c, d: None)
        # then send command
        while True:
            command = input("Enter command: F, B, S: ")
            if command == "F":
                await write_cmd(client, b"F")
            elif command == "B":
                await write_cmd(client, b"B")
            elif command == "S":
                await write_cmd(client, b"S")
            else:
                print("Invalid command")

if __name__ == "__main__":
    asyncio.run(main())
