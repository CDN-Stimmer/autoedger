import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import time
from pygame import mixer
from visualization.manager import VisualizationManager

class Interface:
    def __init__(self, logger, audio_player):
        self.logger = logger
        self.audio_player = audio_player
        self.serial_monitor = None
        self.hooray_count = 0
        self.wait_time = 5  # Default wait time in seconds
        self.hooray_in_progress = False
        self.root = None
        self.visualization = VisualizationManager()
        
        # Connect audio player to visualization
        self.audio_player.set_visualization_manager(self.visualization)
        
        # Set up UI
        self.setup_ui()

    def set_serial_monitor(self, serial_monitor):
        """Set up the serial monitor after UI initialization."""
        self.serial_monitor = serial_monitor
        # Set up callbacks
        self.serial_monitor.start_monitoring(
            pressure_callback=self._update_pressure_display,
            hooray_callback=self.hooray_action,
            next_file_callback=self._skip_file
        )

    def setup_ui(self):
        """Set up the main UI window and components."""
        self.root = tk.Tk()
        self.root.title("Random Audio Player")
        self.root.geometry("450x750")
        self.root.resizable(False, False)

        # Pressure Display
        self.pressure_label = tk.Label(self.root, text="Current Pressure: -- kPa", font=("Arial", 18))
        self.pressure_label.pack(pady=10)

        # Threshold Slider
        tk.Label(self.root, text="Pressure Threshold (kPa):").pack(pady=5)
        self.threshold_slider = tk.Scale(
            self.root, from_=5, to=45, orient="horizontal",
            resolution=0.1, length=300,
            command=self._update_threshold
        )
        self.threshold_slider.set(10.0)  # Default threshold
        self.threshold_slider.pack(pady=10)

        # Hooray Count
        self.hooray_count_label = tk.Label(self.root, text="0", font=("Arial", 32), fg="blue")
        self.hooray_count_label.pack(pady=10)

        # Status Frame
        status_frame = tk.Frame(self.root)
        status_frame.pack(pady=10)

        self.file_name_label = tk.Label(status_frame, text="File: --", font=("Arial", 18))
        self.file_name_label.grid(row=0, column=0, columnspan=3, pady=10)

        self.time_remaining_label = tk.Label(status_frame, text="Time Remaining: --:--", font=("Arial", 18))
        self.time_remaining_label.grid(row=1, column=0, padx=10)

        self.volume_label = tk.Label(status_frame, text="Volume: 100%", font=("Arial", 18))
        self.volume_label.grid(row=1, column=1, padx=10)

        # Control Buttons
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=20)

        tk.Button(
            button_frame, text="Skip", command=self._skip_file,
            font=("Arial", 12), width=10, height=5, bg="lightblue"
        ).grid(row=0, column=0, padx=5)

        tk.Button(
            button_frame, text="Stop", command=self._stop_playback,
            font=("Arial", 12), width=10, height=5, bg="red", fg="black"
        ).grid(row=0, column=1, padx=5)

        self.loop_button = tk.Button(
            button_frame, text="Loop: OFF", command=self._toggle_loop,
            font=("Arial", 12), width=10, height=5, bg="lightgreen"
        )
        self.loop_button.grid(row=0, column=2, padx=5)

        # Load and Reset Controls
        control_frame = tk.Frame(self.root)
        control_frame.pack(pady=10)

        tk.Button(
            control_frame, text="Load MP3 Folder", command=self._load_files,
            font=("Arial", 12), width=15, height=3, bg="lightgray"
        ).grid(row=0, column=0, padx=10)

        tk.Button(
            control_frame, text="Reset", command=self._reset_counter,
            font=("Arial", 12), width=15, height=3, bg="lightgray"
        ).grid(row=0, column=1, padx=10)

        # Wait Time Slider
        tk.Label(self.root, text="Wait Time (seconds):").pack(pady=5)
        self.wait_time_slider = tk.Scale(
            self.root, from_=0, to=30, orient="horizontal",
            command=self._update_wait_time
        )
        self.wait_time_slider.set(self.wait_time)
        self.wait_time_slider.pack(pady=10, fill=tk.X)

        # Hooray Button
        tk.Button(
            self.root, text="HOORAY!", command=self.hooray_action,
            font=("Arial", 24), bg="red", fg="white", width=20, height=5
        ).pack(side=tk.BOTTOM, pady=20)

        # Window close handler
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def run(self):
        """Start the UI main loop and visualization."""
        # Start visualization in background
        self.visualization.start()
        # Start Tkinter event loop
        self.root.mainloop()

    def _update_pressure_display(self, pressure):
        """Update the pressure display label and visualization."""
        try:
            self.pressure_label.config(text=f"Current Pressure: {pressure:.2f} kPa")
            # Update visualization in the background
            self.root.after(0, self.visualization.update, pressure)
        except Exception as e:
            self.logger.error(f"Error updating pressure display: {str(e)}")

    def _update_threshold(self, value):
        """Update the pressure threshold."""
        if self.serial_monitor:
            self.serial_monitor.set_pressure_threshold(float(value))

    def _update_wait_time(self, value):
        """Update the wait time."""
        self.wait_time = int(value)

    def _load_files(self):
        """Open file dialog and load MP3 files."""
        folder = filedialog.askdirectory()
        if folder:
            if self.audio_player.load_files(folder):
                self.logger.info(f"Loading files from: {folder}")
                # Update UI before starting playback
                self.root.update_idletasks()
                
                if self.audio_player.play_random_file(self._handle_time_update):
                    # Update visualization with current file
                    self.visualization.set_current_file(self.audio_player.current_file)
                    self._do_update(self.audio_player.track_length)
                    self.logger.info("Started playback")
            else:
                messagebox.showerror("Error", "No MP3 files found in the selected folder")

    def _handle_time_update(self, time_left):
        """Handle time updates from the audio player."""
        try:
            # Use after with a small delay instead of after_idle to prevent UI hanging
            self.root.after(50, self._do_update, time_left)
        except Exception as e:
            self.logger.error(f"Error scheduling update: {str(e)}")

    def _do_update(self, time_left):
        """Perform the actual UI update on the main thread."""
        try:
            # Update time
            mins, secs = divmod(int(time_left), 60)
            self.time_remaining_label.config(text=f"Time Remaining: {mins:02}:{secs:02}")
            
            # Update filename only if it has changed
            current_file = self.audio_player.get_current_file_name()
            if current_file:
                current_text = self.file_name_label.cget("text")
                new_text = f"File: {current_file}"
                if current_text != new_text:
                    self.file_name_label.config(text=new_text)
                    self.logger.debug(f"Updated filename display to: {current_file}")
            
            # Update volume only if it has changed
            volume = int(self.audio_player.get_volume() * 100)
            current_volume = self.volume_label.cget("text")
            new_volume = f"Volume: {volume}%"
            if current_volume != new_volume:
                self.volume_label.config(text=new_volume)
                
        except Exception as e:
            self.logger.error(f"Error updating display: {str(e)}")

    def _skip_file(self):
        """Skip to the next random file."""
        self.logger.debug("Skipping to next file")
        # Update UI immediately to show action is being taken
        self.file_name_label.config(text="File: Loading...")
        self.root.update_idletasks()
        
        # Use after with a small delay to prevent blocking
        self.root.after(100, self._do_skip_file)

    def _do_skip_file(self):
        """Actually perform the file skip."""
        try:
            if self.audio_player.play_random_file(self._handle_time_update):
                # Update visualization with new file
                self.visualization.set_current_file(self.audio_player.current_file)
                self._update_ui_state()
                self.logger.info("Started new file")
        except Exception as e:
            self.logger.error(f"Error during file skip: {str(e)}")

    def _stop_playback(self):
        """Stop the current playback."""
        self.logger.debug("Stopping playback")
        if self.audio_player.stop_playback():
            self.file_name_label.config(text="File: --")
            self.time_remaining_label.config(text="Time Remaining: --:--")
            self.volume_label.config(text="Volume: 0%")
            self.logger.info("Playback stopped")

    def _toggle_loop(self):
        """Toggle the loop state."""
        is_looping = self.audio_player.toggle_loop()
        self.loop_button.config(text=f"Loop: {'ON' if is_looping else 'OFF'}")

    def _reset_counter(self):
        """Reset the hooray counter."""
        self.hooray_count = 0
        self.hooray_count_label.config(text=str(self.hooray_count))
        # Reset the cycle number in the serial monitor
        if self.serial_monitor:
            self.serial_monitor.set_cycle(0)

    def hooray_action(self, event=None):
        """Perform the hooray button action."""
        if self.hooray_in_progress:
            self.logger.info("Hooray already in progress. Skipping.")
            return

        self.hooray_in_progress = True
        self.logger.info("Hooray cycle started.")
        self.hooray_count += 1
        self.hooray_count_label.config(text=str(self.hooray_count))

        # Update the cycle number in the serial monitor
        if self.serial_monitor:
            self.serial_monitor.set_cycle(self.hooray_count)

        # Log max pressure at the moment hooray is triggered
        max_pressure_at_hooray = self.serial_monitor.max_pressure
        self.logger.info(f"Max Pressure Recorded at Hooray: {max_pressure_at_hooray:.2f} kPa")
        
        # Log hooray event in visualization
        self.visualization.log_event("hooray", max_pressure_at_hooray)

        if mixer.music.get_busy():
            self.logger.info("Pausing audio...")
            self.audio_player.stop_playback()
            self.volume_label.config(text="Volume: 0%")

            # Start the pause and resume thread
            threading.Thread(target=self._pause_and_resume, daemon=True).start()
        else:
            self.logger.info("Audio is not playing. No pause needed.")
            self.hooray_in_progress = False

    def _pause_and_resume(self):
        """Handle the pause and resume functionality."""
        try:
            time.sleep(self.wait_time)
            self.logger.debug("Resuming after pause")
            if self.audio_player.play_random_file(self._handle_time_update):
                self._update_ui_state()  # Update UI immediately
                self.audio_player.fade_in_volume()
                for i in range(11):
                    volume = i * 10
                    self.volume_label.config(text=f"Volume: {volume}%")
                    time.sleep(0.1)
        finally:
            self.hooray_in_progress = False

    def _on_closing(self):
        """Handle window closing."""
        self.visualization.stop()
        if self.serial_monitor:
            self.serial_monitor.stop_monitoring()
        self.root.destroy() 

    def _update_ui_state(self):
        """Update all UI elements to reflect current state."""
        try:
            # Update filename
            current_file = self.audio_player.get_current_file_name()
            if current_file:
                self.file_name_label.config(text=f"File: {current_file}")
            else:
                self.file_name_label.config(text="File: --")

            # Update volume
            volume = int(self.audio_player.get_volume() * 100)
            self.volume_label.config(text=f"Volume: {volume}%")
            
            self.logger.debug("UI state updated")
        except Exception as e:
            self.logger.error(f"Error updating UI state: {str(e)}") 