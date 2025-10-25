"""
Obstacle avoidance robot example using ultrasonic sensors.

This example demonstrates a robot avoiding obstacles using front ultrasonic
sensor for detection and turning behaviors for avoidance.
"""

model scenic.simulators.webots.robotics_model
from scenic.domains.robotics.behaviors import ObstacleAvoidanceBehavior

# Create an obstacle avoidance robot
robot = new WebotsObstacleAvoidanceRobot at (0, 0, 0.016), facing 90 deg, with behavior ObstacleAvoidanceBehavior()

# Terminate after 60 seconds
terminate after 60 seconds
