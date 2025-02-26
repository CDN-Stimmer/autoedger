import os
import logging
import random
from PySide6.QtCore import QObject, Signal, Slot, QUrl, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

class QtAudioPlayer(QObject):
    """
    Audio player implementation using Qt's QMediaPlayer.
    """
    playback_started = Signal()
    playback_paused = Signal()
    playback_stopped = Signal()
    playback_position_changed = Signal(int)  # Position in milliseconds
    playback_duration_changed = Signal(int)  # Duration in milliseconds
    volume_changed = Signal(float)  # Volume level (0.0 to 1.0)
    time_updated = Signal(int, int)  # Current position and duration in milliseconds
    audio_data_ready = Signal(list)  # Audio data for visualization
    favorites_changed = Signal()  # Signal emitted when favorites list changes
    
    def __init__(self, logger=None):
        """
        Initialize the audio player.
        
        Args:
            logger (logging.Logger, optional): Logger instance
        """
        super().__init__()
        self.logger = logger or logging.getLogger(__name__)
        
        # Create media player and audio output
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        # Connect signals
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        
        # Set default volume
        self.audio_output.setVolume(0.5)
        
        # Initialize additional properties
        self.current_file = None
        self.loop_enabled = False
        self.favorites = set()
        self.audio_files = []
        self.wait_time = 5  # Default wait time in seconds
        
        # Create timer for updating time and generating dummy audio data
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(100)  # 100ms update interval
        self.update_timer.timeout.connect(self._update_time_and_audio)
        self.update_timer.start()
        
        # Scan for audio files
        self._scan_audio_files()
        
        self.logger.info("Qt audio player initialized")
    
    @property
    def file_list(self):
        """Get the list of audio files (alias for audio_files)."""
        return self.audio_files
    
    def _scan_audio_files(self):
        """Scan for audio files in the data directory and src/audio directory."""
        try:
            # Get the path to the script directory
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # Define both audio directories
            data_audio_dir = os.path.join(script_dir, "data", "audio")
            src_audio_dir = os.path.join(script_dir, "audio")
            
            self.audio_files = []
            
            # Check data/audio directory
            if os.path.exists(data_audio_dir):
                for file in os.listdir(data_audio_dir):
                    if file.lower().endswith(('.mp3', '.wav')):
                        self.audio_files.append(os.path.join(data_audio_dir, file))
            
            # Also check src/audio directory
            if os.path.exists(src_audio_dir):
                for file in os.listdir(src_audio_dir):
                    if file.lower().endswith(('.mp3', '.wav')):
                        self.audio_files.append(os.path.join(src_audio_dir, file))
            
            self.logger.info(f"Found {len(self.audio_files)} audio files")
        except Exception as e:
            self.logger.error(f"Error scanning audio files: {e}")
    
    def load_files(self, directory=None):
        """
        Load audio files from a directory.
        
        Args:
            directory (str, optional): Directory to load files from. If None, uses default audio directories.
        
        Returns:
            list: List of loaded audio file paths
        """
        try:
            self.audio_files = []
            
            if directory is not None:
                # If a specific directory is provided, only use that one
                self.logger.info(f"Loading audio files from: {directory}")
                
                if not os.path.exists(directory):
                    self.logger.warning(f"Directory not found: {directory}")
                    return []
                
                for file in os.listdir(directory):
                    if file.lower().endswith(('.mp3', '.wav')):
                        self.audio_files.append(os.path.join(directory, file))
            else:
                # Otherwise, use both default directories
                script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                data_audio_dir = os.path.join(script_dir, "data", "audio")
                src_audio_dir = os.path.join(script_dir, "audio")
                
                # Check data/audio directory
                if os.path.exists(data_audio_dir):
                    self.logger.info(f"Loading audio files from: {data_audio_dir}")
                    for file in os.listdir(data_audio_dir):
                        if file.lower().endswith(('.mp3', '.wav')):
                            self.audio_files.append(os.path.join(data_audio_dir, file))
                
                # Also check src/audio directory
                if os.path.exists(src_audio_dir):
                    self.logger.info(f"Loading audio files from: {src_audio_dir}")
                    for file in os.listdir(src_audio_dir):
                        if file.lower().endswith(('.mp3', '.wav')):
                            self.audio_files.append(os.path.join(src_audio_dir, file))
            
            self.logger.info(f"Loaded {len(self.audio_files)} audio files")
            return self.audio_files
        except Exception as e:
            self.logger.error(f"Error loading audio files: {e}")
            return []
    
    def load_file(self, file_path):
        """
        Load an audio file for playback.
        
        Args:
            file_path (str): Path to the audio file
        """
        if not os.path.exists(file_path):
            self.logger.error(f"File not found: {file_path}")
            return False
        
        url = QUrl.fromLocalFile(file_path)
        self.player.setSource(url)
        self.current_file = file_path
        self.logger.info(f"Loaded audio file: {file_path}")
        return True
    
    def play(self):
        """Start or resume playback."""
        self.player.play()
        self.logger.info("Playback started")
    
    def pause(self):
        """Pause playback."""
        self.player.pause()
        self.logger.info("Playback paused")
    
    def stop_playback(self):
        """Stop playback."""
        self.player.stop()
        self.logger.info("Playback stopped")
    
    def play_random_file(self):
        """Play a random audio file from the available files."""
        if not self.audio_files:
            self.logger.warning("No audio files available")
            return
        
        random_file = random.choice(self.audio_files)
        if self.load_file(random_file):
            self.play()
    
    def toggle_loop(self, enabled=None):
        """
        Toggle loop mode.
        
        Args:
            enabled (bool, optional): If provided, set loop mode to this value
        """
        if enabled is not None:
            self.loop_enabled = enabled
        else:
            self.loop_enabled = not self.loop_enabled
        
        self.logger.info(f"Loop mode {'enabled' if self.loop_enabled else 'disabled'}")
    
    def add_to_favorites(self):
        """
        Add current file to favorites.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if self.current_file:
            self.favorites.add(self.current_file)
            self.favorites_changed.emit()
            self.logger.info(f"Added to favorites: {os.path.basename(self.current_file)}")
            return True
        return False
    
    def remove_from_favorites(self):
        """
        Remove current file from favorites.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if self.current_file and self.current_file in self.favorites:
            self.favorites.remove(self.current_file)
            self.favorites_changed.emit()
            self.logger.info(f"Removed from favorites: {os.path.basename(self.current_file)}")
            return True
        return False
    
    def is_favorite(self, file_path):
        """
        Check if a file is in favorites.
        
        Args:
            file_path (str): Path to the audio file
        """
        return file_path in self.favorites
    
    def get_favorites(self):
        """Get the list of favorite files."""
        return list(self.favorites)
    
    def set_position(self, position_ms):
        """
        Set the playback position.
        
        Args:
            position_ms (int): Position in milliseconds
        """
        self.player.setPosition(position_ms)
        self.logger.debug(f"Set position to {position_ms} ms")
    
    def get_position(self):
        """Get the current playback position in milliseconds."""
        return self.player.position()
    
    def get_duration(self):
        """Get the duration of the current media in milliseconds."""
        return self.player.duration()
    
    def set_volume(self, volume):
        """
        Set the playback volume.
        
        Args:
            volume (float): Volume level from 0.0 (mute) to 1.0 (maximum)
        """
        # Ensure volume is within valid range
        volume = max(0.0, min(1.0, volume))
        self.audio_output.setVolume(volume)
        self.volume_changed.emit(volume)
        self.logger.debug(f"Set volume to {volume}")
    
    def get_volume(self):
        """Get the current volume level (0.0 to 1.0)."""
        return self.audio_output.volume()
    
    def is_playing(self):
        """Check if audio is currently playing."""
        return self.player.playbackState() == QMediaPlayer.PlayingState
    
    def is_paused(self):
        """Check if audio is currently paused."""
        return self.player.playbackState() == QMediaPlayer.PausedState
    
    def get_current_file(self):
        """Get the path of the currently loaded file."""
        return self.current_file
    
    def _update_time_and_audio(self):
        """Update time and generate dummy audio data for visualization."""
        position = self.player.position()
        duration = self.player.duration()
        
        # Emit time update signal
        self.time_updated.emit(position, duration)
        
        # Generate dummy audio data for visualization (random values between 0 and 1)
        if self.is_playing():
            audio_data = [random.random() for _ in range(64)]
            self.audio_data_ready.emit(audio_data)
    
    @Slot(int)
    def _on_position_changed(self, position):
        """Handle position change events."""
        self.playback_position_changed.emit(position)
    
    @Slot(int)
    def _on_duration_changed(self, duration):
        """Handle duration change events."""
        self.playback_duration_changed.emit(duration)
    
    @Slot(QMediaPlayer.PlaybackState)
    def _on_state_changed(self, state):
        """Handle playback state change events."""
        if state == QMediaPlayer.PlayingState:
            self.playback_started.emit()
        elif state == QMediaPlayer.PausedState:
            self.playback_paused.emit()
        elif state == QMediaPlayer.StoppedState:
            self.playback_stopped.emit()
            
            # If loop is enabled and we have a current file, restart playback
            if self.loop_enabled and self.current_file:
                self.load_file(self.current_file)
                self.play()
    
    # Add missing methods needed by AudioControlWidget
    def play_file(self, file_path):
        """
        Load and play an audio file.
        
        Args:
            file_path (str): Path to the audio file
        """
        try:
            if self.load_file(file_path):
                self.play()
                return True
            return False
        except Exception as e:
            # Handle the error properly instead of letting it propagate
            self.logger.error(f"Error playing file {file_path}: {str(e)}")
            return False
    
    def set_wait_time(self, seconds):
        """
        Set wait time for hooray cycle.
        
        Args:
            seconds (int): Wait time in seconds
        """
        self.wait_time = seconds
        self.logger.debug(f"Set wait time to {seconds} seconds")
    
    def start_hooray_cycle(self, wait_time=None):
        """
        Start the hooray cycle (drop volume, wait, then gradually increase).
        
        Args:
            wait_time (int, optional): Wait time in seconds
        """
        if wait_time is not None:
            self.wait_time = wait_time
        
        # Store current volume
        self.pre_hooray_volume = self.get_volume()
        
        # Set volume to 0
        self.set_volume(0.0)
        
        # Schedule volume increase after wait time
        QTimer.singleShot(self.wait_time * 1000, self._hooray_increase_volume)
        
        self.logger.info(f"Started hooray cycle with wait time {self.wait_time}s")
    
    def _hooray_increase_volume(self):
        """Gradually increase volume after hooray wait time."""
        # Create a timer to gradually increase volume
        self.hooray_timer = QTimer(self)
        self.hooray_timer.setInterval(100)  # 100ms interval
        self.hooray_timer.timeout.connect(self._hooray_volume_step)
        self.hooray_volume_target = self.pre_hooray_volume
        self.hooray_volume_current = 0.0
        self.hooray_timer.start()
        
        self.logger.debug(f"Starting volume increase to {self.hooray_volume_target}")
    
    def _hooray_volume_step(self):
        """Increase volume by one step during hooray cycle."""
        # Increase by 0.02 each step (takes about 2.5 seconds to reach full volume)
        self.hooray_volume_current = min(self.hooray_volume_target, self.hooray_volume_current + 0.02)
        self.set_volume(self.hooray_volume_current)
        
        # Stop timer when target is reached
        if self.hooray_volume_current >= self.hooray_volume_target:
            self.hooray_timer.stop()
            self.logger.debug("Hooray volume increase complete") 