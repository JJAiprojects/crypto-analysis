#!/usr/bin/env python3

import requests
import json
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
import os
import re
from ml_enhancer import PredictionEnhancer
from risk_manager import RiskManager
from professional_analysis import ProfessionalTraderAnalysis
from dotenv import load_dotenv

# Import database manager
try:
    from database_manager import db_manager
    DATABASE_AVAILABLE = True
    print("[INFO] Database manager loaded successfully")
except ImportError:
    print("[WARN] Database manager not available, using JSON files only")
    DATABASE_AVAILABLE = False

def load_telegram_config():
    """Load Telegram configuration from environment variables or config file"""
    # Try environment variables first
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if bot_token and chat_id:
        print("[INFO] Using Telegram credentials from environment variables")
        return {
            "bot_token": bot_token,
            "chat_id": chat_id,
            "enabled": True
        }
    
    # Fall back to config file
    config_file = "telegram_config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
            if config.get("enabled") and config.get("bot_token") != "YOUR_BOT_TOKEN":
                print("[INFO] Using Telegram credentials from config file")
                return config
        except Exception as e:
            print(f"[ERROR] Loading telegram config: {e}")
    
    print("[WARN] Telegram notifications not configured - will not send alerts")
    return {"enabled": False, "bot_token": "", "chat_id": ""}

def send_telegram_message(message, is_test=False):
    """Send a message to Telegram with proper bot selection"""
    config = load_config()
    
    # Select appropriate bot token and chat ID
    if is_test and config["test_mode"]["enabled"]:
        bot_token = config["telegram"]["test"]["bot_token"]
        chat_id = config["telegram"]["test"]["chat_id"]
        print("[TEST] Using test Telegram bot")
    else:
        bot_token = config["telegram"]["bot_token"]
        chat_id = config["telegram"]["chat_id"]
    
    if not bot_token or not chat_id:
        print("[WARN] Telegram credentials not configured")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        response = requests.post(url, data=payload, timeout=10)
        
        # Handle parsing errors by falling back to plain text
        if response.status_code == 400 and "can't parse entities" in response.text.lower():
            print("[WARN] HTML parsing failed, sending as plain text")
            payload["parse_mode"] = None
            # Remove HTML tags for plain text
            plain_message = re.sub(r'<[^>]+>', '', message)
            payload["text"] = plain_message
            response = requests.post(url, data=payload, timeout=10)
        
        response.raise_for_status()
        print("[INFO] Telegram validation message sent successfully")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram message: {e}")
        return False

def is_duplicate_validation_point(validation_points, new_point):
    """Check if a validation point is already in the list"""
    for point in validation_points:
        if (point["coin"] == new_point["coin"] and 
            point["type"] == new_point["type"] and
            point.get("predicted_level") == new_point.get("predicted_level")):
                return True
    return False

def get_crypto_prices():
    """Get current cryptocurrency prices with multiple fallbacks"""
    # Try multiple API endpoints
    apis = [
        {
            "name": "CoinGecko",
            "url": "https://api.coingecko.com/api/v3/simple/price",
            "params": {"ids": "bitcoin,ethereum", "vs_currencies": "usd"},
            "extract": lambda data: {
                "btc": data.get("bitcoin", {}).get("usd"),
                "eth": data.get("ethereum", {}).get("usd")
            }
        },
        {
            "name": "Binance",
            "url": "https://api.binance.com/api/v3/ticker/price",
            "params": {},
            "extract": lambda data: {
                "btc": next((float(item["price"]) for item in data if item["symbol"] == "BTCUSDT"), None),
                "eth": next((float(item["price"]) for item in data if item["symbol"] == "ETHUSDT"), None)
            }
        }
    ]
    
    errors = []
    
    # Try each API in order
    for api in apis:
        try:
            print(f"[INFO] Trying to get prices from {api['name']}...")
            if api["name"] == "Binance":
                # For Binance, get both symbols in one call
                response = requests.get("https://api.binance.com/api/v3/ticker/price", timeout=10)
            else:
                response = requests.get(api["url"], params=api["params"], timeout=10)
            
            response.raise_for_status()
            data = response.json()
            
            # Extract prices using the provided extract function
            prices = api["extract"](data)
            
            # Validate that both prices were retrieved
            if prices["btc"] is not None and prices["eth"] is not None:
                print(f"[INFO] Successfully retrieved prices from {api['name']}")
                print(f"[INFO] Current prices: BTC=${prices['btc']:,.2f}, ETH=${prices['eth']:,.2f}")
                return prices
            else:
                errors.append(f"{api['name']}: Missing price data")
        except Exception as e:
            errors.append(f"{api['name']}: {str(e)}")
            print(f"[WARN] Failed to get prices from {api['name']}: {e}")
    
    # If all APIs fail, try to use latest saved prices
    try:
        prediction_file = "detailed_predictions.json"
        if os.path.exists(prediction_file):
            with open(prediction_file, "r") as f:
                predictions = json.load(f)
                if predictions and len(predictions) > 0:
                    latest = predictions[-1]
                    if "market_data" in latest:
                        btc_price = latest["market_data"].get("btc_price")
                        eth_price = latest["market_data"].get("eth_price")
                        if btc_price is not None and eth_price is not None:
                            print("[INFO] Using latest saved prices as fallback")
                            return {"btc": btc_price, "eth": eth_price}
    except Exception as e:
        errors.append(f"Fallback: {str(e)}")
    
    # All methods failed
    raise Exception(f"Failed to get cryptocurrency prices from all sources. Errors: {errors}")

def is_fresh_prediction(prediction_time):
    """Check if a prediction is from the most recent cycle (8am/8pm)"""
    now = datetime.now()
    
    # Get the most recent 8am or 8pm timestamp
    current_hour = now.hour
    if 8 <= current_hour < 20:
        # Last prediction window was at 8am today
        last_window = datetime(now.year, now.month, now.day, 8, 0, 0)
    else:
        # If it's before 8am, the last window was 8pm yesterday
        if current_hour < 8:
            yesterday = now - timedelta(days=1)
            last_window = datetime(yesterday.year, yesterday.month, yesterday.day, 20, 0, 0)
        else:
            # If it's after 8pm, the last window was 8pm today
            last_window = datetime(now.year, now.month, now.day, 20, 0, 0)
    
    # Get the previous window too (to account for slight timing differences)
    previous_window = last_window - timedelta(hours=12)
    
    # Check if the prediction is from the most recent window (with a buffer)
    time_diff = now - prediction_time
    
    # Consider it fresh if it's from the current or previous window (within 16 hours)
    return time_diff.total_seconds() < 16 * 3600

def load_config():
    """Load configuration with proper handling of sensitive data"""
    # Load environment variables - try .env file first (local), then system env vars (Render)
    if os.path.exists('.env'):
        try:
            load_dotenv()
            print("[INFO] Loaded .env file for local development")
        except Exception as e:
            print(f"[WARN] .env file exists but failed to load: {e}")
    else:
        print("[INFO] No .env file found - using system environment variables (cloud deployment mode)")
    
    # Verify telegram credentials
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat = os.getenv("TELEGRAM_CHAT_ID")
    
    if telegram_token and telegram_chat:
        print("[INFO] ✓ Telegram credentials available")
    else:
        print("[WARN] ✗ Telegram credentials not configured")
    
    default_config = {
        "telegram": {
            "enabled": True,
            "bot_token": telegram_token,
            "chat_id": telegram_chat,
            "test": {
                "bot_token": os.getenv("TEST_TELEGRAM_BOT_TOKEN", ""),
                "chat_id": os.getenv("TEST_TELEGRAM_CHAT_ID", "")
            }
        },
        "test_mode": {
            "enabled": False,
            "send_telegram": False,
            "output_prefix": "test_"
        }
    }
    
    # Load non-sensitive config from config.json
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config
        except Exception as e:
            print(f"[ERROR] Loading config: {e}")
    return default_config

