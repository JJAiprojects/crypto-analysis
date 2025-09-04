#!/usr/bin/env python3
"""
Test script to validate the fixes for the crypto prediction system
This script tests the main issues identified in the render logs
"""

import os
import sys
import asyncio
from datetime import datetime
from dotenv import load_dotenv

def load_env():
    """Load environment variables"""
    try:
        if os.path.exists('.env'):
            load_dotenv()
            print("[INFO] Loaded configuration from .env file")
        else:
            print("[INFO] No .env file found, using environment variables")
    except ImportError:
        print("[INFO] python-dotenv not available, using environment variables only")

def test_data_collector():
    """Test the data collector with fixes"""
    print("\n" + "="*60)
    print("🧪 TESTING DATA COLLECTOR")
    print("="*60)
    
    try:
        from data_collector import CryptoDataCollector
        
        # Load config
        config = {
            "api_keys": {
                "xai": os.getenv("XAI_API_KEY"),
                "openai": os.getenv("OPENAI_API_KEY"),
                "fred": os.getenv("FRED_API_KEY"), 
                "alphavantage": os.getenv("ALPHAVANTAGE_API_KEY")
            },
            "indicators": {
                "include_macroeconomic": True,
                "include_stock_indices": True,
                "include_commodities": True,
                "include_social_metrics": True,
                "include_enhanced_data": True
            },
            "minimum_data_points": 50
        }
        
        print("📊 Initializing Data Collector...")
        collector = CryptoDataCollector(config)
        
        print("🔍 Testing individual data collection methods...")
        
        # Test AlphaVantage endpoints
        print("\n1. Testing AlphaVantage Interest Rates...")
        interest_rates = collector.get_interest_rates()
        print(f"   Result: {interest_rates}")
        
        print("\n2. Testing AlphaVantage Inflation Data...")
        inflation_data = collector.get_inflation_data()
        print(f"   Result: {inflation_data}")
        
        # Test network health data
        print("\n3. Testing BTC Network Health...")
        btc_network = collector.get_btc_network_health()
        print(f"   Result: {btc_network}")
        
        print("\n4. Testing ETH Network Health...")
        eth_network = collector.get_eth_network_health()
        print(f"   Result: {eth_network}")
        
        # Test correlation data
        print("\n5. Testing Crypto Correlations...")
        crypto_correlations = collector.calculate_crypto_correlations()
        print(f"   Result: {crypto_correlations}")
        
        print("\n6. Testing Cross-Asset Correlations...")
        cross_asset_correlations = collector.calculate_cross_asset_correlations()
        print(f"   Result: {cross_asset_correlations}")
        
        return True
        
    except Exception as e:
        print(f"❌ Data collector test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_data_point_counting():
    """Test the data point counting logic"""
    print("\n" + "="*60)
    print("🔢 TESTING DATA POINT COUNTING")
    print("="*60)
    
    try:
        from data_collector import CryptoDataCollector
        
        # Load config
        config = {
            "api_keys": {
                "xai": os.getenv("XAI_API_KEY"),
                "openai": os.getenv("OPENAI_API_KEY"),
                "fred": os.getenv("FRED_API_KEY"), 
                "alphavantage": os.getenv("ALPHAVANTAGE_API_KEY")
            },
            "indicators": {
                "include_macroeconomic": True,
                "include_stock_indices": True,
                "include_commodities": True,
                "include_social_metrics": True,
                "include_enhanced_data": True
            },
            "minimum_data_points": 50
        }
        
        collector = CryptoDataCollector(config)
        
        print("📊 Collecting sample data...")
        sample_data = collector.collect_all_data()
        
        print("🔢 Counting data points...")
        data_count = collector._count_data_points(sample_data)
        
        print(f"   Data points collected: {data_count}")
        print(f"   Minimum required: {config['minimum_data_points']}")
        
        if data_count >= config['minimum_data_points']:
            print("   ✅ Data point count is sufficient")
            return True
        else:
            print("   ❌ Data point count is insufficient")
            return False
            
    except Exception as e:
        print(f"❌ Data point counting test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_network_health_validation():
    """Test the network health data validation"""
    print("\n" + "="*60)
    print("🔍 TESTING NETWORK HEALTH VALIDATION")
    print("="*60)
    
    try:
        from data_collector import CryptoDataCollector
        
        # Load config
        config = {
            "api_keys": {
                "xai": os.getenv("XAI_API_KEY"),
                "openai": os.getenv("OPENAI_API_KEY"),
                "fred": os.getenv("FRED_API_KEY"), 
                "alphavantage": os.getenv("ALPHAVANTAGE_API_KEY")
            },
            "indicators": {
                "include_macroeconomic": True,
                "include_stock_indices": True,
                "include_commodities": True,
                "include_social_metrics": True,
                "include_enhanced_data": True
            },
            "minimum_data_points": 50
        }
        
        collector = CryptoDataCollector(config)
        
        # Test with sample data
        sample_results = {
            'btc_network_health': {
                'hash_rate_th_s': 500000,
                'mining_difficulty': 129699156960681,
                'mempool_unconfirmed': 6207,
                'active_addresses_trend': 'stable'
            },
            'eth_network_health': {
                'gas_prices': {'safe_low_gwei': 20, 'fast_gwei': 25},
                'total_supply': {'total_eth_supply': 122373866.22}
            },
            'crypto_correlations': {
                'btc_eth_correlation_30d': 0.85,
                'btc_eth_correlation_7d': 0.92,
                'correlation_strength': 'strong',
                'correlation_direction': 'positive',
                'correlation_trend': 'increasing'
            },
            'cross_asset_correlations': {
                'market_regime': 'neutral',
                'crypto_equity_regime': 'decoupled',
                'sp500_change_24h': 0.51,
                'equity_move_significance': 'medium'
            }
        }
        
        print("🔍 Testing validation with complete data...")
        validation_issues = collector._validate_network_health_data(sample_results)
        print(f"   Validation issues: {validation_issues}")
        
        if not validation_issues:
            print("   ✅ Validation passed with complete data")
        else:
            print("   ❌ Validation failed with complete data")
        
        # Test with fallback data
        fallback_results = {
            'btc_network_health': {'fallback': True},
            'eth_network_health': {'fallback': True},
            'crypto_correlations': {'fallback': True},
            'cross_asset_correlations': {'fallback': True}
        }
        
        print("\n🔍 Testing validation with fallback data...")
        validation_issues = collector._validate_network_health_data(fallback_results)
        print(f"   Validation issues: {validation_issues}")
        
        if not validation_issues:
            print("   ✅ Validation passed with fallback data")
            return True
        else:
            print("   ❌ Validation failed with fallback data")
            return False
            
    except Exception as e:
        print(f"❌ Network health validation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_main_script():
    """Test the main script with fixes"""
    print("\n" + "="*60)
    print("🚀 TESTING MAIN SCRIPT")
    print("="*60)
    
    try:
        print("🧪 Running main script in analysis mode...")
        
        # Import and run the main function
        import subprocess
        result = subprocess.run([
            sys.executable, "6.py", "--analysis"
        ], capture_output=True, text=True, timeout=300)
        
        print(f"   Return code: {result.returncode}")
        print(f"   stdout: {result.stdout[-500:]}")  # Last 500 chars
        if result.stderr:
            print(f"   stderr: {result.stderr[-500:]}")  # Last 500 chars
        
        if result.returncode == 0:
            print("   ✅ Main script completed successfully")
            return True
        else:
            print("   ❌ Main script failed")
            return False
            
    except subprocess.TimeoutExpired:
        print("   ❌ Main script timed out")
        return False
    except Exception as e:
        print(f"❌ Main script test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("🧪 CRYPTO PREDICTION SYSTEM FIXES TEST")
    print("="*60)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Load environment
    load_env()
    
    # Run tests
    test_results = []
    
    try:
        # Test 1: Data Collector
        print("\n🔍 Test 1: Data Collector")
        result1 = test_data_collector()
        test_results.append(("Data Collector", result1))
        
        # Test 2: Data Point Counting
        print("\n🔍 Test 2: Data Point Counting")
        result2 = test_data_point_counting()
        test_results.append(("Data Point Counting", result2))
        
        # Test 3: Network Health Validation
        print("\n🔍 Test 3: Network Health Validation")
        result3 = test_network_health_validation()
        test_results.append(("Network Health Validation", result3))
        
        # Test 4: Main Script
        print("\n🔍 Test 4: Main Script")
        result4 = test_main_script()
        test_results.append(("Main Script", result4))
        
        # Summary
        print("\n" + "="*60)
        print("📋 TEST SUMMARY")
        print("="*60)
        
        passed_tests = 0
        total_tests = len(test_results)
        
        for test_name, result in test_results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"   {test_name}: {status}")
            if result:
                passed_tests += 1
        
        print(f"\n📊 Overall Result: {passed_tests}/{total_tests} tests passed ({passed_tests/total_tests*100:.1f}%)")
        
        if passed_tests == total_tests:
            print("\n🎉 ALL TESTS PASSED - Fixes are working correctly!")
            return True
        else:
            print(f"\n⚠️  {total_tests - passed_tests} test(s) failed - some fixes may need adjustment")
            return False
        
    except Exception as e:
        print(f"\n💥 CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
