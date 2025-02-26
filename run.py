#!/usr/bin/env python3
"""
Run script for Audio Control Application
This script provides a simple way to start the application from the project root.
"""
import os
import sys
import subprocess
import logging
import argparse

def setup_logging():
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def main():
    """Main function to run the application."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run Audio Control Application')
    parser.add_argument('--no-voice', action='store_true', help='Run without voice control')
    args = parser.parse_args()
    
    logger = setup_logging()
    
    # Check if src/main.py exists
    main_script = os.path.join('src', 'main.py')
    if not os.path.exists(main_script):
        logger.error(f"Could not find {main_script}. Make sure you're in the right directory.")
        return 1
    
    # Check if directories exist, create them if needed
    required_dirs = [
        os.path.join('src', 'data', 'audio'),
        os.path.join('src', 'data', 'model'),
        os.path.join('src', 'data', 'logs'),
        os.path.join('src', 'data', 'favorites')
    ]
    
    for directory in required_dirs:
        if not os.path.exists(directory):
            logger.warning(f"Creating missing directory: {directory}")
            os.makedirs(directory, exist_ok=True)
    
    # Check if model files exist
    model_dir = os.path.join('src', 'data', 'model')
    model_files = os.listdir(model_dir)
    if not any(f for f in model_files if f != '.gitkeep'):
        logger.warning("No model files found! Voice control may not work.")
        logger.warning("Please run `python setup.py` to set up the voice model.")
        # Automatically set no-voice flag if model files are missing
        args.no_voice = True
        logger.info("Automatically enabling --no-voice mode due to missing model files")
    
    # Run the application
    try:
        logger.info("Starting Audio Control Application...")
        
        # Set up environment for the subprocess
        env = os.environ.copy()
        
        # Set PYTHONPATH to include the current directory
        python_path = env.get('PYTHONPATH', '')
        current_dir = os.path.abspath(os.path.dirname(__file__))
        if python_path:
            env['PYTHONPATH'] = f"{current_dir}:{python_path}"
        else:
            env['PYTHONPATH'] = current_dir
            
        # Set environment variable for voice control if needed
        if args.no_voice:
            logger.info("Running without voice control (--no-voice flag specified)")
            env['DISABLE_VOICE_CONTROL'] = '1'
        
        # Run the main script as a subprocess
        cmd = [sys.executable, main_script]
        process = subprocess.run(cmd, env=env)
        return process.returncode
        
    except Exception as e:
        logger.error(f"Error running application: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 