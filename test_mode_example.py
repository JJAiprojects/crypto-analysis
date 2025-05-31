#!/usr/bin/env python3
"""
Test Mode Example - Demonstrates the differences between test and production modes

This script shows:
1. How to configure test vs production environments
2. Different telegram bot tokens and chat IDs
3. File prefixes for test outputs
4. Database saving behavior

Usage:
    python test_mode_example.py --production
    python test_mode_example.py --test
"""

import os
import sys
import json
from datetime import datetime, timezone

def show_configuration_differences():
    """Show the differences between test and production configurations"""
    
    print("🔧 CONFIGURATION COMPARISON")
    print("=" * 60)
    
    # Production Configuration
    prod_config = {
        "telegram": {
            "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", "Not set"),
            "chat_id": os.getenv("TELEGRAM_CHAT_ID", "Not set")
        },
        "database_save": True,
        "file_creation": True,
        "api_calls": True
    }
    
    # Test Configuration
    test_config = {
        "telegram": {
            "bot_token": os.getenv("TEST_TELEGRAM_BOT_TOKEN", "Not set"),
            "chat_id": os.getenv("TEST_TELEGRAM_CHAT_ID", "Not set")
        },
        "database_save": True,  # Same as production
        "file_creation": True,  # Same as production
        "api_calls": True       # Same as production
    }
    
    print("\n🚀 PRODUCTION MODE:")
    print(f"  📤 Bot Token: {prod_config['telegram']['bot_token'][:10]}..." if prod_config['telegram']['bot_token'] != "Not set" else "  📤 Bot Token: Not configured")
    print(f"  📍 Chat ID: {prod_config['telegram']['chat_id']}")
    print(f"  💾 Database Save: {prod_config['database_save']}")
    print(f"  📄 File Creation: {prod_config['file_creation']}")
    print(f"  🌐 API Calls: {prod_config['api_calls']}")
    
    print("\n🧪 TEST MODE:")
    print(f"  📤 Bot Token: {test_config['telegram']['bot_token'][:10]}..." if test_config['telegram']['bot_token'] != "Not set" else "  📤 Bot Token: Not configured")
    print(f"  📍 Chat ID: {test_config['telegram']['chat_id']}")
    print(f"  💾 Database Save: {test_config['database_save']} (SAME as production)")
    print(f"  📄 File Creation: {test_config['file_creation']} (SAME as production)")
    print(f"  🌐 API Calls: {test_config['api_calls']} (SAME as production)")
    
    print(f"\n🔍 KEY DIFFERENCE:")
    print(f"  🧪 Test mode ONLY uses different Telegram bot and chat")
    print(f"  ✅ All other functionality is identical to production")
    
    return prod_config, test_config

def simulate_prediction_workflow(test_mode=False):
    """Simulate how a prediction workflow works in both modes"""
    
    mode_name = "TEST" if test_mode else "PRODUCTION"
    mode_emoji = "🧪" if test_mode else "🚀"
    
    print(f"\n{mode_emoji} SIMULATION - {mode_name} MODE")
    print("=" * 60)
    
    # Mock prediction data
    prediction_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "ai_prediction",
        "test_mode": test_mode,
        "prediction": "BTC expected to reach $47,000 within 12 hours",
        "confidence": 0.75,
        "market_context": {
            "btc_price": 45000,
            "fear_greed": 35,
            "trend": "bullish"
        }
    }
    
    # File naming (same for both modes)
    filename = f"ai_prediction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    print(f"1️⃣ Data Collection:")
    print(f"   🌐 API calls to CoinGecko, Binance, FRED, etc.")
    print(f"   📊 50+ data points collected")
    print(f"   ✅ IDENTICAL for both modes")
    
    print(f"\n2️⃣ AI Prediction Generation:")
    print(f"   🤖 OpenAI GPT-4 API call")
    print(f"   📈 {prediction_data['prediction']}")
    print(f"   🎯 Confidence: {prediction_data['confidence']*100:.1f}%")
    print(f"   ✅ IDENTICAL for both modes")
    
    print(f"\n3️⃣ File Saving:")
    print(f"   📄 Filename: {filename}")
    print(f"   💾 Content includes test_mode flag: {test_mode}")
    print(f"   ✅ IDENTICAL naming and saving process")
    
    print(f"\n4️⃣ Database Saving:")
    print(f"   💽 Saving to crypto_predictions.db")
    print(f"   📝 Record marked with test_mode: {test_mode}")
    print(f"   ✅ IDENTICAL database operations")
    
    print(f"\n5️⃣ Telegram Notification:")
    if test_mode:
        print(f"   🧪 Message sent to TEST group")
        print(f"   📱 Bot: TEST_TELEGRAM_BOT_TOKEN")
        print(f"   💬 Chat: TEST_TELEGRAM_CHAT_ID")
        print(f"   📝 Prefix: '🧪 [TEST]'")
        print(f"   ⚠️ ONLY DIFFERENCE from production")
    else:
        print(f"   🚀 Message sent to PRODUCTION group")
        print(f"   📱 Bot: TELEGRAM_BOT_TOKEN")
        print(f"   💬 Chat: TELEGRAM_CHAT_ID")
        print(f"   📝 Prefix: (none)")
    
    # Save actual file for demonstration
    try:
        with open(filename, 'w') as f:
            json.dump(prediction_data, f, indent=2)
        print(f"\n✅ Demo file created: {filename}")
        print(f"   📋 Check 'test_mode' field to identify test vs production")
    except Exception as e:
        print(f"\n❌ Failed to create demo file: {e}")

