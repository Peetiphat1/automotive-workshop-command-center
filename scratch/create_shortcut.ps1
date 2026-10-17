$wshShell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop "Zero Garage Command Center.lnk"

$shortcut = $wshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "C:\Users\Admin\Downloads\automotive-workshop-command-center(1)\START.bat"
$shortcut.WorkingDirectory = "C:\Users\Admin\Downloads\automotive-workshop-command-center(1)"
$shortcut.IconLocation = "C:\Users\Admin\Downloads\automotive-workshop-command-center(1)\app_icon.ico,0"
$shortcut.Description = "Zero Garage - Automotive Workshop Command Center"
$shortcut.Save()

Write-Host "Desktop shortcut created successfully at: $shortcutPath"
