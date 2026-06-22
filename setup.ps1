# 가상환경 생성 + 의존성 설치 (Windows). 최초 1회 실행.
# 실행:  powershell -ExecutionPolicy Bypass -File .\setup.ps1

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Output "1) 가상환경(.venv) 생성"
python -m venv .venv

Write-Output "2) pip 업그레이드 + 의존성 설치"
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Output ""
Write-Output "[완료] 다음 순서로 진행하세요:"
Write-Output "  1. .env 파일에 자격증명 입력 (.env.example 참고)"
Write-Output "  2. GA4 서비스계정 JSON 키를 이 폴더에 ga4-key.json 으로 저장"
Write-Output "  3. python auth_adsense.py   (AdSense OAuth 최초 1회 브라우저 인증)"
Write-Output "  4. powershell -ExecutionPolicy Bypass -File .\run_daily.ps1   (1회 테스트)"
Write-Output "  5. powershell -ExecutionPolicy Bypass -File .\register_schedule.ps1   (매일 09:00 등록)"
