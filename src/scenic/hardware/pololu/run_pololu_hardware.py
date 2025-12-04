import asyncio
import scenic

from scenic.hardware.pololu.interface import HardwareInterface
from scenic.hardware.pololu.simulator import HardwareSimulator

SCENIC_FILE = "examples/webots/robotics/pololu_hardware.scenic"
TIMESTEP = 0.02  # 50 Hz


def main():
    # Create a single event loop for the entire program
    # This avoids creating/destroying loops repeatedly and prevents nested loop errors
    print("[EVENT_LOOP] Creating single event loop for entire program...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    print(f"[EVENT_LOOP] Event loop created: {loop}")
    
    try:
        # 1) Connect to hardware (BLE + mocap) using the event loop
        interface = HardwareInterface(mocap_target_id=15)  # adjust as needed
        interface._event_loop = loop  # Store loop for use in simulator
        print("[EVENT_LOOP] Stored event loop in interface")
        print("[HW] Connecting to hardware...")
        if not loop.run_until_complete(interface.connect()):
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
                loop.run_until_complete(interface.send_wheel_speed_command(0, 0))
            except Exception:
                pass
            try:
                loop.run_until_complete(interface.disconnect())
            except Exception:
                pass
            print("[HW] Done.")
    finally:
        # Clean up the event loop
        print("[EVENT_LOOP] Closing event loop...")
        loop.close()
        print("[EVENT_LOOP] Event loop closed")


if __name__ == "__main__":
    main()
