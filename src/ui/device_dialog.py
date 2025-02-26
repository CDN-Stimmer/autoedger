from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QComboBox, QDialogButtonBox
from PySide6.QtCore import Qt

class DeviceSelectionDialog(QDialog):
    """Dialog for selecting audio input/output devices."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Audio Device Selection")
        self.setMinimumWidth(400)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Add info label
        info_label = QLabel("Select audio devices:")
        layout.addWidget(info_label)
        
        # Add input device selection
        input_label = QLabel("Input Device:")
        self.input_combo = QComboBox()
        layout.addWidget(input_label)
        layout.addWidget(self.input_combo)
        
        # Add output device selection
        output_label = QLabel("Output Device:")
        self.output_combo = QComboBox()
        layout.addWidget(output_label)
        layout.addWidget(self.output_combo)
        
        # Add button box
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def get_selected_devices(self):
        """Return the selected input and output devices."""
        input_device = self.input_combo.currentText()
        output_device = self.output_combo.currentText()
        return input_device, output_device 