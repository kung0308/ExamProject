@echo off
chcp 65001 >nul
title 試題3 - 監控平台管理工具

echo ===================================================
echo.
echo           試題 3：監控平台 (PLG Stack) 管理工具
echo.
echo ===================================================
echo.
echo [1] 啟動監控平台 (在背景執行)
echo [2] 關閉監控平台 (釋放電腦資源)
echo [3] 離開
echo [4] 重設 Grafana 密碼 (忘記密碼/無法登入專用)
echo.

set /p choice="👉 請輸入您的選擇 (1、2、3 或 4): "

if "%choice%"=="1" goto start
if "%choice%"=="2" goto stop
if "%choice%"=="3" goto end
if "%choice%"=="4" goto reset_pwd

:start
echo.
echo ⏳ 正在啟動服務，請稍候...
cd /d "C:\ExamProject\試題 3"
docker compose up -d
echo.
echo ✅ 服務已成功在背景啟動！
echo 👉 Grafana 網址：http://localhost:3000
echo.
pause
goto end

:stop
echo.
echo ⏳ 正在關閉並移除服務，請稍候...
cd /d "C:\ExamProject\試題 3"
docker compose down
echo.
echo 🛑 服務已完全關閉！
echo.
pause
goto end

:reset_pwd
echo.
echo ⏳ 正在強制重設 Grafana 管理員密碼...
REM 【已修正】將 grafana-cli 改為新版 grafana cli 指令
docker exec -it grafana grafana cli admin reset-admin-password admin
echo.
echo ✅ 密碼已成功重設！
echo 👉 請使用帳號: admin / 密碼: admin 重新登入 http://localhost:3000
echo.
pause
goto end

:end
exit