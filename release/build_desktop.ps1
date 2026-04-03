param(
    [string]$PythonExe = "python",
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$version = (Get-Content (Join-Path $root 'VERSION') -Encoding UTF8 | Select-Object -First 1).Trim()
$distDir = Join-Path $root 'dist'
$buildDir = Join-Path $root 'build'
$iconPath = Join-Path $root 'release\app.ico'
$mainFile = Join-Path $root 'analytics_app_fixed.py'

if (Test-Path $distDir) { Remove-Item -LiteralPath $distDir -Recurse -Force }
if (Test-Path $buildDir) { Remove-Item -LiteralPath $buildDir -Recurse -Force }

$pyiArgs = @(
  '-m', 'PyInstaller',
  '--noconfirm', '--clean', '--windowed', '--onefile',
  '--name', 'ROMILab',
  '--add-data', "VERSION;.",
  '--add-data', "release_config.json;.",
  '--add-data', "app_release.py;."
)
if (Test-Path $iconPath) {
  $pyiArgs += @('--icon', $iconPath)
}
$pyiArgs += $mainFile

& $PythonExe @pyiArgs

if (-not $SkipInstaller) {
  $iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
  $isccPath = if ($iscc) { $iscc.Source } else { $null }

  if (-not $isccPath) {
    $uninstallKeys = @(
      'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
      'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
      'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )
    $innoInstall = Get-ItemProperty $uninstallKeys -ErrorAction SilentlyContinue |
      Where-Object { $_.DisplayName -like '*Inno Setup*' -and $_.InstallLocation } |
      Select-Object -First 1
    if ($innoInstall) {
      $candidate = Join-Path $innoInstall.InstallLocation 'ISCC.exe'
      if (Test-Path $candidate) {
        $isccPath = $candidate
      }
    }
  }

  if ($isccPath) {
    & $isccPath (Join-Path $root 'release\desktop_installer.iss') "/DAppVersion=$version"
  }
  else {
    Write-Warning 'ISCC.exe not found. Installer step skipped.'
  }
}


