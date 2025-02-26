"""
Test script for the audio analysis and synthesis module.
"""

from pathlib import Path
import numpy as np
from analyzer import AudioAnalyzer
from synthesizer import Synthesizer
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
import sounddevice as sd
import os
import threading
import time
import scipy.io.wavfile as wavfile

def create_test_audio(duration=2.0, sample_rate=44100):
    """Create a test audio file with a chirp and some harmonics."""
    t = np.linspace(0, duration, int(duration * sample_rate))
    
    # Create a chirp (frequency sweep)
    f0, f1 = 220, 880  # Sweep from A3 to A5
    phase = 2 * np.pi * t * (f0 + (f1-f0) * t / duration)
    
    # Generate audio with harmonics
    audio = (0.5 * np.sin(phase) +  # Fundamental
            0.3 * np.sin(2 * phase) +  # First harmonic
            0.2 * np.sin(3 * phase))  # Second harmonic
            
    # Add amplitude modulation
    envelope = 0.5 * (1 + np.sin(2 * np.pi * 2 * t))  # 2 Hz modulation
    audio *= envelope
    
    # Normalize
    audio = audio / np.max(np.abs(audio))
    
    return audio.astype(np.float32), sample_rate

class AudioPlayer:
    CHUNK_SIZE = 1024  # Smaller chunks for better device switching
    
    def __init__(self, wav_data, sample_rate, features):
        self.wav_data = wav_data
        self.sample_rate = sample_rate
        self.features = features
        self.is_playing_wav = False
        self.is_playing_synth = False
        self._current_frame = 0
        self.audio_thread = None
        
        # Pre-synthesize the audio
        print("Synthesizing audio...")
        self.synth_data = self.create_matching_synthesis()
        print("Synthesis complete")
        
    def get_current_device(self):
        """Get the current default output device."""
        try:
            device_info = sd.query_devices(kind='output')
            return device_info['name'], device_info['default_samplerate']
        except Exception as e:
            print(f"Error getting device info: {e}")
            return None, self.sample_rate
            
    def create_matching_synthesis(self):
        """Create a synthesized version that matches the original audio."""
        # Get time points for the features
        pitch_times = self.features['times']
        envelope_times = self.features['times']
        
        # Generate audio with pitch modulation
        num_samples = len(self.wav_data)
        t = np.linspace(0, self.features['times'][-1], num_samples, False)
        
        # Interpolate pitch and amplitude to match audio sample rate
        pitch_contour = np.interp(t, pitch_times, self.features['pitch_contour'])
        amplitude_env = np.interp(t, envelope_times, self.features['amplitude_envelope'])
        
        # Generate audio with pitch modulation
        audio = np.zeros(num_samples)
        
        # Use vectorized operations where possible
        time_step = 1.0 / self.sample_rate
        phase_incr = 2 * np.pi * pitch_contour * time_step
        
        # Accumulate phase
        phase = np.cumsum(phase_incr)
        
        # Generate harmonics
        audio = (0.5 * np.sin(phase) +  # Fundamental
                0.3 * np.sin(2 * phase) +  # First harmonic
                0.2 * np.sin(3 * phase))  # Second harmonic
        
        # Apply amplitude envelope
        audio *= amplitude_env / np.max(np.abs(audio))
        
        return audio.astype(np.float32)
        
    def play_audio(self, data):
        """Generic audio playback function."""
        device_name, device_sr = self.get_current_device()
        if device_name is None:
            return
            
        try:
            with sd.OutputStream(samplerate=self.sample_rate,
                               channels=1,
                               blocksize=self.CHUNK_SIZE,
                               device=None,  # Use default device
                               latency='low') as stream:
                
                while self.is_playing_wav or self.is_playing_synth:
                    if self._current_frame >= len(data):
                        self._current_frame = 0
                        
                    chunk_size = min(self.CHUNK_SIZE, len(data) - self._current_frame)
                    chunk = data[self._current_frame:self._current_frame + chunk_size]
                    stream.write(chunk.reshape(-1, 1))
                    self._current_frame += chunk_size
                    
                    # Small sleep to prevent CPU overload
                    time.sleep(0.001)
                    
        except Exception as e:
            print(f"Error in audio playback: {e}")
            self.stop()
            
    def play_wav(self, event=None):
        if self.is_playing_wav or self.audio_thread is not None:
            return
            
        # Stop synth if it's playing
        self.stop_synth()
        
        self.is_playing_wav = True
        self._current_frame = 0
        
        # Start playback in a new thread
        self.audio_thread = threading.Thread(
            target=self.play_audio,
            args=(self.wav_data,),
            daemon=True
        )
        self.audio_thread.start()
            
    def play_synth(self, event=None):
        if self.is_playing_synth or self.audio_thread is not None:
            return
            
        # Stop wav if it's playing
        self.stop_wav()
        
        self.is_playing_synth = True
        self._current_frame = 0
        
        # Start playback in a new thread
        self.audio_thread = threading.Thread(
            target=self.play_audio,
            args=(self.synth_data,),
            daemon=True
        )
        self.audio_thread.start()
            
    def stop_wav(self):
        self.is_playing_wav = False
        if self.audio_thread is not None:
            self.audio_thread.join(timeout=0.5)
            self.audio_thread = None
                
    def stop_synth(self):
        self.is_playing_synth = False
        if self.audio_thread is not None:
            self.audio_thread.join(timeout=0.5)
            self.audio_thread = None
                
    def stop(self, event=None):
        self.stop_wav()
        self.stop_synth()
        self._current_frame = 0

