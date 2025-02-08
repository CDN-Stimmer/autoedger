import logging
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from .widgets.dg_control_widget import DGControlWidget


class CoyoteWindow(QMainWindow):
    def __init__(self, logger, dg_adapter, parent=None):
        super().__init__(parent)
        self.logger = logger
        self.dg_adapter = dg_adapter
        self.setWindowTitle("Coyote Module")
        self.resize(800, 600)
        
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        
        # Create and add the DGControlWidget to control the Coyote module
        self.dg_control_widget = DGControlWidget(dg_adapter)
        layout.addWidget(self.dg_control_widget)
        
        self.setCentralWidget(central_widget) 