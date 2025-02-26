import logging
import csv
from datetime import datetime
import os
import sys

class Logger:
    def __init__(self, log_dir='data/logs'):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
        # File paths
        self.pressure_log_file = os.path.join(log_dir, "pressure-log.txt")
        self.contractions_log_file = os.path.join(log_dir, "contractions-log.csv")
        self.application_log_file = os.path.join(log_dir, "application.log")
        
        # Configure logging to output to both file and console
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.application_log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Initialize contractions log CSV with headers if it does not exist
        if not os.path.exists(self.contractions_log_file):
            with open(self.contractions_log_file, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    'Timestamp',
                    'Pressure (kPa)',
                    'Hooray Cycle #'
                ])

    def log_pressure_data(self, average_pressure, max_pressure_at_hooray):
        """Log the average and maximum pressure with a timestamp to a file."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"{timestamp}, Average Pressure: {average_pressure:.2f} kPa, Max Pressure: {max_pressure_at_hooray:.2f} kPa\n"
            with open(self.pressure_log_file, "a") as file:
                file.write(log_entry)
            logging.info(f"Logged pressure data: {log_entry.strip()}")
        except Exception as e:
            logging.error(f"Error logging pressure data: {e}")

    def log_pressure_point(self, pressure, cycle_num):
        """Log a single pressure reading with timestamp and cycle number."""
        try:
            with open(self.contractions_log_file, "a", newline='') as csvfile:
                writer = csv.writer(csvfile)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                writer.writerow([timestamp, round(pressure, 2), cycle_num])
        except Exception as e:
            logging.error(f"Error logging pressure point: {e}")

    @staticmethod
    def info(message):
        logging.info(message)

    @staticmethod
    def error(message):
        logging.error(message)

    @staticmethod
    def warning(message):
        logging.warning(message)

    @staticmethod
    def debug(message):
        logging.debug(message) 