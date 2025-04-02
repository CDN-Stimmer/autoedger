from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                 QLabel, QSlider, QFrame, QSpinBox, QComboBox, QGroupBox)
from PySide6.QtCore import Qt, Slot, QTimer, QSize
from .volume_meter import VolumeMeter
import os
import logging
from PySide6.QtGui import QColor, QIcon, QFont
from PySide6.QtMultimedia import QMediaPlayer

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
        self.audio_player.playback_paused.connect(self._on_playback_paused)
        self.audio_player.playback_stopped.connect(self._on_playback_stopped)
        self.audio_player.time_updated.connect(self._on_time_updated)
        self.audio_player.audio_data_ready.connect(self._on_audio_data)
        self.audio_player.volume_changed.connect(self._on_volume_update)
        self.audio_player.favorites_changed.connect(self._update_file_list)
        self.audio_player.playback_duration_changed.connect(self._on_duration_changed)
        self.logger.debug("Audio player signals connected")
        
        # Create main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create playback info section with reduced height
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-radius: 8px;
                padding: 2px 6px;
                max-height: 40px;
            }
        """)
        info_layout = QHBoxLayout(info_frame)
        info_layout.setSpacing(6)
        info_layout.setContentsMargins(6, 2, 6, 2)  # Minimal padding
        
        # View switching buttons
        self.voice_view_button = QPushButton("🎙️") # Microphone symbol
        # self.voice_view_button.setIcon(QIcon("src/ui/icons/mic.png"))
        # self.voice_view_button.setIconSize(QSize(16, 16))
        self.voice_view_button.setFixedSize(28, 28)
        self.voice_view_button.setCheckable(True)
        self.voice_view_button.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border-radius: 14px;
                border: none;
                padding: 4px;
                color: #5f6368; /* Ensure symbol is visible */
                font-size: 14px; /* Adjust font size for symbol */
            }
            QPushButton:hover {
                background-color: #e8f0fe;
            }
            QPushButton:pressed {
                background-color: #e1e8ed;
            }
            QPushButton:checked {
                background-color: #1a73e8;
                color: white;
            }
        """)
        self.voice_view_button.clicked.connect(self._switch_to_voice_view)
        info_layout.addWidget(self.voice_view_button)
        
        # Status section (left side)
        status_layout = QVBoxLayout()
        status_layout.setSpacing(0)  # Minimal spacing between labels
        
        # Now Playing label with smaller font
        self.playing_label = QLabel("No file playing")
        self.playing_label.setStyleSheet("""
            QLabel {
                color: #1a73e8;
                font-size: 11px;
                font-weight: 500;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI';
            }
        """)
        status_layout.addWidget(self.playing_label)
        
        # Voice Status with smaller font
        self.voice_status = QLabel("Listening...")
        self.voice_status.setStyleSheet("""
            QLabel {
                color: #34a853;
                font-size: 9px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI';
            }
        """)
        status_layout.addWidget(self.voice_status)
        
        info_layout.addLayout(status_layout)
        
        # Counter (right side)
        counter_container = QHBoxLayout()
        counter_container.setContentsMargins(0, 0, 0, 0)
        counter_container.setAlignment(Qt.AlignCenter)
        self.hooray_counter = QLabel("0")
        self.hooray_counter.setStyleSheet("""
            QLabel {
                color: #34a853;
                font-size: 14px;
                font-weight: 500;
                padding: 2px 6px;
                background: #f1f8f1;
                border-radius: 4px;
                min-width: 20px;
                text-align: center;
            }
        """)
        self.hooray_counter.setAlignment(Qt.AlignCenter)
        counter_container.addWidget(self.hooray_counter)
        info_layout.addLayout(counter_container)
        
        layout.addWidget(info_frame)
        
        # File selection and controls
        controls_frame = QFrame()
        controls_frame.setStyleSheet("""
            QFrame {
                background-color: #e8f0fe;
                border-radius: 12px;
                padding: 12px;
            }
        """)
        controls_frame_layout = QVBoxLayout(controls_frame)
        controls_frame_layout.setSpacing(12)
        
        # File selection row
        file_row = QHBoxLayout()
        self.favorites_button = QPushButton("♥")  # Heart symbol for favorites
        self.favorites_button.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                padding: 6px;
                border: none;
                border-radius: 8px;
                background: #f8f9fa;
                color: #5f6368;
                min-width: 32px;
            }
            QPushButton:checked {
                background: #fce8e6;
                color: #ea4335;
            }
        """)
        self.favorites_button.setCheckable(True)
        self.favorites_button.clicked.connect(self._update_file_list)
        
        self.file_combo = QComboBox()
        self.file_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                border: 1px solid #dadce0;
                border-radius: 8px;
                background: white;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI';
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: url(resources/down-arrow.png);
            }
        """)
        
        file_row.addWidget(self.favorites_button)
        file_row.addWidget(self.file_combo)
        controls_frame_layout.addLayout(file_row)
        
        # Playback controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)
        
        # Play button
        self.play_button = QPushButton("▶")  # Play symbol
        self.play_button.setFixedSize(40, 40)
        self.play_button.setStyleSheet("""
            QPushButton {
                background-color: #1a73e8;
                border-radius: 20px;
                border: none;
                color: white; /* Ensure symbol is visible */
                font-size: 18px; /* Adjust font size for symbol */
            }
            QPushButton:hover {
                background-color: #1557b0;
            }
            QPushButton:pressed {
                background-color: #174ea6;
            }
            QPushButton:checked {
                background-color: #1557b0;
            }
        """)
        controls_layout.addWidget(self.play_button)
        
        # Next button
        self.next_button = QPushButton("⏭")  # Next symbol
        self.next_button.setFixedSize(40, 40)
        self.next_button.setStyleSheet(self.play_button.styleSheet().replace("#1a73e8", "#f8f9fa").replace("white", "#5f6368").replace("#1557b0", "#e8f0fe").replace("#174ea6", "#e1e8ed")) # Base style on play, but use secondary colors
        controls_layout.addWidget(self.next_button)
        
        # Random button
        self.random_button = QPushButton("🔀") # Shuffle symbol
        self.random_button.setFixedSize(40, 40)
        self.random_button.setStyleSheet(self.next_button.styleSheet()) # Reuse style from Next
        controls_layout.addWidget(self.random_button)
        
        # Stop button
        self.stop_button = QPushButton("⏹") # Stop symbol
        self.stop_button.setFixedSize(40, 40)
        self.stop_button.setStyleSheet(self.next_button.styleSheet()) # Reuse style from Next
        controls_layout.addWidget(self.stop_button)
        
        # Loop button
        self.loop_button = QPushButton("🔁") # Repeat symbol
        self.loop_button.setFixedSize(40, 40)
        self.loop_button.setStyleSheet(self.next_button.styleSheet()) # Reuse style from Next
        self.loop_button.setCheckable(True)
        controls_layout.addWidget(self.loop_button)
        
        # Add playback controls to layout
        controls_layout.addStretch()
        controls_layout.addWidget(self.play_button)
        controls_layout.addWidget(self.next_button)
        controls_layout.addWidget(self.random_button)
        controls_layout.addWidget(self.stop_button)
        controls_layout.addWidget(self.loop_button)
        controls_layout.addStretch()
        
        # Add controls layout to main controls layout
        controls_frame_layout.addLayout(controls_layout)
        
        # Progress bar and time labels
        progress_container = QFrame()
        progress_container.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        progress_layout = QVBoxLayout(progress_container)
        progress_layout.setSpacing(4)
        
        # Time labels
        time_labels = QHBoxLayout()
        self.current_time = QLabel("0:00")
        self.current_time.setStyleSheet("""
            QLabel {
                color: #5f6368;
                font-size: 12px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI';
            }
        """)
        self.total_time = QLabel("0:00")
        self.total_time.setStyleSheet(self.current_time.styleSheet())
        time_labels.addWidget(self.current_time)
        time_labels.addStretch()
        time_labels.addWidget(self.total_time)
        progress_layout.addLayout(time_labels)
        
        # Position slider
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #dadce0;
                height: 4px;
                background: #e8f0fe;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #1a73e8;
                border: none;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #1a73e8;
                border-radius: 2px;
            }
        """)
        self.position_slider.setRange(0, 0)  # Initialize with zero range
        self.position_slider.sliderPressed.connect(self._on_position_slider_pressed)
        self.position_slider.sliderReleased.connect(self._on_position_slider_released)
        self.position_slider.valueChanged.connect(self._on_position_changed)
        progress_layout.addWidget(self.position_slider)
        
        controls_frame_layout.addWidget(progress_container)
        
        # Volume control
        volume_container = QFrame()
        volume_container.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        volume_layout = QHBoxLayout(volume_container)
        volume_layout.setSpacing(8)
        
        # Volume label
        volume_label = QLabel("Volume:")
        volume_label.setStyleSheet("""
            QLabel {
                color: #5f6368;
                font-size: 12px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI';
            }
        """)
        volume_layout.addWidget(volume_label)
        
        # Volume slider
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setStyleSheet(self.position_slider.styleSheet())
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)  # Default volume 50%
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        volume_layout.addWidget(self.volume_slider)
        
        # Volume percentage
        self.volume_value = QLabel("50%")
        self.volume_value.setStyleSheet(volume_label.styleSheet())
        volume_layout.addWidget(self.volume_value)
        
        controls_frame_layout.addWidget(volume_container)
        
        # Wait time controls
        wait_container = QFrame()
        wait_container.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        wait_layout = QVBoxLayout(wait_container)  # Changed to vertical layout
        wait_layout.setSpacing(8)
        
        # Wait time slider row
        wait_slider_row = QHBoxLayout()
        wait_slider_row.setSpacing(8)
        
        # Wait time label
        wait_label = QLabel("Wait Time:")
        wait_label.setStyleSheet("""
            QLabel {
                color: #5f6368;
                font-size: 12px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI';
            }
        """)
        wait_slider_row.addWidget(wait_label)
        
        # Wait time slider
        self.wait_slider = QSlider(Qt.Horizontal)
        self.wait_slider.setStyleSheet(self.position_slider.styleSheet())
        self.wait_slider.setMinimumWidth(250)  # Set minimum width
        self.wait_slider.setRange(1, 60)
        self.wait_slider.setValue(5)
        self.wait_slider.valueChanged.connect(self._on_wait_time_changed)
        wait_slider_row.addWidget(self.wait_slider)
        
        # Wait time value label
        self.wait_time_value = QLabel("5s")
        self.wait_time_value.setStyleSheet(wait_label.styleSheet())
        wait_slider_row.addWidget(self.wait_time_value)
        
        wait_layout.addLayout(wait_slider_row)
        
        # NOW button
        self.now_button = QPushButton("NOW")
        self.now_button.setStyleSheet("""
            QPushButton {
                background-color: #34a853;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px;
                font-size: 12px;
                font-weight: 500;
                margin-top: 4px;
            }
            QPushButton:hover {
                background-color: #2d8e47;
            }
            QPushButton:pressed {
                background-color: #2a8443;
            }
        """)
        self.now_button.clicked.connect(self._on_hooray)
        wait_layout.addWidget(self.now_button)
        
        controls_frame_layout.addWidget(wait_container)
        layout.addWidget(controls_frame)
        
        # Connect button signals
        self.play_button.clicked.connect(self._on_play_pause_toggle)
        self.next_button.clicked.connect(self._on_play_next)
        self.random_button.clicked.connect(self._on_play_random_file)
        self.stop_button.clicked.connect(self._on_stop)
        self.loop_button.clicked.connect(self._on_loop_toggled)
        
        # Initialize UI
        self._update_file_list()
        self._update_ui()

    def _format_time(self, seconds):
        """Format time in MM:SS format."""
        # Ensure input is a number, default to 0 if not
        if not isinstance(seconds, (int, float)):
            seconds = 0
        # Prevent negative times
        seconds = max(0, seconds)
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes}:{seconds:02d}"

    def _on_position_slider_pressed(self):
        """Handle position slider pressed."""
        self.dragging_position = True
        self.logger.debug("Position slider pressed")

    def _on_position_slider_released(self):
        """Handle position slider released."""
        slider_value_ms = self.position_slider.value()
        self.logger.debug(f"Position slider released at value: {slider_value_ms} ms")
        self.dragging_position = False
        # Allow seeking even when paused
        if self.audio_player.is_playing() or self.audio_player.is_paused(): 
            self.logger.debug(f"Setting player position to: {slider_value_ms} ms")
            try:
                # Pass milliseconds directly to the player's set_position
                self.audio_player.set_position(slider_value_ms)
            except OverflowError:
                 # QMediaPlayer might have limits, log the error
                 self.logger.error(f"OverflowError: Cannot set position to {slider_value_ms} ms. Value likely exceeds QMediaPlayer limits.")
            except Exception as e:
                self.logger.error(f"Error setting position to {slider_value_ms} ms: {e}")
            
            # Update time label immediately after seeking
            position_seconds = slider_value_ms / 1000.0
            formatted_time = self._format_time(position_seconds)
            self.logger.debug(f"Updating current time label (on release) to: {formatted_time}")
            self.current_time.setText(formatted_time)

    def _on_position_changed(self, value):
        """Handle position slider value changed (only while dragging)."""
        if not self._slider_updating and self.dragging_position:
            current_time_seconds = value / 1000.0  # Slider value is milliseconds
            formatted_time = self._format_time(current_time_seconds)
            self.logger.debug(f"Slider dragged to value: {value} ms, updating label to: {formatted_time}")
            self.current_time.setText(formatted_time)

    def _on_playback_started(self):
        """Handle playback started."""
        self.logger.info("Playback started event received")
        self.play_button.setChecked(True)
        self._update_ui()
        
        # Update position slider range with actual duration
        file_path = self.audio_player.get_current_file()
        if file_path:
            self.logger.debug(f"Getting duration for file: {file_path}")
            duration_sec = self.audio_player.get_file_duration(file_path)
            duration_ms = int(duration_sec * 1000)
            self.logger.debug(f"Received duration: {duration_sec:.2f} sec ({duration_ms} ms)")
            if duration_ms > 0:
                self.position_slider.setRange(0, duration_ms) # Range in milliseconds
                formatted_total_time = self._format_time(duration_sec)
                self.logger.debug(f"Setting slider range 0-{duration_ms}, total time label: {formatted_total_time}")
                self.total_time.setText(formatted_total_time)
                self.current_time.setText("0:00")
                self.position_slider.setValue(0) # Reset slider position
            else:
                self.logger.warning(f"Invalid duration ({duration_sec}) received for {file_path}. Resetting slider.")
                 # Reset if duration is invalid
                self.position_slider.setRange(0, 0)
                self.total_time.setText("0:00")
                self.current_time.setText("0:00")
        else:
            self.logger.warning("Playback started but no current file reported by player. Resetting slider.")
            # Reset if no file is loaded
            self.position_slider.setRange(0, 0)
            self.total_time.setText("0:00")
            self.current_time.setText("0:00")

    def _on_time_updated(self, current_position_ms):
        """Handle time update from player (position in ms)."""
        # Use current_position_ms directly from the player signal
        if not self.dragging_position:
            current_time_seconds = current_position_ms / 1000.0
            formatted_time = self._format_time(current_time_seconds)
            # Limit frequent logging
            # self.logger.debug(f"Time updated: {current_position_ms} ms, label: {formatted_time}") 
            self.current_time.setText(formatted_time)
            self._slider_updating = True
            self.position_slider.setValue(current_position_ms) # Update slider in milliseconds
            self._slider_updating = False
        # else: # Optional: log that update is skipped due to dragging
            # self.logger.debug(f"Skipping time update ({current_position_ms} ms) due to dragging.")

    def _on_playback_stopped(self):
        """Handle playback stopped."""
        self.logger.info("Playback stopped event received")
        self.play_button.setChecked(False)
        self._update_ui() # Update button states
        # Optionally reset slider and times? Depends on desired behavior after stop.
        # self.current_time.setText("0:00")
        # self.position_slider.setValue(0)
        # Keep total time as is
        self.playing_label.setText("Playback Stopped")
        
    def _on_audio_data(self, audio_data):
        """Handle incoming audio data."""
        if not audio_data:
            return
            
        # Calculate RMS (Root Mean Square) amplitude from the audio data
        # This gives us a more accurate representation of the audio level
        squared_sum = sum(sample * sample for sample in audio_data)
        rms = (squared_sum / len(audio_data)) ** 0.5
        
        # Scale the RMS value to a reasonable range (0-1)
        # Using a smaller scaling factor to prevent maxing out
        scaled_level = min(1.0, rms * 1.5)  # Reduced from 2.5 to 1.5
        
        self.logger.debug(f"Audio level - RMS: {rms:.3f}, scaled: {scaled_level:.3f}")

    def _on_wait_time_changed(self, value):
        """Handle wait time slider change."""
        self.wait_time_value.setText(f"{value}s")
        self.audio_player.set_wait_time(value)
        
    def _on_hooray(self):
        """Handle hooray button click."""
        # Increment hooray counter
        current_count = int(self.hooray_counter.text())
        self.hooray_counter.setText(str(current_count + 1))
        self.audio_player.start_hooray_cycle(self.wait_slider.value())
        
    def _on_loop_toggled(self):
        """Handle loop button click."""
        self.audio_player.toggle_loop()
        
    def _on_stop(self):
        """Handle stop button click."""
        self.audio_player.stop_playback()
        
    def _on_play_pause_toggle(self):
        """Toggle play/pause for the currently loaded file."""
        if self.audio_player.is_playing():
            self.audio_player.pause()
            self.logger.debug("Audio paused via button")
        else:
            # If no file is technically "loaded" but one is selected, load and play it.
            # Otherwise, resume/play the currently loaded one.
            current_player_file = self.audio_player.get_current_file()
            selected_combo_text = self.file_combo.currentText()
            
            # Extract filename from the combo box text (remove duration part)
            selected_filename = self.file_combo.currentData()
            
            target_file_to_play = None
            if current_player_file:
                 # If player has a file loaded (even if stopped), use that one
                 target_file_to_play = current_player_file
            elif selected_filename:
                 # If player has no file, but one is selected in combo, find its full path
                 for file_path in self.audio_player.file_list:
                     if os.path.basename(file_path) == selected_filename:
                         target_file_to_play = file_path
                         break # Found the file path

            if target_file_to_play:
                # Ensure the target file is loaded before playing
                if self.audio_player.get_current_file() != target_file_to_play:
                     if not self.audio_player.load_file(target_file_to_play):
                          self.logger.error(f"Failed to load file for play: {target_file_to_play}")
                          return # Don't proceed if load failed
                
                self.audio_player.play()
                self.logger.debug(f"Audio played/resumed via button: {target_file_to_play}")
            else:
                self.logger.warning("Play button clicked, but no file loaded or selected.")
                # Optionally provide user feedback, e.g., status bar message

    def _on_play_next(self):
        """Handle play next button click."""
        self.audio_player.play_next()

    def _on_play_random_file(self):
        """Handle play random button click by calling the correct player method."""
        self.logger.debug("Random button clicked, calling play_random_file")
        self.audio_player.play_random_file() # Correct method call

    def _update_file_list(self):
        """Update the file combo box with current files and their durations."""
        if not hasattr(self.audio_player, 'file_list'):
            return
            
        current_text = self.file_combo.currentText()
        self.file_combo.clear()
        
        # Get all filenames and filter based on favorites if needed
        file_info = []  # List to store tuples of (filename, display_text)
        seen_filenames = set()  # Track unique filenames
        
        for file_path in self.audio_player.file_list:
            if not self.favorites_button.isChecked() or self.audio_player.is_favorite(file_path):
                filename = os.path.basename(file_path)
                
                # Skip if we've already seen this filename
                if filename in seen_filenames:
                    self.logger.warning(f"Skipping duplicate filename: {filename}")
                    continue
                    
                seen_filenames.add(filename)
                
                # Get duration and format it
                duration_sec = self.audio_player.get_file_duration(file_path)
                
                # Only show duration if it's valid (greater than 0)
                if duration_sec and duration_sec > 0:
                    duration_text = self._format_time(duration_sec)
                    display_text = f"{filename} ({duration_text})"
                else:
                    # If duration retrieval failed, just show the filename
                    display_text = filename
                    self.logger.warning(f"Could not get duration for {filename}")
                
                file_info.append((filename, display_text))
        
        # Add files to combo box with durations (sorted by filename)
        for filename, display_text in sorted(file_info, key=lambda x: x[0].lower()):
            self.file_combo.addItem(display_text, filename)  # Store original filename as item data
                
        # Try to restore the previous selection
        if current_text:
            # Extract just the filename part for matching
            current_filename = current_text.split(" (")[0] if " (" in current_text else current_text
            # Find the index where the filename matches
            for i in range(self.file_combo.count()):
                if self.file_combo.itemData(i) == current_filename:
                    self.file_combo.setCurrentIndex(i)
                    break

    def _on_volume_update(self, volume):
        """Handle volume updates from the audio player."""
        if not self._slider_updating:  # Prevent feedback loop
            self._slider_updating = True
            self.volume_slider.setValue(int(volume * 100))
            self._slider_updating = False
        
    def resizeEvent(self, event):
        """Handle widget resize events."""
        super().resizeEvent(event)
        # Update NOW button width to maintain 80% of container width
        if hasattr(self, 'now_button'):
            self.now_button.setFixedWidth(int(self.width() * 0.8))
        
    def _on_volume_changed(self, value):
        """Handle volume slider change."""
        if not self._slider_updating:  # Prevent feedback loop
            volume = value / 100.0  # Convert percentage to float
            self.audio_player.set_volume(volume)
            self.volume_value.setText(f"{value}%")
        
    def _switch_to_voice_view(self):
        """Switch to voice commands view."""
        self.parent().switch_to_voice_view()  # Assuming the parent widget has this method
        
    def switch_back_from_voice(self):
        """Called when switching back from voice view."""
        self.voice_view_button.setChecked(False)
        
    def _update_ui(self):
        """Update UI elements based on playback state."""
        is_playing = self.audio_player.is_playing()
        self.play_button.setChecked(is_playing)
        self.play_button.setText("⏸" if is_playing else "▶")
        
        is_looping = self.audio_player.is_looping()
        self.loop_button.setChecked(is_looping)
        
        # Update playing label
        current_file = self.audio_player.get_current_file()
        if is_playing:
            filename = os.path.basename(current_file) if current_file else "Unknown File"
            self.playing_label.setText(f"Playing: {filename}")
        elif self.audio_player.is_paused() and current_file:
            filename = os.path.basename(current_file)
            self.playing_label.setText(f"Paused: {filename}")
        else:
            self.playing_label.setText("No file playing")
        
    def _on_duration_changed(self, duration_ms):
        """Handle duration update from player (in milliseconds)."""
        if duration_ms > 0:
            duration_sec = duration_ms / 1000.0
            formatted_total_time = self._format_time(duration_sec)
            self.logger.debug(f"Duration updated: {duration_sec:.2f} sec, label: {formatted_total_time}")
            self.total_time.setText(formatted_total_time)
            self.position_slider.setRange(0, duration_ms)
        
    def _on_playback_paused(self):
        """Handle playback paused event."""
        self.logger.info("Playback paused event received")
        self.play_button.setChecked(False)
        self._update_ui()
        # Keep the current position and duration, just update the UI state
        