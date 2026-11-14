@echo off
setlocal
cd /d "%~dp0"

rem Usa Node instalado; en esta computadora también admite la copia portátil.
where node.exe >nul 2>nul
if errorlevel 1 (
  if exist "%LOCALAPPDATA%\Temp\opencode\node-v24.22.3-win-x64\node.exe" (
    set "PATH=%LOCALAPPDATA%\Temp\opencode\node-v24.22.3-win-x64;%PATH%"
  ) else (
    echo BARA-DRIVE necesita Node.js 24 LTS para ejecutar este prototipo.
    echo Instalalo desde https://nodejs.org y volve a abrir este archivo.
    pause
    exit /b 1
  )
)

if not exist "node_modules\vite\package.json" (
  call npm.cmd ci --no-fund --no-audit
  if errorlevel 1 (
    echo No se pudieron instalar las dependencias. Revisa la conexion y Node.js.
    pause
    exit /b 1
  )
)

echo BARA-DRIVE - Abriendo http://127.0.0.1:5173
echo Deja esta ventana abierta mientras jugas. Ctrl+C para detener.
call npm.cmd run dev -- --open
if errorlevel 1 pause
