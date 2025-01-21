from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QLinearGradient
import logging

class VolumeMeter(QWidget):
    def __init__(self, label="", parent=None):
        super().__init__(parent)
        self.setMinimumWidth(30)
        self.setMinimumHeight(150)
        self.logger = logging.getLogger(__name__)
        
        # Set background color
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(40, 40, 40))
        self.setPalette(palette)
        
        # Create layout for label
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 5)  # Add bottom margin for spacing
        layout.setSpacing(2)  # Reduce spacing
        
        # Add label at the bottom
        self.label = QLabel(label)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color: white; font-weight: bold; font-size: 10px;")
        layout.addStretch()  # Push label to bottom
        layout.addWidget(self.label)
        
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
            width = self.width()
            height = self.height() - self.label.height() - 10  # Leave space for label and margins
            x = 2  # Add margin
            y = 5  # Start from top with margin
            meter_width = width - 4  # Account for margins
            
            self.logger.debug(f"{self.label.text()} meter painted - height: {height}, level_height: {int(height * self._level)}")
            
            # Create gradient
            gradient = QLinearGradient(x, y + height, x, y)
            for pos, color in self._colors:
                gradient.setColorAt(pos, color)
                
            # Draw background
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(30, 30, 30))
            painter.drawRect(x, y, meter_width, height)
            
            # Draw level
            if height > 0:  # Only draw level if we have positive height
                painter.setBrush(gradient)
                level_height = int(height * self._level)
                painter.drawRect(x, y + height - level_height, meter_width, level_height)
                
                # Draw peak indicator
                peak_y = y + height - int(height * self._peak_level)
                painter.setPen(QColor(255, 255, 255))
                painter.drawLine(x, peak_y, x + meter_width, peak_y)
                
        except Exception as e:
            self.logger.error(f"Error painting volume meter: {e}")
            self.logger.exception("Stack trace:") 