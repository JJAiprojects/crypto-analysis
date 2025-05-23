#!/bin/bash

# Enhanced validation script for the professional crypto analysis system
# Runs hourly to validate predictions and train ML models

# Set script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [VALIDATION] $1"
}

log "Starting Professional Crypto Validation System..."

# Check if .env file exists
if [ ! -f ".env" ]; then
    log "ERROR: .env file not found!"
    log "Please create .env file with your API keys and bot tokens"
    exit 1
fi

# Source environment variables
source .env

# Verify critical environment variables
if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
    log "ERROR: Missing critical environment variables!"
    log "Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env"
    exit 1
fi

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
required_modules = ['pandas', 'requests', 'scikit-learn', 'beautifulsoup4', 'python-dotenv']
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
print('All validation dependencies available')
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

# Run the validation script with proper error handling
log "Starting prediction validation..."
$PYTHON_CMD validation_script.py

# Check exit status
if [ $? -eq 0 ]; then
    log "Validation completed successfully"
else
    log "ERROR: Validation failed with exit code $?"
    exit 1
fi

log "Professional Crypto Validation System completed"