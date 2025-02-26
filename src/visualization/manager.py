"""
Manager class for coordinating visualization and data logging.
"""
import numpy as np
from .realtime_plot import RealtimePlotter
from log_utils.metrics_logger import MetricsLoggerAdapter
import time
import threading
import queue
import math
import os
import logging
from PySide6.QtMultimedia import QAudioBuffer, QAudioFormat
from mutagen.mp3 import MP3
from PySide6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib
matplotlib.use('Qt5Agg')  # Set the backend before importing pyplot

class PlotWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.plotter = RealtimePlotter()
        self.canvas = FigureCanvas(self.plotter.fig)
        self.layout.addWidget(self.canvas)
        self.setWindowTitle("Real-time Data")
        self.resize(800, 600)

class VisualizationManager:
    def __init__(self, audio_control_widget=None):
        """Initialize the visualization manager."""
        self.plot_window = None
        self.data_logger = MetricsLoggerAdapter()
        self.is_running = False
        self.data_queue = queue.Queue()
        self.viz_thread = None
        self.last_update = time.time()
        self.sample_rate = 44100  # Standard audio sample rate
        self.buffer_size = 2048  # Buffer size for FFT
        self.current_file = None
        self.audio_control_widget = audio_control_widget
        self.last_amplitude = 0.0
        self.last_frequency = 0.0
        self.current_cycle = 0
        self.start_time = time.time()  # Initialize start_time
        self.logger = logging.getLogger(__name__)  # Initialize logger
        
        # Connect to audio player signals if available
        if self.audio_control_widget and self.audio_control_widget.audio_player:
            player = self.audio_control_widget.audio_player
            player.audio_data_ready.connect(self._on_audio_data)
            player.hooray_cycle_complete.connect(self._on_hooray_cycle_complete)
            player.playback_started.connect(self._on_playback_started)

    def _on_audio_data(self, amplitude, frequency):
        """Handle incoming audio data."""
        self.last_amplitude = amplitude
        self.last_frequency = frequency
        self.data_logger.set_frequency(frequency)
        
    def _on_hooray_cycle_complete(self):
        """Handle completion of a hooray cycle."""
        self.current_cycle += 1
        self.data_logger.set_cycle_number(self.current_cycle)
        self.log_event("hooray_complete")
        
    def _on_playback_started(self, filename):
        """Handle new playback starting."""
        self.current_file = filename
        self.data_logger.set_current_file(filename)
        # Reset visualization data
        if self.plot_window and self.plot_window.plotter:
            self.plot_window.plotter.timestamps.clear()
            self.plot_window.plotter.pressure_data.clear()
            self.plot_window.plotter.audio_data.clear()
            self.plot_window.plotter.freq_data.clear()
        self.last_amplitude = 0.0
        self.last_frequency = 0.0
        self.start_time = time.time()  # Reset time reference
        
    def start(self):
        """Start visualization and logging."""
        self.is_running = True
        self.current_cycle = 0  # Reset cycle counter on start
        self.data_logger.start_session()
        
        # Create plot window
        self.plot_window = PlotWindow()
        self.plot_window.show()
        
        # Start data processing thread
        self.viz_thread = threading.Thread(target=self._process_data, daemon=True)
        self.viz_thread.start()

    def get_current_file(self):
        """Get the name of the current audio file."""
        if self.audio_control_widget and self.audio_control_widget.audio_player:
            return os.path.basename(self.audio_control_widget.audio_player.current_file or '')
        return None
        
    def _get_audio_data(self):
        """Get current audio amplitude and frequency data."""
        return self.last_amplitude, self.last_frequency
        
    def update(self, pressure):
        """Update visualization with new pressure data."""
        if not self.is_running:
            return
            
        try:
            current_time = time.time() - self.start_time
            
            # Get audio data
            amplitude, frequency = self._get_audio_data()
            
            # Add data to queue
            self.data_queue.put((current_time, pressure, amplitude, frequency))
            
            # Log data
            self.data_logger.add_data_point(current_time, pressure, amplitude)
            
            # Update last known values
            self.last_amplitude = amplitude
            self.last_frequency = frequency
        except Exception as e:
            self.logger.error(f"Error updating visualization: {e}")

    def update_audio_metrics(self, amplitude, frequency):
        """Update audio metrics."""
        self.last_amplitude = amplitude
        self.last_frequency = frequency
        self.data_logger.set_frequency(frequency)
        
    def set_cycle(self, cycle_num):
        """Update the current cycle number."""
        self.current_cycle = cycle_num
        self.data_logger.set_cycle_number(cycle_num)
        self.log_event("cycle_changed", None)
        
    def log_event(self, event_type, value=None):
        """Log a specific event."""
        current_time = time.time() - self.start_time
        self.data_logger.add_event(current_time, event_type, value)
        
    def stop(self):
        """Stop visualization and logging."""
        self.is_running = False
        self.data_logger.close()
        if self.plot_window:
            self.plot_window.plotter.fig.clear()
            self.plot_window.canvas.close()
            self.plot_window.close()
            self.plot_window.deleteLater()  # Ensure Qt properly destroys the window
            self.plot_window = None
        if self.viz_thread and self.viz_thread.is_alive():
            self.viz_thread.join(timeout=1.0)  # Don't wait forever

    def _process_data(self):
        """Process data points from the queue."""
        while self.is_running:
            try:
                # Process all available data points
                while not self.data_queue.empty():
                    timestamp, pressure, amplitude, frequency = self.data_queue.get_nowait()
                    if self.plot_window and self.plot_window.plotter:
                        self.plot_window.plotter.add_data(timestamp, pressure, amplitude, frequency)
            except queue.Empty:
                pass
                
            time.sleep(0.01)  # Check queue every 10ms 