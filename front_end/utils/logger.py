import logging
from ..config import AppConfig


class Logger:
    def __init__(self, event_bus):
        self._configure_logging()

    def _configure_logging(self):
        logging.basicConfig(
            format=AppConfig.LOG_FORMAT,
            level=logging.INFO,
            filename='app.log',
            filemode='a'
        )