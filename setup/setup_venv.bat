@echo off
setlocal

rem Set project root to the parent directory of this script
cd /d "%~dp0\.."

echo === Creating venv ===
python -m venv .venv
if errorlevel 1 (
    echo Error: Failed to create venv. Make sure Python is installed.
    exit /b 1
)

echo === Upgrading pip ===
.venv\Scripts\python.exe -m pip install --upgrade pip

echo === Installing pytest ===
.venv\Scripts\pip.exe install pytest
if errorlevel 1 (
    echo Error: Failed to install pytest.
    exit /b 1
)

echo === Installing run_workflow dependencies ===
.venv\Scripts\pip.exe install -r run_workflow\requirements.txt
if errorlevel 1 (
    echo Error: Failed to install run_workflow dependencies.
    exit /b 1
)

echo === Installing generate_image_bot dependencies ===
.venv\Scripts\pip.exe install -r generate_image_bot\requirements.txt
if errorlevel 1 (
    echo Error: Failed to install generate_image_bot dependencies.
    exit /b 1
)

echo.
echo === Setup complete ===
echo To activate the virtual environment, run:
echo   .venv\Scripts\activate
