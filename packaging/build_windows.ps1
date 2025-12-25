$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  pip install pyinstaller
}

$distDir = Join-Path $root "dist"
if (Test-Path $distDir) {
  Remove-Item -Recurse -Force $distDir
}

pyinstaller apps/windows/main.py `
  --paths . `
  --name GrapplingOverlay `
  --onedir `
  --noconsole `
  --add-data "packaging/resources;resources" `
  --clean

$exeDir = Join-Path $distDir "GrapplingOverlay"
$resourceDllDir = Join-Path $exeDir "resources\dlls"
New-Item -ItemType Directory -Path $resourceDllDir -Force | Out-Null

$dlls = @("vcruntime140.dll", "vcruntime140_1.dll")
foreach ($dll in $dlls) {
  $systemPath = Join-Path $env:WINDIR "System32\$dll"
  if (Test-Path $systemPath) {
    Copy-Item $systemPath $exeDir -Force
    Copy-Item $systemPath $resourceDllDir -Force
  }
}

Write-Host "Build complete: $exeDir"
