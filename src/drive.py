import time
import os
import json
from functools import partial
import logging
from datetime import datetime as dt
from datetime import timedelta as td
import datetime
from enum import Enum
import time

import pandas as pd

from kivy.network.urlrequest import UrlRequest

logger = logging.getLogger(__name__)


TEST_MODE = True

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
        "data",
        "test_jobs.json",
    )


class JobState(Enum):
    INACTIVE = 0
    WAITING_HOME = 1
    IN_PROGRESS = 2


def job_state_to_text(state):
    if state == JobState.INACTIVE:
        return "inactive"
    elif state == JobState.WAITING_HOME:
        return "waiting home position"
    elif state == JobState.IN_PROGRESS:
        return "in progress"
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
        self._timestamp_start = dt.strptime(kwargs.get("timestamp_start"), "%Y/%m/%d %H:%M:%S")
        self._timestamp_end = dt.strptime(kwargs.get("timestamp_end"), "%Y/%m/%d %H:%M:%S")
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
                hours = [int(h) for h in self.repetition_value.replace(" ", "").split(",")]
            elif isinstance(self.repetition_value, list):
                hours = self.repetition_value
            else:
                hours = []
            while current < last:
                self.time_points.extend(
                    [dt.combine(date=current, time=datetime.time(hour=h)) for h in hours]
                )
                current = current + td(days=1)

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
        self._timestamp_start = value
        self.update_time_points()

    @property
    def timestamp_end(self):
        return self._timestamp_end

    @timestamp_end.setter
    def timestamp_end(self, value):
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
                self.jobs_data[0].timestamp_start = dt.now() - td(hours=1) + td(seconds=15)
            else:
                self.jobs_data = []

            if os.path.isfile(settings_path):
                with open(settings_path, "r") as f:
                    self.settings = json.load(f)
            else:
                self.settings = {
                    "target_ip": "http://127.0.0.1",
                    "target_port": 8000,
                    "tray_count": 56,
                    "show_images": False,
                }
        except Exception as e:
            logger.error(f"Failed to load data because: {repr(e)}")
        else:
            logger.info("Loaded data")

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
        elif self.robot_state["current_state"] >= 0:
            msg += f"Tray {self.robot_state['current_state']} camera ready"
        else:
            msg += f"Unknown position"
        return msg

    def on_success(self, *args):
        sent_cmd, _, received_command = args

        if sent_cmd != received_command:
            logger.error(
                f"Inconsistent message received, expected {sent_cmd}, received {received_command}"
            )

        if received_command == "go_home":
            self.robot_state["home"] = True
        elif received_command == "go_next" and self.robot_state["home"] is True:
            self.robot_state["current_state"] = 0
            self.robot_state["last_state"] = -1
            self.robot_state["home"] = False
        elif received_command == "go_next":
            self.robot_state["current_state"] = self.robot_state["last_state"] + 1
            self.robot_state["last_state"] = -1
        elif self.robot_state["home"] is True:
            self.robot_state["home"] = False

        if self.job_in_progress is not None:
            if received_command == "go_home":
                if self.job_in_progress.state == JobState.WAITING_HOME:
                    self.job_in_progress.state = JobState.IN_PROGRESS
                    self.callback(
                        message=f"Job {self.job_in_progress.name} - Home position reached",
                        wipe_after=-1,
                        log_level=logging.INFO,
                    )
                elif self.job_in_progress.state == JobState.IN_PROGRESS:
                    self.job_in_progress.state = JobState.INACTIVE
                    self.callback(
                        message=f"Job {self.job_in_progress.name} - Ended",
                        wipe_after=5,
                        log_level=logging.INFO,
                    )
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
                        message=f"Job {self.job_in_progress.name} - {plant['plant_name']} excluded from image capture",
                        wipe_after=-1,
                        log_level=logging.INFO,
                    )
            elif received_command == "stop":
                self.job_in_progress.state = JobState.INACTIVE
                self.callback(
                    message=f"Job {self.job_in_progress.name} - Cancelled",
                    wipe_after=5,
                    log_level=logging.INFO,
                )
        else:
            self.callback(
                message=self.state_to_text(),
                wipe_after=-1 if self.job_in_progress is None else 2,
                log_level=logging.INFO,
            )

        self.awaiting_command = False
        if self.waiting_commands:
            next_command = self.waiting_commands.pop(0)
            self.send_command(
                command=next_command["cmd"],
                callback=next_command["callback"],
            )

    def on_failure(self, on_success, *args):
        _, _, received_command = args
        self.callback(
            message=f"Command: {received_command}, State: {self.robot_state}",
            wipe_after=2,
            log_level=logging.INFO,
        )
        self.awaiting_command = False
        if self.waiting_commands:
            next_command = self.waiting_commands.pop(0)
            self.send_command(
                command=next_command["cmd"],
                feedback_label=next_command["feedback_label"],
            )

    def send_command(self, command, callback):
        if command == "stop" or self.awaiting_command is False:
            self.awaiting_command = True
            if command == "stop":
                self.waiting_commands = []
                self.job_in_progress = None
                self.robot_state["last_state"] = -1
                self.robot_state["current_state"] = -1
            elif command == "go_next":
                self.robot_state["last_state"] = self.robot_state["current_state"]
                self.robot_state["current_state"] = -1
            elif command in ["stop", "start", "go_home"]:
                self.robot_state["last_state"] = -1
                self.robot_state["current_state"] = -1
            elif command in ["go_home"]:
                self.robot_state["last_state"] = -1
                self.robot_state["current_state"] = -1
            else:
                logger.error(f"Unknown command: {command}")
            self.callback = callback
            logger.info(f"Sent {command}")
            self.r = UrlRequest(
                url=f"{self.settings['target_ip']}:{self.settings['target_port']}",
                req_body=f'{{"action": "{command}"}}',
                on_success=partial(self.on_success, command),
                on_failure=partial(self.on_failure, command),
            )
        elif self.awaiting_command is True:
            self.waiting_commands.append({"cmd": command, "callback": callback})

    def get_current_plant(self):
        if self.robot_state["current_state"] >= 0:
            tmp = self.plant_data[self.plant_data.position == self.robot_state["current_state"]]
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

    def snap(self, callback):
        sr = self.snap_request()
        if self.job_in_progress is None:
            prefix = ""
        else:
            prefix = f"Job {self.job_in_progress.name} - "
        if sr == "empty":
            callback(
                f"{prefix}Snapped at nothing",
                wipe_after=-1,
                log_level=logging.WARNING,
            )
        elif sr == "disabled":
            callback(
                f"{prefix}Capture not allowed for plant {self.get_current_plant()['plant_name']}",
                wipe_after=-1,
                log_level=logging.WARNING,
            )
        elif sr == "allowed":
            callback(
                f"{prefix}Snapped plant {self.get_current_plant()['plant_name']}",
                wipe_after=-1,
                log_level=logging.INFO,
            )
            time.sleep(1)
        elif sr == "no_tray":
            callback(
                f"{prefix}No tray in position",
                wipe_after=-1,
                log_level=logging.WARNING,
            )

    def execute_job(self, job: JobData, callback):
        if job.enabled is True:
            callback(
                f"Starting Job {job.name}",
                wipe_after=-1,
                log_level=logging.INFO,
            )
            self.job_in_progress = job
            self.job_in_progress.state = JobState.WAITING_HOME
            self.send_command(
                command="go_home",
                callback=callback,
            )
            for _ in range(self.settings["tray_count"]):
                self.send_command(
                    command="go_next",
                    callback=callback,
                )
            self.send_command(
                command="go_home",
                callback=callback,
            )
        else:
            callback(
                f"Job {job.name} is not active, skipped",
                wipe_after=-1,
                log_level=logging.WARNING,
            )
