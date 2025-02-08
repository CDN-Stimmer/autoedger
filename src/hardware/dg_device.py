import logging
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass
from PySide6.QtCore import QObject, Signal, QTimer
import asyncio
from bleak import BleakClient, BleakScanner, BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from enum import Enum, IntEnum, auto
import time
import numpy as np

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

class ChannelState:
    """Represents the state of a single channel."""
    def __init__(self):
        self.enabled = False
        self.strength = 0
        self.wave_params = WaveParameters(
            frequencies=[15, 15, 15, 15],
            intensities=[0, 0, 0, 0]
        )
        self.last_update = 0

class DGDevice(QObject):
    """DG-LAB Coyote V3 device controller."""
    
    # Service and Characteristic UUIDs
    SERVICE_UUID = "180C"
    WRITE_CHAR_UUID = "150A"
    NOTIFY_CHAR_UUID = "150B"
    
    # Timing constants
    COMMAND_DELAY = 0.3  # Increased from 0.2
    CONNECT_TIMEOUT = 15.0  # Increased from 10.0
    RETRY_DELAY = 1.0  # Increased from 0.5
    MAX_RETRIES = 5  # Increased from 3
    SERVICE_DISCOVERY_TIMEOUT = 10.0  # Increased from 5.0
    CHARACTERISTIC_DISCOVERY_TIMEOUT = 5.0  # Increased from 3.0
    MTU_SIZE = 512  # Added MTU size
    
    # Connection parameters
    CONNECTION_INTERVAL_MIN = 15  # 18.75ms (15 * 1.25ms)
    CONNECTION_INTERVAL_MAX = 30  # 37.5ms (30 * 1.25ms)
    SUPERVISION_TIMEOUT = 500  # 5 seconds (500 * 10ms)
    SLAVE_LATENCY = 0
    
    # Signals
    connection_changed = Signal(bool)
    strength_changed = Signal(Channel, int)
    battery_level_changed = Signal(int)
    devices_discovered = Signal(list)
    connection_error = Signal(str)
    
    def __init__(self):
        """Initialize the device controller."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._target_device = None
        self._client = None
        self._write_char = None
        self._notify_char = None
        self._is_connected = False
        self._battery_level = 0
        self._discovered_devices = []
        self._discovery_in_progress = False
        self._last_command_time = 0
        self._consecutive_errors = 0
        self._recovery_attempts = 0
        self._last_recovery_time = 0
        self._sequence_number = 0  # Add sequence number initialization
        self.channels = {
            Channel.A: ChannelState(),
            Channel.B: ChannelState()
        }
        self._connect_lock = asyncio.Lock()
        self._command_lock = asyncio.Lock()
        self._last_connect_attempt = 0
        self._connect_attempts = 0
        self._max_connect_attempts = 5
        self._min_connect_delay = 2.0  # Minimum time between connect attempts

    @property
    def target_device(self) -> Optional[BLEDevice]:
        """Get the target device."""
        return self._target_device

    @target_device.setter
    def target_device(self, device: Optional[BLEDevice]):
        """Set the target device."""
        self._target_device = device

    @property
    def is_connected(self) -> bool:
        """Get the connection state."""
        return self._is_connected

    async def connect_to_device(self, device: BLEDevice) -> bool:
        """Connect to a BLE device."""
        if self._discovery_in_progress:
            if hasattr(self, 'logger'):
                self.logger.warning("Discovery in progress, stopping before connect")
            await self.stop_discovery()
            
        try:
            async with self._connect_lock:
                current_time = time.time()
                
                # Check if we need to wait before attempting connection
                if (current_time - self._last_connect_attempt) < self._min_connect_delay:
                    await asyncio.sleep(self._min_connect_delay)
                    
                # Update connection attempt tracking
                self._last_connect_attempt = time.time()
                self._connect_attempts += 1
                
                if self._connect_attempts > self._max_connect_attempts:
                    error_msg = "Maximum connection attempts reached"
                    if hasattr(self, 'logger'):
                        self.logger.error(error_msg)
                    self.connection_error.emit(error_msg)
                    return False
                    
                # Store the target device
                self._target_device = device
                if hasattr(self, 'logger'):
                    self.logger.info(f"Attempting to connect to {device.name or device.address}")
                
                # Disconnect if already connected
                if self._client and self._client.is_connected:
                    await self.disconnect()
                    await asyncio.sleep(1.0)  # Wait before reconnecting
                    
                # Create new client with timeout
                self._client = BleakClient(
                    device,
                    timeout=self.CONNECT_TIMEOUT,
                    disconnected_callback=self._handle_disconnect
                )
                
                # Attempt connection with retry
                for attempt in range(self.MAX_RETRIES):
                    try:
                        await self._client.connect()
                        if hasattr(self, 'logger'):
                            self.logger.info("Connected to device")
                        break
                    except Exception as e:
                        if attempt == self.MAX_RETRIES - 1:
                            raise
                        if hasattr(self, 'logger'):
                            self.logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                        await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                        
                # Request larger MTU
                try:
                    await self._client.request_mtu(self.MTU_SIZE)
                    if hasattr(self, 'logger'):
                        self.logger.debug(f"Requested MTU size: {self.MTU_SIZE}")
                except Exception as e:
                    if hasattr(self, 'logger'):
                        self.logger.warning(f"Failed to set MTU: {e}")
                    
                # Get service
                services = await asyncio.wait_for(
                    self._client.get_services(),
                    timeout=self.SERVICE_DISCOVERY_TIMEOUT
                )
                service = services.get_service(self.SERVICE_UUID)
                if not service:
                    error_msg = f"Service {self.SERVICE_UUID} not found"
                    if hasattr(self, 'logger'):
                        self.logger.error(error_msg)
                    raise Exception(error_msg)
                    
                # Get characteristics
                self._write_char = service.get_characteristic(self.WRITE_CHAR_UUID)
                self._notify_char = service.get_characteristic(self.NOTIFY_CHAR_UUID)
                
                if not self._write_char or not self._notify_char:
                    error_msg = "Required characteristics not found"
                    if hasattr(self, 'logger'):
                        self.logger.error(error_msg)
                    raise Exception(error_msg)
                    
                # Start notifications with retry
                for attempt in range(self.MAX_RETRIES):
                    try:
                        await self._client.start_notify(
                            self._notify_char,
                            self._notification_handler
                        )
                        if hasattr(self, 'logger'):
                            self.logger.debug("Started notifications")
                        break
                    except Exception as e:
                        if attempt == self.MAX_RETRIES - 1:
                            raise
                        if hasattr(self, 'logger'):
                            self.logger.warning(f"Notification setup attempt {attempt + 1} failed: {e}")
                        await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                        
                self._is_connected = True
                self._connect_attempts = 0  # Reset attempt counter on success
                self.connection_changed.emit(True)
                
                # Restore channel states if they were enabled
                for channel, state in self.channels.items():
                    if state.enabled:
                        await self.set_strength(channel, state.strength)
                        await self.set_wave_parameters(channel, state.wave_params)
                
                if hasattr(self, 'logger'):
                    self.logger.info("Device connection completed successfully")
                return True
                
        except Exception as e:
            error_msg = f"Connection error: {str(e)}"
            if hasattr(self, 'logger'):
                self.logger.error(error_msg)
            self.connection_error.emit(error_msg)
            self._is_connected = False
            return False
            
        finally:
            self._discovery_in_progress = False

    async def disconnect(self):
        """Disconnect from the device."""
        if not self._client:
            return
            
        try:
            # Reset channel states
            for state in self.channels.values():
                state.enabled = False
                state.strength = 0
                
            if self._client.is_connected:
                await self._client.disconnect()
                
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"Error disconnecting: {e}")
        finally:
            self._client = None
            self._write_char = None
            self._notify_char = None
            self.connection_changed.emit(False)

    def _handle_disconnect(self, client):
        """Handle unexpected disconnection."""
        if hasattr(self, 'logger'):
            self.logger.warning("Device disconnected")
        self._client = None
        self._write_char = None
        self._notify_char = None
        
        self.connection_changed.emit(False)
        
        # Attempt reconnection if we have a target device
        if self._target_device:
            asyncio.create_task(self.reconnect())

    def _notification_handler(self, char: BleakGATTCharacteristic, data: bytearray):
        """Handle notifications from the device."""
        try:
            if len(data) < 2:
                return
                
            notification_type = data[0]
            
            if notification_type == 0xB1 and len(data) >= 4:  # Strength update
                status = data[1]
                strength_a = data[2]
                strength_b = data[3]
                
                # Update channel A state
                if strength_a > 0:
                    self.channels[Channel.A].enabled = True
                self.channels[Channel.A].strength = strength_a
                self.strength_changed.emit(Channel.A, strength_a)
                
                # Update channel B state
                if strength_b > 0:
                    self.channels[Channel.B].enabled = True
                self.channels[Channel.B].strength = strength_b
                self.strength_changed.emit(Channel.B, strength_b)
                
                # Update last successful update time
                for channel in self.channels.values():
                    channel.last_update = time.time()
                
            elif notification_type == 0x51 and len(data) >= 2:  # Battery level
                level = data[1]
                self._battery_level = level
                self.battery_level_changed.emit(level)
                
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"Error handling notification: {e}")

    async def set_strength(self, channel: Channel, strength: int) -> bool:
        """Set the strength for a channel."""
        if not self.is_connected:
            return False
            
        try:
            async with self._command_lock:
                # Ensure proper timing between commands
                current_time = time.time()
                time_since_last = current_time - self._last_command_time
                if time_since_last < self.COMMAND_DELAY:
                    await asyncio.sleep(self.COMMAND_DELAY - time_since_last)
                
                # Clamp strength value
                strength = max(0, min(100, int(strength)))
                
                # Update channel state
                self.channels[channel].enabled = strength > 0
                self.channels[channel].strength = strength
                
                # Create command
                seq = self._sequence_number = (self._sequence_number + 1) & 0x0F
                command = bytearray([
                    0xB0,  # Command header
                    (seq << 4) | (0b1100 if channel == Channel.A else 0b0011),  # Sequence and mode
                    strength if channel == Channel.A else self.channels[Channel.A].strength,  # A strength
                    strength if channel == Channel.B else self.channels[Channel.B].strength,  # B strength
                ])
                
                # Add current wave parameters
                for ch in [Channel.A, Channel.B]:
                    command.extend(self.channels[ch].wave_params.frequencies)
                    command.extend(self.channels[ch].wave_params.intensities)
                
                # Send command with retries and increasing delays
                for attempt in range(self.MAX_RETRIES):
                    try:
                        await self._client.write_gatt_char(self._write_char.uuid, command)
                        self._last_command_time = time.time()
                        self.channels[channel].last_update = time.time()
                        return True
                        
                    except Exception as e:
                        if attempt < self.MAX_RETRIES - 1:
                            # Exponential backoff
                            await asyncio.sleep(self.RETRY_DELAY * (2 ** attempt))
                            continue
                        raise
                        
                return False
                
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"Error setting strength for channel {channel}: {e}")
            return False

    async def set_wave_parameters(self, channel: Channel, params: WaveParameters) -> bool:
        """Set wave parameters for a channel."""
        if not self.is_connected:
            return False
            
        try:
            async with self._command_lock:
                # Ensure proper timing between commands
                current_time = time.time()
                time_since_last = current_time - self._last_command_time
                if time_since_last < self.COMMAND_DELAY:
                    await asyncio.sleep(self.COMMAND_DELAY - time_since_last)
                
                # Create command
                seq = self._sequence_number = (self._sequence_number + 1) & 0x0F
                command = bytearray([
                    0xB0,  # Command header
                    seq << 4,  # Sequence number
                    self.channels[Channel.A].strength,
                    self.channels[Channel.B].strength,
                ])
                
                # Add wave parameters
                if channel == Channel.A:
                    command.extend(params.frequencies)
                    command.extend(params.intensities)
                    command.extend(self.channels[Channel.B].wave_params.frequencies)
                    command.extend(self.channels[Channel.B].wave_params.intensities)
                else:
                    command.extend(self.channels[Channel.A].wave_params.frequencies)
                    command.extend(self.channels[Channel.A].wave_params.intensities)
                    command.extend(params.frequencies)
                    command.extend(params.intensities)
                
                # Send command with retries
                for attempt in range(self.MAX_RETRIES):
                    try:
                        await self._client.write_gatt_char(self._write_char.uuid, command)
                        self._last_command_time = time.time()
                        
                        # Update channel state
                        self.channels[channel].wave_params = params
                        self.channels[channel].last_update = time.time()
                        return True
                        
                    except Exception as e:
                        if attempt < self.MAX_RETRIES - 1:
                            await asyncio.sleep(self.RETRY_DELAY)
                            continue
                        raise
                        
                return False
                
        except Exception as e:
            self.logger.error(f"Error setting wave parameters for channel {channel}: {e}")
            return False

    async def scan_devices(self) -> List[BLEDevice]:
        """Scan for available DG-LAB devices."""
        try:
            self.logger.info("Starting device discovery...")
            discovered = []
            
            def _device_found(device, advertisement_data):
                if device.name and device.name.startswith("47L"):
                    # Check if device is already in list
                    if not any(d.address == device.address for d in discovered):
                        self.logger.debug(f"Found device: {device.name} ({device.address})")
                        discovered.append(device)
                        self.devices_discovered.emit(discovered.copy())
                        
            async with BleakScanner(_device_found) as scanner:
                await asyncio.sleep(5.0)  # Scan for 5 seconds
                
            if not discovered:
                self.logger.warning("No DG-LAB devices found")
            else:
                self.logger.info(f"Found {len(discovered)} DG-LAB devices")
                
            self._discovered_devices = discovered
            return discovered
            
        except Exception as e:
            self.logger.error(f"Error scanning for devices: {e}")
            return []

    @property
    def battery_level(self) -> int:
        """Get current battery level."""
        return self._battery_level

    def get_channel_strength(self, channel: Channel) -> int:
        """Get current channel strength."""
        return self.channels[channel].strength

    async def audio_to_pattern(self, audio_data, channel: Channel) -> bool:
        """Convert audio data to device pattern and send it."""
        if not self.is_connected:
            self.logger.error("Cannot process audio - device not connected")
            return False
            
        try:
            if not audio_data or len(audio_data) == 0:
                self.logger.warning("No audio data to process")
                return False
                
            # Process audio data in chunks for smoother output
            chunk_size = min(len(audio_data), 1024)  # Process max 1024 samples at a time
            chunks = [audio_data[i:i + chunk_size] for i in range(0, len(audio_data), chunk_size)]
            
            # Calculate frequency and intensity values from audio
            frequencies = []
            intensities = []
            
            for chunk in chunks[:4]:  # Use up to 4 chunks for the 4 pattern slots
                # Calculate RMS amplitude for intensity (ensure proper scaling 0-100)
                rms = np.sqrt(np.mean(np.square(chunk)))
                # Scale RMS to 0-100 range with better curve
                intensity = int(min(100, max(0, (1 - np.exp(-5 * rms)) * 100)))
                
                # Calculate dominant frequency (simple zero-crossing method)
                zero_crossings = np.where(np.diff(np.signbit(chunk)))[0]
                if len(zero_crossings) > 1:
                    avg_period = (zero_crossings[-1] - zero_crossings[0]) / (len(zero_crossings) - 1)
                    # Map frequency to 15-100Hz range with better curve
                    raw_freq = 44100 / (2 * avg_period)  # Assuming 44.1kHz sample rate
                    freq = int(min(100, max(15, 15 + (raw_freq / 1000) * 85)))
                else:
                    freq = 15  # Default frequency if can't detect
                    
                frequencies.append(freq)
                intensities.append(intensity)
                
                self.logger.debug(f"Chunk stats - RMS: {rms:.3f}, Intensity: {intensity}, Freq: {freq}Hz")
            
            # Pad with defaults if we have less than 4 chunks
            while len(frequencies) < 4:
                frequencies.append(15)
                intensities.append(40)
                
            wave_params = WaveParameters(
                frequencies=frequencies,
                intensities=intensities
            )
            
            self.logger.debug(f"Audio pattern - Frequencies: {frequencies}, Intensities: {intensities}")
            return await self.set_wave_parameters(channel, wave_params)

        except Exception as e:
            self.logger.error(f"Error processing audio: {e}")
            return False

    async def _on_playback_started(self):
        """Handle playback started."""
        if not self.is_connected:
            return
            
        try:
            # Initialize both channels with very conservative parameters first
            initial_params = WaveParameters(
                frequencies=[1] * 4,    # Start with minimum frequency
                intensities=[20] * 4    # Start with very low intensity
            )
            
            # Set initial parameters for both channels
            for channel in [Channel.A, Channel.B]:
                # Set wave parameters first
                await self.set_wave_parameters(channel, initial_params)
                await asyncio.sleep(0.2)  # Consistent delay
                
                # Then set initial strength
                await self.set_strength(channel, 20)  # Start with very low strength
                await asyncio.sleep(0.2)  # Consistent delay
                
            # Now ramp up to conservative parameters
            normal_params = WaveParameters(
                frequencies=[20] * 4,   # Low frequency
                intensities=[50] * 4    # Low-medium intensity
            )
            
            # Set normal parameters for both channels
            for channel in [Channel.A, Channel.B]:
                await self.set_wave_parameters(channel, normal_params)
                await asyncio.sleep(0.2)  # Consistent delay
                await self.set_strength(channel, 50)  # Low-medium strength
                await asyncio.sleep(0.2)  # Consistent delay
                
        except Exception as e:
            self.logger.error(f"Error in playback start: {e}")
            
    async def _on_playback_stopped(self):
        """Handle playback stopped."""
        if not self.is_connected:
            return
            
        try:
            # Set both channels to 0 strength
            for channel in [Channel.A, Channel.B]:
                await self.set_strength(channel, 0)
                await asyncio.sleep(0.3)  # Delay between channels
                
        except Exception as e:
            self.logger.error(f"Error in playback stop: {e}")

    async def start_discovery(self):
        """Start scanning for BLE devices."""
        self.logger.info("Starting device discovery...")
        try:
            self._discovered_devices = []  # Clear previous discoveries
            devices = await self.scan_devices()
            if devices:
                self.logger.info(f"Found {len(devices)} devices")
                self._discovered_devices = devices
                self.devices_discovered.emit(devices)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error starting device discovery: {e}")
            return False

    async def stop_discovery(self):
        """Stop scanning for BLE devices."""
        self.logger.info("Stopping device discovery...")
        try:
            async with self._scan_lock:
                # BleakScanner automatically stops after discovery
                # but we'll keep this method for symmetry and future use
                return True
        except Exception as e:
            self.logger.error(f"Error stopping device discovery: {e}")
            return False

    @property
    def discovered_devices(self) -> List[BLEDevice]:
        """Get the list of discovered devices."""
        return self._discovered_devices.copy() if self._discovered_devices else []

    async def reconnect(self):
        """Attempt to reconnect to the last known device."""
        if not self._target_device:
            if hasattr(self, 'logger'):
                self.logger.error("No target device available for reconnection")
            return False
            
        if self._discovery_in_progress:
            if hasattr(self, 'logger'):
                self.logger.warning("Discovery in progress, stopping before reconnect")
            await self.stop_discovery()
            
        if hasattr(self, 'logger'):
            self.logger.info(f"Attempting to reconnect to {self._target_device.address}")
            
        return await self.connect_to_device(self._target_device) 