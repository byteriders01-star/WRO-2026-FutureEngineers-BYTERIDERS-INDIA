from enum import IntEnum
from typing import Final


class LogSeverity(IntEnum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


SEVERITY_LABELS: Final[dict[LogSeverity, str]] = {
    LogSeverity.DEBUG: "DEBUG",
    LogSeverity.INFO: "INFO",
    LogSeverity.WARNING: "WARN",
    LogSeverity.ERROR: "ERROR",
    LogSeverity.CRITICAL: "CRIT",
}


def format_severity(severity: LogSeverity) -> str:
    """
    Convert severity enum into readable text.
    """
    return SEVERITY_LABELS.get(
        severity,
        "UNKNOWN"
    )


SEVERITY_RATE_LIMITS_S: Final[dict[LogSeverity, float]] = {
    LogSeverity.DEBUG: 2.0,
    LogSeverity.INFO: 2.0,
    LogSeverity.WARNING: 2.0,
    LogSeverity.ERROR: 5.0,
    LogSeverity.CRITICAL: 0.0,
}


def get_rate_limit(severity: LogSeverity) -> float:
    """
    Returns rate limit interval for a given severity level.
    CRITICAL messages are never rate limited.
    """
    return SEVERITY_RATE_LIMITS_S.get(
        severity,
        2.0
    )