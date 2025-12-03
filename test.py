import asyncio
from scenic.hardware.pololu.interface import HardwareInterface

async def main():
    interface = HardwareInterface(mocap_target_id=15)

    print("Connecting to BLE...")
    ok = await interface.connect()
    print("Connected:", ok)
    if not ok:
        return

    try:
        # 1) Check mocap
        pose = interface.get_pose()
        print("Initial pose from mocap:", pose)

        # 2) Drive the robot a bit
        print("Driving forward...")
        await interface.send_wheel_speed_command(80, 80)
        await asyncio.sleep(1.0)

        print("Turning on the spot...")
        await interface.send_wheel_speed_command(80, -80)
        await asyncio.sleep(1.0)

        print("Stopping...")
        await interface.send_wheel_speed_command(0, 0)

    finally:
        await interface.disconnect()
        print("Disconnected.")

if __name__ == "__main__":
    asyncio.run(main())
