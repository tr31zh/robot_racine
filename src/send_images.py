from logging import log
import os
from time import sleep
import logging
from datetime import datetime as dt
import sys
import shutil
import glob
import argparse
from timeit import default_timer as timer

import paramiko

try:
    from server_credentials import connection_data
except Exception as e:
    server_conf = {}
else:
    server_conf = connection_data.get("phenopsis", {})

lock_file = os.path.join(
    os.path.dirname(__file__),
    "..",
    "data",
    "images",
    "snap_in_progress.txt",
)

MOVE_IMAGES_MAX_DURATION = 5 * 60

src_folder = os.path.join(os.path.dirname(__file__), "..", "data", "images", "to_send", "")

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


def send_images():
    start = timer()

    src_folder = os.path.join(
        os.path.dirname(__file__),
        "..",
        "data",
        "images",
        "to_send",
        "",
    )

    if server_conf:
        p = paramiko.SSHClient()
        p.set_missing_host_key_policy(paramiko.AutoAddPolicy)
        p.connect(
            server_conf["address"],
            port=server_conf["port"],
            username=server_conf["user"],
            password=server_conf["password"],
        )
        ftp = p.open_sftp()
        ftp.chdir("RobotRacine")
        for name in os.listdir(src_folder):
            if (timer() - start) >= MOVE_IMAGES_MAX_DURATION:
                logger.info(
                    f"Stopping sending images to avoid job conflicts after {(timer() - start) / 60} minutes"
                )
                break
            try:
                exp_folder = os.path.basename(name).split("#")[1]
                try:
                    ftp.stat(exp_folder)
                except FileNotFoundError:
                    logger.info(f"Creating {exp_folder} folder")
                    ftp.mkdir(exp_folder)
                ftp.put(
                    os.path.join(src_folder, name),
                    os.path.join(exp_folder, name),
                )
            except Exception as e:
                logger.error(f"Unable to move {name} because {repr(e)}")
            else:
                # Check file size and delete source
                if (
                    os.path.getsize(os.path.join(src_folder, name))
                    == ftp.stat(os.path.join(exp_folder, name)).st_size
                ):
                    logger.info(f"Moved {name}, deleted source")
                else:
                    logger.error(f"Wrong destination file size: {name}")

        else:
            logger.info("Ended file sending")
        ftp.close()
        p.close()
    else:
        # Find the target folder
        for fld in glob.glob(os.path.join("/", "media", "pi", "*")):
            if os.path.isdir(os.path.join(fld, "robot_racine", "")):
                base_target_folder = os.path.join(fld, "robot_racine", "")
                break
        else:
            base_target_folder = ""
            logger.warning("No target folder found, will not move images")
        if base_target_folder:
            for name in os.listdir(src_folder):
                if (timer() - start) >= MOVE_IMAGES_MAX_DURATION:
                    logger.info(
                        f"Stopping sending images to avoid job conflicts after {(timer() - start) / 60} minutes"
                    )
                    break
                try:
                    # Get experiment name
                    target_folder = os.path.join(
                        base_target_folder, os.path.basename(name).split("#")[1]
                    )
                    if not os.path.exists(target_folder):
                        os.makedirs(target_folder)

                    shutil.move(
                        os.path.join(src_folder, name),
                        os.path.join(target_folder, name),
                    )
                except Exception as e:
                    logger.error(f"Unable to move {name} because {repr(e)}")
                else:
                    logger.info(f"Moved {name}")
            else:
                logger.info("Ended file sending")


if __name__ == "__main__":
    send_images()