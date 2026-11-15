@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title Optimus Gang Bot Runner

echo ========================================================
echo        🔥 ИГРОВОЙ БОТ TELEGRAM: OPTIMUS GANG 🔥
echo ========================================================
echo.

cd /d "%~dp0"

:: Поиск рабочего интерпретатора Python
set PYTHON_EXE=

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    for /f "tokens=*" %%i in ('where python') do (
        "%%i" --version >nul 2>&1
        if !ERRORLEVEL! equ 0 (
            set PYTHON_EXE="%%i"
            goto :python_found
        )
    )
)

where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    py --version >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        set PYTHON_EXE=py
        goto :python_found
    )
)

for %%p in (
    "%LocalAppData%\Programs\Python\Python313\python.exe"
    "%LocalAppData%\Programs\Python\Python312\python.exe"
    "%LocalAppData%\Programs\Python\Python311\python.exe"
    "%LocalAppData%\Programs\Python\Python310\python.exe"
    "%ProgramFiles%\Python313\python.exe"
    "%ProgramFiles%\Python312\python.exe"
    "%ProgramFiles%\Python311\python.exe"
    "%ProgramFiles%\Python310\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "D:\Python312\python.exe"
    "D:\Python311\python.exe"
    "%ProgramFiles%\Image-Line\FL Studio 2025\Shared\Python\python.exe"
) do (
    if exist %%p (
        set PYTHON_EXE=%%p
        goto :python_found
    )
)

echo [ОШИБКА] Python 3 не найден в системе!
echo Пожалуйста, установите Python с официального сайта:
echo https://www.python.org/downloads/
echo Не забудьте поставить галочку "Add Python to PATH" при установке!
echo.
pause
exit /b 1

:python_found
echo [+] Найден Python: !PYTHON_EXE!
!PYTHON_EXE! --version

:: Проверка и создание виртуального окружения
if not exist ".venv" (
    echo [*] Создание виртуального окружения .venv...
    !PYTHON_EXE! -m venv .venv
)

if exist ".venv\Scripts\python.exe" (
    set VENV_PYTHON=".venv\Scripts\python.exe"
    set VENV_PIP=".venv\Scripts\pip.exe"
) else (
    set VENV_PYTHON=!PYTHON_EXE!
    set VENV_PIP=!PYTHON_EXE! -m pip
)

:: Установка зависимостей
echo [*] Проверка и установка зависимостей из requirements.txt...
!VENV_PIP! install -r requirements.txt --quiet --upgrade

:: Проверка наличия .env
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [!] Создан файл .env из шаблона.
    )
)

echo.
echo ========================================================
echo        🚀 ЗАПУСК БОТА OPTIMUS GANG...
echo ========================================================
echo.

!VENV_PYTHON! bot.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] Бот завершил работу с ошибкой (код %ERRORLEVEL%).
    pause
)
