@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
where py > nul 2>&1 && (py -3 haeoe_trend.py) || (python haeoe_trend.py)
echo.
echo 끝났습니다. 결과.html 이 열렸는지 확인하세요.
pause
