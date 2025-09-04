#!/usr/bin/env python3
"""
Debug script for AlphaVantage API issues
This script tests the AlphaVantage API endpoints used in the crypto prediction system
"""

import os
import requests
import json
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

def test_alphavantage_endpoint(function_name, interval="monthly", description=""):
    """Test a specific AlphaVantage endpoint"""
    api_key = os.getenv("ALPHAVANTAGE_API_KEY")
    
    if not api_key or api_key == "YOUR_ALPHAVANTAGE_API_KEY":
        print(f"❌ {function_name}: API key not configured")
        return None
    
    print(f"\n🔍 Testing {function_name} - {description}")
    print(f"   API Key: {api_key[:8]}...{api_key[-4:]}")
    
    url = "https://www.alphavantage.co/query"
    params = {
        "function": function_name,
        "interval": interval,
        "apikey": api_key
    }
    
    try:
        print(f"   URL: {url}")
        print(f"   Params: {params}")
        
        response = requests.get(url, params=params, timeout=30)
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"   Response Keys: {list(data.keys())}")
                
                # Check for error messages
                if "Error Message" in data:
                    print(f"   ❌ Error: {data['Error Message']}")
                    return None
                
                if "Note" in data:
                    print(f"   ⚠️ Note: {data['Note']}")
                
                if "Information" in data:
                    print(f"   ℹ️ Information: {data['Information']}")
                
                # Check for data structure
                if "data" in data:
                    data_array = data["data"]
                    if isinstance(data_array, list) and len(data_array) > 0:
                        print(f"   ✅ Data available: {len(data_array)} records")
                        print(f"   📅 Date range: {data_array[0].get('date', 'N/A')} to {data_array[-1].get('date', 'N/A')}")
                        print(f"   📊 Sample record: {data_array[0]}")
                        return data
                    else:
                        print(f"   ❌ Data array is empty or invalid")
                        return None
                else:
                    print(f"   ❌ No 'data' key in response")
                    print(f"   📄 Full response: {json.dumps(data, indent=2)[:500]}...")
                    return None
                    
            except json.JSONDecodeError as e:
                print(f"   ❌ JSON decode error: {e}")
                print(f"   📄 Raw response: {response.text[:500]}...")
                return None
        else:
            print(f"   ❌ HTTP error: {response.status_code}")
            print(f"   📄 Response: {response.text[:500]}...")
            return None
            
    except requests.exceptions.Timeout:
        print(f"   ❌ Request timeout")
        return None
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request error: {e}")
        return None

def test_inflation_data():
    """Test inflation data endpoint"""
    print("\n" + "="*60)
    print("📈 TESTING INFLATION DATA (CPI)")
    print("="*60)
    
    data = test_alphavantage_endpoint("CPI", "monthly", "Consumer Price Index")
    
    if data and "data" in data:
        data_array = data["data"]
        if data_array:
            # Calculate year-over-year inflation
            try:
                latest = data_array[0]
                year_ago = None
                
                # Find data from 12 months ago
                for record in data_array:
                    if record.get("date"):
                        record_date = datetime.strptime(record["date"], "%Y-%m-%d")
                        latest_date = datetime.strptime(latest["date"], "%Y-%m-%d")
                        if (latest_date - record_date).days >= 365:
                            year_ago = record
                            break
                
                if year_ago:
                    latest_cpi = float(latest["value"])
                    year_ago_cpi = float(year_ago["value"])
                    yoy_inflation = ((latest_cpi - year_ago_cpi) / year_ago_cpi) * 100
                    
                    print(f"   ✅ Inflation calculation successful:")
                    print(f"      Latest CPI: {latest_cpi} ({latest['date']})")
                    print(f"      Year ago CPI: {year_ago_cpi} ({year_ago['date']})")
                    print(f"      YoY Inflation: {yoy_inflation:.2f}%")
                else:
                    print(f"   ⚠️ Not enough historical data for YoY calculation")
            except Exception as e:
                print(f"   ❌ Inflation calculation error: {e}")
    
    return data

def test_interest_rates():
    """Test interest rates endpoints"""
    print("\n" + "="*60)
    print("💰 TESTING INTEREST RATES")
    print("="*60)
    
    # Test Fed Funds Rate
    print("\n🔍 Testing Fed Funds Rate...")
    fed_data = test_alphavantage_endpoint("FEDERAL_FUNDS_RATE", "daily", "Federal Funds Rate")
    
    # Test 10-Year Treasury Yield
    print("\n🔍 Testing 10-Year Treasury Yield...")
    treasury_data = test_alphavantage_endpoint("TREASURY_YIELD", "daily", "10-Year Treasury Yield")
    
    # Analyze results
    if fed_data and treasury_data:
        print(f"\n📊 Interest Rates Analysis:")
        
        if "data" in fed_data and fed_data["data"]:
            fed_rate = fed_data["data"][0]["value"]
            fed_date = fed_data["data"][0]["date"]
            print(f"   ✅ Fed Rate: {fed_rate}% ({fed_date})")
        else:
            print(f"   ❌ Fed Rate: No data available")
        
        if "data" in treasury_data and treasury_data["data"]:
            treasury_yield = treasury_data["data"][0]["value"]
            treasury_date = treasury_data["data"][0]["date"]
            print(f"   ✅ 10Y Treasury: {treasury_yield}% ({treasury_date})")
        else:
            print(f"   ❌ 10Y Treasury: No data available")
    
    return fed_data, treasury_data

