# Register a daily 09:00 task in Windows Task Scheduler.
# Run:     powershell -ExecutionPolicy Bypass -File .\register_schedule.ps1
# Remove:  Unregister-ScheduledTask -TaskName "AdSenseDailyReport" -Confirm:$false

$ErrorActionPreference = "Stop"
$taskName = "AdSenseDailyReport"
$script = Join-Path $PSScriptRoot "run_daily.ps1"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`"" `
    -WorkingDirectory $PSScriptRoot

$trigger = New-ScheduledTaskTrigger -Daily -At 9:00AM

# If the PC was off/asleep at 09:00, run the missed task once it is available.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Dongascience daily AdSense+GA4 report" -Force | Out-Null

Write-Output "[OK] Task Scheduler registered: '$taskName' daily at 09:00"
Write-Output "Test now with:  Start-ScheduledTask -TaskName $taskName"
