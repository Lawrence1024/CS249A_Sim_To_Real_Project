"""Webots-specific robotics model.

This model extends the generic robotics domain with Webots-specific implementations
for robot control and sensor integration.
"""

from scenic.domains.robotics.model import *
from scenic.simulators.webots.model import WebotsObject
from scenic.simulators.webots.actions import *

class WebotsRobot(WebotsObject, DifferentialDriveRobot):
    """Webots robot with differential drive capabilities."""
    
    def setLeftMotor(self, speed):
        """Set left motor speed and send command to robot controller."""
        super().setLeftMotor(speed)
        self._sendMotorCommand()
    
    def setRightMotor(self, speed):
        """Set right motor speed and send command to robot controller."""
        super().setRightMotor(speed)
        self._sendMotorCommand()
    
    def _sendMotorCommand(self):
        """Send motor command to robot controller."""
        if hasattr(self, 'webotsSupervisor') and self.webotsSupervisor:
            try:
                emitter = self.webotsSupervisor.getDevice("emitter")
                if emitter:
                    import json
                    # Send percent values (0..100) and let the robot controller scale to its maxVelocity.
                    command = {
                        "type": "motor_command",
                        "left_speed": self.leftMotorSpeed,
                        "right_speed": self.rightMotorSpeed
                    }
                    message = json.dumps(command)
                    emitter.send(message.encode('utf-8'))
            except Exception as e:
                print(f"Motor command error: {e}")
    
    def _sendWaypointReached(self, waypoint_num):
        """Send waypoint reached signal to robot controller."""
        if hasattr(self, 'webotsSupervisor') and self.webotsSupervisor:
            try:
                emitter = self.webotsSupervisor.getDevice("emitter")
                if emitter:
                    import json
                    command = {
                        "type": "waypoint_reached",
                        "waypoint_num": waypoint_num
                    }
                    message = json.dumps(command)
                    emitter.send(message.encode('utf-8'))
            except Exception as e:
                print(f"Waypoint command error: {e}")


class WebotsPololuRobot(WebotsRobot, PololuRobot):
    """Webots implementation of Pololu robot."""
    
    webotsName: "POLOLU_ROBOT"
    webotsType: "PololuRobot"

class WebotsLineFollowingRobot(WebotsRobot, LineFollowingRobot):
    """Webots implementation of line following robot."""
    
    webotsName: "LINE_FOLLOWING_ROBOT"
    webotsType: "LineFollowingRobot"

class WebotsObstacleAvoidanceRobot(WebotsRobot, ObstacleAvoidanceRobot):
    """Webots implementation of obstacle avoidance robot."""
    
    webotsName: "OBSTACLE_AVOIDANCE_ROBOT"
    webotsType: "OBSTACLE_AVOIDANCE_ROBOT"

# Webots-specific environment objects
class WebotsMaze(WebotsObject, Maze):
    """Webots maze environment."""
    
    webotsName: "MAZE"
    webotsType: "Maze"

class WebotsTrack(WebotsObject, Track):
    """Webots track environment for line following."""
    
    webotsName: "TRACK"
    webotsType: "Track"

class WebotsWall(WebotsObject, Wall):
    """Webots wall obstacle."""
    
    webotsName: "WALL"
    webotsType: "Wall"

class WebotsBox(WebotsObject, Box):
    """Webots box obstacle."""
    
    webotsName: "BOX"
    webotsType: "Box"