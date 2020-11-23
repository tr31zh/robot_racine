import os
import logging
from datetime import datetime as dt
from datetime import timedelta as td


log_folder = os.path.join(
    os.path.dirname(__file__),
    "..",
    "data",
    "logs",
    "",
)
if not os.path.exists(log_folder):
    os.mkdir(log_folder)
log_path = os.path.join(log_folder, f"{dt.now().strftime('%Y%m%d %H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(name)s - %(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler(
            log_path,
            mode="a",
            delay=True,
        )
    ],
)

from uuid import uuid4
from functools import partial

import pandas as pd

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.config import Config
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, ObjectProperty, BooleanProperty
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.clock import Clock

from drive import Controller, JobData, JobState


controller: Controller = Controller()

Config.set("graphics", "width", "800")
Config.set("graphics", "height", "480")
Config.set("graphics", "borderless", "1")


logger = logging.getLogger("ui")


class RootWidget(BoxLayout):
    pass


class ModalDialog(ModalView):

    modal_dialog_title = ObjectProperty(None)
    modal_dialog_body = ObjectProperty(None)


class SelectableRecycleBoxLayout(
    FocusBehavior,
    LayoutSelectionBehavior,
    RecycleBoxLayout,
):
    """ Adds selection and focus behavior to the view. """


class SelectableLabel(RecycleDataViewBehavior, Label):
    """ Add selection support to the Label """

    index = None
    selected = BooleanProperty(False)
    selectable = BooleanProperty(True)
    guid = StringProperty("")

    def refresh_view_attrs(self, rv, index, data):
        """ Catch and handle the view changes """
        self.index = index
        return super(SelectableLabel, self).refresh_view_attrs(rv, index, data)

    def on_touch_down(self, touch):
        """ Add selection on touch down """
        if super(SelectableLabel, self).on_touch_down(touch):
            return True
        if self.collide_point(*touch.pos) and self.selectable:
            return self.parent.select_with_touch(self.index, touch)

    def apply_selection(self, rv, index, is_selected):
        """ Respond to the selection of items in the view. """
        self.selected = is_selected
        if self.selected and hasattr(rv, "page"):
            if hasattr(rv.page, "update_data"):
                rv.page.update_data(guid=self.guid)
            elif hasattr(rv.page, "update_plants"):
                rv.page.update_plants(experiment=self.text)


