from PySide6.QtCore import QObject, Signal, QThread
import serial
import serial.tools.list_ports
import time
import re

class SerialThread(QThread):
    """Thread for handling serial communication."""
    def __init__(self, serial_monitor):
        super().__init__()
        self.serial_monitor = serial_monitor
        
    def run(self):
        """Run the serial monitoring loop."""
        try:
            # Initialize serial connection
            self.serial_monitor.ser = serial.Serial(
                port=self.serial_monitor.port,
                baudrate=self.serial_monitor.baud_rate,
                timeout=0.1
            )
            
            # Reset input/output buffers
            self.serial_monitor.ser.reset_input_buffer()
            self.serial_monitor.ser.reset_output_buffer()
            
            # Small delay to let Teensy reset
            time.sleep(0.1)
            
            self.serial_monitor.logger.info(f"Serial connection opened on {self.serial_monitor.port}")
            self.serial_monitor.debug_message.emit(f"Connected to {self.serial_monitor.port}")
            
        except Exception as e:
            error_msg = f"Error opening serial port: {e}"
            self.serial_monitor.logger.error(error_msg)
            self.serial_monitor.error_occurred.emit(error_msg)
            self.serial_monitor.debug_message.emit(f"Error opening port: {e}")
            return
            
        while self.serial_monitor.is_running:
            try:
                if self.serial_monitor.ser and self.serial_monitor.ser.is_open:
                    if self.serial_monitor.ser.in_waiting > 0:
                        data = self.serial_monitor.ser.readline().decode('utf-8').strip()
                        if data:
                            self.serial_monitor._process_data(data)
                    time.sleep(0.01)  # Small delay to prevent CPU overuse
                else:
                    error_msg = "Serial port not open"
                    self.serial_monitor.logger.error(error_msg)
                    self.serial_monitor.error_occurred.emit(error_msg)
                    self.serial_monitor.debug_message.emit("Serial port not open")
                    break
                    
            except Exception as e:
                error_msg = f"Error reading serial data: {e}"
                self.serial_monitor.logger.error(error_msg)
                self.serial_monitor.error_occurred.emit(error_msg)
                self.serial_monitor.debug_message.emit(f"Read error: {e}")
                break

class QtSerialMonitor(QObject):
    pressure_updated = Signal(float)  # Emits pressure value
    button_single_press = Signal()    # Emits on single press
    button_double_press = Signal()    # Emits on double press
    debug_message = Signal(str)       # Emits debug messages
    error_occurred = Signal(str)      # Emits error messages

    def __init__(self, logger, port=None, baud_rate=9600):
        super().__init__()
        self.logger = logger
        self.port = port
        self.baud_rate = baud_rate
        self.ser = None
        self.is_running = False
        self.thread = None
        self.pressure_threshold = 20.0  # Default threshold
        
    def _process_data(self, data):
        """Process data received from serial port."""
        try:
            # Log raw data for debugging
            self.logger.debug(f"Serial Debug: Raw data: {data}")
            self.debug_message.emit(f"Raw data: {data}")
            
            # Check for pressure data
            pressure_match = re.search(r"Pressure \(kPa\): ([-\d.]+)", data)
            if pressure_match:
                pressure = float(pressure_match.group(1))
                self.logger.debug(f"Pressure: {pressure} kPa")
                self.pressure_updated.emit(pressure)
                
                # Check if pressure exceeds threshold
                if pressure >= self.pressure_threshold:
                    self.logger.info(f"Pressure threshold exceeded: {pressure} kPa")
                    self.button_single_press.emit()
                return
                
            # Check for button presses
            if "Hooray Button Pressed" in data:
                self.logger.info("Hooray button press detected")
                self.button_single_press.emit()
                return
                
            if "Next File" in data:
                self.logger.info("Next file button press detected")
                self.button_double_press.emit()
                return
                
        except Exception as e:
            error_msg = f"Error processing serial data: {e}"
            self.logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            self.debug_message.emit(f"Error processing data: {e}")
            
    def start(self):
        """Start serial monitoring in a separate thread."""
        if self.is_running:
            return
            
        self.is_running = True
        self.thread = SerialThread(self)
        self.thread.start()
        
    def stop(self):
        """Stop serial monitoring."""
        self.is_running = False
        if self.thread:
            # Give the thread a chance to finish gracefully
            if not self.thread.wait(1000):  # Wait up to 1 second
                self.logger.warning("Serial thread did not finish gracefully")
            self.thread = None
            
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.logger.info("Serial monitoring stopped")
            self.debug_message.emit("Monitoring stopped")
            
    def set_pressure_threshold(self, value):
        """Set the pressure threshold value."""
        self.pressure_threshold = value
        self.logger.debug(f"Pressure threshold set to {value} kPa") 