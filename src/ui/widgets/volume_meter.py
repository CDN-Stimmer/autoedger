from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QLinearGradient
import logging

class VolumeMeter(QWidget):
    def __init__(self, label="", parent=None):
        super().__init__(parent)
        self.setMinimumWidth(150)  # Swapped dimensions
        self.setMinimumHeight(30)  # Swapped dimensions
        self.logger = logging.getLogger(__name__)
        
        # Set background color
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(40, 40, 40))
        self.setPalette(palette)
        
        # Create layout for label
        layout = QHBoxLayout(self)  # Changed to horizontal layout
        layout.setContentsMargins(5, 0, 0, 0)  # Add left margin for spacing
        layout.setSpacing(2)  # Reduce spacing
        
        # Add label at the left
        self.label = QLabel(label)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color: white; font-weight: bold; font-size: 10px;")
        layout.addWidget(self.label)
        layout.addStretch()  # Push label to left
        
        # Volume level (0.0 to 1.0)
        self._level = 0.0
        self._peak_level = 0.0
        self._peak_decay = 0.001
        
        # Gradient colors with adjusted thresholds
        self._colors = [
            (0.0, QColor("#4CAF50")),    # Green
            (0.4, QColor("#FFA500")),    # Orange (lowered threshold)
            (0.7, QColor("#ff4444"))     # Red (lowered threshold)
        ]
        
    def set_level(self, level):
        """Set the current volume level (0.0 to 1.0)."""
        self._level = max(0.0, min(1.0, level))
        
        # Update peak level
        if self._level > self._peak_level:
            self._peak_level = self._level
        else:
            self._peak_level = max(self._level, self._peak_level - self._peak_decay)
            
        self.logger.debug(f"{self.label.text()} meter - level: {self._level:.3f}, peak: {self._peak_level:.3f}")
        self.update()
        
    def paintEvent(self, event):
        """Paint the volume meter."""
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Calculate meter dimensions
            width = self.width() - self.label.width() - 10  # Leave space for label and margins
            height = self.height()
            x = self.label.width() + 5  # Start after label with margin
            y = 2  # Add margin
            meter_height = height - 4  # Account for margins
            
            self.logger.debug(f"{self.label.text()} meter painted - width: {width}, level_width: {int(width * self._level)}")
            
            # Create gradient (horizontal)
            gradient = QLinearGradient(x, y, x + width, y)
            for pos, color in self._colors:
                gradient.setColorAt(pos, color)
                
            # Draw background
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(30, 30, 30))
            painter.drawRect(x, y, width, meter_height)
            
            # Draw level
            if width > 0:  # Only draw level if we have positive width
                painter.setBrush(gradient)
                level_width = int(width * self._level)
                painter.drawRect(x, y, level_width, meter_height)
                
                # Draw peak indicator
                peak_x = x + int(width * self._peak_level)
                painter.setPen(QColor(255, 255, 255))
                painter.drawLine(peak_x, y, peak_x, y + meter_height)
                
        except Exception as e:
            self.logger.error(f"Error painting volume meter: {e}")
            self.logger.exception("Stack trace:") 