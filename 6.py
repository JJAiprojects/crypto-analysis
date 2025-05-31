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
from calculation_predictor import CalculationPredictor
from database_manager import db_manager

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
            "include_social_metrics": True
        },
        "minimum_data_points": 40  # Minimum required data points
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

async def run_dual_prediction_system(test_mode=False, analysis_only=False, ai_only=False, calc_only=False):
    """Main function to run both AI and calculation prediction systems"""
    
    print("=" * 80)
    if test_mode and ai_only:
        print("🧪 CRYPTO AI PREDICTION SYSTEM TESTING - TEST MODE")
        print("⚠️  Using TEST Telegram bot and chat (AI predictor only)")
    elif test_mode and calc_only:
        print("🧪 CRYPTO CALCULATION PREDICTION SYSTEM TESTING - TEST MODE")
        print("⚠️  Using TEST Telegram bot and chat (Calculation predictor only)")
    elif test_mode:
        print("🧪 CRYPTO DUAL PREDICTION SYSTEM STARTING - TEST MODE")
        print("⚠️  Using TEST Telegram bot and chat (all other functionality identical)")
    else:
        print("🚀 CRYPTO DUAL PREDICTION SYSTEM STARTING - PRODUCTION MODE")
    print("=" * 80)
    
    try:
        # Load configuration
        config = load_config()
        
        if test_mode:
            mode_text = "🧪 AI TEST MODE" if ai_only else "🧪 TEST MODE"
            print(f"🧪 Running in {mode_text}")
            
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
        
        if not calc_only:
            print("🤖 Initializing AI Predictor...")
            ai_predictor = AIPredictor(config)
        else:
            print("⏭️  Skipping AI Predictor (Calculation-only mode)")
        
        if not ai_only:
            print("🧮 Initializing Calculation Predictor...")
            calc_predictor = CalculationPredictor(config)
        else:
            print("⏭️  Skipping Calculation Predictor (AI-only mode)")
        
        # STEP 1: Data Collection (47 data points)
        print("\n" + "=" * 60)
        print("📈 STEP 1: COLLECTING 47 DATA POINTS")
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
        
        # STEP 2: AI Prediction (12h prediction using ALL data points)
        print("\n" + "=" * 60)
        if ai_only:
            mode_text = "🧪 AI TEST MODE" if test_mode else "🚀 AI PRODUCTION MODE"
            print(f"🤖 STEP 2: AI PREDICTION SYSTEM - {mode_text}")
        elif calc_only:
            print("⏭️  STEP 2: SKIPPED - AI Predictor (Calculation-only mode)")
        else:
            mode_text = "🧪 TEST MODE" if test_mode else "🚀 PRODUCTION MODE"
            print(f"🤖 STEP 2: AI PREDICTION SYSTEM - {mode_text}")
        print("=" * 60)
        
        if not calc_only:
            print("Running AI analysis with all collected data...")
            ai_prediction = await ai_predictor.generate_prediction(all_data, test_mode)
            
            if ai_prediction:
                print("✅ AI Prediction completed successfully")
            else:
                print("❌ AI Prediction failed")
        else:
            ai_prediction = None
            print("⏭️  AI prediction skipped (Calculation-only mode)")
        
        # STEP 3: Calculation Method (Skip if ai_only mode)
        calc_prediction = None
        if not ai_only:
            print("\n" + "=" * 60)
            if calc_only:
                mode_text = "🧪 CALC TEST MODE" if test_mode else "🚀 CALC PRODUCTION MODE"
                print(f"🧮 STEP 3: CALCULATION PREDICTION SYSTEM - {mode_text}")
            else:
                mode_text = "🧪 TEST MODE" if test_mode else "🚀 PRODUCTION MODE"
                print(f"🧮 STEP 3: CALCULATION PREDICTION SYSTEM - {mode_text}")
            print("=" * 60)
            
            print("Running calculation-based analysis with identical data...")
            calc_prediction = await calc_predictor.generate_prediction(all_data, test_mode)
            
            if calc_prediction:
                print("✅ Calculation Prediction completed successfully")
            else:
                print("❌ Calculation Prediction failed")
        else:
            print("\n⏭️  STEP 3: SKIPPED - Calculation Predictor (AI-only mode)")
        
        # STEP 4: Extract and save essential prediction data
        print("\n" + "=" * 60)
        print("💾 STEP 4: EXTRACTING & SAVING TRADING SIGNALS")
        print("=" * 60)
        
        # Import the prediction extractor
        from prediction_extractor import extractor
        
        # Get current BTC price for extraction
        current_btc_price = all_data.get("crypto", {}).get("btc", 0)
        
        if current_btc_price == 0:
            print("❌ Error: BTC price not available for signal extraction")
            return False
        
        # Extract trading signals from predictions
        if ai_prediction and not calc_only:
            print("🤖 Extracting AI trading signals...")
            ai_text = ai_prediction.get("prediction", "") if isinstance(ai_prediction, dict) else str(ai_prediction)
            ai_signals = extractor.extract_from_ai_prediction(ai_text, current_btc_price)
            print(f"   Entry: ${ai_signals['entry_level']:,.2f} | SL: ${ai_signals['stop_loss']:,.2f} | TP: ${ai_signals['take_profit']:,.2f} | Confidence: {ai_signals['confidence']:.1f}%")
        else:
            ai_signals = None
            if calc_only:
                print("⏭️  AI prediction skipped (Calculation-only mode)")
            else:
                print("❌ AI prediction not available for extraction")
        
        if calc_prediction and not ai_only:
            print("🧮 Extracting calculation trading signals...")
            calc_signals = extractor.extract_from_calculation_prediction(calc_prediction, current_btc_price)
            
            # Debug information
            print(f"[DEBUG] calc_signals type: {type(calc_signals)}")
            print(f"[DEBUG] calc_signals keys: {list(calc_signals.keys()) if isinstance(calc_signals, dict) else 'Not a dict'}")
            
            if calc_signals and isinstance(calc_signals, dict) and 'entry_level' in calc_signals:
                print(f"   Entry: ${calc_signals['entry_level']:,.2f} | SL: ${calc_signals['stop_loss']:,.2f} | TP: ${calc_signals['take_profit']:,.2f} | Confidence: {calc_signals['confidence']:.1f}%")
            else:
                print(f"   ❌ Extraction failed or incomplete: {calc_signals}")
        else:
            calc_signals = None
            if ai_only:
                print("⏭️  Calculation prediction skipped (AI-only mode)")
            else:
                print("❌ Calculation prediction not available for extraction")
        
        # Save extracted signals to database
        print("\n💾 Saving prediction signals to database...")
        if ai_signals and calc_signals:
            # Save both predictions
            save_success = extractor.save_extracted_predictions(ai_signals, calc_signals, all_data, test_mode)
        elif ai_signals and ai_only:
            # Save only AI prediction in AI-only mode
            save_success = db_manager.save_simple_prediction(
                date=datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                time=datetime.now(timezone.utc).strftime('%H:%M'),
                method='ai',
                entry_level=ai_signals['entry_level'],
                stop_loss=ai_signals['stop_loss'],
                take_profit=ai_signals['take_profit'],
                confidence=ai_signals['confidence'],
                coin='BTC',
                notes=f"[{'TEST' if test_mode else 'PROD'}] BTC: ${current_btc_price:,.0f} | AI-Only Mode"
            )
            if save_success:
                print("✅ AI prediction signals saved to database")
        elif calc_signals and calc_only:
            # Validate calc_signals has all required fields
            required_fields = ['entry_level', 'stop_loss', 'take_profit', 'confidence']
            missing_fields = [field for field in required_fields if field not in calc_signals or calc_signals[field] is None]
            
            if missing_fields:
                print(f"❌ Calculation signals missing required fields: {missing_fields}")
                print(f"[DEBUG] Available fields: {list(calc_signals.keys()) if isinstance(calc_signals, dict) else 'Not a dict'}")
                save_success = False
            else:
                # Save only calculation prediction in calc-only mode
                save_success = db_manager.save_simple_prediction(
                    date=datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                    time=datetime.now(timezone.utc).strftime('%H:%M'),
                    method='calculation',
                    entry_level=calc_signals['entry_level'],
                    stop_loss=calc_signals['stop_loss'],
                    take_profit=calc_signals['take_profit'],
                    confidence=calc_signals['confidence'],
                    coin='BTC',
                    notes=f"[{'TEST' if test_mode else 'PROD'}] BTC: ${current_btc_price:,.0f} | Calc-Only Mode"
                )
                if save_success:
                    print("✅ Calculation prediction signals saved to database")
                else:
                    print("❌ Failed to save calculation prediction signals to database")
        else:
            print("❌ No valid predictions to save")
            save_success = False
        
        # Original summary saving (now optional/minimal)
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "test_mode": test_mode,
            "ai_only_mode": ai_only,
            "data_points_collected": data_count,
            "signals_extracted": {
                "ai_success": ai_signals is not None,
                "calc_success": calc_signals is not None,
                "database_saved": save_success
            }
        }
        
        # Final status
        if ai_only:
            success_count = 1 if ai_prediction else 0
            total_systems = 1
            mode_indicator = "🧪 AI TEST" if test_mode else "🚀 AI PRODUCTION"
            print(f"\n🎯 SYSTEM COMPLETION ({mode_indicator}): {success_count}/{total_systems} prediction system successful")
            
            if success_count == 1:
                print("🎉 AI PREDICTION SYSTEM COMPLETED SUCCESSFULLY!")
            else:
                print("⚠️ AI prediction system failed")
        elif calc_only:
            success_count = 1 if calc_prediction else 0
            total_systems = 1
            mode_indicator = "🧪 CALC TEST" if test_mode else "🚀 CALC PRODUCTION"
            print(f"\n🎯 SYSTEM COMPLETION ({mode_indicator}): {success_count}/{total_systems} prediction system successful")
            
            if success_count == 1:
                print("🎉 CALCULATION PREDICTION SYSTEM COMPLETED SUCCESSFULLY!")
            else:
                print("⚠️ Calculation prediction system failed")
        else:
            success_count = sum([bool(ai_prediction), bool(calc_prediction)])
            mode_indicator = "🧪 TEST" if test_mode else "🚀 PRODUCTION"
            print(f"\n🎯 SYSTEM COMPLETION ({mode_indicator}): {success_count}/2 prediction systems successful")
            
            if success_count == 2:
                print("🎉 DUAL PREDICTION SYSTEM COMPLETED SUCCESSFULLY!")
            else:
                print("⚠️ Partial completion - some prediction systems failed")
        
        return success_count > 0
        
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
    
    # Check database health
    health = db_manager.health_check()
    print(f"\n📊 Database Status:")
    print(f"   • Connection Type: {health['connection_type']}")
    print(f"   • Database Available: {health['database_available']}")
    print(f"   • Engine URL: {health.get('engine_url', 'N/A')}")
    print(f"   • Tables Exist: {health['tables_exist']}")
    print(f"   • Total Predictions: {health['total_predictions']}")
    print(f"   • Total Insights: {health['total_insights']}")
    
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
    
    # Load and show recent predictions
    try:
        predictions = db_manager.load_predictions(limit=5)
        if predictions:
            print(f"\n📈 Recent Predictions (last 5):")
            for i, pred in enumerate(predictions, 1):
                # Handle both old and new data formats
                if 'method' in pred:
                    # New simplified format
                    print(f"   {i}. {pred.get('date', 'N/A')} {pred.get('time', 'N/A')} | {pred.get('method', 'N/A').upper()}")
                    print(f"      Entry: ${pred.get('entry_level', 0):,.2f} | SL: ${pred.get('stop_loss', 0):,.2f} | TP: ${pred.get('take_profit', 0):,.2f}")
                    # Fix f-string syntax error by extracting accuracy value first
                    accuracy_display = 'Pending' if pred.get('accuracy') is None else f"{pred.get('accuracy'):.1f}%"
                    print(f"      Confidence: {pred.get('confidence', 0):.1f}% | Accuracy: {accuracy_display}")
                    print(f"      Notes: {pred.get('notes', 'N/A')[:50]}...")
                else:
                    # Legacy format
                    print(f"   {i}. Date: {pred.get('date', 'N/A')}")
                    print(f"      Time: {pred.get('time', pred.get('session', 'N/A'))}")
                    print(f"      BTC Price: ${pred.get('market_data', {}).get('btc_price', 'N/A'):,.2f}" if pred.get('market_data', {}).get('btc_price') else "      BTC Price: N/A")
                    print(f"      Has AI Prediction: {'✅' if pred.get('predictions', {}).get('ai_prediction') else '❌'}")
                print("")
        else:
            print(f"\n📈 No predictions found in storage")
            
        # Show method breakdown
        ai_predictions = db_manager.get_predictions_by_method('ai', limit=10)
        calc_predictions = db_manager.get_predictions_by_method('calculation', limit=10)
        
        print(f"\n📊 Prediction Method Breakdown:")
        print(f"   • AI Predictions: {len(ai_predictions)}")
        print(f"   • Calculation Predictions: {len(calc_predictions)}")
        
        # Show recent accuracy updates
        recent_validated = [p for p in predictions[:10] if p.get('accuracy') is not None]
        if recent_validated:
            print(f"\n✅ Recent Validated Predictions: {len(recent_validated)}")
            for pred in recent_validated[:3]:
                method = pred.get('method', 'unknown').upper()
                accuracy = pred.get('accuracy', 0)
                print(f"   • {method}: {accuracy:.1f}% accuracy")
        else:
            print(f"\n⏳ No validated predictions yet (accuracy field empty)")
            
    except Exception as e:
        print(f"\n❌ Error loading predictions: {e}")
    
    print("="*70)

