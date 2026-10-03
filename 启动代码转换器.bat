@echo off
title 代码转换器
cd /d "%~dp0"

set "URL=http://127.0.0.1:8765/"

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo   [错误] 没有找到 Python。
  echo   请先安装 Python 3.8 或更高版本（安装时勾选 Add python.exe to PATH），
  echo   安装完成后重新双击本文件即可。
  echo.
  timeout /t 3 /nobreak >nul
  exit /b 1
)

echo 正在启动代码转换器，浏览器将自动打开…

REM ---------- 若服务已在运行，直接打开浏览器 ----------
set "CODE="
for /f %%i in ('curl.exe -s -o NUL -w "%%{http_code}" --max-time 2 %URL%api/langs 2^>nul') do set "CODE=%%i"
if "%CODE%"=="200" (
  echo 服务已在后台运行，直接打开浏览器…
  start "" "%URL%"
  exit /b 0
)

REM ---------- 后台启动服务（隐藏窗口，无需保留任何窗口） ----------
where pythonw >nul 2>nul
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath 'python.exe' -ArgumentList 'server.py','--port','8765','--no-browser' -WorkingDirectory '%~dp0' -WindowStyle Hidden"
) else (
  powershell -NoProfile -Command "Start-Process -FilePath 'pythonw.exe' -ArgumentList 'server.py','--port','8765','--no-browser' -WorkingDirectory '%~dp0'"
)

REM ---------- 等待服务就绪（最多约 12 秒） ----------
set /a TRY=0
:WAIT
timeout /t 1 /nobreak >nul
set /a TRY+=1
set "CODE="
for /f %%i in ('curl.exe -s -o NUL -w "%%{http_code}" --max-time 2 %URL%api/langs 2^>nul') do set "CODE=%%i"
if "%CODE%"=="200" goto OPEN
if %TRY% lss 12 goto WAIT

echo.
echo   [提示] 服务启动较慢或失败，请稍后手动在浏览器打开 %URL%
timeout /t 3 /nobreak >nul
exit /b 1

:OPEN
start "" "%URL%"
echo.
echo   ? 启动完成：服务在后台运行，本窗口可以随时关闭，不影响使用。
echo   需要停止服务时，双击「停止代码转换器.bat」即可。
echo.
timeout /t 1 /nobreak >nul
exit /b 0
