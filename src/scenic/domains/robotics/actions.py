"""Actions for dynamic agents in the robotics domain.

These actions are automatically imported when using the robotics domain.

The actions are designed for mobile robots with differential drive systems,
sensor-based navigation, and robot-specific behaviors.
"""

import math
from scenic.core.simulators import Action
from scenic.core.vectors import Vector

## Mixin classes indicating support for various types of robot actions.

class DifferentialDrive:
    """Mixin protocol for robots with differential drive (left/right motors).
    
    Robots must support setting left and right motor speeds independently.
    """
    
    def setLeftMotor(self, speed):
        """Set left motor speed (-100 to 100)."""
        raise NotImplementedError
        
    def setRightMotor(self, speed):
        """Set right motor speed (-100 to 100)."""
        raise NotImplementedError
        
    def setMotors(self, left, right):
        """Set both motors simultaneously."""
        self.setLeftMotor(left)
        self.setRightMotor(right)

## Robot-specific actions

class MoveForwardAction(Action):
    """Move robot forward at given speed."""
    
    def __init__(self, speed):
        self.speed = speed
        
    def applyTo(self, obj, sim):
        if hasattr(obj, 'setMotors'):
            obj.setMotors(self.speed, self.speed)
        else:
            raise RuntimeError(f"Object {obj} does not support motor control")

class MoveBackwardAction(Action):
    """Move robot backward at given speed."""
    
    def __init__(self, speed):
        self.speed = speed
        
    def applyTo(self, obj, sim):
        if hasattr(obj, 'setMotors'):
            obj.setMotors(-self.speed, -self.speed)
        else:
            raise RuntimeError(f"Object {obj} does not support motor control")

class TurnLeftAction(Action):
    """Turn robot left (counter-clockwise) at given speed."""
    
    def __init__(self, speed=50):
        self.speed = speed
        
    def applyTo(self, obj, sim):
        if hasattr(obj, 'setMotors'):
            obj.setMotors(-self.speed, self.speed)
        else:
            raise RuntimeError(f"Object {obj} does not support motor control")

class TurnRightAction(Action):
    """Turn robot right (clockwise) at given speed."""
    
    def __init__(self, speed=50):
        self.speed = speed
        
    def applyTo(self, obj, sim):
        if hasattr(obj, 'setMotors'):
            obj.setMotors(self.speed, -self.speed)
        else:
            raise RuntimeError(f"Object {obj} does not support motor control")

class StopAction(Action):
    """Stop the robot (set both motors to 0)."""
    
    def applyTo(self, obj, sim):
        if hasattr(obj, 'setMotors'):
            obj.setMotors(0, 0)
        else:
            raise RuntimeError(f"Object {obj} does not support motor control")

class SetMotorAction(Action):
    """Set individual motor speeds."""
    
    def __init__(self, left, right):
        self.left = left
        self.right = right
        
    def applyTo(self, obj, sim):
        if hasattr(obj, 'setMotors'):
            obj.setMotors(self.left, self.right)
        else:
            raise RuntimeError(f"Object {obj} does not support motor control")

class TurnByAngleAction(Action):
    """Turn robot by a specific angle."""
    
    def __init__(self, angle, speed=50):
        self.angle = angle
        self.speed = speed
        
    def applyTo(self, obj, sim):
        if hasattr(obj, 'setMotors'):
            if self.angle > 0:  # Turn right
                obj.setMotors(self.speed, -self.speed)
            else:  # Turn left
                obj.setMotors(-self.speed, self.speed)
        else:
            raise RuntimeError(f"Object {obj} does not support motor control")
