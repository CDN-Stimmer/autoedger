from PySide6.QtCore import QObject, Signal, QUrl, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QAudioBuffer, QAudioFormat
import os
import random
import numpy as np
import soundfile as sf
import time
import threading
import asyncio

class QtAudioPlayer(QObject):
    playback_started = Signal(str)  # Emits filename
    playback_stopped = Signal()
    playback_error = Signal(str)    # Emits error message
    time_updated = Signal(float)    # Emits time remaining
    audio_data_ready = Signal(float, float)  # Emits (amplitude, frequency)
    hooray_cycle_complete = Signal()  # Emits when hooray cycle is complete
    
    # Internal signals for thread-safe player control
    _pause_player = Signal()
    _resume_player = Signal(int)  # Takes position
    _set_volume = Signal(float)
    _play_player = Signal()
    _start_analysis = Signal()  # New signal for starting analysis
    _stop_analysis = Signal()   # New signal for stopping analysis

    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        
        # Initialize audio system
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        # Initialize state
        self.file_list = []
        self.current_file = None
        self.is_looping = False
        self.audio_output.setVolume(1.0)
        self.current_audio_data = None
        self.sample_rate = 44100
        self.is_in_hooray_cycle = False
        self.wait_time = 5  # Default wait time
        self._hooray_thread = None
        
        # Create peak performers directory
        self.peak_performers_dir = os.path.join("logs", "peak_performers")
        os.makedirs(self.peak_performers_dir, exist_ok=True)
        
        # Set up timer for audio analysis
        self.analysis_timer = QTimer()
        self.analysis_timer.setInterval(50)  # Update every 50ms
        self.analysis_timer.timeout.connect(self._analyze_audio)
        
        # Connect signals
        self.player.errorOccurred.connect(self._handle_error)
        self.player.positionChanged.connect(self._handle_position_change)
        self.player.mediaStatusChanged.connect(self._handle_media_status_change)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        
        # Connect internal control signals
        self._pause_player.connect(self.player.pause)
        self._resume_player.connect(self.player.setPosition)
        self._set_volume.connect(self.audio_output.setVolume)
        self._play_player.connect(self.player.play)
        self._start_analysis.connect(self.analysis_timer.start)
        self._stop_analysis.connect(self.analysis_timer.stop)
        
        self._volume_lock = threading.Lock()
        
    def _analyze_audio(self):
        """Analyze current audio data and emit metrics."""
        try:
            # Check playback state and audio data availability
            if not self.player.isPlaying():
                self.logger.debug("Audio analysis skipped - player not playing")
                return
                
            if self.current_audio_data is None:
                self.logger.debug("Audio analysis skipped - no audio data available")
                return
                
            # Get current playback position in ms
            position = self.player.position()
            
            # Convert position to samples
            sample_position = int((position / 1000.0) * self.sample_rate)
            
            # Get a window of audio data
            window_size = 2048
            if sample_position + window_size > len(self.current_audio_data):
                self.logger.debug("Audio analysis skipped - window exceeds audio data length")
                return
                
            window = self.current_audio_data[sample_position:sample_position + window_size]
            
            # Calculate RMS amplitude
            amplitude = float(np.sqrt(np.mean(np.square(window))))
            
            # Calculate frequency using FFT
            fft = np.fft.fft(window)
            freqs = np.fft.fftfreq(len(window), 1/self.sample_rate)
            magnitude = np.abs(fft)
            
            # Find dominant frequency
            peak_idx = np.argmax(magnitude[:len(magnitude)//2])
            frequency = float(abs(freqs[peak_idx]))
            
            # Ensure amplitude is between 0 and 1
            amplitude = min(1.0, amplitude)
            
            # Store last known good values
            self.last_amplitude = amplitude
            self.last_frequency = frequency
            
            # Emit the audio data
            self.logger.debug(f"Emitting audio data - amplitude: {amplitude:.3f}, frequency: {frequency:.1f}Hz")
            self.audio_data_ready.emit(amplitude, frequency)
            
        except Exception as e:
            self.logger.error(f"Error analyzing audio: {e}")
            # Emit last known good values if we have them
            if hasattr(self, 'last_amplitude') and hasattr(self, 'last_frequency'):
                self.audio_data_ready.emit(self.last_amplitude, self.last_frequency)
            
    def _load_audio_data(self, file_path):
        """Load audio data for analysis."""
        try:
            import soundfile as sf
            import numpy as np
            
            # Load audio data
            self.logger.debug(f"Loading audio data from {file_path}")
            audio_data, sample_rate = sf.read(file_path)
            
            # Convert stereo to mono if needed
            if len(audio_data.shape) > 1:
                self.logger.debug("Converting stereo to mono")
                audio_data = np.mean(audio_data, axis=1)
            
            # Normalize audio data
            self.logger.debug("Normalizing audio data")
            audio_data = audio_data / np.max(np.abs(audio_data))
            
            # Store audio data and sample rate
            self.current_audio_data = audio_data
            self.sample_rate = sample_rate
            
            self.logger.debug(f"Audio data loaded successfully - length: {len(audio_data)}, sample rate: {sample_rate}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading audio data: {e}")
            self.current_audio_data = None
            return False
            
    def load_files(self, folder_path):
        """Load audio files (MP3 and WAV) from the specified folder."""
        try:
            if not os.path.exists(folder_path):
                self.logger.error(f"Folder not found: {folder_path}")
                return False
                
            self.file_list = []
            for file in os.listdir(folder_path):
                if file.lower().endswith(('.mp3', '.wav')):
                    full_path = os.path.join(folder_path, file)
                    self.file_list.append(full_path)
                    self.logger.debug(f"Added file: {file}")
            
            self.logger.info(f"Loaded {len(self.file_list)} audio files from {folder_path}")
            if len(self.file_list) == 0:
                self.logger.warning(f"No audio files found in {folder_path}")
            return len(self.file_list) > 0
            
        except Exception as e:
            self.logger.error(f"Error loading files from {folder_path}: {str(e)}")
            return False
            
    def play_random_file(self):
        """Play a random file from the loaded files."""
        if not self.file_list:
            self.logger.warning("No files available to play")
            return False
            
        try:
            # Store current volume
            current_volume = self.audio_output.volume()
            
            # Stop current playback and timer
            self.player.stop()
            self.analysis_timer.stop()
            
            # Select and play new file
            self.current_file = random.choice(self.file_list)
            
            # Load audio data for analysis
            if not self._load_audio_data(self.current_file):
                return False
                
            # Start playback
            self.player.setSource(QUrl.fromLocalFile(self.current_file))
            self.player.play()
            
            # Restore volume
            self.audio_output.setVolume(current_volume)
            
            # Start analysis timer
            self.analysis_timer.start()
            
            # Log and emit signals
            name = os.path.basename(self.current_file)
            self.logger.info(f"Playing file: {name}")
            self.playback_started.emit(name)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error playing file: {str(e)}")
            self.playback_error.emit(str(e))
            return False
            
    def stop_playback(self):
        """Stop the current playback."""
        try:
            # Stop analysis timer
            if self.analysis_timer.isActive():
                self.analysis_timer.stop()
            
            # Stop any active hooray cycle
            self.is_in_hooray_cycle = False
            if self._hooray_thread and self._hooray_thread.is_alive():
                self._hooray_thread.join(timeout=0.5)
            
            # Set current_file to None before stopping to prevent auto-play
            self.current_file = None
            self.player.stop()
            self.logger.info("Playback stopped")
            self.playback_stopped.emit()
            return True
        except Exception as e:
            self.logger.error(f"Error stopping playback: {str(e)}")
            return False
            
    def replay_file(self):
        """Replay the current file."""
        if not self.current_file:
            self.logger.warning("No file to replay")
            return False
            
        try:
            # Store current volume
            current_volume = self.audio_output.volume()
            
            # Stop current playback and timer
            self.player.stop()
            self.analysis_timer.stop()
            
            # Start playback
            self.player.setSource(QUrl.fromLocalFile(self.current_file))
            self.player.play()
            
            # Restore volume
            self.audio_output.setVolume(current_volume)
            
            # Start analysis timer
            self.analysis_timer.start()
            
            # Log and emit signals
            name = os.path.basename(self.current_file)
            self.logger.info(f"Replaying file: {name}")
            self.playback_started.emit(name)
            
            return True
        except Exception as e:
            self.logger.error(f"Error replaying file: {str(e)}")
            self.playback_error.emit(str(e))
            return False
            
    def toggle_loop(self):
        """Toggle looping for the current file."""
        self.is_looping = not self.is_looping
        self.logger.info(f"Looping {'enabled' if self.is_looping else 'disabled'}")
        return self.is_looping
        
    def set_volume(self, volume):
        """Set the volume level (0.0 to 1.0)."""
        with self._volume_lock:
            try:
                volume = max(0.0, min(1.0, volume))
                self.audio_output.setVolume(volume)
                self.logger.debug(f"Volume set to {volume}")
                return True
            except Exception as e:
                self.logger.error(f"Error setting volume: {str(e)}")
                return False
            
    def get_volume(self):
        """Get the current volume level."""
        with self._volume_lock:
            try:
                return self.audio_output.volume()
            except Exception as e:
                self.logger.error(f"Error getting volume: {str(e)}")
                return 0.0
            
    def get_current_file_name(self):
        """Get the name of the current file."""
        if not self.current_file:
            return None
        return os.path.basename(self.current_file)
        
    def _handle_error(self, error):
        """Handle player errors."""
        error_msg = f"Player error: {error}"
        self.logger.error(error_msg)
        
        # Stop analysis timer if it's running
        if self.analysis_timer.isActive():
            self.logger.debug("Stopping audio analysis timer due to error")
            self.analysis_timer.stop()
            
        # Reset audio data
        self.current_audio_data = None
        self.last_amplitude = 0.0
        self.last_frequency = 0.0
        
        # Emit error signal
        self.playback_error.emit(error_msg)
        
        # Stop playback
        self.player.stop()
        self.playback_stopped.emit()
        
    def _handle_position_change(self, position):
        """Handle playback position changes."""
        if self.player.duration() > 0:
            time_remaining = (self.player.duration() - position) / 1000.0
            self.time_updated.emit(time_remaining)
            
    def _handle_media_status_change(self, status):
        """Handle media status changes."""
        self.logger.debug(f"Media status changed to: {status}")
        
        if status == QMediaPlayer.LoadedMedia:
            self.logger.debug("Media loaded successfully")
            
        elif status == QMediaPlayer.LoadingMedia:
            self.logger.debug("Loading media...")
            
        elif status == QMediaPlayer.NoMedia:
            self.logger.debug("No media loaded")
            
        elif status == QMediaPlayer.EndOfMedia:
            self.logger.info("End of media reached")
            # Handle end of playback
            # Only auto-play next file if we didn't explicitly stop (current_file is not None)
            if self.current_file is not None:
                if self.is_looping:
                    # Immediately restart the same file from the beginning
                    self.logger.info("Looping enabled - replaying current file")
                    self.replay_file()
                else:
                    # Play a new random file
                    self.logger.info("Looping disabled - playing random file")
                    self.play_random_file()
                    
        elif status == QMediaPlayer.InvalidMedia:
            self.logger.error("Invalid media - cannot play file")
            self.playback_error.emit("Invalid media format")
            
    def fade_in_volume(self, steps=20, step_delay=0.5):
        """
        Fade in volume over specified steps with delay between each step.
        
        Args:
            steps (int): Number of steps to use for fade-in
            step_delay (float): Delay in seconds between steps
        """
        try:
            self.logger.info("Starting volume fade-in")
            for i in range(steps + 1):
                volume = i / steps
                self.set_volume(volume)
                time.sleep(step_delay)
            self.logger.info("Volume fade-in completed")
        except Exception as e:
            self.logger.error(f"Error during fade-in: {e}")
            # Ensure volume is restored even if fade-in fails
            self.set_volume(1.0)
            
    def start_hooray_cycle(self, wait_time=None):
        """Start the hooray cycle with optional wait time."""
        if self.is_in_hooray_cycle:
            self.logger.warning("Hooray cycle already in progress")
            return False
            
        if wait_time is not None:
            self.wait_time = wait_time
            
        # Start entire hooray cycle in a separate thread
        def run_cycle():
            try:
                self.is_in_hooray_cycle = True
                self._stop_analysis.emit()  # Stop analysis during cycle
                
                # Store current position and volume
                position = self.player.position()
                user_volume = self.audio_output.volume()
                self._pause_player.emit()
                
                # Wait for specified time
                time.sleep(self.wait_time)
                
                # Resume from stored position and play
                self._resume_player.emit(position)
                self._play_player.emit()
                
                # Start fade-in
                current_volume = 0.0
                self._set_volume.emit(current_volume)
                
                # 20 steps over 5 seconds = 0.25s per step
                step_size = user_volume / 20  # Scale step size to reach user's volume
                step_time = 0.25  # Time per step in seconds
                
                for i in range(20):
                    if not self.is_in_hooray_cycle:  # Check if cycle was cancelled
                        break
                    current_volume += step_size
                    self._set_volume.emit(min(current_volume, user_volume))
                    time.sleep(step_time)
                    
                # Ensure we end at user's volume
                self._set_volume.emit(user_volume)
                self.logger.info("Volume fade-in completed")
                
                # Restart analysis timer
                self._start_analysis.emit()
                
            except Exception as e:
                self.logger.error(f"Error in hooray cycle: {e}")
                # Ensure volume is restored even if fade-in fails
                self._set_volume.emit(user_volume)
                self._start_analysis.emit()  # Ensure timer restarts even on error
                
            finally:
                self.is_in_hooray_cycle = False
                self.hooray_cycle_complete.emit()
                
        # Start the cycle thread
        self._hooray_thread = threading.Thread(target=run_cycle, daemon=True)
        self._hooray_thread.start()
        
    def _on_state_changed(self, state):
        """Handle player state changes."""
        self.logger.debug(f"Player state changed to: {state}")
        
        if state == QMediaPlayer.PlaybackState.StoppedState:
            self.logger.debug("Stopping audio analysis timer")
            self.analysis_timer.stop()
            self.logger.debug("Emitting playback_stopped")
            # Emit the signal directly since it's not actually a coroutine
            self.playback_stopped.emit()
        elif state == QMediaPlayer.PlaybackState.PlayingState:
            self.analysis_timer.start()
            
    async def _emit_playback_stopped(self):
        """Helper to emit playback stopped signal asynchronously."""
        try:
            # Emit the signal directly since it's not actually a coroutine
            self.playback_stopped.emit()
        except Exception as e:
            self.logger.error(f"Error emitting playback stopped: {e}")
            
    def play_file(self, file_path):
        """Play a specific audio file."""
        if not os.path.exists(file_path):
            self.logger.error(f"File not found: {file_path}")
            return False
            
        try:
            # Store current volume
            current_volume = self.audio_output.volume()
            
            # Stop current playback and timer
            self.player.stop()
            self.analysis_timer.stop()
            
            # Set current file and load audio data
            self.current_file = file_path
            
            # Load audio data for analysis
            if not self._load_audio_data(self.current_file):
                return False
                
            # Start playback
            self.player.setSource(QUrl.fromLocalFile(file_path))
            self.player.play()
            
            # Restore volume
            self.audio_output.setVolume(current_volume)
            
            # Start analysis timer
            self.analysis_timer.start()
            
            # Log and emit signals
            name = os.path.basename(file_path)
            self.logger.info(f"Playing file: {name}")
            self.playback_started.emit(name)
            
            return True
        except Exception as e:
            self.logger.error(f"Error playing file {file_path}: {e}")
            self.playback_error.emit(str(e))
            return False

    def set_wait_time(self, value):
        """Set the wait time for hooray cycles."""
        self.wait_time = value
        self.logger.debug(f"Wait time set to {value} seconds")

    def save_peak_performer(self, prefix="hooray"):
        """Save the last 15 seconds of audio as a peak performer clip.
        
        Args:
            prefix (str): Prefix for the saved file name (e.g. 'hooray' or 'yes')
        """
        try:
            if not self.current_file or self.current_audio_data is None:
                self.logger.warning("No audio data available to save peak performer clip")
                return
                
            # Create peak performers directory if it doesn't exist
            os.makedirs(self.peak_performers_dir, exist_ok=True)
            
            # Calculate start sample based on current playback position
            current_pos = self.player.position() / 1000.0  # Convert ms to seconds
            sample_rate = self.sample_rate
            current_sample = int(current_pos * sample_rate)
            
            # Calculate start sample (15 seconds before current position)
            start_sample = max(0, current_sample - (15 * sample_rate))
            
            # Get the audio segment
            peak_segment = self.current_audio_data[start_sample:current_sample]
            
            # Generate filename with timestamp
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            original_name = os.path.splitext(os.path.basename(self.current_file))[0]
            output_filename = f"{prefix}-{original_name}-{timestamp}.wav"
            output_path = os.path.join(self.peak_performers_dir, output_filename)
            
            # Save the audio segment
            sf.write(output_path, peak_segment, self.sample_rate)
            self.logger.info(f"Saved peak performer clip: {output_filename}")
            
        except Exception as e:
            self.logger.error(f"Error saving peak performer clip: {e}") 