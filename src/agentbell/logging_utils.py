"""Logging configuration for AgentBell.

All logs go to USERPROFILE/.agentbell/logs/agentbell.log
to avoid polluting stdout/stderr (which would break Claude Code hook JSON parsing).
"""

import logging
import os
from pathlib import Path


def get_log_dir() -> Path:
    log_dir = Path(os.environ.get("USERPROFILE", Path.home())) / ".agentbell" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("agentbell")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    log_file = get_log_dir() / "agentbell.log"
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
