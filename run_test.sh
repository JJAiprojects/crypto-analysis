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

# Check for environment variables (both .env file and system env vars)
if [ -f ".env" ]; then
    log "✓ Found .env file - loading local development environment"
    source .env
else
    log "No .env file found - using system environment variables (cloud deployment mode)"
fi

# Verify critical environment variables are set (from either source)
if [ -z "$TEST_TELEGRAM_BOT_TOKEN" ] || [ -z "$TEST_TELEGRAM_CHAT_ID" ]; then
    log "ERROR: Missing test environment variables!"
    log "TEST_TELEGRAM_BOT_TOKEN: ${TEST_TELEGRAM_BOT_TOKEN:+SET}"
    log "TEST_TELEGRAM_CHAT_ID: ${TEST_TELEGRAM_CHAT_ID:+SET}"
    log ""
    log "For local development: Add test variables to .env file"
    log "For cloud deployment: Set test environment variables in your platform dashboard"
    exit 1
fi

log "✓ Test environment variables configured"

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