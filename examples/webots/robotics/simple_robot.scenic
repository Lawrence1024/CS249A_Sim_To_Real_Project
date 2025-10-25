"""
Simple robot movement example using the robotics domain.

This example demonstrates basic robot control with forward/backward movement
and turning actions.
"""

model scenic.simulators.webots.robotics_model
from scenic.domains.robotics.behaviors import RandomWalkBehavior

# Create a simple Pololu robot with random walk behavior
robot = new WebotsPololuRobot at (0, 0, 0.016), facing 90 deg, with behavior RandomWalkBehavior()

# Terminate after 30 seconds
terminate after 30 seconds
