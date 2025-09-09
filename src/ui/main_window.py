from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                                 QHBoxLayout, QPushButton, QLabel, QFrame, QSpacerItem, QSizePolicy, QSlider, QSpinBox, QStatusBar,
                                 QScrollArea, QGridLayout, QStackedWidget)
from PySide6.QtCore import Qt, QTimer, QDateTime
from PySide6.QtGui import QIcon, QFont
from ui.widgets.audio_control_widget import AudioControlWidget
from ui.widgets.voice_command_widget import VoiceCommandWidget
from audio.voice_control import VoiceController
from ui.device_dialog import DeviceSelectionDialog
import os
import csv

class MainWindow(QMainWindow):
    def __init__(self, logger, audio_player):
        super().__init__()
        self.logger = logger
        self.audio_player = audio_player
        self.session_start_ms = QDateTime.currentMSecsSinceEpoch()
        
        # Initialize voice control with correct model path using relative paths
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_path = os.path.join(script_dir, "data", "model")
        self.logger.info(f"Using voice model path: {model_path}")
        self.voice_controller = VoiceController(model_path, logger)
        self.voice_controller.command_recognized.connect(self._handle_voice_command)
        
        # Set window properties
        self.setWindowTitle("The Controller")
        self.setMinimumSize(400, 600)
        
        # Top App Bar
        app_bar = QFrame()
        app_bar.setObjectName("AppBar")
        app_bar_layout = QHBoxLayout(app_bar)
        app_bar_layout.setContentsMargins(12, 6, 12, 6)
        # Removed left title label
        app_bar_layout.addStretch()

        # Removed theme toggle
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Add app bar at the top
        layout.addWidget(app_bar)
        
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
        commands_frame.setObjectName("Card")
        commands_layout = QVBoxLayout(commands_frame)
        
        # Title for commands section
        commands_title = QLabel("Voice Commands")
        commands_title.setObjectName("AppTitle")
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
            desc_label = QLabel(description)
            
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
        # Add "I'm done" button on the right
        self.done_button = QPushButton("I'm done")
        self.done_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: none;
                border-radius: 16px;
                background: #ea4335;
                color: white;
                font-size: 14px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI';
            }
            QPushButton:hover { background: #d93025; }
        """)
        self.done_button.clicked.connect(self._on_done_clicked)
        nav_layout.addWidget(self.done_button)
        layout.addWidget(nav_bar)
        
        # Create status bar with modern styling
        self.status_bar = QStatusBar()
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
        elif command in ["easy", "medium", "hard"]:
            # Set difficulty in the audio control widget
            self.audio_control.set_auto_mode_difficulty(command)
            self.status_bar.showMessage(f"Difficulty set to {command.capitalize()}", 2000)

    def update_status(self):
        """Update status bar with current playback information."""
        if self.audio_player.current_file:
            self.status_bar.showMessage(f"Playing: {os.path.basename(self.audio_player.current_file)}")
        else:
            self.status_bar.showMessage("Ready")

    def closeEvent(self, event):
        """Handle application close event."""
        self.logger.info("Closing application, stopping voice listener.")
        if hasattr(self.voice_controller, 'stop_listening'):
            self.voice_controller.stop_listening()
        event.accept()

    def _switch_view(self, index):
        """Switch between audio control and voice command views."""
        self.stacked_widget.setCurrentIndex(index)
        self.audio_button.setChecked(index == 0)
        self.voice_button.setChecked(index == 1)

    def _show_device_dialog(self):
        """Show dialog for selecting audio output device."""
        dialog = DeviceSelectionDialog(self)
        dialog.device_selected.connect(self._on_device_selected)
        dialog.exec_()

    def _on_device_selected(self, device_name, device_id):
        """Handle audio device selection."""
        self.audio_player.set_output_device(device_id)
        self.status_bar.showMessage(f"Audio device changed to: {device_name}", 2000)

    def _on_done_clicked(self):
        """Write session performance stats and close the app."""
        try:
            # Compute total length
            end_ms = QDateTime.currentMSecsSinceEpoch()
            total_seconds = max(0, (end_ms - self.session_start_ms) // 1000)
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            total_length_str = f"{minutes}:{seconds:02d}"

            # Total edges from UI label
            try:
                total_edges = int(self.audio_control.hooray_counter.text())
            except Exception:
                total_edges = 0

            # Final file name
            final_file_path = self.audio_player.get_current_file() if hasattr(self.audio_player, 'get_current_file') else None
            final_file = os.path.basename(final_file_path) if final_file_path else ""

            # CSV path (project root or src/data/logs if preferred)
            csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../PerformanceStats.CSV'))

            # Ensure header exists; append row
            file_exists = os.path.exists(csv_path)
            with open(csv_path, 'a', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Total length", "Total edges", "Final file"])
                writer.writerow([total_length_str, total_edges, final_file])
            self.logger.info(f"Session stats written to {csv_path}")
        except Exception as e:
            self.logger.error(f"Failed to write PerformanceStats: {e}")
        finally:
            # Close the application
            self.close() 