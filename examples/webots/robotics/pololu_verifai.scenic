"""
Rectangular racetrack example using the robotics domain with VerifAI parameters.

This demonstrates a robot following a rectangular race track with inner and outer boundaries.
Parameters marked with VerifaiRange can be varied by VerifAI falsification.

Uses Frenet frame: "s" parameter represents arc length along the track centerline.
"""

model scenic.simulators.webots.robotics_model
from scenic.domains.robotics.behaviors import SquareTrackBehavior
from scenic.core.external_params import VerifaiRange
import math

# Define track centerline waypoints for rectangular track
# Forms a 0.7m x 0.82m rectangle
track_waypoints = [(-0.32, -0.46), (-0.32, 0.36), (-1.02, 0.36), (-1.02, -0.46)]
# Calculate perimeter (2 * width + 2 * height)
width = 0.7  # meters (X direction: -0.32 to -1.02)
height = 0.82  # meters (Y direction: -0.46 to 0.36)
track_perimeter = 2 * (width + height)  # ~3.04 meters

# Define track centerline as a closed polyline (add first point at end to close loop)
track_points = track_waypoints + [track_waypoints[0]]
track_centerline = PolylineRegion(track_points)

# Define a workspace region (3x3 meter area centered at (-0.67, -0.05) for track)
workspace_region = RectangularRegion((-0.67, -0.05, 0.02465), 0, 3, 3)
workspace = Workspace(workspace_region)

# Parameter: arc length along track centerline (s) - using Frenet frame
# Normalize s to be within track perimeter (wraps around)
param s = VerifaiRange(0, track_perimeter)

# Create a Pololu robot that follows the rectangular track
# Position determined by arc length "s" along the track centerline using pointAlongBy
# This method works with distributions - Scenic handles it properly
# Normalize s to track perimeter and set z coordinate to 0.02465 (robot height)
# Waypoints (hardcoded in behavior): (-0.32,-0.46), (-0.32,0.36), (-1.02,0.36), (-1.02,-0.46)
s_normalized = globalParameters.s % track_perimeter
s_pos_2d = track_centerline.pointAlongBy(s_normalized, normalized=False)

robot = new WebotsPololuRobot at (s_pos_2d.x, s_pos_2d.y, 0.02465), 
    with behavior SquareTrackBehavior(
        forwardSpeed=VerifaiRange(50, 100), 
        turnSpeed=VerifaiRange(40, 80), 
        headingOffset=-90 deg
    )

# Terminate after 120 seconds
terminate after 120 seconds
