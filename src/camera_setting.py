import os
import json

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
import time


with open(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "data",
        "settings.json",
    ),
    "r",
) as f:
    settings = json.load(f)
    width, height = settings["image_resolution"].split("x")
    # if int(width) / int(height) < 1.6:
    #     width, height = "640", "480"
    # else:
    width, height = "640", "480"


Builder.load_string(
    f"""
<CameraClick>:
    orientation: 'vertical'
    Camera:
        id: camera
        resolution: ({width}, {height})
        play: True
    BoxLayout:
        orientation: "horizontal"
        size_hint: 1, 0.2
        ToggleButton:
            text: 'Freeze'
            on_press: camera.play = not camera.play
            size_hint_y: None
            height: '48dp'
        Button:
            text: 'Exit'
            size_hint_y: None
            height: '48dp'
            on_press: root.exit()
"""
)


class CameraClick(BoxLayout):
    def exit(self):
        App.get_running_app().stop()


class TestCamera(App):
    def build(self):
        return CameraClick()


TestCamera().run()
