"""Simple robot controller for Scenic robotics domain.

This controller receives motor commands from Scenic via Webots communication
and controls the robot's motors accordingly.
"""

from controller import Robot, Receiver, Emitter
import json

class SimpleRobotController:
    def __init__(self):
        self.robot = Robot()
        self.timestep = int(self.robot.getBasicTimeStep())
        
        # Get motors
        self.left_motor = self.robot.getDevice("leftMotor")
        self.right_motor = self.robot.getDevice("rightMotor")
        
        if self.left_motor and self.right_motor:
            self.left_motor.setPosition(float('inf'))
            self.right_motor.setPosition(float('inf'))
            self.left_motor.setVelocity(0.0)
            self.right_motor.setVelocity(0.0)
            print("Robot controller initialized - motors ready")
        else:
            print("ERROR: Failed to initialize motors")
            if not self.left_motor:
                print("ERROR: leftMotor not found")
            if not self.right_motor:
                print("ERROR: rightMotor not found")
        
        # Communication with Scenic supervisor
        self.receiver = self.robot.getDevice("receiver")
        if self.receiver:
            self.receiver.enable(self.timestep)
            print("Robot controller - receiver enabled")
        else:
            print("ERROR: No receiver found")
    
    def run(self):
        """Main control loop."""
        print("Robot controller starting main loop")
        
        while self.robot.step(self.timestep) != -1:
            # Check for commands from Scenic
            if self.receiver and self.receiver.getQueueLength() > 0:
                message = self.receiver.getString()
                self.receiver.nextPacket()
                
                try:
                    command = json.loads(message)
                    self.handle_command(command)
                except json.JSONDecodeError:
                    print(f"ERROR: Invalid JSON command: {message}")
                except Exception as e:
                    print(f"ERROR: Command handling error: {e}")
    
    def handle_command(self, command):
        """Handle motor commands from Scenic."""
        if command.get("type") == "motor_command":
            left_speed = command.get("left_speed", 0)
            right_speed = command.get("right_speed", 0)
            
            if self.left_motor:
                self.left_motor.setVelocity(float(left_speed))
            if self.right_motor:
                self.right_motor.setVelocity(float(right_speed))
        elif command.get("type") == "waypoint_reached":
            waypoint_num = command.get("waypoint_num", "?")
            if isinstance(waypoint_num, str):
                print(f"✓ {waypoint_num}")
            else:
                print(f"✓ Waypoint {waypoint_num} reached!")

# Create and run the controller
controller = SimpleRobotController()
controller.run()
