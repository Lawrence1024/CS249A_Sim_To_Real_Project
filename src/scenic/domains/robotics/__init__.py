"""Domain for robotics scenarios.

This domain provides a foundation for mobile robotics scenarios, including
differential drive robots, sensor-based navigation, and robot-specific behaviors.

The :doc:`world model <scenic.domains.robotics.model>` defines Scenic classes for robots,
sensors, environments, and robot-specific actions and behaviors. Scenarios for the 
robotics domain should import the model as follows::

    model scenic.domains.robotics.model

This domain is designed to work with robotics simulators like Webots, Gazebo, 
and CoppeliaSim, providing a simulator-agnostic interface for robot programming.

Example usage:
    * Basic robot movement:
        .. code-block:: console

            $ scenic examples/webots/robotics/simple_robot.scenic

    * Line following robot:
        .. code-block:: console

            $ scenic examples/webots/robotics/line_following.scenic
"""
