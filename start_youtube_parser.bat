```bat
@echo off
ECHO Запуск YouTube Channel Parser...

:: Проверка наличия Python
where python >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO Ошибка: Python не установлен. Пожалуйста, установите Python 3.10 с https://www.python.org/downloads/release/python-31010/ и выберите "Add Python to PATH".
    pause
    exit /b 1
)

:: Проверка версии Python
python --version 2>&1 | findstr /R "3\.[8-10]" >nul
IF %ERRORLEVEL% NEQ 0 (
    ECHO Предупреждение: Рекомендуется Python 3.8-3.10. Текущая версия может быть несовместима.
    ECHO Установите Python 3.10 с https://www.python.org/downloads/release/python-31010/ для лучшей совместимости.
    pause
)

:: Создание виртуального окружения, если его нет
IF NOT EXIST venv (
    ECHO Создание виртуального окружения...
    python -m venv venv
    IF %ERRORLEVEL% NEQ 0 (
        ECHO Ошибка при создании виртуального окружения.
        pause
        exit /b 1
    )
)

:: Активация виртуального окружения
CALL venv\Scripts\activate.bat
IF %ERRORLEVEL% NEQ 0 (
    ECHO Ошибка при активации виртуального окружения.
    pause
    exit /b 1
)

:: Установка зависимостей
ECHO Установка зависимостей...
pip install streamlit==1.28.0 google-api-python-client pandas
IF %ERRORLEVEL% NEQ 0 (
    ECHO Ошибка при установке зависимостей. Проверьте интернет-соединение и повторите.
    pause
    exit /b 1
)

:: Проверка наличия pythonParse.py
IF NOT EXIST pythonParse.py (
    ECHO Ошибка: Файл pythonParse.py не найден в текущей папке.
    pause
    exit /b 1
)

:: Запуск приложения
ECHO Запуск приложения...
streamlit run pythonParse.py
IF %ERRORLEVEL% NEQ 0 (
    ECHO Ошибка при запуске приложения. Проверьте файл pythonParse.py и зависимости.
    pause
    exit /b 1
)

pause
```