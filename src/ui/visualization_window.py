from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from .widgets.visualization_widget import VisualizationWidget
from visualization.manager import VisualizationManager

class VisualizationWindow(QMainWindow):
    def __init__(self, audio_control, serial_monitor):
        super().__init__()
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Create visualization widget
        self.visualization = VisualizationWidget()
        layout.addWidget(self.visualization)
        
        # Create visualization manager
        self.viz_manager = VisualizationManager(audio_control_widget=audio_control)
        self.viz_manager.start()
        
        # Connect visualization manager to serial monitor
        serial_monitor.pressure_updated.connect(self.viz_manager.update)
        
        # Connect audio player to visualization
        audio_player = audio_control.audio_player
        audio_player.playback_started.connect(self.visualization.on_playback_started)
        audio_player.playback_stopped.connect(self.visualization.on_playback_stopped)
        audio_player.audio_data_ready.connect(self.viz_manager.update_audio_metrics)
        
        # Set up window
        self.setWindowTitle("Visualization")
        self.resize(800, 400)
        
    def closeEvent(self, event):
        """Handle window close event."""
        self.viz_manager.stop()
        event.accept() 