def validate_predictions():
    """Enhanced validation with ML learning and professional analysis integration"""
    # Log times in different timezones
    server_time = datetime.now()
    utc_time = datetime.now(timezone.utc)
    print(f"[INFO] UTC time: {utc_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[INFO] Server time: {server_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[INFO] Expected Vietnam time: {(utc_time + timedelta(hours=7)).strftime('%Y-%m-%d %H:%M:%S')}")
    

    # Load config
    config = load_config()
    
    if config["test_mode"]["enabled"]:
        print("[TEST] Running validation in test mode")
    
    # Use test file if in test mode
    prediction_file = "detailed_predictions.json"
    if config["test_mode"]["enabled"]:
        prediction_file = config["test_mode"]["output_prefix"] + prediction_file
        print(f"[TEST] Using test prediction file: {prediction_file}")
    
    # Load predictions from database or JSON file
    predictions = []
    if DATABASE_AVAILABLE:
        try:
            predictions = db_manager.load_predictions()
            if predictions:
                print(f"[INFO] Loaded {len(predictions)} predictions from database")
            else:
                print("[INFO] No predictions found in database")
        except Exception as e:
            print(f"[ERROR] Failed to load predictions from database: {e}")
            # Fall back to JSON file
    
    # Fallback to JSON file if database failed or not available
    if not predictions:
        if not os.path.exists(prediction_file):
            print("[INFO] No predictions to validate yet")
            return
        
        try:
            with open(prediction_file, "r") as f:
                predictions = json.load(f)
                print(f"[INFO] Loaded {len(predictions)} predictions from JSON file")
        except Exception as e:
            print(f"[ERROR] Failed to load predictions from JSON: {e}")
            return
    
    if not predictions:
        print("[INFO] No predictions to validate")
        return
    
    # Initialize components
    ml_enhancer = PredictionEnhancer()
    risk_manager = RiskManager()
    professional_trader = ProfessionalTraderAnalysis()
    
    # Get current prices
    prices = get_crypto_prices()
    
    # Track notifications and improvements
    notifications = []
    ml_training_data = []
    
    # Get the latest prediction for detailed tracking
    latest_prediction = predictions[-1] if predictions else None
    
    # Process all unvalidated predictions
    for pred in predictions:
        # Handle both timestamp formats (ISO and space-separated)
        timestamp_str = pred["timestamp"]
        if 'T' in timestamp_str:
            # ISO format from database: '2025-05-24T10:12:01'
            pred_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', ''))
        else:
            # Space format from JSON: '2025-05-24 10:12:01'
            pred_timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        
        # Skip very recent predictions (less than 1 hour old)
        if (datetime.now() - pred_timestamp).total_seconds() < 3600:
            continue
        
        # Initialize validation points if not exists
        if "validation_points" not in pred:
            pred["validation_points"] = []
        
        # Extract professional analysis predictions
        ai_pred = pred.get("predictions", {}).get("ai_prediction", "")
        pro_analysis = pred.get("predictions", {}).get("professional_analysis", {})
        ml_pred = pred.get("predictions", {}).get("ml_predictions", {})
        
        # Enhanced target extraction for professional format
        if pro_analysis and "price_targets" in pro_analysis:
            btc_targets = {
                "current": pro_analysis["price_targets"].get("current"),
                "target_1": pro_analysis["price_targets"].get("target_1"),
                "target_2": pro_analysis["price_targets"].get("target_2"),
                "stop_loss": pro_analysis["price_targets"].get("stop_loss"),
                "scenario": pro_analysis.get("primary_scenario", "NEUTRAL")
            }
            
            # Validate BTC targets
            validate_professional_targets(pred, "BTC", btc_targets, prices["btc"], latest_prediction == pred, notifications)
        
        # Also validate any AI predictions (fallback/additional)
        targets = extract_professional_targets(ai_pred)
        for coin in ["BTC", "ETH"]:
            if targets[coin]:
                price = prices[coin.lower()]
                validate_legacy_targets(pred, coin, targets[coin], price, latest_prediction == pred, notifications)
        
        # Collect ML training data
        if not pred.get("ml_processed", False):
            training_point = {
                "prediction_data": pred,
                "actual_btc_price": prices["btc"],
                "actual_eth_price": prices["eth"],
                "validation_points": pred["validation_points"],
                "timestamp": datetime.now().isoformat()
            }
            ml_training_data.append(training_point)
            pred["ml_processed"] = True
        
        # Mark as validated
        if not pred.get("hourly_validated"):
            pred["hourly_validated"] = True
            pred["last_validation"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Save updated predictions (database or JSON)
    if DATABASE_AVAILABLE:
        try:
            # Update predictions in database
            for pred in predictions:
                if pred.get("hourly_validated") and pred.get("validation_points"):
                    db_manager.update_prediction_validation(
                        pred["timestamp"], 
                        pred["validation_points"], 
                        pred.get("final_accuracy")
                    )
            print("[INFO] Updated predictions in database")
        except Exception as e:
            print(f"[ERROR] Failed to update database: {e}")
    else:
        # Save to JSON file
        try:
            with open(prediction_file, "w") as f:
                json.dump(predictions, f, indent=4)
            print("[INFO] Updated predictions in JSON file")
        except Exception as e:
            print(f"[ERROR] Failed to save predictions to JSON: {e}")
    
    # Train ML models with new data
    if ml_training_data:
        print(f"[INFO] Training ML models with {len(ml_training_data)} new data points")
        try:
            ml_enhancer.incremental_learning(ml_training_data)
            print("[INFO] ML incremental learning completed")
        except Exception as e:
            print(f"[ERROR] ML training failed: {e}")
    
    # Send notifications for latest prediction
    if notifications:
        print(f"[INFO] Sending {len(notifications)} validation notifications")
        for notification in notifications[-3:]:  # Limit to last 3 notifications
            message = format_notification_message(notification)
            send_telegram_message(message, is_test=config["test_mode"]["enabled"])
    
    # Check if it's time for accuracy report (7:45 PM and 7:45 AM)
    current_hour = datetime.now().hour
    current_minute = datetime.now().minute
    
    # Send accuracy report at 7:45 PM (19:45) for 8 AM predictions
    # Send accuracy report at 7:45 AM (07:45) for 8 PM predictions from previous day
    if (current_hour == 19 and 45 <= current_minute <= 59) or (current_hour == 7 and 45 <= current_minute <= 59):
        if current_hour == 19:
            report_type = "8 AM predictions"
        else:
            report_type = "8 PM predictions (previous day)"
        
        print(f"[INFO] Generating daily accuracy report for {report_type}")
        accuracy_metrics = calculate_enhanced_accuracy(predictions)
        accuracy_message = format_accuracy_summary(accuracy_metrics)
        send_telegram_message(accuracy_message, is_test=config["test_mode"]["enabled"])
        
        # Also send improvement suggestions to AI
        improvement_data = generate_improvement_suggestions(accuracy_metrics, predictions)
        save_improvement_data(improvement_data)
    
    # Weekly Deep Learning Analysis - Every Sunday at 8 PM
    current_weekday = datetime.now().weekday()  # 6 = Sunday
    if current_weekday == 6 and current_hour == 20 and 0 <= current_minute <= 15:
        print("[INFO] Generating weekly deep learning analysis...")
        weekly_insights = generate_deep_learning_insights(predictions, "weekly")
        save_deep_learning_insights(weekly_insights)
        
        # Send comprehensive weekly report
        weekly_report = format_deep_insights_summary(weekly_insights)
        send_telegram_message(weekly_report, is_test=config["test_mode"]["enabled"])
        print("[INFO] Weekly deep learning analysis completed")
    
    # Monthly Deep Learning Analysis - Every 1st of month at 8 PM
    current_day = datetime.now().day
    if current_day == 1 and current_hour == 20 and 0 <= current_minute <= 15:
        print("[INFO] Generating monthly deep learning analysis...")
        monthly_insights = generate_deep_learning_insights(predictions, "monthly")
        save_deep_learning_insights(monthly_insights)
        
        # Send comprehensive monthly report
        monthly_report = format_deep_insights_summary(monthly_insights)
        send_telegram_message(monthly_report, is_test=config["test_mode"]["enabled"])
        print("[INFO] Monthly deep learning analysis completed")
        
        # Also trigger ML model retraining with insights
        try:
            ml_enhancer.learn_from_insights(monthly_insights)
            print("[INFO] ML models updated with monthly insights")
        except Exception as e:
            print(f"[ERROR] Failed to update ML models with insights: {e}")
    
    print("[INFO] Enhanced prediction validation completed successfully")

def validate_professional_targets(prediction, coin, targets, current_price, is_latest, notifications):
    """Validate professional analysis targets"""
    if not targets or not current_price:
        return
    
    scenario = targets.get("scenario", "NEUTRAL")
    
    # Check target 1
    if targets.get("target_1") and validate_target_hit(current_price, targets["target_1"], "TARGET_1", scenario):
        validation_point = {
            "coin": coin,
            "type": "PROFESSIONAL_TARGET_1",
            "predicted_level": targets["target_1"],
            "actual_price": current_price,
            "scenario": scenario,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if not is_duplicate_validation_point(prediction.get("validation_points", []), validation_point):
            prediction.setdefault("validation_points", []).append(validation_point)
            
            if is_latest:
                notifications.append({
                    "type": "professional_target",
                    "coin": coin,
                    "target_level": targets["target_1"],
                    "current_price": current_price,
                    "scenario": scenario,
                    "target_number": 1
                })
    
    # Check target 2
    if targets.get("target_2") and validate_target_hit(current_price, targets["target_2"], "TARGET_2", scenario):
        validation_point = {
            "coin": coin,
            "type": "PROFESSIONAL_TARGET_2", 
            "predicted_level": targets["target_2"],
            "actual_price": current_price,
            "scenario": scenario,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if not is_duplicate_validation_point(prediction.get("validation_points", []), validation_point):
            prediction.setdefault("validation_points", []).append(validation_point)
            
            if is_latest:
                notifications.append({
                    "type": "professional_target",
                    "coin": coin,
                    "target_level": targets["target_2"],
                    "current_price": current_price,
                    "scenario": scenario,
                    "target_number": 2
                })
    
    # Check stop loss
    if targets.get("stop_loss") and validate_target_hit(current_price, targets["stop_loss"], "STOP_LOSS", scenario):
        validation_point = {
            "coin": coin,
            "type": "PROFESSIONAL_STOP_LOSS",
            "predicted_level": targets["stop_loss"],
            "actual_price": current_price,
            "scenario": scenario,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if not is_duplicate_validation_point(prediction.get("validation_points", []), validation_point):
            prediction.setdefault("validation_points", []).append(validation_point)
            
            if is_latest:
                notifications.append({
                    "type": "professional_stop_loss",
                    "coin": coin,
                    "stop_level": targets["stop_loss"],
                    "current_price": current_price,
                    "scenario": scenario
                })

def validate_legacy_targets(prediction, coin, targets, current_price, is_latest, notifications):
    """Validate legacy AI prediction format targets"""
    # Implementation for backward compatibility with older prediction formats
    pass

def calculate_enhanced_accuracy(predictions):
    """Calculate enhanced accuracy metrics with detailed insights for faster learning"""
    metrics = {
        "total_predictions": len(predictions),
        "validated_predictions": 0,
        
        # Core Performance Metrics
        "win_rate_overall": 0,
        "win_rate_long": 0,
        "win_rate_short": 0,
        "r_expectancy": 0,
        "average_rr_ratio": 0,
        "profit_factor": 0,
        
        # Detailed Analysis - NEW ENHANCED SECTIONS
        "best_setup_analysis": {},
        "best_time_analysis": {},
        "worst_mistakes_analysis": {},
        "confluence_performance": {},
        
        # Volatility & Sentiment Analysis
        "volatility_performance": {},
        "sentiment_performance": {},
        
        # Specific Insights Discovery
        "key_insights": [],
        "actionable_recommendations": [],
        
        # Performance by Market Conditions
        "market_edge_analysis": {},
        
        # Mistake Patterns
        "recurring_mistakes": {},
        
        # Setup Confluence Analysis
        "signal_combination_performance": {}
    }
    
    recent_predictions = [p for p in predictions if datetime.strptime(p["timestamp"], "%Y-%m-%d %H:%M:%S") > datetime.now() - timedelta(days=30)]
    
    if not recent_predictions:
        return metrics
    
    # Extract all completed trades with enhanced metrics
    all_trades = []
    setup_performance = {}
    time_performance = {}
    mistake_frequency = {}
    confluence_performance = {}
    
    for pred in recent_predictions:
        if not pred.get("validation_points"):
            continue
            
        metrics["validated_predictions"] += 1
        
        # Extract enhanced trade data
        trade_data = extract_trade_metrics(pred)
        if not trade_data or trade_data["outcome"] == "PENDING":
            continue
            
        all_trades.append(trade_data)
        
        # Analyze setup types with confluence
        setup_key = create_setup_signature(trade_data)
        if setup_key not in setup_performance:
            setup_performance[setup_key] = {"trades": [], "wins": 0, "total_r": 0, "signals": trade_data["signals_used"]}
        
        setup_performance[setup_key]["trades"].append(trade_data)
        setup_performance[setup_key]["total_r"] += trade_data["r_multiple"]
        if trade_data["result"] == "WIN":
            setup_performance[setup_key]["wins"] += 1
        
        # Analyze time performance
        time_key = f"{trade_data['pred_hour']:02d}:00"
        if time_key not in time_performance:
            time_performance[time_key] = {"trades": [], "wins": 0, "total_r": 0}
        
        time_performance[time_key]["trades"].append(trade_data)
        time_performance[time_key]["total_r"] += trade_data["r_multiple"]
        if trade_data["result"] == "WIN":
            time_performance[time_key]["wins"] += 1
        
        # Analyze mistakes
        for mistake in trade_data["mistake_tags"]:
            if mistake not in mistake_frequency:
                mistake_frequency[mistake] = {"count": 0, "total_loss_r": 0}
            mistake_frequency[mistake]["count"] += 1
            if trade_data["result"] == "LOSS":
                mistake_frequency[mistake]["total_loss_r"] += abs(trade_data["r_multiple"])
        
        # Analyze confluence performance
        confluence_score = trade_data["confluence_score"]
        confluence_bucket = "high" if confluence_score > 7 else "medium" if confluence_score > 4 else "low"
        if confluence_bucket not in confluence_performance:
            confluence_performance[confluence_bucket] = {"trades": [], "wins": 0, "total_r": 0}
        
        confluence_performance[confluence_bucket]["trades"].append(trade_data)
        confluence_performance[confluence_bucket]["total_r"] += trade_data["r_multiple"]
        if trade_data["result"] == "WIN":
            confluence_performance[confluence_bucket]["wins"] += 1
    
    if not all_trades:
        return metrics
    
    # Calculate Core Metrics
    winning_trades = [t for t in all_trades if t["result"] == "WIN"]
    losing_trades = [t for t in all_trades if t["result"] == "LOSS"]
    long_trades = [t for t in all_trades if t["direction"] in ["BUY", "LONG", "BULLISH"]]
    short_trades = [t for t in all_trades if t["direction"] in ["SELL", "SHORT", "BEARISH"]]
    
    metrics["win_rate_overall"] = len(winning_trades) / len(all_trades)
    metrics["win_rate_long"] = len([t for t in long_trades if t["result"] == "WIN"]) / len(long_trades) if long_trades else 0
    metrics["win_rate_short"] = len([t for t in short_trades if t["result"] == "WIN"]) / len(short_trades) if short_trades else 0
    
    total_r = sum(t["r_multiple"] for t in all_trades)
    metrics["r_expectancy"] = total_r / len(all_trades)
    
    rr_ratios = [t["rr_ratio"] for t in all_trades if t["rr_ratio"] > 0]
    metrics["average_rr_ratio"] = sum(rr_ratios) / len(rr_ratios) if rr_ratios else 0
    
    total_wins_r = sum(t["r_multiple"] for t in winning_trades)
    total_losses_r = abs(sum(t["r_multiple"] for t in losing_trades))
    metrics["profit_factor"] = total_wins_r / total_losses_r if total_losses_r > 0 else float('inf')
    
    # ENHANCED ANALYSIS - Best Setup Analysis
    best_setups = {}
    for setup, data in setup_performance.items():
        if len(data["trades"]) >= 2:  # Minimum sample size
            win_rate = data["wins"] / len(data["trades"])
            avg_r = data["total_r"] / len(data["trades"])
            expectancy = win_rate * avg_r
            
            best_setups[setup] = {
                "win_rate": win_rate,
                "avg_r_per_trade": avg_r,
                "expectancy": expectancy,
                "total_trades": len(data["trades"]),
                "signals_used": data["signals"],
                "confluence_score": calculate_confluence_score(data["signals"])
            }
    
    # Sort by expectancy
    metrics["best_setup_analysis"] = dict(sorted(best_setups.items(), key=lambda x: x[1]["expectancy"], reverse=True)[:5])
    
    # ENHANCED ANALYSIS - Best Time Analysis
    best_times = {}
    for time_slot, data in time_performance.items():
        if len(data["trades"]) >= 2:
            win_rate = data["wins"] / len(data["trades"])
            avg_r = data["total_r"] / len(data["trades"])
            
            best_times[time_slot] = {
                "win_rate": win_rate,
                "avg_r_per_trade": avg_r,
                "total_trades": len(data["trades"]),
                "session": classify_time_session(int(time_slot.split(":")[0]))
            }
    
    metrics["best_time_analysis"] = dict(sorted(best_times.items(), key=lambda x: x[1]["win_rate"], reverse=True)[:5])
    
    # ENHANCED ANALYSIS - Worst Mistakes Analysis
    worst_mistakes = {}
    for mistake, data in mistake_frequency.items():
        if data["count"] >= 2:
            avg_loss_per_mistake = data["total_loss_r"] / data["count"] if data["count"] > 0 else 0
            impact_score = data["count"] * avg_loss_per_mistake
            
            worst_mistakes[mistake] = {
                "frequency": data["count"],
                "avg_loss_r": avg_loss_per_mistake,
                "total_impact_r": data["total_loss_r"],
                "impact_score": impact_score,
                "mistake_description": get_mistake_description(mistake)
            }
    
    metrics["worst_mistakes_analysis"] = dict(sorted(worst_mistakes.items(), key=lambda x: x[1]["impact_score"], reverse=True)[:5])
    
    # ENHANCED ANALYSIS - Confluence Performance
    for confluence_level, data in confluence_performance.items():
        if data["trades"]:
            win_rate = data["wins"] / len(data["trades"])
            avg_r = data["total_r"] / len(data["trades"])
            
            metrics["confluence_performance"][confluence_level] = {
                "win_rate": win_rate,
                "avg_r_per_trade": avg_r,
                "total_trades": len(data["trades"])
            }
    
    # Generate Key Insights (Examples from user requirements)
    insights = []
    
    # Insight 1: Overall profitability despite win rate
    if metrics["win_rate_overall"] < 0.6 and metrics["r_expectancy"] > 0.2:
        insights.append(f"Profitable despite {metrics['win_rate_overall']:.0%} win rate due to {metrics['average_rr_ratio']:.1f}:1 RR ratio")
    
    # Insight 2: Direction bias analysis
    if metrics["win_rate_long"] > metrics["win_rate_short"] + 0.15:
        insights.append(f"Strong long bias: {metrics['win_rate_long']:.0%} vs {metrics['win_rate_short']:.0%} short success")
    elif metrics["win_rate_short"] > metrics["win_rate_long"] + 0.15:
        insights.append(f"Strong short bias: {metrics['win_rate_short']:.0%} vs {metrics['win_rate_long']:.0%} long success")
    
    # Insight 3: Confluence analysis
    if "high" in metrics["confluence_performance"] and "low" in metrics["confluence_performance"]:
        high_conf_wr = metrics["confluence_performance"]["high"]["win_rate"]
        low_conf_wr = metrics["confluence_performance"]["low"]["win_rate"]
        if high_conf_wr > low_conf_wr + 0.2:
            insights.append(f"High confluence setups win {high_conf_wr:.0%} vs {low_conf_wr:.0%} for low confluence")
    
    # Insight 4: Best setup identification
    if metrics["best_setup_analysis"]:
        best_setup = list(metrics["best_setup_analysis"].keys())[0]
        best_setup_data = metrics["best_setup_analysis"][best_setup]
        if best_setup_data["win_rate"] > 0.7:
            active_signals = [k for k, v in best_setup_data["signals_used"].items() if v]
            insights.append(f"Best setup ({' + '.join(active_signals[:2])}) hits TP {best_setup_data['win_rate']:.0%} of the time")
    
    # Insight 5: Time-based performance
    if metrics["best_time_analysis"]:
        best_time = list(metrics["best_time_analysis"].keys())[0]
        worst_time = list(metrics["best_time_analysis"].keys())[-1]
        best_wr = metrics["best_time_analysis"][best_time]["win_rate"]
        worst_wr = metrics["best_time_analysis"][worst_time]["win_rate"]
        if best_wr > worst_wr + 0.2:
            insights.append(f"{best_time} calls perform {best_wr:.0%} vs {worst_time} at {worst_wr:.0%}")
    
    metrics["key_insights"] = insights
    
    # Generate Actionable Recommendations
    recommendations = []
    
    # Recommendation 1: Focus on best setups
    if metrics["best_setup_analysis"]:
        best_setup = list(metrics["best_setup_analysis"].keys())[0]
        if metrics["best_setup_analysis"][best_setup]["expectancy"] > 0.5:
            recommendations.append(f"Increase position size on {best_setup} setups (highest expectancy)")
    
    # Recommendation 2: Avoid worst mistakes
    if metrics["worst_mistakes_analysis"]:
        worst_mistake = list(metrics["worst_mistakes_analysis"].keys())[0]
        recommendations.append(f"Priority fix: Avoid {worst_mistake} (most costly mistake)")
    
    # Recommendation 3: Time optimization
    if metrics["best_time_analysis"]:
        best_time = list(metrics["best_time_analysis"].keys())[0]
        worst_time = list(metrics["best_time_analysis"].keys())[-1]
        recommendations.append(f"Focus on {best_time} predictions, reduce {worst_time} frequency")
    
    # Recommendation 4: Confluence filtering
    if "low" in metrics["confluence_performance"]:
        low_conf_performance = metrics["confluence_performance"]["low"]
        if low_conf_performance["win_rate"] < 0.4:
            recommendations.append("Filter out low confluence setups (win rate too low)")
    
    metrics["actionable_recommendations"] = recommendations
    
    return metrics

def create_setup_signature(trade_data):
    """Create a unique signature for setup type based on signals used"""
    signals = trade_data["signals_used"]
    active_signals = [k for k, v in signals.items() if v]
    
    # Create meaningful combinations
    if len(active_signals) == 0:
        return "no_confluence"
    elif len(active_signals) == 1:
        return f"single_{active_signals[0]}"
    elif len(active_signals) >= 3:
        # Sort for consistency and take top 3 most important
        signal_priority = ["technical_analysis", "support_resistance", "divergence", "volume_analysis", "rsi_momentum"]
        prioritized = [s for s in signal_priority if s in active_signals]
        others = [s for s in active_signals if s not in signal_priority]
        top_signals = (prioritized + others)[:3]
        return f"multi_{'_'.join(sorted(top_signals))}"
    else:
        return f"dual_{'_'.join(sorted(active_signals))}"

def get_mistake_description(mistake_code):
    """Get human-readable description of mistake patterns"""
    descriptions = {
        "poor_rr_ratio": "Taking trades with insufficient risk-reward ratio",
        "ignored_greed_signal": "Buying during extreme greed conditions",
        "ignored_fear_signal": "Selling during extreme fear conditions", 
        "short_in_low_volatility": "Shorting during low volatility periods",
        "insufficient_rr_for_volatility": "Inadequate RR ratio for high volatility",
        "overconfident_loss": "High confidence predictions that failed",
        "rushed_entry": "Entering trades too quickly without confirmation",
        "bought_overbought": "Buying when RSI shows overbought conditions",
        "sold_oversold": "Selling when RSI shows oversold conditions",
        "bad_timing_session": "Trading during low-activity time sessions"
    }
    return descriptions.get(mistake_code, mistake_code.replace("_", " ").title())

def extract_trade_metrics(prediction):
    """Extract comprehensive trade metrics from a prediction for advanced analysis - Enhanced Version"""
    try:
        # Get prediction details
        pro_analysis = prediction.get("predictions", {}).get("professional_analysis", {})
        ai_prediction = prediction.get("predictions", {}).get("ai_prediction", "")
        market_data = prediction.get("market_data", {})
        
        if not pro_analysis and not ai_prediction:
            return None

        # Extract price targets
        if pro_analysis:
            price_targets = pro_analysis.get("price_targets", {})
            entry_price = price_targets.get("current", 0) or 0
            tp_price = price_targets.get("target_1", 0) or 0
            sl_price = price_targets.get("stop_loss", 0) or 0
            direction = pro_analysis.get("primary_scenario", "NEUTRAL") or "NEUTRAL"
            confidence = pro_analysis.get("confidence_level", "medium")
            # Convert confidence level to numeric
            if isinstance(confidence, str):
                confidence_map = {"low": 30, "medium": 60, "high": 85}
                confidence = confidence_map.get(confidence.lower(), 60)
            elif confidence is None:
                confidence = 60
        else:
            # Fallback to AI prediction parsing
            entry_price = extract_price_from_text(ai_prediction, "entry")
            tp_price = extract_price_from_text(ai_prediction, "target")
            sl_price = extract_price_from_text(ai_prediction, "stop")
            direction = extract_direction_from_text(ai_prediction)
            confidence = 60  # Default confidence

        # Determine outcome from validation points
        validation_points = prediction.get("validation_points", [])
        outcome = "PENDING"
        actual_exit_price = entry_price
        duration_hours = 0
        hit_timestamp = None
        
        for vp in validation_points:
            vp_time = datetime.strptime(vp["timestamp"], "%Y-%m-%d %H:%M:%S")
            if vp["type"] in ["PROFESSIONAL_TARGET_1", "PROFESSIONAL_TARGET_2"]:
                outcome = "TP_HIT"
                actual_exit_price = vp["actual_price"]
                hit_timestamp = vp_time
                break
            elif vp["type"] == "PROFESSIONAL_STOP_LOSS":
                outcome = "SL_HIT"
                actual_exit_price = vp["actual_price"]
                hit_timestamp = vp_time
                break

        # Calculate duration if trade completed
        if hit_timestamp:
            pred_time = datetime.strptime(prediction["timestamp"], "%Y-%m-%d %H:%M:%S")
            duration_hours = (hit_timestamp - pred_time).total_seconds() / 3600

        if outcome == "PENDING" and duration_hours == 0:
            # Check if trade should be marked as breakeven or partial
            current_time = datetime.now()
            pred_time = datetime.strptime(prediction["timestamp"], "%Y-%m-%d %H:%M:%S")
            hours_since = (current_time - pred_time).total_seconds() / 3600
            
            if hours_since > 24:  # After 24 hours, evaluate as breakeven if no hits
                outcome = "BREAKEVEN"
                actual_exit_price = entry_price

        # Calculate comprehensive metrics
        risk = abs(entry_price - sl_price) if sl_price and entry_price else 0
        
        # Calculate R-multiple (how many R risked vs gained)
        if outcome == "TP_HIT":
            reward = abs(actual_exit_price - entry_price)
            r_multiple = reward / risk if risk > 0 else 0
        elif outcome == "SL_HIT":
            r_multiple = -1  # Lost 1R
        elif outcome == "BREAKEVEN":
            r_multiple = 0
        else:
            # Pending - calculate unrealized R
            current_btc = market_data.get("btc_price", entry_price)
            unrealized_pnl = abs(current_btc - entry_price)
            r_multiple = unrealized_pnl / risk if risk > 0 else 0
            if direction in ["SELL", "SHORT", "BEARISH"] and current_btc > entry_price:
                r_multiple = -r_multiple
            elif direction in ["BUY", "LONG", "BULLISH"] and current_btc < entry_price:
                r_multiple = -r_multiple

        # Calculate RR ratio
        potential_reward = abs(tp_price - entry_price) if tp_price and entry_price else 0
        rr_ratio = potential_reward / risk if risk > 0 else 0

        # Calculate actual price movement over 12h
        pred_time = datetime.strptime(prediction["timestamp"], "%Y-%m-%d %H:%M:%S")
        twelve_hour_mark = pred_time + timedelta(hours=12)
        
        # Try to find the 12h price from validation points or current price
        twelve_hour_price = market_data.get("btc_price", entry_price)
        actual_move_12h = abs(twelve_hour_price - entry_price) / entry_price if entry_price else 0

        # Extract market conditions - ENHANCED
        btc_rsi = market_data.get("btc_rsi", 50) or 50
        fear_greed = market_data.get("fear_greed", 50) or 50
        if isinstance(fear_greed, dict):
            fear_greed = fear_greed.get("index", 50) or 50

        # Enhanced volatility assessment using multiple indicators
        btc_price = market_data.get("btc_price", 0) or 0
        volatility = "medium"  # Default
        volatility_score = 0
        
        # Method 1: Price movement volatility
        if tp_price and entry_price:
            price_range_pct = abs(tp_price - entry_price) / entry_price
            if price_range_pct > 0.05:  # >5% move expected
                volatility_score += 2
            elif price_range_pct > 0.03:  # >3% move expected
                volatility_score += 1

        # Method 2: RSI volatility (extreme RSI = high volatility)
        if btc_rsi > 70 or btc_rsi < 30:
            volatility_score += 1

        # Method 3: Fear/Greed extremes = high volatility
        if fear_greed > 75 or fear_greed < 25:
            volatility_score += 1

        # Classify volatility
        if volatility_score >= 3:
            volatility = "high"
        elif volatility_score <= 1:
            volatility = "low"

        # Sentiment classification - ENHANCED
        sentiment = "neutral"
        if fear_greed < 25:
            sentiment = "extreme_fear"
        elif fear_greed < 40:
            sentiment = "fear"
        elif fear_greed > 75:
            sentiment = "extreme_greed"
        elif fear_greed > 60:
            sentiment = "greed"

        # Divergence detection (basic implementation)
        divergence_present = False
        # Check if price and sentiment are diverging
        if direction in ["BUY", "LONG", "BULLISH"] and fear_greed < 40:
            divergence_present = True  # Bullish divergence - buying in fear
        elif direction in ["SELL", "SHORT", "BEARISH"] and fear_greed > 60:
            divergence_present = True  # Bearish divergence - selling in greed

        # Extract signals used (confluence analysis) - ENHANCED
        signals_used = extract_confluence_signals(prediction)
        setup_strength = len([s for s in signals_used.values() if s]) / len(signals_used) if signals_used else 0

        # Mistake tagging - ENHANCED
        mistake_tags = identify_trade_mistakes(prediction, outcome, market_data, {
            "rr_ratio": rr_ratio,
            "volatility": volatility,
            "sentiment": sentiment,
            "confidence": confidence,
            "duration_hours": duration_hours
        })

        # Time analysis
        pred_hour = datetime.strptime(prediction["timestamp"], "%Y-%m-%d %H:%M:%S").hour
        time_session = classify_time_session(pred_hour)

        return {
            # Core tracking data
            "timestamp": prediction["timestamp"],
            "prediction_id": prediction.get("date", "") + "_" + prediction.get("session", ""),
            
            # Trade details
            "direction": direction,
            "entry_price": entry_price,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "actual_exit_price": actual_exit_price,
            "outcome": outcome,
            
            # Performance metrics
            "r_multiple": r_multiple,
            "rr_ratio": rr_ratio,
            "duration_hours": duration_hours,
            "actual_move_12h": actual_move_12h,
            
            # Market conditions
            "rsi": btc_rsi,
            "fear_greed": fear_greed,
            "sentiment": sentiment,
            "volatility": volatility,
            "volatility_score": volatility_score,
            "divergence_present": divergence_present,
            
            # Confluence & Setup
            "signals_used": signals_used,
            "setup_strength": setup_strength,
            "confluence_score": calculate_confluence_score(signals_used),
            
            # Analysis
            "confidence": confidence,
            "time_session": time_session,
            "pred_hour": pred_hour,
            "mistake_tags": mistake_tags,
            
            # Additional context
            "strongest_signal": pro_analysis.get("key_factors", {}).get("strongest_signal", ["unknown", 0])[0] if pro_analysis else "unknown",
            "bullish_probability": pro_analysis.get("bullish_probability", 50) if pro_analysis else 50,
            "bearish_probability": pro_analysis.get("bearish_probability", 50) if pro_analysis else 50,
            
            # Result classification
            "result": "WIN" if outcome == "TP_HIT" else "LOSS" if outcome == "SL_HIT" else "NEUTRAL"
        }
        
    except Exception as e:
        print(f"[ERROR] Extracting enhanced trade metrics: {e}")
        import traceback
        traceback.print_exc()
        return {}
        return None

def identify_setup_type(prediction):
    """Identify the type of setup/confluence signals used"""
    try:
        pro_analysis = prediction.get("predictions", {}).get("professional_analysis", {})
        if not pro_analysis:
            return "basic"
        
        strongest_signal = pro_analysis.get("key_factors", {}).get("strongest_signal", ["unknown", 0])[0]
        scenario = pro_analysis.get("primary_scenario", "neutral")
        confidence = pro_analysis.get("confidence_level", "low")
        
        # Create setup type based on confluence
        component_scores = pro_analysis.get("component_scores", {})
        high_scoring_components = [k for k, v in component_scores.items() if v > 7.0]
        
        if len(high_scoring_components) >= 3:
            setup_type = "high_confluence"
        elif len(high_scoring_components) >= 2:
            setup_type = "medium_confluence"
        else:
            setup_type = "single_signal"
        
        # Add strongest signal to setup type
        setup_type += f"_{strongest_signal}"
        
        return setup_type
    except Exception:
        return "unknown"

def identify_mistake_patterns(trades):
    """Identify recurring mistake patterns that hurt performance"""
    mistakes = []
    
    if not trades:
        return mistakes
    
    # Analyze overconfidence
    overconfident_losses = [t for t in trades if t["confidence"] > 80 and t["outcome"] == "SL_HIT"]
    if len(overconfident_losses) / len(trades) > 0.3:
        mistakes.append({
            "type": "overconfidence",
            "description": f"High confidence trades ({len(overconfident_losses)}) hitting SL",
            "frequency": len(overconfident_losses),
            "impact": "Overestimating certainty in uncertain markets"
        })
    
    # Analyze poor RR trades
    poor_rr_trades = [t for t in trades if t["rr_ratio"] < 1.5 and t["outcome"] == "SL_HIT"]
    if len(poor_rr_trades) / len(trades) > 0.2:
        mistakes.append({
            "type": "poor_risk_reward",
            "description": f"Taking trades with RR < 1.5 that failed ({len(poor_rr_trades)})",
            "frequency": len(poor_rr_trades),
            "impact": "Not maintaining proper risk-reward ratios"
        })
    
    # Analyze sentiment timing
    greed_losses = [t for t in trades if t["fear_greed"] > 70 and t["direction"] in ["LONG", "BUY"] and t["outcome"] == "SL_HIT"]
    if len(greed_losses) > 3:
        mistakes.append({
            "type": "greed_timing",
            "description": f"Buying during extreme greed ({len(greed_losses)} failures)",
            "frequency": len(greed_losses),
            "impact": "Poor market timing - buying tops"
        })
    
    # Analyze RSI extremes
    rsi_overbought_losses = [t for t in trades if t["rsi"] > 70 and t["direction"] in ["LONG", "BUY"] and t["outcome"] == "SL_HIT"]
    if len(rsi_overbought_losses) > 2:
        mistakes.append({
            "type": "rsi_overbought",
            "description": f"Longing while RSI > 70 ({len(rsi_overbought_losses)} failures)",
            "frequency": len(rsi_overbought_losses),
            "impact": "Ignoring overbought conditions"
        })
    
    return sorted(mistakes, key=lambda x: x["frequency"], reverse=True)

def generate_improvement_suggestions(accuracy_metrics, predictions):
    """Generate suggestions for AI improvement based on validation results"""
    suggestions = {
        "timestamp": datetime.now().isoformat(),
        "accuracy_summary": accuracy_metrics,
        "improvement_areas": [],
        "successful_patterns": [],
        "recommendations": []
    }
    
    # Analyze accuracy and generate suggestions
    if accuracy_metrics["professional_accuracy"] < 0.6:
        suggestions["improvement_areas"].append("Professional target accuracy below 60%")
        suggestions["recommendations"].append("Adjust professional analysis weightings")
    
    if accuracy_metrics["target_hit_rate"] < 0.4:
        suggestions["improvement_areas"].append("Target hit rate too low")
        suggestions["recommendations"].append("Revise target distance calculations")
    
    if accuracy_metrics["average_confidence"] > 80 and accuracy_metrics["professional_accuracy"] < 0.7:
        suggestions["improvement_areas"].append("Overconfidence detected")
        suggestions["recommendations"].append("Calibrate confidence scoring system")
    
    return suggestions

def save_improvement_data(improvement_data):
    """Save improvement suggestions for AI learning"""
    improvement_file = "ai_improvement_log.json"
    
    improvements = []
    if os.path.exists(improvement_file):
        try:
            with open(improvement_file, "r") as f:
                improvements = json.load(f)
        except Exception:
            improvements = []
    
    improvements.append(improvement_data)
    
    # Keep only last 30 days of improvements
    cutoff = datetime.now() - timedelta(days=30)
    improvements = [imp for imp in improvements 
                   if datetime.fromisoformat(imp["timestamp"]) > cutoff]
    
    with open(improvement_file, "w") as f:
        json.dump(improvements, f, indent=4)

def format_notification_message(notification):
    """Format a notification message for Telegram"""
    if notification["type"] == "professional_target":
        return (
            f"🎯 <b>PROFESSIONAL TARGET HIT</b>\n\n"
            f"Coin: {notification['coin']}\n"
            f"Target Level: {notification['target_level']}\n"
            f"Predicted: ${notification['predicted_price']:,.2f}\n"
            f"Actual: ${notification['actual_price']:,.2f}\n"
            f"Scenario: {notification['scenario']}\n\n"
            f"<i>Professional analysis target reached successfully!</i>"
        )
    elif notification["type"] == "professional_stop_loss":
        return (
            f"⚠️ <b>PROFESSIONAL STOP LOSS HIT</b>\n\n"
            f"Coin: {notification['coin']}\n"
            f"Predicted: ${notification['predicted_price']:,.2f}\n"
            f"Actual: ${notification['actual_price']:,.2f}\n"
            f"Scenario: {notification['scenario']}\n\n"
            f"<i>Professional stop loss triggered. Position closed.</i>"
        )
    else:
        return f"📊 Validation update: {notification['type']} for {notification['coin']}"

def format_accuracy_summary(metrics):
    """Format enhanced accuracy metrics summary for Telegram - Professional Trader Style"""
    overall_score = (
        metrics.get('win_rate_overall', 0) * 0.4 +
        max(0, metrics.get('r_expectancy', 0)) * 0.3 +
        min(1, metrics.get('average_rr_ratio', 0) / 2) * 0.3
    ) * 100

    # Format the comprehensive report
    report = f"📊 <b>PROFESSIONAL TRADING PERFORMANCE</b>\n"
    report += f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    report += f"{'═' * 35}\n\n"
    
    # Overall Performance
    report += f"🏆 <b>OVERALL SCORE: {overall_score:.1f}%</b>\n\n"
    
    # Core Metrics
    report += f"<b>📈 CORE PERFORMANCE</b>\n"
    report += f"• Win Rate: {metrics.get('win_rate_overall', 0):.1%}\n"
    report += f"• R-Expectancy: {metrics.get('r_expectancy', 0):.2f}R\n"
    report += f"• Avg RR Ratio: {metrics.get('average_rr_ratio', 0):.1f}:1\n"
    report += f"• Total Trades: {metrics.get('validated_predictions', 0)}\n\n"
    
    # Directional Performance
    report += f"<b>📊 DIRECTIONAL ANALYSIS</b>\n"
    long_rate = metrics.get('win_rate_long', 0)
    short_rate = metrics.get('win_rate_short', 0)
    
    if long_rate > 0 or short_rate > 0:
        report += f"• Long Trades: {long_rate:.1%}\n"
        report += f"• Short Trades: {short_rate:.1%}\n"
        
        # Bias analysis
        if long_rate > short_rate + 0.1:
            bias = "🟢 Long Bias"
        elif short_rate > long_rate + 0.1:
            bias = "🔴 Short Bias"
        else:
            bias = "⚪ Balanced"
        report += f"• Direction Bias: {bias}\n\n"
    else:
        report += f"• Not enough directional data yet\n\n"
    
    # Best Setups & Timing
    report += f"<b>⭐ BEST PERFORMING</b>\n"
    report += f"• Best Time: {metrics.get('best_timeframe', 'Analyzing...')}\n"
    report += f"• Best Setup: {metrics.get('best_setup_type', 'Analyzing...')}\n\n"
    
    # Market Conditions Performance
    vol_perf = metrics.get('volatility_performance', {})
    if vol_perf:
        report += f"<b>🌊 VOLATILITY PERFORMANCE</b>\n"
        for vol_level, stats in vol_perf.items():
            if stats['trade_count'] >= 2:
                report += f"• {vol_level.title()}: {stats['win_rate']:.1%} ({stats['trade_count']} trades)\n"
        report += "\n"
    
    # Sentiment Performance
    sent_perf = metrics.get('sentiment_performance', {})
    if sent_perf:
        report += f"<b>😨😐😍 SENTIMENT PERFORMANCE</b>\n"
        for sentiment, stats in sent_perf.items():
            if stats['trade_count'] >= 2:
                emoji = "😨" if sentiment == "fear" else "😍" if sentiment == "greed" else "😐"
                report += f"• {emoji} {sentiment.title()}: {stats['win_rate']:.1%} (RR: {stats['avg_rr']:.1f})\n"
        report += "\n"
    
    # Worst Mistakes
    mistakes = metrics.get('worst_mistakes', [])
    if mistakes:
        report += f"<b>⚠️ TOP MISTAKES TO AVOID</b>\n"
        for i, mistake in enumerate(mistakes[:3], 1):
            report += f"{i}. {mistake['description']}\n"
        report += "\n"
    
    # Pattern Recognition
    patterns = metrics.get('prediction_patterns', {})
    if patterns:
        avg_conf_winners = patterns.get('avg_confidence_winners', 0)
        avg_conf_losers = patterns.get('avg_confidence_losers', 0)
        
        if avg_conf_winners > 0 and avg_conf_losers > 0:
            confidence_edge = avg_conf_winners - avg_conf_losers
            report += f"<b>🧠 PATTERN INSIGHTS</b>\n"
            report += f"• Winner Confidence: {avg_conf_winners:.0f}%\n"
            report += f"• Loser Confidence: {avg_conf_losers:.0f}%\n"
            
            if confidence_edge > 10:
                report += f"• ✅ Good confidence calibration (+{confidence_edge:.0f})\n"
            elif confidence_edge < -5:
                report += f"• ❌ Overconfident on losers ({confidence_edge:.0f})\n"
            else:
                report += f"• ⚪ Neutral confidence pattern\n"
            report += "\n"
    
    # Key Insights
    report += f"<b>💡 KEY INSIGHTS</b>\n"
    
    # R-Expectancy insight
    r_exp = metrics.get('r_expectancy', 0)
    if r_exp > 0.5:
        report += f"• 🟢 Positive expectancy - profitable system\n"
    elif r_exp > 0:
        report += f"• 🟡 Marginally profitable - room for improvement\n"
    else:
        report += f"• 🔴 Negative expectancy - system needs adjustment\n"
    
    # Win rate vs RR insight
    win_rate = metrics.get('win_rate_overall', 0)
    avg_rr = metrics.get('average_rr_ratio', 0)
    if win_rate > 0 and avg_rr > 0:
        breakeven_wr = 1 / (1 + avg_rr)
        if win_rate > breakeven_wr:
            edge = (win_rate - breakeven_wr) * 100
            report += f"• 📈 {edge:.1f}% edge over breakeven\n"
        else:
            deficit = (breakeven_wr - win_rate) * 100
            report += f"• 📉 {deficit:.1f}% below breakeven needs\n"
    
    report += f"\n<i>🚀 System learning and evolving continuously!</i>"
    
    return report

def validate_target_hit(current_price, target_price, target_type, scenario="NEUTRAL"):
    """Check if a target was hit based on scenario and target type"""
    if not current_price or not target_price:
        return False
    
    # For professional analysis targets
    if target_type.startswith("TARGET"):
        if scenario.upper() in ["BUY", "STRONG BUY", "BULLISH"]:
            # Bullish scenario: targets should be above current price
            return current_price >= target_price
        elif scenario.upper() in ["SELL", "STRONG SELL", "BEARISH"]:
            # Bearish scenario: targets should be below current price
            return current_price <= target_price
        else:
            # Neutral: check both directions
            return abs(current_price - target_price) / target_price < 0.02  # Within 2%
    
    elif target_type == "STOP_LOSS":
        if scenario.upper() in ["BUY", "STRONG BUY", "BULLISH"]:
            # Bullish scenario: stop loss below entry
            return current_price <= target_price
        elif scenario.upper() in ["SELL", "STRONG SELL", "BEARISH"]:
            # Bearish scenario: stop loss above entry
            return current_price >= target_price
        else:
            # Check if stop loss was hit (either direction)
            return abs(current_price - target_price) / target_price < 0.01  # Within 1%
    
    return False

def extract_professional_targets(prediction_data):
    """Extract professional analysis targets from the enhanced prediction format"""
    targets = {"BTC": {}, "ETH": {}}
    
    try:
        # Check if it's a professional analysis prediction
        if isinstance(prediction_data, dict):
            # Try to find professional analysis targets
            pro_analysis = prediction_data.get("professional_analysis", {})
            if pro_analysis and "price_targets" in pro_analysis:
                price_targets = pro_analysis["price_targets"]
                targets["BTC"] = {
                    "current": price_targets.get("current"),
                    "target_1": price_targets.get("target_1"),
                    "target_2": price_targets.get("target_2"),
                    "stop_loss": price_targets.get("stop_loss"),
                    "scenario": pro_analysis.get("primary_scenario", "NEUTRAL")
                }
            
            # Also check AI prediction format (fallback)
            if "btc_prediction" in prediction_data:
                btc_pred = prediction_data["btc_prediction"]
                targets["BTC"].update({
                    "entry_range": extract_price_range(btc_pred.get("entry_price_range", "")),
                    "take_profits": extract_take_profits(btc_pred.get("take_profit_targets", "")),
                    "stop_loss": extract_price(btc_pred.get("stop_loss", "")),
                    "direction": btc_pred.get("direction", "")
                })
            
            if "eth_prediction" in prediction_data:
                eth_pred = prediction_data["eth_prediction"]
                targets["ETH"].update({
                    "entry_range": extract_price_range(eth_pred.get("entry_price_range", "")),
                    "take_profits": extract_take_profits(eth_pred.get("take_profit_targets", "")),
                    "stop_loss": extract_price(eth_pred.get("stop_loss", "")),
                    "direction": eth_pred.get("direction", "")
                })
                
    except Exception as e:
        print(f"[ERROR] Extracting professional targets: {e}")
    
    return targets

def extract_price_range(price_str):
    """Extract price range from string"""
    if not price_str:
        return None
    try:
        matches = re.findall(r'\$?(\d+(?:,\d+)*(?:\.\d+)?)', price_str)
        if len(matches) >= 2:
            return (float(matches[0].replace(',', '')), float(matches[1].replace(',', '')))
    except Exception:
        pass
    return None

def extract_take_profits(price_str):
    """Extract take profit targets from string"""
    if not price_str:
        return []
    try:
        matches = re.findall(r'TP\d+:\s*\$?(\d+(?:,\d+)*(?:\.\d+)?)', price_str)
        return [float(match.replace(',', '')) for match in matches]
    except Exception:
        return []

def extract_price(price_str):
    """Extract single price from string"""
    if not price_str:
        return None
    try:
        match = re.search(r'\$?(\d+(?:,\d+)*(?:\.\d+)?)', price_str)
        if match:
            return float(match.group(1).replace(',', ''))
    except Exception:
        pass
    return None

def generate_deep_learning_insights(predictions, period_type="weekly"):
    """Generate comprehensive weekly/monthly trading insights for accelerated learning"""
    insights = {
        "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "period_type": period_type,  # Use the passed parameter
        
        # Core Performance Review
        "performance_summary": {},
        
        # Detailed Learning Insights
        "best_setup_findings": {},
        "best_time_findings": {},
        "worst_mistake_patterns": {},
        "market_edge_analysis": {},
        
        # Strategic Recommendations
        "focus_areas": [],
        "avoid_patterns": [],
        "optimization_suggestions": [],
        
        # Learning Progress Tracking
        "improvement_metrics": {},
        "next_period_targets": {}
    }
    
    try:
        # Get enhanced accuracy metrics
        enhanced_metrics = calculate_enhanced_accuracy(predictions)
        
        if not enhanced_metrics or enhanced_metrics["validated_predictions"] == 0:
            insights["performance_summary"] = {"status": "insufficient_data", "message": "Need more completed trades for analysis"}
            return insights
        
        # === PERFORMANCE SUMMARY ===
        insights["performance_summary"] = {
            "total_predictions": enhanced_metrics["total_predictions"],
            "completed_trades": enhanced_metrics["validated_predictions"],
            "overall_win_rate": f"{enhanced_metrics['win_rate_overall']:.1%}",
            "long_win_rate": f"{enhanced_metrics['win_rate_long']:.1%}",
            "short_win_rate": f"{enhanced_metrics['win_rate_short']:.1%}",
            "r_expectancy": f"{enhanced_metrics['r_expectancy']:.2f}R",
            "average_rr_ratio": f"{enhanced_metrics['average_rr_ratio']:.1f}:1",
            "profit_factor": f"{enhanced_metrics['profit_factor']:.2f}" if enhanced_metrics['profit_factor'] != float('inf') else "∞",
            "profitability_status": "Profitable" if enhanced_metrics['r_expectancy'] > 0 else "Unprofitable"
        }
        
        # === BEST SETUP FINDINGS ===
        if enhanced_metrics["best_setup_analysis"]:
            setup_findings = {}
            
            for i, (setup_name, setup_data) in enumerate(enhanced_metrics["best_setup_analysis"].items()):
                if i >= 3:  # Top 3 setups
                    break
                    
                active_signals = [k.replace("_", " ").title() for k, v in setup_data["signals_used"].items() if v]
                
                setup_findings[f"rank_{i+1}"] = {
                    "setup_name": setup_name.replace("_", " ").title(),
                    "win_rate": f"{setup_data['win_rate']:.1%}",
                    "avg_return": f"{setup_data['avg_r_per_trade']:.2f}R",
                    "expectancy": f"{setup_data['expectancy']:.2f}",
                    "sample_size": setup_data['total_trades'],
                    "signals_used": active_signals,
                    "confluence_score": f"{setup_data['confluence_score']:.1f}/10",
                    "recommendation": f"{'HIGH PRIORITY' if setup_data['expectancy'] > 0.5 else 'MODERATE'} - Focus on this setup"
                }
            
            insights["best_setup_findings"] = setup_findings
        
        # === BEST TIME FINDINGS ===
        if enhanced_metrics["best_time_analysis"]:
            time_findings = {}
            
            for i, (time_slot, time_data) in enumerate(enhanced_metrics["best_time_analysis"].items()):
                if i >= 3:  # Top 3 times
                    break
                    
                time_findings[f"rank_{i+1}"] = {
                    "time_slot": time_slot,
                    "session": time_data['session'].replace("_", " ").title(),
                    "win_rate": f"{time_data['win_rate']:.1%}",
                    "avg_return": f"{time_data['avg_r_per_trade']:.2f}R",
                    "sample_size": time_data['total_trades'],
                    "recommendation": f"{'OPTIMAL' if time_data['win_rate'] > 0.6 else 'GOOD'} trading window"
                }
            
            insights["best_time_findings"] = time_findings
        
        # === WORST MISTAKE PATTERNS ===
        if enhanced_metrics["worst_mistakes_analysis"]:
            mistake_findings = {}
            
            for i, (mistake_code, mistake_data) in enumerate(enhanced_metrics["worst_mistakes_analysis"].items()):
                if i >= 3:  # Top 3 mistakes
                    break
                    
                mistake_findings[f"priority_{i+1}"] = {
                    "mistake_type": mistake_data['mistake_description'],
                    "frequency": mistake_data['frequency'],
                    "avg_loss_per_occurrence": f"{mistake_data['avg_loss_r']:.2f}R",
                    "total_cost": f"{mistake_data['total_impact_r']:.2f}R",
                    "impact_score": f"{mistake_data['impact_score']:.1f}",
                    "fix_priority": "CRITICAL" if mistake_data['impact_score'] > 2.0 else "HIGH",
                    "suggested_fix": get_mistake_fix_suggestion(mistake_code)
                }
            
            insights["worst_mistake_patterns"] = mistake_findings
        
        # === MARKET EDGE ANALYSIS ===
        confluence_analysis = {}
        if enhanced_metrics["confluence_performance"]:
            for level, data in enhanced_metrics["confluence_performance"].items():
                confluence_analysis[f"{level}_confluence"] = {
                    "win_rate": f"{data['win_rate']:.1%}",
                    "avg_return": f"{data['avg_r_per_trade']:.2f}R",
                    "trade_count": data['total_trades'],
                    "recommendation": get_confluence_recommendation(level, data['win_rate'])
                }
        
        insights["market_edge_analysis"] = {
            "confluence_performance": confluence_analysis,
            "key_edge_discovery": enhanced_metrics.get("key_insights", []),
            "market_bias": determine_market_bias(enhanced_metrics)
        }
        
        # === STRATEGIC RECOMMENDATIONS ===
        focus_areas = []
        avoid_patterns = []
        optimization_suggestions = []
        
        # Focus Areas
        if enhanced_metrics["best_setup_analysis"]:
            best_setup = list(enhanced_metrics["best_setup_analysis"].keys())[0]
            best_setup_data = enhanced_metrics["best_setup_analysis"][best_setup]
            if best_setup_data["expectancy"] > 0.3:
                focus_areas.append(f"Increase frequency of {best_setup.replace('_', ' ')} setups (highest expectancy)")
        
        if enhanced_metrics["best_time_analysis"]:
            best_time = list(enhanced_metrics["best_time_analysis"].keys())[0]
            best_time_data = enhanced_metrics["best_time_analysis"][best_time]
            if best_time_data["win_rate"] > 0.65:
                focus_areas.append(f"Schedule more predictions around {best_time} ({best_time_data['session'].replace('_', ' ')})")
        
        # Avoid Patterns
        if enhanced_metrics["worst_mistakes_analysis"]:
            worst_mistake = list(enhanced_metrics["worst_mistakes_analysis"].keys())[0]
            worst_mistake_data = enhanced_metrics["worst_mistakes_analysis"][worst_mistake]
            avoid_patterns.append(f"PRIORITY: Stop {worst_mistake_data['mistake_description'].lower()}")
        
        if "low" in enhanced_metrics["confluence_performance"]:
            low_conf_data = enhanced_metrics["confluence_performance"]["low"]
            if low_conf_data["win_rate"] < 0.4:
                avoid_patterns.append("Filter out low confluence setups (win rate below 40%)")
        
        # Optimization Suggestions
        if enhanced_metrics["win_rate_overall"] < 0.5 and enhanced_metrics["average_rr_ratio"] < 2.0:
            optimization_suggestions.append("Increase RR ratio targets to 2:1 minimum to offset low win rate")
        
        if enhanced_metrics["r_expectancy"] < 0.1:
            optimization_suggestions.append("Focus on confluence improvement - current expectancy too low")
        
        optimization_suggestions.extend(enhanced_metrics.get("actionable_recommendations", []))
        
        insights["focus_areas"] = focus_areas[:3]  # Top 3
        insights["avoid_patterns"] = avoid_patterns[:3]  # Top 3
        insights["optimization_suggestions"] = optimization_suggestions[:5]  # Top 5
        
        # === IMPROVEMENT METRICS ===
        # Compare with previous period (simplified - would need historical data)
        insights["improvement_metrics"] = {
            "current_expectancy": enhanced_metrics["r_expectancy"],
            "current_win_rate": enhanced_metrics["win_rate_overall"],
            "current_rr_ratio": enhanced_metrics["average_rr_ratio"],
            "trend_analysis": "Requires historical data for comparison",
            "learning_velocity": calculate_learning_velocity(enhanced_metrics)
        }
        
        # === NEXT PERIOD TARGETS ===
        current_wr = enhanced_metrics["win_rate_overall"]
        current_expectancy = enhanced_metrics["r_expectancy"]
        
        target_wr = min(current_wr + 0.05, 0.8)  # Aim for 5% improvement, max 80%
        target_expectancy = max(current_expectancy + 0.1, 0.3)  # Aim for +0.1R, min 0.3R
        
        insights["next_period_targets"] = {
            "target_win_rate": f"{target_wr:.1%}",
            "target_expectancy": f"{target_expectancy:.2f}R",
            "target_mistake_reduction": "50% reduction in top mistake frequency",
            "target_confluence_improvement": "Increase high confluence trade percentage by 20%",
            "focus_metric": "R-expectancy" if current_expectancy < 0.2 else "Win rate optimization"
        }
        
    except Exception as e:
        print(f"[ERROR] Generating deep learning insights: {e}")
        import traceback
        traceback.print_exc()
        insights["error"] = str(e)
    
    return insights

def get_mistake_fix_suggestion(mistake_code):
    """Get specific suggestions for fixing trading mistakes"""
    suggestions = {
        "poor_rr_ratio": "Set minimum 2:1 RR ratio rule, widen stop losses or better entry timing",
        "ignored_greed_signal": "Create rule: No longs when Fear & Greed > 75, wait for cooldown",
        "ignored_fear_signal": "Create rule: No shorts when Fear & Greed < 25, look for bounces",
        "short_in_low_volatility": "Avoid shorts when expected move < 3%, focus on longs in low vol",
        "insufficient_rr_for_volatility": "High volatility trades need 3:1+ RR, adjust targets",
        "overconfident_loss": "Cap position size when confidence > 80%, add confirmation delays",
        "rushed_entry": "Implement 30-min confirmation delay, wait for retests",
        "bought_overbought": "RSI > 70 = wait for pullback, use RSI divergence instead",
        "sold_oversold": "RSI < 30 = wait for relief bounce, look for reversal patterns",
        "bad_timing_session": "Avoid predictions during 00:00-03:00 UTC (low liquidity)"
    }
    return suggestions.get(mistake_code, "Review and create specific rules to avoid this pattern")

def get_confluence_recommendation(level, win_rate):
    """Get recommendations based on confluence performance"""
    if level == "high" and win_rate > 0.7:
        return "EXCELLENT - Prioritize these setups"
    elif level == "high" and win_rate > 0.5:
        return "GOOD - Continue focusing on high confluence"
    elif level == "medium" and win_rate > 0.6:
        return "SOLID - Good backup when high confluence unavailable"
    elif level == "low" and win_rate < 0.4:
        return "AVOID - Filter out low confluence setups"
    else:
        return "MONITOR - Track performance closely"

def determine_market_bias(metrics):
    """Determine overall market bias and trading preferences"""
    long_wr = metrics["win_rate_long"]
    short_wr = metrics["win_rate_short"]
    
    if long_wr > short_wr + 0.15:
        return f"LONG BIAS - {long_wr:.1%} vs {short_wr:.1%} (favor bullish setups)"
    elif short_wr > long_wr + 0.15:
        return f"SHORT BIAS - {short_wr:.1%} vs {long_wr:.1%} (favor bearish setups)"
    else:
        return f"BALANCED - Similar performance both directions ({long_wr:.1%} L / {short_wr:.1%} S)"

def calculate_learning_velocity(metrics):
    """Calculate how fast the system is learning (simplified)"""
    expectancy = metrics["r_expectancy"]
    win_rate = metrics["win_rate_overall"]
    
    if expectancy > 0.3 and win_rate > 0.6:
        return "FAST - Excellent performance metrics"
    elif expectancy > 0.1 and win_rate > 0.5:
        return "MODERATE - Good progress, room for improvement"
    elif expectancy > 0:
        return "SLOW - Positive but needs optimization"
    else:
        return "NEGATIVE - Requires major strategy revision"

def save_deep_learning_insights(insights):
    """Save deep learning insights for AI evolution"""
    period_type = insights.get('period_type', 'weekly')
    analysis_date = insights.get('analysis_date', datetime.now().isoformat())
    
    # Extract period from analysis_date for database storage
    period_str = analysis_date[:10]  # YYYY-MM-DD format
    if period_type == 'weekly':
        # Convert to week format (e.g., 2025-W20)
        date_obj = datetime.fromisoformat(analysis_date)
        week_num = date_obj.isocalendar()[1]
        period_str = f"{date_obj.year}-W{week_num:02d}"
    elif period_type == 'monthly':
        # Convert to month format (e.g., 2025-05)
        period_str = analysis_date[:7]  # YYYY-MM format
    
    # Try to save to database first
    success = False
    if DATABASE_AVAILABLE:
        try:
            success = db_manager.save_learning_insight(period_type, period_str, insights)
            if success:
                print(f"[INFO] Deep learning insights saved to database for {period_type} period {period_str}")
        except Exception as e:
            print(f"[ERROR] Failed to save insights to database: {e}")
    
    # Fallback to JSON file if database failed or not available
    if not success:
        insights_file = "deep_learning_insights.json"
        
        all_insights = []
        if os.path.exists(insights_file):
            try:
                with open(insights_file, "r") as f:
                    all_insights = json.load(f)
            except Exception:
                all_insights = []
        
        all_insights.append(insights)
        
        # Keep only last 3 months of insights
        cutoff = datetime.now() - timedelta(days=90)
        all_insights = [insight for insight in all_insights 
                       if datetime.fromisoformat(insight["analysis_date"]) > cutoff]
        
        with open(insights_file, "w") as f:
            json.dump(all_insights, f, indent=4)
        
        print(f"[INFO] Deep learning insights saved to JSON file - {len(all_insights)} total analyses stored")

def format_deep_insights_summary(insights):
    """Format deep insights for Telegram - Professional Review Style"""
    if "error" in insights:
        return f"📊 Deep Analysis: {insights['error']}"
    
    report = f"🧠 <b>{insights['period_type'].upper()} DEEP LEARNING ANALYSIS</b>\n"
    report += f"📅 {datetime.now().strftime('%Y-%m-%d')}\n"
    report += f"{'═' * 40}\n\n"
    
    core = insights.get("performance_summary", {})
    
    # Executive Summary
    report += f"<b>📈 EXECUTIVE SUMMARY</b>\n"
    report += f"• Total Trades: {core.get('completed_trades', 0)}\n"
    report += f"• Win Rate: {core.get('overall_win_rate', '0%')}\n"
    report += f"• R-Expectancy: {core.get('r_expectancy', '0.00R')}\n"
    report += f"• Profit Factor: {core.get('profit_factor', '0.0')}\n"
    report += f"• Status: {core.get('profitability_status', 'Unknown')}\n\n"
    
    # Top Performing Setups
    if insights.get("best_setup_findings"):
        report += f"<b>⭐ BEST PERFORMING SETUPS</b>\n"
        for rank_key, setup in insights["best_setup_findings"].items():
            rank_num = rank_key.split('_')[1]
            signals_text = ', '.join(setup.get('signals_used', [])[:2]) if setup.get('signals_used') else 'None'
            report += f"{rank_num}. {setup.get('setup_name', 'Unknown')}\n"
            report += f"   • Win Rate: {setup.get('win_rate', '0%')}\n"
            report += f"   • Avg R: {setup.get('avg_return', '0.00R')}\n"
            report += f"   • Trades: {setup.get('sample_size', 0)}\n"
            report += f"   • Signals: {signals_text}\n\n"
    
    # Best Timing
    if insights.get("best_time_findings"):
        report += f"<b>⏰ OPTIMAL TIMING</b>\n"
        
        for rank_key, time_data in insights["best_time_findings"].items():
            rank_num = rank_key.split('_')[1]
            report += f"{rank_num}. {time_data.get('time_slot', 'Unknown')} ({time_data.get('session', 'Unknown')}) - {time_data.get('win_rate', '0%')}\n"
        report += "\n"
    
    # Market Edge Analysis  
    market_edge = insights.get("market_edge_analysis", {})
    confluence_perf = market_edge.get("confluence_performance", {})
    if confluence_perf:
        report += f"<b>🌊 CONFLUENCE PERFORMANCE</b>\n"
        for level, stats in confluence_perf.items():
            level_name = level.replace('_confluence', '').title()
            report += f"• {level_name}: {stats.get('win_rate', '0%')} ({stats.get('trade_count', 0)} trades)\n"
        report += "\n"
    
    # Key Insights
    key_insights = market_edge.get("key_edge_discovery", [])
    if key_insights:
        report += f"<b>💡 KEY INSIGHTS</b>\n"
        for i, insight in enumerate(key_insights[:3], 1):
            report += f"{i}. {insight}\n"
        report += "\n"
    
    # Worst Mistakes
    if insights.get("worst_mistake_patterns"):
        report += f"<b>⚠️ TOP MISTAKES TO AVOID</b>\n"
        for priority_key, mistake in insights["worst_mistake_patterns"].items():
            priority_num = priority_key.split('_')[1]
            report += f"{priority_num}. {mistake.get('mistake_type', 'Unknown')} (Impact: {mistake.get('impact_score', '0')})\n"
        report += "\n"
    
    # Focus Areas
    if insights.get("focus_areas"):
        report += f"<b>🎯 FOCUS AREAS</b>\n"
        for i, area in enumerate(insights["focus_areas"], 1):
            report += f"{i}. {area}\n"
        report += "\n"
    
    # Optimization Suggestions
    if insights.get("optimization_suggestions"):
        report += f"<b>🔧 OPTIMIZATION SUGGESTIONS</b>\n"
        for i, suggestion in enumerate(insights["optimization_suggestions"][:3], 1):
            report += f"{i}. {suggestion}\n"
        report += "\n"
    
    report += f"<i>🚀 Evolution in progress - becoming more profitable!</i>"
    
    return report

def extract_price_from_text(text, price_type):
    """Extract price from AI prediction text"""
    if not text:
        return None
    
    # Look for specific price patterns
    patterns = {
        "entry": [r'entry.*?\$?(\d+(?:,\d+)*(?:\.\d+)?)', r'buy.*?\$?(\d+(?:,\d+)*(?:\.\d+)?)'],
        "target": [r'target.*?\$?(\d+(?:,\d+)*(?:\.\d+)?)', r'tp.*?\$?(\d+(?:,\d+)*(?:\.\d+)?)'],
        "stop": [r'stop.*?\$?(\d+(?:,\d+)*(?:\.\d+)?)', r'sl.*?\$?(\d+(?:,\d+)*(?:\.\d+)?)']
    }
    
    for pattern in patterns.get(price_type, []):
        match = re.search(pattern, text.lower())
        if match:
            try:
                return float(match.group(1).replace(',', ''))
            except:
                continue
    return None

def extract_direction_from_text(text):
    """Extract direction from AI prediction text"""
    if not text:
        return "NEUTRAL"
    
    text_lower = text.lower()
    if any(word in text_lower for word in ['buy', 'long', 'bullish', 'rally']):
        return "BUY"
    elif any(word in text_lower for word in ['sell', 'short', 'bearish', 'dip']):
        return "SELL"
    return "NEUTRAL"

def extract_confluence_signals(prediction):
    """Extract and analyze confluence signals used in prediction"""
    signals = {
        "technical_analysis": False,
        "volume_analysis": False,
        "support_resistance": False,
        "rsi_momentum": False,
        "macd_signal": False,
        "funding_sentiment": False,
        "fear_greed": False,
        "divergence": False,
        "breakout_pattern": False,
        "trend_alignment": False
    }
    
    try:
        # Analyze professional analysis components
        pro_analysis = prediction.get("predictions", {}).get("professional_analysis", {})
        ai_prediction = prediction.get("predictions", {}).get("ai_prediction", "")
        
        if pro_analysis:
            component_scores = pro_analysis.get("component_scores", {})
            
            # Map component scores to signals
            for component, score in component_scores.items():
                if score > 6.0:  # High confidence signal
                    if "price_action" in component:
                        signals["technical_analysis"] = True
                    elif "volume" in component:
                        signals["volume_analysis"] = True
                    elif "momentum" in component:
                        signals["rsi_momentum"] = True
                    elif "funding" in component or "sentiment" in component:
                        signals["funding_sentiment"] = True
                    elif "volatility" in component:
                        signals["breakout_pattern"] = True
            
            # Check strongest signal
            strongest = pro_analysis.get("key_factors", {}).get("strongest_signal", ["", 0])
            if strongest[1] > 7.0:
                signal_type = strongest[0].lower()
                if "technical" in signal_type:
                    signals["technical_analysis"] = True
                elif "volume" in signal_type:
                    signals["volume_analysis"] = True
                elif "support" in signal_type or "resistance" in signal_type:
                    signals["support_resistance"] = True
        
        # Analyze AI prediction text for signals
        if ai_prediction:
            text_lower = ai_prediction.lower()
            
            if any(word in text_lower for word in ['rsi', 'momentum', 'oversold', 'overbought']):
                signals["rsi_momentum"] = True
            
            if any(word in text_lower for word in ['macd', 'moving average', 'crossover']):
                signals["macd_signal"] = True
                
            if any(word in text_lower for word in ['support', 'resistance', 'level']):
                signals["support_resistance"] = True
                
            if any(word in text_lower for word in ['volume', 'accumulation', 'distribution']):
                signals["volume_analysis"] = True
                
            if any(word in text_lower for word in ['funding', 'sentiment', 'fear', 'greed']):
                signals["funding_sentiment"] = True
                
            if any(word in text_lower for word in ['divergence', 'hidden', 'regular']):
                signals["divergence"] = True
                
            if any(word in text_lower for word in ['breakout', 'breakdown', 'pattern']):
                signals["breakout_pattern"] = True
                
            if any(word in text_lower for word in ['trend', 'uptrend', 'downtrend', 'alignment']):
                signals["trend_alignment"] = True
        
        # Check market data for implicit signals
        market_data = prediction.get("market_data", {})
        if market_data:
            fear_greed = market_data.get("fear_greed", 50)
            if isinstance(fear_greed, dict):
                fear_greed = fear_greed.get("index", 50)
            
            if fear_greed < 25 or fear_greed > 75:
                signals["fear_greed"] = True
    
    except Exception as e:
        print(f"[WARN] Error extracting confluence signals: {e}")
    
    return signals

def calculate_confluence_score(signals):
    """Calculate confluence score based on signal strength"""
    if not signals:
        return 0
    
    # Weight different signals by importance
    signal_weights = {
        "technical_analysis": 2.0,
        "volume_analysis": 1.5,
        "support_resistance": 2.0,
        "rsi_momentum": 1.0,
        "macd_signal": 1.5,
        "funding_sentiment": 1.0,
        "fear_greed": 0.5,
        "divergence": 2.0,
        "breakout_pattern": 1.5,
        "trend_alignment": 1.5
    }
    
    total_score = 0
    max_possible = sum(signal_weights.values())
    
    for signal, active in signals.items():
        if active:
            total_score += signal_weights.get(signal, 1.0)
    
    return (total_score / max_possible) * 10  # Scale to 0-10

def identify_trade_mistakes(prediction, outcome, market_data, trade_metrics):
    """Identify specific mistake patterns in trades"""
    mistakes = []
    
    try:
        rr_ratio = trade_metrics.get("rr_ratio", 0)
        volatility = trade_metrics.get("volatility", "medium")
        sentiment = trade_metrics.get("sentiment", "neutral")
        confidence = trade_metrics.get("confidence", 60)
        duration_hours = trade_metrics.get("duration_hours", 0)
        
        # Get prediction details
        pro_analysis = prediction.get("predictions", {}).get("professional_analysis", {})
        direction = pro_analysis.get("primary_scenario", "NEUTRAL") if pro_analysis else "NEUTRAL"
        
        # Mistake 1: Poor Risk-Reward Ratio
        if rr_ratio < 1.5 and outcome == "SL_HIT":
            mistakes.append("poor_rr_ratio")
        
        # Mistake 2: Ignored Sentiment (Counter-trend in wrong conditions)
        if sentiment == "extreme_greed" and direction in ["BUY", "LONG", "BULLISH"] and outcome == "SL_HIT":
            mistakes.append("ignored_greed_signal")
        elif sentiment == "extreme_fear" and direction in ["SELL", "SHORT", "BEARISH"] and outcome == "SL_HIT":
            mistakes.append("ignored_fear_signal")
        
        # Mistake 3: Wrong Volatility Assessment
        if volatility == "low" and direction in ["SELL", "SHORT", "BEARISH"] and outcome == "SL_HIT":
            mistakes.append("short_in_low_volatility")
        elif volatility == "high" and rr_ratio < 2.0 and outcome == "SL_HIT":
            mistakes.append("insufficient_rr_for_volatility")
        
        # Mistake 4: Overconfidence
        if confidence > 80 and outcome == "SL_HIT":
            mistakes.append("overconfident_loss")
        
        # Mistake 5: Rushed Entry (very quick hits)
        if duration_hours < 1 and outcome == "SL_HIT":
            mistakes.append("rushed_entry")
        
        # Mistake 6: Didn't Wait for Confirmation
        rsi = market_data.get("btc_rsi", 50)
        if direction in ["BUY", "LONG", "BULLISH"] and rsi > 75 and outcome == "SL_HIT":
            mistakes.append("bought_overbought")
        elif direction in ["SELL", "SHORT", "BEARISH"] and rsi < 25 and outcome == "SL_HIT":
            mistakes.append("sold_oversold")
        
        # Mistake 7: Ignored Support/Resistance
        entry_price = trade_metrics.get("entry_price", 0)
        # This would need support/resistance data to implement fully
        
        # Mistake 8: Wrong Time Session
        pred_hour = datetime.strptime(prediction["timestamp"], "%Y-%m-%d %H:%M:%S").hour
        if pred_hour in [0, 1, 2, 23] and outcome == "SL_HIT":  # Dead hours
            mistakes.append("bad_timing_session")
        
    except Exception as e:
        print(f"[WARN] Error identifying trade mistakes: {e}")
    
    return mistakes

def classify_time_session(hour):
    """Classify trading session based on hour"""
    if 0 <= hour < 6:
        return "asia_night"
    elif 6 <= hour < 12:
        return "asia_day"
    elif 12 <= hour < 18:
        return "europe"
    else:
        return "us_evening"

if __name__ == "__main__":
    # Check for test mode argument
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        config = load_config()
        config["test_mode"]["enabled"] = True
        print("[TEST] Test mode enabled for validation")
        validate_predictions()
    elif len(sys.argv) > 1 and sys.argv[1] == "--test-deep-analysis":
        # Test deep learning analysis functionality
        config = load_config()
        config["test_mode"]["enabled"] = True
        print("[TEST] Testing deep learning analysis...")
        
        # Load predictions for analysis
        prediction_file = "detailed_predictions.json"
        if config["test_mode"]["enabled"]:
            prediction_file = config["test_mode"]["output_prefix"] + prediction_file
        
        if os.path.exists(prediction_file):
            with open(prediction_file, "r") as f:
                predictions = json.load(f)
            
            if predictions:
                print(f"[TEST] Analyzing {len(predictions)} predictions...")
                
                # Generate weekly insights
                weekly_insights = generate_deep_learning_insights(predictions, "weekly")
                if "error" not in weekly_insights:
                    print("[TEST] Weekly analysis successful!")
                    save_deep_learning_insights(weekly_insights)
                    
                    # Format and display summary
                    summary = format_deep_insights_summary(weekly_insights)
                    print("\n" + "="*50)
                    print("WEEKLY DEEP LEARNING ANALYSIS PREVIEW:")
                    print("="*50)
                    # Remove HTML tags for console display
                    import re
                    clean_summary = re.sub(r'<[^>]+>', '', summary)
                    print(clean_summary)
                    print("="*50)
                    
                    # Test ML learning integration
                    try:
                        ml_enhancer = PredictionEnhancer()
                        ml_enhancer.learn_from_insights(weekly_insights)
                        print("[TEST] ML learning integration successful!")
                    except Exception as e:
                        print(f"[TEST] ML learning integration failed: {e}")
                else:
                    print(f"[TEST] Analysis failed: {weekly_insights['error']}")
            else:
                print("[TEST] No predictions found for analysis")
        else:
            print(f"[TEST] No prediction file found: {prediction_file}")
    else:
        validate_predictions()
