"""
Test script to verify robotics domain integration.

This script tests the basic functionality of the robotics domain
without requiring Webots to be running.
"""

import sys
import os

# Add the scenic source to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

def test_robotics_domain_import():
    """Test that the robotics domain can be imported."""
    try:
        import scenic.domains.robotics.model
        import scenic.domains.robotics.actions
        import scenic.domains.robotics.behaviors
        print("✅ Robotics domain imports successfully")
        return True
    except ImportError as e:
        print(f"Failed to import robotics domain: {e}")
        return False

def test_webots_robotics_model():
    """Test that the Webots robotics model can be imported."""
    try:
        import scenic.simulators.webots.robotics_model
        print("✅ Webots robotics model imports successfully")
        return True
    except ImportError as e:
        print(f"Failed to import Webots robotics model: {e}")
        return False

def test_robot_classes():
    """Test that robot classes can be instantiated."""
    try:
        import scenic.domains.robotics.model as robotics_model
        
        # Test basic robot creation
        robot = robotics_model.PololuRobot()
        assert hasattr(robot, 'setLeftMotor')
        assert hasattr(robot, 'setRightMotor')
        assert hasattr(robot, 'sensors')
        print("✅ Robot classes instantiate correctly")
        
        # Test motor control
        robot.setLeftMotor(50)
        robot.setRightMotor(-50)
        assert robot.leftMotorSpeed == 50
        assert robot.rightMotorSpeed == -50
        print("✅ Motor control works correctly")
        
        return True
    except Exception as e:
        print(f"Robot class test failed: {e}")
        return False

def test_actions():
    """Test that actions can be created."""
    try:
        import scenic.domains.robotics.actions as robotics_actions
        
        # Test action creation
        move_action = robotics_actions.MoveForwardAction(50)
        turn_action = robotics_actions.TurnLeftAction(30)
        stop_action = robotics_actions.StopAction()
        
        assert move_action.speed == 50
        assert turn_action.speed == 30
        print("✅ Actions create correctly")
        
        return True
    except Exception as e:
        print(f"Action test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Testing robotics domain integration...")
    print("=" * 50)
    
    tests = [
        test_robotics_domain_import,
        test_webots_robotics_model,
        test_robot_classes,
        test_actions
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("All tests passed! Robotics domain integration is working.")
        return True
    else:
        print("Some tests failed. Check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
