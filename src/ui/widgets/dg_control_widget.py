import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QSlider, QSpinBox, QCheckBox, QPushButton, QGroupBox, QMessageBox
)
from PySide6.QtCore import Qt, Slot, QTimer
from hardware.dg_device import Channel, WaveParameters
from hardware.dg_audio_adapter import DGAudioAdapter
from .device_selection_dialog import DeviceSelectionDialog
import asyncio
import qasync
import time

class DGControlWidget(QWidget):
    """Widget for controlling DG device parameters."""
    
    def __init__(self, audio_adapter: DGAudioAdapter, parent=None):
        super().__init__(parent)
        self._adapter = audio_adapter
        self.logger = logging.getLogger(__name__)
        
        self._setup_ui()

        if self._adapter is None:
            # If no adapter is provided, add a warning label and disable interactive elements
            warning = QLabel("Coyote module not active")
            warning.setAlignment(Qt.AlignCenter)
            self.layout().addWidget(warning)
            self.setDisabled(True)
        else:
            # Connect to device signals
            self._adapter.device.connection_changed.connect(self._on_connection_changed)
            self._adapter.device.devices_discovered.connect(self._on_devices_discovered)
            
            # Create timer for strength updates
            self._strength_timer = QTimer()
            self._strength_timer.setInterval(500)  # increased to 500ms to reduce command flooding
            self._strength_timer.timeout.connect(self._update_strengths)
            
            # Create error recovery timer
            self._error_recovery_timer = QTimer()
            self._error_recovery_timer.setInterval(2000)  # 2 second interval
            self._error_recovery_timer.timeout.connect(self._check_error_recovery)
            self._error_recovery_timer.start()
            
            # Initialize channels asynchronously
            QTimer.singleShot(0, self._async_init)
        
        self._sync_enabled = False
        self._user_changing_volume = False
        self._updating_strengths = False
        self._last_volume_a = 0
        self._last_volume_b = 0
        self._current_task = None
        self._device_selection_lock = asyncio.Lock()
        self._selected_device = None
        self._connection_lock = asyncio.Lock()
        self._connecting = False
        self._last_error_time = 0
        self._error_count = 0
        self._last_successful_update = 0
        self._channel_a_state = {'enabled': False, 'strength': 0, 'last_update': 0}
        self._channel_b_state = {'enabled': False, 'strength': 0, 'last_update': 0}
        # Cache for last sent strength values to avoid redundant updates
        self._last_sent_strength_a = None
        self._last_sent_strength_b = None

    def _setup_ui(self):
        # Create the main layout for the DG Control widget
        layout = QVBoxLayout(self)

        # Optional: Add a title label
        title = QLabel("DG Control")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Add a slider for Base Intensity Scale
        base_label = QLabel("Base Intensity Scale")
        layout.addWidget(base_label)

        self.base_scale = QSlider(Qt.Horizontal)
        self.base_scale.setRange(0, 100)
        self.base_scale.setValue(70)  # Default value
        layout.addWidget(self.base_scale)

        # You can add more DG control related UI elements here if needed
        
        # Set the layout
        self.setLayout(layout)

    @Slot()
    async def _on_channel_changed(self):
        """Handle channel enable/disable."""
        try:
            # Update enabled channels
            self._adapter.enabled_channels = []
            
            # Handle Channel A
            if self.channel_a_enabled.isChecked():
                self._adapter.enabled_channels.append(Channel.A)
                # Restore last known volume for channel A
                if self._last_volume_a > 0:
                    self.logger.debug(f"Enabling Channel A with volume: {self._last_volume_a}")
                    await self._adapter.set_channel_strength(Channel.A, self._last_volume_a)
                    self.channel_a_volume.setValue(self._last_volume_a)
            else:
                # Set strength to 0
                self.logger.debug("Disabling Channel A")
                await self._adapter.set_channel_strength(Channel.A, 0)
                # Reset wave parameters
                zero_params = WaveParameters(frequencies=[0]*4, intensities=[0]*4)
                await self._adapter.set_wave_parameters(Channel.A, zero_params)
                # Reset volume slider
                self.channel_a_volume.setValue(0)
            
            # Handle Channel B
            if self.channel_b_enabled.isChecked():
                self._adapter.enabled_channels.append(Channel.B)
                if self._sync_enabled:
                    if self.channel_b_volume.value() > 0:
                        volume = self._last_volume_a
                        self.logger.debug(f"Enabling Channel B in sync mode with channel A volume: {volume}")
                    else:
                        volume = 0
                        self.logger.debug("Channel B volume is zero in sync mode, disabling channel B")
                else:
                    volume = self._last_volume_b
                    self.logger.debug(f"Enabling Channel B with volume: {volume}")
                if volume > 0:
                    await self._adapter.set_channel_strength(Channel.B, volume)
                    self.channel_b_volume.setValue(volume)
                else:
                    await self._disable_channel(Channel.B)
                
        except Exception as e:
            self.logger.error(f"Error updating channels: {e}")
    
    @Slot()
    async def _update_parameters(self):
        """Update DG adapter parameters based on current control values."""
        try:
            # Update base scale label
            base_scale = self.base_scale.value()
            self.base_value.setText(f"{base_scale}%")
            
            # Update pulse range label
            pulse_range = self.pulse_range.value()
            self.pulse_value.setText(f"±{pulse_range}%")
            
            # Update frequency labels
            min_freq = self.min_freq.value()
            max_freq = self.max_freq.value()
            self.min_freq_value.setText(f"{min_freq} Hz")
            self.max_freq_value.setText(f"{max_freq} Hz")
            
            # Update adapter parameters
            # Base intensity is now handled by main window
            self._adapter.intensity_pulse_range = pulse_range / 100.0
            self._adapter.min_frequency = min_freq
            self._adapter.max_frequency = max_freq
            
            # Update channels
            await self._on_channel_changed()
                
        except Exception as e:
            print(f"Error updating parameters: {e}")
    
    @Slot()
    def _validate_frequency_range(self):
        """Ensure min frequency is always less than max frequency."""
        try:
            min_freq = self.min_freq.value()
            max_freq = self.max_freq.value()
            
            if min_freq > max_freq:
                if self.sender() == self.min_freq:
                    self.min_freq.setValue(max_freq)
                else:
                    self.max_freq.setValue(min_freq)
                    
        except Exception as e:
            print(f"Error validating frequency range: {e}")
    
    @Slot(int)
    def _on_volume_changed(self, value):
        """Handle volume slider changes."""
        try:
            if not self._adapter.device.is_connected:
                return
                
            # Update labels
            if self.sender() == self.channel_a_volume:
                self.channel_a_volume_label.setText(str(value))
                # If sync mode is enabled, also update channel B's slider
                if self._adapter.sync_enabled and self.channel_b_enabled.isChecked():
                    self.channel_b_volume.setValue(value)
            else:  # Channel B
                self.channel_b_volume_label.setText(str(value))
                
            # Only send strength updates if playing
            if not self._adapter._is_playing:
                return
                
            # Handle Channel A
            if self.sender() == self.channel_a_volume and Channel.A in self._adapter.enabled_channels:
                asyncio.create_task(self._adapter.set_channel_strength(Channel.A, value))
                # If sync mode is enabled, also update Channel B
                if self._adapter.sync_enabled and Channel.B in self._adapter.enabled_channels:
                    asyncio.create_task(self._adapter.set_channel_strength(Channel.B, value))
                    
            # Handle Channel B (only if not in sync mode)
            elif self.sender() == self.channel_b_volume and not self._adapter.sync_enabled:
                if Channel.B in self._adapter.enabled_channels:
                    asyncio.create_task(self._adapter.set_channel_strength(Channel.B, value))
                    
        except Exception as e:
            self.logger.error(f"Error handling volume change: {e}")

    @Slot(int)
    def _on_sync_changed(self, state):
        """Handle sync mode toggle."""
        try:
            self._adapter.sync_enabled = bool(state)
            
            # Update UI elements
            self.channel_b_volume.setEnabled(not state)
            
            if state and self.channel_b_enabled.isChecked():
                # When enabling sync mode, update Channel B to match A
                if self.channel_a_enabled.isChecked():
                    self.channel_b_volume.setValue(self.channel_a_volume.value())
                    if self._adapter._is_playing:
                        asyncio.create_task(self._adapter.set_channel_strength(Channel.B, self.channel_a_volume.value()))
                else:
                    # If Channel A is disabled, disable Channel B
                    self.channel_b_enabled.setChecked(False)
                    
        except Exception as e:
            self.logger.error(f"Error handling sync mode change: {e}")

    @Slot(bool)
    def _on_channel_a_enabled_changed(self, enabled: bool):
        """Handle Channel A enable/disable."""
        try:
            if enabled:
                self._adapter.enable_channel(Channel.A)
                # Only send non-zero strength if playing and volume > 0
                if self._adapter._is_playing and self.channel_a_volume.value() > 0:
                    asyncio.create_task(self._adapter.set_channel_strength(Channel.A, self.channel_a_volume.value()))
            else:
                self._adapter.disable_channel(Channel.A)
                # If sync mode is enabled, also disable Channel B
                if self._adapter.sync_enabled and self.channel_b_enabled.isChecked():
                    self.channel_b_enabled.setChecked(False)
                    
        except Exception as e:
            self.logger.error(f"Error handling Channel A enable change: {e}")

    @Slot(bool)
    def _on_channel_b_enabled_changed(self, enabled: bool):
        """Handle Channel B enable/disable."""
        try:
            if enabled:
                self._adapter.enable_channel(Channel.B)
                # Only send non-zero strength if playing
                if self._adapter._is_playing:
                    if self._adapter.sync_enabled:
                        # In sync mode, use Channel A's value
                        strength = self.channel_a_volume.value()
                    else:
                        strength = self.channel_b_volume.value()
                    if strength > 0:
                        asyncio.create_task(self._adapter.set_channel_strength(Channel.B, strength))
            else:
                self._adapter.disable_channel(Channel.B)
                
        except Exception as e:
            self.logger.error(f"Error handling Channel B enable change: {e}")

    @Slot()
    async def _update_strengths(self):
        """Periodically send updated strength values to the device."""
        try:
            self.logger.debug(f"_update_strengths called: is_playing={getattr(self._adapter, 'is_playing', False)}, channel_b_enabled={self.channel_b_enabled.isChecked()}, sync_enabled={self._adapter.sync_enabled}, last_volume_a={self._last_volume_a}, last_volume_b={self._last_volume_b}")
            
            # Only update strengths if audio is playing
            if not getattr(self._adapter, 'is_playing', False):
                return
            
            # Determine strength for Channel A based on its slider
            strength_a = self._last_volume_a
            
            # Determine strength for Channel B:
            # If Channel B is enabled, then determine its strength based on sync mode.
            # Otherwise, force its strength to 0
            if self.channel_b_enabled.isChecked():
                if self._adapter.sync_enabled:
                    strength_b = strength_a
                else:
                    strength_b = self._last_volume_b
            else:
                strength_b = 0
            
            self.logger.debug(f"Calculated strengths: Channel A = {strength_a}, Channel B = {strength_b}")
            
            # Optional: Add caching logic to avoid sending redundant updates
            if self._last_sent_strength_a != strength_a:
                await self._adapter.set_channel_strength(Channel.A, strength_a)
                self._last_sent_strength_a = strength_a
            
            if self._last_sent_strength_b != strength_b:
                await self._adapter.set_channel_strength(Channel.B, strength_b)
                self._last_sent_strength_b = strength_b
        except Exception as e:
            self.logger.error(f"Error in _update_strengths: {e}")

    def closeEvent(self, event):
        """Handle widget close."""
        try:
            # Stop strength timer
            self._strength_timer.stop()
            
            # Create task to disable channels
            asyncio.create_task(self._handle_close())
            
        except Exception as e:
            self.logger.error(f"Error during close: {e}")
            
        super().closeEvent(event)
        
    async def _handle_close(self):
        """Handle async operations during close."""
        try:
            # Ensure all channels are disabled
            await self._disable_channel(Channel.A)
            await self._disable_channel(Channel.B)
            
            # Let pending tasks complete
            for task in list(self._adapter._pending_tasks):
                if not task.done():
                    task.cancel()
                    
        except Exception as e:
            self.logger.error(f"Error during close cleanup: {e}")

    @Slot(bool)
    def _on_connection_changed(self, connected: bool):
        """Handle connection state changes."""
        self.logger.info(f"Connection state changed: {connected}")
        
        if connected:
            self.logger.info("Device connected, initializing parameters and strengths")
            # Initialize device
            asyncio.create_task(self._initialize_device())
        else:
            self.logger.info("Device disconnected, stopping strength updates")
            self._strength_timer.stop()
            
        # Update UI state
        self._update_ui_state()

    def _async_init(self):
        """Initialize channels asynchronously."""
        try:
            # Start with both channels disabled
            self.channel_a_enabled.setChecked(False)
            self.channel_b_enabled.setChecked(False)
            
            # Start adapter
            self._adapter.start()
            
        except Exception as e:
            self.logger.error(f"Error during async initialization: {e}")

    @Slot()
    async def _on_playback_started(self):
        """Handle playback start."""
        try:
            # Only proceed if we have enabled channels
            if not self.channel_a_enabled.isChecked() and not self.channel_b_enabled.isChecked():
                return
                
            # Initialize enabled channels with zero strength
            if self.channel_a_enabled.isChecked():
                asyncio.create_task(self._adapter.set_channel_strength(Channel.A, 0))
                
            if self.channel_b_enabled.isChecked():
                if self._adapter.sync_enabled:
                    # In sync mode, use Channel A's value
                    strength = self.channel_a_volume.value()
                else:
                    strength = self.channel_b_volume.value()
                asyncio.create_task(self._adapter.set_channel_strength(Channel.B, 0))
                
        except Exception as e:
            self.logger.error(f"Error handling playback start: {e}")

    @Slot()
    async def _on_playback_stopped(self):
        """Handle playback stop."""
        try:
            # Disable all channels
            if self.channel_a_enabled.isChecked():
                asyncio.create_task(self._adapter.set_channel_strength(Channel.A, 0))
                
            if self.channel_b_enabled.isChecked():
                asyncio.create_task(self._adapter.set_channel_strength(Channel.B, 0))
                
        except Exception as e:
            self.logger.error(f"Error handling playback stop: {e}")

    async def _initialize_device(self):
        """Initialize device after connection."""
        try:
            # Update UI state
            self._update_ui_state()
            
            # Start with both channels disabled
            self.channel_a_enabled.setChecked(False)
            self.channel_b_enabled.setChecked(False)
            
            # Start adapter
            self._adapter.start()
            
        except Exception as e:
            self.logger.error(f"Error initializing device: {e}")

    def _update_ui_state(self):
        """Update UI elements based on current state."""
        is_connected = self._adapter.device.is_connected
        
        # Update button states
        self.connect_button.setEnabled(not self._connecting)
        self.connect_button.setText("Disconnect" if is_connected else "Select Device")
        
        # Update channel controls
        self.channel_a_enabled.setEnabled(is_connected)
        self.channel_b_enabled.setEnabled(is_connected)
        
        # Update volume sliders
        self.channel_a_volume.setEnabled(is_connected)
        self.channel_b_volume.setEnabled(is_connected and not self._adapter.sync_enabled)
        
        # Update other controls
        self.sync_checkbox.setEnabled(is_connected)
        self.base_scale.setEnabled(is_connected)
        self.pulse_range.setEnabled(is_connected)
        self.min_freq.setEnabled(is_connected)
        self.max_freq.setEnabled(is_connected)

    @Slot(list)
    def _on_devices_discovered(self, devices):
        """Handle device discovery."""
        # This signal is emitted when devices are discovered
        # We don't need to do anything here since the dialog handles the device list
        pass 

    async def _show_device_selection(self):
        """Show device selection dialog."""
        try:
            # Only scan if we're not connected
            if not self._adapter.device.is_connected:
                devices = await self._adapter.device.scan_devices()
                if not devices:
                    self.logger.warning("No devices found")
                    return
                    
                # Show device selection dialog
                dialog = DeviceSelectionDialog(devices, self)
                dialog.device_selected.connect(self._on_device_selected)
                dialog.exec()
            else:
                self.logger.info("Already connected to device - skipping scan")
        except Exception as e:
            self.logger.error(f"Error showing device selection: {e}")

    def _on_connect_clicked(self):
        """Handle connect button click."""
        if self._adapter.device.is_connected:
            self.logger.info("Already connected to device")
            return
            
        # Start device discovery
        asyncio.create_task(self._show_device_selection())
        
    @Slot(object)
    def _on_device_selected(self, device):
        """Handle device selection."""
        if not device:
            self.logger.warning("No device selected")
            return
            
        self._selected_device = device
        self.logger.info(f"Selected device: {device.name} ({device.address})")
        # Wait for device selection dialog to close before connecting
        QTimer.singleShot(100, lambda: asyncio.create_task(self._connect_to_selected_device()))

    async def _connect_to_selected_device(self):
        """Connect to the selected device."""
        try:
            if not self._selected_device:
                self.logger.warning("No device selected")
                return

            self.logger.info(f"Connecting to {self._selected_device.name} ({self._selected_device.address})")
            
            # Disable UI elements during connection
            self._connecting = True
            self._update_ui_state()
            
            # Connect to device
            if await self._adapter.device.connect_to_device(self._selected_device):
                self.logger.info(f"Successfully connected to {self._selected_device.name}")
                
                # Schedule parameter updates and strength initialization for next event loop iteration
                asyncio.get_event_loop().call_soon(lambda: asyncio.create_task(self._initialize_device()))
            else:
                self.logger.error("Failed to connect to device")
                
        except Exception as e:
            self.logger.error(f"Error connecting to device: {e}")
        finally:
            self._connecting = False
            self._update_ui_state() 

    def _check_error_recovery(self):
        """Check if error recovery is needed and attempt recovery if necessary."""
        try:
            current_time = time.time()
            
            # Check if we haven't had a successful update in a while
            if (current_time - self._last_successful_update) > 5.0:  # 5 seconds threshold
                self.logger.warning("No successful updates for 5 seconds, attempting recovery")
                self._error_count += 1
                
                # If we've had too many errors, try reconnecting
                if self._error_count > 3:
                    self.logger.error("Too many errors, attempting reconnect")
                    self._error_count = 0
                    asyncio.create_task(self._adapter.device.reconnect())
                    return
                    
                # Otherwise just try resetting the channels
                for channel in self._adapter.enabled_channels:
                    asyncio.create_task(self._adapter.reset_channel(channel))
            
            # Reset error count if we've had recent successful updates
            elif (current_time - self._last_error_time) > 10.0:  # 10 seconds without errors
                self._error_count = 0
                
        except Exception as e:
            self.logger.error(f"Error in recovery check: {e}") 