# 로그인 시 대시보드 서버가 자동으로 켜지도록 작업 스케줄러에 등록.
# 실행:  powershell -ExecutionPolicy Bypass -File .\register_server.ps1
# 삭제:  Unregister-ScheduledTask -TaskName "AdSenseReportServer" -Confirm:$false

$ErrorActionPreference = "Stop"
$taskName = "AdSenseReportServer"
$pyw = Join-Path $PSScriptRoot ".venv\Scripts\pythonw.exe"
$serve = Join-Path $PSScriptRoot "serve.py"

$action = New-ScheduledTaskAction -Execute $pyw -Argument "`"$serve`"" -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn
# 서버는 계속 떠 있어야 하므로 실행시간 제한 없음 + 재시작 옵션
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "동아사이언스닷컴 광고 대시보드 사내망 서버" -Force | Out-Null

Write-Output "[OK] 로그인 시 자동 시작 등록: '$taskName'"
Write-Output "지금 바로 시작:  Start-ScheduledTask -TaskName $taskName"
