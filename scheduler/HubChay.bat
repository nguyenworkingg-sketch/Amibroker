@echo off
rem AmiBroker Exploration Hub - chay Exploration, chuan hoa, day du lieu len GitHub.
rem Dung boi Task Scheduler (08:30 thu 2-6) va boi D:\AmiBroker_VN\TuDong_CapNhat.bat (sau khi chot so lieu 18:00).
rem Nhat ky chi tiet: <repo>\archive\logs\hub_<ngay>.log
cd /d "%~dp0.."
python -I exporter\run_explorations.py --publish --wait-minutes 30 %*
exit /b %errorlevel%
