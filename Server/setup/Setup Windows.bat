@echo off
rem FFXI 2016 Server: one time setup for Windows (Fan Project by Habex).
rem Usually only installs Python: the release comes with the database and the game server programs.
rem If those are missing it installs the database program (MariaDB) and the build tools with winget (part of
rem Windows 10 and 11) and builds the game servers (30-90 minutes).
setlocal
cd /d "%~dp0.."
set "SERVER=%CD%"
echo.
echo   FFXI 2016 Server setup for Windows
echo   Fan Project by Habex
echo   ------------------------------------
echo.
rem Usually only Python is needed: the release comes with the database and the game server programs for Windows.
if exist "%SERVER%\programs\windows\xi_map.exe" if exist "%SERVER%\programs\windows\mariadb\bin\mariadbd.exe" goto :included
echo The included server programs are missing, so this setup installs the tools and builds them (30-90 minutes).
echo.
where winget >nul 2>nul || (
  echo winget is missing. Install "App Installer" from the Microsoft Store, then run this setup again.
  pause & exit /b 1
)
set "WG=winget install -e --accept-package-agreements --accept-source-agreements --silent"
where py >nul 2>nul || %WG% --id Python.Python.3.13
call :have_mariadb || %WG% --id MariaDB.Server
where git >nul 2>nul || %WG% --id Git.Git
where cmake >nul 2>nul || %WG% --id Kitware.CMake
rem the C++ compiler (Visual Studio Build Tools with the "Desktop development with C++" part)
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
set "HAVEVS="
if exist "%VSWHERE%" for /f "usebackq delims=" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "HAVEVS=%%i"
if not defined HAVEVS (
  %WG% --id Microsoft.VisualStudio.BuildTools --override "--wait --quiet --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended" ^
   || %WG% --id Microsoft.VisualStudio.2022.BuildTools --override "--wait --quiet --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
)
rem new programs are on PATH only in a new window: look for Python directly
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "PY=%LocalAppData%\Programs\Python\Python313\python.exe"
if not defined PY (
  echo Python was installed. Close this window and run "Setup Windows" again to continue.
  pause & exit /b 1
)
echo.
echo Building the game server programs (this can take 20-60 minutes)...
cd /d "%SERVER%\lsb"
%PY% -m venv .build-venv || goto :buildfail
".build-venv\Scripts\python.exe" -m pip install --quiet jinja2 jsonschema ruamel.yaml || goto :buildfail
set "VIRTUAL_ENV=%SERVER%\lsb\.build-venv"
set "PATH=%SERVER%\lsb\.build-venv\Scripts;%PATH%"
python tools\build.py || goto :buildfail
for %%p in (xi_connect xi_search xi_world xi_map) do if not exist "%SERVER%\lsb\%%p.exe" goto :buildfail
echo.
cd /d "%SERVER%"
%PY% server_control.py check
echo.
echo Windows will ask once whether these programs may use the network: click "Allow".
echo Setup is finished. Go back to the FFXI Server window and click "Check again".
pause
exit /b 0
:buildfail
echo.
echo The build did not finish. See the messages above. Most often the C++ tools are missing:
echo install "Visual Studio Build Tools" with "Desktop development with C++" and run this setup again.
pause
exit /b 1
:included
echo This computer uses the database and game server programs that come with the release.
set "PY="
where py >nul 2>nul && set "PY=py -3"
for %%v in (314 313 312 311 310) do if not defined PY if exist "%LocalAppData%\Programs\Python\Python%%v\python.exe" set PY="%LocalAppData%\Programs\Python\Python%%v\python.exe"
if not defined PY (
  where winget >nul 2>nul || goto :pysite
  echo Installing Python (for the server window^)...
  winget install -e --id Python.Python.3.13 --scope user --accept-package-agreements --accept-source-agreements || goto :pysite
  for %%v in (313) do if exist "%LocalAppData%\Programs\Python\Python%%v\python.exe" set PY="%LocalAppData%\Programs\Python\Python%%v\python.exe"
)
if not defined PY goto :pysite
echo.
%PY% "%SERVER%\server_control.py" check
echo.
echo Windows will ask once whether the server programs may use the network: click "Allow".
echo Setup is finished. Open "FFXI Server (Windows)" (or click "Check again" in it).
pause
exit /b 0
:pysite
echo.
echo Python is needed for the server window. Opening the download page: run the installer and tick
echo "Add python.exe to PATH" on its first page, then open "FFXI Server (Windows)" again.
start "" "https://www.python.org/downloads/windows/"
pause
exit /b 1
:have_mariadb
for /d %%d in ("%ProgramFiles%\MariaDB*") do if exist "%%d\bin\mariadbd.exe" exit /b 0
exit /b 1
