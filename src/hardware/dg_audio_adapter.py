from PySide6.QtCore import QObject, Slot, QTimer
import asyncio
import qasync
from typing import List, Set, Optional
import logging
from .dg_device import DGDevice, Channel, WaveParameters
from collections import deque
import time
from dataclasses import dataclass
from math import log
from enum import Enum, auto

class CommandType(Enum):
    SET_STRENGTH = auto()
    SET_WAVE = auto()

@dataclass
class Command:
    type: CommandType
    channel: 'Channel'  # Forward reference
    value: Optional[int] = None
    wave_params: Optional['WaveParameters'] = None  # Forward reference

@dataclass
class QueuedCommand:
    """Represents a command queued for sending to the device."""
    params: WaveParameters
    timestamp: float
    channels: Set[Channel]

class DGAudioAdapter(QObject):
    """Adapter to connect QtAudioPlayer to DGDevice."""
    
    # Timing constants
    MIN_COMMAND_INTERVAL = 0.3  # Increased from 0.2
    MAX_QUEUE_SIZE = 3  # Reduced from 5
    RECOVERY_CHECK_INTERVAL = 15.0  # Increased from 10.0
    MAX_ERRORS_BEFORE_RECONNECT = 10  # Increased from 5
    MAX_RECOVERY_ATTEMPTS = 5  # Increased from 3
    COMMAND_BATCH_SIZE = 2  # Reduced from 3
    COMMAND_BATCH_INTERVAL = 0.2  # Increased from 0.1
    
    def __init__(self, audio_player, logger):
        """Initialize the adapter."""
        super().__init__()
        self.logger = logger
        self.audio_player = audio_player
        self.device = DGDevice()
        
        # State management
        self._enabled = False
        self._is_playing = False
        self._has_audio = False
        self._sync_enabled = False
        self._enabled_channels = set()
        self._command_queue = asyncio.Queue(maxsize=self.MAX_QUEUE_SIZE)
        self._command_processor_task = None
        self._last_command_time = 0
        self._last_successful_update = time.time()
        self._consecutive_errors = 0
        self._recovery_attempts = 0
        self._last_recovery_time = 0
        self._command_batch = []
        self._last_batch_time = 0
        self._last_audio_update = 0
        self._audio_update_interval = 0.1  # 100ms between audio updates
        
        # Audio processing parameters
        self.base_intensity_scale = 100
        self.intensity_pulse_range = 50
        self.min_frequency = 10
        self.max_frequency = 1000
        
        # Connect signals
        self.device.connection_changed.connect(self._on_connection_changed)
        self.device.connection_error.connect(self._on_connection_error)
        self.audio_player.audio_data_ready.connect(self._on_audio_data)
        self.audio_player.playback_started.connect(self._on_playback_started)
        self.audio_player.playback_stopped.connect(self._on_playback_stopped)
        
        # Set up command processing timer
        self._queue_timer = QTimer()
        self._queue_timer.setInterval(100)  # Process queue every 100ms
        self._queue_timer.timeout.connect(self._process_queue_timer)
        
        # Set up recovery timer
        self._recovery_timer = QTimer()
        self._recovery_timer.setInterval(5000)  # Check every 5 seconds
        self._recovery_timer.timeout.connect(self._check_recovery)
        self._recovery_timer.start()

    @property
    def sync_enabled(self) -> bool:
        """Get sync mode state."""
        return self._sync_enabled

    @sync_enabled.setter
    def sync_enabled(self, value: bool):
        """Set sync mode state."""
        self._sync_enabled = value
        self.logger.info(f"Sync mode {'enabled' if value else 'disabled'}")
        if value and self._is_playing and Channel.B in self._enabled_channels:
            params = self.device.channels[Channel.A].wave_params
            strength = self.device.channels[Channel.A].strength
            asyncio.create_task(self.device.set_wave_parameters(Channel.B, params))
            asyncio.create_task(self.device.set_strength(Channel.B, strength))

    @Slot(bool)
    def _on_connection_changed(self, connected: bool):
        """Handle device connection changes."""
        if connected:
            self.logger.info("Device connected")
            self._consecutive_errors = 0
            self._recovery_attempts = 0
            self._last_recovery_time = 0
            self._start_command_processor()
            
            # Upon connection, restore channel settings if playback is active
            if self._is_playing:
                asyncio.create_task(self._restore_channels())
        else:
            self.logger.warning("Device disconnected")
            self._stop_command_processor()
            self._command_queue = asyncio.Queue(maxsize=self.MAX_QUEUE_SIZE)  # Create new queue
            self._command_batch.clear()
            self._last_command_time = 0
            self._last_successful_update = time.time()

    @Slot(str)
    def _on_connection_error(self, error_msg: str):
        """Handle connection errors."""
        self.logger.error(f"Connection error: {error_msg}")
        self._consecutive_errors += 1
        
        # Only attempt recovery if we have multiple consecutive errors
        if self._consecutive_errors >= 3:
            asyncio.create_task(self._attempt_recovery())
            
        # If we have too many errors, try reconnecting
        if self._consecutive_errors >= self.MAX_ERRORS_BEFORE_RECONNECT:
            self.logger.error("Too many errors, attempting reconnect")
            asyncio.create_task(self.device.reconnect())
            self._consecutive_errors = 0  # Reset error count

    def _start_command_processor(self):
        """Start the command processor task."""
        if self._command_processor_task is None or self._command_processor_task.done():
            self._command_processor_task = asyncio.create_task(self._process_command_queue())
            self._queue_timer.start()
            
    def _stop_command_processor(self):
        """Stop the command processor task."""
        if self._command_processor_task and not self._command_processor_task.done():
            self._command_processor_task.cancel()
        self._queue_timer.stop()
        
    @Slot()
    def _process_queue_timer(self):
        """Handle queue timer timeout."""
        if not self._command_processor_task or self._command_processor_task.done():
            self._start_command_processor()

    @Slot(float, float)
    def _on_audio_data(self, amplitude: float, frequency: float):
        """Handle incoming audio data."""
        if not self.device.is_connected or not self._enabled or not self._is_playing:
            return
            
        try:
            # Limit update rate
            current_time = time.time()
            if current_time - self._last_audio_update < self._audio_update_interval:
                return
                
            self._last_audio_update = current_time
            
            # Update audio state
            self._has_audio = amplitude > 0
            
            # Only process if queue is not too full
            if self._command_queue.qsize() >= self.MAX_QUEUE_SIZE * 0.8:
                return
                
            # Scale frequency to device range (1-50 Hz)
            scaled_frequency = max(1, min(50, int(frequency / 20)))
            
            # Scale amplitude to intensity (0-255)
            scaled_intensity = max(0, min(255, int(amplitude * 255)))
            
            # Create wave parameters
            params = WaveParameters(
                frequencies=[scaled_frequency] * 4,
                intensities=[scaled_intensity] * 4
            )
            
            # Update enabled channels
            if self._has_audio:
                for channel in self._enabled_channels:
                    if channel == Channel.A or not self._sync_enabled:
                        asyncio.create_task(self.set_wave_parameters(channel, params))
                        asyncio.create_task(self.set_channel_strength(channel, scaled_intensity))
                    elif channel == Channel.B and self._sync_enabled and Channel.A in self._enabled_channels:
                        # In sync mode, B mirrors A's parameters
                        asyncio.create_task(self.set_wave_parameters(channel, params))
                        asyncio.create_task(self.set_channel_strength(channel, scaled_intensity))
                        
                # Update last successful update time and reset error count
                self._last_successful_update = time.time()
                self._consecutive_errors = 0
            else:
                # No audio - set strengths to 0
                for channel in self._enabled_channels:
                    asyncio.create_task(self.set_channel_strength(channel, 0))
                        
        except Exception as e:
            self.logger.error(f"Error processing audio data: {e}")
            self._consecutive_errors += 1
            
            # Only attempt recovery if we have multiple consecutive errors
            if self._consecutive_errors >= 3:
                asyncio.create_task(self._attempt_recovery())

    async def _attempt_recovery(self):
        """Attempt to recover from errors."""
        try:
            current_time = time.time()
            
            # Check if we've tried recovery too recently
            if current_time - self._last_recovery_time < 5.0:
                return
                
            self._last_recovery_time = current_time
            self._recovery_attempts += 1
            
            self.logger.info(f"Attempting recovery (attempt {self._recovery_attempts})")
            
            # If we have too many errors or recovery attempts, try reconnecting
            if (self._consecutive_errors >= self.MAX_ERRORS_BEFORE_RECONNECT or 
                self._recovery_attempts >= self.MAX_RECOVERY_ATTEMPTS):
                self.logger.warning("Recovery threshold reached, attempting reconnect")
                await self.device.reconnect()
                self._recovery_attempts = 0
                self._consecutive_errors = 0
                return
                
            # Otherwise try resetting channels
            for channel in self._enabled_channels:
                success = await self.reset_channel(channel)
                if success:
                    self.logger.info(f"Successfully reset channel {channel}")
                    self._consecutive_errors = 0
                else:
                    self.logger.warning(f"Failed to reset channel {channel}")
                    
        except Exception as e:
            self.logger.error(f"Recovery attempt failed: {e}")

    async def _process_command_queue(self):
        """Process commands in the queue."""
        while True:
            try:
                if not self.device.is_connected:
                    await asyncio.sleep(0.5)
                    continue
                    
                # Get command with timeout
                try:
                    command = await asyncio.wait_for(self._command_queue.get(), timeout=0.2)
                except asyncio.TimeoutError:
                    continue
                    
                # Add command to batch
                self._command_batch.append(command)
                
                # Process batch if it's full or enough time has passed
                current_time = time.time()
                if (len(self._command_batch) >= self.COMMAND_BATCH_SIZE or 
                    (current_time - self._last_batch_time) >= self.COMMAND_BATCH_INTERVAL):
                    
                    # Process all commands in batch
                    for cmd in self._command_batch:
                        # Ensure minimum time between commands
                        time_since_last = current_time - self._last_command_time
                        if time_since_last < self.MIN_COMMAND_INTERVAL:
                            await asyncio.sleep(self.MIN_COMMAND_INTERVAL - time_since_last)
                        
                        success = False
                        try:
                            if cmd.type == CommandType.SET_STRENGTH:
                                success = await self.device.set_strength(cmd.channel, cmd.value)
                            elif cmd.type == CommandType.SET_WAVE:
                                success = await self.device.set_wave_parameters(cmd.channel, cmd.wave_params)
                                
                            if success:
                                self._last_command_time = time.time()
                                self._last_successful_update = time.time()
                                self._consecutive_errors = 0
                            else:
                                self._consecutive_errors += 1
                                await asyncio.sleep(0.2)
                                
                        except Exception as e:
                            self.logger.error(f"Command processing error: {e}")
                            self._consecutive_errors += 1
                            await asyncio.sleep(0.2)
                            
                        finally:
                            self._command_queue.task_done()
                            
                    # Clear batch and update time
                    self._command_batch.clear()
                    self._last_batch_time = current_time
                    
                    # Check if we need recovery
                    if self._consecutive_errors >= 3:
                        asyncio.create_task(self._attempt_recovery())
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Command processor error: {e}")
                await asyncio.sleep(0.5)

    async def set_channel_strength(self, channel: Channel, strength: int):
        """Queue a strength command."""
        try:
            command = Command(
                type=CommandType.SET_STRENGTH,
                channel=channel,
                value=strength
            )
            await self._command_queue.put(command)
        except Exception as e:
            self.logger.error(f"Error queueing strength command: {e}")
            
    async def set_wave_parameters(self, channel: Channel, params: WaveParameters):
        """Queue a wave parameters command."""
        try:
            command = Command(
                type=CommandType.SET_WAVE,
                channel=channel,
                wave_params=params
            )
            await self._command_queue.put(command)
        except Exception as e:
            self.logger.error(f"Error queueing wave parameters command: {e}")

    def start(self):
        """Start the adapter."""
        self._enabled = True
        self._is_playing = False
        self._has_audio = False
        self._enabled_channels.clear()

    def stop(self):
        """Stop the adapter."""
        self._enabled = False
        self._is_playing = False
        self._has_audio = False
        
        # Disable all channels
        for channel in [Channel.A, Channel.B]:
            asyncio.create_task(self.set_channel_strength(channel, 0))
        
        self._enabled_channels.clear()

    @Slot()
    async def _on_playback_started(self):
        """Handle playback started."""
        self._is_playing = True
        self._has_audio = False
        
        # Initialize enabled channels with safe parameters
        for channel in self._enabled_channels:
            params = WaveParameters(
                frequencies=[15] * 4,
                intensities=[0] * 4
            )
            await self.set_wave_parameters(channel, params)
            await self.set_channel_strength(channel, 0)

    @Slot()
    async def _on_playback_stopped(self):
        """Handle playback stopped."""
        self._is_playing = False
        self._has_audio = False
        
        # Disable all channels
        for channel in [Channel.A, Channel.B]:
            await self.set_channel_strength(channel, 0)

    def enable_channel(self, channel: Channel):
        """Enable a channel."""
        if channel not in self._enabled_channels:
            self._enabled_channels.add(channel)
            self.logger.info(f"Channel {channel} enabled")

    def disable_channel(self, channel: Channel):
        """Disable a channel."""
        if channel in self._enabled_channels:
            self._enabled_channels.remove(channel)
            asyncio.create_task(self.set_channel_strength(channel, 0))
            self.logger.info(f"Channel {channel} disabled")

    @property
    def enabled_channels(self) -> set:
        """Get the set of enabled channels."""
        return self._enabled_channels.copy()

    @enabled_channels.setter
    def enabled_channels(self, channels: set):
        """Set the enabled channels."""
        # Disable channels that are no longer enabled
        for channel in self._enabled_channels - set(channels):
            self.disable_channel(channel)
        
        # Enable new channels
        for channel in set(channels) - self._enabled_channels:
            self.enable_channel(channel)

    async def reset_channel(self, channel: Channel):
        """Reset a channel to safe parameters."""
        try:
            # First set wave parameters to safe values
            safe_params = WaveParameters(
                frequencies=[15] * 4,    # Start with minimum frequency
                intensities=[0] * 4      # Start with zero intensity
            )
            
            # Try multiple times to reset the channel
            for attempt in range(3):
                try:
                    # Set wave parameters first
                    success = await self.set_wave_parameters(channel, safe_params)
                    if not success:
                        raise Exception("Failed to set wave parameters")
                    await asyncio.sleep(0.3)  # Increased delay between operations
                    
                    # Then set strength to 0
                    success = await self.set_channel_strength(channel, 0)
                    if not success:
                        raise Exception("Failed to set strength")
                    await asyncio.sleep(0.3)  # Increased delay between operations
                    
                    # If successful, update state
                    self._last_successful_update = time.time()
                    self._consecutive_errors = 0
                    self.logger.info(f"Successfully reset channel {channel}")
                    return True
                except Exception as e:
                    if attempt < 2:
                        await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
                        continue
                    raise
        except Exception as e:
            self.logger.error(f"Error resetting channel {channel}: {e}")
            self._consecutive_errors += 1
            return False
    
    def _check_recovery(self):
        """Check if recovery is needed and attempt recovery if necessary."""
        try:
            current_time = time.time()
            
            # Only check if we're connected and enabled
            if not self.device.is_connected or not self._enabled:
                return
                
            # Only attempt recovery if enough time has passed since last attempt
            if (current_time - self._last_recovery_time) < 5.0:
                return
                
            # Check if we haven't had a successful update in a while
            if (current_time - self._last_successful_update) > self.RECOVERY_CHECK_INTERVAL:
                self.logger.warning(f"No successful updates for {self.RECOVERY_CHECK_INTERVAL} seconds")
                asyncio.create_task(self._attempt_recovery())
                
        except Exception as e:
            self.logger.error(f"Error in recovery check: {e}") 

    async def _restore_channels(self):
        """Restore channel settings after reconnection."""
        await asyncio.sleep(1)  # wait briefly for connection to stabilize
        for channel in self._enabled_channels:
            params = WaveParameters(
                frequencies=[15, 15, 15, 15],
                intensities=[0, 0, 0, 0]
            )
            default_strength = 100  # default strength value; adjust as needed
            await self.set_wave_parameters(channel, params)
            await self.set_channel_strength(channel, default_strength)
            self.logger.info(f"Restored channel {channel} with default strength {default_strength}") 