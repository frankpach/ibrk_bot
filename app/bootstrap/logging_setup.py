# app/bootstrap/logging_setup.py
"""Structured logging setup with structlog."""
import logging
import structlog


def configure_logging() -> None:
    """Configure structlog and stdlib logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if False else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    # Keep stdlib basicConfig for third-party libs that use logging directly
    log_format = "%(asctime)s %(levelname)s %(name)s - %(message)s"
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        file_handler = logging.FileHandler("bot.log", mode="a", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
    except Exception:
        pass
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=handlers,
    )
