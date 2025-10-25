"""
Line following robot example using IR sensors.

This example demonstrates a robot following a black line using left and right
IR sensors for navigation.
"""

model scenic.simulators.webots.robotics_model
from scenic.domains.robotics.behaviors import LineFollowingBehavior

# Create a line following robot
robot = new WebotsLineFollowingRobot at (0, 0, 0.016), facing 90 deg, with behavior LineFollowingBehavior()

# Terminate after 60 seconds
terminate after 60 seconds
