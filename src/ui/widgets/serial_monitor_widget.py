from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                 QLabel, QSpinBox, QDoubleSpinBox, QComboBox,
                                 QFrame, QMessageBox, QTextEdit)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor
import serial.tools.list_ports

class SerialMonitorWidget(QWidget):
    def __init__(self, serial_monitor, parent=None):
        super().__init__(parent)
        self.serial_monitor = serial_monitor
        self.logger = serial_monitor.logger
        
        # Create main layout
        main_layout = QVBoxLayout(self)
        
        # Create frame
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel)
        frame_layout = QVBoxLayout(frame)
        
        # Create title
        title = QLabel("Serial Monitor")
        title.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(title)
        
        # Create port selection
        port_layout = QHBoxLayout()
        port_label = QLabel("Port:")
        port_layout.addWidget(port_label)
        
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(150)
        port_layout.addWidget(self.port_combo)
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._refresh_ports)
        port_layout.addWidget(self.refresh_button)
        
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self._on_connect_clicked)
        port_layout.addWidget(self.connect_button)
        
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self._on_disconnect_clicked)
        self.disconnect_button.setEnabled(False)
        port_layout.addWidget(self.disconnect_button)
        
        frame_layout.addLayout(port_layout)
        
        # Create connection status
        status_layout = QHBoxLayout()
        status_label = QLabel("Status:")
        status_layout.addWidget(status_label)
        
        self.connection_status = QLabel("Disconnected")
        self.connection_status.setStyleSheet("color: red")
        status_layout.addWidget(self.connection_status)
        
        frame_layout.addLayout(status_layout)
        
        # Create threshold control
        threshold_layout = QHBoxLayout()
        threshold_label = QLabel("Threshold (kPa):")
        threshold_layout.addWidget(threshold_label)
        
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0, 100)
        self.threshold_spin.setValue(20.0)
        self.threshold_spin.setSingleStep(0.5)
        self.threshold_spin.valueChanged.connect(self._on_threshold_changed)
        threshold_layout.addWidget(self.threshold_spin)
        
        frame_layout.addLayout(threshold_layout)
        
        # Create pressure displays
        readings_frame = QFrame()
        readings_frame.setFrameStyle(QFrame.StyledPanel)
        readings_layout = QVBoxLayout(readings_frame)
        
        # Current pressure display
        current_layout = QHBoxLayout()
        current_label = QLabel("Current Pressure:")
        current_layout.addWidget(current_label)
        
        self.pressure_label = QLabel("0.0 kPa")
        self.pressure_label.setStyleSheet("font-size: 14px; font-weight: bold")
        current_layout.addWidget(self.pressure_label)
        
        readings_layout.addLayout(current_layout)
        
        # Max pressure display
        max_layout = QHBoxLayout()
        max_label = QLabel("Max Pressure:")
        max_layout.addWidget(max_label)
        
        self.max_pressure_label = QLabel("0.0 kPa")
        self.max_pressure_label.setStyleSheet("font-size: 14px; font-weight: bold")
        max_layout.addWidget(self.max_pressure_label)
        
        readings_layout.addLayout(max_layout)
        
        frame_layout.addWidget(readings_frame)
        
        # Create debug log
        debug_label = QLabel("Debug Log:")
        frame_layout.addWidget(debug_label)
        
        self.debug_log = QTextEdit()
        self.debug_log.setReadOnly(True)
        self.debug_log.setMaximumHeight(100)
        frame_layout.addWidget(self.debug_log)
        
        # Add frame to main layout
        main_layout.addWidget(frame)
        
        # Connect serial monitor signals
        self.serial_monitor.pressure_updated.connect(self._on_pressure_updated)
        self.serial_monitor.error_occurred.connect(self._on_error)
        self.serial_monitor.debug_message.connect(self._on_debug_message)
        
        # Initial port refresh
        self._refresh_ports()
        
    def _refresh_ports(self):
        """Refresh the list of available serial ports."""
        current_port = self.port_combo.currentText()
        self.port_combo.clear()
        
        # Add available ports
        teensy_port = "/dev/cu.usbmodem170307301"
        ports = list(serial.tools.list_ports.comports())
        
        # First check if our specific Teensy port exists
        if any(p.device == teensy_port for p in ports):
            self.port_combo.addItem(teensy_port)
            self._add_debug_message("Found Teensy at " + teensy_port)
            self.port_combo.setCurrentText(teensy_port)
        else:
            # Add other available ports
            for port in ports:
                if "USB" in port.device:
                    self.port_combo.addItem(port.device)
            self._add_debug_message("Specific Teensy port not found, showing available USB ports")
            
        # Update connect button state
        self.connect_button.setEnabled(self.port_combo.count() > 0)
            
    def _on_connect_clicked(self):
        """Handle connect button click."""
        port = self.port_combo.currentText()
        if not port:
            self.logger.warning("No port selected")
            return
            
        try:
            # Update serial monitor port and start monitoring
            self.serial_monitor.port = port
            self.serial_monitor.start()
            
            # Update UI state
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(True)
            self.port_combo.setEnabled(False)
            self.refresh_button.setEnabled(False)
            self.connection_status.setText("Connected")
            self.connection_status.setStyleSheet("color: green")
            
            self.logger.info(f"Started monitoring on {port}")
        except Exception as e:
            self.logger.error(f"Failed to start monitoring: {e}")
            self._on_error(str(e))
            
    def _on_disconnect_clicked(self):
        """Handle disconnect button click."""
        try:
            self.serial_monitor.stop()
            
            # Update UI state
            self.connect_button.setEnabled(True)
            self.disconnect_button.setEnabled(False)
            self.port_combo.setEnabled(True)
            self.refresh_button.setEnabled(True)
            self.connection_status.setText("Disconnected")
            self.connection_status.setStyleSheet("color: red")
            
            self.logger.info("Stopped monitoring")
        except Exception as e:
            self.logger.error(f"Failed to stop monitoring: {e}")
            self._on_error(str(e))
            
    def _on_threshold_changed(self, value):
        """Handle threshold value change."""
        self.serial_monitor.set_pressure_threshold(value)
        
    @Slot(float)
    def _on_pressure_updated(self, pressure):
        """Handle pressure update."""
        self.pressure_label.setText(f"{pressure:.1f} kPa")
        
        # Update max pressure
        current_max = float(self.max_pressure_label.text().split()[0])
        if pressure > current_max:
            self.max_pressure_label.setText(f"{pressure:.1f} kPa")
            
    @Slot(str)
    def _on_error(self, error_msg):
        """Handle serial monitor error."""
        QMessageBox.warning(self, "Serial Monitor Error", error_msg)
        self._add_debug_message(f"ERROR: {error_msg}")
        
        # Reset connection state
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.port_combo.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.connection_status.setText("Error")
        self.connection_status.setStyleSheet("color: red")
        
    @Slot(str)
    def _on_debug_message(self, message):
        """Handle debug message."""
        self._add_debug_message(message)
        
    def _add_debug_message(self, message):
        """Add message to debug log."""
        self.debug_log.append(f"{message}") 