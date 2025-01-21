import asyncio
import logging
from dg_device import DGDevice, Channel, StrengthMode, WaveParameters
import numpy as np

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def strength_callback(channel_a: int, channel_b: int):
    """Callback for strength updates."""
    logger.info(f"Strength callback - Channel A: {channel_a}, Channel B: {channel_b}")

async def test_device():
    """Test basic device functionality."""
    device = DGDevice()
    
    try:
        # Connect to device
        if not await device.connect_device():
            logger.error("Failed to connect")
            return
        
        logger.info(f"Battery level: {device.battery_level}%")
        
        # Test basic strength control
        logger.info("Setting channel A to strength 1...")
        await device.set_strength(
            Channel.A, 1,
            mode=StrengthMode.ABSOLUTE,
            callback=strength_callback
        )
        await asyncio.sleep(1)
        
        # Test wave parameters
        logger.info("Testing wave parameters...")
        wave_params = WaveParameters(
            frequencies=[30, 35, 40, 45],  # Different frequencies
            intensities=[20, 25, 30, 35]   # Different intensities
        )
        await device.set_wave_parameters(Channel.A, wave_params)
        await asyncio.sleep(2)
        
        # Test audio pattern
        logger.info("Testing audio pattern conversion...")
        # Generate a simple sine wave as test audio
        sample_rate = 44100
        duration = 0.1  # seconds
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = np.sin(2 * np.pi * 440 * t)  # 440 Hz sine wave
        
        await device.audio_to_pattern(audio_data, Channel.A)
        await asyncio.sleep(2)
        
        # Set both channels to 0 before disconnecting
        logger.info("Setting channels to 0...")
        await device.set_strength(Channel.A, 0)
        await device.set_strength(Channel.B, 0)
        await asyncio.sleep(1)
        
    finally:
        # Always disconnect
        await device.disconnect()
        logger.info("Test complete")

if __name__ == "__main__":
    asyncio.run(test_device()) 