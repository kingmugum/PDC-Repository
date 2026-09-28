@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo  ALIRA Native Vision Probe - Direct API Quick Test
echo ============================================================
echo.
echo This tool is detached from Requirement Studio main runtime.
echo It will:
echo   1. inspect ALIRA config/CLI help
echo   2. create a deterministic vision-only PNG fixture
echo   3. send the image directly to the configured ALIRA/Qwen API
echo.
echo If your internal API requires a key, set this first:
echo   set ALIRA_VISION_PROBE_API_KEY=YOUR_KEY
echo.
python alira_vision_probe.py --inspect --make-fixture --api-image
set RC=%ERRORLEVEL%
echo.
echo ============================================================
echo Exit code: %RC%
echo Review [DIRECT API RESPONSE] above.
echo PASS requires the image-only facts to be read correctly:
echo   R7K-42 / green / STATE_A to STATE_B / 3.7 s /
echo   star right of STATE_B / VISION_ONLY
echo ============================================================
pause
exit /b %RC%
