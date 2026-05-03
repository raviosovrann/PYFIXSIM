from __future__ import annotations

from PySide6.QtWidgets import QApplication, QListWidget

from src.ui.main_window import MainWindow


def test_app_controller_updates_selected_session_context_and_logs_placeholders(
    qapp: QApplication,
) -> None:
    window = MainWindow()
    window.show()
    qapp.processEvents()

    list_widget = window.findChild(QListWidget, "sessionList")
    assert list_widget is not None
    assert window.app_controller is not None

    first_item = list_widget.item(0)
    first_item.setSelected(True)
    qapp.processEvents()

    assert window.session_state_label.text() == "Session: CLIENT_A->BROKER_A"

    window.send_batch_requested.emit()
    qapp.processEvents()

    assert "[outgoing] Placeholder send batch requested." in window.events_viewer.toPlainText()

    window.close()


def test_app_controller_applies_session_created_updates(qapp: QApplication) -> None:
    window = MainWindow()
    window.show()
    qapp.processEvents()

    window.session_created.emit(
        {
            "sender_comp_id": "BUY_SIDE",
            "target_comp_id": "SELL_SIDE",
            "fix_version": "FIX.4.4",
            "session_type": "Initiator",
        }
    )
    qapp.processEvents()

    assert window.application_state_label.text() == "Application: Session created"
    assert "Controller registered new session: BUY_SIDE->SELL_SIDE" in window.events_viewer.toPlainText()

    window.close()