class MyPageManager(ScreenManager):
    bt_back = ObjectProperty(None)
    lbl_title = ObjectProperty(None)
    lbl_info = ObjectProperty(None)
    lbl_status = ObjectProperty(None)
    event = None

    def __init__(self, **kwargs):
        super(MyPageManager, self).__init__(**kwargs)
        self.countdown_event = Clock.schedule_interval(
            self.update_countdown,
            0.1,
        )

    def on_back(self):
        self.current_screen.back()

    def on_stop(self):
        controller.send_command(
            command="stop",
            callback=self.update_status,
        )

    def back_text(self):
        return self.current_screen.back_text

    def format_text(self, text: str, is_bold: bool = False, font_size: int = 0):
        prefix = "[b]" if is_bold else ""
        prefix += f"[size={font_size}]" if font_size > 0 else ""
        suffix = "[/b]" if is_bold else ""
        suffix += "[/size]" if font_size > 0 else ""
        return f"{prefix}{text}{suffix}"

    def set_active_page(self, new_page_name: str, direction: str):
        self.transition.direction = direction
        self.current = new_page_name
        self.bt_back.text = self.current_screen.back_text
        self.lbl_title.text = self.format_text(
            self.current_screen.title_text, is_bold=True, font_size=30
        )
        self.lbl_info.text = self.current_screen.info_text
        self.lbl_status.text = ""

    def update_status(
        self,
        message: str,
        wipe_after: float,
        reset_event: bool = True,
        log_level: int = logging.INFO,
    ):
        self.lbl_status.text = message
        if self.event is not None and reset_event:
            self.event.cancel()
            self.event = None
        if wipe_after > 0:
            self.event = Clock.schedule_interval(
                partial(self.delayed_update_status, ""),
                wipe_after,
            )
        if log_level == logging.DEBUG:
            logger.debug(message)
        elif log_level == logging.INFO:
            logger.info(message)
        elif log_level == logging.WARNING:
            logger.warning(message)
        elif log_level == logging.ERROR:
            logger.error(message)
        elif log_level == logging.CRITICAL:
            logger.critical(message)
        else:
            logger.info(message)

    def delayed_update_status(self, message, dt):
        self.lbl_status.text = message
        return False

    def update_countdown(self, delta):
        if controller.job_in_progress is not None:
            jib = controller.job_in_progress
            if jib.state == JobState.WAITING_HOME:
                js = "waiting home position"
                self.pg_global.value = 0
            elif jib.state == JobState.IN_PROGRESS:
                idx = max(
                    controller.robot_state["current_state"],
                    controller.robot_state["last_state"],
                )
                self.pg_global.value = idx / controller.settings["tray_count"]
                js = f"in progress {idx}/{controller.settings['tray_count']}"
            elif jib.state == JobState.INACTIVE:
                js = "ended"
                self.pg_global.value = 0
            else:
                js = "unknown"
            self.lbl_info.text = self.lbl_info.text = self.format_text(
                f"Job {controller.job_in_progress.name} {js}",
                is_bold=True,
                font_size=20,
            )
        else:
            self.pg_global.value = 0
            next_job = controller.get_next_job()
            if next_job:
                count_down_text = ""
                td_next = next_job.next_time_point - dt.now()
                if td_next.days < 1 and td_next.seconds < 11:
                    if td_next.seconds > 0.5:
                        self.lbl_info.text = self.format_text(
                            f"Next job {next_job.name} WILL start in {td_next.seconds}{'  ' * round(td_next.seconds)} >",
                            is_bold=True,
                            font_size=20,
                        )
                    else:
                        controller.execute_job(next_job, self.update_status)
                else:
                    count_down_text += f"{td_next.days} days "
                    hours, remainder = divmod(td_next.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    count_down_text += f"{hours} hours "
                    count_down_text += f"{minutes} minutes "
                    count_down_text += f"and {seconds} seconds"
                    self.lbl_info.text = f"Next job {next_job.name} starts in {count_down_text}"
            else:
                self.lbl_info.text = "No job in schedule"

        return True


class StartUpPage(Screen):
    back_text = "< Exit"
    title_text = "Start up"
    info_text = "Welcome to RobotRacine control center"
    modal_dialog = None

    def dialog_callback(self, instance):
        if instance.modal_result == 1:
            controller.send_command(
                command="stop",
                callback=self.manager.update_status,
            )
            controller.save()
            App.get_running_app().stop()
        return False

    def back(self):
        self.modal_dialog = ModalDialog()
        self.modal_dialog.modal_dialog_title.text = self.manager.format_text(
            text="Confirmation required", is_bold=False, font_size=0
        )
        self.modal_dialog.modal_dialog_body.text = "Quit program?\nAll jobs will be stopped."
        self.modal_dialog.bind(on_dismiss=self.dialog_callback)
        self.modal_dialog.open()


class MyScreen(Screen):
    def back(self):
        self.manager.set_active_page(
            new_page_name=self.back_target,
            direction="right",
        )


class ManualRoot(MyScreen):
    back_text = "< Back"
    back_target = "start_up"
    title_text = "Manual Override"
    info_text = "Take control of the robot"

    def go_home(self):
        controller.send_command(
            command="go_home",
            callback=self.manager.update_status,
        )

    def go_next(self):
        controller.send_command(
            command="go_next",
            callback=self.manager.update_status,
        )

    def stop(self):
        controller.send_command(
            command="stop",
            callback=self.manager.update_status,
        )

    def start(self):
        controller.send_command(
            command="start",
            callback=self.manager.update_status,
        )


class ManualCapture(MyScreen):
    back_text = "< Back"
    back_target = "start_up"
    title_text = "Manual Capture"
    info_text = "Set the camera and take snapshots"

    bt_back = ObjectProperty(None)

    def snap(self):
        controller.snap(callback=self.manager.update_status)


class Jobs(MyScreen):
    back_text = "< Back"
    back_target = "start_up"
    title_text = "Jobs"
    info_text = "All about jobs"


class PlantSelector(ModalView):

    available_plants = ObjectProperty(None)
    selected_plants = ObjectProperty(None)
    selected_plants_list = []
    job = None

    def update_list_views(self):
        self.ids["available_plants"].data = [
            {"text": j}
            for j in [
                plant
                for plant in controller.plant_data.plant_name.unique()
                if plant not in self.selected_plants_list
            ]
        ]
        self.ids["selected_plants"].data = [{"text": j} for j in self.selected_plants_list]

    def add_to_selection(self):
        selected_nodes = self.ids["available_plants"].layout_manager.selected_nodes
        self.ids["available_plants"].layout_manager.selected_nodes = []
        if selected_nodes:
            self.selected_plants_list.extend(
                [self.ids["available_plants"].data[i]["text"] for i in selected_nodes]
            )
            self.update_list_views()

    def remove_from_selection(self):
        selected_nodes = [
            self.ids["selected_plants"].data[i]["text"]
            for i in self.ids["selected_plants"].layout_manager.selected_nodes
        ]
        self.ids["selected_plants"].layout_manager.selected_nodes = []
        if selected_nodes:
            self.selected_plants_list = [
                p for p in self.selected_plants_list if p not in selected_nodes
            ]
            self.update_list_views()


class JobsManage(MyScreen):
    back_text = "< Back"
    back_target = "start_up"
    title_text = "Manage jobs"
    info_text = "About the jobs..."
    jobs_list = "Take a snapshot"

    job_description = ObjectProperty(None)

    def init_jobs(self):
        set_index = not self.jobs_list.data
        self.jobs_list.data = [{"text": j.name, "guid": j.guid} for j in controller.jobs_data]
        if set_index and self.jobs_list.data:
            self.jobs_list.layout_manager.selected_nodes = [0]

    def get_current_description(self):
        return "description"

    def get_job(self, guid):
        for job in controller.jobs_data:
            if job.guid == guid:
                return job
        else:
            return None

    def get_job_index(self, guid):
        for i, job in enumerate(controller.jobs_data):
            if job.guid == guid:
                return i
        else:
            return -1

    def new_job(self):
        controller.jobs_data.append(
            JobData(
                **{
                    "name": "Job " + dt.now().strftime("%Y%m%d %H:%M:%S"),
                    "enabled": True,
                    "guid": str(uuid4()),
                    "description": "",
                    "owner": "",
                    "mail_to": "",
                    "repetition_mode": "every",
                    "repetition_value": 6,
                    "timestamp_start": dt.now(),
                    "timestamp_end": dt.now() + td(days=14),
                    "plants": "",
                }
            )
        )
        self.init_jobs()
        self.update_data(guid=controller.jobs_data[-1].guid)
        self.jobs_list.layout_manager.selected_nodes = [len(controller.jobs_data) - 1]

    def update_data(self, guid):
        job = self.get_job(guid=guid)
        if job is None:
            return
        self.job_name.input_text = job.name
        self.job_guid = guid
        self.job_description.input_text = job.description
        self.job_owner.input_text = job.owner
        self.job_mail_list.input_text = "; ".join(job.mail_to)
        self.time_mode.text = job.repetition_mode
        self.time_value.text = str(job.repetition_value)
        self.date_start.text = job.timestamp_start.strftime("%Y/%m/%d %H:%M:%S")
        self.date_end.text = job.timestamp_end.strftime("%Y/%m/%d %H:%M:%S")
        self.job_plant_list.text = ";".join(job.plants)

        if job.enabled is True:
            self.state_image_button.image_path = "../resources/active.png"
            self.state_image_button.lbl_text = "active"
        else:
            self.state_image_button.image_path = "../resources/paused.png"
            self.state_image_button.lbl_text = "paused"

    def save_job(self, guid):
        index = self.get_job_index(guid=guid)
        if index < 0:
            return
        controller.jobs_data[index].name = self.job_name.text_holder.text
        controller.jobs_data[index].enabled = self.state_image_button.lbl_text == "active"
        controller.jobs_data[index]["description"] = self.job_description.text_holder.text
        controller.jobs_data[index].owner = self.job_owner.text_holder.text
        controller.jobs_data[index].mail_to = self.job_mail_list.text_holder.text.replace(
            " ", ""
        ).split(";")
        controller.jobs_data[index].repetition_mode = self.time_mode.text
        try:
            controller.jobs_data[index].repetition_value = int(self.time_value.text)
        except:
            controller.jobs_data[index].repetition_value = 0
        controller.jobs_data[index].timestamp_start = self.date_start.text
        controller.jobs_data[index].timestamp_end = self.date_end.text

    def toggle_job_state(self, guid):
        job = self.get_job(guid=guid)
        if job is None:
            return
        if job.enabled is True:
            self.state_image_button.image_path = "../resources/paused.png"
            job.enabled = False
            self.state_image_button.lbl_text = "paused"
        else:
            self.state_image_button.image_path = "../resources/active.png"
            job.enabled = True
            self.state_image_button.lbl_text = "Enabled"
        self.update_data(guid=guid)

    def start_job(self, guid):
        job = self.get_job(guid=guid)
        if job is None:
            return
        controller.execute_job(job, self.manager.update_status)

    def delete_job(self, guid):
        index = self.get_job_index(guid=guid)
        if index < 0:
            return
        controller.jobs_data.pop(index)
        self.init_jobs()
        self.update_data(guid=controller.jobs_data[-1].guid)

    def close_plant_selection(self, instance):
        if instance.modal_result == 1:
            current_plants = [d["text"] for d in instance.ids["selected_plants"].data]
            instance.job["plants"] = current_plants
            self.update_data(guid=instance.job.guid)
        return False

    def select_plants(self, guid):
        job = self.get_job(guid=guid)
        if job is None:
            return
        self.plant_selector = PlantSelector()
        pl = job.plants[:]
        if not pl:
            pl = []
        self.plant_selector.selected_plants_list = pl
        self.plant_selector.job = job
        self.plant_selector.update_list_views()
        self.plant_selector.bind(on_dismiss=self.close_plant_selection)
        self.plant_selector.open()


class JobsLog(MyScreen):
    back_text = "< Back"
    back_target = "start_up"
    title_text = "Logs"
    info_text = "Logs, logs everywhere"

    def init_logs(self):
        with open(log_path, "r") as f:
            self.log_text.text = "\n".join(
                reversed([line.replace("\n", "") for line in f.readlines() if line != "\n"])
            )


class FileLoader(ModalView):
    file_name = ObjectProperty(None)


class DataIn(MyScreen):
    back_text = "< Back"
    back_target = "start_up"
    title_text = "Data In"
    info_text = "View/add/remove Data In files"

    experiments_list = ObjectProperty(None)
    plants_list = ObjectProperty(None)

    def init_experiments(self):
        self.experiments_list.data = [
            {"text": j} for j in controller.plant_data.experiment.unique()
        ]

    def close_file_selection(self, instance):
        if instance.modal_result == 1:
            try:
                new_df = pd.read_csv(instance.ids["file_name"].text)
            except Exception as e:
                logger.error(f"Failed to load data in because {repr(e)}")
            else:
                controller.plant_data = pd.concat(
                    (controller.plant_data, new_df)
                ).drop_duplicates()
                self.init_experiments()
        return False

    def load_file(self):
        self.file_loader = FileLoader()
        self.file_loader.bind(on_dismiss=self.close_file_selection)
        self.file_loader.open()

    def update_plants(self, experiment):
        if experiment:
            self.plants_list.data = [
                {"text": j}
                for j in controller.plant_data[
                    controller.plant_data.experiment == experiment
                ].plant_name
            ]
        else:
            self.plants_list.data = []

    def remove_experiment(self):
        controller.plant_data = controller.plant_data[
            ~controller.plant_data.experiment.isin(
                [
                    self.ids["experiments_list"].data[i]["text"]
                    for i in self.ids["experiments_list"].layout_manager.selected_nodes
                ]
            )
        ]
        self.ids["experiments_list"].layout_manager.selected_nodes = []
        self.plants_list.data = []
        self.init_experiments()


class SettingsPage(MyScreen):
    back_text = "< Back"
    back_target = "start_up"
    title_text = "Settings"
    info_text = "Manage Robot Racine"

    def init_settings(self):
        self.target_ip.text = controller.settings["target_ip"]
        self.target_port.text = str(controller.settings["target_port"])
        self.tray_count.text = str(controller.settings["tray_count"])

    def save_settings(self):
        try:
            controller.settings["target_ip"] = self.target_ip.text
            controller.settings["target_port"] = int(self.target_port.text)
            controller.settings["tray_count"] = self.tray_count.text
        except Exception as e:
            logger.error(f"Failed to save settings because: {repr(e)}")
        else:
            controller.save_settings()


class RobotRacineApp(App):
    title = "RobotRacine"

    def build(self):
        return RootWidget()


if __name__ == "__main__":
    logger.info("Starting Robot Racine UI")
    logger.info("________________________")
    rr_app = RobotRacineApp()
    rr_app.run()
