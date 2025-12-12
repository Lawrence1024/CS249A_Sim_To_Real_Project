"""
Square racetrack example using the robotics domain.

This demonstrates a robot following a rectangular race track with inner and outer boundaries.
"""

model scenic.simulators.webots.robotics_model
from scenic.domains.robotics.behaviors import SquareTrackBehavior

# Define a workspace region (3x3 meter area centered at (-0.67, -0.05) for track)
workspace_region = RectangularRegion((-0.67, -0.05, 0.01885), 0, 3, 3)
workspace = Workspace(workspace_region)

# Create a Pololu robot that follows the rectangular track
# Waypoints (hardcoded in behavior): (-0.32,-0.46), (-0.32,0.36), (-1.02,0.36), (-1.02,-0.46)
# Forms a 0.7m x 0.82m rectangle
# Position at first waypoint to start the track properly
# Height 0.01885m = body center height (5.8mm clearance + 13.05mm half-height)
robot = new WebotsPololuRobot at (-1.268, -0.737, 0.01885), with behavior SquareTrackBehavior(
    forwardSpeed=68.62114418390924,
    turnSpeed=22.551390921291528,
    waypointThreshold=0.09143188983175649,
    headingOffset=-90 deg
)

# Terminate after 120 seconds
terminate after 120 seconds
