from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class CreateSessionDialog(QDialog):
    """Dialog for entering a placeholder FIX session configuration."""

    session_config_submitted = Signal(dict)
    export_for_console_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create FIX Session")
        self.setModal(True)
        self.resize(1120, 760)

        self._build_ui()
        self._wire_signals()
        self._apply_initial_state()

    def get_session_config(self) -> dict[str, object]:
        """Collect the current dialog values into a configuration dictionary."""
        session_type = "Initiator" if self._initiator_radio.isChecked() else "Acceptor"
        ssl_protocols = [
            checkbox.text()
            for checkbox in self._ssl_protocol_checkboxes
            if checkbox.isChecked()
        ]

        return {
            "configuration_preset": self._configuration_combo.currentText(),
            "session_type": session_type,
            "sender_comp_id": self._sender_comp_id_edit.text().strip(),
            "target_comp_id": self._target_comp_id_edit.text().strip(),
            "fix_version": self._fix_version_combo.currentText(),
            "remote_host": self._remote_host_edit.text().strip(),
            "remote_port": self._remote_port_spin.value(),
            "heartbeat_interval": self._heartbeat_interval_spin.value(),
            "in_seq_num": self._in_seq_num_spin.value(),
            "out_seq_num": self._out_seq_num_spin.value(),
            "use_custom_logon": self._custom_logon_checkbox.isChecked(),
            "custom_logon_message": self._custom_logon_editor.toPlainText().strip(),
            "persistent_storage_type": self._persistent_storage_checkbox.isChecked(),
            "reset_seq_nums": self._reset_seq_nums_combo.currentText(),
            "use_extended_properties": self._use_extended_properties_checkbox.isChecked(),
            "show_session_messages": self._show_session_messages_checkbox.isChecked(),
            "extended_properties": {
                "SenderSubID": self._sender_sub_id_edit.text().strip(),
                "TargetSubID": self._target_sub_id_edit.text().strip(),
                "SenderLocationID": self._sender_location_id_edit.text().strip(),
                "TargetLocationID": self._target_location_id_edit.text().strip(),
                "Qualifier": self._qualifier_edit.text().strip(),
                "SourceIPAddress": self._source_ip_address_edit.text().strip(),
                "UserName": self._username_edit.text().strip(),
                "Password": self._password_edit.text().strip(),
                "FAST templates": self._fast_templates_edit.text().strip(),
                "Encryption": self._encryption_combo.currentText(),
                "IntradayLogoutToleranceMode": self._intraday_logout_combo.currentText(),
                "ForceSeqNumReset": self._force_seq_num_reset_checkbox.isChecked(),
                "ForcedReconnect": self._forced_reconnect_checkbox.isChecked(),
                "EnableMessageRejecting": self._enable_message_rejecting_checkbox.isChecked(),
                "IgnoreSeqNumTooLowAtLogon": self._ignore_seq_num_low_checkbox.isChecked(),
            },
            "backup_connection": {
                "Host": self._backup_host_edit.text().strip(),
                "Port": self._backup_port_spin.value(),
                "EnableCyclicSwitchToBackupConnection": self._cyclic_backup_checkbox.isChecked(),
                "EnableAutoSwitchToBackupConnection": self._auto_backup_checkbox.isChecked(),
                "KeepConnectionState": self._keep_connection_state_checkbox.isChecked(),
            },
            "use_ssl": self._use_ssl_checkbox.isChecked(),
            "ssl": {
                "protocols": ssl_protocols,
                "Ciphers": self._ssl_ciphers_edit.text().strip(),
                "Certificate": self._certificate_edit.text().strip(),
                "Private Key": self._private_key_edit.text().strip(),
                "Validate Peer Certificate": self._validate_peer_checkbox.isChecked(),
                "CA Certificates file": self._ca_certificates_edit.text().strip(),
            },
        }

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(8)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget(scroll_area)
        columns_layout = QHBoxLayout(content)
        columns_layout.setContentsMargins(0, 0, 0, 0)
        columns_layout.setSpacing(10)
        columns_layout.addWidget(self._build_left_column(), 1)
        columns_layout.addWidget(self._build_right_column(), 1)
        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area, 1)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch()
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        self._button_box.setObjectName("createSessionDialogButtonBox")
        buttons_row.addWidget(self._button_box)
        root_layout.addLayout(buttons_row)

    def _build_left_column(self) -> QWidget:
        column = QWidget(self)
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        required_group = QGroupBox("Required parameters", column)
        form = QFormLayout(required_group)
        form.setContentsMargins(10, 14, 10, 10)
        form.setSpacing(8)

        self._configuration_combo = QComboBox(required_group)
        self._configuration_combo.setObjectName("configurationCombo")
        self._configuration_combo.addItems(
            ["Client", "Initiator", "Acceptor", "Trader"]
        )

        configuration_row = QHBoxLayout()
        configuration_row.setContentsMargins(0, 0, 0, 0)
        configuration_row.setSpacing(6)
        configuration_row.addWidget(self._configuration_combo, 1)
        configuration_row.addWidget(QPushButton("Save", required_group))
        configuration_row.addWidget(QPushButton("Delete", required_group))
        form.addRow(
            "Configuration:", self._wrap_layout(configuration_row, required_group)
        )

        self._initiator_radio = QRadioButton("Initiator", required_group)
        self._acceptor_radio = QRadioButton("Acceptor", required_group)
        self._initiator_radio.setChecked(True)
        self._session_type_group = QButtonGroup(required_group)
        self._session_type_group.addButton(self._initiator_radio)
        self._session_type_group.addButton(self._acceptor_radio)

        session_type_row = QHBoxLayout()
        session_type_row.setContentsMargins(0, 0, 0, 0)
        session_type_row.setSpacing(10)
        session_type_row.addWidget(self._initiator_radio)
        session_type_row.addWidget(self._acceptor_radio)
        session_type_row.addStretch()
        form.addRow(
            "Session type:", self._wrap_layout(session_type_row, required_group)
        )

        self._sender_comp_id_edit = QLineEdit(required_group)
        self._sender_comp_id_edit.setObjectName("senderCompIdEdit")
        form.addRow("SenderCompID:", self._sender_comp_id_edit)

        self._target_comp_id_edit = QLineEdit(required_group)
        self._target_comp_id_edit.setObjectName("targetCompIdEdit")
        form.addRow("TargetCompID:", self._target_comp_id_edit)

        self._fix_version_combo = QComboBox(required_group)
        self._fix_version_combo.addItems(["FIX.4.2", "FIX.4.4"])
        form.addRow("FIX version:", self._fix_version_combo)

        self._remote_host_edit = QLineEdit(required_group)
        self._remote_host_edit.setObjectName("remoteHostEdit")
        self._remote_host_edit.setText("127.0.0.1")
        form.addRow("Remote host:", self._remote_host_edit)

        self._remote_port_spin = self._build_spin_box(required_group, 1, 65535, 9878)
        self._remote_port_spin.setObjectName("remotePortSpin")
        form.addRow("Remote port:", self._remote_port_spin)

        self._heartbeat_interval_spin = self._build_spin_box(required_group, 1, 300, 30)
        self._heartbeat_interval_spin.setObjectName("heartbeatIntervalSpin")
        form.addRow("Heartbeat interval:", self._heartbeat_interval_spin)

        self._in_seq_num_spin = self._build_spin_box(required_group, 1, 999999, 1)
        self._in_seq_num_spin.setObjectName("inSeqNumSpin")
        form.addRow("InSeqNum:", self._in_seq_num_spin)

        self._out_seq_num_spin = self._build_spin_box(required_group, 1, 999999, 1)
        self._out_seq_num_spin.setObjectName("outSeqNumSpin")
        form.addRow("OutSeqNum:", self._out_seq_num_spin)

        self._custom_logon_checkbox = QCheckBox(
            "Use custom Logon message", required_group
        )
        self._custom_logon_checkbox.setObjectName("customLogonCheckbox")
        self._custom_logon_editor = QPlainTextEdit(required_group)
        self._custom_logon_editor.setObjectName("customLogonEditor")
        self._custom_logon_editor.setPlaceholderText(
            "8=FIX.4.4|35=A|49=SENDER|56=TARGET|"
        )
        custom_logon_layout = QVBoxLayout()
        custom_logon_layout.setContentsMargins(0, 0, 0, 0)
        custom_logon_layout.setSpacing(6)
        custom_logon_layout.addWidget(self._custom_logon_checkbox)
        custom_logon_layout.addWidget(self._custom_logon_editor)
        form.addRow("", self._wrap_layout(custom_logon_layout, required_group))

        self._persistent_storage_checkbox = QCheckBox(
            "Persistent storage type", required_group
        )
        self._persistent_storage_checkbox.setObjectName("persistentStorageCheckbox")
        form.addRow("", self._persistent_storage_checkbox)

        self._reset_seq_nums_combo = QComboBox(required_group)
        self._reset_seq_nums_combo.addItems(["Never", "At logon", "Always"])
        form.addRow("Reset SeqNums:", self._reset_seq_nums_combo)

        self._export_button = QPushButton("Export for console", required_group)
        self._export_button.setObjectName("exportForConsoleButton")
        form.addRow("", self._export_button)

        layout.addWidget(required_group)
        layout.addStretch()
        return column

    def _build_right_column(self) -> QWidget:
        column = QWidget(self)
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        toggles_group = QGroupBox("Optional controls", column)
        toggles_layout = QVBoxLayout(toggles_group)
        toggles_layout.setContentsMargins(10, 14, 10, 10)
        toggles_layout.setSpacing(8)

        self._use_extended_properties_checkbox = QCheckBox(
            "Use Extended properties",
            toggles_group,
        )
        self._use_extended_properties_checkbox.setObjectName(
            "useExtendedPropertiesCheckbox"
        )
        self._show_session_messages_checkbox = QCheckBox(
            "Show session messages",
            toggles_group,
        )
        self._show_session_messages_checkbox.setObjectName(
            "showSessionMessagesCheckbox"
        )
        self._show_session_messages_checkbox.setChecked(True)
        self._use_ssl_checkbox = QCheckBox("Use SSL", toggles_group)
        self._use_ssl_checkbox.setObjectName("useSslCheckbox")

        toggles_layout.addWidget(self._use_extended_properties_checkbox)
        toggles_layout.addWidget(self._show_session_messages_checkbox)
        toggles_layout.addWidget(self._use_ssl_checkbox)

        layout.addWidget(toggles_group)
        layout.addWidget(self._build_extended_properties_group())
        layout.addWidget(self._build_backup_connection_group())
        layout.addWidget(self._build_ssl_group())
        layout.addStretch()
        return column

    def _build_extended_properties_group(self) -> QGroupBox:
        self._extended_properties_group = QGroupBox("Extended properties", self)
        self._extended_properties_group.setObjectName("extendedPropertiesGroup")
        form = QFormLayout(self._extended_properties_group)
        form.setContentsMargins(10, 14, 10, 10)
        form.setSpacing(8)

        self._sender_sub_id_edit = QLineEdit(self._extended_properties_group)
        self._target_sub_id_edit = QLineEdit(self._extended_properties_group)
        self._sender_location_id_edit = QLineEdit(self._extended_properties_group)
        self._target_location_id_edit = QLineEdit(self._extended_properties_group)
        self._qualifier_edit = QLineEdit(self._extended_properties_group)
        self._source_ip_address_edit = QLineEdit(self._extended_properties_group)
        self._username_edit = QLineEdit(self._extended_properties_group)
        self._password_edit = QLineEdit(self._extended_properties_group)
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._fast_templates_edit = QLineEdit(self._extended_properties_group)
        self._encryption_combo = QComboBox(self._extended_properties_group)
        self._encryption_combo.addItems(["None", "DES", "TLS"])
        self._intraday_logout_combo = QComboBox(self._extended_properties_group)
        self._intraday_logout_combo.addItems(["Default", "Graceful", "Strict"])

        self._force_seq_num_reset_checkbox = QCheckBox(
            "ForceSeqNumReset",
            self._extended_properties_group,
        )
        self._forced_reconnect_checkbox = QCheckBox(
            "ForcedReconnect",
            self._extended_properties_group,
        )
        self._enable_message_rejecting_checkbox = QCheckBox(
            "EnableMessageRejecting",
            self._extended_properties_group,
        )
        self._ignore_seq_num_low_checkbox = QCheckBox(
            "IgnoreSeqNumTooLowAtLogon",
            self._extended_properties_group,
        )

        form.addRow("SenderSubID:", self._sender_sub_id_edit)
        form.addRow("TargetSubID:", self._target_sub_id_edit)
        form.addRow("SenderLocationID:", self._sender_location_id_edit)
        form.addRow("TargetLocationID:", self._target_location_id_edit)
        form.addRow("Qualifier:", self._qualifier_edit)
        form.addRow("SourceIPAddress:", self._source_ip_address_edit)
        form.addRow("UserName:", self._username_edit)
        form.addRow("Password:", self._password_edit)
        form.addRow("FAST templates:", self._fast_templates_edit)
        form.addRow("Encryption:", self._encryption_combo)
        form.addRow("IntradayLogoutToleranceMode:", self._intraday_logout_combo)
        form.addRow("", self._force_seq_num_reset_checkbox)
        form.addRow("", self._forced_reconnect_checkbox)
        form.addRow("", self._enable_message_rejecting_checkbox)
        form.addRow("", self._ignore_seq_num_low_checkbox)
        return self._extended_properties_group

    def _build_backup_connection_group(self) -> QGroupBox:
        self._backup_connection_group = QGroupBox("Backup connection parameters", self)
        self._backup_connection_group.setObjectName("backupConnectionGroup")
        form = QFormLayout(self._backup_connection_group)
        form.setContentsMargins(10, 14, 10, 10)
        form.setSpacing(8)

        self._backup_host_edit = QLineEdit(self._backup_connection_group)
        self._backup_port_spin = self._build_spin_box(
            self._backup_connection_group,
            1,
            65535,
            9879,
        )
        self._backup_port_spin.setObjectName("backupPortSpin")
        self._cyclic_backup_checkbox = QCheckBox(
            "EnableCyclicSwitchToBackupConnection",
            self._backup_connection_group,
        )
        self._auto_backup_checkbox = QCheckBox(
            "EnableAutoSwitchToBackupConnection",
            self._backup_connection_group,
        )
        self._keep_connection_state_checkbox = QCheckBox(
            "KeepConnectionState",
            self._backup_connection_group,
        )

        form.addRow("Host:", self._backup_host_edit)
        form.addRow("Port:", self._backup_port_spin)
        form.addRow("", self._cyclic_backup_checkbox)
        form.addRow("", self._auto_backup_checkbox)
        form.addRow("", self._keep_connection_state_checkbox)
        return self._backup_connection_group

    def _build_ssl_group(self) -> QGroupBox:
        self._ssl_group = QGroupBox("SSL", self)
        self._ssl_group.setObjectName("sslGroup")
        layout = QVBoxLayout(self._ssl_group)
        layout.setContentsMargins(10, 14, 10, 10)
        layout.setSpacing(8)

        protocol_group = QGroupBox("Protocols", self._ssl_group)
        protocol_layout = QGridLayout(protocol_group)
        protocol_layout.setContentsMargins(10, 14, 10, 10)
        protocol_layout.setSpacing(6)

        protocol_labels = [
            "SSL v2",
            "SSL v3",
            "TLS v1.0",
            "TLS v1.1",
            "TLS v1.2",
            "TLS v1.3",
        ]
        self._ssl_protocol_checkboxes: list[QCheckBox] = []
        for index, label in enumerate(protocol_labels):
            checkbox = QCheckBox(label, protocol_group)
            if label in {"TLS v1.2", "TLS v1.3"}:
                checkbox.setChecked(True)
            self._ssl_protocol_checkboxes.append(checkbox)
            protocol_layout.addWidget(checkbox, index // 3, index % 3)

        form_group = QGroupBox("SSL settings", self._ssl_group)
        form = QFormLayout(form_group)
        form.setContentsMargins(10, 14, 10, 10)
        form.setSpacing(8)

        self._ssl_ciphers_edit = QLineEdit(form_group)
        self._certificate_edit = QLineEdit(form_group)
        self._private_key_edit = QLineEdit(form_group)
        self._ca_certificates_edit = QLineEdit(form_group)
        self._validate_peer_checkbox = QCheckBox(
            "Validate Peer Certificate", form_group
        )
        self._validate_peer_checkbox.setChecked(True)

        form.addRow("Ciphers:", self._ssl_ciphers_edit)
        form.addRow("Certificate:", self._certificate_edit)
        form.addRow("Private Key:", self._private_key_edit)
        form.addRow("", self._validate_peer_checkbox)
        form.addRow("CA Certificates file:", self._ca_certificates_edit)

        layout.addWidget(protocol_group)
        layout.addWidget(form_group)
        return self._ssl_group

    def _wire_signals(self) -> None:
        self._custom_logon_checkbox.toggled.connect(self._on_custom_logon_toggled)
        self._use_extended_properties_checkbox.toggled.connect(
            self._on_extended_properties_toggled
        )
        self._use_ssl_checkbox.toggled.connect(self._on_use_ssl_toggled)
        self._export_button.clicked.connect(self._on_export_for_console_clicked)
        self._button_box.accepted.connect(self._on_accept_clicked)
        self._button_box.rejected.connect(self.reject)

    def _apply_initial_state(self) -> None:
        self._custom_logon_editor.setEnabled(False)
        self._extended_properties_group.setEnabled(False)
        self._backup_connection_group.setEnabled(False)
        self._ssl_group.setEnabled(False)

    def _wrap_layout(
        self, layout: QHBoxLayout | QVBoxLayout, parent: QWidget
    ) -> QWidget:
        container = QWidget(parent)
        container.setLayout(layout)
        return container

    def _build_spin_box(
        self,
        parent: QWidget,
        minimum: int,
        maximum: int,
        value: int,
    ) -> QSpinBox:
        spin_box = QSpinBox(parent)
        spin_box.setRange(minimum, maximum)
        spin_box.setValue(value)
        return spin_box

    def _validate_required_fields(self) -> bool:
        required_fields = (
            (self._sender_comp_id_edit, "SenderCompID"),
            (self._target_comp_id_edit, "TargetCompID"),
            (self._remote_host_edit, "Remote host"),
        )
        for widget, label in required_fields:
            if widget.text().strip():
                continue

            QMessageBox.warning(
                self,
                "Validation Error",
                f"{label} is required before the session can be created.",
            )
            widget.setFocus()
            return False

        if (
            self._custom_logon_checkbox.isChecked()
            and not self._custom_logon_editor.toPlainText().strip()
        ):
            QMessageBox.warning(
                self,
                "Validation Error",
                "Custom Logon message text is required when Use custom Logon message is enabled.",
            )
            self._custom_logon_editor.setFocus()
            return False

        return True

    @Slot(bool)
    def _on_custom_logon_toggled(self, checked: bool) -> None:
        self._custom_logon_editor.setEnabled(checked)

    @Slot(bool)
    def _on_extended_properties_toggled(self, checked: bool) -> None:
        self._extended_properties_group.setEnabled(checked)
        self._backup_connection_group.setEnabled(checked)

    @Slot(bool)
    def _on_use_ssl_toggled(self, checked: bool) -> None:
        self._ssl_group.setEnabled(checked)

    @Slot()
    def _on_export_for_console_clicked(self) -> None:
        self.export_for_console_requested.emit(self.get_session_config())

    @Slot()
    def _on_accept_clicked(self) -> None:
        if not self._validate_required_fields():
            return

        self.session_config_submitted.emit(self.get_session_config())
        self.accept()
