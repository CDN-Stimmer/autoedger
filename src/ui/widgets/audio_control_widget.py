from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                 QLabel, QSlider, QFrame, QSpinBox, QComboBox, QGroupBox)
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
        self.logger = logging.getLogger(__name__)  # Initialize logger
        
        # Initialize variables
        self.dragging_position = False
        self.hold_drop_percent = 20  # Default hold drop percentage
        
        # Connect audio player signals
        self.logger.debug("Connecting audio player signals")
        self.audio_player.playback_started.connect(self._on_playback_started)
        self.audio_player.playback_stopped.connect(self._on_playback_stopped)
        self.audio_player.time_updated.connect(self._on_time_updated)
        self.audio_player.audio_data_ready.connect(self._on_audio_data)
        self.audio_player.volume_changed.connect(self._on_volume_update)
        self.audio_player.favorites_changed.connect(self._update_file_list)
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
        
        # Create current file display
        self.current_file_label = QLabel("No file playing")
        self.current_file_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #2196F3;
                padding: 5px;
                background: #E3F2FD;
                border-radius: 3px;
            }
        """)
        self.current_file_label.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(self.current_file_label)
        
        # Create hooray counter
        counter_layout = QHBoxLayout()
        counter_label = QLabel("Hooray Count:")
        counter_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.hooray_counter = QLabel("0")
        self.hooray_counter.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #4CAF50;
                padding: 10px;
                background: #E8F5E9;
                border: 2px solid #4CAF50;
                border-radius: 5px;
                min-width: 50px;
            }
        """)
        self.hooray_counter.setAlignment(Qt.AlignCenter)
        counter_layout.addWidget(counter_label)
        counter_layout.addWidget(self.hooray_counter)
        counter_layout.addStretch()
        frame_layout.addLayout(counter_layout)
        
        # Create playback controls
        controls_layout = QHBoxLayout()
        
        # Add favorites button
        self.favorite_button = QPushButton("♡")  # Empty heart
        self.favorite_button.setCheckable(True)
        self.favorite_button.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                padding: 5px;
                min-width: 40px;
                background-color: #f0f0f0;
            }
            QPushButton:checked {
                color: #FF4081;
                background-color: #FFE0E9;
            }
        """)
        self.favorite_button.clicked.connect(self._on_favorite_clicked)
        controls_layout.addWidget(self.favorite_button)
        
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
        self.favorites_button.clicked.connect(self._update_file_list)
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
        
        # Add play next button
        self.play_next_button = QPushButton("Play Next")
        self.play_next_button.clicked.connect(self._on_play_next)
        controls_layout.addWidget(self.play_next_button)
        
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
        
        # Create control settings group
        settings_group = QGroupBox("Control Settings")
        settings_layout = QVBoxLayout()
        
        # Hold Drop control
        hold_layout = QHBoxLayout()
        hold_label = QLabel("Hold Drop:")
        self.hold_drop_slider = QSlider(Qt.Horizontal)
        self.hold_drop_slider.setRange(0, 100)
        self.hold_drop_slider.setValue(20)
        self.hold_drop_value = QLabel("20%")
        hold_layout.addWidget(hold_label)
        hold_layout.addWidget(self.hold_drop_slider)
        hold_layout.addWidget(self.hold_drop_value)
        settings_layout.addLayout(hold_layout)
        
        # Wait Time control
        wait_layout = QHBoxLayout()
        wait_label = QLabel("Wait Time:")
        self.wait_time_slider = QSlider(Qt.Horizontal)
        self.wait_time_slider.setRange(1, 30)
        self.wait_time_slider.setValue(5)
        self.wait_time_value = QLabel("5s")
        wait_layout.addWidget(wait_label)
        wait_layout.addWidget(self.wait_time_slider)
        wait_layout.addWidget(self.wait_time_value)
        settings_layout.addLayout(wait_layout)
        
        settings_group.setLayout(settings_layout)
        frame_layout.addWidget(settings_group)
        
        # Create action buttons
        action_layout = QHBoxLayout()
        
        # Hooray button
        self.hooray_button = QPushButton("HOORAY!")
        self.hooray_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 18px;
                font-weight: bold;
                padding: 15px;
                border-radius: 5px;
            }
            QPushButton:pressed {
                background-color: #45a049;
            }
        """)
        self.hooray_button.clicked.connect(self._on_hooray)
        action_layout.addWidget(self.hooray_button)
        
        # Hold button
        self.hold_button = QPushButton("HOLD")
        self.hold_button.setStyleSheet("""
            QPushButton {
                background-color: #FFD700;
                font-size: 18px;
                font-weight: bold;
                padding: 15px;
                border-radius: 5px;
            }
            QPushButton:pressed {
                background-color: #FFC700;
            }
        """)
        self.hold_button.clicked.connect(self._on_hold)
        action_layout.addWidget(self.hold_button)
        
        frame_layout.addLayout(action_layout)
        
        # Create mode controls
        mode_layout = QVBoxLayout()
        mode_label = QLabel("Difficulty Mode:")
        mode_layout.addWidget(mode_label)
        
        button_layout = QHBoxLayout()
        self.easy_button = QPushButton("Easy")
        self.medium_button = QPushButton("Medium")
        self.hard_button = QPushButton("Hard")
        
        for btn in [self.easy_button, self.medium_button, self.hard_button]:
            btn.setCheckable(True)
            button_layout.addWidget(btn)
            
        self.medium_button.setChecked(True)
        
        # Connect mode buttons to handlers
        self.easy_button.clicked.connect(self._on_easy_mode)
        self.medium_button.clicked.connect(self._on_medium_mode)
        self.hard_button.clicked.connect(self._on_hard_mode)
        
        mode_layout.addLayout(button_layout)
        frame_layout.addLayout(mode_layout)
        
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
        
        # Set fixed dimensions for containers (swapped for horizontal orientation)
        left_container.setFixedWidth(200)  # Increased width for horizontal meter
        right_container.setFixedWidth(200)  # Increased width for horizontal meter
        left_container.setFixedHeight(40)   # Reduced height for horizontal meter
        right_container.setFixedHeight(40)  # Reduced height for horizontal meter
        
        # Set background color for containers to make them visible
        left_container.setAutoFillBackground(True)
        right_container.setAutoFillBackground(True)
        palette = left_container.palette()
        palette.setColor(left_container.backgroundRole(), QColor(30, 30, 30))
        left_container.setPalette(palette)
        right_container.setPalette(palette)
        
        left_layout = QHBoxLayout(left_container)   # Changed to horizontal layout
        right_layout = QHBoxLayout(right_container) # Changed to horizontal layout
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

        # Connect signals
        self.hold_drop_slider.valueChanged.connect(self._on_hold_drop_changed)
        self.wait_time_slider.valueChanged.connect(self._on_wait_time_changed)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)

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
        """Handle volume slider change initiated by user."""
        if not self._slider_updating:  # Only update if not already being updated
            self.volume_value.setText(f"{value}%")
            self.audio_player.set_volume(value / 100.0)

    def _on_playback_started(self):
        """Handle playback started."""
        # Get current file from audio player
        current_file = self.audio_player.get_current_file()
        if current_file:
            filename = os.path.basename(current_file)
        else:
            filename = "Unknown"
            
        # Update favorite button state
        is_favorite = self.audio_player.is_favorite(current_file) if current_file else False
        self.favorite_button.setChecked(is_favorite)
        self.favorite_button.setText("♥" if is_favorite else "♡")
        
        # Update current file display
        self.current_file_label.setText(filename)
        
    def _on_playback_stopped(self):
        """Handle playback stopped."""
        self.current_file_label.setText("No file playing")
        
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
        
        # Get all filenames and filter based on favorites if needed
        filenames = []
        for file_path in self.audio_player.file_list:
            filename = os.path.basename(file_path)
            if not self.favorites_button.isChecked() or self.audio_player.is_favorite(filename):
                filenames.append(filename)
        
        # Sort filenames alphabetically
        filenames.sort()
        
        # Add sorted files to combo box
        for filename in filenames:
            self.file_combo.addItem(filename)
                
        # Try to restore the previous selection
        index = self.file_combo.findText(current_text)
        if index >= 0:
            self.file_combo.setCurrentIndex(index)
            
        self.play_selected_button.setEnabled(self.file_combo.count() > 0)
        
    def _on_audio_data(self, audio_data):
        """Handle incoming audio data and update volume meters."""
        if not audio_data:
            return
            
        # Calculate average amplitude from the audio data
        amplitude = sum(audio_data) / len(audio_data)
        
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
        
    def _on_hold_drop_changed(self, value):
        """Handle hold drop slider change."""
        self.hold_drop_value.setText(f"{value}%")
        self.hold_drop_percent = value
        self.logger.debug(f"Hold drop set to {value}%")
        
    def _on_wait_time_changed(self, value):
        """Handle wait time slider change."""
        self.wait_time_value.setText(f"{value}s")
        self.audio_player.set_wait_time(value)
        
    def _on_hooray(self):
        """Handle hooray button click."""
        # Increment hooray counter
        current_count = int(self.hooray_counter.text())
        self.hooray_counter.setText(str(current_count + 1))
        self.audio_player.start_hooray_cycle(self.wait_time_slider.value())
        
    def _on_hold(self):
        """Handle hold button click."""
        # Get current volume
        current_volume = self.audio_player.get_volume()
        
        # Calculate reduced volume based on hold drop percentage
        hold_drop_factor = self.hold_drop_percent / 100.0
        reduced_volume = current_volume * (1.0 - hold_drop_factor)
        
        # Set the reduced volume
        self.audio_player.set_volume(reduced_volume)
        self.logger.info(f"Hold activated: Volume reduced by {self.hold_drop_percent}% (from {current_volume:.2f} to {reduced_volume:.2f})")
        
        # Update the volume slider to reflect the new volume
        new_volume_percent = int(reduced_volume * 100)
        self.volume_slider.setValue(new_volume_percent)
        
    def _on_easy_mode(self):
        """Handle easy mode button click."""
        if self.easy_button.isChecked():
            self.logger.info("Switching to Easy mode")
            # Ensure other buttons are unchecked
            self.medium_button.setChecked(False)
            self.hard_button.setChecked(False)
            
            # Set wait time to longer value for easier gameplay
            self.wait_time_slider.setValue(10)
            # Manually trigger the wait time changed handler
            self._on_wait_time_changed(10)
            
            # Set hold drop to lower value for easier gameplay
            self.hold_drop_slider.setValue(10)
            # Manually trigger the hold drop changed handler
            self._on_hold_drop_changed(10)
            
            self.logger.debug("Easy mode activated: Wait time=10s, Hold drop=10%")
        else:
            # If unchecked, default to medium
            self.medium_button.setChecked(True)
            self._on_medium_mode()
    
    def _on_medium_mode(self):
        """Handle medium mode button click."""
        if self.medium_button.isChecked():
            self.logger.info("Switching to Medium mode")
            # Ensure other buttons are unchecked
            self.easy_button.setChecked(False)
            self.hard_button.setChecked(False)
            
            # Set wait time to default value
            self.wait_time_slider.setValue(5)
            # Manually trigger the wait time changed handler
            self._on_wait_time_changed(5)
            
            # Set hold drop to default value
            self.hold_drop_slider.setValue(20)
            # Manually trigger the hold drop changed handler
            self._on_hold_drop_changed(20)
            
            self.logger.debug("Medium mode activated: Wait time=5s, Hold drop=20%")
        else:
            # If unchecked, default to medium
            self.medium_button.setChecked(True)
    
    def _on_hard_mode(self):
        """Handle hard mode button click."""
        if self.hard_button.isChecked():
            self.logger.info("Switching to Hard mode")
            # Ensure other buttons are unchecked
            self.easy_button.setChecked(False)
            self.medium_button.setChecked(False)
            
            # Set wait time to shorter value for harder gameplay
            self.wait_time_slider.setValue(2)
            # Manually trigger the wait time changed handler
            self._on_wait_time_changed(2)
            
            # Set hold drop to higher value for harder gameplay
            self.hold_drop_slider.setValue(40)
            # Manually trigger the hold drop changed handler
            self._on_hold_drop_changed(40)
            
            self.logger.debug("Hard mode activated: Wait time=2s, Hold drop=40%")
        else:
            # If unchecked, default to medium
            self.medium_button.setChecked(True)
            self._on_medium_mode()
        
    def _on_volume_update(self, volume):
        """Handle volume updates from the audio player."""
        self._slider_updating = True  # Prevent feedback loop
        value = int(volume * 100)
        self.volume_slider.setValue(value)
        self.volume_value.setText(f"{value}%")
        self._slider_updating = False
        
    def _on_favorite_clicked(self):
        """Handle favorite button click."""
        if self.favorite_button.isChecked():
            if self.audio_player.add_to_favorites():
                self.favorite_button.setText("♥")  # Filled heart
        else:
            if self.audio_player.remove_from_favorites():
                self.favorite_button.setText("♡")  # Empty heart
        
    def _on_play_next(self):
        """Handle play next button click."""
        if not self.audio_player.file_list:
            return
            
        current_file = self.audio_player.current_file
        if not current_file:
            # If no file is playing, play the first file
            self._play_file_at_index(0)
            return
            
        # Find the current file in the list
        current_files = [f for f in self.audio_player.file_list 
                        if not self.favorites_button.isChecked() or 
                        self.audio_player.is_favorite(os.path.basename(f))]
        try:
            current_index = current_files.index(current_file)
            # Play next file (wrap around to beginning if at end)
            next_index = (current_index + 1) % len(current_files)
            self.audio_player.play_file(current_files[next_index])
        except ValueError:
            # If current file not found in list, play first file
            if current_files:
                self.audio_player.play_file(current_files[0])
                
    def _play_file_at_index(self, index):
        """Play file at specified index in the filtered list."""
        current_files = [f for f in self.audio_player.file_list 
                        if not self.favorites_button.isChecked() or 
                        self.audio_player.is_favorite(os.path.basename(f))]
        if current_files and 0 <= index < len(current_files):
            self.audio_player.play_file(current_files[index])
        