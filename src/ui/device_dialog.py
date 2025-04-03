from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QComboBox, QDialogButtonBox
from PySide6.QtCore import Qt, Signal
import logging

class DeviceSelectionDialog(QDialog):
    """Dialog for selecting audio input/output devices."""
    
    device_selected = Signal(str, str)  # Signal emitted when a device is selected (name, id)
    
    def __init__(self, audio_player, parent=None):
        super().__init__(parent)
        self.audio_player = audio_player
        self.setWindowTitle("Audio Device Selection")
        self.setMinimumWidth(400)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Add info label
        info_label = QLabel("Select audio output device:")
        layout.addWidget(info_label)
        
        # Add output device selection
        output_label = QLabel("Output Device:")
        self.output_combo = QComboBox()
        layout.addWidget(output_label)
        layout.addWidget(self.output_combo)
        
        # Populate devices
        self._populate_devices()
        
        # Add button box
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._on_accepted)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Initialize logger
        self.logger = logging.getLogger(__name__)
    
    def _populate_devices(self):
        """Populate the device combo boxes with available devices."""
        self.output_combo.clear()
        
        # Get available devices
        devices = self.audio_player.get_available_devices()
        self.logger.info(f"Available audio devices: {devices}")
        
        # Add devices to combo box
        for device in devices:
            display_name = device['name']
            if device['is_default']:
                display_name += " (Default)"
            self.output_combo.addItem(display_name, device['id'])
            self.logger.info(f"Added device to combo box: {display_name} (ID: {device['id']})")
        
        # Select current device if available
        current_device = self.audio_player.get_current_device()
        self.logger.info(f"Current audio device: {current_device}")
        if current_device:
            for i in range(self.output_combo.count()):
                if self.output_combo.itemData(i) == current_device['id']:
                    self.output_combo.setCurrentIndex(i)
                    self.logger.info(f"Selected current device in combo box: {current_device['name']}")
                    break
    
    def _on_accepted(self):
        """Handle dialog acceptance."""
        selected_device_id = self.output_combo.currentData()
        if selected_device_id:
            self.logger.info(f"Attempting to set audio output device to: {selected_device_id}")
            if self.audio_player.set_output_device(selected_device_id):
                self.logger.info("Successfully set audio output device")
                self.device_selected.emit(self.output_combo.currentText(), selected_device_id)
                self.accept()
            else:
                self.logger.error("Failed to set audio output device")
                # Show error message
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Error", "Failed to set audio output device")
        else:
            self.logger.warning("No device selected")
            self.reject() 