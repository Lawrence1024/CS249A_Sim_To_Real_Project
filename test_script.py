from mocap.mocap_estimator import *
from pololu_bluetooth_testing.pololu_ble import *
import time

async def main():
    estimator = MocapEstimator(target_id=15)
    ble_sender = PololuBLE()
    if await ble_sender.connect() == False:
        print("Failed to connect to Pololu BLE device.")
        exit(1)
    
    while True:
        try:
            # get pose/ state
            pose = estimator.get_pose()

            # senic compute the action


            # send action via BLE
            if pose.x>0.0:
                command = b"B"  # Example command
            else:
                command = b"F"
            await ble_sender.send_command(command)

            print(pose)
            await asyncio.sleep(0.01)
        except KeyboardInterrupt:
            print("Shutting down test script...")
            break

if __name__ == "__main__":
    asyncio.run(main())