def main():
    """Main entry point with command line argument support"""
    parser = argparse.ArgumentParser(description='Crypto Dual Prediction System')
    parser.add_argument('--test', action='store_true', help='Run in test mode')
    parser.add_argument('--analysis', action='store_true', help='Run analysis only (no predictions)')
    parser.add_argument('--ai-only', action='store_true', help='Run AI predictor only (skip calculation predictor)')
    parser.add_argument('--calc-only', action='store_true', help='Run calculation predictor only (skip AI predictor)')
    parser.add_argument('--inspect', action='store_true', help='Inspect data storage and exit')
    
    args = parser.parse_args()
    
    # Handle inspection first
    if args.inspect:
        inspect_data_storage()
        sys.exit(0)
    
    # Validate argument combinations
    if args.ai_only and args.analysis:
        print("❌ Error: Cannot use --ai-only with --analysis")
        sys.exit(1)
    
    if args.calc_only and args.analysis:
        print("❌ Error: Cannot use --calc-only with --analysis")
        sys.exit(1)
        
    if args.ai_only and args.calc_only:
        print("❌ Error: Cannot use --ai-only with --calc-only")
        sys.exit(1)
    
    # Run the async system
    success = asyncio.run(run_dual_prediction_system(
        test_mode=args.test, 
        analysis_only=args.analysis,
        ai_only=args.ai_only,
        calc_only=args.calc_only
    ))
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

# Flask web service for render.com deployment
if __name__ == "__main__":
    # Check if running as web service (render.com)
    if os.getenv('RENDER') or os.getenv('PORT'):
        print("🌐 Starting web service mode for render.com...")
        from flask import Flask, jsonify
        
        app = Flask(__name__)
        
        @app.route('/')
        def home():
            return jsonify({
                "status": "active",
                "service": "Crypto Dual Prediction System",
                "endpoints": ["/", "/predict", "/health"]
            })
        
        @app.route('/predict')
        def predict():
            try:
                # Run prediction system
                success = asyncio.run(run_dual_prediction_system(test_mode=False, analysis_only=False, ai_only=False))
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
        # Run as CLI application
        main() 