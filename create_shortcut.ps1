$ErrorActionPreference = "Stop"

$appDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $appDir) {
    $appDir = (Get-Location).Path
}

$startBat = Join-Path $appDir "START.bat"
$iconFile = Join-Path $appDir "app_icon.ico"
$appName = "Zero Garage Command Center"
$appDesc = "Zero Garage - Automotive Workshop Command Center"

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "         ZERO GARAGE - AUTOMOTIVE WORKSHOP COMMAND CENTER" -ForegroundColor Cyan
Write-Host "                     Shortcut Creator v2.0" -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $startBat)) {
    Write-Host "[ERROR] Could not find START.bat in $appDir" -ForegroundColor Red
    Write-Host "Please make sure this script is located in the project folder." -ForegroundColor Yellow
    exit 1
}

$wshShell = New-Object -ComObject WScript.Shell

# 1. Desktop Shortcut
try {
    $desktopPath = [Environment]::GetFolderPath([Environment+SpecialFolder]::Desktop)
    $shortcutPath = Join-Path $desktopPath "$appName.lnk"
    
    $shortcut = $wshShell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $startBat
    $shortcut.WorkingDirectory = $appDir
    if (Test-Path $iconFile) {
        $shortcut.IconLocation = "$iconFile,0"
    }
    $shortcut.Description = $appDesc
    $shortcut.WindowStyle = 1
    $shortcut.Save()
    
    Write-Host "[OK] Desktop shortcut created:" -ForegroundColor Green
    Write-Host "     $shortcutPath" -ForegroundColor Gray
} catch {
    Write-Host "[WARN] Failed to create Desktop shortcut: $_" -ForegroundColor Yellow
}

# 2. Start Menu Shortcut
try {
    $startMenuPath = [Environment]::GetFolderPath([Environment+SpecialFolder]::Programs)
    $smShortcutPath = Join-Path $startMenuPath "$appName.lnk"
    
    $smShortcut = $wshShell.CreateShortcut($smShortcutPath)
    $smShortcut.TargetPath = $startBat
    $smShortcut.WorkingDirectory = $appDir
    if (Test-Path $iconFile) {
        $smShortcut.IconLocation = "$iconFile,0"
    }
    $smShortcut.Description = $appDesc
    $smShortcut.WindowStyle = 1
    $smShortcut.Save()
    
    Write-Host "[OK] Start Menu shortcut created:" -ForegroundColor Green
    Write-Host "     $smShortcutPath" -ForegroundColor Gray
} catch {
    Write-Host "[WARN] Failed to create Start Menu shortcut: $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host " Shortcuts created successfully! You can now launch Zero Garage from:" -ForegroundColor Green
Write-Host " 1. Desktop icon" -ForegroundColor White
Write-Host " 2. Windows Start Menu search" -ForegroundColor White
Write-Host "==============================================================================" -ForegroundColor Cyan
