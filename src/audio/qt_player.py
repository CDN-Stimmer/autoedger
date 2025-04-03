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
        self.wait_time = 5  # Default wait time in seconds
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
        return sorted(self.audio_files)
    
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
        """Get the duration of the current file in SECONDS using mutagen."""
        if self.current_file:
            try:
                audio = MutagenFile(self.current_file)
                if audio and audio.info:
                    self.logger.debug(f"Mutagen duration for {self.current_file}: {audio.info.length:.2f}s")
                    return audio.info.length # Returns duration in seconds
                else:
                     self.logger.warning(f"Mutagen could not read info for: {self.current_file}")
            except MutagenError as e:
                self.logger.error(f"Mutagen error reading duration for {self.current_file}: {e}")
            except Exception as e:
                 self.logger.error(f"Unexpected error getting duration for {self.current_file} with mutagen: {e}")
        # Fallback or if no file loaded
        # QMediaPlayer duration can be unreliable, especially at start
        qt_duration_ms = self.player.duration()
        if qt_duration_ms > 0:
            self.logger.warning(f"Falling back to QMediaPlayer duration: {qt_duration_ms} ms")
            return qt_duration_ms / 1000.0 # Convert ms to seconds
        return 0.0 # Default to 0 seconds if unavailable
    
    def get_file_duration(self, file_path):
        """Get the duration of a specific file in SECONDS using mutagen, with fallback."""
        if not os.path.exists(file_path):
            self.logger.error(f"File not found for duration check: {file_path}")
            return 0.0
        
        mutagen_duration = 0.0
        try:
            # Try specific format handlers first
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext == '.mp3':
                audio = MP3(file_path)
            elif file_ext == '.wav':
                audio = WAVE(file_path)
            else:
                # Fall back to generic MutagenFile for other formats
                audio = MutagenFile(file_path)
            
            if audio and audio.info:
                mutagen_duration = audio.info.length # Returns duration in seconds
                self.logger.debug(f"Mutagen duration for {file_path}: {mutagen_duration:.2f}s")
                return mutagen_duration
            else:
                self.logger.warning(f"Mutagen could not read info for: {file_path}")
        except MutagenError as e:
            self.logger.warning(f"Mutagen failed for {file_path}. Attempting QMediaPlayer fallback.")
        except Exception as e:
            self.logger.error(f"Unexpected error getting duration for {file_path} with mutagen: {e}")
        
        # --- Fallback Logic --- 
        # If it's the currently loaded file, use the current player
        if self.current_file == file_path:
            qt_duration_ms = self.player.duration()
            if qt_duration_ms > 0:
                self.logger.warning(f"Using current QMediaPlayer duration as fallback: {qt_duration_ms} ms")
                return qt_duration_ms / 1000.0
        
        # Last resort: Create a temporary player and wait for duration
        self.logger.warning("Creating temporary QMediaPlayer for duration check...")
        temp_player = QMediaPlayer()
        temp_output = QAudioOutput()  # Create a temporary audio output
        temp_player.setAudioOutput(temp_output)  # Set the audio output
        
        try:
            temp_player.setSource(QUrl.fromLocalFile(file_path))
            # Wait up to 2 seconds for duration to be available
            for _ in range(20):  # 20 * 100ms = 2 seconds
                qt_duration_ms = temp_player.duration()
                if qt_duration_ms > 0:
                    self.logger.debug(f"Temporary player reported duration: {qt_duration_ms} ms")
                    return qt_duration_ms / 1000.0
                QTimer.singleShot(100, lambda: None)  # Wait 100ms
            
            self.logger.warning(f"Could not get duration for {file_path} after timeout")
            return 0.0
        except Exception as e:
            self.logger.error(f"Error during temporary QMediaPlayer duration check: {e}")
            return 0.0
        finally:
            temp_output.setVolume(0)  # Mute before cleanup
            temp_player.stop()  # Stop playback
            temp_player.setSource(QUrl())  # Clear source
            temp_output = None  # Remove audio output
            temp_player = None  # Allow player to be cleaned up
    
    def set_volume(self, volume):
        """
        Set the playback volume.
        
        Args:
            volume (float): Volume level from 0.0 (mute) to 1.0 (maximum)
        """
        # Ensure volume is within valid range
        volume = max(0.0, min(1.0, volume))
        self.logger.info(f"Setting volume to {volume}")
        self.logger.info(f"Current device: {self.audio_output.device().description() if self.audio_output.device() else 'None'}")
        self.audio_output.setVolume(volume)
        self.volume_changed.emit(volume)
        self.logger.debug(f"Volume set to {volume}")
    
    def get_volume(self):
        """Get the current volume level (0.0 to 1.0)."""
        return self.audio_output.volume()
    
    def is_playing(self):
        """Check if audio is currently playing."""
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
    
    def is_paused(self):
        """Check if audio is currently paused."""
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PausedState
    
    def is_looping(self):
        """Check if loop mode is enabled."""
        return self.loop_enabled
    
    def get_current_file(self):
        """Get the currently loaded file path."""
        return self.current_file
    
    def _update_time_and_audio(self):
        """Update time and generate dummy audio data for visualization."""
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState or \
           self.player.playbackState() == QMediaPlayer.PlaybackState.PausedState:
            
            position_ms = self.player.position() # Current position from player
            # duration_sec = self.get_duration() # Get accurate duration using mutagen (if needed)
            
            # Emit only position update signal
            self.time_updated.emit(position_ms)
            
            # Generate dummy audio data for visualization (random values between 0 and 1)
            if self.is_playing():
                audio_data = [random.random() for _ in range(64)] # Keep visualization simple for now
                self.audio_data_ready.emit(audio_data)
        # else: # Optional: If stopped, maybe emit 0 position?
            # self.time_updated.emit(0) 
    
    @Slot(int)
    def _on_position_changed(self, position_ms):
        """Handle position change events from QMediaPlayer (in ms)."""
        # This signal might be less frequent/reliable than timer, keep timer for UI updates
        self.logger.debug(f"QMediaPlayer positionChanged signal: {position_ms} ms")
        # We primarily rely on the timer (_update_time_and_audio) for UI updates
        # self.playback_position_changed.emit(position_ms) # Can re-enable if needed
    
    @Slot(int)
    def _on_duration_changed(self, duration_ms):
        """Handle duration change events from QMediaPlayer (in ms)."""
        # This can be unreliable, especially for VBR or at the start.
        self.logger.debug(f"QMediaPlayer durationChanged signal: {duration_ms} ms")
        # We use mutagen for reliable duration, so we might ignore this signal
        # self.playback_duration_changed.emit(duration_ms) # Can re-enable if needed
    
    @Slot(QMediaPlayer.PlaybackState)
    def _on_state_changed(self, state):
        """Handle playback state change events."""
        if state == QMediaPlayer.PlayingState:
            self.playback_started.emit()
            self._explicit_stop = False  # Reset flag when playback starts
        elif state == QMediaPlayer.PausedState:
            self.playback_paused.emit()
        elif state == QMediaPlayer.StoppedState:
            self.playback_stopped.emit()
            
            # Only handle automatic progression if it's not an explicit stop
            if not self._explicit_stop and self.current_file:
                # If loop is enabled and we have a current file, restart playback
                if self.loop_enabled:
                    self.load_file(self.current_file)
                    self.play()
                # If not looping and we have a current file, play the next track
                else:
                    # Find the current file in the list
                    try:
                        current_index = self.file_list.index(self.current_file)
                        # Play next file (wrap around to beginning if at end)
                        next_index = (current_index + 1) % len(self.file_list)
                        self.load_file(self.file_list[next_index])
                        self.play()
                    except ValueError:
                        # If current file not found in list, play first file
                        if self.file_list:
                            self.load_file(self.file_list[0])
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
    
    def play_previous(self):
        """Play the previous audio file in the list."""
        if not self.file_list:
            self.logger.warning("No audio files available to play previous")
            return

        current_index = -1
        if self.current_file:
            try:
                current_index = self.file_list.index(self.current_file)
            except ValueError:
                self.logger.warning("Current file not found in list, cannot determine previous.")
                current_index = 0 # Default to playing file before the first if current not found
        
        if current_index != -1:
            prev_index = (current_index - 1 + len(self.file_list)) % len(self.file_list) # Wrap around backward
            self.logger.info(f"Playing previous file (index {prev_index}): {self.file_list[prev_index]}")
            self.play_file(self.file_list[prev_index])
        else: # No current file, play the last file
             self.logger.info("No current file, playing last file in list.")
             self.play_file(self.file_list[-1])

    def play_next(self):
        """Play the next audio file in the list."""
        if not self.file_list:
            self.logger.warning("No audio files available to play next")
            return

        current_index = -1
        if self.current_file:
            try:
                current_index = self.file_list.index(self.current_file)
            except ValueError:
                self.logger.warning("Current file not found in list, cannot determine next.")
                # Fall through to play the first file
        
        if current_index != -1:
            next_index = (current_index + 1) % len(self.file_list) # Wrap around forward
            self.logger.info(f"Playing next file (index {next_index}): {self.file_list[next_index]}")
            self.play_file(self.file_list[next_index])
        else: # No current file, play the first file
             self.logger.info("No current file, playing first file in list.")
             self.play_file(self.file_list[0]) 
    
    def get_available_devices(self):
        """Get list of available audio output devices."""
        devices = []
        
        try:
            # Get all output devices from Qt
            for device in QMediaDevices.audioOutputs():
                devices.append({
                    'name': device.description(),
                    'id': device.id(),
                    'is_default': device.isDefault()
                })
                self.logger.debug(f"Found audio device: {device.description()} (ID: {device.id()})")
            
            if not devices:
                # Add system default if no devices found
                devices.append({
                    'name': 'System Default',
                    'id': 'default',
                    'is_default': True
                })
                
            return devices
        except Exception as e:
            self.logger.error(f"Error getting audio devices: {e}")
            # Return default device as fallback
            return [{
                'name': 'System Default',
                'id': 'default',
                'is_default': True
            }]
    
    def set_output_device(self, device_id):
        """Set the audio output device by ID."""
        try:
            # Find the device with matching ID
            from PySide6.QtMultimedia import QMediaDevices
            for device in QMediaDevices.audioOutputs():
                if device.id() == device_id:
                    # Create new audio output with selected device
                    new_output = QAudioOutput(device)
                    new_output.setVolume(self.audio_output.volume())  # Preserve volume
                    
                    # Store old position if playing
                    old_position = self.player.position() if self.player.isPlaying() else 0
                    was_playing = self.player.isPlaying()
                    
                    # Set new audio output
                    self.player.setAudioOutput(new_output)
                    self.audio_output = new_output
                    
                    # Restore playback state
                    if was_playing:
                        self.player.setPosition(old_position)
                        self.player.play()
                    
                    self.logger.info(f"Successfully set audio device to: {device.description()}")
                    return True
            
            self.logger.warning(f"Could not find audio device with ID: {device_id}")
            return False
            
        except Exception as e:
            self.logger.error(f"Error setting audio device: {e}")
            return False
    
    def get_current_device(self):
        """Get the current audio output device info."""
        current_device = self.audio_output.device()
        if current_device:
            return {
                'name': current_device.description(),
                'id': current_device.id(),
                'is_default': current_device.isDefault()
            }
        else:
            return {
                'name': 'System Default',
                'id': 'default',
                'is_default': True
            }
    
    def _on_error(self, error, error_string):
        """Handle media player errors."""
        self.logger.error(f"Media player error: {error} - {error_string}")
    
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