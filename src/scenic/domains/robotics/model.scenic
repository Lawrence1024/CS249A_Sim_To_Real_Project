"""World model for robotics scenarios.

This model defines Scenic classes for robots, sensors, environments, and
robot-specific behaviors. It provides a simulator-agnostic interface for
mobile robotics programming.

The model supports:
- Differential drive robots (left/right motor control)
- Sensor-based navigation (IR sensors, ultrasonic, etc.)
- Robot behaviors (line following, obstacle avoidance, etc.)
- Environment modeling (mazes, tracks, obstacles)

Example usage:
    model scenic.domains.robotics.model
    
    robot = new PololuRobot at (0, 0, 0), with behavior LineFollowingBehavior()
"""

import math
import random
from scenic.core.object_types import Object
from scenic.core.distributions import distributionFunction
from scenic.domains.robotics.actions import *
from scenic.domains.robotics.behaviors import *

class Robot(Object):
    """Base class for mobile robots.
    
    Properties:
        position: Default position is (0, 0, 0).
        width: Default width is 0.1 meters.
        length: Default length is 0.1 meters.
        height: Default height is 0.05 meters.
        leftMotorSpeed: Current left motor speed (-100 to 100).
        rightMotorSpeed: Current right motor speed (-100 to 100).
    """
    
    position: (0, 0, 0)
    width: 0.1
    length: 0.1
    height: 0.05
    leftMotorSpeed: 0
    rightMotorSpeed: 0
    
    @property
    def isRobot(self):
        return True

class DifferentialDriveRobot(Robot, DifferentialDrive):
    """Robot with differential drive (left/right motors)."""
    
    def setLeftMotor(self, speed):
        """Set left motor speed (-100 to 100)."""
        self.leftMotorSpeed = max(-100, min(100, speed))
        
    def setRightMotor(self, speed):
        """Set right motor speed (-100 to 100)."""
        self.rightMotorSpeed = max(-100, min(100, speed))
        
    def setMotors(self, left, right):
        """Set both motors simultaneously."""
        self.setLeftMotor(left)
        self.setRightMotor(right)

class PololuRobot(DifferentialDriveRobot):
    """Pololu-style differential drive robot."""
    
    width: 0.1
    length: 0.1
    height: 0.05

class LineFollowingRobot(PololuRobot):
    """Robot optimized for line following."""
    pass

class ObstacleAvoidanceRobot(PololuRobot):
    """Robot optimized for obstacle avoidance."""
    pass

class Environment(Object):
    """Base class for robot environments."""
    
    @property
    def isEnvironment(self):
        return True

class Maze(Environment):
    """Maze environment for robot navigation."""
    
    width: 5.0
    length: 5.0
    wallHeight: 0.2
    wallThickness: 0.05
    
class Track(Environment):
    """Track environment for line following."""
    
    width: 1.0
    length: 10.0
    lineWidth: 0.02
    
class Obstacle(Object):
    """Obstacle object for robot environments."""
    
    width: 0.2
    length: 0.2
    height: 0.1
    
    @property
    def isObstacle(self):
        return True

class Wall(Obstacle):
    """Wall obstacle."""
    
    width: 0.05
    length: 1.0
    height: 0.2

class Box(Obstacle):
    """Box obstacle."""
    
    width: 0.3
    length: 0.3
    height: 0.3

# Global parameters for robotics scenarios
param robotSpeed = 50          # Default robot speed
param turnSpeed = 40          # Default turn speed
param sensorThreshold = 500   # Default sensor threshold
param simulationTime = 30     # Default simulation time in seconds
