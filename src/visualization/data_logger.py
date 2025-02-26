"""
Data logging functionality for audio and pressure visualization.
"""
import os
import h5py
import numpy as np
from datetime import datetime

class DataLogger:
    def __init__(self, base_dir='data/visualization'):
        """
        Initialize the data logger.
        
        Args:
            base_dir (str): Base directory for storing visualization data
        """
        self.base_dir = base_dir
        self.current_session = None
        self.buffer_size = 1000  # Number of samples to buffer before writing
        self.reset_buffers()
        
        # Create directory if it doesn't exist
        os.makedirs(base_dir, exist_ok=True)
    
    def reset_buffers(self):
        """Reset data buffers."""
        self.timestamp_buffer = []
        self.pressure_buffer = []
        self.audio_buffer = []
        self.events_buffer = []
    
    def start_session(self):
        """Start a new logging session."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'session_{timestamp}.h5'
        filepath = os.path.join(self.base_dir, filename)
        
        self.current_session = h5py.File(filepath, 'w')
        
        # Create dataset groups
        self.current_session.create_group('time_series')
        self.current_session.create_group('events')
        
        # Add metadata
        self.current_session.attrs['start_time'] = timestamp
        self.current_session.attrs['sample_rate'] = 10  # samples per second
        
        self.reset_buffers()
    
    def add_data_point(self, timestamp, pressure, audio_amplitude):
        """
        Add a new data point to the buffers.
        
        Args:
            timestamp (float): Current timestamp
            pressure (float): Pressure reading in kPa
            audio_amplitude (float): Audio amplitude value
        """
        self.timestamp_buffer.append(timestamp)
        self.pressure_buffer.append(pressure)
        self.audio_buffer.append(audio_amplitude)
        
        if len(self.timestamp_buffer) >= self.buffer_size:
            self._write_buffers()
    
    def add_event(self, timestamp, event_type, value=None):
        """
        Log an event.
        
        Args:
            timestamp (float): Event timestamp
            event_type (str): Type of event (e.g., 'hooray', 'threshold_crossed')
            value (float, optional): Associated value
        """
        self.events_buffer.append({
            'timestamp': timestamp,
            'type': event_type,
            'value': value
        })
    
    def _write_buffers(self):
        """Write buffered data to file."""
        if not self.current_session or not self.timestamp_buffer:
            return
            
        # Get existing datasets or create new ones
        ts_group = self.current_session['time_series']
        
        for name, buffer, dtype in [
            ('timestamps', self.timestamp_buffer, float),
            ('pressure', self.pressure_buffer, float),
            ('audio', self.audio_buffer, float)
        ]:
            if name not in ts_group:
                ts_group.create_dataset(name, data=buffer,
                                     maxshape=(None,),
                                     dtype=dtype)
            else:
                dataset = ts_group[name]
                current_size = dataset.shape[0]
                new_size = current_size + len(buffer)
                dataset.resize((new_size,))
                dataset[current_size:] = buffer
        
        self.reset_buffers()
    
    def close(self):
        """Close the current session."""
        if self.current_session:
            self._write_buffers()  # Write any remaining data
            self.current_session.close()
            self.current_session = None 