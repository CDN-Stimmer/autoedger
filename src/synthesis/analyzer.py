"""
Audio analysis module for extracting features from audio files.
"""

import numpy as np
import sounddevice as sd
from scipy.io import wavfile
from scipy import signal
from pathlib import Path
import librosa

class AudioAnalyzer:
    def __init__(self):
        self.sample_rate = None
        self.audio_data = None
        self.duration = None
        self.features = {}
        self.target_duration = 15.0  # Target duration in seconds
        self.hop_length = 256  # Standard hop length for all analyses
    
    def load_file(self, file_path: str | Path):
        """Load an audio file and prepare it for analysis."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")
            
        # Use librosa for broader format support
        self.audio_data, self.sample_rate = librosa.load(str(file_path), sr=None, duration=self.target_duration)
        self.duration = len(self.audio_data) / self.sample_rate
        
        # If audio is shorter than target duration, loop it to fill the space
        if self.duration < self.target_duration:
            num_repeats = int(np.ceil(self.target_duration / self.duration))
            self.audio_data = np.tile(self.audio_data, num_repeats)[:int(self.target_duration * self.sample_rate)]
            self.duration = self.target_duration
            
        self.features = {}  # Reset features
        
    def analyze_spectrum(self, frame_size: int = 2048):
        """Perform spectral analysis on the loaded audio."""
        if self.audio_data is None:
            raise ValueError("No audio data loaded. Call load_file first.")
            
        # Compute spectrogram
        spectrogram = librosa.stft(self.audio_data, n_fft=frame_size, hop_length=self.hop_length)
        self.features['spectrogram'] = np.abs(spectrogram)
        
        # Compute frequency bins
        self.features['frequencies'] = librosa.fft_frequencies(sr=self.sample_rate, n_fft=frame_size)
        
        # Compute time bins for full duration
        num_frames = self.features['spectrogram'].shape[1]
        self.features['times'] = librosa.times_like(spectrogram, sr=self.sample_rate, hop_length=self.hop_length)
        
    def extract_pitch_contour(self):
        """Extract the fundamental frequency contour."""
        if self.audio_data is None:
            raise ValueError("No audio data loaded. Call load_file first.")
            
        # Compute pitch
        fmin = librosa.note_to_hz('C2')  # Set minimum frequency to avoid noise
        fmax = librosa.note_to_hz('C7')  # Set maximum frequency
        
        pitches, magnitudes = librosa.piptrack(
            y=self.audio_data,
            sr=self.sample_rate,
            hop_length=self.hop_length,
            fmin=fmin,
            fmax=fmax
        )
        
        # Get the most prominent pitch at each time
        pitch_contour = []
        for i in range(pitches.shape[1]):
            # Find the frequency with highest magnitude
            index = magnitudes[:, i].argmax()
            pitch_contour.append(pitches[index, i])
            
        self.features['pitch_contour'] = np.array(pitch_contour)
        self.features['pitch_magnitude'] = np.max(magnitudes, axis=0)
        
    def get_amplitude_envelope(self, frame_size: int = 2048):
        """Calculate the amplitude envelope of the audio."""
        if self.audio_data is None:
            raise ValueError("No audio data loaded. Call load_file first.")
            
        # Compute RMS energy for amplitude envelope
        rms = librosa.feature.rms(
            y=self.audio_data,
            frame_length=frame_size,
            hop_length=self.hop_length,
            center=True
        )[0]
        
        # Ensure the envelope has the same number of points as other features
        if 'times' in self.features:
            target_length = len(self.features['times'])
            if len(rms) > target_length:
                rms = rms[:target_length]
            elif len(rms) < target_length:
                rms = np.pad(rms, (0, target_length - len(rms)))
                
        self.features['amplitude_envelope'] = rms
        
    def play_audio(self):
        """Play the loaded audio file."""
        if self.audio_data is None:
            raise ValueError("No audio data loaded. Call load_file first.")
            
        sd.play(self.audio_data, self.sample_rate)
        sd.wait()  # Wait until the audio is done playing 