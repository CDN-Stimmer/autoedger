import sys
import os
import logging

# Add the src directory to the Python path
src_dir = os.path.dirname(os.path.abspath(__file__))
if src_dir not in sys.path:
    sys.path.insert(0, os.path.dirname(src_dir))

import asyncio
from PySide6.QtWidgets import QApplication
from qasync import QEventLoop
from ui.main_window import MainWindow
from audio.qt_player import QtAudioPlayer
from hardware.dg_audio_adapter import DGAudioAdapter

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
    
    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
            
        loop = QEventLoop(app)
        asyncio.set_event_loop(loop)
        
        # Create components
        audio_player = QtAudioPlayer(logger)
        dg_adapter = DGAudioAdapter(audio_player, logger)
        
        # Create and show main window
        window = MainWindow(logger, audio_player, dg_adapter)
        window.show()
        
        with loop:
            loop.run_forever()
            
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

    