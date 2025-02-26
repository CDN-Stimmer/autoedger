"""
Real-time visualization of audio waveform and pressure data.
"""
import matplotlib
matplotlib.use('Qt5Agg')  # Set the backend before importing pyplot
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import time
from collections import deque
from matplotlib.animation import FuncAnimation

class RealtimePlotter:
    def __init__(self, window_size=30):
        """
        Initialize the real-time plotter.
        
        Args:
            window_size (int): Number of seconds of data to display
        """
        self.window_size = window_size
        self.sample_rate = 10  # samples per second
        self.buffer_size = window_size * self.sample_rate
        
        # Initialize data buffers
        self.timestamps = deque(maxlen=self.buffer_size)
        self.pressure_data = deque(maxlen=self.buffer_size)
        self.audio_data = deque(maxlen=self.buffer_size)
        self.freq_data = deque(maxlen=self.buffer_size)
        
        # Setup the figure and subplots
        plt.style.use('dark_background')  # Use dark theme for better visibility
        self.fig, (self.ax1, self.ax2, self.ax3) = plt.subplots(3, 1, figsize=(10, 8))
        self.fig.suptitle('Real-time Audio and Pressure Data', color='white')
        
        # Initialize empty lines
        self.audio_line = Line2D([], [], color='cyan', linewidth=2)
        self.pressure_line = Line2D([], [], color='red', linewidth=2)
        self.freq_line = Line2D([], [], color='yellow', linewidth=2)
        self.ax1.add_line(self.audio_line)
        self.ax2.add_line(self.pressure_line)
        self.ax3.add_line(self.freq_line)
        
        # Configure axes
        for ax in [self.ax1, self.ax2, self.ax3]:
            ax.set_facecolor('black')
            ax.grid(True, color='gray', alpha=0.3)
            
        # Configure audio plot
        self.ax1.set_ylabel('Audio Volume', color='white')
        self.ax1.set_ylim(-0.05, 1.1)  # Range from 0-1 with small padding
        self.ax1.set_title('Audio Volume Level', color='white', pad=5)
        
        # Configure pressure plot
        self.ax2.set_ylabel('Pressure (kPa)', color='white')
        self.ax2.set_title('Pressure Reading', color='white', pad=5)
        
        # Configure frequency plot
        self.ax3.set_ylabel('Frequency (Hz)', color='white')
        self.ax3.set_xlabel('Time (s)', color='white')
        self.ax3.set_ylim(-10, 5000)  # Range from 0-5000Hz
        self.ax3.set_title('Dominant Frequency', color='white', pad=5)
        
        # Add y-axis labels for frequency plot
        self.ax3.set_yticks([0, 1000, 2000, 3000, 4000, 5000])
        self.ax3.set_yticklabels(['0', '1k', '2k', '3k', '4k', '5k'])
        
        # Set tick colors
        for ax in [self.ax1, self.ax2, self.ax3]:
            ax.tick_params(colors='white')
            
        self.fig.tight_layout(rect=[0, 0.03, 1, 0.95])
        
        self.start_time = time.time()
        
        # Set up animation
        self.anim = FuncAnimation(
            self.fig, self._animate, interval=100,  # Update every 100ms
            blit=True, cache_frame_data=False
        )
        
    def _animate(self, frame):
        """Animation function for updating the plot."""
        if not self.timestamps:
            return [self.audio_line, self.pressure_line, self.freq_line]
            
        # Get current time window
        current_time = max(self.timestamps)
        window_start = current_time - self.window_size
        
        # Update time range for all plots
        for ax in [self.ax1, self.ax2, self.ax3]:
            ax.set_xlim(window_start, current_time)
        
        # Update pressure plot y-range
        self.ax2.set_ylim(-1, 40)  # Fixed range from -1 to 40 kPa
        
        # Update line data
        timestamps_list = list(self.timestamps)
        self.audio_line.set_data(timestamps_list, list(self.audio_data))
        self.pressure_line.set_data(timestamps_list, list(self.pressure_data))
        self.freq_line.set_data(timestamps_list, list(self.freq_data))
        
        return [self.audio_line, self.pressure_line, self.freq_line]
    
    def add_data(self, timestamp, pressure, audio_amplitude, frequency):
        """
        Add new data points to the plot.
        
        Args:
            timestamp (float): Current timestamp
            pressure (float): Pressure reading in kPa
            audio_amplitude (float): Audio amplitude value
            frequency (float): Normalized frequency value (0-1)
        """
        self.timestamps.append(timestamp)
        self.pressure_data.append(pressure)
        self.audio_data.append(audio_amplitude)
        self.freq_data.append(frequency)
    
    def show(self):
        """Display the plot window."""
        plt.show(block=False)
    
    def close(self):
        """Close the plot window."""
        if hasattr(self, 'anim'):
            self.anim.event_source.stop()  # Stop the animation
        plt.close(self.fig) 