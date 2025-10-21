from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                 QLabel, QSlider, QFrame, QSpinBox, QComboBox, QGroupBox, QDialog, QCheckBox)
from PySide6.QtCore import Qt, Slot, QTimer, QSize
from .volume_meter import VolumeMeter
import os
import logging
from PySide6.QtGui import QColor, QIcon, QFont
from PySide6.QtMultimedia import QMediaPlayer
from ..device_dialog import DeviceSelectionDialog
from PySide6.QtWidgets import QRadioButton, QButtonGroup, QStyle

class AudioControlWidget(QWidget):
    def __init__(self, audio_player, parent=None):
        super().__init__(parent)
        self.audio_player = audio_player
        self.audio_player.audio_control_widget = self  # Pass widget reference to player
        self._slider_updating = False  # Flag to prevent feedback loops
        self._suppress_playback = False  # Flag to suppress playback on combo update
        self.logger = logging.getLogger(__name__)  # Initialize logger
        
        # Initialize variables
        self.dragging_position = False
        self.hold_drop_percent = 20  # Default hold drop percentage
        
        # Connect audio player signals
        self.audio_player.playback_started.connect(self._on_playback_started)
        self.audio_player.playback_paused.connect(self._on_playback_paused)
        self.audio_player.playback_stopped.connect(self._on_playback_stopped)
        self.audio_player.time_updated.connect(self._on_time_updated)
        self.audio_player.audio_data_ready.connect(self._on_audio_data)
        self.audio_player.volume_changed.connect(self._on_volume_update)
        self.audio_player.favorites_changed.connect(self._update_file_list)
        self.audio_player.playback_duration_changed.connect(self._on_duration_changed)
        if hasattr(self.audio_player, 'ramp_active_changed'):
            self.audio_player.ramp_active_changed.connect(self._on_ramp_active_changed)
        if hasattr(self.audio_player, 'playlists_changed'):
            self.audio_player.playlists_changed.connect(self._update_playlist_combo)
        
        # Create main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Add device selection button
        # Removed device selection button
        
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
        
        # Add voice commands button
        self.voice_commands_button = QPushButton("📋")  # Clipboard symbol
        self.voice_commands_button.setFixedSize(28, 28)
        self.voice_commands_button.setToolTip("Show Voice Commands")
        self.voice_commands_button.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border-radius: 14px;
                border: none;
                padding: 4px;
                color: #5f6368;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #e8f0fe;
            }
            QPushButton:pressed {
                background-color: #e1e8ed;
            }
        """)
        self.voice_commands_button.clicked.connect(self._show_voice_commands)
        info_layout.addWidget(self.voice_commands_button)
        
        # Status section (left side)
        status_layout = QVBoxLayout()
        status_layout.setSpacing(0)  # Minimal spacing between labels
        
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
                font-size: 20px;
                font-weight: 700;
                padding: 4px 10px;
                background: #f1f8f1;
                border-radius: 6px;
                min-width: 32px;
                text-align: center;
            }
        """)
        self.hooray_counter.setAlignment(Qt.AlignCenter)
        counter_container.addWidget(QLabel("Edges"))
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
        file_row.addWidget(self.favorites_button)
        
        # Playlist selection combo
        self.playlist_combo = QComboBox()
        self.playlist_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                border: 1px solid #dadce0;
                border-radius: 8px;
                background: white;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI';
                font-size: 13px;
                color: #202124;
                min-width: 120px;
            }
        """)
        self.playlist_combo.addItem("All Files")
        self.playlist_combo.currentTextChanged.connect(self._on_playlist_changed)
        file_row.addWidget(self.playlist_combo)
        
        # Duration filter combo box
        self.duration_filter_combo = QComboBox()
        self.duration_filter_combo.addItems([
            "All", "< 1 min", "1–3 min", "3–10 min", "> 10 min"
        ])
        self.duration_filter_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                border: 1px solid #dadce0;
                border-radius: 8px;
                background: white;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI';
                font-size: 13px;
                color: #202124;
                min-width: 100px;
            }
        """)
        self.duration_filter_combo.currentIndexChanged.connect(self._update_file_list)
        file_row.addWidget(self.duration_filter_combo)
        
        self.file_combo = QComboBox()
        self.file_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                border: 1px solid #dadce0;
                border-radius: 8px;
                background: white;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI';
                font-size: 13px;
                color: #202124;
                min-width: 200px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: url(resources/down-arrow.png);
                width: 12px;
                height: 12px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #dadce0;
                border-radius: 8px;
                background: white;
                selection-background-color: #e8f0fe;
                selection-color: #1a73e8;
                padding: 4px;
            }
            QComboBox QAbstractItemView::item {
                padding: 6px;
                min-height: 24px;
                border-radius: 4px;
            }
            QComboBox QAbstractItemView::item:hover {
                background: #f8f9fa;
            }
        """)
        file_row.addWidget(self.file_combo)
        controls_frame_layout.addLayout(file_row)
        
        # File name display
        file_name_row = QHBoxLayout()
        file_name_row.setSpacing(8)
        
        # File name label with larger font and centered text
        self.file_name_label = QLabel("No file playing")
        self.file_name_label.setStyleSheet("""
            QLabel {
                color: #1a73e8;
                font-size: 16px;
                font-weight: 500;
                padding: 4px 0;
            }
        """)
        self.file_name_label.setAlignment(Qt.AlignCenter)
        file_name_row.addWidget(self.file_name_label)
        
        # Add favorite button next to file name
        self.quick_favorite_button = QPushButton("⭐")
        self.quick_favorite_button.setFixedSize(28, 28)
        self.quick_favorite_button.setToolTip("Add to Favorites")
        self.quick_favorite_button.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border-radius: 14px;
                border: none;
                padding: 4px;
                color: #5f6368;
                font-size: 14px;
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
        self.quick_favorite_button.setCheckable(True)
        self.quick_favorite_button.clicked.connect(self._on_quick_favorite_clicked)
        file_name_row.addWidget(self.quick_favorite_button)
        
        # Add to playlist button
        self.add_to_playlist_button = QPushButton("📁")
        self.add_to_playlist_button.setFixedSize(28, 28)
        self.add_to_playlist_button.setToolTip("Add to Playlist")
        self.add_to_playlist_button.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border-radius: 14px;
                border: none;
                padding: 4px;
                color: #5f6368;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #e8f0fe;
            }
            QPushButton:pressed {
                background-color: #e1e8ed;
            }
        """)
        self.add_to_playlist_button.clicked.connect(self._on_add_to_playlist_clicked)
        file_name_row.addWidget(self.add_to_playlist_button)
        
        controls_frame_layout.addLayout(file_name_row)
        
        # Create playback controls section
        controls_group = QGroupBox("Playback Controls")
        controls_layout = QVBoxLayout(controls_group)
        controls_layout.setSpacing(8)
        controls_layout.setContentsMargins(12, 12, 12, 12)
        
        # Create playback buttons row
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)
        
        # Previous file button
        self.prev_button = QPushButton("⏮")
        self.prev_button.setToolTip("Previous File")
        self.prev_button.setFixedSize(40, 40)
        self.prev_button.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #dadce0;
                border-radius: 20px;
                color: #202124;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #f1f3f4;
                border-color: #d2e3fc;
            }
            QPushButton:pressed {
                background-color: #e8f0fe;
                border-color: #1a73e8;
            }
        """)
        self.prev_button.clicked.connect(self._on_play_previous)
        self.prev_button.setText("")
        self.prev_button.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipBackward))
        self.prev_button.setIconSize(QSize(20, 20))
        buttons_row.addWidget(self.prev_button)
        
        # Play/Pause button
        self.play_button = QPushButton("▶")
        self.play_button.setCheckable(True)
        self.play_button.setToolTip("Play/Pause")
        self.play_button.setFixedSize(40, 40)
        self.play_button.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #dadce0;
                border-radius: 20px;
                color: #202124;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #f1f3f4;
                border-color: #d2e3fc;
            }
            QPushButton:checked {
                background-color: #e8f0fe;
                border-color: #1a73e8;
            }
        """)
        self.play_button.clicked.connect(self._on_play_pause_toggle)
        self.play_button.setText("")
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.setIconSize(QSize(20, 20))
        buttons_row.addWidget(self.play_button)
        
        # Next file button
        self.next_button = QPushButton("⏭")
        self.next_button.setToolTip("Next File")
        self.next_button.setFixedSize(40, 40)
        self.next_button.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #dadce0;
                border-radius: 20px;
                color: #202124;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #f1f3f4;
                border-color: #d2e3fc;
            }
            QPushButton:pressed {
                background-color: #e8f0fe;
                border-color: #1a73e8;
            }
        """)
        self.next_button.clicked.connect(self._on_play_next)
        self.next_button.setText("")
        self.next_button.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self.next_button.setIconSize(QSize(20, 20))
        buttons_row.addWidget(self.next_button)
        
        # Random button
        self.random_button = QPushButton("🔀") # Shuffle symbol
        self.random_button.setFixedSize(40, 40)
        self.random_button.setStyleSheet(self.next_button.styleSheet()) # Reuse style from Next
        buttons_row.addWidget(self.random_button)
        
        # Stop button
        self.stop_button = QPushButton("⏹") # Stop symbol
        self.stop_button.setFixedSize(40, 40)
        self.stop_button.setStyleSheet(self.next_button.styleSheet()) # Reuse style from Next
        self.stop_button.setText("")
        self.stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_button.setIconSize(QSize(20, 20))
        buttons_row.addWidget(self.stop_button)
        
        # Loop button
        self.loop_button = QPushButton("🔁") # Repeat symbol
        self.loop_button.setFixedSize(40, 40)
        self.loop_button.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border-radius: 20px;
                border: none;
                color: #5f6368;
                font-size: 18px;
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
                border: 2px solid #1557b0;
            }
        """)
        self.loop_button.setCheckable(True)
        buttons_row.addWidget(self.loop_button)
        
        # Add playback buttons to layout
        controls_layout.addLayout(buttons_row)
        
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
        
        # Position slider container
        position_container = QFrame()
        position_container.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        position_layout = QVBoxLayout(position_container)
        position_layout.setSpacing(8)
        
        # Position slider row
        position_slider_row = QHBoxLayout()
        position_slider_row.setSpacing(8)
        
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
        position_slider_row.addWidget(self.position_slider)
        
        position_layout.addLayout(position_slider_row)
        
        # Time labels row
        time_labels_row = QHBoxLayout()
        time_labels_row.setSpacing(4)  # Reduced spacing for tighter time display
        
        # Current time label
        self.current_time = QLabel("0:00")
        self.current_time.setStyleSheet("""
            QLabel {
                color: #5f6368;
                font-size: 12px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI';
                padding: 0;
            }
        """)
        time_labels_row.addWidget(self.current_time)
        
        # Add a separator
        separator = QLabel("/")
        separator.setStyleSheet("""
            QLabel {
                color: #5f6368;
                font-size: 12px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI';
                padding: 0 2px;
            }
        """)
        time_labels_row.addWidget(separator)
        
        # Total time label
        self.total_time = QLabel("0:00")
        self.total_time.setStyleSheet(self.current_time.styleSheet())
        time_labels_row.addWidget(self.total_time)
        
        # Add stretch at the end to keep time labels left-aligned
        time_labels_row.addStretch()
        
        position_layout.addLayout(time_labels_row)
        
        position_container.setLayout(position_layout)
        controls_frame_layout.addWidget(position_container)
        
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
        self.wait_container = wait_container  # For color feedback
        wait_container.setStyleSheet("""
            QFrame {
                background-color: #fffbe6;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        wait_layout = QVBoxLayout(wait_container)  # Changed to vertical layout
        wait_layout.setSpacing(8)

        # Ramp-up controls
        ramp_container = QFrame()
        ramp_container.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        ramp_layout = QHBoxLayout(ramp_container)
        ramp_layout.setSpacing(8)
        ramp_start_label = QLabel("Ramp start %:")
        ramp_start_label.setStyleSheet(volume_label.styleSheet())
        self.ramp_start_spin = QSpinBox()
        self.ramp_start_spin.setRange(0, 100)
        self.ramp_start_spin.setValue(10)
        ramp_duration_label = QLabel("Duration (s):")
        ramp_duration_label.setStyleSheet(volume_label.styleSheet())
        self.ramp_duration_spin = QSpinBox()
        self.ramp_duration_spin.setRange(1, 180)
        self.ramp_duration_spin.setValue(10)
        ramp_duration_label.setText("Duration (min):")
        self.ramp_button = QPushButton("Start Ramp")
        self.ramp_button.clicked.connect(self._on_start_ramp)
        ramp_layout.addWidget(ramp_start_label)
        ramp_layout.addWidget(self.ramp_start_spin)
        ramp_layout.addWidget(ramp_duration_label)
        ramp_layout.addWidget(self.ramp_duration_spin)
        ramp_layout.addWidget(self.ramp_button)
        controls_frame_layout.addWidget(ramp_container)
        
        # Wait time label (define early for style reuse)
        wait_label = QLabel("Wait Time:")
        wait_label.setStyleSheet("""
            QLabel {
                color: #5f6368;
                font-size: 12px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI';
            }
        """)
        
        # Difficulty selector row
        difficulty_row = QHBoxLayout()
        difficulty_row.setSpacing(8)
        difficulty_label = QLabel("Difficulty:")
        difficulty_label.setStyleSheet(wait_label.styleSheet())
        difficulty_row.addWidget(difficulty_label)
        self.difficulty_group = QButtonGroup(self)
        self.easy_radio = QRadioButton("Easy")
        self.medium_radio = QRadioButton("Medium")
        self.hard_radio = QRadioButton("Hard")
        self.difficulty_group.addButton(self.easy_radio, 0)
        self.difficulty_group.addButton(self.medium_radio, 1)
        self.difficulty_group.addButton(self.hard_radio, 2)
        self.medium_radio.setChecked(True)
        difficulty_row.addWidget(self.easy_radio)
        difficulty_row.addWidget(self.medium_radio)
        difficulty_row.addWidget(self.hard_radio)
        wait_layout.addLayout(difficulty_row)
        self.auto_mode_difficulty = 'medium'  # Default
        self.difficulty_group.buttonClicked.connect(self._on_difficulty_changed)
        
        # Wait time slider row
        wait_slider_row = QHBoxLayout()
        wait_slider_row.setSpacing(8)
        wait_slider_row.addWidget(wait_label)
        # Wait time slider
        self.wait_slider = QSlider(Qt.Horizontal)
        self.wait_slider.setStyleSheet("""
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
            QSlider:disabled {
                background: #f1f3f4;
                color: #b0b0b0;
            }
            QSlider::handle:horizontal:disabled {
                background: #b0b0b0;
                border: none;
            }
        """)
        self.wait_slider.setMinimumWidth(250)  # Set minimum width
        self.wait_slider.setRange(1, 60)
        self.wait_slider.setValue(8)  # Default value of 8 seconds
        self.wait_slider.valueChanged.connect(self._on_wait_time_changed)
        wait_slider_row.addWidget(self.wait_slider)
        # Wait time value label
        self.wait_time_value = QLabel("8s")
        self.wait_time_value.setStyleSheet(wait_label.styleSheet())
        wait_slider_row.addWidget(self.wait_time_value)
        # Auto mode checkbox
        self.auto_wait_checkbox = QCheckBox("Auto")
        self.auto_wait_checkbox.setStyleSheet("""
            QCheckBox {
                color: #5f6368;
                font-size: 12px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI';
            }
        """)
        self.auto_wait_checkbox.stateChanged.connect(self._on_auto_wait_toggled)
        wait_slider_row.addWidget(self.auto_wait_checkbox)
        wait_layout.addLayout(wait_slider_row)
        # Only enable when auto mode is checked (now that auto_wait_checkbox exists)
        self._set_difficulty_enabled(self.auto_wait_checkbox.isChecked())
        
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
        layout.addWidget(controls_group)
        layout.addWidget(controls_frame)
        
        # Connect button signals
        self.play_button.clicked.connect(self._on_play_pause_toggle)
        self.next_button.clicked.connect(self._on_play_next)
        self.random_button.clicked.connect(self._on_play_random_file)
        self.stop_button.clicked.connect(self._on_stop)
        self.loop_button.clicked.connect(self._on_loop_toggled)
        
        # Initialize UI
        self._update_file_list()
        self._update_playlist_combo()
        self._update_ui()
        # Set startup volume to 100% and reflect in UI
        try:
            self.audio_player.set_volume(1.0)
        except Exception:
            pass
        self.volume_slider.setValue(100)
        self.volume_value.setText("100%")
        # Default wait mode to Auto and Easy
        self.auto_wait_checkbox.setChecked(True)
        self.easy_radio.setChecked(True)
        self._on_auto_wait_toggled(True)
        self._on_difficulty_changed()
        
        # Connect file combo box signal
        self.file_combo.currentIndexChanged.connect(self._on_file_selected)

    def _on_start_ramp(self):
        # Toggle behavior: start or stop ramp
        if hasattr(self.audio_player, '_ramp_active') and self.audio_player._ramp_active:
            if hasattr(self.audio_player, 'stop_volume_ramp'):
                self.audio_player.stop_volume_ramp()
            return
        start_percent = self.ramp_start_spin.value()
        duration_minutes = self.ramp_duration_spin.value()
        duration_seconds = duration_minutes * 60
        self.audio_player.start_volume_ramp(start_percent / 100.0, duration_seconds)

    def _on_ramp_active_changed(self, active: bool):
        self.ramp_button.setText("Stop Ramp" if active else "Start Ramp")
        self.ramp_button.setProperty("primary", active)
        self.ramp_button.style().unpolish(self.ramp_button)
        self.ramp_button.style().polish(self.ramp_button)

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

    def _on_position_slider_released(self):
        """Handle position slider released."""
        slider_value_ms = self.position_slider.value()
        self.dragging_position = False
        # Allow seeking even when paused
        if self.audio_player.is_playing() or self.audio_player.is_paused(): 
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
            self.current_time.setText(formatted_time)

    def _on_position_changed(self, value):
        """Handle position slider value changed (only while dragging)."""
        if not self._slider_updating and self.dragging_position:
            current_time_seconds = value / 1000.0  # Slider value is milliseconds
            formatted_time = self._format_time(current_time_seconds)
            self.current_time.setText(formatted_time)

    def _on_playback_started(self):
        """Handle playback started."""
        self.logger.info("Playback started event received")
        self.play_button.setChecked(True)
        self._update_ui()
        
        # Update the file name display
        self._update_file_name_display()
        
        # Update position slider range with actual duration
        file_path = self.audio_player.get_current_file()
        if file_path:
            duration_sec = self.audio_player.get_file_duration(file_path)
            duration_ms = int(duration_sec * 1000)
            if duration_ms > 0:
                self.position_slider.setRange(0, duration_ms) # Range in milliseconds
                formatted_total_time = self._format_time(duration_sec)
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

    def _update_file_name_display(self):
        """Update the file name display and favorite button state."""
        current_file = self.audio_player.get_current_file()
        if current_file:
            filename = os.path.basename(current_file)
            self.file_name_label.setText(filename)
            
            # Update quick favorite button state
            is_favorite = current_file in self.audio_player.favorites
            self.quick_favorite_button.setChecked(is_favorite)
            self.quick_favorite_button.setStyleSheet("""
                QPushButton {
                    background-color: %s;
                    border-radius: 14px;
                    border: none;
                    padding: 4px;
                    color: %s;
                    font-size: 14px;
                }
            """ % ("#1a73e8" if is_favorite else "#f8f9fa", 
                   "white" if is_favorite else "#5f6368"))
            
            # Update combo box selection
            for i in range(self.file_combo.count()):
                if self.file_combo.itemData(i) == current_file:
                    self.file_combo.setCurrentIndex(i)
                    break
        else:
            self.file_name_label.setText("No file playing")
            self.quick_favorite_button.setChecked(False)
            self.quick_favorite_button.setStyleSheet("""
                QPushButton {
                    background-color: #f8f9fa;
                    border-radius: 14px;
                    border: none;
                    padding: 4px;
                    color: #5f6368;
                    font-size: 14px;
                }
            """)

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
        self._update_ui()
        self._update_file_name_display()  # Update file name display
        
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

    def _on_wait_time_changed(self, value):
        """Handle wait time slider change."""
        self.wait_time_value.setText(f"{value}s")
        self.audio_player.set_wait_time(value)
        
    def _on_hooray(self):
        """Handle hooray button click."""
        import random
        # Increment hooray counter
        current_count = int(self.hooray_counter.text())
        self.hooray_counter.setText(str(current_count + 1))
        if self.auto_wait_checkbox.isChecked():
            if self.auto_mode_difficulty == 'easy':
                wait_time = random.randint(12, 25)
            elif self.auto_mode_difficulty == 'medium':
                wait_time = random.randint(8, 15)
            elif self.auto_mode_difficulty == 'hard':
                wait_time = random.randint(4, 8)
            else:
                wait_time = random.randint(8, 15)  # fallback
        else:
            wait_time = self.wait_slider.value()
        self.audio_player.start_hooray_cycle(wait_time)
        
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
            else:
                self.logger.warning("Play button clicked, but no file loaded or selected.")
                # Optionally provide user feedback, e.g., status bar message

    def _on_play_next(self):
        """Handle play next button click."""
        count = self.file_combo.count()
        if count == 0:
            return
        current_index = self.file_combo.currentIndex()
        next_index = (current_index + 1) % count
        self.file_combo.setCurrentIndex(next_index)
        # This will trigger _on_file_selected and start playback

    def _on_play_random_file(self):
        """Handle play random button click by calling the correct player method."""
        self.audio_player.play_random_file() # Correct method call
        
    def _update_file_list(self):
        """Update the file combo box with current files and their durations."""
        if not hasattr(self.audio_player, 'file_list'):
            return
        
        current_text = self.file_combo.currentText()
        self._suppress_playback = True
        self.file_combo.clear()
        
        # Get files to display (playlist or all files)
        files_to_show = []
        if hasattr(self.audio_player, 'get_current_playlist_files'):
            playlist_files = self.audio_player.get_current_playlist_files()
            if playlist_files:
                files_to_show = playlist_files
            else:
                files_to_show = self.audio_player.file_list
        else:
            files_to_show = self.audio_player.file_list
        
        # Get all filenames and filter based on favorites and duration if needed
        file_info = []  # List to store tuples of (file_path, display_text)
        seen_filenames = set()  # Track unique filenames
        show_favorites_only = self.favorites_button.isChecked()
        duration_filter = self.duration_filter_combo.currentText() if hasattr(self, 'duration_filter_combo') else "All"
        for file_path in files_to_show:
            is_fav = self.audio_player.is_favorite(file_path)
            if not show_favorites_only or is_fav:
                # Show relative path from audio root
                audio_root = os.path.dirname(os.path.abspath(self.audio_player.file_list[0])) if self.audio_player.file_list else ''
                rel_path = os.path.relpath(file_path, audio_root) if audio_root else os.path.basename(file_path)
                if rel_path in seen_filenames:
                    self.logger.warning(f"Skipping duplicate filename: {rel_path}")
                    continue
                seen_filenames.add(rel_path)
                duration_sec = self.audio_player.get_file_duration(file_path)
                # Duration filter logic
                if duration_filter == "< 1 min" and (not duration_sec or duration_sec >= 60):
                    continue
                elif duration_filter == "1–3 min" and (not duration_sec or not (60 <= duration_sec < 180)):
                    continue
                elif duration_filter == "3–10 min" and (not duration_sec or not (180 <= duration_sec < 600)):
                    continue
                elif duration_filter == "> 10 min" and (not duration_sec or duration_sec < 600):
                    continue
                if duration_sec and duration_sec > 0:
                    duration_text = self._format_time(duration_sec)
                    display_text = f"{rel_path} ({duration_text})"
                else:
                    display_text = rel_path
                    self.logger.warning(f"Could not get duration for {rel_path}")
                file_info.append((file_path, display_text))
        for file_path, display_text in sorted(file_info, key=lambda x: os.path.basename(x[0]).lower()):
            self.file_combo.addItem(display_text, file_path)
        # Try to restore the previous selection
        if current_text:
            current_filename = current_text.split(" (")[0] if " (" in current_text else current_text
            for i in range(self.file_combo.count()):
                if os.path.basename(self.file_combo.itemData(i)) == current_filename:
                    self.file_combo.setCurrentIndex(i)
                    break
        self._suppress_playback = False

    def _on_volume_update(self, volume):
        """Handle volume updates from the audio player."""
        if not self._slider_updating:  # Prevent feedback loop
            self._slider_updating = True
            self.volume_slider.setValue(int(volume * 100))
            self._slider_updating = False
        # Always reflect label to the latest value
        self.volume_value.setText(f"{int(round(volume * 100))}%")
        
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
        
    def _show_device_dialog(self):
        """Show the device selection dialog."""
        pass
        
    def _on_device_selected(self, device_name, device_id):
        """Handle device selection."""
        self.audio_player.set_output_device(device_id)
        self.logger.info(f"Selected audio device: {device_name} (ID: {device_id})")
        
    def _on_file_selected(self, index):
        """Handle file selection from combo box."""
        if index >= 0 and index < self.file_combo.count():
            file_path = self.file_combo.currentData()
            if file_path:
                self.file_name_label.setText(f"Playing: {os.path.basename(file_path)}")
                self._update_favorite_button()
                if not self._suppress_playback:
                    self.audio_player.play_file(file_path)
                
    def _update_favorite_button(self):
        """Update the favorite button state based on current file."""
        current_file = self.file_combo.currentData()
        if current_file:
            is_favorite = current_file in self.audio_player.favorites
            self.favorites_button.setChecked(is_favorite)
            
    def _on_quick_favorite_clicked(self):
        """Handle quick favorite button click (toggle)."""
        current_file = self.file_combo.currentData()
        if current_file:
            if self.quick_favorite_button.isChecked():
                if self.audio_player.add_to_favorites():
                    self.quick_favorite_button.setStyleSheet("""
                        QPushButton {
                            background-color: #1a73e8;
                            border-radius: 14px;
                            border: none;
                            padding: 4px;
                            color: white;
                            font-size: 14px;
                        }
                    """)
            else:
                if self.audio_player.remove_from_favorites():
                    self.quick_favorite_button.setStyleSheet("""
                        QPushButton {
                            background-color: #f8f9fa;
                            border-radius: 14px;
                            border: none;
                            padding: 4px;
                            color: #5f6368;
                            font-size: 14px;
                        }
                    """)
        
    def _on_play_previous(self):
        """Handle play previous button click."""
        self.audio_player.play_previous()
        
    def _show_voice_commands(self):
        """Show the voice commands dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Voice Commands")
        dialog.setMinimumWidth(400)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QLabel {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI';
            }
        """)
        
        layout = QVBoxLayout(dialog)
        
        # Title
        title = QLabel("Available Voice Commands")
        title.setStyleSheet("""
            QLabel {
                color: #1a73e8;
                font-size: 18px;
                font-weight: bold;
                padding: 10px 0;
            }
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Commands list
        commands_frame = QFrame()
        commands_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        commands_layout = QVBoxLayout(commands_frame)
        
        commands = [
            ("🎯 Hooray/Edge/Now", "Trigger hooray action"),
            ("⏸ Hold", "Trigger hold action"),
            ("⏭ Skip", "Play random file"),
            ("🔊 Up/More", "Increase volume by 10%"),
            ("🔉 Down/Less", "Decrease volume by 10%"),
            ("🔈 Max", "Set volume to 100%"),
            ("🔉 Half", "Set volume to 50%"),
            ("⏸ Pause", "Pause playback"),
            ("▶ Playback", "Resume playback"),
            ("⏹ Stop", "Stop playback"),
            ("⭐ Favorite", "Add current track to favorites")
        ]
        
        for command, description in commands:
            command_layout = QHBoxLayout()
            
            cmd_label = QLabel(command)
            cmd_label.setStyleSheet("""
                QLabel {
                    color: #1a73e8;
                    font-weight: 500;
                    font-size: 14px;
                }
            """)
            desc_label = QLabel(description)
            desc_label.setStyleSheet("""
                QLabel {
                    color: #5f6368;
                    font-size: 14px;
                }
            """)
            
            command_layout.addWidget(cmd_label)
            command_layout.addWidget(desc_label)
            command_layout.addStretch()
            
            commands_layout.addLayout(command_layout)
        
        layout.addWidget(commands_frame)
        
        # Close button
        close_button = QPushButton("Close")
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #1a73e8;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #1557b0;
            }
        """)
        close_button.clicked.connect(dialog.accept)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        dialog.exec()
        
    def _update_ui(self):
        """Update UI elements based on playback state."""
        is_playing = self.audio_player.is_playing()
        self.play_button.setChecked(is_playing)
        # Toggle play/pause icon
        self.play_button.setIcon(
            self.style().standardIcon(QStyle.SP_MediaPause) if is_playing else self.style().standardIcon(QStyle.SP_MediaPlay)
        )
        
        is_looping = self.audio_player.is_looping()
        self.loop_button.setChecked(is_looping)
        
        # Update voice status
        if is_playing:
            self.voice_status.setText("Listening...")
        elif self.audio_player.is_paused():
            self.voice_status.setText("Paused")
        else:
            self.voice_status.setText("Stopped")
        
    def _on_duration_changed(self, duration_ms):
        """Handle duration change from player."""
        if duration_ms > 0:
            duration_sec = duration_ms / 1000.0
            formatted_total_time = self._format_time(duration_sec)
            self.total_time.setText(formatted_total_time)
            self.position_slider.setRange(0, duration_ms)
        
    def _on_playback_paused(self):
        """Handle playback paused."""
        self.logger.info("Playback paused event received")
        self.play_button.setChecked(False)
        self._update_ui()
        self._update_file_name_display()  # Update file name display
        
    def _on_difficulty_changed(self):
        if self.easy_radio.isChecked():
            self.auto_mode_difficulty = 'easy'
        elif self.medium_radio.isChecked():
            self.auto_mode_difficulty = 'medium'
        elif self.hard_radio.isChecked():
            self.auto_mode_difficulty = 'hard'
        self._update_wait_container_color()
    def _set_difficulty_enabled(self, enabled):
        self.easy_radio.setEnabled(enabled)
        self.medium_radio.setEnabled(enabled)
        self.hard_radio.setEnabled(enabled)
    def _update_wait_container_color(self):
        color = {
            'easy': '#e6ffe6',   # green
            'medium': '#fffbe6', # yellow
            'hard': '#ffe6e6'    # red
        }.get(self.auto_mode_difficulty, '#fffbe6')
        self.wait_container.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
    def set_auto_mode_difficulty(self, difficulty):
        # For programmatic (voice) changes
        if difficulty == 'easy':
            self.easy_radio.setChecked(True)
        elif difficulty == 'medium':
            self.medium_radio.setChecked(True)
        elif difficulty == 'hard':
            self.hard_radio.setChecked(True)
        self._on_difficulty_changed()
    def _on_auto_wait_toggled(self, state):
        auto = self.auto_wait_checkbox.isChecked()
        self.wait_slider.setEnabled(not auto)
        self.wait_time_value.setEnabled(not auto)
        self._set_difficulty_enabled(auto)
        self._update_wait_container_color()
    
    def _update_playlist_combo(self):
        """Update the playlist combo box with available playlists."""
        current_text = self.playlist_combo.currentText()
        self.playlist_combo.clear()
        self.playlist_combo.addItem("All Files")
        
        if hasattr(self.audio_player, 'get_playlist_names'):
            playlist_names = self.audio_player.get_playlist_names()
            for name in playlist_names:
                self.playlist_combo.addItem(name)
        
        # Try to restore selection
        if current_text and current_text != "All Files":
            index = self.playlist_combo.findText(current_text)
            if index >= 0:
                self.playlist_combo.setCurrentIndex(index)
    
    def _on_playlist_changed(self, playlist_name):
        """Handle playlist selection change."""
        if playlist_name == "All Files":
            self.audio_player.set_current_playlist(None)
        else:
            self.audio_player.set_current_playlist(playlist_name)
        self._update_file_list()
    
    def _on_add_to_playlist_clicked(self):
        """Handle add to playlist button click."""
        current_file = self.file_combo.currentData()
        if not current_file:
            return
        
        # Get available playlists
        if not hasattr(self.audio_player, 'get_playlist_names'):
            return
        
        playlist_names = self.audio_player.get_playlist_names()
        if not playlist_names:
            # No playlists exist, create one
            self._create_new_playlist_dialog(current_file)
        else:
            # Show playlist selection dialog
            self._show_playlist_selection_dialog(current_file, playlist_names)
    
    def _create_new_playlist_dialog(self, file_path):
        """Create a new playlist with the given file."""
        from PySide6.QtWidgets import QInputDialog
        
        name, ok = QInputDialog.getText(self, "New Playlist", "Enter playlist name:")
        if ok and name.strip():
            if hasattr(self.audio_player, 'create_playlist'):
                if self.audio_player.create_playlist(name.strip(), [file_path]):
                    self.logger.info(f"Created playlist '{name}' with {os.path.basename(file_path)}")
                else:
                    self.logger.warning(f"Failed to create playlist '{name}'")
    
    def _show_playlist_selection_dialog(self, file_path, playlist_names):
        """Show dialog to select which playlist to add the file to."""
        from PySide6.QtWidgets import QInputDialog
        
        playlist_name, ok = QInputDialog.getItem(
            self, "Add to Playlist", "Select playlist:", 
            playlist_names + ["Create New..."], 0, False
        )
        
        if ok and playlist_name:
            if playlist_name == "Create New...":
                self._create_new_playlist_dialog(file_path)
            else:
                if hasattr(self.audio_player, 'add_to_playlist'):
                    if self.audio_player.add_to_playlist(playlist_name, file_path):
                        self.logger.info(f"Added {os.path.basename(file_path)} to playlist '{playlist_name}'")
                    else:
                        self.logger.info(f"File already in playlist '{playlist_name}'")
        