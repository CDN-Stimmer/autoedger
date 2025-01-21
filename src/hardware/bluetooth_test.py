import asyncio
from bleak import BleakScanner, BleakClient
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# DG-LAB Coyote V3 Constants
DEVICE_NAME = "47L121000"
SERVICE_UUID = "0000180C-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID = "0000150A-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR_UUID = "0000150B-0000-1000-8000-00805f9b34fb"
BATTERY_SERVICE_UUID = "0000180A-0000-1000-8000-00805f9b34fb"
BATTERY_CHAR_UUID = "00001500-0000-1000-8000-00805f9b34fb"

def notification_handler(sender, data):
    """Handle incoming notifications."""
    logger.info(f"Received notification: {data.hex()}")
    if data[0] == 0xB1:  # Response to B0 command
        sequence = (data[1] >> 4) & 0x0F
        channel_a = data[2]
        channel_b = data[3]
        logger.info(f"Sequence: {sequence}, Channel A: {channel_a}, Channel B: {channel_b}")

async def scan_for_device():
    """Scan specifically for the DG-LAB device."""
    logger.info(f"Scanning for {DEVICE_NAME}...")
    devices = await BleakScanner.discover()
    for d in devices:
        if d.name == DEVICE_NAME:
            logger.info(f"Found device: {d.name} ({d.address})")
            return d
    return None

async def connect_and_control_device(address):
    """Connect to the device and demonstrate basic control."""
    try:
        async with BleakClient(address, timeout=20.0) as client:
            logger.info(f"Connected: {client.is_connected}")
            
            # Set up notification handler
            await client.start_notify(NOTIFY_CHAR_UUID, notification_handler)
            
            # Read battery level
            try:
                battery = await client.read_gatt_char(BATTERY_CHAR_UUID)
                logger.info(f"Battery level: {battery[0]}%")
            except Exception as e:
                logger.error(f"Could not read battery: {e}")
            
            # Example command: Set both channels to 0 intensity
            command = bytearray([
                0xB0,           # Command header
                0x30,           # Sequence 3 + absolute mode (0b0011 0000)
                0x00,           # Channel A intensity
                0x00,           # Channel B intensity
            ] + [0x00] * 16)    # Wave parameters (all zero for now)
            
            await client.write_gatt_char(WRITE_CHAR_UUID, command)
            logger.info("Sent zero intensity command")
            
            # Wait for response
            await asyncio.sleep(1)
            
            # Example: Set channel A to intensity 1
            command = bytearray([
                0xB0,           # Command header
                0x31,           # Sequence 3 + absolute mode (0b0011 0001)
                0x01,           # Channel A intensity
                0x00,           # Channel B intensity
            ] + [0x00] * 16)    # Wave parameters
            
            await client.write_gatt_char(WRITE_CHAR_UUID, command)
            logger.info("Set channel A to intensity 1")
            
            # Wait for response
            await asyncio.sleep(1)
            
            # Stop notifications before disconnecting
            await client.stop_notify(NOTIFY_CHAR_UUID)
            
    except Exception as e:
        logger.error(f"Error controlling device: {e}")

async def main():
    """Main function to run the Bluetooth test."""
    try:
        device = await scan_for_device()
        if device:
            logger.info("Found DG-LAB device, connecting...")
            await connect_and_control_device(device.address)
        else:
            logger.error(f"Device {DEVICE_NAME} not found")
                
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 