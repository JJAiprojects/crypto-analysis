#!/usr/bin/env python3

import os
import json
from dotenv import load_dotenv

def debug_config():
    """Debug the configuration loading in main script"""
    print("🔍 CONFIGURATION DEBUG")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    print("1️⃣ Environment Variables:")
    env_vars = [
        "TELEGRAM_BOT_TOKEN",
        "TEST_TELEGRAM_BOT_TOKEN", 
        "TELEGRAM_CHAT_ID",
        "TEST_TELEGRAM_CHAT_ID"
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            print(f"   ✅ {var}: {value[:10]}...")
        else:
            print(f"   ❌ {var}: Not set")
    
    print("\n2️⃣ Config.json file:")
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
            
            telegram_config = config.get("telegram", {})
            print(f"   telegram.enabled: {telegram_config.get('enabled')}")
            
            bot_token = telegram_config.get("bot_token", "")
            chat_id = telegram_config.get("chat_id", "")
            print(f"   telegram.bot_token: {bot_token[:10] if bot_token else 'Not set'}...")
            print(f"   telegram.chat_id: {chat_id}")
            
            test_config = telegram_config.get("test", {})
            test_bot_token = test_config.get("bot_token", "")
            test_chat_id = test_config.get("chat_id", "")
            print(f"   telegram.test.bot_token: {test_bot_token[:10] if test_bot_token else 'Not set'}...")
            print(f"   telegram.test.chat_id: {test_chat_id}")
            
        except Exception as e:
            print(f"   ❌ Error reading config.json: {e}")
    else:
        print("   ❌ config.json not found")
    
    print("\n3️⃣ Simulating main script config loading:")
    
    # Simulate the config loading from main script
    config = {
        "telegram": {
            "enabled": True,
            "bot_token": "",
            "chat_id": "",
            "test": {
                "enabled": True,
                "bot_token": "",
                "chat_id": ""
            }
        },
        "test_mode": {
            "enabled": False
        }
    }
    
    # Load existing config if it exists (but skip sensitive data)
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r") as f:
                existing_config = json.load(f)
                # Update config with existing values, but exclude sensitive data
                for key, value in existing_config.items():
                    if key in config:
                        if key == "telegram":
                            # Skip telegram section - will be loaded from env vars
                            continue
                        elif isinstance(value, dict) and isinstance(config[key], dict):
                            config[key].update(value)
                        else:
                            config[key] = value
        except Exception as e:
            print(f"   ❌ Error loading existing config: {e}")
    
    # NOW load sensitive data from environment variables (ALWAYS takes priority)
    config["telegram"]["bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN", "")
    config["telegram"]["chat_id"] = os.getenv("TELEGRAM_CHAT_ID", "")
    config["telegram"]["test"]["bot_token"] = os.getenv("TEST_TELEGRAM_BOT_TOKEN", "")
    config["telegram"]["test"]["chat_id"] = os.getenv("TEST_TELEGRAM_CHAT_ID", "")
    
    print(f"   ✅ Loaded from environment variables:")
    print(f"   Production bot_token: {config['telegram']['bot_token'][:10] if config['telegram']['bot_token'] else 'Empty'}...")
    print(f"   Production chat_id: {config['telegram']['chat_id']}")
    print(f"   Test bot_token: {config['telegram']['test']['bot_token'][:10] if config['telegram']['test']['bot_token'] else 'Empty'}...")
    print(f"   Test chat_id: {config['telegram']['test']['chat_id']}")
    
    # Simulate test mode
    is_test_mode = True  # Assuming you're running with --test
    if is_test_mode:
        print("\n   🧪 TEST MODE SIMULATION:")
        original_bot_token = config["telegram"]["bot_token"]
        original_chat_id = config["telegram"]["chat_id"]
        
        print(f"   Original (production) bot_token: {original_bot_token[:10] if original_bot_token else 'Empty'}...")
        print(f"   Original (production) chat_id: {original_chat_id}")
        
        # Switch to test settings
        config["telegram"]["bot_token"] = config["telegram"]["test"]["bot_token"]
        config["telegram"]["chat_id"] = config["telegram"]["test"]["chat_id"]
        
        print(f"   Switched to test bot_token: {config['telegram']['bot_token'][:10] if config['telegram']['bot_token'] else 'Empty'}...")
        print(f"   Switched to test chat_id: {config['telegram']['chat_id']}")
    
    print("\n4️⃣ Final configuration for TelegramBot:")
    final_bot_token = config["telegram"]["bot_token"]
    final_chat_id = config["telegram"]["chat_id"]
    print(f"   bot_token: {final_bot_token[:10] if final_bot_token else 'Empty'}...")
    print(f"   chat_id: {final_chat_id}")
    
    if not final_bot_token or not final_chat_id:
        print("\n❌ PROBLEM FOUND: Missing bot token or chat ID in final config!")
        return False
    
    print("\n5️⃣ Quick test with final config:")
    import requests
    
    try:
        url = f"https://api.telegram.org/bot{final_bot_token}/getMe"
        response = requests.get(url)
        if response.status_code == 200:
            print("   ✅ Bot token is valid")
        else:
            print(f"   ❌ Bot token validation failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error validating bot token: {e}")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{final_bot_token}/getChat"
        params = {"chat_id": final_chat_id}
        response = requests.get(url, params=params)
        if response.status_code == 200:
            print("   ✅ Chat access is valid")
            return True
        else:
            print(f"   ❌ Chat access failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Error checking chat access: {e}")
        return False

def debug_production_config():
    """Debug production configuration"""
    print("=== PRODUCTION CONFIG DEBUG ===\n")
    
    # Check .env file
    if os.path.exists('.env'):
        print("✓ .env file exists (local development)")
        try:
            from dotenv import load_dotenv
            load_dotenv()
            print("✓ .env file loaded successfully")
        except ImportError:
            print("⚠ python-dotenv not installed - using system environment variables")
        except Exception as e:
            print(f"⚠ Error loading .env file: {e}")
    else:
        print("No .env file found - using system environment variables (cloud deployment mode)")
    
    # Check production variables
    print("\n📱 PRODUCTION TELEGRAM CONFIG:")
    prod_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    prod_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    print(f"TELEGRAM_BOT_TOKEN: {'✓ Set' if prod_bot_token else '✗ Missing'}")
    print(f"TELEGRAM_CHAT_ID: {'✓ Set' if prod_chat_id else '✗ Missing'}")
    
    if prod_bot_token:
        print(f"Bot token starts with: {prod_bot_token[:10]}...")
    if prod_chat_id:
        print(f"Chat ID: {prod_chat_id}")
    
    # Check test variables
    print("\n🧪 TEST TELEGRAM CONFIG:")
    test_bot_token = os.getenv("TEST_TELEGRAM_BOT_TOKEN")
    test_chat_id = os.getenv("TEST_TELEGRAM_CHAT_ID")
    
    print(f"TEST_TELEGRAM_BOT_TOKEN: {'✓ Set' if test_bot_token else '✗ Missing'}")
    print(f"TEST_TELEGRAM_CHAT_ID: {'✓ Set' if test_chat_id else '✗ Missing'}")
    
    # Check other important env vars
    print("\n🔑 OTHER CREDENTIALS:")
    openai_key = os.getenv("OPENAI_API_KEY")
    print(f"OPENAI_API_KEY: {'✓ Set' if openai_key else '✗ Missing'}")
    
    # Summary
    print("\n📋 SUMMARY:")
    if prod_bot_token and prod_chat_id:
        print("✅ Production Telegram credentials are configured")
    else:
        print("❌ Production Telegram credentials are MISSING")
        print("   → Script will not send messages in production mode")
    
    if test_bot_token and test_chat_id:
        print("✅ Test Telegram credentials are configured")
    else:
        print("❌ Test Telegram credentials are MISSING")
    
    # Configuration suggestions
    if not prod_bot_token or not prod_chat_id:
        print("\n🔧 TO FIX:")
        if os.path.exists('.env'):
            print("Add these lines to your .env file:")
            print("TELEGRAM_BOT_TOKEN=your_production_bot_token")
            print("TELEGRAM_CHAT_ID=your_production_chat_id")
        else:
            print("For cloud deployment: Set these environment variables in your platform dashboard:")
            print("TELEGRAM_BOT_TOKEN=your_production_bot_token")
            print("TELEGRAM_CHAT_ID=your_production_chat_id")

if __name__ == "__main__":
    debug_config()
    debug_production_config() 