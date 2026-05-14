# app/infrastructure/llm/opencode_adapter.py
import json
import logging
import subprocess

logger = logging.getLogger(__name__)


class OpenCodeAdapter:
    """Runs opencode via subprocess and extracts text from JSON event stream."""

    def call(self, prompt: str, timeout: int = 60) -> str:
        from app.config.settings import OPENCODE_BIN, OPENCODE_MODEL, OPENCODE_CWD
        try:
            result = subprocess.run(
                [OPENCODE_BIN, "run", "--model", OPENCODE_MODEL, "--format", "json", prompt],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=OPENCODE_CWD,
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
