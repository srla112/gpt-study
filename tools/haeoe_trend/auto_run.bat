@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
where py > nul 2>&1 && (py -3 haeoe_trend.py --no-open > last_run_log.txt 2>&1) || (python haeoe_trend.py --no-open > last_run_log.txt 2>&1)
