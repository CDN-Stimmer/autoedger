import logging
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QListWidget, QListWidgetItem)
from PySide6.QtCore import Qt, Signal
from bleak.backends.device import BLEDevice

class DeviceSelectionDialog(QDialog):
    """Dialog for selecting a BLE device."""
    
    device_selected = Signal(BLEDevice)
    
    def __init__(self, devices, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.setWindowTitle("Select Device")
        self.setModal(True)
        self.resize(400, 300)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Add instructions
        instructions = QLabel("Select a device to connect to:")
        instructions.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(instructions)
        
        # Create device list
        self.device_list = QListWidget()
        self.device_list.itemDoubleClicked.connect(self._on_device_selected)
        layout.addWidget(self.device_list)
        
        # Add devices to list
        for device in devices:
            item = QListWidgetItem()
            name = device.name or "Unknown Device"
            item.setText(f"{name} ({device.address})")
            item.setData(Qt.UserRole, device)
            self.device_list.addItem(item)
            self.logger.debug(f"Added device to list: {name} ({device.address})")
            
        # Create buttons
        button_layout = QHBoxLayout()
        
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.reject)  # Will trigger a new scan
        button_layout.addWidget(refresh_button)
        
        connect_button = QPushButton("Connect")
        connect_button.clicked.connect(self._on_device_selected)
        connect_button.setDefault(True)
        button_layout.addWidget(connect_button)
        
        layout.addLayout(button_layout)
        
    def _on_device_selected(self):
        """Handle device selection."""
        current_item = self.device_list.currentItem()
        if current_item:
            device = current_item.data(Qt.UserRole)
            self.logger.info(f"Device selected: {device.name or 'Unknown'} ({device.address})")
            self.device_selected.emit(device)
            self.accept()
        else:
            self.logger.warning("No device selected") 