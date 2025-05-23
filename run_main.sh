#!/bin/bash

# Enhanced run script for the professional crypto analysis system
# Version: 2.1 - Environment-aware (supports both .env and system env vars)

# Set script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting Professional Crypto Analysis System..."

# Check for environment variables (both .env file and system env vars)
if [ -f ".env" ]; then
    log "✓ Found .env file - loading local development environment"
    source .env
else
    log "No .env file found - using system environment variables (cloud deployment mode)"
fi

# Verify critical environment variables are set (from either source)
if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
    log "ERROR: Missing critical environment variables!"
    log "TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:+SET}"
    log "TELEGRAM_CHAT_ID: ${TELEGRAM_CHAT_ID:+SET}"
    log ""
    log "For local development: Create .env file with your API keys"
    log "For cloud deployment: Set environment variables in your platform dashboard"
    exit 1
fi

log "✓ Environment variables configured"

# Check if Python is available
if ! command -v python &> /dev/null; then
    if ! command -v python3 &> /dev/null; then
        log "ERROR: Python not found!"
        exit 1
    else
        PYTHON_CMD="python3"
    fi
else
    PYTHON_CMD="python"
fi

# Check if required modules are installed
log "Checking dependencies..."
$PYTHON_CMD -c "
import sys
required_modules = ['pandas', 'requests', 'openai', 'yfinance', 'scikit-learn', 'beautifulsoup4', 'python-dotenv']
missing = []
for module in required_modules:
    try:
        __import__(module.replace('-', '_'))
    except ImportError:
        missing.append(module)
if missing:
    print('ERROR: Missing required modules:', ', '.join(missing))
    print('Please run: pip install -r requirements.txt')
    sys.exit(1)
print('All dependencies available')
"

if [ $? -ne 0 ]; then
    log "Dependency check failed!"
    exit 1
fi

# Check if models directory exists, create if not
if [ ! -d "models" ]; then
    log "Creating models directory..."
    mkdir models
fi

# Run the main script with proper error handling
log "Starting analysis..."
$PYTHON_CMD 6.py

# Check exit status
if [ $? -eq 0 ]; then
    log "Analysis completed successfully"
else
    log "ERROR: Analysis failed with exit code $?"
    exit 1
fi

log "Professional Crypto Analysis System completed"