import threading
from dataclasses import dataclass

# Import NatNetClient from the local PythonClient directory
import sys, os
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


class MocapEstimator:
    def __init__(self, target_id):
        self.pose = Pose()
        self.pose_lock = threading.Lock()

        # for debugging prints
        self.enable_print = False
        self.print_interval = 100  # count
        self.print_counter = -1

        # Mocap parameters
        self.target_id = target_id  #
        self.server_ip = "169.254.10.221"
        self.client_ip = "169.254.10.222"
        self.stream_type = 'd'  # 'd' = data stream, 'c' = command stream
        self.use_multicast = False

        print("------------------------------")
        print("Initializing MocapEstimator:")
        print(f"* Target ID: {self.target_id}")
        print(f"* Server IP: {self.server_ip}")
        print(f"* Client IP: {self.client_ip}")
        print("------------------------------")
       
        # initialize NatNet client
        self.streaming_client = NatNetClient()
        self.streaming_client.set_print_level(0)
        self.streaming_client.set_client_address(self.client_ip)
        self.streaming_client.set_server_address(self.server_ip)
        self.streaming_client.set_use_multicast(self.use_multicast)
        self.streaming_client.rigid_body_listener = self.mocap_callback

        # Start streaming (runs on its own thread).
        if not self.streaming_client.run(self.stream_type):
            print("ERROR: Could not start streaming client.")
            self.streaming_client.shutdown()

    def __del__(self):
        self.streaming_client.shutdown()

    def mocap_callback(self, id, pos, rot):
        if id == self.target_id:
            with self.pose_lock:
                self.pose.x = pos[0]
                self.pose.y = pos[1]
                self.pose.z = pos[2]
                self.pose.qx = rot[0]
                self.pose.qy = rot[1]
                self.pose.qz = rot[2]
                self.pose.qw = rot[3]

                # print debug info
                if self.enable_print:
                    self.print_counter += 1
                    if (self.print_counter % self.print_interval == 0):
                        print(f"Mocap data ID {id}:")
                        print(f"Position: x={self.pose.x}, y={self.pose.y}, z={self.pose.z}")
                        print(f"Orientation: qx={self.pose.qx}, qy={self.pose.qy}, qz={self.pose.qz}, qw={self.pose.qw}")
                        self.print_counter = 0


    def get_pose(self):
        with self.pose_lock:
            return Pose(
                x=self.pose.x,
                y=self.pose.y,
                z=self.pose.z,
                qx=self.pose.qx,
                qy=self.pose.qy,
                qz=self.pose.qz,
                qw=self.pose.qw
            )
        
        
if __name__ == "__main__":
    est = MocapEstimator(target_id=8)
    while True:
        pose = est.get_pose()
        print(f"Current Pose: Position({pose.x}, {pose.y}, {pose.z}), Orientation({pose.qx}, {pose.qy}, {pose.qz}, {pose.qw})")