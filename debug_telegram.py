#!/usr/bin/env python3

import os
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

from telegram_utils import TelegramBot

# Load environment variables if available
if os.path.exists('.env') and DOTENV_AVAILABLE:
    load_dotenv()
    print("✓ Loaded .env file for local development")
elif os.path.exists('.env') and not DOTENV_AVAILABLE:
    print("⚠ .env file found but python-dotenv not installed - using system environment variables")
else:
    print("No .env file found - using system environment variables (cloud deployment mode)")

def test_env_loading():
    """Test if environment variables are loading correctly"""
    print("\nTesting environment variable loading...")
    
    # Test loading variables
    test_bot_token = os.getenv("TEST_TELEGRAM_BOT_TOKEN")
    test_chat_id = os.getenv("TEST_TELEGRAM_CHAT_ID")
    
    print(f"Test bot token loaded: {'Yes' if test_bot_token else 'No'}")
    print(f"Test chat ID loaded: {'Yes' if test_chat_id else 'No'}")
    
    if test_bot_token:
        print(f"Bot token starts with: {test_bot_token[:10]}...")
    if test_chat_id:
        print(f"Chat ID: {test_chat_id}")
    
    if not test_bot_token or not test_chat_id:
        print("\n⚠ Missing test environment variables!")
        print("For local development: Add TEST_TELEGRAM_BOT_TOKEN and TEST_TELEGRAM_CHAT_ID to .env file")
        print("For cloud deployment: Set these variables in your platform dashboard")
    
    return bool(test_bot_token and test_chat_id)

def test_simple_message():
    """Test sending a simple message without complex formatting"""
    print("\nTesting simple message...")
    
    bot = TelegramBot(
        bot_token=os.getenv("TEST_TELEGRAM_BOT_TOKEN"),
        chat_id=os.getenv("TEST_TELEGRAM_CHAT_ID")
    )
    
    simple_message = "🔍 TEST MESSAGE\n\nThis is a simple test message to verify Telegram functionality."
    
    success = bot.send_message(simple_message)
    return success

def test_formatted_message():
    """Test sending a message with basic Markdown formatting"""
    print("\nTesting formatted message...")
    
    bot = TelegramBot(
        bot_token=os.getenv("TEST_TELEGRAM_BOT_TOKEN"),
        chat_id=os.getenv("TEST_TELEGRAM_CHAT_ID")
    )
    
    formatted_message = """🔍 *CRYPTO ANALYSIS TEST*

📊 *EXECUTIVE SUMMARY*
• Scenario: *BULLISH* (medium confidence)
• Timeframe: next 12 hours

₿ *BTC ANALYSIS*
━━━━━━━━━━━━━━━━━━━━━━━━
💰 Current: `$110,000`
📈 Resistance: `$112,000`
📉 Support: `$108,000`

🎯 *TRADING PLAN*
• Entry Zone: `$110,000`
• Target 1: 📈 `$112,000` (1.8%)
• Stop Loss: 📉 `$108,000` (1.8%)

⚠️ *Risk Management: Use proper position sizing*"""
    
    success = bot.send_message(formatted_message)
    return success

def main():
    print("=== TELEGRAM DEBUG TEST ===\n")
    
    # Test 1: Environment variable loading
    if not test_env_loading():
        print("❌ Environment variables not loaded correctly!")
        return
    
    # Test 2: Simple message
    if not test_simple_message():
        print("❌ Simple message failed!")
        return
    
    print("✓ Simple message sent successfully!")
    
    # Test 3: Formatted message
    if not test_formatted_message():
        print("❌ Formatted message failed!")
        return
    
    print("✓ Formatted message sent successfully!")
    print("\n🎉 All tests passed!")

if __name__ == "__main__":
    main() 