def show_environment_setup():
    """Show how to set up environment variables for test mode"""
    
    print("\n🔐 ENVIRONMENT VARIABLE SETUP")
    print("=" * 60)
    
    print("\n📋 Required Environment Variables:")
    
    env_examples = [
        ("TELEGRAM_BOT_TOKEN", "Production Telegram bot token", "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"),
        ("TELEGRAM_CHAT_ID", "Production chat/group ID", "-1001234567890"),
        ("TEST_TELEGRAM_BOT_TOKEN", "Test Telegram bot token", "0987654321:XYZABCDEFGHIJKLMNOPQRSTUVWXYZzyxwvu"),
        ("TEST_TELEGRAM_CHAT_ID", "Test chat/group ID", "-1009876543210"),
        ("OPENAI_API_KEY", "OpenAI API key for AI predictions", "sk-1234567890abcdef..."),
        ("FRED_API_KEY", "FRED API for economic data", "abcdef1234567890..."),
        ("ALPHAVANTAGE_API_KEY", "Alpha Vantage for stock data", "ABCDEF123456...")
    ]
    
    for var_name, description, example in env_examples:
        current_value = os.getenv(var_name, "Not set")
        status = "✅" if current_value != "Not set" else "❌"
        print(f"\n{status} {var_name}")
        print(f"   📝 {description}")
        print(f"   💡 Example: {example}")
        if current_value != "Not set":
            masked = current_value[:8] + "..." if len(current_value) > 8 else current_value
            print(f"   🔑 Current: {masked}")

def show_telegram_setup_guide():
    """Show how to set up different Telegram bots for test and production"""
    
    print("\n📱 TELEGRAM SETUP GUIDE")
    print("=" * 60)
    
    print("""
🤖 Creating Telegram Bots:

1️⃣ Production Bot:
   • Message @BotFather on Telegram
   • Create new bot: /newbot
   • Name it: "Crypto Prediction Bot" (or similar)
   • Get bot token (format: 1234567890:ABC...)
   • Save as TELEGRAM_BOT_TOKEN

2️⃣ Test Bot:
   • Message @BotFather again
   • Create another bot: /newbot
   • Name it: "Crypto Prediction TEST Bot"
   • Get bot token
   • Save as TEST_TELEGRAM_BOT_TOKEN

📍 Getting Chat IDs:

1️⃣ Production Group:
   • Create a group for production alerts
   • Add your production bot to the group
   • Send a message in the group
   • Visit: https://api.telegram.org/bot<TOKEN>/getUpdates
   • Look for "chat":{"id": -1001234567890}
   • Save as TELEGRAM_CHAT_ID

2️⃣ Test Group:
   • Create a separate group for testing
   • Add your test bot to this group
   • Follow same process with test bot token
   • Save as TEST_TELEGRAM_CHAT_ID

⚠️ Important: Keep production and test groups separate!
    This prevents test messages from cluttering production alerts.
""")

def main():
    """Main demonstration function"""
    
    import argparse
    parser = argparse.ArgumentParser(description="Test Mode vs Production Mode Demonstration")
    parser.add_argument("--test", action="store_true", help="Run in test mode")
    parser.add_argument("--production", action="store_true", help="Run in production mode")
    parser.add_argument("--setup", action="store_true", help="Show setup guide")
    
    args = parser.parse_args()
    
    print("🧪 TEST MODE vs PRODUCTION MODE DEMONSTRATION")
    print("=" * 80)
    
    if args.setup:
        show_environment_setup()
        show_telegram_setup_guide()
        return
    
    # Show configuration differences
    show_configuration_differences()
    
    if args.test:
        simulate_prediction_workflow(test_mode=True)
    elif args.production:
        simulate_prediction_workflow(test_mode=False)
    else:
        print("\n📖 USAGE EXAMPLES:")
        print("   python test_mode_example.py --test       # Simulate test mode")
        print("   python test_mode_example.py --production # Simulate production mode")
        print("   python test_mode_example.py --setup      # Show setup guide")
        
        print("\n🚀 To run the actual system:")
        print("   python 6.py --test      # Run in test mode")
        print("   python 6.py             # Run in production mode")
        print("   python 6.py --analysis  # Analyze data only")

if __name__ == "__main__":
    main() 