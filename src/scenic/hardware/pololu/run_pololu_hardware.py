import asyncio
import scenic

from scenic.hardware.pololu.interface import HardwareInterface
from scenic.hardware.pololu.simulator import HardwareSimulator

SCENIC_FILE = "examples/webots/robotics/pololu_hardware.scenic"
TIMESTEP = 0.02  # 50 Hz


def main():
    # 1) Connect to hardware (BLE + mocap) using asyncio once
    interface = HardwareInterface(mocap_target_id=15)  # adjust as needed
    print("[HW] Connecting to hardware...")
    if not asyncio.run(interface.connect()):
        print("[HW] Failed to connect; aborting.")
        return
    print("[HW] Connected.")

    # 2) Load Scenic scenario and generate a scene
    scenario = scenic.scenarioFromFile(SCENIC_FILE)
    scene, _ = scenario.generate()
    
    # Set hardware interface on robot objects
    for obj in scene.objects:
        if hasattr(obj, 'setHardwareInterface'):
            obj.setHardwareInterface(interface)

    # 3) Create hardware-backed Scenic simulator
    simulator = HardwareSimulator(interface=interface, timestep=TIMESTEP)

    print("[Scenic] Starting closed-loop hardware simulation...")
    try:
        # simulate() blocks until 'terminate after ...' or failure
        simulation = simulator.simulate(scene, maxSteps=None, verbosity=2)

        print("[Scenic] Simulation finished.")
        print("  termination:", simulation.result.terminationReason)

    finally:
        # Extra safety: stop robot & disconnect even if simulate() failed
        print("[HW] Stopping robot and disconnecting...")
        try:
            asyncio.run(interface.send_wheel_speed_command(0, 0))
        except Exception:
            pass
        asyncio.run(interface.disconnect())
        print("[HW] Done.")


if __name__ == "__main__":
    main()
