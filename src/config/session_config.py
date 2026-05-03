from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

_CONFIG_DIRECTORY = Path(__file__).resolve().parent

DEFAULT_SESSION_CONFIG_PATH = _CONFIG_DIRECTORY / "session.cfg"
DEFAULT_SESSION_CONFIG_EXAMPLE_PATH = _CONFIG_DIRECTORY / "session.cfg.example"

_SESSION_SECTION = "SESSION"
_EXTENDED_PROPERTIES_SECTION = "EXTENDED_PROPERTIES"
_BACKUP_CONNECTION_SECTION = "BACKUP_CONNECTION"
_SSL_SECTION = "SSL"

_DEFAULT_CONFIGURATION_PRESET = "Client"
_DEFAULT_SESSION_TYPE = "Initiator"
_DEFAULT_FIX_VERSION = "FIX.4.2"
_DEFAULT_HEARTBEAT_INTERVAL = 30
_DEFAULT_RECONNECT_ATTEMPTS = 10
_DEFAULT_SEQ_NUM = 1
_DEFAULT_REMOTE_PORT = 9878
_DEFAULT_BACKUP_PORT = 9879
_DEFAULT_RESET_SEQ_NUMS = "Never"
_DEFAULT_ENCRYPTION = "None"
_DEFAULT_INTRADAY_LOGOUT_TOLERANCE_MODE = "Default"
_DEFAULT_SSL_PROTOCOLS = ("TLS v1.2", "TLS v1.3")

_ALLOWED_SESSION_TYPES = {"Initiator", "Acceptor"}


class SessionConfigError(Exception):
    """Base exception for FIX session configuration errors."""


class SessionConfigFileError(SessionConfigError):
    """Raised when a configuration file cannot be found, parsed, or written."""


class SessionConfigSectionError(SessionConfigError):
    """Raised when a required configuration section is missing or empty."""

    def __init__(self, section_name: str) -> None:
        super().__init__(f"Missing required configuration section: {section_name}")
        self.section_name = section_name


class SessionConfigMissingValueError(SessionConfigError):
    """Raised when a required configuration value is missing."""

    def __init__(self, field_name: str) -> None:
        super().__init__(f"Missing required configuration value: {field_name}")
        self.field_name = field_name


class SessionConfigValidationError(SessionConfigError):
    """Raised when a configuration value has an invalid type or value or is out of range."""

    def __init__(self, field_name: str, reason: str) -> None:
        super().__init__(f"Invalid configuration value for {field_name}: {reason}")
        self.field_name = field_name
        self.reason = reason


class _CasePreservingConfigParser(ConfigParser):
    """Config parser that preserves option name casing on read and write."""

    def optionxform(self, optionstr: str) -> str:
        return optionstr


def _normalize_path(path: str | Path) -> Path:
    return Path(path).expanduser()


def _resolve_load_path(path: str | Path | None) -> Path:
    if path is not None:
        resolved_path = _normalize_path(path)
        if not resolved_path.exists():
            raise SessionConfigFileError(
                f"Configuration file not found: {resolved_path}"
            )
        return resolved_path

    if DEFAULT_SESSION_CONFIG_PATH.exists():
        return DEFAULT_SESSION_CONFIG_PATH

    if DEFAULT_SESSION_CONFIG_EXAMPLE_PATH.exists():
        return DEFAULT_SESSION_CONFIG_EXAMPLE_PATH

    raise SessionConfigFileError(
        "No configuration file found at either "
        f"{DEFAULT_SESSION_CONFIG_PATH} or {DEFAULT_SESSION_CONFIG_EXAMPLE_PATH}"
    )


def _require_section(parser: ConfigParser, section_name: str) -> None:
    if not parser.has_section(section_name):
        raise SessionConfigSectionError(section_name)


def _read_required_string_option(
    parser: ConfigParser,
    section_name: str,
    option_name: str,
) -> str:
    field_name = f"{section_name}.{option_name}"
    if not parser.has_option(section_name, option_name):
        raise SessionConfigMissingValueError(field_name)

    value = parser.get(section_name, option_name).strip()
    if not value:
        raise SessionConfigMissingValueError(field_name)

    return value


def _read_string_option(
    parser: ConfigParser,
    section_name: str,
    option_name: str,
    fallback: str,
) -> str:
    if not parser.has_section(section_name) or not parser.has_option(
        section_name, option_name
    ):
        return fallback

    return parser.get(section_name, option_name).strip()


