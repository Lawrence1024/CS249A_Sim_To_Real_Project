"""Hardware-specific robotics model for Pololu robots.

This model extends the generic robotics domain with hardware integration
for controlling physical Pololu robots via BLE and receiving feedback
from motion capture systems.

Example usage:
    model scenic.hardware.pololu.model
    
    robot = new HardwarePololuRobot at (0, 0, 0), with behavior SomeBehavior()
"""

from scenic.domains.robotics.model import *
from scenic.domains.robotics.actions import *

class HardwarePololuRobot(PololuRobot):
    """Pololu robot with hardware control via BLE and mocap feedback.
    
    This robot class extends PololuRobot to send commands to physical
    hardware via BLE and receive position/orientation from mocap.
    
    The hardware interface must be set externally using setHardwareInterface()
    before using the robot.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Reference to hardware interface (set externally)
        self._hardware_interface = None
        # Queue for pending motor commands (for async execution)
        self._pending_motor_command = None
    
    def setHardwareInterface(self, interface):
        """Set the hardware interface for this robot.
        
        Args:
            interface: HardwareInterface instance to use for control and feedback
        """
        self._hardware_interface = interface
    
    def setLeftMotor(self, speed):
        """Set left motor speed and send command to hardware."""
        super().setLeftMotor(speed)
        self._sendMotorCommand()
    
    def setRightMotor(self, speed):
        """Set right motor speed and send command to hardware."""
        super().setRightMotor(speed)
        self._sendMotorCommand()
    
    def _sendMotorCommand(self):
        """Queue motor command to be sent to hardware via BLE.
        
        The command is stored and should be executed by the simulation
        loop which handles async operations.
        """
        if self._hardware_interface:
            try:
                # Convert from Scenic speed range (-100 to 100) to BLE range (-255 to 255)
                left_ble = int((self.leftMotorSpeed / 100.0) * 255)
                right_ble = int((self.rightMotorSpeed / 100.0) * 255)
                
                # Store command to be sent asynchronously
                self._pending_motor_command = (left_ble, right_ble)
            except Exception as e:
                print(f"Hardware motor command error: {e}")
    
    def getPendingMotorCommand(self):
        """Get and clear any pending motor command.
        
        Returns:
            Tuple of (left_speed, right_speed) in BLE range, or None if no command
        """
        cmd = self._pending_motor_command
        self._pending_motor_command = None
        return cmd
    
    def updatePositionFromMocap(self):
        """Update robot position and orientation from motion capture system."""
        if self._hardware_interface:
            try:
                pose = self._hardware_interface.get_pose()
                
                # Update position (mocap coordinates in meters)
                self.position = (pose.x, pose.y, pose.z)
                
                # Convert quaternion to heading/yaw
                euler = pose.get_euler_zyx(degrees=False)
                yaw = euler[0]  # z-axis rotation is yaw/heading
                
                # Update orientation (Scenic uses yaw in radians)
                from scenic.core.vectors import Orientation
                self.heading = yaw
                
            except Exception as e:
                print(f"Error updating position from mocap: {e}")

