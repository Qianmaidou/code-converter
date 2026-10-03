@echo off
title 停止代码转换器

echo 正在停止代码转换器后台服务…
echo.

powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*server.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Output ('已停止服务进程 PID ' + $_.ProcessId) }; if (-not (Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*server.py*' })) { Write-Output '没有发现正在运行的代码转换器服务。' }"

echo.
echo 完成。浏览器页面如还开着，关闭即可。
timeout /t 3 /nobreak >nul
