import numpy as np
import matplotlib.pyplot as plt
from multiprocessing import Pool, freeze_support
from scipy import integrate
from scipy.spatial.transform import Rotation as R
import random
import sys
import time
import argparse
from PythonClient.NatNetClient import NatNetClient


parser = argparse.ArgumentParser()
args = parser.parse_args()


curr_frame = 0
SKIP_FRAMES = 1
TARGET_ID = 8
TARGET_NAME = b"pololu"

latest_pos = None
latest_rot = None

def pololu_rigid_body_listener(id, pos, rot):
    if id == TARGET_ID:
        global latest_pos, latest_rot
        t1 = time.time()
        print("Mocap data received at:", t1)
        latest_pos = pos
        latest_rot = rot
        print("Pololu position:", latest_pos)
        print("Pololu rotation:", latest_rot)

if __name__ == "__main__":   
    SERVER_IP   = "169.254.10.221"   # Motive machine
    CLIENT_IP   = "169.254.10.222"   # Your NIC on same subnet
    USE_MULTICAST = False             # Multicast = True, Unicast = False
    MULTICAST_GRP = "239.255.42.99"  # Motive default
    STREAM_TYPE   = 'd'              # 'd' = data stream, 'c' = command stream

    streaming_client = NatNetClient()
    streaming_client.set_print_level(0)
    streaming_client.set_client_address(CLIENT_IP)
    streaming_client.set_server_address(SERVER_IP)
    streaming_client.set_use_multicast(USE_MULTICAST)
    # streaming_client.set_multicast_address(MULTICAST_GRP)
    streaming_client.rigid_body_listener = pololu_rigid_body_listener


    print("NatNet Python Client (preconfigured)\n")

    # Start streaming (runs on its own thread).
    if not streaming_client.run(STREAM_TYPE):
        print("ERROR: Could not start streaming client.")
        sys.exit(1)
    try :
        time.sleep(1)
    except KeyboardInterrupt :
        streaming_client.shutdown()
        exit(0)

