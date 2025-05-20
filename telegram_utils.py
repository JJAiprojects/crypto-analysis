import requests
import json
import os
import time

# Load Telegram configuration
def load_telegram_config():
    # Try environment variables first
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if bot_token and chat_id:
        return {
            "bot_token": bot_token,
            "chat_id": chat_id,
            "enabled": True
        }
            # Fall back to default if file exists but is corrupted
            pass
    
    # Create default config file
    default_config = {
        "bot_token": "YOUR_BOT_TOKEN",
        "chat_id": "YOUR_CHAT_ID",
        "enabled": False
    }
    
    try:
        with open(config_file, "w") as f:
            json.dump(default_config, f, indent=4)
        print("[INFO] Created default telegram_config.json. Please update with your bot token and chat ID.")
    except Exception as e:
        print(f"[ERROR] Creating telegram config: {e}")
    
    return default_config

# Send message to Telegram
def send_telegram_message(message, disable_web_page_preview=True):
    """Send message(s) to Telegram - can handle a single message or a list of messages"""
    config = load_telegram_config()
    if not config["enabled"] or config["bot_token"] == "YOUR_BOT_TOKEN":
        print("[INFO] Telegram notifications not enabled or configured")
        return False
    
    # Handle a list of messages
    if isinstance(message, list):
        success = True
        for i, msg in enumerate(message):
            result = send_telegram_message(msg)
            success = success and result
            
            # Add a small delay between messages to maintain order
            if i < len(message) - 1:
                time.sleep(1.0)
        return success
    
    # Handle a single message
    try:
        url = f"https://api.telegram.org/bot{config['bot_token']}/sendMessage"
        payload = {
            "chat_id": config["chat_id"],
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": disable_web_page_preview
        }
        response = requests.post(url, data=payload)
        response.raise_for_status()
        print("[INFO] Telegram message sent successfully")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram message: {e}")
        return False
