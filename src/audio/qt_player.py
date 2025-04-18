import os
import logging
import random
from PySide6.QtCore import QObject, Signal, Slot, QUrl, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QAudioDevice, QMediaDevices
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
from mutagen import File as MutagenFile, MutagenError

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
    time_updated = Signal(int)  # Current position in milliseconds
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
        self.logger.info("Created QMediaPlayer instance")
        
        # Create default audio output
        self.audio_output = QAudioOutput()
        self.logger.info("Created QAudioOutput instance")
        
        # Log available audio devices
        devices = self.get_available_devices()
        self.logger.info(f"Available audio devices: {devices}")
        
        # Set audio output to player
        self.player.setAudioOutput(self.audio_output)
        self.logger.info("Set audio output to media player")
        
        # Connect signals
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.errorOccurred.connect(self._on_error)  # Add error handling
        
        # Set default volume to 100%
        self.audio_output.setVolume(1.0)
        self.logger.info(f"Initialized audio player with default device and 100% volume. Current device: {self.audio_output.device().description() if self.audio_output.device() else 'None'}")
        
        # Initialize additional properties
        self.current_file = None
        self.loop_enabled = False
        self.favorites = set()
        self.audio_files = []
        self.wait_time = 8  # Default wait time in seconds
        self._explicit_stop = False  # Flag to track explicit stop vs natural end
        
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
        """Get the sorted list of audio files."""
        # Return a copy of the sorted list to ensure consistency
        return sorted(self.audio_files)
    
    def get_sorted_file_list(self):
        """Get a consistently sorted list of audio files."""
        return sorted(self.audio_files)
    
    def _scan_audio_files(self):
        """Scan for audio files in the src/audio directory."""
        try:
            # Get the path to the script directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Define audio directory
            audio_dir = script_dir
            
            self.audio_files = []
            
            # Check audio directory
            if os.path.exists(audio_dir):
                for file in os.listdir(audio_dir):
                    if file.lower().endswith(('.mp3', '.wav')):
                        self.audio_files.append(os.path.join(audio_dir, file))
            
            self.logger.info(f"Found {len(self.audio_files)} audio files")
        except Exception as e:
            self.logger.error(f"Error scanning audio files: {e}")
    
    def load_files(self, directory=None):
        """
        Load audio files from a directory.
        
        Args:
            directory (str, optional): Directory to load files from. If None, uses default audio directory.
        
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
                # Otherwise, use the default audio directory
                script_dir = os.path.dirname(os.path.abspath(__file__))
                audio_dir = script_dir
                
                # Check audio directory
                if os.path.exists(audio_dir):
                    self.logger.info(f"Loading audio files from: {audio_dir}")
                    for file in os.listdir(audio_dir):
                        if file.lower().endswith(('.mp3', '.wav')):
                            self.audio_files.append(os.path.join(audio_dir, file))
            
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
        """Start playback of the current file."""
        if not self.current_file:
            self.logger.warning("No file loaded to play")
            return
            
        self.logger.info(f"Starting playback of {self.current_file}")
        self.logger.info(f"Current audio device: {self.audio_output.device().description() if self.audio_output.device() else 'None'}")
        self.logger.info(f"Current volume: {self.audio_output.volume()}")
        
        self.player.play()
        self._explicit_stop = False
    
    def pause(self):
        """Pause playback."""
        self.player.pause()
        self.logger.info("Playback paused")
    
    def stop_playback(self):
        """Stop playback."""
        self._explicit_stop = True  # Set flag before stopping
        self.player.stop()
        self.current_file = None  # Clear the current file
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
            
        Returns:
            bool: True if the file is in favorites, False otherwise
        """
        return file_path in self.favorites
    
    def get_favorites(self):
        """Get the list of favorite files."""
        return sorted(list(self.favorites))
    
    def set_position(self, position_ms):
        """
        Set the playback position.
        
        Args:
            position_ms (int): Position in milliseconds
        """
        self.player.setPosition(position_ms)
        self.logger.info(f"Set position to {position_ms}ms")
    
    def get_position(self):
        """Get the current playback position in milliseconds."""
        return self.player.position()
    
    def get_duration(self):
        """Get the duration of the current file in milliseconds."""
        return self.player.duration()
    
    def get_file_duration(self, file_path):
        """
        Get the duration of a specific audio file.
        
        Args:
            file_path (str): Path to the audio file
            
        Returns:
            float: Duration in seconds, or None if unable to determine
        """
        try:
            if file_path.lower().endswith('.mp3'):
                audio = MP3(file_path)
                return audio.info.length
            elif file_path.lower().endswith('.wav'):
                audio = WAVE(file_path)
                return audio.info.length
            else:
                # Try using mutagen's File class as a fallback
                audio = MutagenFile(file_path)
                if audio is not None:
                    return audio.info.length
                return None
        except MutagenError as e:
            self.logger.warning(f"Could not read audio info for {file_path}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting duration for {file_path}: {e}")
            return None
    
    def set_volume(self, volume):
        """
        Set the playback volume.
        
        Args:
            volume (float): Volume level from 0.0 to 1.0
        """
        # Ensure volume is within valid range
        volume = max(0.0, min(1.0, volume))
        self.audio_output.setVolume(volume)
        self.volume_changed.emit(volume)
        self.logger.info(f"Set volume to {volume}")
    
    def get_volume(self):
        """Get the current volume level (0.0 to 1.0)."""
        return self.audio_output.volume()
    
    def is_playing(self):
        """Check if audio is currently playing."""
        return self.player.playbackState() == QMediaPlayer.PlayingState
    
    def is_paused(self):
        """Check if audio is currently paused."""
        return self.player.playbackState() == QMediaPlayer.PausedState
    
    def is_looping(self):
        """Check if loop mode is enabled."""
        return self.loop_enabled
    
    def get_current_file(self):
        """Get the path of the currently loaded file."""
        return self.current_file
    
    def _update_time_and_audio(self):
        """Update time and generate dummy audio data."""
        if self.is_playing():
            # Emit current position
            position = self.get_position()
            self.time_updated.emit(position)
            
            # Generate dummy audio data (replace with real audio data if needed)
            dummy_data = [random.random() for _ in range(128)]
            self.audio_data_ready.emit(dummy_data)
    
    @Slot(int)
    def _on_position_changed(self, position_ms):
        """Handle position change events."""
        self.playback_position_changed.emit(position_ms)
        self.logger.debug(f"Position changed to {position_ms}ms")
    
    @Slot(int)
    def _on_duration_changed(self, duration_ms):
        """Handle duration change events."""
        self.playback_duration_changed.emit(duration_ms)
        self.logger.debug(f"Duration changed to {duration_ms}ms")
    
    @Slot(QMediaPlayer.PlaybackState)
    def _on_state_changed(self, state):
        """Handle playback state change events."""
        if state == QMediaPlayer.PlayingState:
            self.playback_started.emit()
            self.logger.info("Playback started")
        elif state == QMediaPlayer.PausedState:
            self.playback_paused.emit()
            self.logger.info("Playback paused")
        elif state == QMediaPlayer.StoppedState:
            self.playback_stopped.emit()
            self.logger.info("Playback stopped")
            
            # Handle end of playback
            if not self._explicit_stop:  # Only handle if not explicitly stopped
                if self.loop_enabled and self.current_file:
                    # Restart the same file if loop is enabled
                    self.logger.info("Loop enabled, restarting playback")
                    self.play()
                else:
                    # Play next file if available
                    self.logger.info("End of file reached, playing next")
                    self.play_next()
    
    def play_file(self, file_path):
        """
        Load and play a specific audio file.
        
        Args:
            file_path (str): Path to the audio file
            
        Returns:
            bool: True if successful, False otherwise
        """
        if self.load_file(file_path):
            self.play()
            return True
        return False
    
    def set_wait_time(self, seconds):
        """
        Set the wait time between files.
        
        Args:
            seconds (int): Wait time in seconds
        """
        if seconds >= 0:
            self.wait_time = seconds
            self.logger.info(f"Set wait time to {seconds} seconds")
    
    def start_hooray_cycle(self, wait_time=None):
        """
        Start the hooray cycle with gradually increasing volume.
        
        Args:
            wait_time (int, optional): Wait time in seconds before starting
        """
        if wait_time is not None:
            self.wait_time = wait_time
        
        # Start with minimum volume
        self.set_volume(0.1)
        
        # Schedule the first volume increase
        QTimer.singleShot(self.wait_time * 1000, self._hooray_increase_volume)
    
    def _hooray_increase_volume(self):
        """Start the gradual volume increase."""
        if not self.is_playing():
            return
        
        # Create a timer for volume steps
        self.volume_timer = QTimer(self)
        self.volume_timer.setInterval(100)  # 100ms between steps
        self.volume_timer.timeout.connect(self._hooray_volume_step)
        self.volume_timer.start()
    
    def _hooray_volume_step(self):
        """Increase volume by one step."""
        current_volume = self.get_volume()
        if current_volume >= 1.0:
            self.volume_timer.stop()
            return
        
        new_volume = min(1.0, current_volume + 0.01)
        self.set_volume(new_volume)
    
    def play_next(self):
        """
        Play the next file in the list.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.audio_files:
            self.logger.warning("No audio files available")
            return False
        
        if not self.current_file:
            # If no file is currently playing, play the first one
            next_file = self.audio_files[0]
        else:
            # Find the current file in the list
            try:
                current_index = self.audio_files.index(self.current_file)
                # Get the next file (wrap around to beginning if at end)
                next_index = (current_index + 1) % len(self.audio_files)
                next_file = self.audio_files[next_index]
            except ValueError:
                # Current file not in list, start from beginning
                next_file = self.audio_files[0]
        
        # Load and play the next file
        if self.load_file(next_file):
            self.play()
            return True
        
        return False
    
    def play_previous(self):
        """
        Play the previous file in the list.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.audio_files:
            self.logger.warning("No audio files available")
            return False
        
        if not self.current_file:
            # If no file is currently playing, play the last one
            prev_file = self.audio_files[-1]
        else:
            # Find the current file in the list
            try:
                current_index = self.audio_files.index(self.current_file)
                # Get the previous file (wrap around to end if at beginning)
                prev_index = (current_index - 1) % len(self.audio_files)
                prev_file = self.audio_files[prev_index]
            except ValueError:
                # Current file not in list, start from end
                prev_file = self.audio_files[-1]
        
        # Load and play the previous file
        if self.load_file(prev_file):
            self.play()
            return True
        
        return False
    
    def get_available_devices(self):
        """
        Get a list of available audio output devices.
        
        Returns:
            list: List of dictionaries containing device information
        """
        devices = []
        for device in QMediaDevices.audioOutputs():
            device_info = {
                'id': device.id().data().decode(),
                'description': device.description(),
                'is_default': device.isDefault(),
                'preferred_format': {
                    'sample_rate': device.preferredFormat().sampleRate(),
                    'channel_count': device.preferredFormat().channelCount(),
                    'sample_format': str(device.preferredFormat().sampleFormat())
                }
            }
            devices.append(device_info)
        return devices
    
    def set_output_device(self, device_id):
        """
        Set the audio output device.
        
        Args:
            device_id (str): Device ID to set as output
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Convert device_id to bytes if it's a string
            if isinstance(device_id, str):
                device_id = device_id.encode()
            
            # Find the device with matching ID
            for device in QMediaDevices.audioOutputs():
                if device.id().data() == device_id:
                    # Create new audio output with selected device
                    new_output = QAudioOutput(device)
                    
                    # Store current volume
                    current_volume = self.audio_output.volume()
                    
                    # Set new audio output
                    self.player.setAudioOutput(new_output)
                    self.audio_output = new_output
                    
                    # Restore volume
                    self.audio_output.setVolume(current_volume)
                    
                    self.logger.info(f"Set audio output device to: {device.description()}")
                    return True
            
            self.logger.warning(f"Audio device with ID {device_id} not found")
            return False
        except Exception as e:
            self.logger.error(f"Error setting audio output device: {e}")
            return False
    
    def get_current_device(self):
        """
        Get information about the current audio output device.
        
        Returns:
            dict: Dictionary containing device information, or None if no device
        """
        device = self.audio_output.device()
        if device:
            return {
                'id': device.id().data().decode(),
                'description': device.description(),
                'is_default': device.isDefault(),
                'preferred_format': {
                    'sample_rate': device.preferredFormat().sampleRate(),
                    'channel_count': device.preferredFormat().channelCount(),
                    'sample_format': str(device.preferredFormat().sampleFormat())
                }
            }
        return None
    
    def _on_error(self, error, error_string):
        """Handle media player errors."""
        self.logger.error(f"Media player error {error}: {error_string}") 