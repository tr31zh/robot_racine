from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.config import Config

import drive as drive

Config.set("graphics", "width", "800")
Config.set("graphics", "height", "480")


class RootWidget(ScreenManager):
    pass


class StartUpPage(Screen):
    back_text = "< Exit"

    def back(self):
        App.get_running_app().stop()


class MyScreen(Screen):
    def back(self):
        self.manager.transition.direction = "right"
        self.manager.current = self.back_target


class ManualRoot(MyScreen):
    back_text = "< Back"
    back_target = "start_up"

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


class ManualStream(MyScreen):
    back_text = "< Back"
    back_target = "manual_root"


class Jobs(MyScreen):
    back_text = "< Back"
    back_target = "start_up"


class JobsView(MyScreen):
    back_text = "< Back"
    back_target = ""


class JobsEditAdd(MyScreen):
    back_text = "< Back"
    back_target = ""


class JobsLog(MyScreen):
    back_text = "< Back"
    back_target = ""


class DataIn(MyScreen):
    back_text = "< Back"
    back_target = "start_up"


class DataInEdit(MyScreen):
    back_text = "< Back"
    back_target = ""


class RobotRacineApp(App):
    title = "RobotRacine"

    def build(self):
        return RootWidget()


if __name__ == "__main__":
    rr_app = RobotRacineApp()
    rr_app.run()
