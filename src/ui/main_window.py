from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                                 QHBoxLayout, QPushButton, QLabel, QFrame, QSpacerItem, QSizePolicy, QSlider, QSpinBox, QStatusBar,
                                 QScrollArea, QGridLayout)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from ui.widgets.audio_control_widget import AudioControlWidget
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
        self.setMinimumSize(800, 600)  # Increased size to accommodate command list
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)  # Changed to horizontal layout
        
        # Create left panel for audio controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Create audio control widget
        self.audio_control = AudioControlWidget(audio_player)
        left_layout.addWidget(self.audio_control)
        
        # Add left panel to main layout
        layout.addWidget(left_panel, stretch=2)
        
        # Create right panel for voice commands reference
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Create voice commands reference
        commands_frame = QFrame()
        commands_frame.setFrameStyle(QFrame.StyledPanel)
        commands_layout = QVBoxLayout(commands_frame)
        
        # Add title
        title = QLabel("Voice Commands Reference")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #2196F3; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignCenter)
        commands_layout.addWidget(title)
        
        # Create scrollable area for commands
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        grid_layout = QGridLayout(scroll_content)
        
        # Define command categories and their commands
        commands = {
            "Playback Controls": {
                "hooray/edge/now": "Trigger hooray action",
                "hold": "Trigger hold action",
                "skip": "Play random file",
                "pause": "Pause playback",
                "playback": "Resume playback",
                "stop": "Stop playback"
            },
            "Volume Controls": {
                "up/more": "Increase volume by 10%",
                "down/less": "Decrease volume by 10%",
                "max": "Set volume to 100%",
                "half": "Set volume to 50%"
            },
            "Mode Controls": {
                "easy": "Switch to easy mode",
                "medium": "Switch to medium mode",
                "hard": "Switch to hard mode"
            },
            "Other Commands": {
                "yes": "Trigger yes indicator",
                "favorite": "Add current track to favorites"
            }
        }
        
        row = 0
        for category, category_commands in commands.items():
            # Add category header
            category_label = QLabel(category)
            category_label.setStyleSheet("font-weight: bold; color: #4CAF50; padding-top: 10px;")
            grid_layout.addWidget(category_label, row, 0, 1, 2)
            row += 1
            
            # Add commands in this category
            for command, description in category_commands.items():
                cmd_label = QLabel(f"{command}")
                cmd_label.setStyleSheet("color: #FF5722; font-family: monospace;")
                desc_label = QLabel(description)
                grid_layout.addWidget(cmd_label, row, 0)
                grid_layout.addWidget(desc_label, row, 1)
                row += 1
        
        scroll.setWidget(scroll_content)
        commands_layout.addWidget(scroll)
        right_layout.addWidget(commands_frame)
        
        # Add right panel to main layout
        layout.addWidget(right_panel, stretch=1)
        
        # Connect volume control
        self.audio_control.volume_slider.valueChanged.connect(self._on_volume_changed)
        
        # Load audio files
        self._load_audio_files()
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Set up update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(1000)  # Update every second
        
        # Start voice control
        self.voice_controller.start_listening()

    def _load_audio_files(self):
        """Load audio files from the audio directory."""
        try:
            # Use relative path for audio directory
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            audio_dir = os.path.join(script_dir, "data", "audio")
            self.logger.info(f"Loading audio files from: {audio_dir}")
            
            # Create directory if it doesn't exist
            os.makedirs(audio_dir, exist_ok=True)
            
            # Load the files
            if self.audio_player.load_files(audio_dir):
                self.logger.info("Audio files loaded successfully")
                # Update the file list in the audio control widget
                self.audio_control._update_file_list()
            else:
                self.logger.warning(f"No audio files found in audio directory: {audio_dir}")
                
        except Exception as e:
            self.logger.error(f"Error loading audio files: {e}")
        
    def _on_volume_changed(self, value):
        """Handle volume slider changes."""
        self.audio_player.set_volume(value / 100.0)
        self.status_bar.showMessage(f"Volume set to {value}%")

    def update_status(self):
        """Update status bar with current state."""
        volume = int(self.audio_player.get_volume() * 100)
        self.status_bar.showMessage(f"Volume: {volume}%")

    def _handle_voice_command(self, command):
        """Handle voice commands."""
        self.logger.debug(f"Received voice command: {command}")
        
        if command in ["hooray", "edge", "now"]:
            self.audio_control._on_hooray()
        elif command == "hold":
            self.audio_control._on_hold()
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
            if hasattr(self.audio_player, 'player'):
                self.audio_player.player.pause()
        elif command == "playback":
            if hasattr(self.audio_player, 'player'):
                self.audio_player.player.play()
        elif command == "stop":
            self.audio_player.stop_playback()
        elif command in ["easy", "easy_mode"]:
            self.logger.info("Voice command: Switching to Easy mode")
            self.audio_control._on_easy_mode()
            self.status_bar.showMessage("Voice command: Switched to Easy mode")
        elif command in ["medium", "medium_mode"]:
            self.logger.info("Voice command: Switching to Medium mode")
            self.audio_control._on_medium_mode()
            self.status_bar.showMessage("Voice command: Switched to Medium mode")
        elif command in ["hard", "hard_mode"]:
            self.logger.info("Voice command: Switching to Hard mode")
            self.audio_control._on_hard_mode()
            self.status_bar.showMessage("Voice command: Switched to Hard mode")
        elif command == "yes":
            self.audio_control.show_yes_triggered()
        elif command == "favorite":
            current_file = self.audio_control.file_combo.currentText()
            if current_file:
                self.audio_control.favorites_button.setChecked(True)
                self.status_bar.showMessage(f"Added {current_file} to favorites")
            
        # Update status bar to show the recognized command
        self.status_bar.showMessage(f"Voice command: {command}")

    def closeEvent(self, event):
        """Handle window close event."""
        # Stop voice control when window is closed
        self.voice_controller.stop_listening()
        super().closeEvent(event)