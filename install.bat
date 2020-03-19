if [%1]==[] goto missing_param
%1 -m venv env && .\env\Scripts\activate.bat && python -m pip install --upgrade pip && python -m pip install docutils pygments pypiwin32 kivy_deps.sdl2==0.1.* kivy_deps.glew==0.1.* && python -m pip install kivy_deps.gstreamer==0.1.* && python -m pip install kivy_deps.angle==0.1.* && python -m pip install kivy==1.11.1 && python -m pip install kivy_examples==1.11.1

:missing_param
echo Please indicate the path to your python.exe file
echo Exemple: install.bat C:\Users\<user_name>\AppData\Local\Programs\Python\Python37\python.exe
echo.
echo If there is a folder called "env" the installation may not be needed, try running launch_me.bat