import sys
import logging

import asyncio
from PySide6.QtWidgets import QApplication
from qasync import QEventLoop
from ui.main_window import MainWindow

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
        
        window = MainWindow(logger)
        window.show()
        
        with loop:
            loop.run_forever()
            
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

    