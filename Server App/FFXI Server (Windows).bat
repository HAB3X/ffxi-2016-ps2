@echo off
rem FFXI Server for Windows. Fan Project by Habex. Double-click to open the server window.
rem Needs Python 3 (free, from python.org). Keep this file inside the "Server App" folder.
rem Everything else the server needs (database and game server programs) comes in the release folder.
setlocal
set "PYAPP=%~dp0app\ffxi_server_app.py"
if not exist "%PYAPP%" (
  echo The app's files were not found. Keep this file inside the "Server App" folder.
  pause
  exit /b 1
)
call :findpy
if defined PYW goto :run
echo.
echo   FFXI Server needs Python 3 to open its window. Python is free (python.org).
echo.
where winget >nul 2>nul || goto :website
choice /C YN /M "  Install Python now? It takes a minute or two and needs no admin password"
if errorlevel 2 goto :website
winget install -e --id Python.Python.3.13 --scope user --accept-package-agreements --accept-source-agreements
call :findpy
if defined PYW goto :run
echo.
echo   Python was installed. Close this window and double-click "FFXI Server (Windows)" again.
pause
exit /b 0

:website
echo   Opening the Python download page. Download and run the installer, tick
echo   "Add python.exe to PATH" on its first page, then double-click "FFXI Server (Windows)" again.
start "" "https://www.python.org/downloads/windows/"
echo.
pause
exit /b 1

:run
start "" %PYW% "%PYAPP%"
exit /b 0

:findpy
set "PYW="
for %%v in (314 313 312 311 310) do if not defined PYW if exist "%LocalAppData%\Programs\Python\Python%%v\pythonw.exe" set PYW="%LocalAppData%\Programs\Python\Python%%v\pythonw.exe"
for %%v in (314 313 312 311 310) do if not defined PYW if exist "%ProgramFiles%\Python%%v\pythonw.exe" set PYW="%ProgramFiles%\Python%%v\pythonw.exe"
if not defined PYW where pyw >nul 2>nul && set "PYW=pyw -3"
if not defined PYW where pythonw >nul 2>nul && set "PYW=pythonw"
exit /b 0
