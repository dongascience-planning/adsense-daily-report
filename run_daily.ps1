# Full pipeline (Windows). Task Scheduler runs this daily.
# Manual run:  powershell -ExecutionPolicy Bypass -File .\run_daily.ps1
#
# Note: step success is judged by the Python process exit code ($LASTEXITCODE),
# NOT by stderr text. Some Google libraries print harmless warnings to stderr
# (e.g. "Regional Access Boundary ...") even on a successful call.

$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$logDir = Join-Path $PSScriptRoot "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd"
$log = Join-Path $logDir "$stamp.log"

function Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg
    Write-Output $line
    Add-Content -Path $log -Value $line -Encoding UTF8
}

# venv python preferred, fallback to system python
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$py = if (Test-Path $venvPy) { $venvPy } else { "python" }

$steps = @(
    @{ n = "1/5 AdSense collect";    f = "collect_adsense.py" },
    @{ n = "2/5 GA4 collect";        f = "collect_ga4.py" },
    @{ n = "3/5 Analyze + insight";  f = "analyze.py" },
    @{ n = "4/5 Build dashboard";    f = "build_dashboard.py" },
    @{ n = "5/5 Jandi send";         f = "send_jandi.py" }
)

# 원페이지(광고수익_원페이지.html) 는 매일 아침 별도로 갱신한다.
# best-effort: 실패해도 위 핵심 파이프라인(수집→대시보드→Jandi)에는 영향 없음.
$onepager = "build_onepager.py"

Log "Pipeline start (python=$py)"
foreach ($s in $steps) {
    Log $s.n
    $out = & $py $s.f 2>&1
    foreach ($line in $out) {
        $text = [string]$line
        Write-Output $text
        Add-Content -Path $log -Value $text -Encoding UTF8
    }
    if ($LASTEXITCODE -ne 0) {
        Log "FAILED at $($s.f) (exit=$LASTEXITCODE)"
        exit 1
    }
}

# 원페이지 갱신 (best-effort — 실패해도 파이프라인 성공으로 둔다)
Log "extra: Build one-pager ($onepager)"
$out = & $py $onepager 2>&1
foreach ($line in $out) {
    $text = [string]$line
    Write-Output $text
    Add-Content -Path $log -Value $text -Encoding UTF8
}
if ($LASTEXITCODE -ne 0) { Log "WARN one-pager 갱신 실패 (exit=$LASTEXITCODE) — 무시하고 계속" }

Log "Done"
