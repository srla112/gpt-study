@echo off
chcp 65001 > nul
cd /d "%~dp0"
schtasks /create /f /sc daily /st 09:00 /tn "HaeoeTrend" /tr "\"%~dp0auto_run.bat\""
echo.
echo 매일 오전 9시에 자동으로 실행되도록 등록했습니다.
echo 시간을 바꾸려면 이 파일을 메모장으로 열어 09:00 을 원하는 시간으로 고친 뒤 다시 실행하세요.
echo 등록을 지우려면 매일자동실행_해제.bat 을 실행하세요.
pause
