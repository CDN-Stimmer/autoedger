from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                 QLabel, QSlider, QFrame, QSpinBox, QComboBox)
from PySide6.QtCore import Qt, Slot, QTimer
from .volume_meter import VolumeMeter
import os
import logging
from PySide6.QtGui import QColor

class AudioControlWidget(QWidget):
    def __init__(self, audio_player, parent=None):
        super().__init__(parent)
        self.audio_player = audio_player
        self._slider_updating = False  # Flag to prevent feedback loops
        self.setObjectName("AudioControlWidget")
        self.logger = logging.getLogger(__name__)  # Initialize logger
        
        # Connect audio player signals
        self.logger.debug("Connecting audio player signals")
        self.audio_player.playback_started.connect(self._on_playback_started)
        self.audio_player.playback_stopped.connect(self._on_playback_stopped)
        self.audio_player.time_updated.connect(self._on_time_updated)
        self.audio_player.audio_data_ready.connect(self._on_audio_data)  # Connect to the same signal used by plotter
        self.logger.debug("Audio player signals connected")
        
        # Create main layout
        main_layout = QVBoxLayout(self)
        
        # Create frame
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel)
        frame_layout = QVBoxLayout(frame)
        
        # Create title
        title = QLabel("Audio Control")
        title.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(title)
        
        # Create playback controls
        controls_layout = QHBoxLayout()
        
        # Add favorites filter toggle
        self.favorites_button = QPushButton("Show Favorites")
        self.favorites_button.setCheckable(True)
        self.favorites_button.setStyleSheet("""
            QPushButton {
                padding: 5px;
                background-color: #f0f0f0;
            }
            QPushButton:checked {
                background-color: #FFD700;
            }
        """)
        controls_layout.addWidget(self.favorites_button)
        
        # Add file selection dropdown
        self.file_combo = QComboBox()
        self.file_combo.setMinimumWidth(200)  # Make it wide enough to show filenames
        controls_layout.addWidget(self.file_combo)
        
        # Add play selected button
        self.play_selected_button = QPushButton("Play Selected")
        self.play_selected_button.clicked.connect(self._on_play_selected)
        self.play_selected_button.setEnabled(False)  # Disabled until files are loaded
        controls_layout.addWidget(self.play_selected_button)
        
        self.play_button = QPushButton("Play Random")
        self.play_button.clicked.connect(self.audio_player.play_random_file)
        controls_layout.addWidget(self.play_button)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.audio_player.stop_playback)
        controls_layout.addWidget(self.stop_button)
        
        self.loop_button = QPushButton("Loop")
        self.loop_button.setCheckable(True)
        self.loop_button.clicked.connect(self.audio_player.toggle_loop)
        controls_layout.addWidget(self.loop_button)
        
        frame_layout.addLayout(controls_layout)

        # Create position slider
        position_layout = QHBoxLayout()
        position_label = QLabel("Position:")
        position_layout.addWidget(position_label)
        
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 1000)  # Use 1000 steps for smooth scrubbing
        self.position_slider.setValue(0)
        self.position_slider.sliderPressed.connect(self._on_position_slider_pressed)
        self.position_slider.sliderReleased.connect(self._on_position_slider_released)
        self.position_slider.valueChanged.connect(self._on_position_changed)
        position_layout.addWidget(self.position_slider)
        
        self.time_label = QLabel("0:00 / 0:00")
        position_layout.addWidget(self.time_label)
        
        frame_layout.addLayout(position_layout)
        
        # Create volume control with meters
        volume_container = QWidget()
        volume_layout = QVBoxLayout(volume_container)
        volume_layout.setContentsMargins(0, 0, 0, 0)
        
        # Volume slider layout
        slider_layout = QHBoxLayout()
        volume_label = QLabel("Max Volume:")
        slider_layout.addWidget(volume_label)
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        slider_layout.addWidget(self.volume_slider)
        
        self.volume_value = QLabel("100%")
        self.volume_value.setMinimumWidth(50)
        slider_layout.addWidget(self.volume_value)
        
        volume_layout.addLayout(slider_layout)
        
        # Volume meters layout
        meters_layout = QHBoxLayout()
        meters_layout.setSpacing(10)
        meters_layout.setContentsMargins(10, 0, 10, 0)  # Add some padding
        
        # Create volume meters
        self.logger.debug("Creating volume meters")
        self.left_meter = VolumeMeter("L")
        self.right_meter = VolumeMeter("R")
        
        # Create containers for meters to control their size
        left_container = QWidget()
        right_container = QWidget()
        
        # Set fixed dimensions for containers
        left_container.setFixedWidth(40)
        right_container.setFixedWidth(40)
        left_container.setFixedHeight(200)  # Increase height to accommodate label
        right_container.setFixedHeight(200)  # Increase height to accommodate label
        
        # Set background color for containers to make them visible
        left_container.setAutoFillBackground(True)
        right_container.setAutoFillBackground(True)
        palette = left_container.palette()
        palette.setColor(left_container.backgroundRole(), QColor(30, 30, 30))
        left_container.setPalette(palette)
        right_container.setPalette(palette)
        
        left_layout = QVBoxLayout(left_container)
        right_layout = QVBoxLayout(right_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        right_layout.setSpacing(0)
        
        left_layout.addWidget(self.left_meter)
        right_layout.addWidget(self.right_meter)
        
        meters_layout.addWidget(left_container)
        meters_layout.addWidget(right_container)
        meters_layout.addStretch()  # Add stretch to keep meters left-aligned
        
        volume_layout.addLayout(meters_layout)
        self.logger.debug("Volume meters added to layout")
        frame_layout.addWidget(volume_container)
        
        # Create yes command indicator
        self.yes_indicator = QLabel("Yes!")
        self.yes_indicator.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #4CAF50;
                padding: 5px;
                border: 2px solid #4CAF50;
                border-radius: 5px;
                background: #E8F5E9;
            }
        """)
        self.yes_indicator.setAlignment(Qt.AlignCenter)
        self.yes_indicator.hide()
        frame_layout.addWidget(self.yes_indicator)
        
        # Add timer for hiding yes indicator
        self.yes_timer = QTimer()
        self.yes_timer.setSingleShot(True)
        self.yes_timer.timeout.connect(lambda: self.yes_indicator.hide())
        
        # Add the frame to the main layout
        main_layout.addWidget(frame)
        
        # Connect to position changes from the player
        if hasattr(self.audio_player, 'player'):
            self.audio_player.player.positionChanged.connect(self._on_player_position_changed)
            self.audio_player.player.durationChanged.connect(self._on_duration_changed)

    def _format_time(self, ms):
        """Format milliseconds as MM:SS"""
        total_seconds = int(ms / 1000)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}"

    def _on_position_slider_pressed(self):
        """Handle slider press - prepare for scrubbing"""
        self._slider_updating = True

    def _on_position_slider_released(self):
        """Handle slider release - perform the seek"""
        if hasattr(self.audio_player, 'player'):
            position = self.position_slider.value()
            # Convert from slider range (0-1000) to actual duration
            actual_position = int((position / 1000.0) * self.audio_player.player.duration())
            self.audio_player.player.setPosition(actual_position)
        self._slider_updating = False

    def _on_position_changed(self, value):
        """Handle position slider value change"""
        if self._slider_updating and hasattr(self.audio_player, 'player'):
            # Update time label while scrubbing
            duration = self.audio_player.player.duration()
            current = int((value / 1000.0) * duration)
            self.time_label.setText(f"{self._format_time(current)} / {self._format_time(duration)}")

    def _on_player_position_changed(self, position):
        """Handle position updates from the player"""
        if not self._slider_updating and hasattr(self.audio_player, 'player'):
            duration = self.audio_player.player.duration()
            if duration > 0:
                # Convert actual position to slider range (0-1000)
                slider_pos = int((position / duration) * 1000)
                self.position_slider.setValue(slider_pos)
                self.time_label.setText(f"{self._format_time(position)} / {self._format_time(duration)}")

    def _on_duration_changed(self, duration):
        """Handle duration changes from the player"""
        if duration > 0:
            self.time_label.setText(f"0:00 / {self._format_time(duration)}")

    def _on_volume_changed(self, value):
        """Handle volume slider change."""
        self.volume_value.setText(f"{value}%")
        # Volume setting is now handled by main window
        
    def _on_playback_started(self, filename):
        """Handle playback started."""
        pass
        
    def _on_playback_stopped(self):
        """Handle playback stopped."""
        pass
        
    def _on_time_updated(self, time_remaining):
        """Handle time update."""
        pass
        
    def _on_play_selected(self):
        """Handle play selected button click."""
        current_file = self.file_combo.currentText()
        if current_file:
            for file_path in self.audio_player.file_list:
                if os.path.basename(file_path) == current_file:
                    self.audio_player.play_file(file_path)
                    break 
        
    def _update_file_list(self):
        """Update the file combo box with current files."""
        if not hasattr(self.audio_player, 'file_list'):
            return
            
        current_text = self.file_combo.currentText()
        self.file_combo.clear()
        
        for file_path in self.audio_player.file_list:
            self.file_combo.addItem(os.path.basename(file_path))
                
        # Try to restore the previous selection
        index = self.file_combo.findText(current_text)
        if index >= 0:
            self.file_combo.setCurrentIndex(index)
            
        self.play_selected_button.setEnabled(self.file_combo.count() > 0)
        
    def _on_audio_data(self, amplitude, frequency):
        """Handle incoming audio data and update volume meters."""
        # Scale amplitude to make the meters more responsive
        scaled_amplitude = min(1.0, amplitude * 2.5)  # Multiply by 2.5 to make it more sensitive
        self.logger.debug(f"Received audio data - raw amplitude: {amplitude:.3f}, scaled: {scaled_amplitude:.3f}")
        
        # Update both meters with the same value since we're using mono audio
        self.left_meter.set_level(scaled_amplitude)
        self.right_meter.set_level(scaled_amplitude)

    def show_yes_triggered(self):
        """Show the yes indicator for 2 seconds."""
        self.yes_indicator.show()
        self.yes_timer.start(2000)  # Hide after 2 seconds
        