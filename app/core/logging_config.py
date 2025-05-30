import logging
import os
from logging.handlers import TimedRotatingFileHandler

LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)

def setup_logging():
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s')

    # Handler для общего логирования по дням
    general_handler = TimedRotatingFileHandler(
        filename=os.path.join(LOG_DIR, "app.log"),
        when="midnight",
        interval=1,
        backupCount=10,
        encoding="utf-8",
        utc=True
    )
    general_handler.setLevel(logging.INFO)
    general_handler.setFormatter(formatter)

    # Handler для критических логов по дням
    critical_handler = TimedRotatingFileHandler(
        filename=os.path.join(LOG_DIR, "proxy_critical.log"),
        when="midnight",
        interval=1,
        backupCount=10,
        encoding="utf-8",
        utc=True
    )
    critical_handler.setLevel(logging.ERROR)
    critical_handler.setFormatter(formatter)

    # Корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(general_handler)
    root_logger.addHandler(critical_handler)

    # Логгер для proxy_critical
    proxy_critical_logger = logging.getLogger("proxy_critical")
    proxy_critical_logger.setLevel(logging.ERROR)
    proxy_critical_logger.addHandler(critical_handler)
    proxy_critical_logger.propagate = False
