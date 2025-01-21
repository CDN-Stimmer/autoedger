from PySide6.QtCore import QObject, Slot, QTimer
import asyncio
import qasync
from typing import List
import logging
from .dg_device import DGDevice, Channel, WaveParameters

class DGAudioAdapter(QObject):
    """Adapter to connect QtAudioPlayer to DGDevice."""
    
    def __init__(self, audio_player, logger):
        """Initialize the adapter."""
        super().__init__()
        self.logger = logger
        self.audio_player = audio_player
        self.device = DGDevice()
        self._started = False
        self._stopping = False
        self._enabled = False
        self._connected = False
        
        # Parameters for audio-to-pattern conversion
        self.base_intensity_scale = 100  # Scale factor for converting amplitude to intensity
        self.intensity_pulse_range = 50  # Range for intensity pulsing
        self.min_frequency = 10  # Minimum frequency in Hz
        self.max_frequency = 1000  # Maximum frequency in Hz
        self.enabled_channels: List[Channel] = [Channel.A]  # Enabled channels
        
        # Sync mode state
        self._sync_enabled = False
        
        # Connect to audio player signals
        self.audio_player.audio_data_ready.connect(self._on_audio_data)
        self.audio_player.playback_started.connect(self._on_playback_started)
        self.audio_player.playback_stopped.connect(self._on_playback_stopped)
        
        # Set up reconnection timer
        self._reconnect_timer = QTimer()
        self._reconnect_timer.setInterval(5000)  # Try every 5 seconds
        self._reconnect_timer.timeout.connect(lambda: asyncio.create_task(self._try_reconnect()))

    @property
    def sync_enabled(self) -> bool:
        """Get sync mode state."""
        return self._sync_enabled

    @sync_enabled.setter
    def sync_enabled(self, value: bool):
        """Set sync mode state."""
        self._sync_enabled = value
        self.logger.info(f"DG sync mode {'enabled' if value else 'disabled'}")
        
        # When sync mode is enabled, ensure channel B is updated with current parameters
        if value and self._started and self.device.is_connected:
            # Get current wave parameters for channel A
            params = self.device._wave_parameters[Channel.A]
            if params:
                # Update channel B with the same parameters and strength
                asyncio.create_task(self.device.set_wave_parameters(Channel.B, params))
                strength_a = self.device._current_strengths[Channel.A]
                asyncio.create_task(self.device.set_strength(Channel.B, strength_a))

    async def _try_reconnect(self):
        """Try to reconnect to the device."""
        if not self._started or self._stopping:
            return

        if not self.device.is_connected:
            try:
                if await self.device.connect_device():
                    self._connected = True
                    self.logger.info("Connected to DG device")
                    if self._reconnect_timer:
                        self._reconnect_timer.stop()  # Stop timer on successful connection
                else:
                    self.logger.warning("Failed to connect to DG device, will retry...")
                    if self._reconnect_timer and not self._reconnect_timer.isActive():
                        self._reconnect_timer.start()
            except Exception as e:
                self.logger.warning(f"Failed to reconnect: {e}")
                if self._reconnect_timer and not self._reconnect_timer.isActive():
                    self._reconnect_timer.start()
        
    def start(self):
        """Start the adapter."""
        if self._started:
            return

        self._started = True
        self._stopping = False

        # Start the reconnection timer
        self._reconnect_timer.start()

        # Initial connection attempt
        asyncio.create_task(self._try_reconnect())

        # Connect audio player signals
        self.audio_player.audio_data_ready.connect(self._on_audio_data)
        self.audio_player.playback_started.connect(self._on_playback_started)
        self.audio_player.playback_stopped.connect(self._on_playback_stopped)

    async def stop(self):
        """Stop the adapter."""
        if not self._started:
            return

        self._started = False
        self._stopping = True

        # Stop reconnection timer
        if self._reconnect_timer:
            self._reconnect_timer.stop()
            self._reconnect_timer = None

        # Set all channels to 0
        if self.device.is_connected:
            try:
                zero_params = WaveParameters(frequencies=[0]*4, intensities=[0]*4)
                await self.device.set_wave_parameters(Channel.A, zero_params)
                await self.device.set_wave_parameters(Channel.B, zero_params)
            except Exception as e:
                self.logger.error(f"Error setting channels to 0: {e}")

        # Disconnect from device
        try:
            await self.device.disconnect()
        except Exception as e:
            self.logger.error(f"Error disconnecting device: {e}")

        # Disconnect audio player signals
        self.audio_player.audio_data_ready.disconnect(self._on_audio_data)
        self.audio_player.playback_started.disconnect(self._on_playback_started)
        self.audio_player.playback_stopped.disconnect(self._on_playback_stopped)
    
    async def _connect(self):
        """Connect to the DG device."""
        try:
            if await self.device.connect_device():
                self._connected = True
                self.logger.info("Connected to DG device")
                return True
            else:
                self.logger.warning("Failed to connect to DG device, will retry...")
                self._reconnect_timer.start()
        except Exception as e:
            self.logger.error(f"Error connecting to DG device: {e}")
            self._reconnect_timer.start()
        return False
    
    async def _disconnect(self):
        """Disconnect from the DG device."""
        try:
            await self.device.disconnect()
            self._connected = False
            self.logger.info("Disconnected from DG device")
        except Exception as e:
            self.logger.error(f"Error disconnecting from DG device: {e}")
        
    @Slot(float, float)
    def _on_audio_data(self, amplitude: float, frequency: float):
        """Handle audio data updates."""
        if not self._started or not self.device.is_connected:
            self.logger.debug("Audio data received but adapter not started or device not connected")
            return
            
        try:
            self.logger.info(f"Processing audio - amplitude: {amplitude:.3f}, frequency: {frequency:.1f}Hz")
            self.logger.info(f"Enabled channels: {self.enabled_channels}")
            self.logger.info(f"Sync mode: {self._sync_enabled}")

            # Convert audio data to wave parameters
            scaled_intensity = min(255, int(self._scale_intensity(amplitude)))  # Ensure intensity is capped at 255
            scaled_frequency = int(self._scale_frequency(frequency))
            params = WaveParameters(
                frequencies=[scaled_frequency] * 4,
                intensities=[scaled_intensity] * 4
            )
            self.logger.info(f"Wave parameters - frequencies: {params.frequencies}, intensities: {params.intensities}")

            # Get current strengths
            strength_a = self.device._current_strengths[Channel.A]
            strength_b = self.device._current_strengths[Channel.B]
            self.logger.info(f"Current strengths - A: {strength_a}, B: {strength_b}")

            # Update Channel A if enabled
            if Channel.A in self.enabled_channels:
                self.logger.info(f"Updating Channel A - strength: {strength_a}")
                asyncio.create_task(self.device.set_wave_parameters(Channel.A, params))
                asyncio.create_task(self.device.set_strength(Channel.A, strength_a))
            else:
                self.logger.info("Channel A not enabled")
            
            # Update Channel B if enabled
            if Channel.B in self.enabled_channels:
                # In sync mode, use Channel A's strength if enabled
                if self._sync_enabled and Channel.A in self.enabled_channels:
                    strength = strength_a
                else:
                    strength = strength_b

                self.logger.info(f"Updating Channel B - strength: {strength}")
                asyncio.create_task(self.device.set_wave_parameters(Channel.B, params))
                asyncio.create_task(self.device.set_strength(Channel.B, strength))
            else:
                self.logger.info("Channel B not enabled")
                
        except Exception as e:
            self.logger.error(f"Error updating pattern: {e}")
            
    @Slot()
    def _on_playback_started(self):
        """Handle playback started."""
        self._enabled = True
        
    @Slot()
    def _on_playback_stopped(self):
        """Handle playback stopped."""
        # Only disable and reset channels if we're actually stopping,
        # not just switching files or loading new media
        if (not self.audio_player.player.mediaStatus() == self.audio_player.player.MediaStatus.LoadingMedia and 
            not self.audio_player.player.mediaStatus() == self.audio_player.player.MediaStatus.BufferedMedia):
            self._enabled = False
            # Set all channels to 0 only when actually stopping playback
            if self._connected:
                for channel in Channel:
                    asyncio.create_task(self.device.set_strength(channel, 0))

    def _scale_intensity(self, amplitude):
        """Scale amplitude (0-1) to intensity (0-255)"""
        return amplitude * self.base_intensity_scale

    def _scale_frequency(self, frequency):
        """Scale frequency (Hz) to device frequency value (1-100)"""
        # Clamp frequency to min/max range
        frequency = max(self.min_frequency, min(self.max_frequency, frequency))
        # Map frequency to 1-100 range
        return int(1 + 99 * (frequency - self.min_frequency) / (self.max_frequency - self.min_frequency)) 