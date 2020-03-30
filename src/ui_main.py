import os
from datetime import datetime as dt
from datetime import timedelta as td
from uuid import uuid4
import json

import pandas as pd
import numpy as np

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
from kivy.uix.filechooser import FileChooserListView

import drive as drive

Config.set("graphics", "width", "800")
Config.set("graphics", "height", "480")
Config.set("graphics", "borderless", "1")

TEST_MODE = True

plant_data_path = os.path.join(".", "data", "plants_data.csv")
if TEST_MODE:
    jobs_file_path = os.path.join(".", "test_files", "test_jobs.json")
    log_file_path = os.path.join(".", "test_files", "test_logs.txt")
else:
    jobs_file_path = os.path.join(".", "data", "jobs_data.json")
    log_file_path = os.path.join(".", "data", "logs.txt")

if os.path.isfile(plant_data_path):
    plant_data = pd.read_csv(plant_data_path)
else:
    plant_data = pd.DataFrame(
        columns=["experiment", "plant_name", "position", "allow_capture"]
    )

if os.path.isfile(jobs_file_path):
    with open(jobs_file_path, "r") as f:
        jobs_data = json.load(f)
else:
    jobs_data = {"jobs": []}

if os.path.isfile(log_file_path):
    with open(log_file_path, "r") as f:
        log_data = [
            line.replace("\n", "") for line in f.readlines() if line != "\n"
        ]
else:
    log_data = []


class RootWidget(BoxLayout):
    pass


class ModalDialog(ModalView):

    modal_dialog_title = ObjectProperty(None)
    modal_dialog_body = ObjectProperty(None)


