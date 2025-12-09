"""
Rectangular racetrack example using the robotics domain with VerifAI parameters.

This demonstrates a robot following a rectangular race track with inner and outer boundaries.
Parameters marked with VerifaiRange can be varied by VerifAI falsification.
"""

model scenic.simulators.webots.robotics_model
from scenic.domains.robotics.behaviors import SquareTrackBehavior
from scenic.core.external_params import VerifaiRange

# Define a workspace region (3x3 meter area centered at (-0.67, -0.05) for track)
workspace_region = RectangularRegion((-0.67, -0.05, 0.01885), 0, 3, 3)
workspace = Workspace(workspace_region)

# Create a Pololu robot that follows the rectangular track
# Waypoints (hardcoded in behavior): (-0.32,-0.46), (-0.32,0.36), (-1.02,0.36), (-1.02,-0.46)
# Forms a 0.7m x 0.82m rectangle
# Position at first waypoint to start the track properly
# Height 0.01885m = body center height (5.8mm clearance + 13.05mm half-height)
robot = new WebotsPololuRobot at (-0.32, -0.46, 0.01885), 
    with behavior SquareTrackBehavior(
        forwardSpeed=VerifaiRange(50, 100), 
        turnSpeed=VerifaiRange(40, 80), 
        waypointThreshold=VerifaiRange(0.05, 0.2),
        headingOffset=-90 deg
    )

# Terminate after 120 seconds
terminate after 120 seconds
