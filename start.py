#!/usr/bin/env python3
"""
Simple start script for Render deployment
Runs the crypto analysis system without shell script dependencies
"""

import os
import sys
from datetime import datetime

def log(message):
    """Log with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def main():
    log("Starting Crypto Analysis System on Render...")
    
    # Check Python version
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    log(f"Python version: {python_version}")
    
    # Check critical environment variables
    critical_vars = ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'OPENAI_API_KEY']
    missing_vars = []
    
    for var in critical_vars:
        value = os.getenv(var)
        if not value or len(value) < 5:
            missing_vars.append(var)
        else:
            log(f"✓ {var} configured")
    
    if missing_vars:
        log("❌ Missing environment variables:")
        for var in missing_vars:
            log(f"  ❌ {var}")
        log("Configure these in your Render dashboard under Environment settings")
        sys.exit(1)
    
    # Import and run main script
    try:
        log("Loading main analysis module...")
        import importlib.util
        
        # Load 6.py as a module
        spec = importlib.util.spec_from_file_location("crypto_analysis", "6.py")
        crypto_module = importlib.util.module_from_spec(spec)
        
        log("Executing crypto analysis...")
        spec.loader.exec_module(crypto_module)
        
        log("✅ Crypto analysis completed successfully")
        
    except ImportError as e:
        log(f"❌ Import error: {e}")
        log("Make sure all required packages are installed")
        sys.exit(1)
    except Exception as e:
        log(f"❌ Execution error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 