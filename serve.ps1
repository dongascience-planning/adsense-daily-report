# 대시보드 사내망 웹서버 실행 (콘솔창 없이 백그라운드).
# 수동 실행:  powershell -ExecutionPolicy Bypass -File .\serve.ps1
# 자동 시작은 register_server.ps1 로 로그인 시 자동 실행 등록.
Set-Location -Path $PSScriptRoot
$pyw = Join-Path $PSScriptRoot ".venv\Scripts\pythonw.exe"
$py = if (Test-Path $pyw) { $pyw } else { "pythonw" }
& $py (Join-Path $PSScriptRoot "serve.py")
