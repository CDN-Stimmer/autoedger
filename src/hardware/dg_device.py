import logging
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass
from PySide6.QtCore import QObject, Signal
import asyncio
from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from enum import Enum, IntEnum, auto

logger = logging.getLogger(__name__)

class Channel(IntEnum):
    """Channel identifiers."""
    A = 0
    B = 1

class StrengthMode(IntEnum):
    """Strength adjustment modes."""
    NO_CHANGE = 0b00
    RELATIVE_INCREASE = 0b01
    RELATIVE_DECREASE = 0b10
    ABSOLUTE = 0b11

@dataclass
class WaveParameters:
    """Wave parameters for a channel."""
    frequencies: List[int]  # 4 frequency values
    intensities: List[int]  # 4 intensity values

    def __post_init__(self):
        if len(self.frequencies) != 4 or len(self.intensities) != 4:
            raise ValueError("Must provide exactly 4 frequency and 4 intensity values")

class DGDevice(QObject):
    """DG-LAB Coyote V3 device controller."""
    
    DEVICE_NAME = "47L121000"
    SERVICE_UUID = "0000180C-0000-1000-8000-00805f9b34fb"
    WRITE_CHAR_UUID = "0000150A-0000-1000-8000-00805f9b34fb"
    NOTIFY_CHAR_UUID = "0000150B-0000-1000-8000-00805f9b34fb"
    BATTERY_SERVICE_UUID = "0000180A-0000-1000-8000-00805f9b34fb"
    BATTERY_CHAR_UUID = "00001500-0000-1000-8000-00805f9b34fb"
    
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds
    
    connection_changed = Signal(bool)  # Signal emitted when connection state changes

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._client: Optional[BleakClient] = None
        self._sequence_number = 0
        self._current_strengths = {Channel.A: 0, Channel.B: 0}
        self._wave_parameters = {
            Channel.A: WaveParameters(frequencies=[0]*4, intensities=[0]*4),
            Channel.B: WaveParameters(frequencies=[0]*4, intensities=[0]*4)
        }
        self._strength_callbacks: Dict[int, Callable] = {}
        self._battery_level = 0
        self._is_connected = False
        self._disconnect_requested = False
        self._is_connecting = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected and self._client and self._client.is_connected

    def _notification_handler(self, sender: int, data: bytearray):
        """Handle notifications from the device."""
        try:
            self.logger.debug(f"Read characteristic value")
            self.logger.debug(f"Read Characteristic {sender:08x}-0000-1000-8000-00805f9b34fb : {data}")
            
            # Handle battery level notifications
            if sender == int(self.BATTERY_CHAR_UUID.split('-')[0], 16):
                # Convert ASCII value to integer (e.g. 'Z' = 90%)
                level = ord(data.decode()) - ord('0')
                self._battery_level = level
                self.logger.debug(f"Battery level: {self._battery_level}%")
                
            # Handle strength notifications
            elif sender == int(self.NOTIFY_CHAR_UUID.split('-')[0], 16):
                if data[0] == 0xB1:  # Response to B0 command
                    sequence = (data[1] >> 4) & 0x0F
                    channel_a = data[2]
                    channel_b = data[3]
                    
                    # Only update strengths if they're different from what we expect
                    if channel_a != self._current_strengths[Channel.A] or channel_b != self._current_strengths[Channel.B]:
                        self._current_strengths[Channel.A] = channel_a
                        self._current_strengths[Channel.B] = channel_b
                        self.logger.debug(f"Strength update - A: {channel_a}, B: {channel_b}")
                    
                    # Call callback if exists
                    if sequence in self._strength_callbacks:
                        self._strength_callbacks[sequence](channel_a, channel_b)
                        del self._strength_callbacks[sequence]
                
        except Exception as e:
            self.logger.debug("peripheral_didUpdateValueForCharacteristic_error_")

    async def connect_device(self):
        """Connect to the DG device."""
        if self._is_connected or self._is_connecting:
            self.logger.info("Already connected or connecting, skipping connection attempt")
            return

        self._is_connecting = True
        try:
            self.logger.info("Starting device discovery...")
            devices = await BleakScanner.discover()
            self.logger.info(f"Found {len(devices)} BLE devices")
            
            for device in devices:
                self.logger.debug(f"Found device: {device.name} ({device.address})")
                if device.name == self.DEVICE_NAME:  # Only look for exact match
                    self.logger.info(f"Found DG device: {device.name} at address {device.address}")
                    self._client = BleakClient(device.address)
                    
                    # Connect to device
                    self.logger.info("Attempting to connect...")
                    await self._client.connect()
                    self.logger.info("Connected to BLE device")
                    
                    # Wait for services to be discovered
                    self.logger.info("Discovering services...")
                    services = await self._client.get_services()
                    self.logger.info(f"Services discovered: {[service.uuid for service in services]}")
                    
                    # Set up notification handler
                    self.logger.info("Enabling notifications...")
                    await self._client.start_notify(self.NOTIFY_CHAR_UUID, self._notification_handler)
                    self.logger.info("Notifications enabled")
                    
                    # Read initial battery level
                    try:
                        self.logger.info("Reading initial battery level...")
                        battery_data = await self._client.read_gatt_char(self.BATTERY_CHAR_UUID)
                        if battery_data:
                            self._battery_level = battery_data[0]
                            self.logger.info(f"Initial battery level: {self._battery_level}%")
                    except Exception as e:
                        self.logger.warning(f"Could not read battery level: {e}")
                    
                    # Only mark as connected after all setup is complete
                    self._is_connected = True
                    self.connection_changed.emit(True)
                    self.logger.info("DG device fully initialized")
                    return True

            self.logger.warning(f"Device {self.DEVICE_NAME} not found in scan results")
            return False

        except Exception as e:
            self.logger.error(f"Error connecting to DG device: {e}")
            self._is_connected = False
            self.connection_changed.emit(False)
            return False
        finally:
            self._is_connecting = False

    async def disconnect(self):
        """Disconnect from the DG device."""
        if not self._is_connected:
            return

        try:
            await self._client.disconnect()
            self._is_connected = False
            self.connection_changed.emit(False)
            self.logger.info("Disconnected from DG device")
        except Exception as e:
            self.logger.error(f"Error disconnecting from DG device: {e}")
        finally:
            self._client = None

    def _get_next_sequence(self) -> int:
        """Get next sequence number (0-15)."""
        self._sequence_number = (self._sequence_number + 1) & 0x0F
        return self._sequence_number

    async def set_strength(self, channel: Channel, strength: int, 
                         mode: StrengthMode = StrengthMode.ABSOLUTE,
                         callback: Optional[Callable] = None) -> bool:
        """Set channel strength."""
        if not self.is_connected:
            return False

        try:
            sequence = self._get_next_sequence()
            if callback:
                self._strength_callbacks[sequence] = callback

            # Prepare command
            command = bytearray([
                0xB0,  # Command header
                (sequence << 4) | (mode << 2 if channel == Channel.A else mode),  # Sequence + mode
                strength if channel == Channel.A else self._current_strengths[Channel.A],  # Channel A
                strength if channel == Channel.B else self._current_strengths[Channel.B],  # Channel B
            ])

            # Add wave parameters
            for ch in [Channel.A, Channel.B]:
                command.extend(self._wave_parameters[ch].frequencies)
                command.extend(self._wave_parameters[ch].intensities)

            await self._client.write_gatt_char(self.WRITE_CHAR_UUID, command)
            return True

        except Exception as e:
            logger.error(f"Error setting strength: {e}")
            return False

    async def set_wave_parameters(self, channel: Channel, wave_params: WaveParameters) -> bool:
        """Set wave parameters for a channel."""
        if not self.is_connected:
            return False

        try:
            self._wave_parameters[channel] = wave_params
            # Send command to update with current strengths
            return await self.set_strength(
                channel,
                self._current_strengths[channel],
                StrengthMode.ABSOLUTE
            )

        except Exception as e:
            logger.error(f"Error setting wave parameters: {e}")
            return False

    async def audio_to_pattern(self, audio_data, channel: Channel) -> bool:
        """Convert audio data to device pattern and send it.
        This is a placeholder - we'll implement the actual audio processing logic later.
        """
        # TODO: Implement audio processing
        # For now, just a simple example that sets intensity based on audio level
        try:
            # Placeholder: Convert audio amplitude to frequency/intensity
            max_amp = max(abs(min(audio_data)), abs(max(audio_data)))
            intensity = int(max_amp * 100)  # Scale to 0-100
            
            wave_params = WaveParameters(
                frequencies=[40, 40, 40, 40],  # Fixed frequency for now
                intensities=[intensity] * 4     # Use audio level for intensity
            )
            
            return await self.set_wave_parameters(channel, wave_params)

        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            return False

    @property
    def battery_level(self) -> int:
        """Get current battery level."""
        return self._battery_level

    def get_channel_strength(self, channel: Channel) -> int:
        """Get current channel strength."""
        return self._current_strengths[channel] 