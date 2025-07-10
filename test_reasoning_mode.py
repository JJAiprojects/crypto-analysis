#!/usr/bin/env python3
"""
Test script for reasoning mode functionality
"""

import asyncio
import sys
import os
from datetime import datetime, timezone

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_predictor import AIPredictor

def load_test_config():
    """Load test configuration"""
    return {
        "api_keys": {
            "openai": os.getenv("OPENAI_API_KEY", "test_key")
        },
        "telegram": {
            "enabled": True,
            "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", "test_bot_token"),
            "chat_id": os.getenv("TELEGRAM_CHAT_ID", "test_chat_id"),
            "test": {
                "enabled": True,
                "bot_token": os.getenv("TEST_TELEGRAM_BOT_TOKEN", "test_bot_token"),
                "chat_id": os.getenv("TEST_TELEGRAM_CHAT_ID", "test_chat_id")
            }
        },
        "reasoning_mode": {
            "enabled": True,
            "show_thought_process": True,
            "send_separate_message": True,
            "include_framework_steps": True
        }
    }

def create_mock_market_data():
    """Create mock market data for testing"""
    return {
        "crypto": {
            "btc": 45000,
            "eth": 2800
        },
        "fear_greed": {
            "index": 35,
            "sentiment": "Fear"
        },
        "btc_dominance": 52.5,
        "technical_indicators": {
            "BTC": {
                "price": 45000,
                "rsi14": 45.2,
                "signal": "BUY",
                "trend": "bullish",
                "support": 44000,
                "resistance": 46000,
                "volatility": "medium"
            },
            "ETH": {
                "price": 2800,
                "rsi14": 48.1,
                "signal": "BUY", 
                "trend": "bullish",
                "support": 2750,
                "resistance": 2850,
                "volatility": "medium"
            }
        },
        "macroeconomic": {
            "t10_yield": 4.2,
            "dollar_index": 105.5
        }
    }

async def test_reasoning_mode():
    """Test reasoning mode functionality"""
    print("🧠 TESTING REASONING MODE FUNCTIONALITY")
    print("=" * 50)
    
    # Load config
    config = load_test_config()
    
    # Create AI predictor
    ai_predictor = AIPredictor(config)
    
    # Create mock data
    market_data = create_mock_market_data()
    
    print("📊 Mock market data created")
    print(f"   BTC Price: ${market_data['crypto']['btc']:,}")
    print(f"   ETH Price: ${market_data['crypto']['eth']:,}")
    print(f"   Fear & Greed: {market_data['fear_greed']['index']} ({market_data['fear_greed']['sentiment']})")
    
    # Test 1: Regular prediction (no reasoning mode)
    print("\n🧪 TEST 1: Regular prediction (no reasoning mode)")
    print("-" * 40)
    
    try:
        result = ai_predictor.get_ai_prediction(market_data, reasoning_mode=False)
        if result and "error" not in result:
            print("✅ Regular prediction successful")
            print(f"   Response length: {result.get('response_length', 0)} chars")
            print(f"   Data points used: {result.get('data_points_used', 0)}")
        else:
            print("❌ Regular prediction failed")
            print(f"   Error: {result.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Regular prediction exception: {e}")
    
    # Test 2: Reasoning mode prediction
    print("\n🧠 TEST 2: Reasoning mode prediction")
    print("-" * 40)
    
    try:
        result = ai_predictor.get_ai_prediction(market_data, reasoning_mode=True)
        if result and "error" not in result:
            print("✅ Reasoning mode prediction successful")
            print(f"   Response length: {result.get('response_length', 0)} chars")
            print(f"   Data points used: {result.get('data_points_used', 0)}")
            print(f"   Reasoning mode: {result.get('reasoning_mode', False)}")
            
            # Check if reasoning sections are present
            prediction = result.get('prediction', '')
            if "STEP-BY-STEP REASONING" in prediction:
                print("✅ Step-by-step reasoning section found")
            else:
                print("⚠️  Step-by-step reasoning section not found")
                
            if "FINAL PREDICTION" in prediction:
                print("✅ Final prediction section found")
            else:
                print("⚠️  Final prediction section not found")
                
        else:
            print("❌ Reasoning mode prediction failed")
            print(f"   Error: {result.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Reasoning mode prediction exception: {e}")
    
    # Test 3: Message formatting
    print("\n📱 TEST 3: Message formatting")
    print("-" * 40)
    
    try:
        # Get reasoning mode result
        result = ai_predictor.get_ai_prediction(market_data, reasoning_mode=True)
        if result and "error" not in result:
            # Test thought process message formatting
            thought_message = ai_predictor.format_thought_process_message(result, market_data)
            print("✅ Thought process message formatted successfully")
            print(f"   Message length: {len(thought_message)} chars")
            
            # Test regular message formatting
            regular_message = ai_predictor.format_ai_telegram_message(result, market_data, test_mode=True)
            print("✅ Regular message formatted successfully")
            print(f"   Message length: {len(regular_message)} chars")
            
        else:
            print("❌ Cannot test message formatting - no valid result")
    except Exception as e:
        print(f"❌ Message formatting exception: {e}")
    
    print("\n" + "=" * 50)
    print("🧠 REASONING MODE TESTING COMPLETE")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(test_reasoning_mode()) 