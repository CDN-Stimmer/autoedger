"""
Logging utilities for metrics collection.
"""
import csv
import os
from datetime import datetime
import threading

class MetricsLogger:
    def __init__(self, log_dir='data/logs'):
        """Initialize the metrics logger.
        
        Args:
            log_dir (str): Directory to store log files
        """
        self.log_dir = log_dir
        self.current_file = None
        self.writer = None
        self.lock = threading.Lock()
        self._ensure_log_dir()
        self.start_new_log()
        
    def _ensure_log_dir(self):
        """Ensure the log directory exists."""
        os.makedirs(self.log_dir, exist_ok=True)
        
    def start_new_log(self):
        """Start a new log file."""
        if self.current_file:
            self.current_file.close()
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'metrics_{timestamp}.csv'
        filepath = os.path.join(self.log_dir, filename)
        
        self.current_file = open(filepath, 'w', newline='')
        self.writer = csv.writer(self.current_file)
        
        # Write header
        self.writer.writerow([
            'timestamp',
            'pressure_kpa',
            'volume_db',
            'frequency_hz',
            'cycle_number',
            'audio_file',
            'event_type',
            'playhead_time'
        ])
        self.current_file.flush()
        
    def log_metrics(self, pressure, volume, frequency, cycle_number, audio_file, event_type='data', playhead_time=None):
        """Log a set of metrics.
        
        Args:
            pressure (float): Pressure reading in kPa
            volume (float): Volume level in dB
            frequency (float): Frequency in Hz
            cycle_number (int): Current hooray cycle number
            audio_file (str): Name of the audio file being played
            event_type (str): Type of event (e.g., 'data', 'hooray', 'next_file')
            playhead_time (float): Current playback time in seconds
        """
        with self.lock:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
            self.writer.writerow([
                timestamp,
                f"{pressure:.2f}",
                f"{volume:.2f}",
                f"{frequency:.1f}",
                cycle_number,
                audio_file or 'None',
                event_type,
                f"{playhead_time:.1f}" if playhead_time is not None else ''
            ])
            self.current_file.flush()
            
    def close(self):
        """Close the current log file."""
        if self.current_file:
            self.current_file.close()
            self.current_file = None
            self.writer = None 

class MetricsLoggerAdapter:
    """Adapter class to make MetricsLogger match the DataLogger interface."""
    def __init__(self, log_dir='data/logs'):
        self.metrics_logger = MetricsLogger(log_dir)
        self.cycle_number = 0
        self.current_file = None
        self.last_frequency = 0.0

    def start_session(self):
        """Start a new logging session."""
        self.metrics_logger.start_new_log()
        self.cycle_number = 0
        self.current_file = None
        self.last_frequency = 0.0

    def add_data_point(self, timestamp, pressure, audio_amplitude):
        """Add a new data point to the log."""
        self.metrics_logger.log_metrics(
            pressure=pressure,
            volume=audio_amplitude,
            frequency=self.last_frequency,
            cycle_number=self.cycle_number,
            audio_file=self.current_file,
            event_type='data'
        )

    def add_event(self, timestamp, event_type, value=None):
        """Add an event to the log.
        
        Args:
            timestamp: Current timestamp
            event_type: Type of event
            value: Optional value associated with the event (e.g., playhead time)
        """
        try:
            playhead_time = float(value) if value is not None else None
        except (ValueError, TypeError):
            playhead_time = None
            
        self.metrics_logger.log_metrics(
            pressure=0.0,  # No pressure reading for events
            volume=0.0,    # No volume reading for events
            frequency=self.last_frequency,
            cycle_number=self.cycle_number,
            audio_file=self.current_file,
            event_type=event_type,
            playhead_time=playhead_time
        )

    def close(self):
        """Close the current session."""
        self.metrics_logger.close()

    def set_current_file(self, filename):
        """Set the current audio file name."""
        self.current_file = filename

    def set_cycle_number(self, cycle_num):
        """Set the current cycle number."""
        self.cycle_number = cycle_num

    def set_frequency(self, frequency):
        """Set the last known frequency."""
        self.last_frequency = frequency 