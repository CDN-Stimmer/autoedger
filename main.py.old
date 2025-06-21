import sys
import os
import logging
import asyncio
import qasync
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from audio.qt_player import QtAudioPlayer
from hardware.dg_audio_adapter import DGAudioAdapter

def setup_logging():
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def main():
    """Main entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        # Create Qt application
        app = QApplication(sys.argv)
        app.setApplicationName("AudioHaptic")
        app.setOrganizationName("AudioHaptic")

        # Create event loop before components
        loop = qasync.QEventLoop(app)
        asyncio.set_event_loop(loop)

        # Create components after event loop is set
        audio_player = QtAudioPlayer(logger)
        dg_adapter = DGAudioAdapter(audio_player, logger)
        
        # Start the adapter
        dg_adapter.start()
        
        # Create and show main window
        window = MainWindow(audio_player, dg_adapter)
        window.show()

        # Run event loop
        return loop.run_forever()

    except Exception as e:
        logger.error(f"Application error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 