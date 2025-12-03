# example_usage.py - Examples of using pololu_ble module
import asyncio
from pololu_ble import PololuBLE, send_ble_command, send_ble_command_async


async def example_1_class_usage():
    """Example 1: Using PololuBLE class directly (recommended for multiple commands)"""
    print("\n=== Example 1: Using PololuBLE class ===")
    
    pololu = PololuBLE()
    
    # Connect to device
    if await pololu.connect():
        # Send single character commands
        await pololu.send_command(b"F")  # Forward
        await pololu.send_command("B")   # Backward (string auto-converted)
        await pololu.send_command(b"S")  # Stop
        
        # Send multi-byte commands
        await pololu.send_command(b"Forward\x00")
        await pololu.send_command("CustomCommand123")
        
        # Disconnect when done
        await pololu.disconnect()


async def example_2_context_manager():
    """Example 2: Using context manager (auto connect/disconnect)"""
    print("\n=== Example 2: Using context manager ===")
    
    async with PololuBLE() as pololu:
        # Send various commands
        await pololu.send_command("F")
        await pololu.send_command(b"B")
        await pololu.send_command("S")
        
        # Send complex commands
        command_data = b"MotorSpeed:100\x00"
        await pololu.send_command(command_data)


def example_3_sync_wrapper():
    """Example 3: Using synchronous wrapper function"""
    print("\n=== Example 3: Using sync wrapper ===")
    
    # Simple usage - auto connects if needed
    send_ble_command("F")
    send_ble_command(b"B")
    send_ble_command("Stop")
    
    # Send multi-byte command
    send_ble_command(b"CustomCommand\x00")


async def example_4_async_wrapper():
    """Example 4: Using async wrapper function"""
    print("\n=== Example 4: Using async wrapper ===")
    
    # Send commands with async wrapper
    await send_ble_command_async("F")
    await send_ble_command_async(b"B")
    await send_ble_command_async("S")
    
    # Send complex command
    await send_ble_command_async(b"MotorControl:50,60\x00")


if __name__ == "__main__":
    # Run examples
    print("Pololu BLE Module Examples\n")
    
    # Uncomment the example you want to run:
    
    # asyncio.run(example_1_class_usage())
    # asyncio.run(example_2_context_manager())
    # example_3_sync_wrapper()
    # asyncio.run(example_4_async_wrapper())

