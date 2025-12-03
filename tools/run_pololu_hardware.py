import asyncio
import time

import scenic
from scenic.hardware.pololu.interface import HardwareInterface

CONTROL_PERIOD = 0.02  # 50 Hz


async def main():
    # 1) Set up hardware interface (fill in your real params here)
    interface = HardwareInterface(
        mocap_target_id=15,     
    )

    print("[HW] Connecting BLE...")
    connected = await interface.connect()
    if not connected:
        print("[HW] BLE connection failed; aborting.")
        return
    print("[HW] BLE connected.")

    # 2) Load Scenic scenario
    scenario = scenic.scenarioFromFile(
        "examples/webots/robotics/pololu_hardware.scenic"
    )
    scene, _ = scenario.generate()
    print("[Scenic] Scene generated.")

    # 3) Find the hardware robot and attach the interface
    robots = [obj for obj in scene.objects
              if hasattr(obj, "setHardwareInterface")]
    if not robots:
        print("[Scenic] No HardwarePololuRobot found in scene.")
        return

    robot = robots[0]
    robot.setHardwareInterface(interface)
    print("[Scenic] Attached HardwareInterface to robot:", robot)

    # 4) If your scenario is dynamic, get a simulator & simulation
    simulator = scenario.getSimulator()
    simulation = simulator.createSimulation(scene)
    print("[Scenic] Simulation created.")

    # 5) Control loop
    try:
        print("[Loop] Starting control loop...")
        last = time.time()
        while True:
            now = time.time()
            dt = now - last
            last = now

            # 5a) Update robot pose from mocap (if available)
            if hasattr(robot, "updatePositionFromMocap"):
                try:
                    robot.updatePositionFromMocap()
                except Exception as e:
                    # Safe to ignore for now; just log
                    print(f"[Loop] Mocap update error: {e}")

            # 5b) Advance Scenic one step
            #     (this updates behaviors, which will call setMotors inside Scenic)
            simulation.step()

            # 5c) Get desired motor command from Scenic robot
            cmd = None
            if hasattr(robot, "getPendingMotorCommand"):
                cmd = robot.getPendingMotorCommand()

            if cmd is not None:
                left, right = cmd
                # HardwareInterface expects -255..255; conversion is handled inside
                print(f"[Loop] Sending command: L={left:.1f}, R={right:.1f}")
                await interface.send_wheel_speed_command(left, right)

            # 5d) Sleep to maintain control rate
            await asyncio.sleep(max(0.0, CONTROL_PERIOD - (time.time() - now)))

    finally:
        print("[Loop] Stopping robot and disconnecting...")
        try:
            await interface.send_wheel_speed_command(0, 0)
        except Exception:
            pass
        await interface.disconnect()
        print("[Loop] Done.")


if __name__ == "__main__":
    asyncio.run(main())