def plot_features(features, audio_data, sample_rate):
    """Helper function to visualize analysis results with playback controls."""
    fig = plt.figure(figsize=(15, 12))  # Made taller to accommodate buttons
    
    # Create audio player
    player = AudioPlayer(audio_data, sample_rate, features)
    
    # Create a grid of subplots with space for colorbar
    gs = plt.GridSpec(3, 2, width_ratios=[20, 1], height_ratios=[1, 1, 1])
    
    # Plot spectrogram
    ax1 = plt.subplot(gs[0, 0])
    im = ax1.pcolormesh(features['times'], features['frequencies'], 
                       20 * np.log10(features['spectrogram'] + 1e-10), shading='gouraud')
    ax1.set_title('Spectrogram')
    ax1.set_ylabel('Frequency [Hz]')
    # Add colorbar to the right of the spectrogram
    cax = plt.subplot(gs[0, 1])
    plt.colorbar(im, cax=cax, label='Amplitude [dB]')
    
    # Plot pitch contour
    ax2 = plt.subplot(gs[1, 0], sharex=ax1)
    ax2.plot(features['times'], features['pitch_contour'])
    ax2.set_title('Pitch Contour')
    ax2.set_ylabel('Frequency [Hz]')
    
    # Plot amplitude envelope
    # Adjust x-axis to match the time scale of other plots
    ax3 = plt.subplot(gs[2, 0], sharex=ax1)
    ax3.plot(features['times'], features['amplitude_envelope'])
    ax3.set_title('Amplitude Envelope')
    ax3.set_ylabel('Amplitude')
    ax3.set_xlabel('Time [s]')
    
    # Set x-axis limit to 15 seconds
    ax1.set_xlim(0, 15)
    
    # Hide x labels for top two plots
    ax1.label_outer()
    ax2.label_outer()
    
    # Adjust layout to make room for buttons
    plt.subplots_adjust(bottom=0.15, right=0.92, hspace=0.3)
    
    # Style for buttons
    button_color = 'lightgray'
    button_hover_color = 'gray'
    text_color = 'black'
    
    # Add WAV button
    wav_ax = plt.axes([0.6, 0.02, 0.1, 0.05])
    wav_button = Button(wav_ax, 'WAV', color=button_color, hovercolor=button_hover_color)
    wav_button.label.set_color(text_color)
    wav_button.on_clicked(player.play_wav)
    
    # Add SYNTH button
    synth_ax = plt.axes([0.71, 0.02, 0.1, 0.05])
    synth_button = Button(synth_ax, 'SYNTH', color=button_color, hovercolor=button_hover_color)
    synth_button.label.set_color(text_color)
    synth_button.on_clicked(player.play_synth)
    
    # Add Stop button
    stop_ax = plt.axes([0.82, 0.02, 0.1, 0.05])
    stop_button = Button(stop_ax, 'STOP', color=button_color, hovercolor=button_hover_color)
    stop_button.label.set_color(text_color)
    stop_button.on_clicked(player.stop)
    
    # Handle window close event
    def on_close(event):
        player.stop()
    fig.canvas.mpl_connect('close_event', on_close)
    
    plt.show()

def main():
    # Create a test audio file
    print("Creating test audio...")
    audio_data, sample_rate = create_test_audio()
    
    # Save the test audio
    test_file = Path("test_audio.wav")
    wavfile.write(test_file, sample_rate, audio_data)
    
    # Initialize analyzer
    analyzer = AudioAnalyzer()
    
    # Load and analyze audio file
    print(f"Loading audio file: {test_file}")
    analyzer.load_file(test_file)
    
    print("Analyzing audio...")
    analyzer.analyze_spectrum()
    analyzer.extract_pitch_contour()
    analyzer.get_amplitude_envelope()
    
    # Plot the analysis results with playback controls
    plot_features(analyzer.features, analyzer.audio_data, analyzer.sample_rate)
    
    # Clean up
    test_file.unlink()

if __name__ == "__main__":
    main() 