import serial
import threading
from tkinter import messagebox
import time
from datetime import datetime

class SerialMonitor:
    def __init__(self, logger, pressure_threshold=20.0):
        self.logger = logger
        self.serial_port = "/dev/cu.usbmodem170307301"  # Default port for Teensy
        self.baud_rate = 9600
        self.ser = None
        self.is_running = False
        self.current_pressure = 0.0
        self.max_pressure = 0.0
        self.pressure_threshold = pressure_threshold
        self.current_cycle = 0  # Track the current hooray cycle

    def initialize_serial(self):
        """Initialize serial connection to the Teensy."""
        try:
            self.ser = serial.Serial(self.serial_port, self.baud_rate, timeout=1)
            self.logger.info(f"Connected to Teensy on {self.serial_port}")
            return True
        except serial.SerialException as e:
            self.logger.error(f"Error connecting to Teensy: {e}")
            messagebox.showerror("Serial Error", f"Could not connect to Teensy on {self.serial_port}.\n{e}")
            return False

    def _monitor_loop(self, pressure_callback, hooray_callback, next_file_callback):
        """Monitor pressure readings and button inputs from the Teensy."""
        while self.is_running:
            try:
                if self.ser and self.ser.in_waiting > 0:
                    # Read and decode the data from the serial port
                    data = self.ser.readline().decode("utf-8").strip()

                    # Handle pressure readings
                    if data.startswith("Pressure (kPa):"):
                        pressure_value = data.split(":")[1].strip()
                        self.current_pressure = float(pressure_value)
                        self.max_pressure = max(self.max_pressure, self.current_pressure)
                        self.logger.debug(f"Pressure: {self.current_pressure} kPa")
                        
                        # Log each pressure reading with the current cycle number
                        self.logger.log_pressure_point(self.current_pressure, self.current_cycle)
                        
                        if pressure_callback:
                            pressure_callback(self.current_pressure)

                        # Check if pressure exceeds the threshold
                        if self.current_pressure >= self.pressure_threshold and hooray_callback:
                            self.logger.info(f"Triggering hooray! Current Pressure: {self.current_pressure}, Threshold: {self.pressure_threshold}")
                            hooray_callback()

                    # Handle button inputs
                    elif "Hooray Button Pressed" in data and hooray_callback:
                        self.logger.info("Hooray button action triggered!")
                        hooray_callback()
                    elif "Next File" in data and next_file_callback:
                        self.logger.info("Next file action triggered!")
                        next_file_callback()

            except Exception as e:
                self.logger.error(f"Error reading pressure data: {e}")

    def start_monitoring(self, pressure_callback=None, hooray_callback=None, next_file_callback=None):
        """Start monitoring the serial port in a separate thread."""
        if self.initialize_serial():
            self.is_running = True
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop,
                args=(pressure_callback, hooray_callback, next_file_callback),
                daemon=True
            )
            self.monitor_thread.start()
            self.logger.info("Serial monitoring thread started")
        else:
            self.logger.error("Failed to start serial monitoring - could not initialize serial connection")

    def stop(self):
        """Stop the serial monitor and close the connection."""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join()
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.logger.info("Serial connection closed")

    def set_pressure_threshold(self, threshold):
        """Update the pressure threshold."""
        self.pressure_threshold = threshold
        self.logger.debug(f"Pressure threshold updated to {threshold} kPa")

    def get_current_pressure(self):
        """Get the current pressure reading."""
        return self.current_pressure

    def get_max_pressure(self):
        """Get the maximum pressure reading."""
        return self.max_pressure

    def reset_max_pressure(self):
        """Reset the maximum pressure reading."""
        self.max_pressure = 0.0

    def set_cycle(self, cycle_num):
        """Update the current cycle number."""
        self.current_cycle = cycle_num
        self.logger.debug(f"Updated to cycle #{cycle_num}")

    def stop_monitoring(self):
        """Stop monitoring serial data"""
        self.is_monitoring = False
        if hasattr(self, 'serial') and self.serial and self.serial.is_open:
            self.serial.close() 