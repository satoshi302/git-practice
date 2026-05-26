import logging
import os
from datetime import datetime

import colorlog


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    fmt = "%(log_color)s[%(asctime)s] [%(levelname)-8s] [%(name)s]%(reset)s %(message)s"
    datefmt = "%H:%M:%S"
    color_handler = colorlog.StreamHandler()
    color_handler.setFormatter(colorlog.ColoredFormatter(fmt, datefmt=datefmt))
    color_handler.setLevel(logging.DEBUG)
    logger.addHandler(color_handler)

    os.makedirs("logs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_handler = logging.FileHandler(f"logs/recovery_{timestamp}.log")
    file_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s", datefmt=datefmt
    ))
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    return logger
