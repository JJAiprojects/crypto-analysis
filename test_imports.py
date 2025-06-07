#!/usr/bin/env python3

try:
    from data_collector import CryptoDataCollector
    print("✅ CryptoDataCollector imported successfully")
except ImportError as e:
    print(f"❌ Failed to import CryptoDataCollector: {e}")

try:
    from ai_predictor import AIPredictor
    print("✅ AIPredictor imported successfully")
except ImportError as e:
    print(f"❌ Failed to import AIPredictor: {e}")

try:
    # Calculation predictor removed - AI predictor is more accurate
    print("✅ CalculationPredictor removed (AI predictor is more accurate)")
except ImportError as e:
    print(f"❌ Failed to import CalculationPredictor: {e}")

try:
    from telegram_utils import send_telegram_message
    print("✅ telegram_utils imported successfully")
except ImportError as e:
    print(f"❌ Failed to import telegram_utils: {e}")

print("\n🎉 All module imports tested!") 