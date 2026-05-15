# app/application/use_cases/update_control_setting.py
"""UpdateControlSettingUseCase — validates, persists, and optionally hot-reloads a setting."""
from dataclasses import dataclass
from typing import Any

import structlog

from app.application.event_bus import EventBus
from app.application.services.risk_service import RiskService
from app.application.services.setting_validator import SettingValidator, SettingValidationError
from app.infrastructure.db.compat import get_control_setting, update_control_setting_full
from app.domain.trading.events import ControlSettingChanged
from app.infrastructure.system.secret_manager import SecretManager

logger = structlog.get_logger(__name__)

_SECRET_MASK = "••••••••"


@dataclass
class UpdateSettingCommand:
    key: str
    value: str
    changed_by: str = "system"
    ip_address: str | None = None


@dataclass
class UpdateSettingResult:
    key: str
    success: bool
    requires_restart: bool = False
    message: str = ""
    error: str | None = None


class UpdateControlSettingUseCase:
    """Single write point for ``control_settings``.

    Flow:
        1. Validate the value via ``SettingValidator``.
        2. Encrypt if the setting is marked ``is_secret``.
        3. Persist to ``control_settings``.
        4. Publish ``ControlSettingChanged`` event.
        5. If ``requires_restart=False`` and a hot-reload handler exists, apply immediately.
    """

    def __init__(
        self,
        event_bus: EventBus,
        secret_manager: SecretManager | None = None,
        risk_service: RiskService | None = None,
    ):
        self._event_bus = event_bus
        self._secret_manager = secret_manager
        self._risk_service = risk_service

    def execute(self, command: UpdateSettingCommand) -> UpdateSettingResult:
        key = command.key

        definition = SettingValidator.get_definition(key)
        is_secret = definition.is_secret if definition else False
        requires_restart = definition.requires_restart if definition else False

        # 1. Validate
        try:
            coerced = SettingValidator.validate(key, command.value)
        except SettingValidationError as exc:
            logger.warning(f"setting_validation_failed", key=key, error=str(exc))
            return UpdateSettingResult(
                key=key, success=False, error=str(exc),
            )

        # 2. Get old value
        old_row = get_control_setting(key)
        old_value = old_row["value"] if old_row else ""

        # 3. Encrypt if secret
        persisted_value = str(coerced)
        if is_secret:
            if self._secret_manager is None:
                return UpdateSettingResult(
                    key=key, success=False, error="SecretManager not configured",
                )
            persisted_value = self._secret_manager.encrypt(str(coerced))

        # 4. Persist
        update_control_setting_full(
            key=key,
            value=persisted_value,
            updated_by=command.changed_by,
            is_secret=is_secret,
            requires_restart=requires_restart,
        )

        # 5. Publish event (mask secrets)
        event_old = "[REDACTED]" if is_secret else old_value
        event_new = "[REDACTED]" if is_secret else str(coerced)
        self._event_bus.publish(
            ControlSettingChanged(
                key=key,
                old_value=event_old,
                new_value=event_new,
                changed_by=command.changed_by,
                is_secret=is_secret,
            )
        )

        # 6. Hot-reload
        if not requires_restart and definition and definition.hot_reload:
            self._hot_reload(key, coerced)

        msg = f"Setting '{key}' updated successfully."
        if requires_restart:
            msg += " Restart required for changes to take effect."

        return UpdateSettingResult(
            key=key,
            success=True,
            requires_restart=requires_restart,
            message=msg,
        )

    def _hot_reload(self, key: str, value: Any) -> None:
        """Apply the new value to in-memory services immediately."""
        if key in ("max_risk_pct", "max_positions", "capital_cap",
                   "min_risk_usd", "max_position_usd") and self._risk_service is not None:
            logger.info(f"hot_reload_risk_setting", key=key, value=value)
            # RiskService reads from ISystemStateRepository; we cannot patch it
            # directly without a repository.  For now we log the intent.
            # Future: update a mutable config store that RiskService reads.
        else:
            logger.info(f"hot_reload_no_handler", key=key)
