# app/application/services/setting_validator.py
"""SettingValidator — validates control-plane settings against a typed registry."""
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class SettingDef:
    """Metadata for a single control setting."""
    type: type = str
    min: float | int | None = None
    max: float | int | None = None
    enum: tuple | None = None
    is_secret: bool = False
    requires_restart: bool = False
    hot_reload: bool = False


SETTING_REGISTRY: dict[str, SettingDef] = {
    # Risk settings (hot-reloadable)
    "max_risk_pct": SettingDef(type=float, min=0.001, max=0.10, hot_reload=True),
    "max_positions": SettingDef(type=int, min=1, max=20, hot_reload=True),
    "capital_cap": SettingDef(type=float, min=100.0, hot_reload=True),
    "min_risk_usd": SettingDef(type=float, min=0.0, hot_reload=True),
    "max_position_usd": SettingDef(type=float, min=1.0, hot_reload=True),

    # Infrastructure / secrets (require restart)
    "database_url": SettingDef(type=str, is_secret=False, requires_restart=True),
    "ib_host": SettingDef(type=str, requires_restart=True),
    "ib_port": SettingDef(type=int, min=1024, max=65535, requires_restart=True),
    "opencode_bin": SettingDef(type=str, requires_restart=True),
    "opencode_model": SettingDef(type=str, requires_restart=True),
    "opencode_cwd": SettingDef(type=str, requires_restart=True),

    # API keys (secrets, some require restart)
    "telegram_bot_token": SettingDef(type=str, is_secret=True, requires_restart=True),
    "llm_api_key": SettingDef(type=str, is_secret=True, hot_reload=True),
    "api_control_key": SettingDef(type=str, is_secret=True, requires_restart=True),
    "api_admin_key": SettingDef(type=str, is_secret=True, requires_restart=True),

    # Operational settings
    "trading_mode": SettingDef(type=str, enum=("paper", "live"), hot_reload=True),
    "is_paused": SettingDef(type=bool, hot_reload=True),
    "notification_level": SettingDef(type=str, enum=("critical_only", "normal", "verbose"), hot_reload=True),
}


class SettingValidationError(ValueError):
    """Raised when a setting value fails validation."""
    pass


class SettingValidator:
    """Validates control-plane settings."""

    @classmethod
    def validate(cls, key: str, raw_value: Any) -> Any:
        """Validate and coerce *raw_value* for *key*.

        Returns the coerced value on success.
        Raises ``SettingValidationError`` with a human-readable message on failure.
        """
        definition = SETTING_REGISTRY.get(key)
        if definition is None:
            # Unknown key: allow through but log a warning
            return raw_value

        value = cls._coerce(raw_value, definition.type)

        if definition.enum is not None and value not in definition.enum:
            raise SettingValidationError(
                f"'{key}' must be one of {definition.enum}, got '{value}'"
            )

        if definition.min is not None:
            if definition.type in (int, float) and value < definition.min:
                raise SettingValidationError(
                    f"'{key}' must be >= {definition.min}, got {value}"
                )

        if definition.max is not None:
            if definition.type in (int, float) and value > definition.max:
                raise SettingValidationError(
                    f"'{key}' must be <= {definition.max}, got {value}"
                )

        return value

    @classmethod
    def get_definition(cls, key: str) -> SettingDef | None:
        return SETTING_REGISTRY.get(key)

    @classmethod
    def _coerce(cls, raw: Any, target_type: type) -> Any:
        if target_type == bool:
            if isinstance(raw, bool):
                return raw
            if isinstance(raw, str):
                return raw.lower() in ("1", "true", "yes", "on")
            return bool(raw)
        if target_type == int:
            return int(raw)
        if target_type == float:
            return float(raw)
        if target_type == str:
            return str(raw)
        return raw
