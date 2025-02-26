import os
import logging
import threading
import time
import json
import pyaudio
from vosk import Model, KaldiRecognizer
from PySide6.QtCore import QObject, Signal

class VoiceController(QObject):
    """
    Voice controller class that handles voice commands using Vosk.
    This is a simplified implementation that can be expanded with actual voice recognition.
    """
    command_recognized = Signal(str)
    
    def __init__(self, model_path, logger=None):
        """
        Initialize the voice controller with the given model path.
        
        Args:
            model_path (str): Path to the Vosk model directory
            logger (logging.Logger, optional): Logger instance
        """
        super().__init__()
        self.model_path = model_path
        self.logger = logger or logging.getLogger(__name__)
        self.listening = False
        self.thread = None
        
        # Check if model path exists
        if not os.path.exists(model_path):
            self.logger.error(f"Model path does not exist: {model_path}")
            self.model = None
            return
            
        try:
            # Initialize Vosk model
            self.logger.info(f"Loading Vosk model from {model_path}")
            self.model = Model(model_path)
            self.logger.info("Vosk model loaded successfully")
            
            # Initialize PyAudio
            self.audio = pyaudio.PyAudio()
            
            # Define command keywords - these should match what's handled in MainWindow._handle_voice_command
            self.commands = {
                "hooray": self._handle_hooray,
                "edge": self._handle_hooray,  # Alias for hooray
                "now": self._handle_hooray,   # Alias for hooray
                "hold": self._handle_hold,
                "skip": self._handle_skip,
                "stop": self._handle_stop,
                "up": self._handle_up,
                "more": self._handle_up,      # Alias for up
                "down": self._handle_down,
                "less": self._handle_down,    # Alias for down
                "max": self._handle_max,
                "half": self._handle_half,
                "pause": self._handle_pause,
                "playback": self._handle_resume,
                "resume": self._handle_resume,
                "easy": self._handle_easy_mode,  # Simple name for easy mode
                "easy_mode": self._handle_easy_mode,
                "medium": self._handle_medium_mode,  # Simple name for medium mode
                "medium_mode": self._handle_medium_mode,
                "hard": self._handle_hard_mode,  # Simple name for hard mode
                "hard_mode": self._handle_hard_mode,
                "yes": self._handle_yes,
                "favorite": self._handle_favorite
            }
            
        except Exception as e:
            self.logger.error(f"Error initializing voice controller: {e}")
            self.model = None
    
    def start_listening(self):
        """Start listening for voice commands."""
        if self.model is None:
            self.logger.error("Cannot start listening: model not loaded")
            return False
            
        if self.listening:
            self.logger.warning("Already listening")
            return True
            
        self.listening = True
        self.thread = threading.Thread(target=self._listening_loop)
        self.thread.daemon = True
        self.thread.start()
        self.logger.info("Started listening for voice commands")
        return True
    
    def stop_listening(self):
        """Stop listening for voice commands."""
        if not self.listening:
            return
            
        self.listening = False
        if self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None
        self.logger.info("Stopped listening for voice commands")
    
    def _listening_loop(self):
        """Main loop for listening to voice commands."""
        try:
            # Create recognizer
            rec = KaldiRecognizer(self.model, 16000)
            
            # Open microphone stream
            stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=8000
            )
            stream.start_stream()
            
            self.logger.info("Voice recognition started")
            
            while self.listening:
                data = stream.read(4000, exception_on_overflow=False)
                if len(data) == 0:
                    break
                    
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    if "text" in result and result["text"]:
                        text = result["text"].lower()
                        self.logger.info(f"Recognized: {text}")
                        
                        # Check for commands in the recognized text
                        for command, handler in self.commands.items():
                            if command in text:
                                self.logger.info(f"Command detected: {command}")
                                handler()
                                self.command_recognized.emit(command)
                                break
            
            # Clean up
            stream.stop_stream()
            stream.close()
            
        except Exception as e:
            self.logger.error(f"Error in listening loop: {e}")
        finally:
            self.listening = False
            self.logger.info("Listening loop ended")
    
    # Command handlers
    def _handle_hooray(self):
        """Handle 'hooray' command."""
        self.logger.info("Handling 'hooray' command")
        # Implementation will be added by the application
    
    def _handle_hold(self):
        """Handle 'hold' command."""
        self.logger.info("Handling 'hold' command")
        # Implementation will be added by the application
    
    def _handle_skip(self):
        """Handle 'skip' command."""
        self.logger.info("Handling 'skip' command")
        # Implementation will be added by the application
    
    def _handle_stop(self):
        """Handle 'stop' command."""
        self.logger.info("Handling 'stop' command")
        # Implementation will be added by the application
    
    def _handle_up(self):
        """Handle 'up/more' command."""
        self.logger.info("Handling 'up/more' command")
        # Implementation will be added by the application
    
    def _handle_down(self):
        """Handle 'down/less' command."""
        self.logger.info("Handling 'down/less' command")
        # Implementation will be added by the application
    
    def _handle_max(self):
        """Handle 'max' command."""
        self.logger.info("Handling 'max' command")
        # Implementation will be added by the application
    
    def _handle_half(self):
        """Handle 'half' command."""
        self.logger.info("Handling 'half' command")
        # Implementation will be added by the application
    
    def _handle_pause(self):
        """Handle 'pause' command."""
        self.logger.info("Handling 'pause' command")
        # Implementation will be added by the application
    
    def _handle_resume(self):
        """Handle 'resume/playback' command."""
        self.logger.info("Handling 'resume/playback' command")
        # Implementation will be added by the application
        
    def _handle_easy_mode(self):
        """Handle 'easy_mode' command."""
        self.logger.info("Handling 'easy_mode' command")
        # Implementation will be added by the application
        
    def _handle_medium_mode(self):
        """Handle 'medium_mode' command."""
        self.logger.info("Handling 'medium_mode' command")
        # Implementation will be added by the application
        
    def _handle_hard_mode(self):
        """Handle 'hard_mode' command."""
        self.logger.info("Handling 'hard_mode' command")
        # Implementation will be added by the application
        
    def _handle_yes(self):
        """Handle 'yes' command."""
        self.logger.info("Handling 'yes' command")
        # Implementation will be added by the application
        
    def _handle_favorite(self):
        """Handle 'favorite' command."""
        self.logger.info("Handling 'favorite' command")
        # Implementation will be added by the application 