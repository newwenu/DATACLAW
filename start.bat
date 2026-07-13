@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM 切换到脚本所在目录
cd /d "%~dp0"

REM 优先使用项目虚拟环境 Python（快速路径）
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe start.py %*
    exit /b %errorlevel%
)

REM 回退到便携 Python
if exist ".python\python.exe" (
    .python\python.exe start.py %*
    exit /b %errorlevel%
)

REM 回退到系统 Python
where python >nul 2>&1
if %errorlevel%==0 (
    python start.py %*
    exit /b %errorlevel%
)

where python3 >nul 2>&1
if %errorlevel%==0 (
    python3 start.py %*
    exit /b %errorlevel%
)

REM 未找到任何 Python，提示下载便携版
echo [!] 未找到 Python。
echo.
echo 请选择：
echo   [1] 自动下载 Python 3.10 便携版到 .python/（推荐）
echo   [2] 手动安装 Python 3.10+ 后重试
echo.

set /p choice="请选择 (1/2): "

if "%choice%"=="1" goto :download_portable
goto :manual_hint

:download_portable
set PYTHON_VERSION=3.10.11
set PYTHON_ZIP=python-%PYTHON_VERSION%-embed-amd64.zip
set PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/%PYTHON_ZIP%
set PYTHON_DIR=.python

echo.
echo [*] 正在下载 Python %PYTHON_VERSION% 便携版 ...
echo     %PYTHON_URL%

REM 使用 PowerShell 下载
powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_ZIP%'" 2>nul
if not exist "%PYTHON_ZIP%" (
    echo [!] 下载失败，请检查网络连接。
    goto :manual_hint
)

echo [*] 正在解压到 %PYTHON_DIR%/ ...
if exist "%PYTHON_DIR%" rmdir /s /q "%PYTHON_DIR%"
mkdir "%PYTHON_DIR%"
powershell -Command "Expand-Archive -Path '%PYTHON_ZIP%' -DestinationPath '%PYTHON_DIR%' -Force"
del "%PYTHON_ZIP%"

REM 启用 site-packages（修改 _pth 文件）
for %%f in ("%PYTHON_DIR%\*._pth") do (
    echo [*] 配置 %%~nxf ...
    powershell -Command "(Get-Content '%%f') -replace '#import site', 'import site' | Set-Content '%%f'"
)

REM 安装 pip
echo [*] 正在安装 pip ...
powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'get-pip.py'"
.python\python.exe get-pip.py 2>nul
del get-pip.py 2>nul

if not exist ".python\Scripts\pip.exe" (
    echo [!] pip 安装失败，你可以稍后手动运行：
    echo     .python\python.exe -m ensurepip --upgrade
)

echo.
echo [+] Python %PYTHON_VERSION% 便携版安装完成。
echo [*] 正在启动 DataClaw ...
echo.

.python\python.exe start.py %*
exit /b %errorlevel%

:manual_hint
echo.
echo 请手动安装 Python 3.10+ 后重新运行本脚本。
echo     下载地址: https://www.python.org/downloads/
exit /b 1