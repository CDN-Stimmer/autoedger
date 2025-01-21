import sys
import os

# Add src directory to Python path
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, src_dir)

from PySide6.QtCore import QCoreApplication
from PySide6.QtMultimedia import QMediaPlayer
import logging
from log_utils.logger import Logger
from audio.qt_player import QtAudioPlayer
from hardware.dg_audio_adapter import DGAudioAdapter
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Test DG device with audio playback."""
    app = QCoreApplication(sys.argv)
    
    # Initialize components
    logger = Logger()
    audio_player = QtAudioPlayer(logger)
    dg_adapter = DGAudioAdapter(audio_player, logger)
    
    try:
        # Start the DG adapter
        dg_adapter.start()
        time.sleep(2)  # Wait for connection
        
        # Load test audio file
        test_file = "0b3554f628b4805861b35992b60bf26a4dbdf11e.mp3"
        if not os.path.exists(test_file):
            logger.error(f"Test file not found: {test_file}")
            return
            
        # Load audio data for analysis
        if not audio_player._load_audio_data(test_file):
            logger.error("Failed to load audio data")
            return
            
        # Set volume to max
        audio_player.set_volume(1.0)
        
        # Play the file
        audio_player.play_file(test_file)
        logger.info(f"Playing test file: {test_file}")
        
        # Let it play for 30 seconds
        logger.info("Will play for 30 seconds...")
        time.sleep(30)
        
        # Stop playback
        logger.info("Stopping playback...")
        audio_player.stop_playback()
        
        # Clean up
        logger.info("Cleaning up...")
        dg_adapter.stop()
        
    except Exception as e:
        logger.error(f"Test error: {e}")
    finally:
        app.quit()

if __name__ == "__main__":
    main() 