import requests
import json
import os
import time

class TelegramBot:
    def __init__(self, bot_token=None, chat_id=None):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
        
    def send_message(self, message, disable_web_page_preview=True, parse_mode="HTML"):
        """Send a message to Telegram with length checking and error handling"""
        if not self.bot_token or not self.chat_id:
            print("[INFO] Telegram bot not configured")
            return False
        
        # Check message length (Telegram limit is 4096 characters)
        if len(message) > 4096:
            print(f"[WARN] Message too long ({len(message)} chars). Splitting into parts...")
            return self._send_long_message(message, disable_web_page_preview)
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview
        }
            
            print(f"[DEBUG] Sending message ({len(message)} chars)")
            response = requests.post(url, json=payload, timeout=30)
            
            # Get response details for debugging
            result = response.json()
            
            if response.status_code == 200 and result.get("ok"):
                print("[INFO] Telegram message sent successfully")
                return True
            else:
                print(f"[ERROR] Telegram API error:")
                print(f"  Status Code: {response.status_code}")
                print(f"  Error Code: {result.get('error_code', 'Unknown')}")
                print(f"  Description: {result.get('description', 'Unknown error')}")
                
                # Try sending without formatting if parsing error
                if "parse" in result.get('description', '').lower():
                    print("[INFO] HTML parse error. Trying without formatting...")
                    return self._send_plain_message(message, disable_web_page_preview)
                
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Network error sending Telegram message: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] Unexpected error sending Telegram message: {e}")
            return False
    
    def _send_plain_message(self, message, disable_web_page_preview=True):
        """Send message without HTML/Markdown formatting as fallback"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            # Remove HTML and markdown formatting
            plain_message = (message.replace('<b>', '').replace('</b>', '')
                           .replace('<u>', '').replace('</u>', '')
                           .replace('<i>', '').replace('</i>', '')
                           .replace('━━━', '---')  # Replace box drawing chars with dashes
                           .replace('*', '').replace('`', '').replace('_', ''))
            
            payload = {
                "chat_id": self.chat_id,
                "text": plain_message,
                "disable_web_page_preview": disable_web_page_preview
            }
            
            response = requests.post(url, json=payload, timeout=30)
            result = response.json()
            
            if response.status_code == 200 and result.get("ok"):
                print("[INFO] Plain text message sent successfully")
                return True
            else:
                print(f"[ERROR] Plain text message also failed: {result.get('description', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Plain text fallback failed: {e}")
            return False
    
    def _send_long_message(self, message, disable_web_page_preview=True):
        """Split long messages and send in parts"""
        try:
            # Split message into chunks of ~3500 chars to stay well under limit
            max_chunk_size = 3500
            chunks = []
            
            # Try to split at natural boundaries (double newlines first)
            parts = message.split('\n\n')
            current_chunk = ""
            
            for part in parts:
                if len(current_chunk + part + '\n\n') <= max_chunk_size:
                    current_chunk += part + '\n\n'
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = part + '\n\n'
            
            if current_chunk:
                chunks.append(current_chunk.strip())
            
            # If chunks are still too long, split more aggressively
            final_chunks = []
            for chunk in chunks:
                if len(chunk) <= max_chunk_size:
                    final_chunks.append(chunk)
                else:
                    # Split by single newlines
                    lines = chunk.split('\n')
                    current_line_chunk = ""
                    for line in lines:
                        if len(current_line_chunk + line + '\n') <= max_chunk_size:
                            current_line_chunk += line + '\n'
                        else:
                            if current_line_chunk:
                                final_chunks.append(current_line_chunk.strip())
                            current_line_chunk = line + '\n'
                    if current_line_chunk:
                        final_chunks.append(current_line_chunk.strip())
            
            # Send all chunks
            success = True
            for i, chunk in enumerate(final_chunks):
                print(f"[INFO] Sending part {i+1}/{len(final_chunks)} ({len(chunk)} chars)")
                result = self.send_message(chunk, disable_web_page_preview)
                success = success and result
                
                # Small delay between messages
                if i < len(final_chunks) - 1:
                    time.sleep(1)
            
            return success
            
        except Exception as e:
            print(f"[ERROR] Failed to split and send long message: {e}")
            return False

# Load Telegram configuration
def load_telegram_config():
    config_file = "telegram_config.json"  # Define the missing variable
    
    # Try environment variables first
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if bot_token and chat_id:
        return {
            "bot_token": bot_token,
            "chat_id": chat_id,
            "enabled": True
        }
    
    # Try loading from config file
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
                if config.get("bot_token") and config.get("chat_id"):
                    return config
        except Exception as e:
            print(f"[ERROR] Loading telegram config: {e}")
    
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
            "parse_mode": "HTML",  # Use HTML to match debug script
            "disable_web_page_preview": disable_web_page_preview
        }
        # Use json=payload instead of data=payload for better compatibility
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        # Check if the response is actually successful
        result = response.json()
        if result.get("ok"):
            print("[INFO] Telegram message sent successfully")
            return True
        else:
            print(f"[ERROR] Telegram API returned error: {result.get('description', 'Unknown error')}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to send Telegram message: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error sending Telegram message: {e}")
        return False