class SelectableRecycleBoxLayout(
    FocusBehavior, LayoutSelectionBehavior, RecycleBoxLayout
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

    def on_back(self):
        self.current_screen.back()

    def back_text(self):
        return self.current_screen.back_text

    def format_text(
        self, text: str, is_bold: bool = False, font_size: int = 0
    ):
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


class StartUpPage(Screen):
    back_text = "< Exit"
    title_text = "Start up"
    info_text = "Welcome to RobotRacine control center"
    modal_dialog = None

    def dialog_callback(self, instance):
        if instance.modal_result == 1:
            plant_data.to_csv(plant_data_path, index=False)
            with open(os.path.join(".", "data", "logs.txt"), "w") as f:
                f.writelines(log_data)
            with open(os.path.join(".", "data", "jobs_data.json"), "w") as f:
                json.dump(jobs_data, f, indent=2)
            App.get_running_app().stop()
        return False

    def back(self):
        self.modal_dialog = ModalDialog()
        self.modal_dialog.modal_dialog_title.text = self.manager.format_text(
            text="Confirmation required", is_bold=False, font_size=0
        )
        self.modal_dialog.modal_dialog_body.text = (
            "Quit program?\nAll jobs will be stopped."
        )
        self.modal_dialog.bind(on_dismiss=self.dialog_callback)
        self.modal_dialog.open()


class MyScreen(Screen):
    def back(self):
        self.manager.set_active_page(
            new_page_name=self.back_target, direction="right"
        )


class ManualRoot(MyScreen):
    back_text = "< Back"
    back_target = "start_up"
    title_text = "Manual Override"
    info_text = "Take control of the robot"

    def go_home(self):
        self.manager.lbl_status.text = "Going Home"
        drive.go_home()
        self.manager.lbl_status.text = "Went Home"

    def run(self):
        self.manager.lbl_status.text = "Engine On"
        drive.run()

    def go_next(self):
        self.manager.lbl_status.text = "Setting next plant"
        drive.go_next()
        self.manager.lbl_status.text = "Next plant set"

    def stop(self):
        drive.stop()
        self.manager.lbl_status.text = "Engine stopped"


class ManualCapture(MyScreen):
    back_text = "< Back"
    back_target = "manual_root"
    title_text = "Manual Capture"
    info_text = "Set the camera and take snapshots"

    bt_back = ObjectProperty(None)

    def snap(self):
        self.manager.lbl_status.text = "Oh, snap"


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
                for plant in plant_data.plant_name.unique()
                if plant not in self.selected_plants_list
            ]
        ]
        self.ids["selected_plants"].data = [
            {"text": j} for j in self.selected_plants_list
        ]

    def add_to_selection(self):
        selected_nodes = self.ids[
            "available_plants"
        ].layout_manager.selected_nodes
        self.ids["available_plants"].layout_manager.selected_nodes = []
        if selected_nodes:
            self.selected_plants_list.extend(
                [
                    self.ids["available_plants"].data[i]["text"]
                    for i in selected_nodes
                ]
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
    back_target = "jobs"
    title_text = "Manage jobs"
    info_text = "About the jobs..."
    jobs_list = "Take a snapshot"

    job_description = ObjectProperty(None)

    def init_jobs(self):
        set_index = not self.jobs_list.data
        self.jobs_list.data = [
            {"text": j["name"], "guid": j["guid"]} for j in jobs_data["jobs"]
        ]
        if set_index and self.jobs_list.data:
            self.jobs_list.layout_manager.selected_nodes = [0]

    def get_current_description(self):
        return "description"

    def get_job(self, guid):
        for job in jobs_data["jobs"]:
            if job["guid"] == guid:
                return job
        else:
            return None

    def get_job_index(self, guid):
        for i, job in enumerate(jobs_data["jobs"]):
            if job["guid"] == guid:
                return i
        else:
            return -1

    def new_job(self):
        if not jobs_data:
            jobs_data["jobs"] = []
        jobs_data["jobs"].append(
            {
                "name": "Job " + dt.now().strftime("%Y%m%d %H:%M:%S"),
                "state": "active",
                "guid": str(uuid4()),
                "description": "",
                "owner": "",
                "mail_to": "",
                "repetition_mode": "every",
                "repetition_value": 6,
                "repetition_unit": "hours",
                "timestamp_start": dt.now().strftime("%Y%m%d %H:%M:%S"),
                "timestamp_end": (dt.now() + td(days=14)).strftime(
                    "%Y%m%d %H:%M:%S"
                ),
                "plants": "",
            }
        )
        self.init_jobs()
        self.update_data(guid=jobs_data["jobs"][-1]["guid"])
        self.jobs_list.layout_manager.selected_nodes = [
            len(jobs_data["jobs"]) - 1
        ]

    def update_data(self, guid):
        job = self.get_job(guid=guid)
        if job is None:
            return
        self.job_name.input_text = job["name"]
        self.job_guid = guid
        self.job_state.text = "" if job["state"] == "active" else "paused"
        self.job_description.input_text = job["description"]
        self.job_owner.input_text = job["owner"]
        self.job_mail_list.input_text = "; ".join(job["mail_to"])
        self.time_mode.text = job["repetition_mode"]
        self.time_value.text = str(job["repetition_value"])
        self.time_unit.text = job["repetition_unit"]
        self.date_start.text = job["timestamp_start"]
        self.date_end.text = job["timestamp_end"]
        self.job_plant_list.text = ";".join(job["plants"])

    def save_job(self, guid):
        index = self.get_job_index(guid=guid)
        if index < 0:
            return
        jobs_data["jobs"][index]["name"] = self.job_name.text_holder.text
        jobs_data["jobs"][index]["state"] = (
            "paused" if self.job_state.text == "paused" else "active"
        )
        jobs_data["jobs"][index][
            "description"
        ] = self.job_description.text_holder.text
        jobs_data["jobs"][index]["owner"] = self.job_owner.text_holder.text
        jobs_data["jobs"][index][
            "mail_to"
        ] = self.job_mail_list.text_holder.text.replace(" ", "").split(";")
        jobs_data["jobs"][index]["repetition_mode"] = self.time_mode.text
        try:
            jobs_data["jobs"][index]["repetition_value"] = int(
                self.time_value.text
            )
        except:
            jobs_data["jobs"][index]["repetition_value"] = 0
        jobs_data["jobs"][index]["repetition_unit"] = self.time_unit.text
        jobs_data["jobs"][index]["timestamp_start"] = self.date_start.text
        jobs_data["jobs"][index]["timestamp_end"] = self.date_end.text

    def resume_job(self, guid):
        job = self.get_job(guid=guid)
        if job is None:
            return
        job["state"] = "active"
        self.update_data(guid=guid)

    def pause_job(self, guid):
        job = self.get_job(guid=guid)
        if job is None:
            return
        job["state"] = "paused"
        self.update_data(guid=guid)

    def delete_job(self, guid):
        index = self.get_job_index(guid=guid)
        if index < 0:
            return
        jobs_data["jobs"].pop(index)
        self.init_jobs()
        self.update_data(guid=jobs_data["jobs"][-1]["guid"])

    def close_plant_selection(self, instance):
        if instance.modal_result == 1:
            current_plants = [
                d["text"] for d in instance.ids["selected_plants"].data
            ]
            instance.job["plants"] = current_plants
            self.update_data(guid=instance.job["guid"])
        return False

    def select_plants(self, guid):
        job = self.get_job(guid=guid)
        if job is None:
            return
        self.plant_selector = PlantSelector()
        pl = job["plants"][:]
        if not pl:
            pl = []
        self.plant_selector.selected_plants_list = pl
        self.plant_selector.job = job
        self.plant_selector.update_list_views()
        self.plant_selector.bind(on_dismiss=self.close_plant_selection)
        self.plant_selector.open()


class JobsLog(MyScreen):
    back_text = "< Back"
    back_target = "jobs"
    title_text = "Jobs log"
    info_text = "Logs, logs everywhere"

    def init_logs(self):
        self.log_text.text = "\n".join(reversed(log_data))


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
            {"text": j} for j in plant_data.experiment.unique()
        ]

    def close_file_selection(self, instance):
        if instance.modal_result == 1:
            try:
                new_df = pd.read_csv(instance.ids["file_name"].text)
            except Exception as e:
                log_data.append(
                    f"{dt.now().strftime('%Y%m%d %H:%M:%S')} - Failed to load data in because {repr(e)}"
                )
            else:
                global plant_data
                plant_data = pd.concat((plant_data, new_df)).drop_duplicates()
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
                for j in plant_data[
                    plant_data.experiment == experiment
                ].plant_name
            ]
        else:
            self.plants_list.data = []

    def remove_experiment(self):
        global plant_data
        plant_data = plant_data[
            ~plant_data.experiment.isin(
                [
                    self.ids["experiments_list"].data[i]["text"]
                    for i in self.ids[
                        "experiments_list"
                    ].layout_manager.selected_nodes
                ]
            )
        ]
        self.ids["experiments_list"].layout_manager.selected_nodes = []
        self.plants_list.data = []
        self.init_experiments()


class RobotRacineApp(App):
    title = "RobotRacine"

    def build(self):
        return RootWidget()


if __name__ == "__main__":
    rr_app = RobotRacineApp()
    rr_app.run()
