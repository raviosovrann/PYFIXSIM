from __future__ import annotations
from pathlib import Path
import pytest

from src.config.session_config import (
    SessionConfig,
    SessionConfigMissingValueError,
    SessionConfigValidationError,
    load_config,
    save_config,
)


def test_session_config_loads_minimal_ini_with_v1_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "session.cfg"
    config_path.write_text(
        "\n".join(
            [
                "[SESSION]",
                "Host=127.0.0.1",
                "Port=9876",
                "SenderCompID=CLIENT",
                "TargetCompID=SERVER",
                "HeartBtInt=30",
                "ReconnectAttempts=10",
                "FixVersion=FIX.4.2",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.sender_comp_id == "CLIENT"
    assert config.target_comp_id == "SERVER"
    assert config.host == "127.0.0.1"
    assert config.remote_host == "127.0.0.1"
    assert config.port == 9876
    assert config.remote_port == 9876
    assert config.configuration_preset == "Client"
    assert config.session_type == "Initiator"
    assert config.fix_version == "FIX.4.2"
    assert config.heartbeat_interval == 30
    assert config.reconnect_attempts == 10
    assert config.in_seq_num == 1
    assert config.out_seq_num == 1
    assert config.show_session_messages is True
    assert config.use_ssl is False
    assert config.ssl.protocols == ["TLS v1.2", "TLS v1.3"]


def test_session_config_round_trips_nested_settings(tmp_path: Path) -> None:
    config = SessionConfig.from_dict(
        {
            "configuration_preset": "Trader",
            "session_type": "Initiator",
            "sender_comp_id": "BUY_SIDE",
            "target_comp_id": "SELL_SIDE",
            "fix_version": "FIX.4.4",
            "remote_host": "10.0.0.10",
            "remote_port": 7001,
            "heartbeat_interval": 15,
            "reconnect_attempts": 7,
            "in_seq_num": 21,
            "out_seq_num": 34,
            "use_custom_logon": True,
            "custom_logon_message": "8=FIX.4.4|35=A|49=BUY_SIDE|56=SELL_SIDE|",
            "persistent_storage_type": True,
            "reset_seq_nums": "At logon",
            "use_extended_properties": True,
            "show_session_messages": False,
            "extended_properties": {
                "SenderSubID": "DESK1",
                "TargetSubID": "TARGET_DESK",
                "SenderLocationID": "LDN",
                "TargetLocationID": "NYC",
                "Qualifier": "PRIMARY",
                "SourceIPAddress": "10.0.0.20",
                "UserName": "alice",
                "Password": "secret",
                "FAST templates": "templates.xml",
                "Encryption": "TLS",
                "IntradayLogoutToleranceMode": "Graceful",
                "ForceSeqNumReset": True,
                "ForcedReconnect": True,
                "EnableMessageRejecting": True,
                "IgnoreSeqNumTooLowAtLogon": True,
            },
            "backup_connection": {
                "Host": "10.0.0.11",
                "Port": 7002,
                "EnableCyclicSwitchToBackupConnection": True,
                "EnableAutoSwitchToBackupConnection": True,
                "KeepConnectionState": True,
            },
            "use_ssl": True,
            "ssl": {
                "protocols": ["TLS v1.0", "TLS v1.2"],
                "Ciphers": "HIGH:!aNULL",
                "Certificate": "client.pem",
                "Private Key": "client.key",
                "Validate Peer Certificate": False,
                "CA Certificates file": "ca.pem",
            },
        }
    )

    saved_path = save_config(config, tmp_path / "nested" / "session.cfg")
    loaded_config = load_config(saved_path)
    loaded_dict = loaded_config.to_dict()
    backup_connection = loaded_dict["backup_connection"]
    ssl_settings = loaded_dict["ssl"]

    assert saved_path.exists() is True
    assert loaded_config == config
    assert loaded_dict["remote_host"] == "10.0.0.10"
    assert isinstance(backup_connection, dict)
    assert isinstance(ssl_settings, dict)
    assert backup_connection["Host"] == "10.0.0.11"
    assert ssl_settings["protocols"] == ["TLS v1.0", "TLS v1.2"]


def test_session_config_load_raises_typed_error_for_missing_required_values(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "session.cfg"
    config_path.write_text(
        "\n".join(
            [
                "[SESSION]",
                "Host=127.0.0.1",
                "Port=9876",
                "TargetCompID=SERVER",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(SessionConfigMissingValueError) as exc_info:
        load_config(config_path)

    assert exc_info.value.field_name == "SESSION.SenderCompID"


def test_session_config_rejects_invalid_port_values() -> None:
    with pytest.raises(SessionConfigValidationError) as exc_info:
        SessionConfig.from_dict(
            {
                "sender_comp_id": "BUY_SIDE",
                "target_comp_id": "SELL_SIDE",
                "remote_host": "127.0.0.1",
                "remote_port": "not-a-port",
            }
        )

    assert exc_info.value.field_name == "port"
