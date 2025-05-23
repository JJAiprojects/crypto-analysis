#!/usr/bin/env python3

import requests
import json
import os
import re
from datetime import datetime

class TelegramBot:
    """Simple Telegram Bot class for sending messages"""
    
    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    def send_message(self, message, parse_mode="HTML", disable_web_page_preview=True):
        """Send a message to Telegram"""
        if not self.bot_token or not self.chat_id:
            print("[WARN] Telegram credentials not configured")
            return False
        
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode,
                "disable_web_page_preview": disable_web_page_preview
            }
            
            response = requests.post(url, data=payload, timeout=10)
            
            # Handle parsing errors by falling back to plain text
            if response.status_code == 400 and "can't parse entities" in response.text.lower():
                print("[WARN] HTML parsing failed, sending as plain text")
                payload["parse_mode"] = None
                # Remove HTML tags for plain text
                plain_message = re.sub(r'<[^>]+>', '', message)
                payload["text"] = plain_message
                response = requests.post(url, data=payload, timeout=10)
            
            response.raise_for_status()
            print("[INFO] Telegram message sent successfully")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to send Telegram message: {e}")
            return False
    
    def get_updates(self):
        """Get updates from Telegram (for testing chat ID)"""
        try:
            url = f"{self.base_url}/getUpdates"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[ERROR] Failed to get Telegram updates: {e}")
            return None

def send_telegram_message(message, is_test=False):
    """Legacy function for backward compatibility"""
    from dotenv import load_dotenv
    load_dotenv()
    
    # Select appropriate bot credentials
    if is_test:
        bot_token = os.getenv("TEST_TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TEST_TELEGRAM_CHAT_ID", "")
        print("[TEST] Using test Telegram bot")
    else:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    
    if not bot_token or not chat_id:
        print("[WARN] Telegram credentials not configured")
        return False
    
    bot = TelegramBot(bot_token, chat_id)
    return bot.send_message(message)

def test_telegram_connection():
    """Test Telegram bot connection"""
    from dotenv import load_dotenv
    load_dotenv()
    
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    
    if not bot_token or not chat_id:
        print("[ERROR] Telegram credentials not configured")
        print("Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables")
        return False
    
    bot = TelegramBot(bot_token, chat_id)
    
    # Test message
    test_message = f"🤖 <b>MarketAI Test Message</b>\n\n✅ Telegram connection successful!\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    success = bot.send_message(test_message)
    
    if success:
        print("[SUCCESS] Telegram test message sent successfully!")
        print(f"Bot Token: {bot_token[:10]}...")
        print(f"Chat ID: {chat_id}")
    else:
        print("[ERROR] Failed to send Telegram test message")
        print("Please check your bot token and chat ID")
    
    return success

if __name__ == "__main__":
    # Test Telegram connection when run directly
    test_telegram_connection()
