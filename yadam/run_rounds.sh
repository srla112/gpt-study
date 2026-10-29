#!/bin/bash
# 관련 영상 따라가기 → 새 채널 수집을 반복한다. 새로 찾는 채널이 없으면 멈춘다.
cd "$(dirname "$0")/.."
for r in 1 2 3 4 5 6 7 8; do
  echo "=== 라운드 $r ==="
  before=$(ls yadam/raw/[0-9]*.json | wc -l)
  python3 tools/pipeline.py yadam crawl
  python3 tools/pipeline.py yadam collect
  after=$(ls yadam/raw/[0-9]*.json | wc -l)
  echo "채널 수: $before -> $after"
  [ "$after" -eq "$before" ] && break
done
python3 tools/pipeline.py yadam analyze
echo ALLDONE
