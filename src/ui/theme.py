from PySide6.QtGui import QPalette, QColor


def _light_qss() -> str:
    return """
    /* Base */
    QWidget {
        background: #f5f7fb;
        color: #1f2937;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
        font-size: 13px;
    }

    /* App bar */
    QFrame#AppBar {
        background: #ffffff;
        border-bottom: 1px solid #e5e7eb;
    }
    QLabel#AppTitle {
        color: #111827;
        font-size: 16px;
        font-weight: 600;
        padding: 10px 8px;
    }

    /* Cards / containers */
    QFrame#Card,
    QGroupBox {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 4px 6px 0 6px;
        color: #374151;
        font-weight: 600;
    }

    /* Buttons */
    QPushButton {
        background: #eef2ff;
        color: #374151;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 6px 12px;
    }
    QPushButton:hover {
        background: #e0e7ff;
    }
    QPushButton:pressed {
        background: #c7d2fe;
    }
    QPushButton[primary="true"] {
        background: #2563eb;
        border: 1px solid #1d4ed8;
        color: #ffffff;
    }
    QPushButton[primary="true"]:hover {
        background: #1d4ed8;
    }

    /* Segmented (checkable) buttons */
    QPushButton:checked {
        background: #e8f0fe;
        color: #1a73e8;
        border-color: #dbeafe;
    }

    /* Sliders */
    QSlider::groove:horizontal {
        height: 6px;
        background: #e5e7eb;
        border-radius: 3px;
    }
    QSlider::handle:horizontal {
        background: #2563eb;
        border: 2px solid #ffffff;
        width: 16px;
        height: 16px;
        margin: -6px 0; /* center the handle */
        border-radius: 10px;
    }

    /* Combo boxes */
    QComboBox {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 4px 8px;
    }
    QComboBox:hover {
        border-color: #cbd5e1;
    }

    /* Status bar */
    QStatusBar {
        background: #ffffff;
        border-top: 1px solid #e5e7eb;
        color: #6b7280;
    }

    /* Scrollbars */
    QScrollBar:vertical {
        background: transparent;
        width: 10px;
        margin: 2px;
    }
    QScrollBar::handle:vertical {
        background: #d1d5db;
        border-radius: 6px;
        min-height: 24px;
    }
    QScrollBar::handle:vertical:hover {
        background: #9ca3af;
    }
    """


def _dark_qss() -> str:
    return """
    QWidget {
        background: #0f1115;
        color: #e5e7eb;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
        font-size: 13px;
    }

    QFrame#AppBar {
        background: #111827;
        border-bottom: 1px solid #1f2937;
    }
    QLabel#AppTitle {
        color: #f9fafb;
        font-size: 16px;
        font-weight: 600;
        padding: 10px 8px;
    }

    QFrame#Card,
    QGroupBox {
        background: #111827;
        border: 1px solid #1f2937;
        border-radius: 12px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 4px 6px 0 6px;
        color: #d1d5db;
        font-weight: 600;
    }

    QPushButton {
        background: #1f2937;
        color: #e5e7eb;
        border: 1px solid #374151;
        border-radius: 10px;
        padding: 6px 12px;
    }
    QPushButton:hover {
        background: #233044;
    }
    QPushButton:pressed {
        background: #2a3a52;
    }
    QPushButton[primary="true"] {
        background: #2563eb;
        border: 1px solid #1d4ed8;
        color: #ffffff;
    }
    QPushButton[primary="true"]:hover {
        background: #1d4ed8;
    }

    QPushButton:checked {
        background: #233044;
        color: #60a5fa;
        border-color: #334155;
    }

    QSlider::groove:horizontal {
        height: 6px;
        background: #374151;
        border-radius: 3px;
    }
    QSlider::handle:horizontal {
        background: #3b82f6;
        border: 2px solid #0f1115;
        width: 16px;
        height: 16px;
        margin: -6px 0;
        border-radius: 10px;
    }

    QComboBox {
        background: #111827;
        border: 1px solid #374151;
        border-radius: 8px;
        padding: 4px 8px;
        color: #e5e7eb;
    }
    QComboBox:hover {
        border-color: #475569;
    }

    QStatusBar {
        background: #111827;
        border-top: 1px solid #1f2937;
        color: #9ca3af;
    }

    QScrollBar:vertical {
        background: transparent;
        width: 10px;
        margin: 2px;
    }
    QScrollBar::handle:vertical {
        background: #374151;
        border-radius: 6px;
        min-height: 24px;
    }
    QScrollBar::handle:vertical:hover {
        background: #4b5563;
    }
    """


def load_stylesheet(mode: str = "dark") -> str:
    if mode.lower() == "light":
        return _light_qss()
    return _dark_qss()


def apply_theme(app, mode: str = "dark") -> None:
    app.setStyleSheet(load_stylesheet(mode))
    app.setProperty("themeMode", mode.lower())


def get_theme_mode(app) -> str:
    mode = app.property("themeMode")
    return mode if isinstance(mode, str) else "dark"




