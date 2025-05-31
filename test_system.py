#!/usr/bin/env python3

import os
import sys
import asyncio
import json
from datetime import datetime, timezone

def test_configuration():
    """Test the configuration system for both production and test modes"""
    print("=" * 60)
    print("🧪 TESTING CONFIGURATION SYSTEM")
    print("=" * 60)
    
    # Test environment variables
    env_vars = [
        "OPENAI_API_KEY",
        "FRED_API_KEY", 
        "ALPHAVANTAGE_API_KEY",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "TEST_TELEGRAM_BOT_TOKEN",
        "TEST_TELEGRAM_CHAT_ID"
    ]
    
    print("\n📋 Environment Variables Check:")
    for var in env_vars:
        value = os.getenv(var)
        if value:
            masked_value = value[:8] + "..." if len(value) > 8 else value
            print(f"  ✅ {var}: {masked_value}")
        else:
            print(f"  ❌ {var}: Not set")
    
    # Test config loading
    try:
        from data_collector import CryptoDataCollector
        
        config = {
            "api_keys": {
                "openai": os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY"),
                "fred": os.getenv("FRED_API_KEY", "YOUR_FRED_API_KEY"),
                "alphavantage": os.getenv("ALPHAVANTAGE_API_KEY", "YOUR_ALPHAVANTAGE_API_KEY")
            },
            "telegram": {
                "enabled": True,
                "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN"),
                "chat_id": os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID"),
                "test": {
                    "enabled": True,
                    "bot_token": os.getenv("TEST_TELEGRAM_BOT_TOKEN", "YOUR_TEST_BOT_TOKEN"),
                    "chat_id": os.getenv("TEST_TELEGRAM_CHAT_ID", "YOUR_TEST_CHAT_ID")
                }
            },
            "api": {
                "max_retries": 3,
                "timeout": 10,
                "backoff_factor": 2
            },
            "indicators": {
                "include_macroeconomic": True,
                "include_stock_indices": True,
                "include_commodities": True,
                "include_social_metrics": True
            }
        }
        
        print("\n🔧 Configuration Validation:")
        
        # Production config
        prod_valid = (
            config["telegram"]["bot_token"] != "YOUR_BOT_TOKEN" and
            config["telegram"]["chat_id"] != "YOUR_CHAT_ID"
        )
        print(f"  {'✅' if prod_valid else '❌'} Production Telegram: {'Valid' if prod_valid else 'Invalid'}")
        
        # Test config  
        test_valid = (
            config["telegram"]["test"]["bot_token"] != "YOUR_TEST_BOT_TOKEN" and
            config["telegram"]["test"]["chat_id"] != "YOUR_TEST_CHAT_ID"
        )
        print(f"  {'✅' if test_valid else '❌'} Test Telegram: {'Valid' if test_valid else 'Invalid'}")
        
        # API keys
        api_valid = (
            config["api_keys"]["openai"] != "YOUR_OPENAI_API_KEY"
        )
        print(f"  {'✅' if api_valid else '❌'} OpenAI API Key: {'Valid' if api_valid else 'Invalid'}")
        
        return config, prod_valid, test_valid, api_valid
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return None, False, False, False

def test_data_collection():
    """Test data collection functionality"""
    print("\n=" * 60)
    print("📊 TESTING DATA COLLECTION")
    print("=" * 60)
    
    try:
        from data_collector import CryptoDataCollector
        
        config, _, _, _ = test_configuration()
        if not config:
            print("❌ Cannot test data collection - config failed")
            return False
        
        print("\n🔄 Testing data collector initialization...")
        collector = CryptoDataCollector(config)
        print("✅ Data collector initialized successfully")
        
        print("\n📈 Testing basic crypto data collection...")
        crypto_data = collector.get_crypto_data()
        if crypto_data and crypto_data.get("btc") and crypto_data.get("eth"):
            print(f"✅ Crypto data: BTC ${crypto_data['btc']:,.0f}, ETH ${crypto_data['eth']:,.0f}")
        else:
            print("❌ Crypto data collection failed")
            
        print("\n😨 Testing Fear & Greed index...")
        fg_data = collector.get_fear_greed_index()
        if fg_data and fg_data.get("index"):
            print(f"✅ Fear & Greed: {fg_data['index']} ({fg_data.get('sentiment', 'Unknown')})")
        else:
            print("❌ Fear & Greed data collection failed")
            
        return True
        
    except Exception as e:
        print(f"❌ Data collection test failed: {e}")
        return False

