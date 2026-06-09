@echo off
REM Amazon Video Intelligence Pipeline — Windows Quick Runner
REM Usage: Drag and drop this file to cmd, or double-click and follow prompts

set /p URL="Paste Amazon video URL: "
set /p APIKEY="Paste Anthropic API key: "

echo.
echo [1/4] Downloading video...
python layer1_download.py "%URL%"

REM Extract video ID from downloads folder (most recent)
for /f "delims=" %%i in ('dir /b /ad /od downloads') do set VID=%%i

echo.
echo [2/4] Transcribing audio...
python layer2_transcribe.py %VID%

echo.
echo [3/4] Analyzing with Claude...
python layer3_analyze.py %VID% --api-key %APIKEY%

echo.
echo [4/4] Exporting to Excel...
python layer4_export.py %VID%

echo.
echo ============================================
echo  DONE! Open your Excel report:
echo  downloads\%VID%\
echo ============================================
pause
