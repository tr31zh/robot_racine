from logging import log
import os
from time import sleep
import logging
from datetime import datetime as dt
import sys
import shutil

lock_file = os.path.join(
    os.path.dirname(__file__),
    "..",
    "data",
    "images",
    "snap_in_progress.txt",
)

src_folder = os.path.join(os.path.dirname(__file__), "..", "data", "images", "to_send", "")
dst_folder = os.path.join(os.path.dirname(__file__), "..", "data", "images", "sent", "")

log_file_handler = logging.FileHandler(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "logs",
        f"file_sender_{dt.now().strftime('%Y%m%d')}.log",
    ),
    mode="a",
    delay=True,
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(name)s - %(levelname)s] - %(message)s",
    handlers=[
        log_file_handler,
    ],
)

logger = logging.getLogger("file_sender")
logger.info("__________________________________________________________")
logger.info("____________________Starting filesender___________________")
logger.info("__________________________________________________________")


def main():
    while True:

        for name in os.listdir(src_folder):
            if os.path.isdir(lock_file):
                logger.info("File sending locked by main RobotRacine")
                continue
            try:
                shutil.move(
                    os.path.join(src_folder, name),
                    os.path.join(dst_folder, name),
                )
            except Exception as e:
                logger.error(f"Unable to move {name} because {repr(e)}")
            else:
                logger.info(f"Moved {name}")

        logger.info("Going to sleep for a while...")
        sleep(600)


if __name__ == "__main__":
    main()