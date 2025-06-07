#!/usr/bin/env python3

import json
import os
import sys
import argparse
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv
from data_collector import CryptoDataCollector
from ai_predictor import AIPredictor
# Calculation predictor removed - AI predictor is more accurate
# Database manager removed - using file-based storage only

def load_config():
    """Load configuration with proper handling of both .env files and environment variables"""
    
    # Try to load .env file (for local development)
    try:
        if os.path.exists('.env'):
            load_dotenv()
            print("[INFO] Loaded configuration from .env file")
        else:
            print("[INFO] No .env file found, using environment variables")
    except ImportError:
        print("[INFO] python-dotenv not available, using environment variables only")
    
    config = {
        "api_keys": {
            "openai": os.getenv("OPENAI_API_KEY"),
            "fred": os.getenv("FRED_API_KEY"), 
            "alphavantage": os.getenv("ALPHAVANTAGE_API_KEY")
        },
        "telegram": {
            "enabled": True,
            "bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
            "chat_id": os.getenv("TELEGRAM_CHAT_ID"),
            "test": {
                "enabled": True,
                "bot_token": os.getenv("TEST_TELEGRAM_BOT_TOKEN"),
                "chat_id": os.getenv("TEST_TELEGRAM_CHAT_ID")
            }
        },
        "storage": {
            "file": "crypto_data_history.csv",
            "database": "crypto_predictions.db"
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
            "include_social_metrics": True,
            "include_enhanced_data": True
        },
        "minimum_data_points": 46  # Updated from 45 to 46 (minimum required data points for enhanced data)
    }
    
    # Load existing config.json if available (for additional settings)
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r") as f:
                existing_config = json.load(f)
                # Only merge non-sensitive configuration (not API keys or tokens)
                for key, value in existing_config.items():
                    if key not in ["api_keys", "telegram"]:
                        if isinstance(value, dict) and isinstance(config.get(key), dict):
                            config[key].update(value)
                        else:
                            config[key] = value
        except Exception as e:
            print(f"[ERROR] Loading config.json: {e}")
    
    # Validate critical configuration
    missing_keys = []
    if not config["api_keys"]["openai"]:
        missing_keys.append("OPENAI_API_KEY")
    if not config["telegram"]["bot_token"]:
        missing_keys.append("TELEGRAM_BOT_TOKEN") 
    if not config["telegram"]["chat_id"]:
        missing_keys.append("TELEGRAM_CHAT_ID")
    
    if missing_keys:
        print(f"[WARNING] Missing required environment variables: {', '.join(missing_keys)}")
        print("[WARNING] Some functionality may be limited")
    
    return config

def count_data_points(data):
    """Count the number of valid data points collected - ACCURATE COUNT (matches data_collector.py)"""
    count = 0
    
    # 1. Crypto Prices (2 points)
    crypto = data.get("crypto", {})
    if crypto.get("btc"): count += 1
    if crypto.get("eth"): count += 1
    
    # 2. Technical Indicators (12 points: 6 per coin)
    tech = data.get("technical_indicators", {})
    for coin in ["BTC", "ETH"]:
        coin_data = tech.get(coin, {})
        if coin_data:
            # Count individual technical indicators
            if coin_data.get('rsi14') is not None: count += 1
            if coin_data.get('signal'): count += 1
            if coin_data.get('support') is not None: count += 1
            if coin_data.get('resistance') is not None: count += 1
            if coin_data.get('trend'): count += 1
            if coin_data.get('volatility'): count += 1
    
    # 3. Futures Sentiment (8 points: 4 per coin)
    futures = data.get("futures", {})
    for coin in ["BTC", "ETH"]:
        coin_data = futures.get(coin, {})
        if coin_data:
            if coin_data.get('funding_rate') is not None: count += 1
            if coin_data.get('long_ratio') is not None: count += 1
            if coin_data.get('short_ratio') is not None: count += 1
            if coin_data.get('open_interest') is not None: count += 1
    
    # 4. Market Sentiment (3 points)
    if data.get("fear_greed", {}).get("index"): count += 1
    if data.get("btc_dominance"): count += 1
    if data.get("market_cap"): count += 1
    
    # 5. Trading Volumes (2 points)
    volumes = data.get("volumes", {})
    if volumes.get("btc_volume"): count += 1
    if volumes.get("eth_volume"): count += 1
    
    # 6. Macroeconomic Data (4 points)
    if data.get("m2_supply", {}).get("m2_supply"): count += 1
    if data.get("inflation", {}).get("inflation_rate") is not None: count += 1
    rates = data.get("interest_rates", {})
    if rates.get("fed_rate") is not None: count += 1
    if rates.get("t10_yield") is not None: count += 1
    
    # 7. Stock Indices (4 points)
    indices = data.get("stock_indices", {})
    for key in ["sp500", "nasdaq", "dow_jones", "vix"]:
        if indices.get(key) is not None: count += 1
    
    # 8. Commodities (4 points)
    commodities = data.get("commodities", {})
    for key in ["gold", "silver", "crude_oil", "natural_gas"]:
        if commodities.get(key) is not None: count += 1
    
    # 9. Social Metrics (6 points)
    social = data.get("social_metrics", {})
    if social.get("forum_posts"): count += 1
    if social.get("forum_topics"): count += 1
    if social.get("btc_github_stars"): count += 1
    if social.get("eth_github_stars"): count += 1
    if social.get("btc_recent_commits"): count += 1
    if social.get("eth_recent_commits"): count += 1
    
    # 10. Historical Data (2 points)
    historical = data.get("historical_data", {})
    if historical.get("BTC"): count += 1
    if historical.get("ETH"): count += 1
    
    # 11. Volatility Regime (1 point: market-wide) - NEW
    if data.get("volatility_regime"): count += 1
    
    # 12. NEW ENHANCED DATA SOURCES (9 points)
    if data.get("order_book_analysis"): count += 1
    if data.get("liquidation_heatmap"): count += 1
    if data.get("economic_calendar"): count += 1
    if data.get("multi_source_sentiment"): count += 1
    if data.get("whale_movements"): count += 1
    
    return count

