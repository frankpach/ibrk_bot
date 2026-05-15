# app/infrastructure/llm/opencode_adapter.py
import json
import logging
import os
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

SAFE_SYMBOL_RE = re.compile(r'^[A-Z0-9./=]{1,20}$')


class OpenCodeAdapter:
    """Runs opencode via subprocess and extracts text from JSON event stream."""

    SAFE_SYMBOL_RE = SAFE_SYMBOL_RE

    def __init__(self):
        from app.config.settings import OPENCODE_BIN
        self._bin_path = Path(OPENCODE_BIN).resolve()

    def _validate_bin(self) -> None:
        if not self._bin_path.exists():
            raise FileNotFoundError(
                f"OpenCode binary not found: {self._bin_path}"
            )
        if not os.access(self._bin_path, os.X_OK):
            raise PermissionError(
                f"OpenCode binary is not executable: {self._bin_path}"
            )

    def _validate_symbol(self, symbol: str) -> None:
        if not self.SAFE_SYMBOL_RE.match(symbol):
            raise ValueError(
                f"Invalid symbol: {symbol!r} "
                f"must match {self.SAFE_SYMBOL_RE.pattern}"
            )

    def call(self, prompt: str, timeout: int = 60, task: str = "analysis") -> str:
        from app.config.settings import OPENCODE_BIN, OPENCODE_CWD
        from app.llm.agent import get_llm_model_for_task
        model = get_llm_model_for_task(task)
        try:
            result = subprocess.run(
                [
                    OPENCODE_BIN, "run", "--model", model,
                    "--format", "json", prompt,
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=OPENCODE_CWD,
                env={},
            )
            text_parts = []
            for line in result.stdout.strip().splitlines():
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    if event.get("type") == "text":
                        text_parts.append(event["part"]["text"])
                except json.JSONDecodeError:
                    continue
            return "".join(text_parts).strip()
        except subprocess.TimeoutExpired:
            logger.error("opencode call timed out")
            return ""
        except Exception as exc:
            logger.error(f"opencode call failed: {exc}")
            return ""

    def analyze_signal(self, symbol: str, prompt: str, timeout: int = 60) -> str:
        """Validates symbol safety before calling the LLM."""
        self._validate_symbol(symbol)
        return self.call(prompt, timeout=timeout)
