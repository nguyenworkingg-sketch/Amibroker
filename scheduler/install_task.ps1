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

# Chay bu 15:15 (sau khi bo cap nhat trong phien DNSE dung luc 15:05): neu lich 18:00 hom truoc bi lo (may tat/ngu),
# chay lai cac phuong phap tinh theo phien cho phien EOD do. Ngay binh thuong: tu thoat ngay, khong dung AmiBroker.
$name2 = "AmiBroker VN - Exploration Hub (chay bu)"
$action2 = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$bat`" --catchup"
$trigger2 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At "15:15"
Register-ScheduledTask -TaskName $name2 -Action $action2 -Trigger $trigger2 -Settings $settings -Principal $principal -Force `
  -Description "Chay bu Exploration Hub cho phien EOD bi lo (lich 18:00 khong chay). Nhat ky: archive\logs" | Out-Null
Get-ScheduledTask -TaskName $name2 | Get-ScheduledTaskInfo | Select-Object TaskName, NextRunTime