def _validate_int_range(
    value: int,
    field_name: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if minimum is not None and value < minimum:
        raise SessionConfigValidationError(field_name, f"must be >= {minimum}")

    if maximum is not None and value > maximum:
        raise SessionConfigValidationError(field_name, f"must be <= {maximum}")

    return value


def _read_int_option(
    parser: ConfigParser,
    section_name: str,
    option_name: str,
    *,
    fallback: int | None = None,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    field_name = f"{section_name}.{option_name}"
    if not parser.has_section(section_name) or not parser.has_option(
        section_name, option_name
    ):
        if fallback is None:
            raise SessionConfigMissingValueError(field_name)
        return _validate_int_range(
            fallback,
            field_name,
            minimum=minimum,
            maximum=maximum,
        )

    raw_value = parser.get(section_name, option_name).strip()
    if not raw_value:
        if fallback is None:
            raise SessionConfigMissingValueError(field_name)
        return _validate_int_range(
            fallback,
            field_name,
            minimum=minimum,
            maximum=maximum,
        )

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise SessionConfigValidationError(
            field_name,
            f"expected integer, got {raw_value!r}",
        ) from exc

    return _validate_int_range(
        value,
        field_name,
        minimum=minimum,
        maximum=maximum,
    )


def _read_bool_option(
    parser: ConfigParser,
    section_name: str,
    option_name: str,
    *,
    fallback: bool,
) -> bool:
    field_name = f"{section_name}.{option_name}"
    if not parser.has_section(section_name) or not parser.has_option(
        section_name, option_name
    ):
        return fallback

    try:
        return parser.getboolean(section_name, option_name)
    except ValueError as exc:
        raw_value = parser.get(section_name, option_name)
        raise SessionConfigValidationError(
            field_name,
            f"expected boolean, got {raw_value!r}",
        ) from exc


def _coerce_required_string(value: object, field_name: str) -> str:
    if value is None:
        raise SessionConfigMissingValueError(field_name)

    coerced_value = str(value).strip()
    if not coerced_value:
        raise SessionConfigMissingValueError(field_name)

    return coerced_value


def _coerce_optional_string(value: object, field_name: str) -> str:
    if value is None:
        return ""

    if isinstance(value, bytes):
        raise SessionConfigValidationError(field_name, "expected text, got bytes")

    return str(value).strip()


def _coerce_bool(value: object, field_name: str, *, fallback: bool) -> bool:
    if value is None:
        return fallback

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        normalized_value = value.strip().lower()
        if normalized_value in {"1", "true", "yes", "on"}:
            return True
        if normalized_value in {"0", "false", "no", "off"}:
            return False

    raise SessionConfigValidationError(field_name, f"expected boolean, got {value!r}")


def _coerce_int(
    value: object,
    field_name: str,
    *,
    fallback: int | None = None,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if value is None:
        if fallback is None:
            raise SessionConfigMissingValueError(field_name)
        return _validate_int_range(
            fallback,
            field_name,
            minimum=minimum,
            maximum=maximum,
        )

    if isinstance(value, bool):
        raise SessionConfigValidationError(
            field_name,
            f"expected integer, got {value!r}",
        )

    if isinstance(value, int):
        return _validate_int_range(
            value,
            field_name,
            minimum=minimum,
            maximum=maximum,
        )

    if isinstance(value, str):
        try:
            int_value = int(value.strip())
        except ValueError as exc:
            raise SessionConfigValidationError(
                field_name,
                f"expected integer, got {value!r}",
            ) from exc
        return _validate_int_range(
            int_value,
            field_name,
            minimum=minimum,
            maximum=maximum,
        )

    raise SessionConfigValidationError(field_name, f"expected integer, got {value!r}")


def _coerce_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if value is None:
        return {}

    if isinstance(value, Mapping):
        return value

    raise SessionConfigValidationError(
        field_name,
        f"expected mapping, got {type(value).__name__}",
    )


def _mapping_string(
    mapping: Mapping[str, object],
    key: str,
    field_name: str,
    *,
    default: str = "",
) -> str:
    value = mapping.get(key)
    if value is None:
        return default

    text = _coerce_optional_string(value, field_name)
    return text or default


def _mapping_required_string(
    mapping: Mapping[str, object],
    key: str,
    field_name: str,
) -> str:
    return _coerce_required_string(mapping.get(key), field_name)


def _mapping_bool(
    mapping: Mapping[str, object],
    key: str,
    field_name: str,
    *,
    fallback: bool,
) -> bool:
    return _coerce_bool(mapping.get(key), field_name, fallback=fallback)


def _mapping_int(
    mapping: Mapping[str, object],
    key: str,
    field_name: str,
    *,
    fallback: int | None = None,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    return _coerce_int(
        mapping.get(key),
        field_name,
        fallback=fallback,
        minimum=minimum,
        maximum=maximum,
    )


def _normalize_protocols(protocols: Sequence[object]) -> list[str]:
    normalized_protocols: list[str] = []
    seen_protocols: set[str] = set()
    for raw_protocol in protocols:
        protocol = _coerce_optional_string(raw_protocol, "ssl.protocols")
        if not protocol or protocol in seen_protocols:
            continue
        normalized_protocols.append(protocol)
        seen_protocols.add(protocol)

    return normalized_protocols


def _coerce_protocols(value: object, *, fallback: Sequence[str]) -> list[str]:
    if value is None:
        return list(fallback)

    if isinstance(value, str):
        return _normalize_protocols(value.split(","))

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return _normalize_protocols(value)

    raise SessionConfigValidationError(
        "ssl.protocols",
        f"expected sequence, got {value!r}",
    )


def _serialize_bool(value: bool) -> str:
    return "true" if value else "false"


def _serialize_protocols(protocols: Sequence[str]) -> str:
    return ", ".join(protocols)


@dataclass(slots=True)
class ExtendedPropertiesConfig:
    """Optional extended FIX session properties collected by the UI."""

    sender_sub_id: str = ""
    target_sub_id: str = ""
    sender_location_id: str = ""
    target_location_id: str = ""
    qualifier: str = ""
    source_ip_address: str = ""
    username: str = ""
    password: str = ""
    fast_templates: str = ""
    encryption: str = _DEFAULT_ENCRYPTION
    intraday_logout_tolerance_mode: str = _DEFAULT_INTRADAY_LOGOUT_TOLERANCE_MODE
    force_seq_num_reset: bool = False
    forced_reconnect: bool = False
    enable_message_rejecting: bool = False
    ignore_seq_num_too_low_at_logon: bool = False

    def __post_init__(self) -> None:
        self.sender_sub_id = _coerce_optional_string(
            self.sender_sub_id,
            "extended_properties.sender_sub_id",
        )
        self.target_sub_id = _coerce_optional_string(
            self.target_sub_id,
            "extended_properties.target_sub_id",
        )
        self.sender_location_id = _coerce_optional_string(
            self.sender_location_id,
            "extended_properties.sender_location_id",
        )
        self.target_location_id = _coerce_optional_string(
            self.target_location_id,
            "extended_properties.target_location_id",
        )
        self.qualifier = _coerce_optional_string(
            self.qualifier,
            "extended_properties.qualifier",
        )
        self.source_ip_address = _coerce_optional_string(
            self.source_ip_address,
            "extended_properties.source_ip_address",
        )
        self.username = _coerce_optional_string(
            self.username,
            "extended_properties.username",
        )
        self.password = _coerce_optional_string(
            self.password,
            "extended_properties.password",
        )
        self.fast_templates = _coerce_optional_string(
            self.fast_templates,
            "extended_properties.fast_templates",
        )
        self.encryption = self.encryption or _DEFAULT_ENCRYPTION
        self.intraday_logout_tolerance_mode = (
            self.intraday_logout_tolerance_mode
            or _DEFAULT_INTRADAY_LOGOUT_TOLERANCE_MODE
        )
        self.force_seq_num_reset = _coerce_bool(
            self.force_seq_num_reset,
            "extended_properties.force_seq_num_reset",
            fallback=False,
        )
        self.forced_reconnect = _coerce_bool(
            self.forced_reconnect,
            "extended_properties.forced_reconnect",
            fallback=False,
        )
        self.enable_message_rejecting = _coerce_bool(
            self.enable_message_rejecting,
            "extended_properties.enable_message_rejecting",
            fallback=False,
        )
        self.ignore_seq_num_too_low_at_logon = _coerce_bool(
            self.ignore_seq_num_too_low_at_logon,
            "extended_properties.ignore_seq_num_too_low_at_logon",
            fallback=False,
        )

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, object] | None = None,
    ) -> "ExtendedPropertiesConfig":
        mapping = _coerce_mapping(data, "extended_properties")
        return cls(
            sender_sub_id=_mapping_string(
                mapping,
                "SenderSubID",
                "extended_properties.SenderSubID",
            ),
            target_sub_id=_mapping_string(
                mapping,
                "TargetSubID",
                "extended_properties.TargetSubID",
            ),
            sender_location_id=_mapping_string(
                mapping,
                "SenderLocationID",
                "extended_properties.SenderLocationID",
            ),
            target_location_id=_mapping_string(
                mapping,
                "TargetLocationID",
                "extended_properties.TargetLocationID",
            ),
            qualifier=_mapping_string(
                mapping,
                "Qualifier",
                "extended_properties.Qualifier",
            ),
            source_ip_address=_mapping_string(
                mapping,
                "SourceIPAddress",
                "extended_properties.SourceIPAddress",
            ),
            username=_mapping_string(
                mapping,
                "UserName",
                "extended_properties.UserName",
            ),
            password=_mapping_string(
                mapping,
                "Password",
                "extended_properties.Password",
            ),
            fast_templates=_mapping_string(
                mapping,
                "FAST templates",
                "extended_properties.FAST templates",
            ),
            encryption=_mapping_string(
                mapping,
                "Encryption",
                "extended_properties.Encryption",
                default=_DEFAULT_ENCRYPTION,
            ),
            intraday_logout_tolerance_mode=_mapping_string(
                mapping,
                "IntradayLogoutToleranceMode",
                "extended_properties.IntradayLogoutToleranceMode",
                default=_DEFAULT_INTRADAY_LOGOUT_TOLERANCE_MODE,
            ),
            force_seq_num_reset=_mapping_bool(
                mapping,
                "ForceSeqNumReset",
                "extended_properties.ForceSeqNumReset",
                fallback=False,
            ),
            forced_reconnect=_mapping_bool(
                mapping,
                "ForcedReconnect",
                "extended_properties.ForcedReconnect",
                fallback=False,
            ),
            enable_message_rejecting=_mapping_bool(
                mapping,
                "EnableMessageRejecting",
                "extended_properties.EnableMessageRejecting",
                fallback=False,
            ),
            ignore_seq_num_too_low_at_logon=_mapping_bool(
                mapping,
                "IgnoreSeqNumTooLowAtLogon",
                "extended_properties.IgnoreSeqNumTooLowAtLogon",
                fallback=False,
            ),
        )

    @classmethod
    def from_parser(cls, parser: ConfigParser) -> "ExtendedPropertiesConfig":
        return cls(
            sender_sub_id=_read_string_option(
                parser,
                _EXTENDED_PROPERTIES_SECTION,
                "SenderSubID",
                "",
            ),
            target_sub_id=_read_string_option(
                parser,
                _EXTENDED_PROPERTIES_SECTION,
                "TargetSubID",
                "",
            ),
            sender_location_id=_read_string_option(
                parser,
                _EXTENDED_PROPERTIES_SECTION,
                "SenderLocationID",
                "",
            ),
            target_location_id=_read_string_option(
                parser,
                _EXTENDED_PROPERTIES_SECTION,
                "TargetLocationID",
                "",
            ),
            qualifier=_read_string_option(
                parser,
                _EXTENDED_PROPERTIES_SECTION,
                "Qualifier",
                "",
            ),
            source_ip_address=_read_string_option(
                parser,
                _EXTENDED_PROPERTIES_SECTION,
                "SourceIPAddress",
                "",
            ),
            username=_read_string_option(
                parser,
                _EXTENDED_PROPERTIES_SECTION,
                "UserName",
                "",
            ),
            password=_read_string_option(
                parser,
                _EXTENDED_PROPERTIES_SECTION,
                "Password",
                "",
            ),
            fast_templates=_read_string_option(
                parser,
                _EXTENDED_PROPERTIES_SECTION,
                "FAST templates",
                "",
            ),
            encryption=_read_string_option(
                parser,
                _EXTENDED_PROPERTIES_SECTION,
                "Encryption",
                _DEFAULT_ENCRYPTION,
            ),
            intraday_logout_tolerance_mode=_read_string_option(
                parser,
                _EXTENDED_PROPERTIES_SECTION,
                "IntradayLogoutToleranceMode",
                _DEFAULT_INTRADAY_LOGOUT_TOLERANCE_MODE,
            ),
            force_seq_num_reset=_read_bool_option(
                parser,
                _EXTENDED_PROPERTIES_SECTION,
                "ForceSeqNumReset",
                fallback=False,
            ),
            forced_reconnect=_read_bool_option(
                parser,
                _EXTENDED_PROPERTIES_SECTION,
                "ForcedReconnect",
                fallback=False,
            ),
            enable_message_rejecting=_read_bool_option(
                parser,
                _EXTENDED_PROPERTIES_SECTION,
                "EnableMessageRejecting",
                fallback=False,
            ),
            ignore_seq_num_too_low_at_logon=_read_bool_option(
                parser,
                _EXTENDED_PROPERTIES_SECTION,
                "IgnoreSeqNumTooLowAtLogon",
                fallback=False,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "SenderSubID": self.sender_sub_id,
            "TargetSubID": self.target_sub_id,
            "SenderLocationID": self.sender_location_id,
            "TargetLocationID": self.target_location_id,
            "Qualifier": self.qualifier,
            "SourceIPAddress": self.source_ip_address,
            "UserName": self.username,
            "Password": self.password,
            "FAST templates": self.fast_templates,
            "Encryption": self.encryption,
            "IntradayLogoutToleranceMode": self.intraday_logout_tolerance_mode,
            "ForceSeqNumReset": self.force_seq_num_reset,
            "ForcedReconnect": self.forced_reconnect,
            "EnableMessageRejecting": self.enable_message_rejecting,
            "IgnoreSeqNumTooLowAtLogon": self.ignore_seq_num_too_low_at_logon,
        }

    def to_section(self) -> dict[str, str]:
        return {
            "SenderSubID": self.sender_sub_id,
            "TargetSubID": self.target_sub_id,
            "SenderLocationID": self.sender_location_id,
            "TargetLocationID": self.target_location_id,
            "Qualifier": self.qualifier,
            "SourceIPAddress": self.source_ip_address,
            "UserName": self.username,
            "Password": self.password,
            "FAST templates": self.fast_templates,
            "Encryption": self.encryption,
            "IntradayLogoutToleranceMode": self.intraday_logout_tolerance_mode,
            "ForceSeqNumReset": _serialize_bool(self.force_seq_num_reset),
            "ForcedReconnect": _serialize_bool(self.forced_reconnect),
            "EnableMessageRejecting": _serialize_bool(self.enable_message_rejecting),
            "IgnoreSeqNumTooLowAtLogon": _serialize_bool(
                self.ignore_seq_num_too_low_at_logon
            ),
        }


@dataclass(slots=True)
class BackupConnectionConfig:
    """Optional backup connection details for a FIX session."""

    host: str = ""
    port: int = _DEFAULT_BACKUP_PORT
    enable_cyclic_switch_to_backup_connection: bool = False
    enable_auto_switch_to_backup_connection: bool = False
    keep_connection_state: bool = False

    def __post_init__(self) -> None:
        self.host = _coerce_optional_string(self.host, "backup_connection.host")
        self.port = _coerce_int(
            self.port,
            "backup_connection.port",
            fallback=_DEFAULT_BACKUP_PORT,
            minimum=1,
            maximum=65535,
        )
        self.enable_cyclic_switch_to_backup_connection = _coerce_bool(
            self.enable_cyclic_switch_to_backup_connection,
            "backup_connection.enable_cyclic_switch_to_backup_connection",
            fallback=False,
        )
        self.enable_auto_switch_to_backup_connection = _coerce_bool(
            self.enable_auto_switch_to_backup_connection,
            "backup_connection.enable_auto_switch_to_backup_connection",
            fallback=False,
        )
        self.keep_connection_state = _coerce_bool(
            self.keep_connection_state,
            "backup_connection.keep_connection_state",
            fallback=False,
        )

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, object] | None = None,
    ) -> "BackupConnectionConfig":
        mapping = _coerce_mapping(data, "backup_connection")
        return cls(
            host=_mapping_string(mapping, "Host", "backup_connection.Host"),
            port=_mapping_int(
                mapping,
                "Port",
                "backup_connection.Port",
                fallback=_DEFAULT_BACKUP_PORT,
                minimum=1,
                maximum=65535,
            ),
            enable_cyclic_switch_to_backup_connection=_mapping_bool(
                mapping,
                "EnableCyclicSwitchToBackupConnection",
                "backup_connection.EnableCyclicSwitchToBackupConnection",
                fallback=False,
            ),
            enable_auto_switch_to_backup_connection=_mapping_bool(
                mapping,
                "EnableAutoSwitchToBackupConnection",
                "backup_connection.EnableAutoSwitchToBackupConnection",
                fallback=False,
            ),
            keep_connection_state=_mapping_bool(
                mapping,
                "KeepConnectionState",
                "backup_connection.KeepConnectionState",
                fallback=False,
            ),
        )

    @classmethod
    def from_parser(cls, parser: ConfigParser) -> "BackupConnectionConfig":
        return cls(
            host=_read_string_option(parser, _BACKUP_CONNECTION_SECTION, "Host", ""),
            port=_read_int_option(
                parser,
                _BACKUP_CONNECTION_SECTION,
                "Port",
                fallback=_DEFAULT_BACKUP_PORT,
                minimum=1,
                maximum=65535,
            ),
            enable_cyclic_switch_to_backup_connection=_read_bool_option(
                parser,
                _BACKUP_CONNECTION_SECTION,
                "EnableCyclicSwitchToBackupConnection",
                fallback=False,
            ),
            enable_auto_switch_to_backup_connection=_read_bool_option(
                parser,
                _BACKUP_CONNECTION_SECTION,
                "EnableAutoSwitchToBackupConnection",
                fallback=False,
            ),
            keep_connection_state=_read_bool_option(
                parser,
                _BACKUP_CONNECTION_SECTION,
                "KeepConnectionState",
                fallback=False,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "Host": self.host,
            "Port": self.port,
            "EnableCyclicSwitchToBackupConnection": (
                self.enable_cyclic_switch_to_backup_connection
            ),
            "EnableAutoSwitchToBackupConnection": (
                self.enable_auto_switch_to_backup_connection
            ),
            "KeepConnectionState": self.keep_connection_state,
        }

    def to_section(self) -> dict[str, str]:
        return {
            "Host": self.host,
            "Port": str(self.port),
            "EnableCyclicSwitchToBackupConnection": _serialize_bool(
                self.enable_cyclic_switch_to_backup_connection
            ),
            "EnableAutoSwitchToBackupConnection": _serialize_bool(
                self.enable_auto_switch_to_backup_connection
            ),
            "KeepConnectionState": _serialize_bool(self.keep_connection_state),
        }


@dataclass(slots=True)
class SSLConfig:
    """Optional SSL/TLS settings for a FIX session."""

    protocols: list[str] = field(default_factory=lambda: list(_DEFAULT_SSL_PROTOCOLS))
    ciphers: str = ""
    certificate: str = ""
    private_key: str = ""
    validate_peer_certificate: bool = True
    ca_certificates_file: str = ""

    def __post_init__(self) -> None:
        self.protocols = _coerce_protocols(
            self.protocols,
            fallback=_DEFAULT_SSL_PROTOCOLS,
        )
        self.ciphers = _coerce_optional_string(self.ciphers, "ssl.ciphers")
        self.certificate = _coerce_optional_string(self.certificate, "ssl.certificate")
        self.private_key = _coerce_optional_string(self.private_key, "ssl.private_key")
        self.validate_peer_certificate = _coerce_bool(
            self.validate_peer_certificate,
            "ssl.validate_peer_certificate",
            fallback=True,
        )
        self.ca_certificates_file = _coerce_optional_string(
            self.ca_certificates_file,
            "ssl.ca_certificates_file",
        )

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, object] | None = None,
    ) -> "SSLConfig":
        mapping = _coerce_mapping(data, "ssl")
        return cls(
            protocols=_coerce_protocols(
                mapping.get("protocols"),
                fallback=_DEFAULT_SSL_PROTOCOLS,
            ),
            ciphers=_mapping_string(mapping, "Ciphers", "ssl.Ciphers"),
            certificate=_mapping_string(mapping, "Certificate", "ssl.Certificate"),
            private_key=_mapping_string(mapping, "Private Key", "ssl.Private Key"),
            validate_peer_certificate=_mapping_bool(
                mapping,
                "Validate Peer Certificate",
                "ssl.Validate Peer Certificate",
                fallback=True,
            ),
            ca_certificates_file=_mapping_string(
                mapping,
                "CA Certificates file",
                "ssl.CA Certificates file",
            ),
        )

    @classmethod
    def from_parser(cls, parser: ConfigParser) -> "SSLConfig":
        return cls(
            protocols=_coerce_protocols(
                _read_string_option(
                    parser,
                    _SSL_SECTION,
                    "Protocols",
                    _serialize_protocols(_DEFAULT_SSL_PROTOCOLS),
                ),
                fallback=_DEFAULT_SSL_PROTOCOLS,
            ),
            ciphers=_read_string_option(parser, _SSL_SECTION, "Ciphers", ""),
            certificate=_read_string_option(parser, _SSL_SECTION, "Certificate", ""),
            private_key=_read_string_option(parser, _SSL_SECTION, "Private Key", ""),
            validate_peer_certificate=_read_bool_option(
                parser,
                _SSL_SECTION,
                "Validate Peer Certificate",
                fallback=True,
            ),
            ca_certificates_file=_read_string_option(
                parser,
                _SSL_SECTION,
                "CA Certificates file",
                "",
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "protocols": list(self.protocols),
            "Ciphers": self.ciphers,
            "Certificate": self.certificate,
            "Private Key": self.private_key,
            "Validate Peer Certificate": self.validate_peer_certificate,
            "CA Certificates file": self.ca_certificates_file,
        }

    def to_section(self) -> dict[str, str]:
        return {
            "Protocols": _serialize_protocols(self.protocols),
            "Ciphers": self.ciphers,
            "Certificate": self.certificate,
            "Private Key": self.private_key,
            "Validate Peer Certificate": _serialize_bool(
                self.validate_peer_certificate
            ),
            "CA Certificates file": self.ca_certificates_file,
        }


@dataclass(slots=True)
class SessionConfig:
    """Typed FIX session configuration with load/save helpers."""

    sender_comp_id: str
    target_comp_id: str
    host: str
    port: int
    configuration_preset: str = _DEFAULT_CONFIGURATION_PRESET
    session_type: str = _DEFAULT_SESSION_TYPE
    fix_version: str = _DEFAULT_FIX_VERSION
    heartbeat_interval: int = _DEFAULT_HEARTBEAT_INTERVAL
    reconnect_attempts: int = _DEFAULT_RECONNECT_ATTEMPTS
    in_seq_num: int = _DEFAULT_SEQ_NUM
    out_seq_num: int = _DEFAULT_SEQ_NUM
    use_custom_logon: bool = False
    custom_logon_message: str = ""
    persistent_storage_type: bool = False
    reset_seq_nums: str = _DEFAULT_RESET_SEQ_NUMS
    use_extended_properties: bool = False
    show_session_messages: bool = True
    extended_properties: ExtendedPropertiesConfig = field(
        default_factory=ExtendedPropertiesConfig
    )
    backup_connection: BackupConnectionConfig = field(
        default_factory=BackupConnectionConfig
    )
    use_ssl: bool = False
    ssl: SSLConfig = field(default_factory=SSLConfig)

    def __post_init__(self) -> None:
        if isinstance(self.extended_properties, Mapping):
            self.extended_properties = ExtendedPropertiesConfig.from_mapping(
                self.extended_properties
            )
        elif not isinstance(self.extended_properties, ExtendedPropertiesConfig):
            raise SessionConfigValidationError(
                "extended_properties",
                "expected ExtendedPropertiesConfig or mapping",
            )

        if isinstance(self.backup_connection, Mapping):
            self.backup_connection = BackupConnectionConfig.from_mapping(
                self.backup_connection
            )
        elif not isinstance(self.backup_connection, BackupConnectionConfig):
            raise SessionConfigValidationError(
                "backup_connection",
                "expected BackupConnectionConfig or mapping",
            )

        if isinstance(self.ssl, Mapping):
            self.ssl = SSLConfig.from_mapping(self.ssl)
        elif not isinstance(self.ssl, SSLConfig):
            raise SessionConfigValidationError(
                "ssl",
                "expected SSLConfig or mapping",
            )

        self.sender_comp_id = _coerce_required_string(
            self.sender_comp_id,
            "sender_comp_id",
        )
        self.target_comp_id = _coerce_required_string(
            self.target_comp_id,
            "target_comp_id",
        )
        self.host = _coerce_required_string(self.host, "host")
        self.port = _coerce_int(self.port, "port", minimum=1, maximum=65535)
        self.configuration_preset = (
            _coerce_optional_string(
                self.configuration_preset,
                "configuration_preset",
            )
            or _DEFAULT_CONFIGURATION_PRESET
        )
        self.session_type = (
            _coerce_optional_string(self.session_type, "session_type")
            or _DEFAULT_SESSION_TYPE
        )
        if self.session_type not in _ALLOWED_SESSION_TYPES:
            raise SessionConfigValidationError(
                "session_type",
                f"must be one of {sorted(_ALLOWED_SESSION_TYPES)}",
            )

        self.fix_version = _coerce_required_string(self.fix_version, "fix_version")
        self.heartbeat_interval = _coerce_int(
            self.heartbeat_interval,
            "heartbeat_interval",
            minimum=1,
        )
        self.reconnect_attempts = _coerce_int(
            self.reconnect_attempts,
            "reconnect_attempts",
            minimum=1,
        )
        self.in_seq_num = _coerce_int(self.in_seq_num, "in_seq_num", minimum=1)
        self.out_seq_num = _coerce_int(self.out_seq_num, "out_seq_num", minimum=1)
        self.use_custom_logon = _coerce_bool(
            self.use_custom_logon,
            "use_custom_logon",
            fallback=False,
        )
        self.custom_logon_message = _coerce_optional_string(
            self.custom_logon_message,
            "custom_logon_message",
        )
        if self.use_custom_logon and not self.custom_logon_message:
            raise SessionConfigMissingValueError("custom_logon_message")

        self.persistent_storage_type = _coerce_bool(
            self.persistent_storage_type,
            "persistent_storage_type",
            fallback=False,
        )
        self.reset_seq_nums = (
            _coerce_optional_string(self.reset_seq_nums, "reset_seq_nums")
            or _DEFAULT_RESET_SEQ_NUMS
        )
        self.use_extended_properties = _coerce_bool(
            self.use_extended_properties,
            "use_extended_properties",
            fallback=False,
        )
        self.show_session_messages = _coerce_bool(
            self.show_session_messages,
            "show_session_messages",
            fallback=True,
        )
        self.use_ssl = _coerce_bool(self.use_ssl, "use_ssl", fallback=False)

    @property
    def remote_host(self) -> str:
        return self.host

    @property
    def remote_port(self) -> int:
        return self.port

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "SessionConfig":
        mapping = _coerce_mapping(data, "session_config")
        raw_host = (
            mapping["remote_host"] if "remote_host" in mapping else mapping.get("host")
        )
        raw_port = (
            mapping["remote_port"]
            if "remote_port" in mapping
            else mapping.get("port", _DEFAULT_REMOTE_PORT)
        )

        return cls(
            configuration_preset=_mapping_string(
                mapping,
                "configuration_preset",
                "configuration_preset",
                default=_DEFAULT_CONFIGURATION_PRESET,
            ),
            session_type=_mapping_string(
                mapping,
                "session_type",
                "session_type",
                default=_DEFAULT_SESSION_TYPE,
            ),
            sender_comp_id=_mapping_required_string(
                mapping,
                "sender_comp_id",
                "sender_comp_id",
            ),
            target_comp_id=_mapping_required_string(
                mapping,
                "target_comp_id",
                "target_comp_id",
            ),
            fix_version=_mapping_string(
                mapping,
                "fix_version",
                "fix_version",
                default=_DEFAULT_FIX_VERSION,
            ),
            host=_coerce_required_string(raw_host, "host"),
            port=_coerce_int(raw_port, "port", minimum=1, maximum=65535),
            heartbeat_interval=_mapping_int(
                mapping,
                "heartbeat_interval",
                "heartbeat_interval",
                fallback=_DEFAULT_HEARTBEAT_INTERVAL,
                minimum=1,
            ),
            reconnect_attempts=_mapping_int(
                mapping,
                "reconnect_attempts",
                "reconnect_attempts",
                fallback=_DEFAULT_RECONNECT_ATTEMPTS,
                minimum=1,
            ),
            in_seq_num=_mapping_int(
                mapping,
                "in_seq_num",
                "in_seq_num",
                fallback=_DEFAULT_SEQ_NUM,
                minimum=1,
            ),
            out_seq_num=_mapping_int(
                mapping,
                "out_seq_num",
                "out_seq_num",
                fallback=_DEFAULT_SEQ_NUM,
                minimum=1,
            ),
            use_custom_logon=_mapping_bool(
                mapping,
                "use_custom_logon",
                "use_custom_logon",
                fallback=False,
            ),
            custom_logon_message=_mapping_string(
                mapping,
                "custom_logon_message",
                "custom_logon_message",
            ),
            persistent_storage_type=_mapping_bool(
                mapping,
                "persistent_storage_type",
                "persistent_storage_type",
                fallback=False,
            ),
            reset_seq_nums=_mapping_string(
                mapping,
                "reset_seq_nums",
                "reset_seq_nums",
                default=_DEFAULT_RESET_SEQ_NUMS,
            ),
            use_extended_properties=_mapping_bool(
                mapping,
                "use_extended_properties",
                "use_extended_properties",
                fallback=False,
            ),
            show_session_messages=_mapping_bool(
                mapping,
                "show_session_messages",
                "show_session_messages",
                fallback=True,
            ),
            extended_properties=ExtendedPropertiesConfig.from_mapping(
                _coerce_mapping(
                    mapping.get("extended_properties"), "extended_properties"
                )
            ),
            backup_connection=BackupConnectionConfig.from_mapping(
                _coerce_mapping(mapping.get("backup_connection"), "backup_connection")
            ),
            use_ssl=_mapping_bool(mapping, "use_ssl", "use_ssl", fallback=False),
            ssl=SSLConfig.from_mapping(_coerce_mapping(mapping.get("ssl"), "ssl")),
        )

    @classmethod
    def load(cls, path: str | Path | None = None) -> "SessionConfig":
        resolved_path = _resolve_load_path(path)
        parser = _CasePreservingConfigParser(interpolation=None)

        try:
            with resolved_path.open("r", encoding="utf-8") as config_file:
                parser.read_file(config_file)
        except FileNotFoundError as exc:
            raise SessionConfigFileError(
                f"Configuration file not found: {resolved_path}"
            ) from exc

        _require_section(parser, _SESSION_SECTION)

        return cls(
            configuration_preset=_read_string_option(
                parser,
                _SESSION_SECTION,
                "ConfigurationPreset",
                _DEFAULT_CONFIGURATION_PRESET,
            ),
            session_type=_read_string_option(
                parser,
                _SESSION_SECTION,
                "SessionType",
                _DEFAULT_SESSION_TYPE,
            ),
            sender_comp_id=_read_required_string_option(
                parser,
                _SESSION_SECTION,
                "SenderCompID",
            ),
            target_comp_id=_read_required_string_option(
                parser,
                _SESSION_SECTION,
                "TargetCompID",
            ),
            fix_version=_read_string_option(
                parser,
                _SESSION_SECTION,
                "FixVersion",
                _DEFAULT_FIX_VERSION,
            ),
            host=_read_required_string_option(parser, _SESSION_SECTION, "Host"),
            port=_read_int_option(
                parser,
                _SESSION_SECTION,
                "Port",
                minimum=1,
                maximum=65535,
            ),
            heartbeat_interval=_read_int_option(
                parser,
                _SESSION_SECTION,
                "HeartBtInt",
                fallback=_DEFAULT_HEARTBEAT_INTERVAL,
                minimum=1,
            ),
            reconnect_attempts=_read_int_option(
                parser,
                _SESSION_SECTION,
                "ReconnectAttempts",
                fallback=_DEFAULT_RECONNECT_ATTEMPTS,
                minimum=1,
            ),
            in_seq_num=_read_int_option(
                parser,
                _SESSION_SECTION,
                "InSeqNum",
                fallback=_DEFAULT_SEQ_NUM,
                minimum=1,
            ),
            out_seq_num=_read_int_option(
                parser,
                _SESSION_SECTION,
                "OutSeqNum",
                fallback=_DEFAULT_SEQ_NUM,
                minimum=1,
            ),
            use_custom_logon=_read_bool_option(
                parser,
                _SESSION_SECTION,
                "UseCustomLogon",
                fallback=False,
            ),
            custom_logon_message=_read_string_option(
                parser,
                _SESSION_SECTION,
                "CustomLogonMessage",
                "",
            ),
            persistent_storage_type=_read_bool_option(
                parser,
                _SESSION_SECTION,
                "PersistentStorageType",
                fallback=False,
            ),
            reset_seq_nums=_read_string_option(
                parser,
                _SESSION_SECTION,
                "ResetSeqNums",
                _DEFAULT_RESET_SEQ_NUMS,
            ),
            use_extended_properties=_read_bool_option(
                parser,
                _SESSION_SECTION,
                "UseExtendedProperties",
                fallback=False,
            ),
            show_session_messages=_read_bool_option(
                parser,
                _SESSION_SECTION,
                "ShowSessionMessages",
                fallback=True,
            ),
            extended_properties=ExtendedPropertiesConfig.from_parser(parser),
            backup_connection=BackupConnectionConfig.from_parser(parser),
            use_ssl=_read_bool_option(
                parser, _SESSION_SECTION, "UseSSL", fallback=False
            ),
            ssl=SSLConfig.from_parser(parser),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "configuration_preset": self.configuration_preset,
            "session_type": self.session_type,
            "sender_comp_id": self.sender_comp_id,
            "target_comp_id": self.target_comp_id,
            "fix_version": self.fix_version,
            "host": self.host,
            "port": self.port,
            "remote_host": self.host,
            "remote_port": self.port,
            "heartbeat_interval": self.heartbeat_interval,
            "reconnect_attempts": self.reconnect_attempts,
            "in_seq_num": self.in_seq_num,
            "out_seq_num": self.out_seq_num,
            "use_custom_logon": self.use_custom_logon,
            "custom_logon_message": self.custom_logon_message,
            "persistent_storage_type": self.persistent_storage_type,
            "reset_seq_nums": self.reset_seq_nums,
            "use_extended_properties": self.use_extended_properties,
            "show_session_messages": self.show_session_messages,
            "extended_properties": self.extended_properties.to_dict(),
            "backup_connection": self.backup_connection.to_dict(),
            "use_ssl": self.use_ssl,
            "ssl": self.ssl.to_dict(),
        }

    def save(self, path: str | Path | None = None) -> Path:
        resolved_path = (
            _normalize_path(path) if path is not None else DEFAULT_SESSION_CONFIG_PATH
        )
        resolved_path.parent.mkdir(parents=True, exist_ok=True)

        parser = _CasePreservingConfigParser(interpolation=None)
        parser[_SESSION_SECTION] = {
            "ConfigurationPreset": self.configuration_preset,
            "SessionType": self.session_type,
            "SenderCompID": self.sender_comp_id,
            "TargetCompID": self.target_comp_id,
            "FixVersion": self.fix_version,
            "Host": self.host,
            "Port": str(self.port),
            "HeartBtInt": str(self.heartbeat_interval),
            "ReconnectAttempts": str(self.reconnect_attempts),
            "InSeqNum": str(self.in_seq_num),
            "OutSeqNum": str(self.out_seq_num),
            "UseCustomLogon": _serialize_bool(self.use_custom_logon),
            "CustomLogonMessage": self.custom_logon_message,
            "PersistentStorageType": _serialize_bool(self.persistent_storage_type),
            "ResetSeqNums": self.reset_seq_nums,
            "UseExtendedProperties": _serialize_bool(self.use_extended_properties),
            "ShowSessionMessages": _serialize_bool(self.show_session_messages),
            "UseSSL": _serialize_bool(self.use_ssl),
        }
        parser[_EXTENDED_PROPERTIES_SECTION] = self.extended_properties.to_section()
        parser[_BACKUP_CONNECTION_SECTION] = self.backup_connection.to_section()
        parser[_SSL_SECTION] = self.ssl.to_section()

        with resolved_path.open("w", encoding="utf-8") as config_file:
            parser.write(config_file)

        return resolved_path


def load_config(path: str | Path | None = None) -> SessionConfig:
    return SessionConfig.load(path)


def load_session_config(path: str | Path | None = None) -> SessionConfig:
    return SessionConfig.load(path)


def save_config(config: SessionConfig, path: str | Path | None = None) -> Path:
    return config.save(path)


def save_session_config(
    config: SessionConfig,
    path: str | Path | None = None,
) -> Path:
    return config.save(path)


__all__ = [
    "DEFAULT_SESSION_CONFIG_EXAMPLE_PATH",
    "DEFAULT_SESSION_CONFIG_PATH",
    "BackupConnectionConfig",
    "ExtendedPropertiesConfig",
    "SSLConfig",
    "SessionConfig",
    "SessionConfigError",
    "SessionConfigFileError",
    "SessionConfigMissingValueError",
    "SessionConfigSectionError",
    "SessionConfigValidationError",
    "load_config",
    "load_session_config",
    "save_config",
    "save_session_config",
]
