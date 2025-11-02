@echo off
setlocal
if not defined VENV_DIR set VENV_DIR=.venv
if not exist %VENV_DIR% (
  py -m venv %VENV_DIR%
)
call %VENV_DIR%\Scripts\activate.bat
py -m pip install -U pip
py -m pip install -r requirements.txt
py backend\vri.py
