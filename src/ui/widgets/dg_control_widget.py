import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QSlider, QSpinBox, QCheckBox, QPushButton, QGroupBox
)
from PySide6.QtCore import Qt, Slot, QTimer
from hardware.dg_device import Channel, WaveParameters
import asyncio
import qasync

class DGControlWidget(QWidget):
    """Widget for controlling DG device parameters."""
    
    def __init__(self, dg_adapter, parent=None):
        super().__init__(parent)
        self.dg_adapter = dg_adapter
        self.logger = logging.getLogger(__name__)
        self._sync_enabled = False
        self._last_channel_a_volume = 100  # Set default volume to 100
        self._last_channel_b_volume = 100  # Set default volume to 100
        self._user_volume_change = False
        self._setup_ui()
        
        # Connect to device signals
        self.dg_adapter.device.connection_changed.connect(self._on_connection_changed)
        
        # Set up timer for strength updates
        self._strength_timer = QTimer()
        self._strength_timer.timeout.connect(self._update_strengths)
        self._strength_timer.start(2000)  # Update every 2 seconds

        # Flag to track if we're currently updating strengths
        self._updating_strengths = False
        
        # Get the existing event loop
        self.loop = asyncio.get_event_loop()

        # Initialize channel strengths
        if self.channel_a_enabled.isChecked():
            self.loop.create_task(self.dg_adapter.device.set_strength(Channel.A, self._last_channel_a_volume))
            self.channel_a_volume.setValue(self._last_channel_a_volume)
        if self.channel_b_enabled.isChecked():
            self.loop.create_task(self.dg_adapter.device.set_strength(Channel.B, self._last_channel_b_volume))
            self.channel_b_volume.setValue(self._last_channel_b_volume)

    def _setup_ui(self):
        # Create main layout
        main_layout = QVBoxLayout(self)
        
        # Create frame
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel)
        frame_layout = QVBoxLayout(frame)
        
        # Create title
        title = QLabel("DG Device Control")
        title.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(title)
        
        # Create sync mode control
        sync_container = QWidget()
        sync_layout = QHBoxLayout(sync_container)
        sync_layout.setContentsMargins(5, 0, 5, 0)
        
        self.sync_checkbox = QCheckBox("Sync Mode")
        self.sync_checkbox.setToolTip("When enabled, Channel B mirrors Channel A")
        self.sync_checkbox.setStyleSheet("""
            QCheckBox {
                font-weight: bold;
                color: #4CAF50;
            }
            QCheckBox:checked {
                color: #45a049;
            }
        """)
        self.sync_checkbox.stateChanged.connect(self._on_sync_changed)
        sync_layout.addWidget(self.sync_checkbox)
        
        frame_layout.addWidget(sync_container)
        
        # Create intensity controls
        intensity_group = QGroupBox("Intensity Scaling")
        intensity_layout = QVBoxLayout(intensity_group)
        
        # Base intensity scale
        base_layout = QHBoxLayout()
        base_layout.addWidget(QLabel("Max Intensity:"))
        self.base_scale = QSlider(Qt.Horizontal)
        self.base_scale.setRange(0, 100)
        self.base_scale.setValue(70)
        # We'll connect this in the main window
        base_layout.addWidget(self.base_scale)
        self.base_value = QLabel("70%")
        base_layout.addWidget(self.base_value)
        intensity_layout.addLayout(base_layout)
        
        # Pulse range
        pulse_layout = QHBoxLayout()
        pulse_layout.addWidget(QLabel("Pulse Range:"))
        self.pulse_range = QSlider(Qt.Horizontal)
        self.pulse_range.setRange(0, 50)
        self.pulse_range.setValue(30)
        self.pulse_range.valueChanged.connect(self._update_parameters)
        pulse_layout.addWidget(self.pulse_range)
        self.pulse_value = QLabel("±30%")
        pulse_layout.addWidget(self.pulse_value)
        intensity_layout.addLayout(pulse_layout)
        
        frame_layout.addWidget(intensity_group)
        
        # Create frequency controls
        freq_group = QGroupBox("Frequency Range")
        freq_layout = QVBoxLayout(freq_group)
        
        # Min frequency
        min_freq_layout = QHBoxLayout()
        min_freq_layout.addWidget(QLabel("Min Frequency:"))
        self.min_freq = QSlider(Qt.Horizontal)
        self.min_freq.setRange(1, 200)
        self.min_freq.setValue(2)
        self.min_freq.valueChanged.connect(self._update_parameters)
        min_freq_layout.addWidget(self.min_freq)
        self.min_freq_value = QLabel("2 Hz")
        self.min_freq_value.setMinimumWidth(50)
        min_freq_layout.addWidget(self.min_freq_value)
        freq_layout.addLayout(min_freq_layout)
        
        # Max frequency
        max_freq_layout = QHBoxLayout()
        max_freq_layout.addWidget(QLabel("Max Frequency:"))
        self.max_freq = QSlider(Qt.Horizontal)
        self.max_freq.setRange(1, 200)
        self.max_freq.setValue(20)
        self.max_freq.valueChanged.connect(self._update_parameters)
        max_freq_layout.addWidget(self.max_freq)
        self.max_freq_value = QLabel("20 Hz")
        self.max_freq_value.setMinimumWidth(50)
        max_freq_layout.addWidget(self.max_freq_value)
        freq_layout.addLayout(max_freq_layout)
        
        # Add frequency validation
        self.min_freq.valueChanged.connect(self._validate_frequency_range)
        self.max_freq.valueChanged.connect(self._validate_frequency_range)
        
        frame_layout.addWidget(freq_group)
        
        # Create channel controls
        channel_group = QGroupBox("Channel Control")
        channel_layout = QVBoxLayout(channel_group)
        
        # Channel A
        channel_a_layout = QHBoxLayout()
        self.channel_a_enabled = QCheckBox("Channel A")
        self.channel_a_enabled.setChecked(True)
        self.channel_a_enabled.stateChanged.connect(self._on_channel_changed)
        channel_a_layout.addWidget(self.channel_a_enabled)
        
        # Channel A volume
        self.channel_a_volume = QSlider(Qt.Horizontal)
        self.channel_a_volume.setRange(0, 255)
        self.channel_a_volume.setValue(0)
        self.channel_a_volume.valueChanged.connect(self._on_volume_changed)
        channel_a_layout.addWidget(self.channel_a_volume)
        self.channel_a_volume_label = QLabel("0")
        channel_a_layout.addWidget(self.channel_a_volume_label)
        
        channel_layout.addLayout(channel_a_layout)
        
        # Channel B
        channel_b_layout = QHBoxLayout()
        self.channel_b_enabled = QCheckBox("Channel B")
        self.channel_b_enabled.setChecked(False)
        self.channel_b_enabled.stateChanged.connect(self._on_channel_changed)
        channel_b_layout.addWidget(self.channel_b_enabled)
        
        # Channel B volume
        self.channel_b_volume = QSlider(Qt.Horizontal)
        self.channel_b_volume.setRange(0, 255)
        self.channel_b_volume.setValue(0)
        self.channel_b_volume.valueChanged.connect(self._on_volume_changed)
        channel_b_layout.addWidget(self.channel_b_volume)
        self.channel_b_volume_label = QLabel("0")
        channel_b_layout.addWidget(self.channel_b_volume_label)
        
        channel_layout.addLayout(channel_b_layout)
        
        frame_layout.addWidget(channel_group)
        
        # Add frame to main layout
        main_layout.addWidget(frame)
        
        # Update DG adapter with initial parameters
        self._update_parameters()

    @Slot()
    def _on_channel_changed(self):
        """Handle channel enable/disable."""
        try:
            # Update enabled channels
            self.dg_adapter.enabled_channels = []
            
            # Handle Channel A
            if self.channel_a_enabled.isChecked():
                self.dg_adapter.enabled_channels.append(Channel.A)
                # Restore last known volume for channel A
                if self._last_channel_a_volume > 0:
                    self.logger.debug(f"Enabling Channel A with volume: {self._last_channel_a_volume}")
                    self.loop.create_task(self.dg_adapter.device.set_strength(Channel.A, self._last_channel_a_volume))
                    self.channel_a_volume.setValue(self._last_channel_a_volume)
            else:
                # Set strength to 0
                self.logger.debug("Disabling Channel A")
                self.loop.create_task(self.dg_adapter.device.set_strength(Channel.A, 0))
                # Reset wave parameters
                zero_params = WaveParameters(frequencies=[0]*4, intensities=[0]*4)
                self.loop.create_task(self.dg_adapter.device.set_wave_parameters(Channel.A, zero_params))
                # Reset volume slider
                self.channel_a_volume.setValue(0)
            
            # Handle Channel B
            if self.channel_b_enabled.isChecked():
                self.dg_adapter.enabled_channels.append(Channel.B)
                # In sync mode, use channel A's volume
                if self._sync_enabled:
                    volume = self._last_channel_a_volume
                    self.logger.debug(f"Enabling Channel B in sync mode with volume: {volume}")
                else:
                    volume = self._last_channel_b_volume
                    self.logger.debug(f"Enabling Channel B with volume: {volume}")
                if volume > 0:
                    self.loop.create_task(self.dg_adapter.device.set_strength(Channel.B, volume))
                    self.channel_b_volume.setValue(volume)
            else:
                # Set strength to 0
                self.logger.debug("Disabling Channel B")
                self.loop.create_task(self.dg_adapter.device.set_strength(Channel.B, 0))
                # Reset wave parameters
                zero_params = WaveParameters(frequencies=[0]*4, intensities=[0]*4)
                self.loop.create_task(self.dg_adapter.device.set_wave_parameters(Channel.B, zero_params))
                # Reset volume slider
                self.channel_b_volume.setValue(0)
                
        except Exception as e:
            self.logger.error(f"Error updating channels: {e}")
    
    @Slot()
    def _update_parameters(self):
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
            self.dg_adapter.intensity_pulse_range = pulse_range / 100.0
            self.dg_adapter.min_frequency = min_freq
            self.dg_adapter.max_frequency = max_freq
            
            # Update channels
            self._on_channel_changed()
                
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
    
    @Slot()
    def _on_volume_changed(self):
        """Handle volume slider changes."""
        try:
            self._user_volume_change = True
            
            # Store the user's volume settings
            if self.channel_a_enabled.isChecked():
                self._last_channel_a_volume = self.channel_a_volume.value()
            if self.channel_b_enabled.isChecked() and not self._sync_enabled:
                self._last_channel_b_volume = self.channel_b_volume.value()
            
            # Update volume labels
            self.channel_a_volume_label.setText(str(self.channel_a_volume.value()))
            self.channel_b_volume_label.setText(str(self.channel_b_volume.value()))
            
            # Update device strengths
            if self.channel_a_enabled.isChecked():
                volume_a = self.channel_a_volume.value()
                self.logger.info(f"Setting Channel A strength to {volume_a}")
                self.loop.create_task(self.dg_adapter.device.set_strength(Channel.A, volume_a))
                # In sync mode, apply channel A volume to channel B if it's enabled
                if self._sync_enabled and self.channel_b_enabled.isChecked():
                    self.logger.info(f"Setting Channel B strength to {volume_a} (sync mode)")
                    self.loop.create_task(self.dg_adapter.device.set_strength(Channel.B, volume_a))
                    self.channel_b_volume.setValue(volume_a)  # Update B slider to match A
            
            # Update channel B if it's enabled and not in sync mode
            if self.channel_b_enabled.isChecked() and not self._sync_enabled:
                volume_b = self.channel_b_volume.value()
                self.logger.info(f"Setting Channel B strength to {volume_b}")
                self.loop.create_task(self.dg_adapter.device.set_strength(Channel.B, volume_b))
                
        except Exception as e:
            self.logger.error(f"Error updating volume: {e}")
            
        finally:
            # Reset the user volume change flag after a short delay
            QTimer.singleShot(100, self._reset_user_volume_change)
            
    def _reset_user_volume_change(self):
        """Reset the user volume change flag."""
        self._user_volume_change = False
        
    @Slot()
    def _update_strengths(self):
        """Update strength displays from device."""
        if self._updating_strengths or self._user_volume_change:
            return
            
        try:
            self._updating_strengths = True
            
            if self.dg_adapter.device.is_connected:
                # Update channel A strength if enabled
                if self.channel_a_enabled.isChecked():
                    strength_a = self.dg_adapter.device._current_strengths[Channel.A]
                    current_a = self.channel_a_volume.value()
                    if current_a != strength_a:
                        self.logger.info(f"Updating Channel A strength display from {current_a} to {strength_a}")
                        self._last_channel_a_volume = strength_a
                        self.channel_a_volume.setValue(strength_a)
                        
                # Update channel B strength if enabled and not in sync mode
                if self.channel_b_enabled.isChecked() and not self._sync_enabled:
                    strength_b = self.dg_adapter.device._current_strengths[Channel.B]
                    current_b = self.channel_b_volume.value()
                    if current_b != strength_b:
                        self.logger.info(f"Updating Channel B strength display from {current_b} to {strength_b}")
                        self._last_channel_b_volume = strength_b
                        self.channel_b_volume.setValue(strength_b)
                    
        except Exception as e:
            self.logger.error(f"Error updating strengths: {e}")
        finally:
            self._updating_strengths = False
            
    def closeEvent(self, event):
        """Handle widget close."""
        self._strength_timer.stop()
        super().closeEvent(event) 

    @Slot(bool)
    def _on_connection_changed(self, connected: bool):
        """Handle connection state changes."""
        if connected:
            self.logger.info("Device connected, initializing parameters and strengths")
            self._update_parameters()  # Update parameters when connected
            
            # Initialize channel strengths
            if self.channel_a_enabled.isChecked():
                self.loop.create_task(self.dg_adapter.device.set_strength(Channel.A, self._last_channel_a_volume))
                self.channel_a_volume.setValue(self._last_channel_a_volume)
            if self.channel_b_enabled.isChecked():
                self.loop.create_task(self.dg_adapter.device.set_strength(Channel.B, self._last_channel_b_volume))
                self.channel_b_volume.setValue(self._last_channel_b_volume)
                
            self._strength_timer.start()  # Start strength updates
        else:
            self.logger.info("Device disconnected, stopping strength updates")
            self._strength_timer.stop()  # Stop strength updates when disconnected

    @Slot(int)
    def _on_sync_changed(self, state):
        """Handle sync mode toggle."""
        self.dg_adapter.sync_enabled = bool(state)
        
        # Update UI elements based on sync mode
        if state:
            # When sync is enabled, disable channel B controls
            if hasattr(self, 'channel_b_group'):
                self.channel_b_group.setEnabled(False)
        else:
            # When sync is disabled, enable channel B controls
            if hasattr(self, 'channel_b_group'):
                self.channel_b_group.setEnabled(True) 