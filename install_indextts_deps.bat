@echo off
chcp 65001 >nul
title IndexTTS2 依赖安装

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║              IndexTTS2 依赖安装脚本                          ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

echo 正在安装 IndexTTS2 所需的依赖...
echo 这可能需要几分钟到几十分钟，取决于网络速度。
echo.

Python3\python.exe install_indextts_deps.py

echo.
echo 按任意键退出...
pause >nul
