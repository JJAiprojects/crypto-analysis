#!/bin/bash

# Test mode runner for the professional crypto analysis system
# This uses test bot credentials instead of production

# Set script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [TEST] $1"
}

log "Starting Professional Crypto Analysis System in TEST MODE..."

# Check if .env file exists
if [ ! -f ".env" ]; then
    log "ERROR: .env file not found!"
    log "Please create .env file with your API keys and bot tokens"
    exit 1
fi

# Source environment variables
source .env

# Verify test environment variables
if [ -z "$TEST_TELEGRAM_BOT_TOKEN" ] || [ -z "$TEST_TELEGRAM_CHAT_ID" ]; then
    log "ERROR: Missing test environment variables!"
    log "Please set TEST_TELEGRAM_BOT_TOKEN and TEST_TELEGRAM_CHAT_ID in .env"
    exit 1
fi

# Check Python availability
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

# Run in test mode
log "Starting analysis in test mode..."
$PYTHON_CMD 6.py --test

# Check exit status
if [ $? -eq 0 ]; then
    log "Test analysis completed successfully"
else
    log "ERROR: Test analysis failed with exit code $?"
    exit 1
fi

log "Test mode completed" 