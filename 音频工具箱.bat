@echo off
setlocal

rem Always run from the project root (this script's directory)
cd /d "%~dp0"

set "PythonPath=%~dp0Python3\python.exe"

if /I "%~1"=="dev" (
	"%PythonPath%" -B dev_runner.py
) else (
	"%PythonPath%" -B main.py
)

endlocal

:: 开发环境使用命令 & ".\音频工具箱.bat" dev 可支持热更新。
