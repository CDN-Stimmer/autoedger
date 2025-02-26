import sys
import os
import logging

# Add the src directory to the Python path
src_dir = os.path.dirname(os.path.abspath(__file__))
if src_dir not in sys.path:
    sys.path.insert(0, os.path.dirname(src_dir))

import asyncio
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Signal, QObject
from qasync import QEventLoop
from ui.main_window import MainWindow
from audio.qt_player import QtAudioPlayer

def setup_logging():
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def main():
    """Main application entry point."""
    logger = setup_logging()
    
    # Check if voice control should be disabled
    voice_disabled = os.environ.get('DISABLE_VOICE_CONTROL', '0') == '1'
    if voice_disabled:
        logger.info("Voice control disabled by environment variable")
    
    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
            
        loop = QEventLoop(app)
        asyncio.set_event_loop(loop)
        
        # Create components
        audio_player = QtAudioPlayer(logger)
        
        # Create and show main window with error handling for voice model
        try:
            # If voice is disabled, patch the VoiceController class before importing MainWindow
            if voice_disabled:
                # Import and patch before creating MainWindow
                import ui.main_window
                
                class DummyVoiceController(QObject):
                    command_recognized = Signal(str)
                    
                    def __init__(self, *args, **kwargs):
                        super().__init__()
                        logger.info("Initialized dummy voice controller")
                        
                    def start_listening(self):
                        logger.info("Dummy voice controller: start_listening called (no-op)")
                        
                    def stop_listening(self):
                        logger.info("Dummy voice controller: stop_listening called (no-op)")
                
                # Replace the real VoiceController with our dummy
                ui.main_window.VoiceController = DummyVoiceController
                logger.info("Replaced voice controller with dummy implementation")
            
            # Create the main window with the correct parameters
            window = MainWindow(logger, audio_player)
            window.show()
        except Exception as e:
            if "Failed to create a model" in str(e):
                logger.warning(f"Voice model initialization failed: {e}")
                # Show warning dialog
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Warning)
                msg.setWindowTitle("Voice Control Not Available")
                msg.setText("Voice control functionality is not available.")
                msg.setInformativeText("The voice recognition model is missing. The application will run without voice control.\n\nTo enable voice commands, please run 'python setup.py' to download and set up the voice model.")
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec()
                
                # Continue without voice control by using a custom version of MainWindow
                # Patch the VoiceController import in the main_window module to return a dummy class
                import ui.main_window
                
                class DummyVoiceController(QObject):
                    command_recognized = Signal(str)
                    
                    def __init__(self, *args, **kwargs):
                        super().__init__()
                        logger.info("Initialized dummy voice controller")
                        
                    def start_listening(self):
                        logger.info("Dummy voice controller: start_listening called (no-op)")
                        
                    def stop_listening(self):
                        logger.info("Dummy voice controller: stop_listening called (no-op)")
                
                # Replace the real VoiceController with our dummy
                ui.main_window.VoiceController = DummyVoiceController
                
                # Now create the window without voice control
                window = MainWindow(logger, audio_player)
                window.show()
            else:
                # For other errors, re-raise
                raise
        
        with loop:
            loop.run_forever()
            
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

    