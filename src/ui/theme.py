from __future__ import annotations

from PySide6.QtGui import QColor


def get_event_role_colors() -> dict[str, QColor]:
    """Return semantic colors used by the Events Viewer highlighter."""
    return {
        "incoming": QColor("#efb1b1"),
        "outgoing": QColor("#9fe0b7"),
        "console": QColor("#f2d88c"),
        "session": QColor("#c7d7ff"),
    }


def get_app_stylesheet() -> str:
    """Return the shared application stylesheet for the first UI pass."""
    return """
    QMainWindow, QWidget {
        background-color: #0b0d10;
        color: #f3f5f7;
        selection-background-color: #2f5f8a;
        selection-color: #f8fbff;
    }

    QMenuBar, QStatusBar, QMenu {
        background-color: #13171b;
        color: #f3f5f7;
    }

    QMenuBar::item {
        padding: 4px 8px;
        background: transparent;
    }

    QMenuBar::item:selected,
    QMenu::item:selected {
        background-color: #262d35;
    }

    QMenu {
        border: 1px solid #343a40;
    }

    QStatusBar {
        border-top: 1px solid #343a40;
    }

    QGroupBox {
        background-color: #101419;
        border: 1px solid #343a40;
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 8px;
        font-weight: 600;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
    }

    QWidget[sessionRow="true"] {
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 4px;
    }

    QWidget[sessionRow="true"][selected="true"] {
        background-color: #22303c;
        border: 1px solid #4b6377;
    }

    QLabel[sessionRole="primary"] {
        color: #f4f7fa;
        font-weight: 600;
        background-color: transparent;
    }

    QLabel[sessionRole="secondary"] {
        color: #c8d0d8;
        background-color: transparent;
    }

    QLabel[sessionIndicator="waiting"] {
        color: #f2c572;
        background-color: transparent;
        font-size: 15px;
    }

    QLabel[sessionIndicator="connected"] {
        color: #70d49b;
        background-color: transparent;
        font-size: 15px;
    }

    QLabel[sessionIndicator="error"] {
        color: #ef7f7f;
        background-color: transparent;
        font-size: 15px;
    }

    QListWidget,
    QTabWidget::pane,
    QPlainTextEdit,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QScrollArea {
        background-color: #14191f;
        color: #f5f7fa;
        border: 1px solid #414851;
        border-radius: 4px;
    }

    QPlainTextEdit,
    QListWidget {
        alternate-background-color: #101419;
    }

    QLineEdit:focus,
    QPlainTextEdit:focus,
    QSpinBox:focus,
    QDoubleSpinBox:focus,
    QComboBox:focus,
    QListWidget:focus {
        border: 1px solid #6e7a86;
    }

    QLineEdit:disabled,
    QPlainTextEdit:disabled,
    QSpinBox:disabled,
    QDoubleSpinBox:disabled,
    QComboBox:disabled {
        background-color: #101419;
        color: #7e8791;
        border: 1px solid #2b3137;
    }

    QTabWidget::pane {
        margin-top: 2px;
    }

    QTabBar::tab {
        background-color: #15191e;
        color: #e7edf3;
        border: 1px solid #343a40;
        border-bottom: none;
        padding: 6px 12px;
        margin-right: 2px;
    }

    QTabBar::tab:selected {
        background-color: #1d2329;
        color: #ffffff;
    }

    QTabBar::tab:hover:!selected {
        background-color: #20262d;
    }

    QPushButton {
        background-color: #1d2329;
        color: #f4f7fa;
        border: 1px solid #4a535c;
        border-radius: 4px;
        padding: 6px 10px;
    }

    QPushButton:hover {
        background-color: #2a3138;
    }

    QPushButton:disabled {
        background-color: #12161a;
        color: #737b84;
        border: 1px solid #2d3338;
    }

    QCheckBox {
        spacing: 6px;
        color: #d7dde4;
    }

    QCheckBox:checked {
        color: #ffffff;
        font-weight: 600;
    }

    QCheckBox::indicator {
        width: 15px;
        height: 15px;
        border: 1px solid #98a4b0;
        border-radius: 3px;
        background-color: #0b0d10;
    }

    QCheckBox::indicator:hover {
        border: 1px solid #d7dde4;
        background-color: #161b20;
    }

    QCheckBox::indicator:checked {
        background-color: #2f5f8a;
        border: 2px solid #eef6ff;
    }

    QCheckBox::indicator:disabled {
        border: 1px solid #525860;
        background-color: #15191d;
    }

    QRadioButton {
        spacing: 6px;
        color: #d7dde4;
    }

    QRadioButton::indicator {
        width: 15px;
        height: 15px;
        border: 1px solid #98a4b0;
        border-radius: 8px;
        background-color: #0b0d10;
    }

    QRadioButton::indicator:checked {
        background-color: #2f5f8a;
        border: 2px solid #eef6ff;
    }

    QRadioButton::indicator:disabled {
        border: 1px solid #525860;
        background-color: #15191d;
    }

    QGroupBox:disabled {
        color: #7e8791;
        border: 1px solid #2b3137;
    }

    QAbstractItemView {
        background-color: #14191f;
        color: #f5f7fa;
        border: 1px solid #414851;
        selection-background-color: #2f5f8a;
        selection-color: #f8fbff;
        outline: none;
    }

    QSplitter::handle {
        background-color: #1a1f24;
    }

    QScrollBar:vertical,
    QScrollBar:horizontal {
        background-color: #101419;
        border: none;
        margin: 0;
    }

    QScrollBar::handle:vertical,
    QScrollBar::handle:horizontal {
        background-color: #3a434b;
        min-height: 24px;
        min-width: 24px;
        border-radius: 4px;
    }

    QScrollBar::handle:vertical:hover,
    QScrollBar::handle:horizontal:hover {
        background-color: #4b5660;
    }

    QScrollBar::add-line,
    QScrollBar::sub-line,
    QScrollBar::add-page,
    QScrollBar::sub-page {
        background: none;
        border: none;
    }

    QLabel[role="incoming"] {
        color: #b9f2bf;
    }

    QLabel[role="outgoing"] {
        color: #ffe4aa;
    }

    QLabel[role="console"] {
        color: #cfd6de;
    }
    """