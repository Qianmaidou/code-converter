@echo off
chcp 65001 >nul
title 代码转换器
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo   [错误] 没有找到 Python。
  echo   请先安装 Python 3.8 或更高版本（安装时勾选 Add python.exe to PATH），
  echo   安装完成后重新双击本文件即可。
  echo.
  pause
  exit /b 1
)

echo 正在启动代码转换器，浏览器将自动打开…
echo 使用完毕后，关闭本窗口即可退出程序。
echo.
python server.py
pause