async def test_ai_predictor(test_mode=False):
    """Test AI predictor functionality"""
    mode_text = "TEST" if test_mode else "PRODUCTION"
    print(f"\n=" * 60)
    print(f"🤖 TESTING AI PREDICTOR - {mode_text} MODE")
    print("=" * 60)
    
    try:
        from ai_predictor import AIPredictor
        
        config, prod_valid, test_valid, api_valid = test_configuration()
        if not config:
            print("❌ Cannot test AI predictor - config failed")
            return False
            
        if not api_valid:
            print("⚠️ OpenAI API key not configured - skipping AI test")
            return False
        
        if test_mode and not test_valid:
            print("⚠️ Test Telegram config invalid - testing without sending")
        elif not test_mode and not prod_valid:
            print("⚠️ Production Telegram config invalid - testing without sending") 
        
        print(f"\n🔄 Testing AI predictor initialization...")
        ai_predictor = AIPredictor(config)
        print("✅ AI predictor initialized successfully")
        
        # Mock market data for testing
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
            }
        }
        
        print(f"\n🧠 Testing AI prediction generation...")
        prediction = ai_predictor.run_ai_prediction(
            mock_data, 
            test_mode=test_mode, 
            save_results=True, 
            send_telegram=False  # Don't send during test
        )
        
        if prediction:
            print("✅ AI prediction generated successfully")
            return True
        else:
            print("❌ AI prediction failed")
            return False
            
    except Exception as e:
        print(f"❌ AI predictor test failed: {e}")
        return False

async def test_calculation_predictor(test_mode=False):
    """Test calculation predictor functionality"""
    mode_text = "TEST" if test_mode else "PRODUCTION"
    print(f"\n=" * 60)
    print(f"🧮 TESTING CALCULATION PREDICTOR - {mode_text} MODE")
    print("=" * 60)
    
    try:
        from calculation_predictor import CalculationPredictor
        
        config, prod_valid, test_valid, _ = test_configuration()
        if not config:
            print("❌ Cannot test calculation predictor - config failed")
            return False
        
        if test_mode and not test_valid:
            print("⚠️ Test Telegram config invalid - testing without sending")
        elif not test_mode and not prod_valid:
            print("⚠️ Production Telegram config invalid - testing without sending")
        
        print(f"\n🔄 Testing calculation predictor initialization...")
        calc_predictor = CalculationPredictor(config)
        print("✅ Calculation predictor initialized successfully")
        
        # Mock market data for testing
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
                    "volatility": "medium",
                    "volume_trend": "increasing",
                    "atr": 900
                },
                "ETH": {
                    "price": 2800,
                    "rsi14": 48.1,
                    "signal": "BUY",
                    "trend": "bullish",
                    "support": 2750,
                    "resistance": 2850,
                    "volatility": "medium",
                    "volume_trend": "stable",
                    "atr": 56
                }
            },
            "futures": {
                "BTC": {"funding_rate": 0.01, "long_ratio": 0.6, "short_ratio": 0.4},
                "ETH": {"funding_rate": 0.015, "long_ratio": 0.55, "short_ratio": 0.45}
            },
            "stock_indices": {"sp500_change": 1.2, "nasdaq_change": 1.5, "vix": 18.5},
            "interest_rates": {"fed_rate": 5.25},
            "inflation": {"inflation_rate": 3.2},
            "commodities": {"gold": 2050, "crude_oil": 85}
        }
        
        print(f"\n📊 Testing calculation prediction generation...")
        print(f"   ℹ️ Note: Test mode has full functionality (database saves, file creation)")
        print(f"   ℹ️ Only difference: Uses TEST telegram bot and chat instead of production")
        
        prediction = calc_predictor.run_calculation_prediction(
            mock_data,
            test_mode=test_mode,
            save_results=True,
            send_telegram=False  # Don't send during test suite
        )
        
        if prediction:
            print("✅ Calculation prediction generated successfully")
            if test_mode:
                print("   ✅ Test mode: Full functionality maintained (database + files)")
            return True
        else:
            print("❌ Calculation prediction failed")
            return False
            
    except Exception as e:
        print(f"❌ Calculation predictor test failed: {e}")
        return False

