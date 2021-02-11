import time
import os
import json
from functools import partial
import logging
from datetime import datetime as dt
from datetime import timedelta as td
import datetime
from enum import Enum
import shutil
from pathlib import Path
import socket
import subprocess
import glob
from timeit import default_timer as timer
import paramiko

import pandas as pd

from kivy.network.urlrequest import UrlRequest

from picamera import PiCamera

try:
    from server_credentials import connection_data
except Exception as e:
    server_conf = {}
else:
    server_conf = connection_data.get("phenopsis", {})

logger = logging.getLogger("rr_drive")


TEST_MODE = False
USE_UDP = False

plant_data_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "data",
    "plants_data.csv",
)

settings_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "data",
    "settings.json",
)

if TEST_MODE:
    jobs_file_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "test_files",
        "test_jobs.json",
    )
else:
    jobs_file_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "data",
        "jobs_data.json",
    )


class JobState(Enum):
    INACTIVE = 0
    WAITING_HOME = 1
    IN_PROGRESS = 2
    ENDED = 3


def job_state_to_text(state):
    if state == JobState.INACTIVE:
        return "inactive"
    elif state == JobState.WAITING_HOME:
        return "waiting home position"
    elif state == JobState.IN_PROGRESS:
        return "in progress"
    elif state == JobState.ENDED:
        return "ended"
    else:
        return "unknown"


class JobData:
    def __init__(self, **kwargs) -> None:
        self.name = kwargs.get("name")
        self.enabled = kwargs.get("enabled")
        self.guid = kwargs.get("guid")
        self.description = kwargs.get("description")
        self.owner = kwargs.get("owner")
        self.mail_to = kwargs.get("mail_to")
        self.plants = kwargs.get("plants")
        self._repetition_mode = kwargs.get("repetition_mode")
        self._repetition_value = kwargs.get("repetition_value")
        self._timestamp_start = dt.strptime(
            kwargs.get("timestamp_start"), "%Y/%m/%d %H:%M:%S"
        )
        self._timestamp_end = dt.strptime(
            kwargs.get("timestamp_end"), "%Y/%m/%d %H:%M:%S"
        )
        self.time_points = []
        self.update_time_points()

        self.state = JobState.INACTIVE

    def to_json(self):
        return {
            "name": self.name,
            "enabled": self.enabled,
            "guid": self.guid,
            "description": self.description,
            "owner": self.owner,
            "mail_to": self.mail_to,
            "plants": self.plants,
            "repetition_mode": self.repetition_mode,
            "repetition_value": self.repetition_value,
            "timestamp_start": self.timestamp_start.strftime("%Y/%m/%d %H:%M:%S"),
            "timestamp_end": self.timestamp_end.strftime("%Y/%m/%d %H:%M:%S"),
        }

    def update_time_points(self):
        self.time_points = []
        if self.repetition_mode == "every":
            current = self.timestamp_start
            while current < self.timestamp_end:
                self.time_points.append(current)
                current = current + td(hours=int(self.repetition_value))
        elif self.repetition_mode == "at":
            current = self.timestamp_start.date()
            last = self.timestamp_end.date()
            if isinstance(self.repetition_value, int):
                hours = [self.repetition_value]
            elif isinstance(self.repetition_value, str):
                hours = [
                    int(h) for h in self.repetition_value.replace(" ", "").split(",")
                ]
            elif isinstance(self.repetition_value, list):
                hours = self.repetition_value
            else:
                hours = []
            while current < last:
                self.time_points.extend(
                    [dt.combine(date=current, time=datetime.time(hour=h)) for h in hours]
                )
                current = current + td(days=1)

    def update_time_boundaries(self, start_time, end_time, rep_mode, rep_value):
        if isinstance(start_time, str):
            self._timestamp_start = dt.strptime(start_time, "%Y/%m/%d %H:%M:%S")
        else:
            self._timestamp_start = start_time
        if isinstance(end_time, str):
            self._timestamp_end = dt.strptime(end_time, "%Y/%m/%d %H:%M:%S")
        else:
            self._timestamp_end = end_time
        self._repetition_mode = rep_mode
        self._repetition_value = rep_value
        self.update_time_points()

    @property
    def next_time_point(self):
        if self.enabled is True:
            n = dt.now()
            l = [t for t in self.time_points if t >= n]
            return l[0] if l else None
        else:
            return None

    @property
    def repetition_mode(self):
        return self._repetition_mode

    @repetition_mode.setter
    def repetition_mode(self, value):
        self._repetition_mode = value
        self.update_time_points()

    @property
    def repetition_value(self):
        return self._repetition_value

    @repetition_value.setter
    def repetition_value(self, value):
        self._repetition_value = value
        self.update_time_points()

    @property
    def repetition_value(self):
        return self._repetition_value

    @repetition_value.setter
    def repetition_value(self, value):
        self._repetition_value = value
        self.update_time_points()

    @property
    def timestamp_start(self):
        return self._timestamp_start

    @timestamp_start.setter
    def timestamp_start(self, value):
        if isinstance(value, str):
            self._timestamp_start = dt.strptime(value, "%Y/%m/%d %H:%M:%S")
        else:
            self._timestamp_start = value
        self.update_time_points()

    @property
    def timestamp_end(self):
        return self._timestamp_end

    @timestamp_end.setter
    def timestamp_end(self, value):
        if isinstance(value, str):
            self._timestamp_end = dt.strptime(value, "%Y/%m/%d %H:%M:%S")
        else:
            self._timestamp_end = value
        self.update_time_points()


