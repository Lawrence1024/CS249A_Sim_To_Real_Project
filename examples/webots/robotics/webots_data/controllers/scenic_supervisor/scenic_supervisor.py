from controller import Supervisor, Emitter, Receiver
import os
import json

import scenic
from scenic.simulators.webots import WebotsSimulator

supervisor = Supervisor()
simulator = WebotsSimulator(supervisor)

# Set up communication with robot
emitter = supervisor.getDevice("emitter")
receiver = supervisor.getDevice("receiver")
if emitter:
    emitter.setChannel(1)
if receiver:
    receiver.enable(int(supervisor.getBasicTimeStep()))

def send_motor_command(left_speed, right_speed):
    """Send motor command to robot."""
    if emitter:
        command = {
            "type": "motor_command",
            "left_speed": left_speed,
            "right_speed": right_speed
        }
        message = json.dumps(command)
        emitter.send(message.encode('utf-8'))
        print(f"Debug: Sent motor command - Left: {left_speed}, Right: {right_speed}")

# Get the path from customData and resolve it
raw_path = supervisor.getCustomData()
script_dir = os.path.dirname(os.path.abspath(__file__))

if os.path.isabs(raw_path):
    path = raw_path
else:
    path = os.path.normpath(os.path.join(script_dir, raw_path))

print(f"Loading Scenic robotics scenario: {path}")
scenario = scenic.scenarioFromFile(path)

while True:
    scene, _ = scenario.generate()
    
    # Debug: Print robot position to verify randomization
    if scene.objects:
        robot = scene.objects[0]
        print(f"DEBUG: Robot spawned at position: {robot.position}")
    
    print("Starting new robotics simulation...")
    simulator.simulate(scene, verbosity=2)
