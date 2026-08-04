import time
import logging
from enum import IntEnum
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("error_logger")


class Severity(IntEnum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


@dataclass
class SourceState:
    name: str
    last_log_time: float = 0.0
    consecutive_failures: int = 0
    suppressed_count: int = 0
    disabled: bool = False


@dataclass
class ErrorLoggerConfig:
    rate_limit_interval_s: float = 2.0
    error_rate_limit_s: float = 5.0
    max_consecutive_failures: int = 50


class ErrorLogger:

    def __init__(self, config: Optional[ErrorLoggerConfig] = None):
        self.config = config or ErrorLoggerConfig()
        self._sources = {}

    def log(
        self,
        source: str,
        message: str,
        severity: Severity = Severity.ERROR,
        failure: bool = False,
    ) -> bool:

        if source not in self._sources:
            self._sources[source] = SourceState(name=source)

        state = self._sources[source]

        if state.disabled:
            return False

        now = time.monotonic()

        # Critical messages always pass through
        if severity == Severity.CRITICAL:
            self._write(source, message, severity)

            if failure:
                state.consecutive_failures += 1

                if state.consecutive_failures >= self.config.max_consecutive_failures:
                    state.disabled = True
                    logger.warning(
                        f"Source '{source}' disabled after "
                        f"{state.consecutive_failures} critical failures"
                    )
            else:
                state.consecutive_failures = 0

            return True


        interval = (
            self.config.error_rate_limit_s
            if severity >= Severity.ERROR
            else self.config.rate_limit_interval_s
        )


        # Rate limiting
        if now - state.last_log_time < interval:

            state.suppressed_count += 1

            return False


        # Print suppression summary
        if state.suppressed_count > 0:
            logger.info(
                f"Suppressed {state.suppressed_count} messages "
                f"from '{source}' in {interval:.1f}s"
            )

        self._write(source, message, severity)

        state.last_log_time = now
        state.suppressed_count = 0


        # Failure tracking only happens for real failures
        if failure:
            state.consecutive_failures += 1

            if state.consecutive_failures >= self.config.max_consecutive_failures:
                state.disabled = True

                logger.warning(
                    f"Source '{source}' auto-disabled after "
                    f"{state.consecutive_failures} failures"
                )

        else:
            # Recovery detected
            state.consecutive_failures = 0


        return True


    def _write(
        self,
        source: str,
        message: str,
        severity: Severity
    ):

        level_map = {
            Severity.DEBUG: logging.DEBUG,
            Severity.INFO: logging.INFO,
            Severity.WARNING: logging.WARNING,
            Severity.ERROR: logging.ERROR,
            Severity.CRITICAL: logging.CRITICAL,
        }

        logger.log(
            level_map.get(severity, logging.INFO),
            f"[{source}] {message}"
        )


    def reset_source(self, source: str):

        state = self._sources.get(source)

        if state:
            state.disabled = False
            state.consecutive_failures = 0
            state.suppressed_count = 0
            state.last_log_time = 0.0


    def get_disabled_sources(self):

        return [
            name
            for name, state in self._sources.items()
            if state.disabled
        ]


    def get_stats(self):

        return {
            name: {
                "disabled": state.disabled,
                "suppressed": state.suppressed_count,
                "consecutive_failures": state.consecutive_failures,
            }
            for name, state in self._sources.items()
        }