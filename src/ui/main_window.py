from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                                 QHBoxLayout, QPushButton, QLabel, QFrame, QSpacerItem, QSizePolicy, QSlider, QSpinBox)
from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QIcon, QKeyEvent
from .widgets.audio_control_widget import AudioControlWidget
from .widgets.serial_monitor_widget import SerialMonitorWidget
from .widgets.dg_control_widget import DGControlWidget
from hardware.qt_serial_monitor import QtSerialMonitor
from audio.qt_player import QtAudioPlayer
from audio.voice_control import VoiceController
from hardware.dg_audio_adapter import DGAudioAdapter
from visualization.manager import VisualizationManager
import threading
import logging
import os
import asyncio
import qasync
import time
import json

class MainWindow(QMainWindow):
    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        self.is_waiting = False
        self.is_hold_active = False
        self._master_volume = 1.0
        self._ramp_timer = None
        self._target_volume = 1.0
        self._start_volume = 0.0
        self._ramp_start_time = None
        self._ramp_duration_minutes = 0
        self._ramp_paused_time = None
        self._ramp_elapsed_before_pause = 0
        self._volume_lock = threading.Lock()
        
        # Hold-related state variables
        self._original_hold_volume = None
        self._current_hold_volume = None
        self._hold_thread = None
        self._hold_ramp_active = False
        
        # Mode-related state variables
        self.current_mode = "medium"  # Default mode
        
        # Create audio player
        self.audio_player = QtAudioPlayer(self.logger)
        self.current_file = None
        self.favorites = self._load_favorites()
        
        # Create voice controller
        self.voice_controller = VoiceController(self.logger)
        self.voice_controller.command_recognized.connect(self._handle_voice_command)
        
        # Create DG adapter
        self.dg_adapter = DGAudioAdapter(self.audio_player, self.logger)
        
        # Connect DG adapter signals
        self.dg_adapter.device.connection_changed.connect(self._on_connection_changed)
        
        # Get the existing event loop
        self.loop = asyncio.get_event_loop()
        
        # Start DG adapter
        self.loop.create_task(self._start_dg_adapter())
        
        # Load audio files from absolute path
        audio_dir = "/Users/peterflaschner/code/Solo adventure/audio"
        if not self.audio_player.load_files(audio_dir):
            self.logger.warning(f"No audio files found in {audio_dir}")

        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # Create left column
        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setSpacing(5)
        
        # Create top info section
        top_container = QWidget()
        top_layout = QHBoxLayout(top_container)
        top_layout.setContentsMargins(5, 5, 5, 5)

        # Create title label
        self.title_label = QLabel("No file playing")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px")
        top_layout.addWidget(self.title_label)
        
        # Add favorite button
        self.favorite_button = QPushButton("★")
        self.favorite_button.setFixedSize(30, 30)
        self.favorite_button.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                border: none;
                border-radius: 15px;
                background-color: transparent;
                color: #808080;
            }
            QPushButton:hover {
                color: #FFD700;
            }
        """)
        self.favorite_button.clicked.connect(self._on_favorite_clicked)
        self.favorite_button.setEnabled(False)
        top_layout.addWidget(self.favorite_button)
        
        left_layout.addWidget(top_container)
        
        # Add connection status and cycle counter in one row
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(5, 0, 5, 0)
        
        self.connection_label = QLabel("DG: Disconnected")
        self.connection_label.setStyleSheet("font-size: 12px; color: #ff4444")
        status_layout.addWidget(self.connection_label)
        
        left_layout.addWidget(status_container)
        
        # Create current pressure display
        pressure_container = QWidget()
        pressure_layout = QHBoxLayout(pressure_container)
        pressure_layout.setContentsMargins(5, 0, 5, 0)
        
        pressure_label = QLabel("Pressure:")
        pressure_label.setStyleSheet("font-size: 12px; font-weight: bold")
        pressure_layout.addWidget(pressure_label)
        
        self.pressure_value = QLabel("0.00 kPa")
        self.pressure_value.setStyleSheet("font-size: 12px")
        self.pressure_value.setMinimumWidth(80)
        pressure_layout.addWidget(self.pressure_value)
        
        left_layout.addWidget(pressure_container)
        
        # Create master volume control
        master_volume_container = QWidget()
        master_volume_layout = QHBoxLayout(master_volume_container)
        master_volume_layout.setContentsMargins(5, 0, 5, 0)
        
        master_volume_label = QLabel("Master:")
        master_volume_label.setStyleSheet("font-size: 12px; font-weight: bold")
        master_volume_layout.addWidget(master_volume_label)
        
        self.master_volume_slider = QSlider(Qt.Horizontal)
        self.master_volume_slider.setRange(0, 100)
        self.master_volume_slider.setValue(100)
        self.master_volume_slider.valueChanged.connect(self._on_master_volume_changed)
        master_volume_layout.addWidget(self.master_volume_slider)
        
        self.master_volume_value = QLabel("100%")
        self.master_volume_value.setMinimumWidth(40)
        master_volume_layout.addWidget(self.master_volume_value)
        
        left_layout.addWidget(master_volume_container)
        
        # Create hold volume drop control
        hold_drop_container = QWidget()
        hold_drop_layout = QHBoxLayout(hold_drop_container)
        hold_drop_layout.setContentsMargins(5, 0, 5, 0)
        
        hold_drop_label = QLabel("Hold Drop:")
        hold_drop_label.setStyleSheet("font-size: 12px; font-weight: bold")
        hold_drop_layout.addWidget(hold_drop_label)
        
        self.hold_drop_slider = QSlider(Qt.Horizontal)
        self.hold_drop_slider.setRange(0, 100)
        self.hold_drop_slider.setValue(20)
        hold_drop_layout.addWidget(self.hold_drop_slider)
        
        self.hold_drop_value = QLabel("20%")
        self.hold_drop_value.setMinimumWidth(40)
        hold_drop_layout.addWidget(self.hold_drop_value)
        
        self.hold_drop_slider.valueChanged.connect(self._on_hold_drop_changed)
        
        left_layout.addWidget(hold_drop_container)
        
        # Create wait time control
        wait_time_container = QWidget()
        wait_time_layout = QHBoxLayout(wait_time_container)
        wait_time_layout.setContentsMargins(5, 0, 5, 0)
        
        wait_time_label = QLabel("Wait Time:")
        wait_time_label.setStyleSheet("font-size: 12px; font-weight: bold")
        wait_time_layout.addWidget(wait_time_label)
        
        self.wait_time_slider = QSlider(Qt.Horizontal)
        self.wait_time_slider.setRange(0, 30)
        self.wait_time_slider.setValue(5)
        wait_time_layout.addWidget(self.wait_time_slider)
        
        self.wait_time_value = QLabel("5s")
        self.wait_time_value.setMinimumWidth(40)
        wait_time_layout.addWidget(self.wait_time_value)
        
        self.wait_time_slider.valueChanged.connect(self._on_wait_time_changed)
        
        left_layout.addWidget(wait_time_container)

        # Create DG delay control
        dg_delay_container = QWidget()
        dg_delay_layout = QHBoxLayout(dg_delay_container)
        dg_delay_layout.setContentsMargins(5, 0, 5, 0)
        
        dg_delay_label = QLabel("DG Delay:")
        dg_delay_label.setStyleSheet("font-size: 12px; font-weight: bold")
        dg_delay_layout.addWidget(dg_delay_label)
        
        self.dg_delay_slider = QSlider(Qt.Horizontal)
        self.dg_delay_slider.setRange(0, 180)
        self.dg_delay_slider.setValue(0)
        dg_delay_layout.addWidget(self.dg_delay_slider)
        
        self.dg_delay_value = QLabel("0s")
        self.dg_delay_value.setMinimumWidth(40)
        dg_delay_layout.addWidget(self.dg_delay_value)
        
        self.dg_delay_slider.valueChanged.connect(self._on_dg_delay_changed)
        
        left_layout.addWidget(dg_delay_container)

        # Create serial threshold control
        threshold_container = QWidget()
        threshold_layout = QHBoxLayout(threshold_container)
        threshold_layout.setContentsMargins(5, 0, 5, 0)
        
        threshold_label = QLabel("Threshold:")
        threshold_label.setStyleSheet("font-size: 12px; font-weight: bold")
        threshold_layout.addWidget(threshold_label)
        
        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setRange(0, 50)
        self.threshold_slider.setValue(20)
        threshold_layout.addWidget(self.threshold_slider)
        
        self.threshold_value = QLabel("20 kPa")
        self.threshold_value.setMinimumWidth(40)
        threshold_layout.addWidget(self.threshold_value)
        
        self.threshold_slider.valueChanged.connect(self._on_threshold_changed)
        
        left_layout.addWidget(threshold_container)
        
        # Create button container
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create and style hooray button
        self.hooray_button = QPushButton("HOORAY!")
        self.update_hooray_button_style()
        self.hooray_button.clicked.connect(self.on_hooray_clicked)
        button_layout.addWidget(self.hooray_button)
        
        # Create hold buttons container for vertical layout
        hold_container = QWidget()
        hold_layout = QVBoxLayout(hold_container)
        hold_layout.setContentsMargins(0, 0, 0, 0)
        hold_layout.setSpacing(5)
        
        # Create and style hold button
        self.hold_button = QPushButton("HOLD")
        self.hold_button.setFixedSize(self.hooray_button.sizeHint().width(), 50)  # Match hooray button width
        self.update_hold_button_style()
        self.hold_button.clicked.connect(self.on_hold_clicked)
        hold_layout.addWidget(self.hold_button)
        
        # Create and style cancel hold button
        self.cancel_hold_button = QPushButton("Cancel Hold")
        self.cancel_hold_button.setFixedWidth(self.hold_button.width())
        self.cancel_hold_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                padding: 5px;
                background-color: #ff4444;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #ff6666;
            }
            QPushButton:pressed {
                background-color: #cc3333;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.cancel_hold_button.clicked.connect(self.on_cancel_hold_clicked)
        self.cancel_hold_button.setEnabled(False)
        hold_layout.addWidget(self.cancel_hold_button)
        
        button_layout.addWidget(hold_container)
        left_layout.addWidget(button_container)
        
        # Create cycle counter container
        cycle_container = QWidget()
        cycle_layout = QHBoxLayout(cycle_container)
        cycle_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create cycle counter with larger font and centered
        self.cycle_label = QLabel("Cycle: 0")
        self.cycle_label.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #4CAF50;
            padding: 10px;
        """)
        self.cycle_label.setAlignment(Qt.AlignCenter)
        cycle_layout.addWidget(self.cycle_label)
        
        left_layout.addWidget(cycle_container)
        
        # Add stretch to push everything up
        left_layout.addStretch()
        
        # Create right column
        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setSpacing(5)
        
        # Create audio control widget
        self.audio_control = AudioControlWidget(self.audio_player)
        right_layout.addWidget(self.audio_control)
        
        # Connect favorites toggle
        self.audio_control.favorites_button.clicked.connect(self._on_show_favorites_clicked)

        # Create DG control widget
        self.dg_control = DGControlWidget(self.dg_adapter)
        right_layout.addWidget(self.dg_control)

        # Create collapsible serial monitor
        monitor_container = QWidget()
        monitor_layout = QVBoxLayout(monitor_container)
        monitor_layout.setContentsMargins(0, 0, 0, 0)
        
        monitor_header = QPushButton("Serial Monitor ▼")
        monitor_header.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 5px;
                background-color: #f0f0f0;
                border: none;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        monitor_header.clicked.connect(self._toggle_serial_monitor)
        monitor_layout.addWidget(monitor_header)
        
        self.serial_monitor = SerialMonitorWidget(QtSerialMonitor(self.logger))
        self.serial_monitor.setVisible(False)
        monitor_layout.addWidget(self.serial_monitor)
        
        right_layout.addWidget(monitor_container)
        
        # Add columns to main layout with proper sizing
        main_layout.addWidget(left_column, 40)
        main_layout.addWidget(right_column, 60)
        
        # Connect volume controls
        self.audio_control.volume_slider.valueChanged.connect(self._on_audio_volume_changed)
        self.dg_control.base_scale.valueChanged.connect(self._on_dg_volume_changed)

        # Create visualization manager (for plotting)
        self.viz_manager = VisualizationManager(audio_control_widget=self.audio_control)
        self.viz_manager.start()

        # Connect serial monitor signals
        self.serial_monitor.serial_monitor.button_single_press.connect(self.on_hooray_clicked)
        self.serial_monitor.serial_monitor.button_double_press.connect(self._on_double_press)
        self.serial_monitor.serial_monitor.pressure_updated.connect(self.viz_manager.update)
        self.serial_monitor.serial_monitor.pressure_updated.connect(self._on_pressure_updated)

        # Start serial monitor
        self.serial_monitor.serial_monitor.port = "/dev/cu.usbmodem170307301"
        self.serial_monitor.serial_monitor.start()

        # Connect audio player signals
        self.audio_player.playback_started.connect(self._on_playback_started)
        self.audio_player.playback_stopped.connect(self._on_playback_stopped)
        self.audio_player.audio_data_ready.connect(self.viz_manager.update_audio_metrics)
        self.audio_player.hooray_cycle_complete.connect(self._on_hooray_cycle_complete)
        
        # Set up window
        self.setWindowTitle("Auto Player")
        self.resize(1000, 600)
        
        # Populate dropdown with available files
        self._populate_file_dropdown()

        # Create cleanup timer
        self._cleanup_timer = QTimer()
        self._cleanup_timer.setSingleShot(True)
        self._cleanup_timer.timeout.connect(self._force_cleanup)

        # Create ramp time control
        ramp_time_container = QWidget()
        ramp_time_layout = QHBoxLayout(ramp_time_container)
        ramp_time_layout.setContentsMargins(5, 0, 5, 0)
        
        ramp_time_label = QLabel("Ramp Time (min):")
        ramp_time_label.setStyleSheet("font-size: 12px; font-weight: bold")
        ramp_time_layout.addWidget(ramp_time_label)
        
        self.ramp_time_slider = QSlider(Qt.Horizontal)
        self.ramp_time_slider.setRange(1, 90)
        self.ramp_time_slider.setValue(30)
        self.ramp_time_slider.valueChanged.connect(self._on_ramp_time_changed)
        ramp_time_layout.addWidget(self.ramp_time_slider)
        
        self.ramp_time_value = QLabel("30")
        self.ramp_time_value.setMinimumWidth(40)
        ramp_time_layout.addWidget(self.ramp_time_value)
        
        left_layout.addWidget(ramp_time_container)
        
        # Create start ramp button
        self.start_ramp_button = QPushButton("Start Volume Ramp")
        self.start_ramp_button.clicked.connect(self.start_volume_ramp)
        self.start_ramp_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 5px;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        left_layout.addWidget(self.start_ramp_button)

        # Create mode selection container (after master volume control)
        mode_container = QWidget()
        mode_layout = QVBoxLayout(mode_container)
        mode_layout.setContentsMargins(5, 0, 5, 0)
        
        # Add mode label
        mode_label = QLabel("Difficulty Mode:")
        mode_label.setStyleSheet("font-size: 12px; font-weight: bold")
        mode_layout.addWidget(mode_label)
        
        # Add current mode indicator
        self.mode_indicator = QLabel("MEDIUM MODE")
        self.mode_indicator.setAlignment(Qt.AlignCenter)
        self.mode_indicator.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: white;
            background-color: #FFA500;
            padding: 5px;
            border-radius: 5px;
            margin: 5px;
        """)
        mode_layout.addWidget(self.mode_indicator)
        
        # Create mode buttons container
        mode_buttons = QWidget()
        mode_buttons_layout = QHBoxLayout(mode_buttons)
        mode_buttons_layout.setSpacing(5)
        
        # Create mode buttons
        self.easy_button = QPushButton("Easy")
        self.medium_button = QPushButton("Medium")
        self.hard_button = QPushButton("Hard")
        
        # Style mode buttons
        for button, color in [(self.easy_button, "#4CAF50"), 
                            (self.medium_button, "#FFA500"), 
                            (self.hard_button, "#ff4444")]:
            button.setCheckable(True)
            button.setStyleSheet(f"""
                QPushButton {{
                    font-size: 12px;
                    font-weight: bold;
                    padding: 5px;
                    background-color: {color};
                    color: white;
                    border: none;
                    border-radius: 3px;
                    opacity: 0.7;
                }}
                QPushButton:checked {{
                    opacity: 1.0;
                }}
                QPushButton:hover {{
                    opacity: 0.9;
                }}
            """)
            mode_buttons_layout.addWidget(button)
        
        # Connect mode buttons
        self.easy_button.clicked.connect(lambda: self.set_mode("easy"))
        self.medium_button.clicked.connect(lambda: self.set_mode("medium"))
        self.hard_button.clicked.connect(lambda: self.set_mode("hard"))
        
        # Set initial mode
        self.medium_button.setChecked(True)
        
        mode_layout.addWidget(mode_buttons)
        left_layout.addWidget(mode_container)

    def _toggle_serial_monitor(self):
        """Toggle the visibility of the serial monitor."""
        self.serial_monitor.setVisible(not self.serial_monitor.isVisible())

    def update_hooray_button_style(self):
        """Update the hooray button style based on wait state."""
        color = "#808080" if self.is_waiting else "#4CAF50"
        hover_color = "#707070" if self.is_waiting else "#45a049"
        pressed_color = "#606060" if self.is_waiting else "#3d8b40"
        
        self.hooray_button.setStyleSheet(f"""
            QPushButton {{
                font-size: 24px;
                font-weight: bold;
                padding: 20px 40px;
                background-color: {color};
                color: white;
                border: none;
                border-radius: 10px;
                min-width: 200px;
                min-height: 100px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {pressed_color};
            }}
        """)
        
    def _populate_file_dropdown(self, show_favorites=False):
        """Populate the file dropdown with available audio files."""
        if hasattr(self.audio_control, 'file_combo'):
            self.audio_control.file_combo.clear()
            # Filter files based on favorites if needed
            files_to_show = [f for f in self.audio_player.file_list 
                           if not show_favorites or os.path.basename(f) in self.favorites]
            # Sort files by their base names
            sorted_files = sorted(files_to_show, key=lambda x: os.path.basename(x).lower())
            for file_path in sorted_files:
                self.audio_control.file_combo.addItem(os.path.basename(file_path))
            if files_to_show:
                self.audio_control.play_selected_button.setEnabled(True)
            else:
                self.audio_control.play_selected_button.setEnabled(False)

    def _on_show_favorites_clicked(self, checked):
        """Handle show favorites button toggle."""
        self.audio_control.favorites_button.setText("Show All" if checked else "Show Favorites")
        self._populate_file_dropdown(show_favorites=checked)

    def _on_playback_started(self, filename):
        """Handle playback started."""
        self.current_file = filename
        self.title_label.setText(f"Playing: {os.path.basename(filename)}")
        self.favorite_button.setEnabled(True)
        
        # Update favorite button style based on current file
        self._update_favorite_button()
        
    def _on_playback_stopped(self):
        """Handle playback stopped."""
        self.current_file = None
        self.title_label.setText("No file playing")
        self.favorite_button.setEnabled(False)
        self.favorite_button.setStyleSheet("""
            QPushButton {
                font-size: 24px;
                border: none;
                border-radius: 20px;
                background-color: transparent;
                color: #808080;
            }
            QPushButton:hover {
                color: #FFD700;
            }
        """)

    def _on_hooray_cycle_complete(self):
        """Handle completion of a hooray cycle."""
        self.is_waiting = False
        self.update_hooray_button_style()
        self.cycle_label.setText(f"Cycle: {self.viz_manager.current_cycle}")
        
    def on_hooray_clicked(self):
        """Handle hooray button click."""
        if self.is_waiting:
            self.logger.info("Waiting for previous hooray to complete")
            return
            
        self.logger.info("Hooray button clicked!")
        if not self.audio_player.player.isPlaying():
            self.logger.info("No audio playing, ignoring hooray")
            return
            
        # Get current playback time in seconds
        current_time = self.audio_player.player.position() / 1000.0  # Convert ms to seconds
        current_file = os.path.basename(self.current_file) if self.current_file else "unknown"
        self.logger.info(f"Starting hooray cycle at {current_time:.1f}s in track: {current_file}")
        
        # Save peak performer clip only if not in hard mode
        if self.current_mode != "hard":
            self.audio_player.save_peak_performer("hooray")
        
        # Set waiting state
        self.is_waiting = True
        self.update_hooray_button_style()
        
        # Log the hooray event with playhead time
        self.viz_manager.log_event("hooray_started", value=f"{current_time:.1f}")
        self.viz_manager.current_cycle += 1
        self.cycle_label.setText(f"Cycle: {self.viz_manager.current_cycle}")
        
        # If hold is active, store its state
        hold_was_active = self.is_hold_active
        hold_original_volume = self._original_hold_volume
        hold_current_volume = self._current_hold_volume
        
        # Temporarily disable hold if it's active
        if hold_was_active:
            self.is_hold_active = False
        
        # Start hooray cycle in a separate thread
        threading.Thread(
            target=lambda: self._run_hooray_cycle(hold_was_active, hold_original_volume, hold_current_volume),
            daemon=True
        ).start()

    def _run_hooray_cycle(self, resume_hold=False, hold_original_volume=None, hold_current_volume=None):
        """Run the hooray cycle with separate audio and DG timing."""
        try:
            # Store original volumes - use master volume instead of audio control
            original_master_volume = self.master_volume_slider.value()
            audio_volume = self.audio_control.volume_slider.value() / 100.0
            dg_volume = self.dg_control.base_scale.value() / 100.0
            
            # Immediately set master volume to 0
            self.master_volume_slider.setValue(0)
            self._on_master_volume_changed(0)
            self.logger.info("Volumes set to 0")
            
            # Wait for user-defined wait time
            wait_time = self.wait_time_slider.value()
            self.logger.info(f"Waiting {wait_time} seconds")
            time.sleep(wait_time)
            
            # Ramp master volume back up over 5 seconds
            self.logger.info("Ramping volume back up")
            start_time = time.time()
            while time.time() - start_time < 5:
                progress = (time.time() - start_time) / 5
                new_volume = int(original_master_volume * progress)
                self.master_volume_slider.setValue(new_volume)
                self._on_master_volume_changed(new_volume)
                time.sleep(0.05)  # Small sleep to prevent CPU overload
            
            # Ensure final volume is set
            self.master_volume_slider.setValue(original_master_volume)
            self._on_master_volume_changed(original_master_volume)
            
            # Start DG delay countdown
            dg_delay = self.dg_delay_slider.value()
            if dg_delay > 0:
                self.logger.info(f"Starting DG delay countdown: {dg_delay}s")
                time.sleep(dg_delay)
            
            self.logger.info("Hooray cycle complete")
            
            # Resume hold if it was active
            if resume_hold and hold_original_volume is not None and hold_current_volume is not None:
                self.is_hold_active = True
                self._original_hold_volume = hold_original_volume
                self._current_hold_volume = hold_current_volume
                self.update_hold_button_style()
                
                # Start a new hold thread to continue the ramp up
                self._hold_thread = threading.Thread(
                    target=self._run_hold_cycle,
                    daemon=True
                )
                self._hold_thread.start()
            
            # Mark hooray as complete to allow new activations
            self.is_waiting = False
            self.update_hooray_button_style()
            
        except Exception as e:
            self.logger.error(f"Error in hooray cycle: {e}")
            self.is_waiting = False
            self.update_hooray_button_style()

    def _on_double_press(self):
        """Handle double button press from Teensy."""
        self.logger.info("Double press detected - playing random file")
        self.viz_manager.log_event("next_file")
        self.audio_player.play_random_file()

    def closeEvent(self, event):
        """Handle window close event."""
        self.logger.info("Closing")
        try:
            # Stop any active cycles
            self.is_hold_active = False
            self.is_waiting = False

            # Stop visualization manager
            if hasattr(self, 'viz_manager'):
                self.viz_manager.stop()

            # Stop audio playback
            if hasattr(self, 'audio_player'):
                self.audio_player.stop_playback()

            # Stop DG adapter
            if hasattr(self, 'dg_adapter'):
                asyncio.create_task(self.dg_adapter.stop())
            
            # Stop serial monitor
            if hasattr(self, 'serial_monitor'):
                self.serial_monitor.stop()
                # Give threads time to clean up
                QThread.msleep(100)

            # Accept the close event
            event.accept()
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            event.accept()  # Still close even if there's an error

        # Force cleanup after a short delay if needed
        QTimer.singleShot(500, self._force_cleanup)

    def _force_cleanup(self):
        """Force cleanup after timeout."""
        try:
            self.logger.info("Force cleanup")
            # Force close any remaining windows
            for window in QApplication.topLevelWidgets():
                if window != self:
                    window.close()
            self.close()
        except Exception as e:
            self.logger.error(f"Error during force cleanup: {e}")
            self.close()

    @Slot(bool)
    def _on_connection_changed(self, connected: bool):
        """Handle DG device connection state changes."""
        if connected:
            self.connection_label.setText("DG: Connected")
            self.connection_label.setStyleSheet("font-size: 14px; padding: 10px; color: #44ff44")
        else:
            self.connection_label.setText("DG: Disconnected")
            self.connection_label.setStyleSheet("font-size: 14px; padding: 10px; color: #ff4444") 

    async def _start_dg_adapter(self):
        """Start the DG adapter."""
        try:
            self.dg_adapter.start()
        except Exception as e:
            self.logger.error(f"Error starting DG adapter: {e}") 

    @Slot(int)
    def _on_master_volume_changed(self, value):
        """Handle master volume slider change."""
        self._master_volume = value / 100.0
        self.master_volume_value.setText(f"{value}%")
        
        # Scale audio volume
        if hasattr(self, 'audio_control'):
            audio_max = self.audio_control.volume_slider.value() / 100.0
            self.audio_player.set_volume(audio_max * self._master_volume)
        
        # Scale DG volume (base intensity)
        if hasattr(self, 'dg_control'):
            dg_max = self.dg_control.base_scale.value() / 100.0
            self.dg_adapter.base_intensity_scale = dg_max * self._master_volume

    def _on_audio_volume_changed(self, value):
        """Handle audio volume slider change."""
        audio_max = value / 100.0
        self.audio_player.set_volume(audio_max * self._master_volume)

    def _on_dg_volume_changed(self, value):
        """Handle DG volume (base intensity) change."""
        dg_max = value / 100.0
        self.dg_adapter.base_intensity_scale = dg_max * self._master_volume 

    def update_hold_button_style(self):
        """Update the hold button style based on active state."""
        color = "#808080" if self.is_hold_active else "#FFD700"
        hover_color = "#707070" if self.is_hold_active else "#FFE55C"
        pressed_color = "#606060" if self.is_hold_active else "#E6C200"
        
        self.hold_button.setStyleSheet(f"""
            QPushButton {{
                font-size: 18px;
                font-weight: bold;
                padding: 10px;
                background-color: {color};
                color: {'white' if self.is_hold_active else 'black'};
                border: none;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {pressed_color};
            }}
        """)

    def on_hold_clicked(self):
        """Handle hold button click."""
        if not self.audio_player.player.isPlaying():
            self.logger.info("No audio playing, ignoring hold")
            return
            
        # If this is the first hold in a cycle
        if not self.is_hold_active:
            self.is_hold_active = True
            self._original_hold_volume = self.master_volume_slider.value()
            self._current_hold_volume = self._original_hold_volume
            self._hold_ramp_active = False
            self.update_hold_button_style()
            self.cancel_hold_button.setEnabled(True)  # Enable cancel button
            self.logger.info("Hold cycle started")
            
            # Start hold cycle in a separate thread
            self._hold_thread = threading.Thread(
                target=self._run_hold_cycle,
                daemon=True
            )
            self._hold_thread.start()
        else:
            # This is a subsequent hold during the same cycle
            self.logger.info("Additional hold triggered during cycle")
            self._trigger_additional_hold()
        
    def on_cancel_hold_clicked(self):
        """Handle cancel hold button click."""
        if not self.is_hold_active or self._original_hold_volume is None:
            return
            
        self.logger.info("Canceling hold cycle")
        
        # Stop the hold cycle
        self.is_hold_active = False
        self._hold_ramp_active = False
        
        # Restore original volume immediately
        self.master_volume_slider.setValue(self._original_hold_volume)
        self._on_master_volume_changed(self._original_hold_volume)
        
        # Reset hold state
        self._original_hold_volume = None
        self._current_hold_volume = None
        self._hold_thread = None
        self.update_hold_button_style()
        self.cancel_hold_button.setEnabled(False)  # Disable cancel button
        
        # Resume volume ramp if it was active
        self._resume_volume_ramp()
        
        self.logger.info("Hold cycle canceled")

    def _trigger_additional_hold(self):
        """Handle an additional hold during an active hold cycle."""
        try:
            # Calculate new dropped volume from current volume
            hold_drop_percent = self.hold_drop_slider.value() / 100.0
            self._current_hold_volume = max(0, int(self._current_hold_volume * (1 - hold_drop_percent)))
            
            # Apply the new dropped volume
            self.master_volume_slider.setValue(self._current_hold_volume)
            self._on_master_volume_changed(self._current_hold_volume)
            self.logger.info(f"Additional hold: Volume dropped to {self._current_hold_volume}%")
            
            # Pause any active ramp up
            self._hold_ramp_active = False
            
        except Exception as e:
            self.logger.error(f"Error in additional hold: {e}")
        
    def _run_hold_cycle(self):
        """Run the hold cycle in a separate thread."""
        try:
            # Pause volume ramp if active
            self._pause_volume_ramp()
            
            # Initial volume drop
            hold_drop_percent = self.hold_drop_slider.value() / 100.0
            self._current_hold_volume = max(0, int(self._current_hold_volume * (1 - hold_drop_percent)))
            
            # Apply volume drop
            self.master_volume_slider.setValue(self._current_hold_volume)
            self._on_master_volume_changed(self._current_hold_volume)
            self.logger.info(f"Volume dropped to {self._current_hold_volume}%")
            
            # Start ramp up
            self._hold_ramp_active = True
            
            # Ramp back up at 1% per second to original volume
            while self._current_hold_volume < self._original_hold_volume and self.is_hold_active:
                if self._hold_ramp_active:  # Only ramp if not paused
                    self._current_hold_volume = min(self._original_hold_volume, self._current_hold_volume + 1)
                    self.master_volume_slider.setValue(self._current_hold_volume)
                    self._on_master_volume_changed(self._current_hold_volume)
                    self.logger.debug(f"Ramping up to {self._current_hold_volume}%")
                time.sleep(1.0)  # Wait 1 second
            
            # Resume volume ramp if it was active
            self._resume_volume_ramp()
            
            # Reset hold state
            self.is_hold_active = False
            self._original_hold_volume = None
            self._current_hold_volume = None
            self._hold_thread = None
            self._hold_ramp_active = False
            self.update_hold_button_style()
            self.cancel_hold_button.setEnabled(False)  # Disable cancel button
            self.logger.info("Hold cycle completed")
            
        except Exception as e:
            self.logger.error(f"Error in hold cycle: {e}")
            self.is_hold_active = False
            self._original_hold_volume = None
            self._current_hold_volume = None
            self._hold_thread = None
            self._hold_ramp_active = False
            self.update_hold_button_style()
            self.cancel_hold_button.setEnabled(False)  # Disable cancel button

    def _update_all_volumes(self):
        """Update all volume-dependent components."""
        try:
            # Get volume values under lock
            with self._volume_lock:
                master_volume = self._master_volume
                volume_percent = int(master_volume * 100)
                
                if hasattr(self, 'audio_control'):
                    audio_volume = self.audio_control.volume_slider.value() / 100.0
                    
                if hasattr(self, 'dg_control'):
                    dg_volume = self.dg_control.base_scale.value() / 100.0

            # Update UI outside lock
            self.master_volume_slider.blockSignals(True)
            self.master_volume_slider.setValue(volume_percent)
            self.master_volume_slider.blockSignals(False)
            self.master_volume_value.setText(f"{volume_percent}%")
            
            # Update volumes outside lock
            if hasattr(self, 'audio_control'):
                self.audio_player.set_volume(audio_volume * master_volume)
                
            if hasattr(self, 'dg_control'):
                self.dg_adapter.base_intensity_scale = dg_volume * master_volume
                
        except Exception as e:
            self.logger.error(f"Error in _update_all_volumes: {e}")

    def _on_hold_drop_changed(self, value):
        """Handle hold volume drop slider change."""
        hold_drop_percent = value / 100.0
        self.hold_drop_value.setText(f"{hold_drop_percent}%")
        
        # Scale hold volume
        if hasattr(self, 'dg_control'):
            dg_max = self.dg_control.base_scale.value() / 100.0
            self.dg_adapter.hold_volume_scale = dg_max * hold_drop_percent

    def _load_favorites(self):
        """Load favorites from JSON file."""
        favorites_path = os.path.join("data", "favorites.json")
        if os.path.exists(favorites_path):
            try:
                with open(favorites_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading favorites: {e}")
        return []

    def _save_favorites(self):
        """Save favorites to JSON file."""
        favorites_path = os.path.join("data", "favorites.json")
        try:
            os.makedirs("data", exist_ok=True)
            with open(favorites_path, 'w') as f:
                json.dump(self.favorites, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving favorites: {e}")

    def _update_favorite_button(self):
        """Update favorite button appearance based on current file."""
        if not self.current_file:
            return
            
        is_favorite = os.path.basename(self.current_file) in self.favorites
        self.favorite_button.setStyleSheet(f"""
            QPushButton {{
                font-size: 24px;
                border: none;
                border-radius: 20px;
                background-color: transparent;
                color: {'#FFD700' if is_favorite else '#808080'};
            }}
            QPushButton:hover {{
                color: {'#FFA500' if is_favorite else '#FFD700'};
            }}
        """)

    def _on_favorite_clicked(self):
        """Handle favorite button click."""
        if not self.current_file:
            return
            
        current_basename = os.path.basename(self.current_file)
        if current_basename in self.favorites:
            self.favorites.remove(current_basename)
            self.logger.info(f"Removed from favorites: {current_basename}")
        else:
            self.favorites.append(current_basename)
            self.logger.info(f"Added to favorites: {current_basename}")
            
        self._save_favorites()
        self._update_favorite_button()
        
        # Refresh the dropdown if showing favorites
        if self.audio_control.favorites_button.isChecked():
            self._populate_file_dropdown(show_favorites=True)

    def _on_wait_time_changed(self, value):
        """Handle wait time slider value change."""
        self.wait_time_value.setText(f"{value}s")
        self.audio_player.set_wait_time(value)

    def _on_threshold_changed(self, value):
        """Handle threshold slider value change."""
        self.threshold_value.setText(f"{value} kPa")
        if hasattr(self, 'serial_monitor') and self.serial_monitor:
            self.serial_monitor.serial_monitor.set_pressure_threshold(value)

    def _on_pressure_updated(self, pressure):
        """Handle pressure updates."""
        self.pressure_value.setText(f"{pressure:.2f} kPa")

    def _on_ramp_time_changed(self, value):
        """Handle ramp time slider change."""
        self.ramp_time_value.setText(str(value))
        self._ramp_duration_minutes = value
        
    def start_volume_ramp(self):
        """Start the volume ramp-up process."""
        if self._ramp_timer is not None:
            # Stop existing ramp
            self._ramp_timer.stop()
            self._ramp_timer = None
            self._ramp_paused_time = None
            self._ramp_elapsed_before_pause = 0
            self.start_ramp_button.setText("Start Volume Ramp")
            return
            
        # Initialize ramp parameters
        with self._volume_lock:
            self._start_volume = self._master_volume
            self._target_volume = 1.0
            self._ramp_start_time = time.time()
            self._ramp_paused_time = None
            self._ramp_elapsed_before_pause = 0
        
        # Create and start the timer for volume updates
        self._ramp_timer = QTimer(self)
        self._ramp_timer.timeout.connect(self._update_ramped_volume)
        self._ramp_timer.start(1000)  # Update every second
        
        self.start_ramp_button.setText("Stop Volume Ramp")
        self.logger.info(f"Starting volume ramp from {self._start_volume*100:.1f}% to 100% over {self._ramp_duration_minutes} minutes")

    def _update_ramped_volume(self):
        """Update volume during ramp-up."""
        if self._ramp_timer is None:
            return
            
        try:
            # Calculate timing under lock
            with self._volume_lock:
                if self._ramp_paused_time is not None:
                    return
                    
                elapsed_time = time.time() - self._ramp_start_time
                total_duration = self._ramp_duration_minutes * 60  # Convert to seconds
                
                if elapsed_time >= total_duration:
                    # Ramp complete
                    self._master_volume = self._target_volume
                    complete = True
                else:
                    # Calculate new volume based on progress
                    progress = min(1.0, elapsed_time / total_duration)
                    self._master_volume = self._start_volume + (self._target_volume - self._start_volume) * progress
                    complete = False
            
            # Update volumes outside lock
            self._update_all_volumes()
            
            if complete:
                self._ramp_timer.stop()
                self._ramp_timer = None
                self._ramp_paused_time = None
                self._ramp_elapsed_before_pause = 0
                self.start_ramp_button.setText("Start Volume Ramp")
                self.logger.info("Volume ramp complete")
            else:
                self.logger.debug(f"Volume ramped to {self._master_volume*100:.1f}% ({progress*100:.1f}% complete)")
                
        except Exception as e:
            self.logger.error(f"Error in _update_ramped_volume: {e}")
            if self._ramp_timer:
                self._ramp_timer.stop()
                self._ramp_timer = None

    def _pause_volume_ramp(self):
        """Pause the volume ramp if it's running."""
        with self._volume_lock:
            if self._ramp_timer is not None and self._ramp_paused_time is None:
                self._ramp_paused_time = time.time()
                self._ramp_elapsed_before_pause = time.time() - self._ramp_start_time
                self._ramp_timer.stop()
                self.logger.info("Volume ramp paused")
            
    def _resume_volume_ramp(self, hold_duration=0):
        """Resume the volume ramp if it was paused."""
        with self._volume_lock:
            if self._ramp_timer is not None and self._ramp_paused_time is not None:
                # Calculate how much time was left in the ramp when paused
                total_duration = self._ramp_duration_minutes * 60  # Convert to seconds
                remaining_time = total_duration - self._ramp_elapsed_before_pause
                
                # Calculate total pause duration including hold
                pause_duration = time.time() - self._ramp_paused_time
                
                # Adjust start time to account for both pause and hold duration
                self._ramp_start_time = time.time() - self._ramp_elapsed_before_pause
                self._ramp_start_time += pause_duration  # Add pause duration to offset the elapsed time
                self._ramp_paused_time = None
                
                # Stop existing timer if it exists
                if self._ramp_timer.isActive():
                    self._ramp_timer.stop()
                
                # Create and start a new timer
                self._ramp_timer = QTimer(self)
                self._ramp_timer.timeout.connect(self._update_ramped_volume)
                self._ramp_timer.start(1000)  # Update every second
                
                # Update button text to reflect current state
                self.start_ramp_button.setText("Stop Volume Ramp")
                
                # Log the resume with remaining time
                self.logger.info(f"Volume ramp resumed with {remaining_time:.1f} seconds remaining after {pause_duration:.1f} second pause (including {hold_duration:.1f}s hold)")

    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard events."""
        # Check if any QSpinBox has focus
        focused_widget = self.focusWidget()
        
        # Handle arrow keys for volume control regardless of focus
        if event.key() == Qt.Key_Up:
            # Increase master volume by 1%
            current_value = self.master_volume_slider.value()
            new_value = min(100, current_value + 1)
            self.master_volume_slider.setValue(new_value)
            self._on_master_volume_changed(new_value)
            event.accept()  # Mark event as handled
            return
        elif event.key() == Qt.Key_Down:
            # Decrease master volume by 1%
            current_value = self.master_volume_slider.value()
            new_value = max(0, current_value - 1)
            self.master_volume_slider.setValue(new_value)
            self._on_master_volume_changed(new_value)
            event.accept()  # Mark event as handled
            return
            
        # For all other keys, handle normally
        if isinstance(focused_widget, QSpinBox):
            super().keyPressEvent(event)
            return
            
        super().keyPressEvent(event)

    def _on_dg_delay_changed(self, value):
        """Handle DG delay slider value change."""
        self.dg_delay_value.setText(f"{value}s")

    def _handle_voice_command(self, command):
        """Handle voice commands."""
        try:
            current_time = self.audio_player.player.position() / 1000.0  # Convert to seconds
            current_file = os.path.basename(self.current_file) if self.current_file else "unknown"
            
            if command in ["hooray", "now", "edge"]:
                self.logger.info(f"Starting hooray cycle at {current_time:.1f}s in track: {current_file}")
                # Only save peak performer if not in hard mode
                if self.current_mode != "hard":
                    self.audio_player.save_peak_performer("hooray")
                self.on_hooray_clicked()
            elif command == "yes":
                self.logger.info(f"Yes command triggered at {current_time:.1f}s in track: {current_file}")
                # Only save peak performer if not in hard mode
                if self.current_mode != "hard":
                    self.audio_player.save_peak_performer("yes")
                self.audio_control.show_yes_triggered()
            elif command == "hold":
                self.logger.info(f"Hold command triggered at {current_time:.1f}s in track: {current_file}")
                self.on_hold_clicked()
            elif command == "up":
                self._adjust_volume(0.1)
            elif command == "down":
                self._adjust_volume(-0.1)
            elif command == "skip":
                self.audio_player.play_random_file()
            elif command == "pause":
                if self.audio_player.player.playbackState() == QMediaPlayer.PlayingState:
                    self.audio_player.player.pause()
            elif command == "playback":
                if self.audio_player.player.playbackState() == QMediaPlayer.PausedState:
                    self.audio_player.player.play()
            elif command == "stop":
                self.audio_player.stop_playback()
            elif command == "easy_mode":
                self.set_mode("easy")
            elif command == "medium_mode":
                self.set_mode("medium")
            elif command == "hard_mode":
                self.set_mode("hard")
                
        except Exception as e:
            self.logger.error(f"Error handling voice command: {e}")

    def showEvent(self, event):
        """Override showEvent to start voice control when window is shown"""
        super().showEvent(event)
        try:
            self.voice_controller.start_listening()
        except Exception as e:
            self.logger.error(f"Failed to start voice control: {e}")

    def closeEvent(self, event):
        """Override closeEvent to clean up voice control"""
        try:
            self.voice_controller.stop_listening()
        except Exception as e:
            self.logger.error(f"Error stopping voice control: {e}")
            
        # Call existing cleanup
        super().closeEvent(event)

    def set_mode(self, mode):
        """Set the difficulty mode."""
        self.logger.info(f"Setting mode to {mode}")
        self.current_mode = mode
        
        # Update button states
        self.easy_button.setChecked(mode == "easy")
        self.medium_button.setChecked(mode == "medium")
        self.hard_button.setChecked(mode == "hard")
        
        # Update mode indicator
        if mode == "easy":
            self.mode_indicator.setText("EASY MODE")
            self.mode_indicator.setStyleSheet("""
                font-size: 16px;
                font-weight: bold;
                color: white;
                background-color: #4CAF50;
                padding: 5px;
                border-radius: 5px;
                margin: 5px;
            """)
            # Load regular audio files
            audio_dir = "/Users/peterflaschner/code/Solo adventure/audio"
            self.audio_player.load_files(audio_dir)
            self.audio_player.is_looping = False
            self.audio_control.loop_button.setChecked(False)
            self.wait_time_slider.setValue(15)
            self.master_volume_slider.setValue(70)
        elif mode == "medium":
            self.mode_indicator.setText("MEDIUM MODE")
            self.mode_indicator.setStyleSheet("""
                font-size: 16px;
                font-weight: bold;
                color: white;
                background-color: #FFA500;
                padding: 5px;
                border-radius: 5px;
                margin: 5px;
            """)
            # Load regular audio files
            audio_dir = "/Users/peterflaschner/code/Solo adventure/audio"
            self.audio_player.load_files(audio_dir)
            self.audio_player.is_looping = False
            self.audio_control.loop_button.setChecked(False)
            self.wait_time_slider.setValue(7)
            self.master_volume_slider.setValue(80)
        else:  # hard mode
            self.mode_indicator.setText("HARD MODE")
            self.mode_indicator.setStyleSheet("""
                font-size: 16px;
                font-weight: bold;
                color: white;
                background-color: #ff4444;
                padding: 5px;
                border-radius: 5px;
                margin: 5px;
            """)
            # Load peak performer files and enable looping
            peak_dir = os.path.join("logs", "peak_performers")
            if os.path.exists(peak_dir):
                self.logger.info(f"Loading peak performer files from {peak_dir}")
                self.audio_player.load_files(peak_dir)
                self.audio_player.is_looping = True
                self.audio_control.loop_button.setChecked(True)
                self.wait_time_slider.setValue(4)
                self.master_volume_slider.setValue(100)
            else:
                self.logger.warning(f"Peak performers directory not found: {peak_dir}")
        
        # Apply volume change
        self._on_master_volume_changed(self.master_volume_slider.value())
        
        # Update file dropdown
        self._populate_file_dropdown()