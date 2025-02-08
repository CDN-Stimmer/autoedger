from PySide6.QtCore import QObject, QTimer, Slot
import asyncio
import logging
from typing import List
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
        self.enabled_channels = [Channel.A]  # Enabled channels
        
        # Sync mode state
        self._sync_enabled = False
        
        # Connect to audio player signals
        self.audio_player.audio_data_ready.connect(self._on_audio_data)
        self.audio_player.playback_started.connect(self._on_playback_started)
        self.audio_player.playback_stopped.connect(self._on_playback_stopped)
        
        # Set up reconnection timer
        self._reconnect_timer = QTimer()
        self._reconnect_timer.setInterval(5000)
        self._reconnect_timer.timeout.connect(self._handle_reconnect)
        
        # Async state
        self._lock = asyncio.Lock()
        self._running = False
        self._last_wave_params = None
        self._current_task = None
        
    def _handle_reconnect(self):
        """Handle reconnection timer timeout."""
        if not self._started or self._stopping:
            return
            
        try:
            loop = asyncio.get_event_loop()
            if loop and loop.is_running():
                self._current_task = loop.create_task(self._try_reconnect())
                self._current_task.add_done_callback(lambda _: self._handle_reconnect_complete())
        except Exception as e:
            self.logger.error(f"Error in reconnect handler: {e}")
            
    def _handle_reconnect_complete(self):
        """Handle completion of reconnection attempt."""
        if not self.device.is_connected:
            # If still not connected, ensure timer is running
            if not self._reconnect_timer.isActive():
                self._reconnect_timer.start()
        else:
            # If connected, stop the timer
            if self._reconnect_timer.isActive():
                self._reconnect_timer.stop()
                
    @property
    def sync_enabled(self) -> bool:
        """Get sync mode state."""
        return self._sync_enabled
        
    @sync_enabled.setter
    def sync_enabled(self, value: bool):
        """Set sync mode state."""
        self._sync_enabled = value
        self.logger.info(f"Sync mode {'enabled' if value else 'disabled'}")
        
        # When sync mode is enabled, ensure channel B is updated with current parameters
        if value and self._started and self.device.is_connected:
            # Get current wave parameters for channel A
            params = self.device._wave_parameters[Channel.A]
            if params:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Update channel B with the same parameters and strength
                        asyncio.create_task(self.device.set_wave_parameters(Channel.B, params))
                        strength_a = self.device._current_strengths[Channel.A]
                        asyncio.create_task(self.device.set_strength(Channel.B, strength_a))
                except RuntimeError:
                    self.logger.warning("Event loop not ready for sync mode update")
                
    async def _try_reconnect(self):
        """Attempt to reconnect to the device."""
        if not self.device.is_connected:
            try:
                await self.device.connect()
                if self._last_wave_params:
                    await self.set_wave_parameters(*self._last_wave_params)
                return True
            except Exception as e:
                self.logger.error(f"Error reconnecting: {e}")
                return False
        return True
        
    async def set_wave_parameters(self, frequencies, intensities):
        """Set wave parameters safely."""
        async with self._lock:
            try:
                self._last_wave_params = (frequencies, intensities)
                await self.device.set_wave_parameters(frequencies, intensities)
            except Exception as e:
                self.logger.error(f"Error setting wave parameters: {e}")
                
    def start(self):
        """Start the adapter."""
        if self._started:
            return
            
        self._started = True
        self._stopping = False
        
        # Start the reconnection timer
        if not self._reconnect_timer.isActive():
            self._reconnect_timer.start()
            
    async def stop(self):
        """Stop all operations safely."""
        if not self._started:
            return
            
        self._started = False
        self._stopping = True
        
        async with self._lock:
            if self._current_task and not self._current_task.done():
                self._current_task.cancel()
            if self._reconnect_timer.isActive():
                self._reconnect_timer.stop()
            try:
                await self.device.stop()
            except Exception as e:
                self.logger.error(f"Error stopping device: {e}")
                
    @Slot(float, float)
    def _on_audio_data(self, amplitude: float, frequency: float):
        """Handle incoming audio data."""
        if not self._started or not self.device.is_connected:
            return
            
        try:
            # Scale amplitude to intensity
            base_intensity = int(amplitude * self.base_intensity_scale)
            
            # Create wave parameters
            params = WaveParameters(
                frequencies=[int(frequency)] * 4,
                intensities=[base_intensity] * 4
            )
            
            try:
                loop = asyncio.get_event_loop()
                if loop and loop.is_running():
                    # Update Channel A if enabled
                    if Channel.A in self.enabled_channels:
                        strength_a = min(100, base_intensity)
                        loop.create_task(self.device.set_wave_parameters(Channel.A, params))
                        loop.create_task(self.device.set_strength(Channel.A, strength_a))
                        
                    # Update Channel B if enabled
                    if Channel.B in self.enabled_channels:
                        # In sync mode, use Channel A's strength if enabled
                        if self._sync_enabled and Channel.A in self.enabled_channels:
                            strength = strength_a
                        else:
                            strength = min(100, base_intensity)
                            
                        loop.create_task(self.device.set_wave_parameters(Channel.B, params))
                        loop.create_task(self.device.set_strength(Channel.B, strength))
            except Exception as e:
                self.logger.warning(f"Event loop not ready: {e}")
                
        except Exception as e:
            self.logger.error(f"Error updating pattern: {e}")
            
    @Slot()
    def _on_playback_started(self):
        """Handle playback start."""
        self._enabled = True
        
    @Slot()
    def _on_playback_stopped(self):
        """Handle playback stop."""
        self._enabled = False
        
        # Reset all channels to 0
        if self._started and self.device.is_connected:
            try:
                loop = asyncio.get_event_loop()
                if loop and loop.is_running():
                    zero_params = WaveParameters(frequencies=[0]*4, intensities=[0]*4)
                    loop.create_task(self.device.set_wave_parameters(Channel.A, zero_params))
                    loop.create_task(self.device.set_wave_parameters(Channel.B, zero_params))
            except Exception as e:
                self.logger.warning(f"Event loop not ready: {e}")

    def start_reconnect_timer(self):
        """Start the reconnection timer if not already running."""
        if not self._reconnect_timer.isActive():
            self._reconnect_timer.start()
            
    def stop_reconnect_timer(self):
        """Stop the reconnection timer."""
        if self._reconnect_timer.isActive():
            self._reconnect_timer.stop() 
                self.logger.warning("Event loop not ready for playback stop") 