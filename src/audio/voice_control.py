import json
import queue
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import threading
from PySide6.QtCore import QObject, Signal

class VoiceController(QObject):
    command_recognized = Signal(str)  # Emits the recognized command
    
    def __init__(self, logger, model_path="model"):
        super().__init__()
        self.logger = logger
        self.running = False
        self.commands = {
            "edge": self._handle_hooray,
            "now": self._handle_hooray,
            "hooray": self._handle_hooray,
            "hold": self._handle_hold,
            "skip": self._handle_skip,
            "up": self._handle_volume_up,
            "more": self._handle_volume_up,
            "down": self._handle_volume_down,
            "less": self._handle_volume_down,
            "pause": self._handle_pause,
            "playback": self._handle_playback,
            "stop": self._handle_stop,
            "easy": self._handle_easy_mode,
            "medium": self._handle_medium_mode,
            "hard": self._handle_hard_mode,
            "yes": self._handle_yes
        }
        
        try:
            self.model = Model(model_path)
            self.logger.info("Loaded voice recognition model")
            
            # Initialize audio input settings
            self.samplerate = 16000
            self.blocksize = 2000
            self.q = queue.Queue()
            
            self.recognizer = KaldiRecognizer(self.model, self.samplerate)
            self.recognizer.SetWords(True)
            
        except Exception as e:
            self.logger.error(f"Error initializing voice control: {e}")
            raise
            
    def _audio_callback(self, indata, frames, time, status):
        """Callback for audio input"""
        if status:
            self.logger.warning(f"Audio input status: {status}")
        if self.running:
            self.q.put(bytes(indata))
            
    def start_listening(self):
        """Start listening for voice commands"""
        try:
            self.running = True
            self.stream = sd.RawInputStream(
                samplerate=self.samplerate,
                blocksize=self.blocksize,
                dtype="int16",
                channels=1,
                callback=self._audio_callback
            )
            
            # Start processing in a separate thread
            self.process_thread = threading.Thread(target=self._process_audio, daemon=True)
            self.process_thread.start()
            
            self.stream.start()
            self.logger.info("Started voice command listening")
            
        except Exception as e:
            self.logger.error(f"Error starting voice control: {e}")
            self.running = False
            raise
            
    def stop_listening(self):
        """Stop listening for voice commands"""
        self.running = False
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()
        if hasattr(self, 'process_thread'):
            self.process_thread.join(timeout=1.0)
            
    def _process_audio(self):
        """Process audio input and recognize commands"""
        while self.running:
            try:
                data = self.q.get()
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    text = result.get("text", "").lower()
                    
                    # Check for known commands
                    for command, handler in self.commands.items():
                        if command in text:
                            self.logger.info(f"Recognized command: {command}")
                            handler()
                            break
                            
            except Exception as e:
                self.logger.error(f"Error processing audio: {e}")
                
    def _handle_volume_up(self):
        """Handle the volume up command"""
        self.command_recognized.emit("up")
        
    def _handle_volume_down(self):
        """Handle the volume down command"""
        self.command_recognized.emit("down")
        
    def _handle_hold(self):
        """Handle the hold command"""
        self.command_recognized.emit("hold")
        
    def _handle_hooray(self):
        """Handle the hooray command"""
        self.command_recognized.emit("hooray")
        
    def _handle_skip(self):
        """Handle the skip command"""
        self.command_recognized.emit("skip")
        
    def _handle_pause(self):
        """Handle the pause command"""
        self.command_recognized.emit("pause")
        
    def _handle_playback(self):
        """Handle the playback command"""
        self.command_recognized.emit("playback")
        
    def _handle_stop(self):
        """Handle the stop command"""
        self.command_recognized.emit("stop")
        
    def _handle_easy_mode(self):
        """Handle easy mode command"""
        self.command_recognized.emit("easy_mode")
        
    def _handle_medium_mode(self):
        """Handle medium mode command"""
        self.command_recognized.emit("medium_mode")
        
    def _handle_hard_mode(self):
        """Handle hard mode command"""
        self.command_recognized.emit("hard_mode")
        
    def _handle_yes(self):
        """Handle the yes command"""
        self.command_recognized.emit("yes") 