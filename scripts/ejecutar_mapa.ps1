<#
Ejecuta la Fase 1 + Fase 2 del mapa de Baradero con Blender 5.2 en modo headless.
No abre la interfaz ni modifica la sesion de Blender que el usuario tenga abierta.

Uso:
  powershell -ExecutionPolicy Bypass -File scripts\ejecutar_mapa.ps1
  powershell -ExecutionPolicy Bypass -File scripts\ejecutar_mapa.ps1 -Blender "C:\ruta\blender.exe"
  powershell -ExecutionPolicy Bypass -File scripts\ejecutar_mapa.ps1 -InspectOnly
  powershell -ExecutionPolicy Bypass -File scripts\ejecutar_mapa.ps1 -SkipVerify
#>
[CmdletBinding()]
param(
    [string]$Blender = $env:BARA_BLENDER,
    [switch]$InspectOnly,
    [switch]$SkipVerify
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Find-Blender {
    param([string]$Explicit)
    if ($Explicit) {
        if (Test-Path $Explicit) { return (Resolve-Path $Explicit).Path }
        throw "No existe el ejecutable indicado en -Blender: $Explicit"
    }
    $candidates = @(
        (Join-Path $env:ProgramFiles 'Blender Foundation\Blender 5.2\blender.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Blender Foundation\Blender 5.2\blender.exe'),
        (Join-Path $env:ProgramFiles 'Blender Foundation\Blender 5.1\blender.exe'),
        'C:\Users\a22ma\AppData\Local\Temp\opencode\blender-5.2.4-windows-x64\blender.exe'
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    $command = Get-Command blender -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    throw 'No se encontro Blender 5.2. Indique la ruta con -Blender "C:\...\blender.exe" o la variable BARA_BLENDER.'
}

$exe = Find-Blender $Blender
$version = (& $exe --version | Select-Object -First 1)
Write-Host "Usando: $version"
Write-Host "Ejecutable: $exe"
if ($version -notmatch '^Blender 5\.2') {
    throw "Este pipeline fue probado con Blender 5.2. Version detectada: $version"
}

$logs = Join-Path $root 'mapa\logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null

function Invoke-BaraBlender {
    param(
        [Parameter(Mandatory = $true)][string]$Script,
        [string[]]$Extra = @()
    )
    $arguments = @('--background', '--factory-startup', '--python', $Script, '--') + $Extra
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $name = [IO.Path]::GetFileNameWithoutExtension($Script)
    $console = Join-Path $logs ("{0}_{1}.console.log" -f $stamp, $name)
    $errors = Join-Path $logs ("{0}_{1}.stderr.log" -f $stamp, $name)
    Write-Host "Ejecutando $Script ..."
    $process = Start-Process -FilePath $exe -ArgumentList $arguments -WindowStyle Hidden `
        -Wait -PassThru -RedirectStandardOutput $console -RedirectStandardError $errors
    $code = $process.ExitCode
    Get-Content $console -Tail 25 -ErrorAction SilentlyContinue
    if (Test-Path $errors) {
        $stderrTail = Get-Content $errors -Tail 10 -ErrorAction SilentlyContinue
        if ($stderrTail) { Write-Host '--- stderr ---'; $stderrTail }
    }
    if ($code -ne 0) {
        throw "Blender termino con codigo $code. Consola: $console ; errores: $errors"
    }
}

$dependencyWheel = Get-ChildItem (Join-Path $root 'mapa\.deps') -Recurse -Filter 'shapely*' -ErrorAction SilentlyContinue |
    Select-Object -First 1
if (-not $dependencyWheel) {
    Write-Host 'Instalando Shapely aislado para el Python de este Blender ...'
    Invoke-BaraBlender 'scripts\preparar_dependencias_mapa.py'
}

$extra = @()
if ($InspectOnly) { $extra += '--inspect-only' }
Invoke-BaraBlender 'scripts\generar_mapa_baradero.py' -Extra $extra

if (-not $InspectOnly -and -not $SkipVerify) {
    Invoke-BaraBlender 'scripts\verificar_mapa.py'
}

Write-Host ''
Write-Host 'Listo.'
Write-Host '  Mapa:        mapa\blender\Baradero_mapa_3d.blend'
Write-Host '  Diagnostico: docs\diagnostico_mapa.json'
Write-Host '  Calles:      docs\informe_calles.json'
Write-Host '  Verificacion:docs\verificacion_calles.json'
Write-Host '  Vistas:      docs\renders\'
Write-Host '  Logs:        mapa\logs\'
