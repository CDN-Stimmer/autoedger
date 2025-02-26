from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QFileDialog,
                             QSlider, QProgressBar, QMessageBox)
from PySide6.QtCore import Qt, Slot, QSettings
import asyncio
from .device_dialog import DeviceSelectionDialog
from .settings_dialog import SettingsDialog
import os
import logging

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self, audio_player, dg_adapter):
        super().__init__()
        self.audio_player = audio_player
        self.dg_adapter = dg_adapter
        
        self.setWindowTitle("Audio Haptic Controller")
        self.resize(800, 400)
        
        # Load settings
        self.settings = QSettings('AudioHaptic', 'AppSettings')
        
        # Set up UI
        self.setup_ui()
        
        # Connect signals
        self.connect_signals()
        
        # Start the device adapter
        self.dg_adapter.start()

    def setup_ui(self):
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Device section
        device_layout = QHBoxLayout()
        self.device_status = QLabel("Device: Not Connected")
        self.connect_button = QPushButton("Connect Device")
        self.connect_button.clicked.connect(self.show_device_dialog)
        device_layout.addWidget(self.device_status)
        device_layout.addWidget(self.connect_button)
        layout.addLayout(device_layout)

        # Battery indicator
        self.battery_label = QLabel("Battery: --")
        layout.addWidget(self.battery_label)

        # Audio file section
        audio_layout = QHBoxLayout()
        self.file_label = QLabel("No file selected")
        self.load_button = QPushButton("Load Audio")
        self.load_button.clicked.connect(self.load_audio_file)
        audio_layout.addWidget(self.file_label)
        audio_layout.addWidget(self.load_button)
        layout.addLayout(audio_layout)

        # Playback controls
        control_layout = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.toggle_playback)
        self.play_button.setEnabled(False)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_playback)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.play_button)
        control_layout.addWidget(self.stop_button)
        layout.addLayout(control_layout)

        # Volume slider
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("Volume:"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.valueChanged.connect(self.set_volume)
        volume_layout.addWidget(self.volume_slider)
        layout.addLayout(volume_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # Settings button
        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self.show_settings_dialog)
        layout.addWidget(self.settings_button)

    def connect_signals(self):
        # Device signals
        self.dg_adapter.device.connection_changed.connect(self.update_device_status)
        self.dg_adapter.device.battery_updated.connect(self.update_battery)
        self.dg_adapter.device.error_occurred.connect(self.show_error)

        # Audio player signals
        self.audio_player.playback_started.connect(self.on_playback_started)
        self.audio_player.playback_stopped.connect(self.on_playback_stopped)
        self.audio_player.position_changed.connect(self.update_progress)

    @Slot()
    def show_device_dialog(self):
        """Show the device selection dialog."""
        dialog = DeviceSelectionDialog(self)
        dialog.device_selected.connect(self.on_device_selected)
        dialog.exec()

    @Slot(str, str)
    def on_device_selected(self, device_name: str, device_address: str):
        """Handle device selection."""
        self.dg_adapter.device.set_device(device_name, device_address)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.dg_adapter.device.connect())
        except Exception as e:
            logger.error(f"Error connecting to device: {e}")

    @Slot()
    def show_settings_dialog(self):
        """Show the settings dialog."""
        dialog = SettingsDialog(self)
        if dialog.exec():
            # Apply settings to the adapter
            self.apply_settings()

    def apply_settings(self):
        """Apply settings from QSettings to the adapter."""
        settings = QSettings('AudioHaptic', 'AppSettings')
        
        # Update enabled channels
        enabled_channels = []
        if settings.value('channels/enable_a', True, bool):
            enabled_channels.append(0)  # Channel A
        if settings.value('channels/enable_b', False, bool):
            enabled_channels.append(1)  # Channel B
            
        self.dg_adapter.enabled_channels = enabled_channels
        self.dg_adapter.sync_enabled = settings.value('channels/sync_enabled', False, bool)
        
        # Update audio processing parameters
        self.dg_adapter.base_intensity_scale = settings.value('audio/base_intensity_scale', 100, int)
        self.dg_adapter.intensity_pulse_range = settings.value('audio/intensity_pulse_range', 50, int)

    @Slot()
    def load_audio_file(self):
        """Open file dialog to select an audio file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio File",
            os.path.expanduser("~/Music"),
            "Audio Files (*.mp3 *.wav *.ogg *.flac);;All Files (*.*)"
        )
        
        if file_path:
            if self.audio_player.load_file(file_path):
                self.file_label.setText(os.path.basename(file_path))
                self.play_button.setEnabled(True)
            else:
                self.show_error("Failed to load audio file")

    @Slot()
    def toggle_playback(self):
        """Toggle audio playback."""
        if self.audio_player.is_playing:
            self.audio_player.pause_playback()
            self.play_button.setText("Play")
        else:
            self.audio_player.start_playback()
            self.play_button.setText("Pause")

    @Slot()
    def stop_playback(self):
        """Stop audio playback."""
        self.audio_player.stop_playback()
        self.play_button.setText("Play")

    @Slot(int)
    def set_volume(self, value: int):
        """Set audio volume."""
        volume = value / 100.0
        self.audio_player.set_volume(volume)

    @Slot(bool)
    def update_device_status(self, connected: bool):
        """Update device connection status."""
        self.device_status.setText(
            f"Device: {'Connected' if connected else 'Not Connected'}")
        self.settings_button.setEnabled(connected)

    @Slot(int)
    def update_battery(self, level: int):
        """Update battery level display."""
        self.battery_label.setText(f"Battery: {level}%")

    @Slot()
    def on_playback_started(self):
        """Handle playback start."""
        self.stop_button.setEnabled(True)
        self.play_button.setText("Pause")

    @Slot()
    def on_playback_stopped(self):
        """Handle playback stop."""
        self.stop_button.setEnabled(False)
        self.play_button.setText("Play")
        self.progress_bar.setValue(0)

    @Slot(int, int)
    def update_progress(self, position: int, duration: int):
        """Update progress bar."""
        if duration > 0:
            progress = (position / duration) * 100
            self.progress_bar.setValue(int(progress))

    @Slot(str)
    def show_error(self, message: str):
        """Show error message dialog."""
        QMessageBox.critical(self, "Error", message)

    def closeEvent(self, event):
        """Handle application closure."""
        # Stop playback first
        self.audio_player.stop_playback()
        
        try:
            # Get the event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create shutdown task
                shutdown_task = asyncio.create_task(self.dg_adapter.stop())
                
                # Wait briefly for shutdown to complete
                loop.call_later(0.5, event.accept)
            else:
                event.accept()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            event.accept() 