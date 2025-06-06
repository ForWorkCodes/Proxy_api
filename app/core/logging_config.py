import logging
import os
from datetime import datetime, timezone

LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)


def setup_logging():
    print("==========================================================")
    print("Handlers:", logging.getLogger().handlers)
    print("==========================================================")

    logger = logging.getLogger()
    if logger.handlers:
        return

    # Формат даты в имени файла
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s')

    # Лог-файл с датой для общего логирования
    general_log_path = os.path.join(LOG_DIR, f"app_{date_str}.log")
    general_handler = logging.FileHandler(general_log_path, encoding="utf-8")
    general_handler.setLevel(logging.INFO)
    general_handler.setFormatter(formatter)

    # Лог-файл с датой для критических ошибок
    critical_log_path = os.path.join(LOG_DIR, f"proxy_critical_{date_str}.log")
    critical_handler = logging.FileHandler(critical_log_path, encoding="utf-8")
    critical_handler.setLevel(logging.ERROR)
    critical_handler.setFormatter(formatter)

    # Корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(general_handler)
    root_logger.addHandler(critical_handler)

    # Отдельный логгер для proxy_critical
    proxy_critical_logger = logging.getLogger("proxy_critical")
    proxy_critical_logger.setLevel(logging.ERROR)
    proxy_critical_logger.addHandler(critical_handler)
    proxy_critical_logger.propagate = False
