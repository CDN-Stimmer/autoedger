from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import Qt, Slot, QPointF
from PySide6.QtGui import QPainter
import numpy as np
from collections import deque
import time

class VisualizationWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize data storage
        self.window_size = 1000  # 10 seconds at 100Hz
        self.pressure_data = deque(maxlen=self.window_size)
        self.time_data = deque(maxlen=self.window_size)
        self.start_time = time.time()
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Create chart
        self.chart = QChart()
        self.chart.setTitle("Pressure Monitor")
        self.chart.setAnimationOptions(QChart.NoAnimation)
        
        # Create series for pressure data
        self.pressure_series = QLineSeries()
        self.pressure_series.setName("Pressure (kPa)")
        self.chart.addSeries(self.pressure_series)
        
        # Create axes
        self.time_axis = QValueAxis()
        self.time_axis.setTitleText("Time (s)")
        self.time_axis.setRange(0, 10)  # 10 second window
        
        self.pressure_axis = QValueAxis()
        self.pressure_axis.setTitleText("Pressure (kPa)")
        self.pressure_axis.setRange(0, 15)
        
        # Attach axes to chart
        self.chart.addAxis(self.time_axis, Qt.AlignBottom)
        self.chart.addAxis(self.pressure_axis, Qt.AlignLeft)
        self.pressure_series.attachAxis(self.time_axis)
        self.pressure_series.attachAxis(self.pressure_axis)
        
        # Create chart view
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        
        # Add to layout
        layout.addWidget(self.chart_view)
        
        # Initialize update timer
        self.last_update = time.time()
        self.update_interval = 0.05  # 50ms = 20Hz update rate
        
    @Slot(float)
    def update_pressure(self, pressure):
        """Update the pressure plot with new data."""
        current_time = time.time()
        
        # Add new data point
        self.pressure_data.append(pressure)
        self.time_data.append(current_time - self.start_time)
        
        # Update plot if enough time has passed
        if current_time - self.last_update >= self.update_interval:
            self._update_plot()
            self.last_update = current_time
            
    def _update_plot(self):
        """Update the plot with current data."""
        # Clear existing points
        self.pressure_series.clear()
        
        # Convert deques to numpy arrays for vectorized operations
        times = np.array(self.time_data)
        pressures = np.array(self.pressure_data)
        
        # Adjust time axis if needed
        if len(times) > 0:
            latest_time = times[-1]
            self.time_axis.setRange(max(0, latest_time - 10), latest_time)
            
            # Add all points to series
            points = [QPointF(t, p) for t, p in zip(times, pressures)]
            self.pressure_series.append(points)
            
            # Update pressure axis range if needed
            if len(pressures) > 0:
                max_pressure = max(pressures)
                if max_pressure > self.pressure_axis.max():
                    self.pressure_axis.setRange(0, max_pressure * 1.2)
                    
    @Slot()
    def on_playback_started(self, filename):
        """Handle audio playback start."""
        self.chart.setTitle(f"Pressure Monitor - Playing: {filename}")
        
    @Slot()
    def on_playback_stopped(self):
        """Handle audio playback stop."""
        self.chart.setTitle("Pressure Monitor") 