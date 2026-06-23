from __future__ import annotations

import sys
import logging
import datetime as date_time_library
from logging.handlers import RotatingFileHandler

from mypylib.colors import bcolors

INFO = "info"
WARNING = "warning"
ERROR = "error"
DEBUG = "debug"

_MODE_TO_LEVEL = {
    DEBUG: logging.DEBUG,
    INFO: logging.INFO,
    WARNING: logging.WARNING,
    ERROR: logging.ERROR,
}

def level_for_mode(mode: str) -> int:
    return _MODE_TO_LEVEL.get(mode, logging.INFO)


APPROX_BYTES_PER_LINE = 200
ROOT_LOGGER_NAME = "mtc"


class LogFormatter(logging.Formatter):
    _LEVEL_COLORS: dict[int, str] = {
        logging.DEBUG: bcolors.DEBUG,
        logging.INFO: bcolors.INFO,
        logging.WARNING: bcolors.WARNING,
        logging.ERROR: bcolors.ERROR,
    }

    def __init__(self, colored: bool) -> None:
        super().__init__()
        self.colored: bool = colored

    def format(self, record: logging.LogRecord) -> str:
        mode = record.levelname.lower()
        dt = date_time_library.datetime.fromtimestamp(record.created, date_time_library.timezone.utc)
        time_text = dt.strftime("%d.%m.%Y, %H:%M:%S.%f")[:-3]
        time_text = "{0} (UTC)".format(time_text).ljust(32, ' ')
        mode_field = "[{0}]".format(mode).ljust(10, ' ')
        thread_field = "<{0}>".format(record.threadName).ljust(14, ' ')
        message = record.getMessage()
        if record.exc_info:
            message = message + '\n' + self.formatException(record.exc_info)
        if not self.colored:
            return mode_field + time_text + thread_field + message
        mode_color = self._LEVEL_COLORS.get(record.levelno, bcolors.UNDERLINE) + bcolors.BOLD
        mode_text = "{0}{1}{2}".format(mode_color, mode_field, bcolors.ENDC)
        thread_color = (bcolors.ERROR if record.levelno >= logging.ERROR else bcolors.OKGREEN) + bcolors.BOLD
        thread_text = "{0}{1}{2}".format(thread_color, thread_field, bcolors.ENDC)
        return mode_text + time_text + thread_text + message


def get_logger(name: str | None = None) -> logging.Logger:
    if not name:
        return logging.getLogger(ROOT_LOGGER_NAME)
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")


def setup_logging(log_level: str = INFO, log_file_name: str | None = None, log_limit_lines: int | None = None) -> logging.Logger:
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    logger.setLevel(level_for_mode(log_level))  # child loggers inherit this level
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(LogFormatter(colored=True))
    logger.addHandler(console_handler)
    if log_file_name is not None:
        if log_limit_lines is not None:
            max_bytes = (log_limit_lines or 16384) * APPROX_BYTES_PER_LINE
            file_handler: logging.FileHandler = RotatingFileHandler(
                log_file_name, maxBytes=max_bytes, backupCount=1, encoding="utf-8"
            )
        else:
            file_handler = logging.FileHandler(log_file_name, encoding="utf-8")
        file_handler.setFormatter(LogFormatter(colored=True))
        logger.addHandler(file_handler)
    return logger