def test_api_limits():
    """Test API rate limits and quotas"""
    print("\n" + "="*60)
    print("⏱️ TESTING API LIMITS")
    print("="*60)
    
    api_key = os.getenv("ALPHAVANTAGE_API_KEY")
    if not api_key or api_key == "YOUR_ALPHAVANTAGE_API_KEY":
        print("❌ API key not configured - cannot test limits")
        return
    
    # Test multiple rapid requests to check rate limiting
    print("🔄 Testing rapid requests...")
    
    for i in range(3):
        print(f"\n   Request {i+1}/3:")
        data = test_alphavantage_endpoint("CPI", "monthly", f"Rate limit test {i+1}")
        if data is None:
            print(f"   ⚠️ Request {i+1} failed - possible rate limiting")
        else:
            print(f"   ✅ Request {i+1} successful")

def test_alternative_endpoints():
    """Test alternative AlphaVantage endpoints that might work better"""
    print("\n" + "="*60)
    print("🔄 TESTING ALTERNATIVE ENDPOINTS")
    print("="*60)
    
    # Test different intervals
    intervals = ["monthly", "quarterly", "annual"]
    for interval in intervals:
        print(f"\n🔍 Testing CPI with {interval} interval...")
        data = test_alphavantage_endpoint("CPI", interval, f"CPI {interval}")
        if data and "data" in data and data["data"]:
            print(f"   ✅ {interval} interval works")
            break
        else:
            print(f"   ❌ {interval} interval failed")

def main():
    """Main test function"""
    print("🧪 ALPHAVANTAGE API DEBUG SCRIPT")
    print("="*60)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Load environment
    load_env()
    
    # Test API key
    api_key = os.getenv("ALPHAVANTAGE_API_KEY")
    if not api_key or api_key == "YOUR_ALPHAVANTAGE_API_KEY":
        print("\n❌ ALPHAVANTAGE_API_KEY not configured!")
        print("   Set the environment variable: ALPHAVANTAGE_API_KEY=your_key_here")
        print("   Get a free key at: https://www.alphavantage.co/support/#api-key")
        return
    
    print(f"\n✅ API Key found: {api_key[:8]}...{api_key[-4:]}")
    
    # Run tests
    try:
        # Test inflation data
        inflation_data = test_inflation_data()
        
        # Test interest rates
        fed_data, treasury_data = test_interest_rates()
        
        # Test API limits
        test_api_limits()
        
        # Test alternative endpoints
        test_alternative_endpoints()
        
        # Summary
        print("\n" + "="*60)
        print("📋 TEST SUMMARY")
        print("="*60)
        
        success_count = 0
        total_tests = 3
        
        if inflation_data and "data" in inflation_data and inflation_data["data"]:
            print("✅ Inflation data: WORKING")
            success_count += 1
        else:
            print("❌ Inflation data: FAILED")
        
        if fed_data and "data" in fed_data and fed_data["data"]:
            print("✅ Fed Funds Rate: WORKING")
            success_count += 1
        else:
            print("❌ Fed Funds Rate: FAILED")
        
        if treasury_data and "data" in treasury_data and treasury_data["data"]:
            print("✅ Treasury Yield: WORKING")
            success_count += 1
        else:
            print("❌ Treasury Yield: FAILED")
        
        print(f"\n📊 Success Rate: {success_count}/{total_tests} ({success_count/total_tests*100:.1f}%)")
        
        if success_count == 0:
            print("\n🚨 ALL TESTS FAILED - Possible issues:")
            print("   • API key invalid or expired")
            print("   • API quota exceeded")
            print("   • Network connectivity issues")
            print("   • AlphaVantage service down")
        elif success_count < total_tests:
            print(f"\n⚠️  PARTIAL FAILURE - {total_tests - success_count} endpoint(s) not working")
            print("   • Check specific endpoint errors above")
            print("   • Consider using fallback data sources")
        else:
            print("\n🎉 ALL TESTS PASSED - AlphaVantage API is working correctly!")
        
    except Exception as e:
        print(f"\n💥 CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
