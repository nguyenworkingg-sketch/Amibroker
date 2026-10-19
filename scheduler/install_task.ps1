# Tao lich Windows Task Scheduler cho AmiBroker Exploration Hub (chay bang PowerShell cua nguoi dung, khong can quyen admin).
#   powershell -ExecutionPolicy Bypass -File scheduler\install_task.ps1 [-Time 08:30]
param([string]$Time = "08:30")
$bat = Join-Path $PSScriptRoot "HubChay.bat"
$name = "AmiBroker VN - Exploration Hub"
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$bat`""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force `
  -Description "Chay Exploration AmiBroker (Hub_*.afl), chuan hoa JSON, day len GitHub Pages. Nhat ky: archive\logs" | Out-Null
Get-ScheduledTask -TaskName $name | Get-ScheduledTaskInfo | Select-Object TaskName, NextRunTime
