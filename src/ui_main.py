import os

import pandas as pd
import numpy as np
import json

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.config import Config
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, ObjectProperty, BooleanProperty
from kivy.uix.button import Button
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.label import Label

import drive as drive

Config.set("graphics", "width", "800")
Config.set("graphics", "height", "480")


class RootWidget(BoxLayout):
    pass


class SelectableRecycleBoxLayout(
    FocusBehavior, LayoutSelectionBehavior, RecycleBoxLayout
):
    """ Adds selection and focus behavior to the view. """


class SelectableLabel(RecycleDataViewBehavior, Label):
    """ Add selection support to the Label """

    index = None
    selected = BooleanProperty(False)
    selectable = BooleanProperty(True)

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
        if (
            self.selected
            and hasattr(rv, "page")
            and hasattr(rv.page, "update_data")
        ):
            rv.page.update_data(self.text)


root_folder = "./data/" if os.path.isdir("./data/") else "../data"
plant_data = pd.read_csv(os.path.join(root_folder, "plants_data.csv"))
with open(os.path.join(root_folder, "jobs_data.json"), "r") as f:
    jobs_data = json.load(f)


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

    def back(self):
        App.get_running_app().stop()


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
        self.ids["mo_home"].text = "Going Home"
        drive.go_home()
        self.ids["mo_home"].text = "Went Home"

    def run(self):
        drive.run()

    def go_next(self):
        drive.go_next()

    def stop(self):
        drive.stop()


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


class JobsManage(MyScreen):
    back_text = "< Back"
    back_target = "jobs"
    title_text = "Manage jobs"
    info_text = "About the jobs..."
    jobs_list = "Take a snapshot"

    job_description = ObjectProperty(None)

    def init_jobs(self):
        self.jobs_list.data = [{"text": j["name"]} for j in jobs_data["jobs"]]
        print("init jobs")

    def get_current_description(self):
        return "description"

    def update_data(self, name):
        for job in jobs_data["jobs"]:
            if job["name"] == name:
                self.job_description.input_text = job["description"]
                self.job_owner.input_text = job["owner"]
                self.job_mail_list.input_text = "; ".join(job["mail_to"])
                self.time_mode.text = job["repetition_mode"]
                self.time_value.text = str(job["repetition_value"])
                self.time_unit.text = job["repetition_unit"]
                self.date_start.text = job["timestamp_start"]
                self.date_end.text = job["timestamp_end"]
                self.job_plants.input_text = "; ".join(job["plants"])
                continue

    def save_job(self):
        print("Save job")

    def resume_job(self):
        print("Save job")

    def pause_job(self):
        print("Pause job")

    def delete_job(self):
        print("Delete job")


class JobsLog(MyScreen):
    back_text = "< Back"
    back_target = "jobs"
    title_text = "Jobs log"
    info_text = "Logs, logs everywhere"


class DataIn(MyScreen):
    back_text = "< Back"
    back_target = "start_up"
    title_text = "Data In"
    info_text = "View/add/remove Data In files"


class DataInEdit(MyScreen):
    back_text = "< Back"
    back_target = ""
    title_text = "Edit Data In"
    info_text = "Edit Data In"


class RobotRacineApp(App):
    title = "RobotRacine"

    def build(self):
        return RootWidget()


if __name__ == "__main__":
    rr_app = RobotRacineApp()
    rr_app.run()
