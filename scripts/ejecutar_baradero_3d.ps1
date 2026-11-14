<#
Genera y verifica Baradero_3D.blend con Blender 4.2 en modo headless.
No abre la interfaz ni toca la sesion de Blender que el usuario tenga abierta.

Uso:
  powershell -ExecutionPolicy Bypass -File scripts\ejecutar_baradero_3d.ps1
  powershell -ExecutionPolicy Bypass -File scripts\ejecutar_baradero_3d.ps1 -Blender "C:\ruta\blender.exe"
  powershell -ExecutionPolicy Bypass -File scripts\ejecutar_baradero_3d.ps1 -SkipVerify
#>
[CmdletBinding()]
param(
    [string]$Blender = $env:BARA_BLENDER,
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
        (Join-Path $env:ProgramFiles 'Blender Foundation\Blender 4.2\blender.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Blender Foundation\Blender 4.2\blender.exe')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    $command = Get-Command blender -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    throw 'No se encontro Blender 4.2. Indique la ruta con -Blender "C:\...\blender.exe" o BARA_BLENDER.'
}

$exe = Find-Blender $Blender
$version = (& $exe --version | Select-Object -First 1)
Write-Host "Usando: $version"
if ($version -notmatch '^Blender 4\.2') {
    throw "Este pipeline requiere Blender 4.2. Version detectada: $version"
}

$logs = Join-Path $root 'mapa\logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null

function Invoke-Bara {
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
    Get-Content $console -Tail 20 -ErrorAction SilentlyContinue
    if (Test-Path $errors) {
        $stderrTail = Get-Content $errors -Tail 8 -ErrorAction SilentlyContinue
        if ($stderrTail) { Write-Host '--- stderr ---'; $stderrTail }
    }
    if ($code -ne 0) {
        throw "Blender termino con codigo $code. Consola: $console ; errores: $errors"
    }
}

$deps = Join-Path $root 'mapa\.deps\py311'
if (-not (Test-Path (Join-Path $deps 'shapely'))) {
    Write-Host 'Instalando Shapely aislado para el Python de Blender 4.2 ...'
    Invoke-Bara 'scripts\preparar_dependencias_mapa.py'
}

Invoke-Bara 'scripts\generar_baradero_3d.py'
if (-not $SkipVerify) {
    Invoke-Bara 'scripts\verificar_baradero_3d.py'
}

Write-Host ''
Write-Host 'Listo. Edificios marcados PROVISIONAL: no son edificios reales de Baradero.'
Write-Host '  Escena:      mapa\blender\Baradero_3D.blend'
Write-Host '  Informe:     docs\informe_baradero_3d.md'
Write-Host '  Verificacion:docs\verificacion_baradero_3d.md'
Write-Host '  Vistas:      docs\renders\baradero3d_*.png'
