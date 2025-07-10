@echo off
echo 🧠 CRYPTO AI PREDICTION SYSTEM - REASONING MODE TEST
echo ==================================================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH
    pause
    exit /b 1
)

echo ✅ Python found

REM Check if required files exist
if not exist "6.py" (
    echo ❌ Main script (6.py) not found
    pause
    exit /b 1
)

if not exist "ai_predictor.py" (
    echo ❌ AI predictor (ai_predictor.py) not found
    pause
    exit /b 1
)

echo ✅ Required files found

echo.
echo 🧪 TESTING DIFFERENT MODES:
echo.

echo 1️⃣  Testing reasoning mode (--reasoning):
echo    This should show AI thought process and use test environment
python 6.py --reasoning
echo.

echo 2️⃣  Testing regular test mode (--test):
echo    This should use test environment without reasoning
python 6.py --test
echo.

echo 3️⃣  Testing production mode (no flags):
echo    This should use production environment
python 6.py
echo.

echo 4️⃣  Testing reasoning mode with test flag (--reasoning --test):
echo    This should be same as --reasoning (reasoning mode always uses test env)
python 6.py --reasoning --test
echo.

echo 🧠 REASONING MODE TESTING COMPLETE
echo ==================================
echo.
echo Expected behavior:
echo • --reasoning: Shows AI thought process, uses test bot/chat
echo • --test: Normal test mode, uses test bot/chat
echo • No flags: Production mode, uses production bot/chat
echo • --reasoning --test: Same as --reasoning
echo.
pause 