#!/bin/bash
# 관련 영상 따라가기 → 새 채널 수집을 여러 번 반복한다 (새 채널이 거의 안 나올 때까지)
cd "$(dirname "$0")/.."
for r in 1 2 3 4; do
  echo "=== 라운드 $r ==="
  python3 tools/pipeline.py yadam crawl
  python3 tools/pipeline.py yadam collect
done
python3 tools/pipeline.py yadam analyze
echo ALLDONE
