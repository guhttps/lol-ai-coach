<#
.SYNOPSIS
    Gera o executável do LoL AI Coach e o pacote .zip para distribuição.

.DESCRIPTION
    Roda o PyInstaller com LoL_AI_Coach.spec, copia para dist/LoL_AI_Coach os
    arquivos que a pessoa precisa editar (.env.example e player_profile.json)
    e compacta tudo em dist/LoL_AI_Coach-<versão>-windows.zip.

.EXAMPLE
    python -m pip install -r requirements-dev.txt
    .\scripts\build.ps1
#>
param(
    [string]$Python = "python"
)

# Sem $ErrorActionPreference = "Stop": no Windows PowerShell 5.1 ele transforma
# o log do PyInstaller (stderr) em erro. Os comandos externos são checados
# pelo código de saída e os cmdlets usam -ErrorAction Stop.
Set-Location (Split-Path $PSScriptRoot -Parent)

$version = & $Python -c "from config import APP_VERSION; print(APP_VERSION)"
if ($LASTEXITCODE -ne 0) { throw "Não foi possível ler APP_VERSION em config.py." }

& $Python -m PyInstaller --noconfirm --clean LoL_AI_Coach.spec
if ($LASTEXITCODE -ne 0) { throw "O PyInstaller falhou." }

$bundle = "dist/LoL_AI_Coach"
Copy-Item .env.example, player_profile.json, LICENSE, scripts/LEIA-ME.txt -Destination $bundle -ErrorAction Stop

$zip = "dist/LoL_AI_Coach-$version-windows.zip"
if (Test-Path $zip) { Remove-Item $zip -ErrorAction Stop }
Compress-Archive -Path $bundle -DestinationPath $zip -ErrorAction Stop
Write-Output "Pacote gerado: $zip"
