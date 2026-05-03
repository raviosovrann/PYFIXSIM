from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialogButtonBox,
    QGroupBox,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
)

from src.ui.create_session_dialog import CreateSessionDialog


def test_create_session_dialog_toggles_optional_sections(qapp: QApplication) -> None:
    dialog = CreateSessionDialog()
    dialog.show()
    qapp.processEvents()

    custom_logon_checkbox = dialog.findChild(QCheckBox, "customLogonCheckbox")
    use_extended_properties_checkbox = dialog.findChild(
        QCheckBox,
        "useExtendedPropertiesCheckbox",
    )
    use_ssl_checkbox = dialog.findChild(QCheckBox, "useSslCheckbox")
    custom_logon_editor = dialog.findChild(QPlainTextEdit, "customLogonEditor")
    extended_properties_group = dialog.findChild(QGroupBox, "extendedPropertiesGroup")
    backup_connection_group = dialog.findChild(QGroupBox, "backupConnectionGroup")
    ssl_group = dialog.findChild(QGroupBox, "sslGroup")

    assert custom_logon_checkbox is not None
    assert use_extended_properties_checkbox is not None
    assert use_ssl_checkbox is not None
    assert custom_logon_editor is not None
    assert extended_properties_group is not None
    assert backup_connection_group is not None
    assert ssl_group is not None

    assert custom_logon_editor.isEnabled() is False
    assert extended_properties_group.isEnabled() is False
    assert backup_connection_group.isEnabled() is False
    assert ssl_group.isEnabled() is False

    custom_logon_checkbox.click()
    use_extended_properties_checkbox.click()
    use_ssl_checkbox.click()
    qapp.processEvents()

    assert custom_logon_checkbox.isChecked() is True
    assert use_extended_properties_checkbox.isChecked() is True
    assert use_ssl_checkbox.isChecked() is True
    assert custom_logon_editor.isEnabled() is True
    assert extended_properties_group.isEnabled() is True
    assert backup_connection_group.isEnabled() is True
    assert ssl_group.isEnabled() is True

    dialog.close()


def test_create_session_dialog_exports_and_submits_valid_configuration(
    qapp: QApplication,
) -> None:
    dialog = CreateSessionDialog()
    dialog.show()
    qapp.processEvents()

    exported_configs: list[dict[str, object]] = []
    submitted_configs: list[dict[str, object]] = []
    dialog.export_for_console_requested.connect(exported_configs.append)
    dialog.session_config_submitted.connect(submitted_configs.append)

    sender_comp_id_edit = dialog.findChild(QLineEdit, "senderCompIdEdit")
    target_comp_id_edit = dialog.findChild(QLineEdit, "targetCompIdEdit")
    remote_host_edit = dialog.findChild(QLineEdit, "remoteHostEdit")
    export_button = dialog.findChild(QPushButton, "exportForConsoleButton")
    button_box = dialog.findChild(QDialogButtonBox, "createSessionDialogButtonBox")

    assert sender_comp_id_edit is not None
    assert target_comp_id_edit is not None
    assert remote_host_edit is not None
    assert export_button is not None
    assert button_box is not None

    QTest.keyClicks(sender_comp_id_edit, "BUY_SIDE")
    QTest.keyClicks(target_comp_id_edit, "SELL_SIDE")
    QTest.keyClicks(remote_host_edit, "127.0.0.1")
    qapp.processEvents()

    QTest.mouseClick(export_button, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert len(exported_configs) == 1
    assert exported_configs[0]["sender_comp_id"] == "BUY_SIDE"
    assert exported_configs[0]["target_comp_id"] == "SELL_SIDE"
    assert exported_configs[0]["remote_host"] == "127.0.0.1"

    ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
    assert ok_button is not None

    QTest.mouseClick(ok_button, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert len(submitted_configs) == 1
    assert submitted_configs[0]["session_type"] == "Initiator"
    assert submitted_configs[0]["remote_port"] == 9878
    assert dialog.result() == int(dialog.DialogCode.Accepted)
