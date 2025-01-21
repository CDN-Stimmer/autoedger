import os
import random
import threading
from pygame import mixer
from mutagen.mp3 import MP3
import time

class AudioPlayer:
    def __init__(self, logger):
        self.logger = logger
        self.current_file = None
        self.file_list = []
        self.is_looping = False
        self.track_length = 0
        self.stop_thread_flag = False
        self.update_thread = None
        self.volume = 1.0
        self.visualization_manager = None
        self.thread_lock = threading.Lock()
        self.last_update_time = 0
        
        try:
            mixer.quit()  # Ensure clean state
            mixer.init(frequency=44100, size=-16, channels=2, buffer=32768)
            mixer.music.set_volume(self.volume)
            self.logger.info("Audio player initialized")
        except Exception as e:
            self.logger.error(f"Error initializing audio player: {str(e)}")

    def load_files(self, folder):
        """Load MP3 files from a specified folder."""
        try:
            self.file_list = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".mp3")]
            if not self.file_list:
                self.logger.warning("No MP3 files found in the selected folder.")
                return False
            self.logger.info(f"Loaded {len(self.file_list)} MP3 files.")
            return True
        except Exception as e:
            self.logger.error(f"Error loading files: {e}")
            return False

    def play_random_file(self, time_callback=None):
        """Play a random file from the file list."""
        if not self.file_list:
            self.logger.warning("No files available to play.")
            return False

        with self.thread_lock:
            try:
                self._stop_current_playback()
                
                # Select and play new file
                self.current_file = random.choice(self.file_list)
                name = os.path.basename(self.current_file)
                
                # Load and play the file
                mixer.music.load(self.current_file)
                mixer.music.play()
                mixer.music.set_volume(self.volume)
                
                # Get track length after successful load
                audio = MP3(self.current_file)
                self.track_length = int(audio.info.length)
                
                self.logger.info(f"Playing file: {name}")
                
                # Start update thread if callback provided
                if time_callback:
                    self._start_time_update_thread(time_callback)
                
                return True

            except Exception as e:
                self.logger.error(f"Error playing file: {str(e)}")
                self.current_file = None
                return False

    def _stop_current_playback(self):
        """Stop current playback and cleanup thread."""
        if mixer.music.get_busy():
            mixer.music.stop()
        
        self.stop_thread_flag = True
        if self.update_thread and self.update_thread.is_alive():
            try:
                self.update_thread.join(timeout=0.2)  # Shorter timeout to prevent UI hangs
            except Exception as e:
                self.logger.error(f"Error joining thread: {str(e)}")
            finally:
                self.update_thread = None

    def stop_playback(self):
        """Stop the current playback."""
        with self.thread_lock:  # Ensure thread-safe state changes
            try:
                self._stop_current_playback()
                self.current_file = None
                self.logger.info("Playback stopped")
                return True
            except Exception as e:
                self.logger.error(f"Error stopping playback: {str(e)}")
                return False

    def replay_file(self, time_callback=None):
        """Replay the current file."""
        if self.current_file:
            try:
                mixer.music.load(self.current_file)
                mixer.music.play()
                mixer.music.set_volume(self.volume)
                self.logger.info(f"Replaying file: {self.current_file}")
                
                # Notify visualization manager of file replay
                if self.visualization_manager:
                    self.visualization_manager.set_current_file(self.current_file)
                    
                if time_callback:
                    self._start_time_update_thread(time_callback)
                return True
            except Exception as e:
                self.logger.error(f"Error replaying file {self.current_file}: {e}")
                return False
        return False

    def toggle_loop(self):
        """Toggle looping for the current file."""
        self.is_looping = not self.is_looping
        self.logger.info(f"Looping toggled to {'ON' if self.is_looping else 'OFF'}.")
        return self.is_looping

    def get_current_file_name(self):
        """Get the name of the current file."""
        if not self.current_file:
            self.logger.debug("No current file")
            return None
        try:
            name = os.path.basename(self.current_file)
            self.logger.debug(f"Current filename: {name}")
            return name
        except Exception as e:
            self.logger.error(f"Error getting filename: {str(e)}")
            return None

    def set_volume(self, volume):
        """Set the volume level (0.0 to 1.0)."""
        self.volume = max(0.0, min(1.0, volume))
        mixer.music.set_volume(self.volume)

    def get_volume(self):
        """Get the current volume level."""
        return self.volume

    def fade_in_volume(self, steps=10, delay=0.5):
        """Fade in volume over specified steps with delay between each step."""
        for i in range(steps + 1):
            volume = i / steps
            self.set_volume(volume)
            threading.Event().wait(delay) 

    def set_visualization_manager(self, visualization_manager):
        """Set the visualization manager for audio analysis."""
        self.visualization_manager = visualization_manager
        if self.current_file:
            self.visualization_manager.set_current_file(self.current_file)
            
    def _start_time_update_thread(self, time_callback):
        """Start a thread to update the time remaining."""
        self.stop_thread_flag = False
        self.update_thread = threading.Thread(
            target=self._update_time_remaining,
            args=(time_callback,),
            daemon=True
        )
        self.update_thread.start()

    def _update_time_remaining(self, callback):
        """Update the time remaining in the current track."""
        update_interval = 0.25  # Reduced update frequency
        min_update_interval = 0.1  # Minimum time between updates
        
        while not self.stop_thread_flag:
            try:
                if not mixer.music.get_busy():
                    break
                    
                current_time = time.time()
                if current_time - self.last_update_time < min_update_interval:
                    time.sleep(0.01)  # Short sleep to prevent CPU spinning
                    continue
                
                current_pos = mixer.music.get_pos() / 1000.0
                if current_pos < 0:
                    break
                
                time_left = max(0, self.track_length - current_pos)
                if time_left <= 0:
                    break
                
                callback(time_left)
                self.last_update_time = current_time
                time.sleep(update_interval)
                
            except Exception as e:
                self.logger.error(f"Error updating time: {str(e)}")
                break

        # Handle end of playback
        if not self.stop_thread_flag:
            with self.thread_lock:
                if self.is_looping:
                    self.replay_file(callback)
                else:
                    self.play_random_file(callback)

            