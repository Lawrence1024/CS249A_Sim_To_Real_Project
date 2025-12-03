from mocap.mocap_estimator import *
import time

if __name__ == "__main__":
    estimator = MocapEstimator(target_id=15)
    while True:
        try:
            pose = estimator.get_pose()
            print(pose)
            time.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down test script...")
            break