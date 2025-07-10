#!/bin/bash

echo "🧠 CRYPTO AI PREDICTION SYSTEM - REASONING MODE TEST"
echo "=================================================="

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed or not in PATH"
    exit 1
fi

echo "✅ Python3 found"

# Check if required files exist
if [ ! -f "6.py" ]; then
    echo "❌ Main script (6.py) not found"
    exit 1
fi

if [ ! -f "ai_predictor.py" ]; then
    echo "❌ AI predictor (ai_predictor.py) not found"
    exit 1
fi

echo "✅ Required files found"

# Test different modes
echo ""
echo "🧪 TESTING DIFFERENT MODES:"
echo ""

echo "1️⃣  Testing reasoning mode (--reasoning):"
echo "   This should show AI thought process and use test environment"
python3 6.py --reasoning
echo ""

echo "2️⃣  Testing regular test mode (--test):"
echo "   This should use test environment without reasoning"
python3 6.py --test
echo ""

echo "3️⃣  Testing production mode (no flags):"
echo "   This should use production environment"
python3 6.py
echo ""

echo "4️⃣  Testing reasoning mode with test flag (--reasoning --test):"
echo "   This should be same as --reasoning (reasoning mode always uses test env)"
python3 6.py --reasoning --test
echo ""

echo "🧠 REASONING MODE TESTING COMPLETE"
echo "=================================="
echo ""
echo "Expected behavior:"
echo "• --reasoning: Shows AI thought process, uses test bot/chat"
echo "• --test: Normal test mode, uses test bot/chat"
echo "• No flags: Production mode, uses production bot/chat"
echo "• --reasoning --test: Same as --reasoning" 