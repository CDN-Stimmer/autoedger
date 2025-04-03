from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QColor

class VoiceCommandWidget(QWidget):
    """Widget to display voice command recognition status."""
    
    def __init__(self, voice_controller=None, parent=None):
        super().__init__(parent)
        
        # Store voice controller reference
        self.voice_controller = voice_controller
        
        # Create main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Create frame
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 10px;
                padding: 12px;
            }
        """)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setSpacing(8)
        frame_layout.setContentsMargins(8, 8, 8, 8)
        
        # Create title
        title = QLabel("Voice Status")
        title.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #2196F3;
                padding: 3px 0;
            }
        """)
        title.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(title)
        
        # Create status label
        self.status_label = QLabel("Listening...")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #4CAF50;
                font-size: 14px;
                padding: 3px 0;
            }
        """)
        self.status_label.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(self.status_label)
        
        # Create command label
        self.command_label = QLabel("")
        self.command_label.setStyleSheet("""
            QLabel {
                color: #FF5722;
                font-size: 14px;
                font-weight: bold;
                padding: 3px 0;
                font-family: -apple-system, 'Helvetica Neue', monospace;
            }
        """)
        self.command_label.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(self.command_label)
        
        # Add frame to main layout
        layout.addWidget(frame)
        
        # Set up timer to clear command after 3 seconds
        self.clear_timer = QTimer()
        self.clear_timer.setSingleShot(True)
        self.clear_timer.timeout.connect(self._clear_command)
        
        # Connect to voice controller if provided
        if self.voice_controller:
            self.voice_controller.command_recognized.connect(self.on_command_recognized)
        
    @Slot(str)
    def on_command_recognized(self, command):
        """Handle recognized voice command."""
        self.command_label.setText(f"Command: {command}")
        self.status_label.setText("Command Recognized!")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #4CAF50;
                font-size: 14px;
                font-weight: bold;
                padding: 3px 0;
            }
        """)
        
        # Start timer to clear command after 3 seconds
        self.clear_timer.start(3000)
        
    def _clear_command(self):
        """Clear the command display."""
        self.command_label.setText("")
        self.status_label.setText("Listening...")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #4CAF50;
                font-size: 14px;
                padding: 3px 0;
            }
        """) 