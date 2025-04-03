from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                                 QHBoxLayout, QPushButton, QLabel, QFrame, QSpacerItem, QSizePolicy, QSlider, QSpinBox, QStatusBar,
                                 QScrollArea, QGridLayout, QStackedWidget)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QFont
from ui.widgets.audio_control_widget import AudioControlWidget
from ui.widgets.voice_command_widget import VoiceCommandWidget
from audio.voice_control import VoiceController
from ui.device_dialog import DeviceSelectionDialog
import os

class MainWindow(QMainWindow):
    def __init__(self, logger, audio_player):
        super().__init__()
        self.logger = logger
        self.audio_player = audio_player
        
        # Initialize voice control with correct model path using relative paths
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_path = os.path.join(script_dir, "data", "model")
        self.logger.info(f"Using voice model path: {model_path}")
        self.voice_controller = VoiceController(model_path, logger)
        self.voice_controller.command_recognized.connect(self._handle_voice_command)
        
        # Set window properties
        self.setWindowTitle("Audio Control")
        self.setMinimumSize(400, 600)
        
        # Set window style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QWidget {
                font-family: -apple-system, 'Helvetica Neue', sans-serif;
            }
        """)
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create stacked widget for different views
        self.stacked_widget = QStackedWidget()
        
        # Create audio control view
        audio_view = QWidget()
        audio_layout = QVBoxLayout(audio_view)
        audio_layout.setContentsMargins(0, 0, 0, 0)
        self.audio_control = AudioControlWidget(audio_player)
        audio_layout.addWidget(self.audio_control)
        self.stacked_widget.addWidget(audio_view)
        
        # Create voice commands view
        voice_view = QWidget()
        voice_layout = QVBoxLayout(voice_view)
        voice_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add voice command widget
        self.voice_command = VoiceCommandWidget(voice_controller=self.voice_controller)
        voice_layout.addWidget(self.voice_command)
        
        # Add voice commands reference
        commands_frame = QFrame()
        commands_frame.setStyleSheet("""
            QFrame {
                background-color: #e8f0fe;
                border-radius: 12px;
                padding: 12px;
            }
        """)
        commands_layout = QVBoxLayout(commands_frame)
        
        # Title for commands section
        commands_title = QLabel("Voice Commands")
        commands_title.setStyleSheet("""
            QLabel {
                color: #1a73e8;
                font-size: 16px;
                font-weight: 500;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI';
                padding-bottom: 8px;
                border-bottom: 1px solid #dadce0;
            }
        """)
        commands_layout.addWidget(commands_title)
        
        # Add command descriptions
        commands = [
            ("Play/Pause", "Toggle playback"),
            ("Next", "Play next track"),
            ("Previous", "Play previous track"),
            ("Stop", "Stop playback"),
            ("Random", "Play random track"),
            ("Loop", "Toggle loop mode"),
            ("Volume Up/Down", "Adjust volume"),
            ("Favorite", "Add current track to favorites"),
            ("Unfavorite", "Remove current track from favorites")
        ]
        
        for command, description in commands:
            command_layout = QHBoxLayout()
            
            cmd_label = QLabel(command)
            cmd_label.setStyleSheet("""
                QLabel {
                    color: #1a73e8;
                    font-weight: 500;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI';
                }
            """)
            desc_label = QLabel(description)
            desc_label.setStyleSheet("""
                QLabel {
                    color: #5f6368;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI';
                }
            """)
            
            command_layout.addWidget(cmd_label)
            command_layout.addWidget(desc_label)
            command_layout.addStretch()
            
            commands_layout.addLayout(command_layout)
        
        voice_layout.addWidget(commands_frame)
        self.stacked_widget.addWidget(voice_view)
        
        # Add stacked widget to main layout
        layout.addWidget(self.stacked_widget)
        
        # Create bottom navigation bar
        nav_bar = QFrame()
        nav_bar.setStyleSheet("""
            QFrame {
                background-color: white;
                border-top: 1px solid #e0e0e0;
            }
        """)
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setSpacing(8)
        
        # Create navigation buttons
        self.audio_button = QPushButton("Playback")
        self.voice_button = QPushButton("Voice Command")
        
        for button in [self.audio_button, self.voice_button]:
            button.setStyleSheet("""
                QPushButton {
                    padding: 8px 16px;
                    border: none;
                    border-radius: 16px;
                    background: #f8f9fa;
                    color: #5f6368;
                    font-size: 14px;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI';
                }
                QPushButton:checked {
                    background: #e8f0fe;
                    color: #1a73e8;
                }
            """)
            button.setCheckable(True)
            nav_layout.addWidget(button)
            
        self.audio_button.setChecked(True)  # Start with audio view
        
        nav_layout.addStretch()  # Push buttons to the left
        layout.addLayout(nav_layout)
        
        # Create status bar with modern styling
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: white;
                color: #666;
                padding: 3px 8px;
                border-top: 1px solid #e0e0e0;
                font-size: 12px;
            }
        """)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Set up update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(1000)  # Update every second
        
        # Start voice control
        self.voice_controller.start_listening()

        # Connect navigation buttons
        self.audio_button.clicked.connect(lambda: self._switch_view(0))
        self.voice_button.clicked.connect(lambda: self._switch_view(1))

    def _handle_voice_command(self, command):
        """Handle voice commands."""
        self.logger.debug(f"Received voice command: {command}")

        # Update voice command widget
        self.audio_control.voice_status.setText(f"Command: {command}")

        if command in ["now", "edge"]:
            self.audio_control._on_hooray()
        elif command == "hold":
            # Assuming _on_hold exists in AudioControlWidget, add if needed
            if hasattr(self.audio_control, '_on_hold'): 
                self.audio_control._on_hold()
            else:
                self.logger.warning("_on_hold method not found in AudioControlWidget")
        elif command == "skip":
            self.audio_player.play_random_file()
        elif command in ["up", "more"]:
            current = self.audio_control.volume_slider.value()
            self.audio_control.volume_slider.setValue(min(100, current + 10))
        elif command in ["down", "less"]:
            current = self.audio_control.volume_slider.value()
            self.audio_control.volume_slider.setValue(max(0, current - 10))
        elif command == "max":
            self.audio_control.volume_slider.setValue(100)
        elif command == "half":
            self.audio_control.volume_slider.setValue(50)
        elif command == "pause":
            if hasattr(self.audio_player, 'pause'):
                self.audio_player.pause()
            else:
                 self.logger.warning("pause method not found in audio_player")
        elif command == "play":
            if hasattr(self.audio_player, 'play'):
                self.audio_player.play()
            else:
                 self.logger.warning("play method not found in audio_player")
        elif command == "stop":
            self.audio_player.stop_playback()
        elif command == "yes":
            self.status_bar.showMessage("Yes indicator triggered", 2000)
        elif command == "favorite":
            current_file = self.audio_control.file_combo.currentText()
            if current_file:
                # Logic to add to favorites (potentially toggle)
                # Assuming add_to_favorites exists and handles UI update
                if hasattr(self.audio_player, 'add_to_favorites'):
                    if self.audio_player.add_to_favorites():
                        self.status_bar.showMessage(f"Added {current_file} to favorites", 2000)
                else:
                     self.logger.warning("add_to_favorites method not found in audio_player")
        # Add other commands as needed
        # else:
        #     self.logger.warning(f"Unknown voice command: {command}")

        # Update status bar to show the recognized command
        self.status_bar.showMessage(f"Voice command: {command}", 3000)

        # Clear the command display after 3 seconds
        QTimer.singleShot(3000, lambda: self.audio_control.voice_status.setText("Listening..."))

    def update_status(self):
        """Update status bar with current state."""
        volume = int(self.audio_player.get_volume() * 100)
        self.status_bar.showMessage(f"Volume: {volume}%")

    def closeEvent(self, event):
        """Handle window close event."""
        self.logger.info("Closing application, stopping voice listener.")
        try:
            # Stop voice control when window is closed
            self.voice_controller.stop_listening()
        except Exception as e:
            self.logger.error(f"Error stopping voice controller: {e}")
        super().closeEvent(event)

    def _switch_view(self, index):
        """Switch between views and update button states."""
        self.stacked_widget.setCurrentIndex(index)
        self.audio_button.setChecked(index == 0)
        self.voice_button.setChecked(index == 1)

    def _show_device_dialog(self):
        """Show the device selection dialog."""
        dialog = DeviceSelectionDialog(self.audio_player, self)
        dialog.device_selected.connect(self._on_device_selected)
        dialog.exec()
        
    def _on_device_selected(self, device_name, device_id):
        """Handle device selection."""
        print(f"Selected audio device: {device_name} (ID: {device_id})")