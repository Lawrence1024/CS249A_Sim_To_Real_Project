"""Behaviors for robots in the robotics domain.

This module provides common robot behaviors like line following, obstacle avoidance,
and basic navigation patterns.
"""

from scenic.domains.robotics.actions import *

behavior LineFollowingBehavior(forwardSpeed=50, turnSpeed=30):
    """Behavior for following a line using left and right sensors."""
    while True:
        # Simple line following logic without sensors for now
        # Move forward by default
        take MoveForwardAction(forwardSpeed)
        wait

behavior ObstacleAvoidanceBehavior(forwardSpeed=50, turnSpeed=40):
    """Behavior for avoiding obstacles using front sensor."""
    while True:
        # Simple obstacle avoidance without sensors for now
        # Move forward by default
        do MoveForwardAction(forwardSpeed) for 1 seconds

behavior RandomWalkBehavior(forwardSpeed=50, turnSpeed=40):
    """Behavior for random wandering."""
    while True:
        # Move forward for a random time
        do MoveForwardAction(forwardSpeed) for 2 seconds
        
        # Turn in random direction
        if random.random() < 0.5:
            do TurnLeftAction(turnSpeed) for 1 seconds
        else:
            do TurnRightAction(turnSpeed) for 1 seconds

behavior PatrolBehavior(waypoints, forwardSpeed=50, turnSpeed=40):
    """Behavior for patrolling between waypoints."""
    currentWaypoint = 0
    
    while True:
        target = waypoints[currentWaypoint]
        
        # Turn towards target
        angle = self.heading.angleTo(target - self.position)
        if abs(angle) > 5 deg:
            if angle > 0:
                take TurnRightAction(turnSpeed)
            else:
                take TurnLeftAction(turnSpeed)
            wait
        else:
            # Move towards target
            distance = distance from self to target
            if distance > 0.1:
                take MoveForwardAction(forwardSpeed)
                wait
            else:
                # Reached waypoint - move to next
                currentWaypoint = (currentWaypoint + 1) % len(waypoints)
                wait
