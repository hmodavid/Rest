@echo off
REM Instalador do Rest (Windows): abre o installer.py com banner e barra de progresso.
REM Requer Python 3.9+. Opcoes: --skip-tests, --dry-run, --no-color
setlocal
cd /d "%~dp0"
where py >nul 2>nul && goto :use_py
where python >nul 2>nul && goto :use_python
echo.
echo   Python 3.9+ nao encontrado.
echo   Instale em https://www.python.org/downloads/ e marque "Add python.exe to PATH".
set "RC=1"
goto :end

:use_py
py -3 installer.py %*
set "RC=%errorlevel%"
goto :end

:use_python
python installer.py %*
set "RC=%errorlevel%"

:end
REM Se foi aberto com duplo clique, segura a janela para ler o resultado.
echo %cmdcmdline% | find /i "%~nx0" >nul && pause
exit /b %RC%