def send_telegram_notification(message, bot_token, chat_id):
    """Send telegram notification using requests directly"""
    try:
        import requests
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        response = requests.post(url, json=payload, timeout=30)
        result = response.json()
        
        if response.status_code == 200 and result.get("ok"):
            print("[INFO] Telegram notification sent successfully")
            return True
        else:
            print(f"[ERROR] Telegram API error: {result.get('description', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"[ERROR] Failed to send telegram notification: {e}")
        return False

async def run_ai_prediction_system(test_mode=False, analysis_only=False):
    """Main function to run AI prediction system (calculation predictor removed)"""
    
    print("=" * 80)
    if test_mode:
        print("🧪 CRYPTO AI PREDICTION SYSTEM TESTING - TEST MODE")
        print("⚠️  Using TEST Telegram bot and chat")
    else:
        print("🚀 CRYPTO AI PREDICTION SYSTEM STARTING - PRODUCTION MODE")
    print("=" * 80)
    
    try:
        # Load configuration
        config = load_config()
        
        if test_mode:
            print("🧪 Running in AI TEST MODE")
            
            # Validate test configuration
            test_config = config["telegram"]["test"]
            if not test_config.get("bot_token"):
                print("⚠️ [WARNING] Test Telegram bot token not configured!")
                print("   Set TEST_TELEGRAM_BOT_TOKEN environment variable")
            if not test_config.get("chat_id"):
                print("⚠️ [WARNING] Test Telegram chat ID not configured!")
                print("   Set TEST_TELEGRAM_CHAT_ID environment variable")
        else:
            # Validate production configuration
            if not config["telegram"].get("bot_token"):
                print("⚠️ [WARNING] Production Telegram bot token not configured!")
            if not config["telegram"].get("chat_id"):
                print("⚠️ [WARNING] Production Telegram chat ID not configured!")
        
        # Initialize components
        print("\n📊 Initializing Data Collector...")
        data_collector = CryptoDataCollector(config)
        
        print("🤖 Initializing AI Predictor...")
        ai_predictor = AIPredictor(config)
        
        # STEP 1: Data Collection (54 data points) - Updated from 52
        print("\n" + "=" * 60)
        print("📈 STEP 1: COLLECTING 54 DATA POINTS")  # Updated from 52
        print("=" * 60)
        
        print("Gathering comprehensive market data...")
        all_data = data_collector.collect_all_data()
        
        # Validate data completeness
        data_count = count_data_points(all_data)
        print(f"\n✅ Data Collection Complete: {data_count} data points collected")
        
        if data_count < config["minimum_data_points"]:
            error_msg = f"⚠️ Insufficient data: Only {data_count}/{config['minimum_data_points']} minimum data points collected"
            print(error_msg)
            
            # Send critical error notification
            if config["telegram"]["enabled"] and not analysis_only:
                telegram_config = config["telegram"]["test"] if test_mode else config["telegram"]
                mode_prefix = "🧪 [TEST] " if test_mode else ""
                send_telegram_notification(
                    f"{mode_prefix}🚨 CRYPTO PREDICTION SYSTEM ERROR\n\n{error_msg}\n\nSystem halted.",
                    telegram_config["bot_token"],
                    telegram_config["chat_id"]
                )
            return False
        
        if analysis_only:
            print("\n📋 Analysis Mode - Data collection completed")
            print(f"Available data points: {data_count}")
            print("\nData breakdown:")
            for category, data in all_data.items():
                if isinstance(data, dict):
                    valid_items = sum(1 for v in data.values() if v is not None)
                    print(f"  {category}: {valid_items} items")
            return True
        
        # STEP 2: AI Prediction (using ALL data points)
        print("\n" + "=" * 60)
        mode_text = "🧪 TEST MODE" if test_mode else "🚀 PRODUCTION MODE"
        print(f"🤖 STEP 2: AI PREDICTION SYSTEM - {mode_text}")
        print("=" * 60)
        
        print("Running AI analysis with all collected data...")
        ai_prediction = await ai_predictor.generate_prediction(all_data, test_mode)
        
        if ai_prediction:
            print("✅ AI Prediction completed successfully")
        else:
            print("❌ AI Prediction failed")
        
        # STEP 3: Single AI prediction completed (calculation predictor removed)
        
        # STEP 3: Extract and save essential prediction data
        print("\n" + "=" * 60)
        print("💾 STEP 3: EXTRACTING & SAVING TRADING SIGNALS")
        print("=" * 60)
        
        if ai_prediction:
            print("🤖 AI prediction completed successfully!")
            print("📊 Single Telegram message will be sent with AI analysis")
        else:
            print("❌ AI prediction failed - no telegram message will be sent")
            return False
        
        # Final summary
        print("\n🎉 AI PREDICTION SYSTEM COMPLETED SUCCESSFULLY!")
        return True
        
    except Exception as e:
        error_msg = f"💥 CRITICAL ERROR in prediction system: {str(e)}"
        print(error_msg)
        
        # Send error notification
        try:
            if config["telegram"]["enabled"] and not analysis_only:
                telegram_config = config["telegram"]["test"] if test_mode else config["telegram"]
                mode_prefix = "🧪 [TEST] " if test_mode else ""
                send_telegram_notification(
                    f"{mode_prefix}🚨 CRYPTO PREDICTION SYSTEM CRITICAL ERROR\n\n{error_msg}",
                    telegram_config["bot_token"],
                    telegram_config["chat_id"]
                )
        except Exception as telegram_error:
            print(f"Failed to send error notification: {telegram_error}")
        
        return False

def inspect_data_storage():
    """Inspect where and how data is stored"""
    print("\n" + "="*70)
    print(" 🔍 DATA STORAGE INSPECTION")
    print("="*70)
    
    # Database removed - using file-based storage only
    print(f"\n📊 Storage Status:")
    print(f"   • Storage Type: File-based (SQLite removed)")
    print(f"   • Database Removed: Using simple file storage")
    
    # Check local files
    print(f"\n📁 Local File Status:")
    files_to_check = [
        'crypto_predictions.db',
        'detailed_predictions.json',
        'deep_learning_insights.json',
        'market_data.json'
    ]
    
    for filename in files_to_check:
        if os.path.exists(filename):
            size = os.path.getsize(filename)
            print(f"   ✅ {filename}: {size:,} bytes")
        else:
            print(f"   ❌ {filename}: Not found")
    
    # Database functionality removed - now using simple file storage
    print(f"\n📈 Storage: Simple file-based system (no database queries)")
    print(f"   • AI predictions saved to files only")
    print(f"   • Database complexity removed for simplicity")
    
    print("="*70)

def main():
    """Main entry point with command line argument support"""
    parser = argparse.ArgumentParser(description='Crypto AI Prediction System')
    parser.add_argument('--test', action='store_true', help='Run in test mode')
    parser.add_argument('--analysis', action='store_true', help='Run analysis only (no predictions)')
    parser.add_argument('--inspect', action='store_true', help='Inspect data storage and exit')
    
    args = parser.parse_args()
    
    # Handle inspection first
    if args.inspect:
        inspect_data_storage()
        sys.exit(0)
        
    # Run the async system
    success = asyncio.run(run_ai_prediction_system(
        test_mode=args.test, 
        analysis_only=args.analysis
    ))
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

# Flask web service for render.com deployment
if __name__ == "__main__":
    # Check if running as web service (render.com)
    # Only start Flask if PORT is set (web service), not just RENDER (which is set for cron jobs too)
    if os.getenv('PORT') and not os.getenv('IS_CRON_JOB'):
        print("🌐 Starting web service mode for render.com...")
        from flask import Flask, jsonify
        
        app = Flask(__name__)
        
        @app.route('/')
        def home():
            return jsonify({
                "status": "active",
                "service": "Crypto AI Prediction System",
                "endpoints": ["/", "/predict", "/health"]
            })
        
        @app.route('/predict')
        def predict():
            try:
                # Run prediction system
                success = asyncio.run(run_ai_prediction_system(test_mode=False, analysis_only=False))
                return jsonify({
                    "status": "completed" if success else "failed",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }), 500
        
        @app.route('/health')
        def health():
            return jsonify({"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()})
        
        # Run Flask app
        port = int(os.getenv('PORT', 5000))
        app.run(host='0.0.0.0', port=port)
    else:
        # Run as CLI application (includes cron jobs)
        print("🕐 Running as scheduled cron job..." if os.getenv('RENDER') else "💻 Running as CLI application...")
        main()