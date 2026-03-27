import threading
from dataclasses import dataclass
import sys, os
import time
from scipy.spatial.transform import Rotation as R
import numpy as np

# Import NatNetClient from the local PythonClient directory
sys.path.append(os.path.dirname(__file__))
from PythonClient.NatNetClient import NatNetClient

@dataclass
class Pose:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    qx: float = 0.0
    qy: float = 0.0
    qz: float = 0.0
    qw: float = 1.0

    def __str__(self):
        return f"Position: ({self.x:.2f}, {self.y:.2f}, {self.z:.2f}), Orientation [x,y,z,w]): ({self.qx:.2f}, {self.qy:.2f}, {self.qz:.2f}, {self.qw:.2f})"

    def get_euler_zyx(self, degrees = False):
        r = R.from_quat([self.qx, self.qy, self.qz, self.qw])
        return r.as_euler('zyx', degrees=degrees)  # returns (z, y, x)

class MocapDummyEstimator:
    def __init__(self, target_id):
        self.pose = Pose()
        self.pose_lock = threading.Lock()

        # for debugging prints
        self.enable_print = False
        self.print_interval = 100  # count
        self.print_counter = -1

        # Mocap parameters
        self.target_id = target_id  #

    def get_pose(self):
        with self.pose_lock:
            # create dummy pose
            self.pose.x += 0.001  # simulate movement
            self.pose.y += 0.001
            self.pose.z += 0.001
            self.pose.qx += 0.001
            self.pose.qy += 0.001
            self.pose.qz += 0.001
            self.pose.qw += 0.001

            return Pose(
                x=self.pose.x,
                y=self.pose.y,
                z=self.pose.z,
                qx=self.pose.qx,
                qy=self.pose.qy,
                qz=self.pose.qz,
                qw=self.pose.qw
            )
        
