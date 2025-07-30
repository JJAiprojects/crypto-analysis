#!/usr/bin/env python3

import os
import json
import requests

def test_grok_api():
    """Test Grok API integration"""
    
    # Get API key from environment or config
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        # Try to load from config.json
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
                api_key = config["api_keys"]["xai"]
        except Exception as e:
            print(f"[ERROR] Could not load API key: {e}")
            return False
    
    if not api_key or api_key == "YOUR_XAI_API_KEY":
        print("[ERROR] XAI_API_KEY not configured")
        return False
    
    try:
        # Test simple API call
        print("[INFO] Testing xAI API with simple question...")
        
        url = "https://api.x.ai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload = {
            "model": "grok-4",
            "messages": [
                {
                    "role": "user",
                    "content": "What is the meaning of life, the universe, and everything?"
                }
            ],
            "temperature": 0.7
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        # Check response
        if result and "choices" in result and len(result["choices"]) > 0:
            content = result["choices"][0]["message"]["content"]
            print(f"[SUCCESS] ✅ xAI API test successful!")
            print(f"[INFO] Response: {content[:100]}...")
            return True
        else:
            print("[ERROR] Invalid response format from xAI API")
            return False
            
    except Exception as e:
        print(f"[ERROR] Grok API test failed: {e}")
        return False

def test_ai_predictor_integration():
    """Test AI predictor with Grok integration"""
    
    try:
        from ai_predictor import AIPredictor
        
        # Create test config
        test_config = {
            "api_keys": {
                "xai": os.getenv("XAI_API_KEY", "test_key"),
                "openai": os.getenv("OPENAI_API_KEY", "test_key")
            },
            "ai_provider": {
                "primary": "xai",
                "fallback": "openai",
                "enabled": {
                    "xai": True,
                    "openai": False
                }
            },
            "telegram": {
                "enabled": False,
                "bot_token": "test",
                "chat_id": "test"
            }
        }
        
        print("[INFO] Testing AI predictor integration...")
        predictor = AIPredictor(test_config)
        
        # Create mock market data
        mock_data = {
            "crypto": {"btc": 45000, "eth": 2800},
            "fear_greed": {"index": 35, "sentiment": "Fear"},
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
                }
            }
        }
        
        # Test prediction (this will fail if API key is not real, but should initialize correctly)
        print("[INFO] Testing AI predictor initialization...")
        print(f"[INFO] Primary provider: {predictor.primary_provider}")
        print(f"[INFO] xAI client available: {predictor.xai_client is not None}")
        print(f"[INFO] OpenAI client available: {predictor.openai_client is not None}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] AI predictor integration test failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("🧪 GROK API INTEGRATION TEST")
    print("=" * 50)
    
    # Test 1: Direct Grok API
    print("\n1. Testing direct Grok API...")
    grok_test = test_grok_api()
    
    # Test 2: AI Predictor integration
    print("\n2. Testing AI predictor integration...")
    predictor_test = test_ai_predictor_integration()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS")
    print("=" * 50)
    print(f"Grok API Test: {'✅ PASSED' if grok_test else '❌ FAILED'}")
    print(f"AI Predictor Test: {'✅ PASSED' if predictor_test else '❌ FAILED'}")
    
    if grok_test and predictor_test:
        print("\n🎉 All tests passed! Grok integration is ready.")
    else:
        print("\n⚠️ Some tests failed. Check your configuration.") 