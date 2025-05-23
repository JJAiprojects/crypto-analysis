#!/usr/bin/env python3

import os
from dotenv import load_dotenv
from telegram_utils import TelegramBot

# Load environment variables
load_dotenv()

def test_production_bot():
    """Test production bot with clear identification"""
    print("🚀 TESTING PRODUCTION BOT\n")
    
    # Get production credentials
    prod_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    prod_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    print(f"Production Bot: {prod_bot_token[:10]}...")
    print(f"Production Chat: {prod_chat_id}")
    
    # Create production bot instance
    bot = TelegramBot(
        bot_token=prod_bot_token,
        chat_id=prod_chat_id
    )
    
    # Send test message with clear identification
    test_message = """🚀 <b>PRODUCTION BOT TEST</b>

📍 This message was sent to the <b>PRODUCTION</b> chat group
🤖 Bot: PRODUCTION bot (not test bot)
📱 Chat ID: """ + str(prod_chat_id) + """

✅ If you see this message, production bot is working correctly!

⚠️ <b>This confirms the main script is sending to this group</b>"""
    
    print("\n📤 Sending test message to PRODUCTION group...")
    success = bot.send_message(test_message)
    
    if success:
        print("✅ Production message sent successfully!")
        print(f"   Check chat group with ID: {prod_chat_id}")
    else:
        print("❌ Production message failed!")
    
    return success

if __name__ == "__main__":
    test_production_bot() 