class Controller:
    def __init__(self, **kwargs) -> None:
        self.current_position: int = 0
        self.waiting_for: list = {}
        self.plant_data = None
        self.log_data = []
        self.settings = None
        self.callback = None
        self.waiting_commands = []
        self.awaiting_command = False
        self.current_request = None
        self.go_home_timeout_count = 0

        self.camera = PiCamera()

        self.job_in_progress = None

        self.robot_state = {
            "current_state": -1,
            "last_state": -1,
            "home": False,
        }

        self.load()

    def save_settings(self):
        try:
            with open(settings_path, "w") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save settings because: {repr(e)}")
        else:
            logger.info("Saved settings")

    def save_plant_data(self):
        try:
            self.plant_data.to_csv(plant_data_path, index=False)
        except Exception as e:
            logger.error(f"Failed to save plant data because: {repr(e)}")
        else:
            logger.info("Saved plant data")

    def save_jobs_data(self):
        try:
            with open(jobs_file_path, "w") as f:
                json.dump({"jobs": [j.to_json() for j in self.jobs_data]}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save jobs data because: {repr(e)}")
        else:
            logger.info("Saved jobs data")

    def save(self):
        self.save_settings()
        self.save_plant_data()
        self.save_jobs_data()

    def push_command(self, command, callback):
        logger.info(f"Pushed command {command}")
        self.waiting_commands.append({"cmd": command, "callback": callback})

    def pop_command(self):
        if self.waiting_commands:
            next_command = self.waiting_commands.pop(0)
            logger.info(f"popped command {next_command['cmd']}")
            self.send_command(
                command=next_command["cmd"],
                callback=next_command["callback"],
            )

    def clear_commands(self):
        self.waiting_commands = []

    def start_send_tool(self, callback):
        # Check script is running
        p1 = subprocess.Popen(["pgrep", "-af", "python"], stdout=subprocess.PIPE)
        p2 = subprocess.Popen(
            ["grep", "send_images.py"], stdin=p1.stdout, stdout=subprocess.PIPE
        )
        p1.stdout.close()
        output, err = p2.communicate()

        if (err is not None) or ("send_images.py" not in str(output)):
            callback(
                f"Sender script not active, launching it",
                wipe_after=-1,
                log_level=logging.INFO,
            )
            try:
                subprocess.Popen(["python", "src/send_images.py"])
            except Exception as e:
                callback(
                    f"Unable to launch file sender because {repr(e)}, images won't be sent to server",
                    wipe_after=-1,
                    log_level=logging.ERROR,
                )

        # Check files are not too ald
        images = glob.glob(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "data",
                "images",
                "to_send",
                "*",
            )
        )
        files_ok = (
            True
            if not images
            else (
                dt.now()
                - dt.fromtimestamp(os.path.getmtime(min(images, key=os.path.getctime)))
            ).seconds
            < 7200
        )
        if not files_ok:
            callback(
                f"File sender script seems to have an issue, images won't be sent to server",
                wipe_after=-1,
                log_level=logging.ERROR,
            )

    def load(self):
        try:
            if os.path.isfile(plant_data_path):
                self.plant_data = pd.read_csv(plant_data_path)
            else:
                self.plant_data = pd.DataFrame(
                    columns=["experiment", "plant_name", "position", "allow_capture"]
                )

            if os.path.isfile(jobs_file_path):
                with open(jobs_file_path, "r") as f:
                    self.jobs_data = [JobData(**j) for j in json.load(f)["jobs"]]
                # self.jobs_data[0].timestamp_start = dt.now() - td(hours=1) + td(seconds=15)
            else:
                self.jobs_data = []

            if os.path.isfile(settings_path):
                with open(settings_path, "r") as f:
                    self.settings = json.load(f)
            else:
                self.settings = {
                    "target_ip": "http://127.0.0.1",
                    "target_port": 8000,
                    "target_stop_port": 2390,
                    "tray_count": 56,
                    "image_resolution": "1024x768",
                    "show_images": False,
                }
                self.update_camera_resolution()
        except Exception as e:
            logger.error(f"Failed to load data because: {repr(e)}")
        else:
            logger.info("Loaded data")

    def update_camera_resolution(self):
        try:
            self.camera.framerate = 15
            self.camera.resolution = self.settings["image_resolution"].split("x")
        except Exception as e:
            logger.error(f"Unable to set camera resolution because {repr(e)}")
            self.camera.resolution = (1024, 768)

    def get_next_job(self):
        n = dt.now()
        available_jobs = sorted(
            [
                j
                for j in self.jobs_data
                if j.enabled is True and j.timestamp_start <= n <= j.timestamp_end
            ],
            key=lambda x: x.next_time_point,
        )
        return available_jobs[0] if available_jobs else None

    def state_to_text(self):
        if self.job_in_progress is None:
            msg = ""
        else:
            state_text = job_state_to_text(self.job_in_progress.state)
            msg = f"{self.job_in_progress.name} {state_text} - "
        if self.robot_state["home"] == True:
            msg += "Home position"
        elif self.robot_state["current_state"] >= 1:
            msg += f"Tray {self.robot_state['current_state']} camera ready"
        else:
            msg += f"Unknown position"
        return msg

    def on_success(self, *args):
        sent_cmd, _, received_command = args

        if received_command:
            received_command = (
                received_command.split("<br>")[-1].replace("\n", "").replace("\r", "")
            )

        logger.info(f"Entered success, sent: {sent_cmd}, received: {received_command}")

        if received_command == "stop":
            if self.callback is not None:
                self.callback(
                    message=f"Received response for {sent_cmd} cancel request",
                    wipe_after=5,
                    log_level=logging.INFO,
                )
            else:
                logger.info("Sent first stop")
            self.awaiting_command = False
            return

        if received_command == "go_home_timeout":
            self.send_request(command="go_home_dirty")
            return

        if sent_cmd != received_command:
            logger.error(
                f"Inconsistent message received, expected {sent_cmd}, received {received_command}"
            )

        if received_command == "go_home_dirty":
            self.robot_state["home"] = True
        elif received_command == "go_next" and self.robot_state["home"] is True:
            self.robot_state["current_state"] = 1
            self.robot_state["last_state"] = -1
            self.robot_state["home"] = False
        elif received_command == "go_next":
            self.robot_state["current_state"] = self.robot_state["last_state"] + 1
            if self.robot_state["current_state"] > self.settings["tray_count"]:
                self.robot_state["current_state"] = 1
            self.robot_state["last_state"] = -1
        elif self.robot_state["home"] is True:
            self.robot_state["home"] = False

        if self.job_in_progress is not None:
            if received_command == "go_home_dirty":
                if self.job_in_progress.state == JobState.WAITING_HOME:
                    self.job_in_progress.state = JobState.IN_PROGRESS
                    self.callback(
                        message=f"Job {self.job_in_progress.name} - Home position reached",
                        wipe_after=-1,
                        log_level=logging.INFO,
                    )
                elif self.job_in_progress.state == JobState.IN_PROGRESS:
                    self.job_in_progress.state = JobState.ENDED
                    self.callback(
                        message=f"Job {self.job_in_progress.name} - Ended",
                        wipe_after=5,
                        log_level=logging.INFO,
                    )
                    self.job_in_progress.state = JobState.INACTIVE
                    self.job_in_progress = None
            elif received_command == "go_next":
                plant = self.get_current_plant()
                if plant is None:
                    self.callback(
                        message=f"Job {self.job_in_progress.name} - Position error",
                        wipe_after=-1,
                        log_level=logging.ERROR,
                    )
                elif not plant:
                    self.callback(
                        message=f"Job {self.job_in_progress.name} - Tray {self.robot_state['current_state']} empty, moving to next",
                        wipe_after=-1,
                        log_level=logging.INFO,
                    )
                elif plant["allow_capture"]:
                    self.snap(callback=self.callback)
                else:
                    self.callback(
                        message=f"Job {self.job_in_progress.name} - {self.get_plant_desc()} excluded from image capture",
                        wipe_after=-1,
                        log_level=logging.INFO,
                    )
            elif received_command == "stop":
                self.job_in_progress.state = JobState.ENDED
                self.callback(
                    message=f"Job {self.job_in_progress.name} - Cancelled",
                    wipe_after=5,
                    log_level=logging.INFO,
                )
                self.job_in_progress.state = JobState.INACTIVE
        elif self.callback is not None:
            self.callback(
                message=self.state_to_text(),
                wipe_after=-1 if self.job_in_progress is None else 2,
                log_level=logging.INFO,
            )
        else:
            logger.warning(f"No callback available for message: {self.state_to_text()}")

        self.awaiting_command = False
        self.pop_command()

    def on_failure(self, on_success, *args):
        self.callback(
            message=f"FAILURE - Command: {str(args[1])}, State: {self.robot_state}",
            wipe_after=20,
            log_level=logging.WARNING,
        )
        logger.warning(f"FAILURE - Command: {str(args[1])}, State: {self.robot_state}")
        self.awaiting_command = False
        self.pop_command()

    def on_error(self, on_success, *args):
        if (
            isinstance(self.current_request.error, socket.timeout)
            and self.go_home_timeout_count < 10
        ):
            self.go_home_timeout_count += 1
            logger.info(
                f"Dirty fix for kivy's URL request bug, attempt n°{self.go_home_timeout_count}"
            )
            self.send_request("go_home_dirty")
        else:
            self.callback(
                message=f"ERROR - {str(args[1])}, State: {self.robot_state}",
                wipe_after=2,
                log_level=logging.ERROR,
            )
            logger.error(f"ERROR - Command: {str(args[1])}, State: {self.robot_state}")
            self.awaiting_command = False
            self.pop_command()

    def send_request(self, command, callback=None):
        logger.info(f"Sending {command}")
        if callback is not None:
            self.callback = callback
        self.current_request = UrlRequest(
            url=f"http://{self.settings['target_ip']}:{self.settings['target_port']}/{command}",
            req_headers={
                "Content-type": "application/x-www-form-urlencoded",
                "Accept": "text/plain",
            },
            on_success=partial(self.on_success, command),
            on_failure=partial(self.on_failure, command),
            on_error=partial(self.on_error, command),
            # timeout=3 if command == "go_home" else None,
        )

    def send_command(self, command, callback):
        if command == "stop":
            self.clear_commands()
            if self.job_in_progress is not None:
                self.job_in_progress.state = JobState.ENDED
                self.callback(
                    message=f"Job {self.job_in_progress.name} - Cancelled",
                    wipe_after=5,
                    log_level=logging.INFO,
                )
                self.job_in_progress.state = JobState.INACTIVE
                self.job_in_progress = None
            self.robot_state["last_state"] = -1
            self.robot_state["current_state"] = -1
            if USE_UDP is True:
                sock = socket.socket(
                    socket.AF_INET,  # Internet
                    socket.SOCK_DGRAM,  # UDP
                )
                sock.sendto(
                    data=bytes("STOP", "utf-8"),
                    address=(
                        self.settings["target_ip"],
                        self.settings["target_stop_port"],
                    ),
                )
            else:
                if (
                    self.current_request is not None
                    and self.current_request.is_finished is False
                ):
                    self.current_request.cancel()
                self.send_request(command=command, callback=callback)
        elif command == "job_ended":
            self.job_in_progress.state = JobState.ENDED
            callback(
                message=f"Job {self.job_in_progress.name} - Ended",
                wipe_after=5,
                log_level=logging.INFO,
            )
            self.job_in_progress.state = JobState.INACTIVE
            self.job_in_progress = None
        elif self.awaiting_command is False:
            self.awaiting_command = True
            if command == "go_next":
                self.robot_state["last_state"] = self.robot_state["current_state"]
                self.robot_state["current_state"] = -1
            elif command in ["stop", "start", "go_home_dirty"]:
                self.robot_state["last_state"] = -1
                self.robot_state["current_state"] = -1
            else:
                logger.error(f"Unknown command: {command}")
            self.send_request(command=command, callback=callback)
        elif self.awaiting_command is True:
            self.push_command(command=command, callback=callback)

    def get_current_plant(self):
        if self.robot_state["current_state"] >= 1:
            tmp = self.plant_data[
                self.plant_data.position == self.robot_state["current_state"]
            ]
            if tmp.shape[0] == 0:
                return {}
            else:
                return tmp.reset_index(drop=True).iloc[0].to_dict()
        else:
            return None

    def snap_request(self):
        plant = self.get_current_plant()
        if plant is None:
            return "no_tray"
        else:
            if not plant:
                return "empty"
            elif plant["allow_capture"]:
                return "allowed"
            else:
                return "disabled"

    def get_picture_name(self):
        plant = self.get_current_plant()
        sep = "#"
        if plant is None:
            return f"rr{sep}noexp_empty{sep}0{sep}{dt.now().strftime('%Y%m%d_%H%M%S')}"
        else:
            return f"rr{sep}{plant['experiment']}{sep}{plant['plant_name']}{sep}{plant['position']}{sep}{dt.now().strftime('%Y%m%d_%H%M%S')}"

    def get_plant_desc(self):
        plant = self.get_current_plant()
        if plant is None:
            return "no plant"
        else:
            return f"[exp:{plant['experiment']}][name:{plant['plant_name']}][pos:{plant['position']}]"

    def snap(self, callback, save_image: bool = True):
        sr = self.snap_request()
        if (self.job_in_progress is not None) and sr == "disabled":
            callback(
                f"Capture not allowed for {self.get_plant_desc()}",
                wipe_after=-1,
                log_level=logging.WARNING,
            )
        else:
            try:
                self.camera.start_preview()
                self.camera.capture(self.path_to_last_image)
                self.camera.stop_preview()
                if save_image is True:
                    shutil.copy(
                        self.path_to_last_image,
                        os.path.join(
                            os.path.dirname(__file__),
                            "..",
                            "data",
                            "images",
                            "to_send"
                            if (self.job_in_progress is not None) and (sr == "allowed")
                            else "to_keep",
                            f"{self.get_picture_name()}.png",
                        ),
                    )
            except Exception as e:
                callback(
                    f"Failed to capture image because {repr(e)}",
                    wipe_after=-1,
                    log_level=logging.ERROR,
                )
                return

            if self.job_in_progress is None:
                prefix = ""
            else:
                prefix = f"Job {self.job_in_progress.name} - "

            if sr == "empty":
                callback(
                    f"{prefix} Snapped at nothing",
                    wipe_after=-1,
                    log_level=logging.WARNING,
                    update_captured_image=True,
                )
            elif sr == "no_tray":
                callback(
                    f"{prefix} No tray in position",
                    wipe_after=-1,
                    log_level=logging.WARNING,
                    update_captured_image=True,
                )
            else:
                callback(
                    f"Snapped {self.get_plant_desc()}",
                    wipe_after=-1,
                    log_level=logging.INFO,
                    update_captured_image=True,
                )

    def execute_job(self, job: JobData, callback):
        callback(
            f"Starting Job {job.name}",
            wipe_after=-1,
            log_level=logging.INFO,
        )
        self.job_in_progress = job
        self.job_in_progress.state = JobState.WAITING_HOME
        self.send_command(
            command="go_home_dirty",
            callback=callback,
        )
        for _ in range(self.settings["tray_count"]):
            self.push_command(
                command="go_next",
                callback=callback,
            )
        self.push_command(
            command="job_ended",
            callback=callback,
        )

    @property
    def path_to_last_image(self):
        return os.path.join(
            os.path.dirname(__file__),
            "..",
            "data",
            "images",
            "last_picture.png",
        )

    @property
    def path_for_send_lock(self) -> Path:
        return Path(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "data",
                "images",
                "snap_in_progress.txt",
            )
        )


def send_pictures(work_seconds: int):
    start = timer()

    src_folder = os.path.join(
        os.path.dirname(__file__), "..", "data", "images", "to_send", ""
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
            if (timer() - start) >= work_seconds:
                logger.info(
                    f"Stopping sending images to avoid job conflicts after {(timer() - start) / 60} minutes"
                )
                break
            try:
                exp_folder = os.path.basename(name).split("#")[1]
                try:
                    ftp.chdir(exp_folder)
                except IOError:
                    logger.info(f"Creating {exp_folder} folder")
                    ftp.mkdir(exp_folder)
                    ftp.chdir(exp_folder)
                ftp.put(os.path.join(src_folder, name), name)
            except Exception as e:
                logger.error(f"Unable to move {name} because {repr(e)}")
            else:
                # Check file size and delete source
                if (
                    os.path.getsize(os.path.join(src_folder, name))
                    == ftp.stat(name).st_size
                ):
                    logger.info(f"Moved {name}, deleted source")
                else:
                    logger.error(f"Wrong destination file size: {name}")

                ftp.chdir("..")
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
                if (timer() - start) >= work_seconds:
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
