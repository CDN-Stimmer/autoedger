# Audio Control Application

A modern, feature-rich audio player application built with Python and PySide6 (Qt), featuring real-time volume visualization, voice control, and interactive playback features.

## Features

### Core Audio Features
- 🎵 Play MP3 and WAV audio files
- 🔄 Random playback and loop functionality
- ⏭️ Sequential playback with "Play Next" functionality
- 🎚️ Real-time volume control with visual feedback
- 📊 Horizontal stereo volume meters with peak indicators
- ⏳ Position slider for audio scrubbing

### Advanced Controls
- 🎯 "Hooray" action with customizable wait time and volume fade
- ⭐ Favorites system for marking and filtering preferred tracks
- 🗣️ Voice control support for hands-free operation
- 🎮 Multiple difficulty modes (Easy, Medium, Hard)
- 📈 Performance tracking with hooray counter

### User Interface
- 🎨 Modern, intuitive UI with material design influences
- 📱 Responsive controls and real-time feedback
- 🎯 Visual indicators for playback status and actions
- 💫 Smooth animations and transitions
- 🌈 Color-coded feedback for different states

## Requirements

- Python 3.8 or higher
- PySide6
- Qt 6.0 or higher
- Additional Python packages (see requirements.txt)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/audio-control.git
   cd audio-control
   ```

2. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up the voice recognition model:
   
   Download the small English model from Vosk website: https://alphacephei.com/vosk/models
   
   Specifically, download the "vosk-model-small-en-us-0.15" model.
   
   You can either:
   
   a) Use the setup script (recommended):
   ```bash
   # Place the downloaded model zip file in the project root directory
   # Then run the setup script
   python setup.py
   ```
   
   b) Or set it up manually:
   ```bash
   mkdir -p src/data/model
   unzip vosk-model-small-en-us-0.15.zip -d src/data/model
   # Rename the extracted directory for simpler referencing
   mv src/data/model/vosk-model-small-en-us-0.15/* src/data/model/
   rmdir src/data/model/vosk-model-small-en-us-0.15
   ```

5. Add audio files:
   
   The setup script will create the necessary directory structure for you. You just need to add your audio files:
   
   ```bash
   # Copy your audio files to the directory
   cp /path/to/your/audio/files/*.mp3 src/data/audio/
   ```
   
   Alternatively, you can add files through the application's interface once it's running.

## Usage

1. Start the application:
   
   You can start the application using the simple run script:
   ```bash
   python run.py
   ```
   
   To run without voice control (if you haven't set up the voice model):
   ```bash
   python run.py --no-voice
   ```
   
   Or directly:
   ```bash
   python src/main.py
   ```

2. Basic Controls:
   - Use the "Play Random" button to start random playback
   - Adjust volume using the slider or voice commands
   - Toggle loop mode with the "Loop" button
   - Use the position slider to navigate within tracks

3. Advanced Features:
   - Click "HOORAY!" to trigger the hooray action (drops volume to 0, waits, then gradually increases)
   - Use the favorites system to mark and filter favorite tracks
   - Adjust wait time and hold drop settings in the Control Settings panel
   - Use voice commands for hands-free control

### Voice Commands

| Command | Action |
|---------|--------|
| "hooray/edge/now" | Trigger hooray action |
| "hold" | Trigger hold action |
| "skip" | Play random file |
| "up/more" | Increase volume by 10% |
| "down/less" | Decrease volume by 10% |
| "max" | Set volume to 100% |
| "half" | Set volume to 50% |
| "pause" | Pause playback |
| "playback" | Resume playback |
| "stop" | Stop playback |
| "favorite" | Add current track to favorites |

## Creating an Executable

You can create a standalone executable of the application using PyInstaller:

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. Create the executable:
   ```bash
   pyinstaller --onefile --windowed --add-data "src/data/model:data/model" --add-data "src/data/audio:data/audio" src/main.py
   ```

3. Find the executable in the `dist` directory.

   Note: You may need to adjust the paths and options depending on your OS and specific requirements.

## Directory Structure

The application follows this directory structure:

```
audio-control/
├── src/
│   ├── audio/          # Audio playback and processing
│   │   ├── qt_player.py        # Media player implementation
│   │   └── voice_control.py    # Voice recognition
│   ├── ui/             # User interface components
│   │   ├── main_window.py      # Main application window
│   │   └── widgets/            # UI widgets
│   │       ├── audio_control_widget.py  # Audio control panel
│   │       └── volume_meter.py          # Volume visualization
│   ├── data/           # Application data
│   │   ├── audio/      # Audio files
│   │   └── model/      # Voice recognition model
│   └── main.py         # Application entry point
├── data/               # User data storage
│   └── favorites.json  # Saved favorites
├── logs/               # Application logs
│   └── peak_performers/ # Saved audio highlights
└── requirements.txt    # Python dependencies
```

## Troubleshooting

### Voice Recognition Issues

1. **Model not found**: Ensure the Vosk model is correctly downloaded and extracted to the `src/data/model` directory.
   - If you see errors like "Failed to create a model", run the setup script:
     ```bash
     python setup.py
     ```
   - Alternatively, you can run the application without voice control:
     ```bash
     python run.py --no-voice
     ```

2. **Recognition accuracy**: If the voice commands aren't being recognized accurately:
   - Try using a larger Vosk model for better accuracy
   - Adjust your microphone placement or volume
   - Speak clearly and at a moderate pace

3. **No microphone access**: Ensure your system allows microphone access for Python applications.

### Audio Playback Issues

1. **No audio files found**: Make sure you have placed audio files in the `src/data/audio` directory.

2. **Unsupported formats**: The application supports MP3 and WAV formats. Convert other formats to these before use.

3. **Playback errors**: If playback fails, check that you have the required codecs installed on your system.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with PySide6 and Qt for Python
- Uses the Vosk speech recognition model
- Inspired by modern audio processing applications

## Support

For support, please open an issue in the GitHub repository or contact the maintainers. 