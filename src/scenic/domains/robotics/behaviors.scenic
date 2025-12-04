"""Behaviors for robots in the robotics domain.

This module provides common robot behaviors like line following, obstacle avoidance,
and basic navigation patterns.
"""

from scenic.domains.robotics.actions import *
from scenic.core.geometry import headingOfSegment, normalizeAngle

behavior LineFollowingBehavior(forwardSpeed=50, turnSpeed=30):
    """Behavior for following a line using left and right sensors."""
    print("hi---------------")

    while True:
        # Simple line following logic without sensors for now
        # Move forward by default
        take MoveForwardAction(forwardSpeed)
        wait


behavior PatrolBehavior(waypoints, forwardSpeed=50, turnSpeed=40, headingOffset=0 deg):
    """Behavior for patrolling between waypoints using improved proportional control."""
    currentWaypoint = 0
    lastAngleError = 0
    while True:
        target = waypoints[currentWaypoint]
        
        # Compute angle error to target
        targetHeading = headingOfSegment(self.position, target)
        effectiveHeading = normalizeAngle(self.heading + headingOffset)
        angle = normalizeAngle(targetHeading - effectiveHeading)
        distance = distance from self to target
        
        # DIAGNOSTIC: Log all key navigation values
        print(f"[NAV] WP{currentWaypoint} pos=({self.position.x:.2f},{self.position.y:.2f}) dist={distance:.2f}m")
        print(f"[NAV] heading={self.heading:.3f} targetH={targetHeading:.3f} effectiveH={effectiveHeading:.3f} angle={angle:.3f}")
        
        if distance > 0.1:
            # Improved proportional control with gain adjustment
            # Use a higher gain for larger errors (non-linear response)
            maxAngle = 3.14159  # π radians
            
            # Calculate motor speeds for arc motion
            baseSpeed = forwardSpeed
            
            # Apply stronger correction for larger angles
            # Use a quadratic response curve for better tracking
            if abs(angle) > 0.3:  # ~17 degrees
                # Large error: stronger correction
                correctionFactor = 0.8
            elif abs(angle) > 0.15:  # ~9 degrees
                # Medium error: moderate correction
                correctionFactor = 0.4
            else:
                # Small error: gentle correction (but not too weak)
                correctionFactor = 0.15
            
            # Normalize angle to [-1, 1] range
            normalizedAngle = angle / maxAngle
            
            # Adjust speeds proportionally: if normalizedAngle > 0, need to turn left (left slower)
            adjustment = normalizedAngle * turnSpeed * correctionFactor
            leftSpeed = baseSpeed - adjustment
            rightSpeed = baseSpeed + adjustment
            
            # Clamp motor speeds to valid range [0, 100]
            leftSpeed = max(0, min(100, leftSpeed))
            rightSpeed = max(0, min(100, rightSpeed))
            
            lastAngleError = angle
            
            # DIAGNOSTIC: Log motor commands
            print(f"[MOTOR] L={leftSpeed:.1f} R={rightSpeed:.1f}")
            
            # Take proportional turn action
            take SetMotorAction(leftSpeed, rightSpeed)
            wait
        else:
            # Reached waypoint - move to next
            currentWaypoint = (currentWaypoint + 1) % len(waypoints)
            lastAngleError = 0  # Reset error when switching waypoints
            wait

behavior SquareTrackBehavior(forwardSpeed=50, turnSpeed=10, headingOffset=0 deg):
    """Behavior for following a square race track using PatrolBehavior."""
    # Define waypoints that form a square (middle of the track, well within bounds)
    waypoints = [(-0.32,-0.45,0.03), (-0.31,0.37,0.03), (-1.02,0.357,0.03), (-1.03,-0.47,0.03)]
    
    # Use PatrolBehavior for waypoint following
    do PatrolBehavior(waypoints, forwardSpeed, turnSpeed, headingOffset)

