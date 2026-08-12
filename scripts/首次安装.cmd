@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."

where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 Python。请先安装 Python 3.12，然后重新运行本脚本。
  pause
  exit /b 1
)

if not exist "backend\.runtime\Scripts\python.exe" (
  echo 正在创建项目专用 Python 环境...
  python -m venv "backend\.runtime"
  if errorlevel 1 goto :failed
)

echo 正在安装或更新项目依赖...
"backend\.runtime\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
"backend\.runtime\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 goto :failed

echo 正在检查系统...
pushd "backend"
".runtime\Scripts\python.exe" -m pytest -q
if errorlevel 1 (
  popd
  goto :failed
)
popd

echo.
echo 安装完成。现在可以运行 scripts\创建桌面快捷方式.ps1。
pause
exit /b 0

:failed
echo.
echo [错误] 安装没有完成，请保留本窗口中的错误信息。
pause
exit /b 1
