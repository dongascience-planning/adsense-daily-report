#!/usr/bin/env bash
# 전체 파이프라인 (macOS/Linux). cron 이 매일 이 스크립트를 실행한다.
# 수동 실행:  bash run_daily.sh
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p data/logs
LOG="data/logs/$(date +%Y-%m-%d).log"

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

if [ -x ".venv/bin/python" ]; then PY=".venv/bin/python"; else PY="python3"; fi

log "파이프라인 시작 (python=$PY)"
log "1/5 AdSense 수집";   "$PY" collect_adsense.py 2>&1 | tee -a "$LOG"
log "2/5 GA4 수집";       "$PY" collect_ga4.py     2>&1 | tee -a "$LOG"
log "3/5 분석 + 인사이트"; "$PY" analyze.py         2>&1 | tee -a "$LOG"
log "4/5 대시보드 생성";   "$PY" build_dashboard.py 2>&1 | tee -a "$LOG"
log "5/5 Jandi 전송";     "$PY" send_jandi.py      2>&1 | tee -a "$LOG"
log "완료"