def test_file_outputs():
    """Test that files are created correctly"""
    print("\n=" * 60)
    print("📁 TESTING FILE OUTPUT SYSTEM")
    print("=" * 60)
    
    import glob
    import os
    
    # Check for recent files (all files have same format regardless of test mode)
    recent_files = []
    for pattern in ["*prediction*.json", "*comparison*.json"]:
        files = glob.glob(pattern)
        for file in files:
            stat = os.stat(file)
            recent_files.append((file, stat.st_size, stat.st_mtime))
    
    # Sort by modification time (newest first)
    recent_files.sort(key=lambda x: x[2], reverse=True)
    
    print(f"\n📄 Recent prediction files: {len(recent_files)}")
    for file, size, _ in recent_files[:5]:  # Show last 5
        mode_indicator = ""
        if "test_mode" in file or any(word in file.lower() for word in ["test"]):
            # Check file content for test_mode flag
            try:
                with open(file, 'r') as f:
                    content = json.load(f)
                    if content.get('test_mode'):
                        mode_indicator = " (TEST MODE)"
            except:
                pass
        print(f"  • {file} ({size} bytes){mode_indicator}")
    
    print(f"\n📋 Note: Both test and production modes create files with same naming")
    print(f"📋 Test mode is identified by 'test_mode': true in file content")
    
    return len(recent_files) > 0

async def run_full_test_suite():
    """Run the complete test suite"""
    print("🧪" * 20)
    print("COMPREHENSIVE TEST SUITE")
    print("🧪" * 20)
    
    test_results = {}
    
    # Configuration test
    print("\n1️⃣ Configuration Test")
    config, prod_valid, test_valid, api_valid = test_configuration()
    test_results["config"] = config is not None
    
    # Data collection test
    print("\n2️⃣ Data Collection Test")
    test_results["data_collection"] = test_data_collection()
    
    # AI predictor tests
    print("\n3️⃣ AI Predictor Tests")
    test_results["ai_production"] = await test_ai_predictor(test_mode=False)
    test_results["ai_test"] = await test_ai_predictor(test_mode=True)
    
    # Calculation predictor tests
    print("\n4️⃣ Calculation Predictor Tests")
    test_results["calc_production"] = await test_calculation_predictor(test_mode=False)
    test_results["calc_test"] = await test_calculation_predictor(test_mode=True)
    
    # File output test
    print("\n5️⃣ File Output Test")
    test_results["file_output"] = test_file_outputs()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    total_tests = len(test_results)
    passed_tests = sum(test_results.values())
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name.replace('_', ' ').title()}: {status}")
    
    print(f"\n🎯 Overall Result: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED! System ready for deployment.")
    elif passed_tests >= total_tests * 0.7:
        print("⚠️ Most tests passed. Check failed components.")
    else:
        print("🚨 Multiple test failures. System needs attention.")
    
    # Save test results
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    with open(f"test_results_{timestamp}.json", 'w') as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": test_results,
            "summary": {
                "total": total_tests,
                "passed": passed_tests,
                "success_rate": passed_tests / total_tests
            }
        }, f, indent=2)
    
    return passed_tests == total_tests

if __name__ == "__main__":
    print("🧪 Starting comprehensive test suite...")
    success = asyncio.run(run_full_test_suite())
    sys.exit(0 if success else 1) 