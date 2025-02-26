"""
Audio synthesis module for recreating and manipulating audio based on analysis.
"""

import numpy as np
from scipy import signal
import sounddevice as sd

class Synthesizer:
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.audio_data = None
        self.oscillators = []
        
    class Oscillator:
        def __init__(self, waveform='sine'):
            self.waveform = waveform
            self.frequency = 440.0  # Default frequency in Hz
            self.amplitude = 1.0
            self.phase = 0.0
            
        def generate(self, duration: float, sample_rate: int) -> np.ndarray:
            """Generate audio samples for the oscillator."""
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            
            if self.waveform == 'sine':
                samples = np.sin(2 * np.pi * self.frequency * t + self.phase)
            elif self.waveform == 'square':
                samples = signal.square(2 * np.pi * self.frequency * t + self.phase)
            elif self.waveform == 'sawtooth':
                samples = signal.sawtooth(2 * np.pi * self.frequency * t + self.phase)
            elif self.waveform == 'triangle':
                samples = signal.sawtooth(2 * np.pi * self.frequency * t + self.phase, width=0.5)
            else:
                raise ValueError(f"Unknown waveform type: {self.waveform}")
                
            return self.amplitude * samples
            
    def add_oscillator(self, waveform: str = 'sine') -> Oscillator:
        """Add a new oscillator to the synthesizer."""
        osc = self.Oscillator(waveform)
        self.oscillators.append(osc)
        return osc
        
    def synthesize(self, duration: float):
        """Synthesize audio from all oscillators."""
        if not self.oscillators:
            raise ValueError("No oscillators added to synthesizer")
            
        # Initialize empty audio buffer
        num_samples = int(self.sample_rate * duration)
        self.audio_data = np.zeros(num_samples)
        
        # Mix all oscillators
        for osc in self.oscillators:
            self.audio_data += osc.generate(duration, self.sample_rate)
            
        # Normalize to prevent clipping
        max_amplitude = np.max(np.abs(self.audio_data))
        if max_amplitude > 1.0:
            self.audio_data /= max_amplitude
            
    def apply_envelope(self, attack: float = 0.1, decay: float = 0.1,
                      sustain: float = 0.7, release: float = 0.2):
        """Apply an ADSR envelope to the synthesized audio."""
        if self.audio_data is None:
            raise ValueError("No audio data synthesized yet")
            
        total_samples = len(self.audio_data)
        envelope = np.ones(total_samples)
        
        # Convert times to samples
        attack_samples = int(attack * self.sample_rate)
        decay_samples = int(decay * self.sample_rate)
        release_samples = int(release * self.sample_rate)
        
        # Create envelope segments
        envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
        envelope[attack_samples:attack_samples + decay_samples] = \
            np.linspace(1, sustain, decay_samples)
        envelope[-release_samples:] = np.linspace(sustain, 0, release_samples)
        
        # Apply envelope
        self.audio_data *= envelope
        
    def play(self):
        """Play the synthesized audio."""
        if self.audio_data is None:
            raise ValueError("No audio data synthesized yet")
            
        sd.play(self.audio_data, self.sample_rate)
        sd.wait()  # Wait until the audio is done playing 