import logging
from logging import DEBUG, INFO, WARN, ERROR, FATAL
from logging import basicConfig, debug
from logging import FileHandler, StreamHandler

from os.path import isdir, exists
from os import mkdir, getcwd, makedirs

from datetime import datetime
from sys import stdout

from python_json_config import ConfigBuilder


def setup():
    # Checking if log directory exists
    if not isdir("logs"):
        mkdir("logs")

    config = ConfigBuilder().parse_config("config/config.json")

    logging_level = 0
    if config.logging_level == "DEBUG":
        logging_level = DEBUG
    elif config.logging_level == "INFO":
        logging_level = INFO
    elif config.logging_level in ("WARN", "WARNING"):
        logging_level = WARN
    elif config.logging_level == "ERROR":
        logging_level = ERROR
    elif config.logging_level in ("FATAL", "CRITICAL"):
        logging_level = FATAL

    if not exists(f'{datetime.now().strftime("logs/%m.%Y")}'):
        makedirs(f'{datetime.now().strftime("logs/%m.%Y")}')

    # Setting up logging
    basicConfig(
        level=logging_level,
        format="%(asctime)s - %(levelname)s - [%(module)s] - %(message)s",
        handlers=[
            FileHandler(f'{datetime.now().strftime("logs/%m.%Y/%d.%m.%Y.log")}'),
            StreamHandler(stdout),
        ],
        encoding="utf-32",
    )

    debug(f"Logger set up! Cwd: {getcwd()}")
